import json
import time
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app import key_manager as km
from app import job_manager as jm
from app import client_keys as ck
from app import notifier
from app.config import SUPPORTED_MODELS, DEFAULT_MODEL
from app.engine import run_chat, adapter, RouterError
from app.providers.emergent import flatten_messages
from app.providers.errors import classify_error, ErrorClass, NO_FAILOVER
from app.security.auth import require_client
from app.settings_store import get_settings

router = APIRouter(prefix="/api/v1")


def _resolve_provider_model(model: str):
    """Map an OpenAI-style model name to (provider, model). Unknown models default
    to openai; we never invent unsupported models."""
    if not model:
        return "openai", DEFAULT_MODEL
    for provider, models in SUPPORTED_MODELS.items():
        if model in models:
            return provider, model
    if model.startswith("claude"):
        return "anthropic", model
    if model.startswith("gemini"):
        return "gemini", model
    return "openai", model


@router.get("/models")
async def list_models(client=Depends(require_client)):
    data = []
    for provider, models in SUPPORTED_MODELS.items():
        for m in models:
            data.append({"id": m, "object": "model", "owned_by": provider})
    return {"object": "list", "data": data}


@router.post("/chat/completions")
async def chat_completions(
    request: Request,
    client=Depends(require_client),
    idempotency_key: str = Header(None, alias="Idempotency-Key"),
):
    body = await request.json()
    messages = body.get("messages")
    if not messages or not isinstance(messages, list):
        raise HTTPException(status_code=400, detail="'messages' is required")

    model = body.get("model") or DEFAULT_MODEL
    provider, model = _resolve_provider_model(model)
    stream = bool(body.get("stream", False))
    session_id = (body.get("session_id") or body.get("user")
                  or request.headers.get("X-Session-Id") or f"sess_{uuid.uuid4().hex[:12]}")
    client_id = client["id"]
    await ck.touch_usage(client_id)

    if stream:
        return await _stream_completion(client_id, session_id, provider, model, messages)

    try:
        content, meta = await run_chat(
            client_id=client_id, session_id=session_id, provider=provider,
            model=model, messages=messages, idempotency_key=idempotency_key,
        )
    except RouterError as e:
        return JSONResponse(
            status_code=e.http_status,
            content={"error": {"message": e.message, "type": e.error_class.value, "code": e.error_class.value}},
        )

    return {
        "id": f"chatcmpl-{meta['request_id']}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": content},
                     "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "x_router": {"job_id": meta["job_id"], "key": meta.get("key_mask"), "replayed": meta.get("replayed")},
    }


async def _stream_completion(client_id, session_id, provider, model, messages):
    """SSE streaming. Failover is only safe BEFORE the first token is emitted
    (a partially streamed response cannot be transferred between keys)."""
    settings = await get_settings()
    timeout = int(settings.get("request_timeout", 120))
    retry_count = int(settings.get("retry_count", 2))
    strategy = settings.get("routing_strategy", "priority")
    system_message, prompt = flatten_messages(messages)

    job = await jm.get_or_create_job(session_id, client_id, provider, model)
    step = await jm.next_step(job["id"])
    req = await jm.create_request(job["id"], session_id, client_id, provider, model, None)
    request_id = req["id"]
    completion_id = f"chatcmpl-{request_id}"

    async def gen():
        tried = set()
        prev_key_id = None
        first_token_sent = False
        while True:
            key = await km.select_key(strategy=strategy, exclude=tried)
            if key is None:
                await jm.update_request(request_id, status="failed", action="NO_HEALTHY_KEYS")
                await jm.update_job(job["id"], status="failed")
                err = {"error": {"message": "No healthy keys available", "type": "NO_HEALTHY_KEYS"}}
                yield f"data: {json.dumps(err)}\n\n"
                yield "data: [DONE]\n\n"
                return
            tried.add(key["id"])
            if prev_key_id and prev_key_id != key["id"]:
                await km.record_failover(prev_key_id)
                await jm.log_failover(job["id"], request_id, prev_key_id, key["id"], "stream_failover")
            await jm.update_request(request_id, status="running", key_id=key["id"], step=step)
            await jm.update_job(job["id"], current_key_id=key["id"], current_step=step, status="running")
            secret = await km.get_secret(key["id"])
            started = time.time()
            try:
                async for delta in adapter.stream(
                    api_key=secret, session_id=session_id, system_message=system_message,
                    prompt=prompt, provider=provider, model=model,
                ):
                    if not delta:
                        continue
                    first_token_sent = True
                    chunk = {"id": completion_id, "object": "chat.completion.chunk",
                             "created": int(time.time()), "model": model,
                             "choices": [{"index": 0, "delta": {"content": delta}, "finish_reason": None}]}
                    yield f"data: {json.dumps(chunk)}\n\n"
                # done
                await km.record_success(key["id"], int((time.time() - started) * 1000))
                await jm.update_request(request_id, status="success", key_id=key["id"], action="SUCCESS")
                await jm.update_job(job["id"], status="success")
                final = {"id": completion_id, "object": "chat.completion.chunk",
                         "created": int(time.time()), "model": model,
                         "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}
                yield f"data: {json.dumps(final)}\n\n"
                yield "data: [DONE]\n\n"
                return
            except Exception as exc:
                ec = classify_error(exc)
                await km.record_failure(key["id"], ec, settings["cooldown_seconds"],
                                        settings["rate_limit_cooldown_seconds"])
                if first_token_sent:
                    # Cannot safely fail over mid-stream; report and end.
                    await jm.update_request(request_id, status="failed", error_type=ec.value,
                                            action="MIDSTREAM_ABORT")
                    await jm.update_job(job["id"], status="failed")
                    err = {"error": {"message": "Stream interrupted; cannot fail over mid-response",
                                     "type": ec.value}}
                    yield f"data: {json.dumps(err)}\n\n"
                    yield "data: [DONE]\n\n"
                    return
                if ec in NO_FAILOVER:
                    await jm.update_request(request_id, status="failed", error_type=ec.value,
                                            action="RETURN_ERROR")
                    await jm.update_job(job["id"], status="failed")
                    err = {"error": {"message": "Invalid request", "type": ec.value}}
                    yield f"data: {json.dumps(err)}\n\n"
                    yield "data: [DONE]\n\n"
                    return
                await jm.update_request(request_id, error_type=ec.value, action="FAILOVER")
                prev_key_id = key["id"]
                continue  # pre-token failover to next key

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
