import asyncio
import logging
import time

from app import key_manager as km
from app import job_manager as jm
from app import notifier
from app.providers.emergent import EmergentAdapter
from app.providers.errors import (
    classify_error, ErrorClass, FAILOVER_IMMEDIATELY, RETRYABLE_SAME_KEY, NO_FAILOVER,
)
from app.settings_store import get_settings

logger = logging.getLogger("router.engine")

adapter = EmergentAdapter()


class RouterError(Exception):
    def __init__(self, error_class: ErrorClass, message: str, http_status: int = 502):
        self.error_class = error_class
        self.message = message
        self.http_status = http_status
        super().__init__(message)


async def _mask_of(key_id):
    doc = await km._public_one(key_id)
    return doc.get("mask") if doc else "unknown"


async def run_chat(*, client_id, session_id, provider, model, messages, idempotency_key=None):
    """Execute a logical chat request with automatic failover across keys.

    Returns (content, meta). Raises RouterError when it cannot be completed.
    The logical job (session) is preserved across key changes.
    """
    settings = await get_settings()
    if settings.get("paused"):
        raise RouterError(ErrorClass.PROVIDER_ERROR, "Router is paused by administrator", 503)

    # Idempotency: replay a previously completed identical request.
    if idempotency_key:
        cached = await jm.find_completed_by_idempotency(client_id, idempotency_key)
        if cached and cached.get("result") is not None:
            return cached["result"], {"job_id": cached["job_id"], "request_id": cached["id"],
                                      "key_id": cached["key_id"], "replayed": True}

    system_message, prompt = None, None
    job = await jm.get_or_create_job(session_id, client_id, provider, model)
    step = await jm.next_step(job["id"])
    req = await jm.create_request(job["id"], session_id, client_id, provider, model, idempotency_key)
    request_id = req["id"]

    strategy = settings.get("routing_strategy", "priority")
    retry_count = int(settings.get("retry_count", 2))
    timeout = int(settings.get("request_timeout", 120))
    cooldown = int(settings.get("cooldown_seconds", 300))
    rate_cooldown = int(settings.get("rate_limit_cooldown_seconds", 60))
    max_tokens = int(settings.get("max_output_tokens", 8192))

    tried_keys = set()
    prev_key_id = None
    last_error = None

    while True:
        key = await km.select_key(strategy=strategy, exclude=tried_keys)
        if key is None:
            await jm.update_request(request_id, status="failed",
                                    error_type=(last_error.value if last_error else "NO_HEALTHY_KEYS"),
                                    action="NO_HEALTHY_KEYS")
            await jm.update_job(job["id"], status="failed")
            if settings["notifications"].get("on_no_healthy_keys"):
                await notifier.notify_no_keys()
            raise RouterError(last_error or ErrorClass.PROVIDER_ERROR,
                              "No healthy keys available to service the request", 503)

        tried_keys.add(key["id"])
        if prev_key_id and prev_key_id != key["id"]:
            await km.record_failover(prev_key_id)
            await jm.log_failover(job["id"], request_id, prev_key_id, key["id"],
                                  last_error.value if last_error else "unknown")
            await jm.update_job(job["id"], retry_count=len(tried_keys) - 1)
            if settings["notifications"].get("on_failover"):
                await notifier.notify_failover(
                    job["id"], await _mask_of(prev_key_id), key.get("mask"),
                    last_error.value if last_error else "unknown")

        await jm.update_request(request_id, status="running", key_id=key["id"], step=step)
        await jm.update_job(job["id"], current_key_id=key["id"], current_step=step, status="running")

        secret = await km.get_secret(key["id"])
        same_key_attempts = 0

        while True:
            same_key_attempts += 1
            await jm.update_request(request_id, attempts=len(tried_keys) - 1 + same_key_attempts)
            started = time.time()
            try:
                content = await adapter.chat(
                    api_key=secret, session_id=session_id, messages=messages,
                    provider=provider, model=model, timeout=timeout, max_tokens=max_tokens,
                )
                latency_ms = int((time.time() - started) * 1000)
                await km.record_success(key["id"], latency_ms)
                result_fields = {"status": "success", "key_id": key["id"], "latency_ms": latency_ms,
                                 "action": "SUCCESS"}
                if idempotency_key:
                    result_fields["result"] = content
                await jm.update_request(request_id, **result_fields)
                await jm.update_job(job["id"], current_key_id=key["id"], status="success")
                logger.info("Request %s key=%s Result: SUCCESS (%sms)", request_id, key["id"], latency_ms)
                return content, {"job_id": job["id"], "request_id": request_id,
                                 "key_id": key["id"], "key_mask": key.get("mask"),
                                 "step": step, "replayed": False}
            except Exception as exc:
                ec = classify_error(exc)
                last_error = ec
                logger.info("Request %s key=%s Error: %s Action: %s",
                            request_id, key["id"], ec.value,
                            "RETURN" if ec in NO_FAILOVER else "FAILOVER")

                await km.record_failure(key["id"], ec, cooldown, rate_cooldown)

                if ec == ErrorClass.AUTH_FAILED and settings["notifications"].get("on_key_auth_error"):
                    await notifier.notify_auth_error(key.get("mask"))
                if ec == ErrorClass.CREDIT_EXHAUSTED and settings["notifications"].get("on_key_exhausted"):
                    await notifier.notify_exhausted(key.get("mask"), None)

                if ec in NO_FAILOVER:
                    await jm.update_request(request_id, status="failed", error_type=ec.value,
                                            action="RETURN_ERROR")
                    await jm.update_job(job["id"], status="failed")
                    raise RouterError(ec, "Invalid request was rejected by the provider", 400)

                if ec in RETRYABLE_SAME_KEY and same_key_attempts <= retry_count:
                    await jm.update_request(request_id, error_type=ec.value, action="RETRY_SAME_KEY")
                    await asyncio.sleep(min(2 ** (same_key_attempts - 1), 5))
                    continue  # retry same key

                # Fail over to the next key (preserving the logical job)
                await jm.update_request(request_id, error_type=ec.value, action="FAILOVER",
                                        next_key_id=None)
                prev_key_id = key["id"]
                break  # break inner loop -> select next key
