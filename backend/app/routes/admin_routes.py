import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app import key_manager as km
from app import client_keys as ck
from app.db import jobs, requests, failovers, audit_logs
from app.config import SUPPORTED_MODELS, DEFAULT_PROVIDER, DEFAULT_MODEL
from app.engine import adapter, RouterError
from app.providers.errors import classify_error
from app.security.auth import require_admin
from app.settings_store import get_settings, update_settings

router = APIRouter(prefix="/api/admin")


# ---------- request models ----------
class AddKeyBody(BaseModel):
    secret: str
    label: str | None = None
    priority: int | None = None
    provider: str = "emergent"


class PriorityBody(BaseModel):
    priority: int


class EnabledBody(BaseModel):
    enabled: bool


class SettingsBody(BaseModel):
    routing_strategy: str | None = None
    retry_count: int | None = None
    cooldown_seconds: int | None = None
    rate_limit_cooldown_seconds: int | None = None
    request_timeout: int | None = None
    max_output_tokens: int | None = None
    max_concurrent_jobs: int | None = None
    health_check_interval: int | None = None
    logging_level: str | None = None
    paused: bool | None = None
    telegram_admin_ids: list | None = None
    notifications: dict | None = None


class ClientKeyBody(BaseModel):
    name: str
    rate_limit: int | None = None


async def _audit(actor, action, target=None, meta=None):
    await audit_logs.insert_one({
        "actor": actor, "action": action, "target": target,
        "meta": meta or {}, "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })


# ---------- dashboard ----------
@router.get("/dashboard")
async def dashboard(admin=Depends(require_admin)):
    key_counts = await km.counts()
    active_jobs = await jobs.count_documents({"status": "running"})
    completed_jobs = await jobs.count_documents({"status": "success"})
    today = time.strftime("%Y-%m-%d", time.gmtime())
    total_today = await requests.count_documents({"created_at": {"$regex": f"^{today}"}})
    success_today = await requests.count_documents({"created_at": {"$regex": f"^{today}"}, "status": "success"})
    failed_today = await requests.count_documents({"created_at": {"$regex": f"^{today}"}, "status": "failed"})
    failovers_today = await failovers.count_documents({"created_at": {"$regex": f"^{today}"}})
    settings = await get_settings()
    return {
        "system_online": not settings.get("paused", False),
        "paused": settings.get("paused", False),
        "keys": key_counts,
        "active_jobs": active_jobs,
        "completed_jobs": completed_jobs,
        "requests_today": total_today,
        "successful_today": success_today,
        "failed_today": failed_today,
        "failovers_today": failovers_today,
    }


# ---------- keys ----------
@router.get("/keys")
async def get_keys(admin=Depends(require_admin)):
    return await km.list_keys()


@router.post("/keys")
async def create_key(body: AddKeyBody, admin=Depends(require_admin)):
    if not body.secret or len(body.secret) < 8:
        raise HTTPException(status_code=400, detail="Invalid key value")
    # Validate connectivity before storing (best-effort, short timeout)
    test = await _test_secret(body.secret, body.provider)
    key = await km.add_key(body.secret, body.label, body.priority, body.provider)
    await km.record_health_check(key["id"], test["ok"], test.get("error_type"), test.get("latency_ms"))
    if test["ok"]:
        await km.record_success(key["id"], test.get("latency_ms", 0))
    await _audit(admin["sub"], "add_key", key["id"])
    return {"key": key, "validation": test}


@router.delete("/keys/{key_id}")
async def remove_key(key_id: str, admin=Depends(require_admin)):
    ok = await km.delete_key(key_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Key not found")
    await _audit(admin["sub"], "delete_key", key_id)
    return {"deleted": True}


@router.post("/keys/{key_id}/enabled")
async def toggle_key(key_id: str, body: EnabledBody, admin=Depends(require_admin)):
    res = await km.set_enabled(key_id, body.enabled)
    if not res:
        raise HTTPException(status_code=404, detail="Key not found")
    await _audit(admin["sub"], "enable_key" if body.enabled else "disable_key", key_id)
    return res


@router.post("/keys/{key_id}/priority")
async def change_priority(key_id: str, body: PriorityBody, admin=Depends(require_admin)):
    res = await km.set_priority(key_id, body.priority)
    if not res:
        raise HTTPException(status_code=404, detail="Key not found")
    return res


@router.post("/keys/{key_id}/test")
async def test_key(key_id: str, admin=Depends(require_admin)):
    secret = await km.get_secret(key_id)
    if not secret:
        raise HTTPException(status_code=404, detail="Key not found")
    doc = await km._public_one(key_id)
    test = await _test_secret(secret, doc.get("provider", "emergent"))
    await km.record_health_check(key_id, test["ok"], test.get("error_type"), test.get("latency_ms"))
    if test["ok"]:
        await km.record_success(key_id, test.get("latency_ms", 0))
    else:
        settings = await get_settings()
        from app.providers.errors import ErrorClass
        await km.record_failure(key_id, ErrorClass(test["error_type"]),
                                settings["cooldown_seconds"], settings["rate_limit_cooldown_seconds"])
    return {"result": test, "key": await km._public_one(key_id)}


async def _test_secret(secret: str, provider: str):
    model = DEFAULT_MODEL if provider in ("emergent", "openai") else SUPPORTED_MODELS.get(provider, [DEFAULT_MODEL])[0]
    prov = "openai" if provider == "emergent" else provider
    started = time.time()
    try:
        await adapter.chat(api_key=secret, session_id=f"healthcheck-{int(started)}",
                           messages=[{"role": "system", "content": "You are a health check."},
                                     {"role": "user", "content": "Reply with OK."}],
                           provider=prov, model=model, timeout=30, max_tokens=16)
        return {"ok": True, "latency_ms": int((time.time() - started) * 1000)}
    except Exception as exc:
        return {"ok": False, "error_type": classify_error(exc).value,
                "latency_ms": int((time.time() - started) * 1000)}


# ---------- jobs ----------
@router.get("/jobs")
async def list_jobs(admin=Depends(require_admin)):
    docs = await jobs.find({}, {"_id": 0}).sort("updated_at", -1).limit(100).to_list(100)
    return docs


@router.get("/jobs/{job_id}")
async def job_detail(job_id: str, admin=Depends(require_admin)):
    job = await jobs.find_one({"id": job_id}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    reqs = await requests.find({"job_id": job_id}, {"_id": 0, "result": 0}).sort("created_at", 1).to_list(500)
    fos = await failovers.find({"job_id": job_id}, {"_id": 0}).sort("created_at", 1).to_list(500)
    return {"job": job, "requests": reqs, "failovers": fos}


# ---------- usage ----------
@router.get("/usage")
async def usage(admin=Depends(require_admin)):
    keys = await km.list_keys()
    total = await requests.count_documents({})
    success = await requests.count_documents({"status": "success"})
    failed = await requests.count_documents({"status": "failed"})
    total_failovers = await failovers.count_documents({})
    # error breakdown
    pipeline = [{"$match": {"error_type": {"$ne": None}}},
                {"$group": {"_id": "$error_type", "count": {"$sum": 1}}}]
    breakdown = {row["_id"]: row["count"] async for row in requests.aggregate(pipeline)}
    return {
        "total_requests": total,
        "successful": success,
        "failed": failed,
        "failovers": total_failovers,
        "error_breakdown": breakdown,
        "per_key": [{"id": k["id"], "label": k["label"], "mask": k["mask"],
                     "requests": k["request_count"], "success": k["success_count"],
                     "failures": k["failure_count"], "failovers": k["failover_count"],
                     "avg_latency_ms": k["avg_latency_ms"]} for k in keys],
        "note": "Credit balances are not shown: the provider does not expose a reliable programmatic balance endpoint.",
    }


# ---------- health ----------
@router.get("/health")
async def health(admin=Depends(require_admin)):
    return {"keys": await km.list_keys()}


@router.post("/health/check")
async def run_health_check(admin=Depends(require_admin)):
    results = []
    for k in await km.list_keys():
        secret = await km.get_secret(k["id"])
        if not secret:
            continue
        test = await _test_secret(secret, k.get("provider", "emergent"))
        await km.record_health_check(k["id"], test["ok"], test.get("error_type"), test.get("latency_ms"))
        if test["ok"]:
            await km.record_success(k["id"], test.get("latency_ms", 0))
        results.append({"key_id": k["id"], "mask": k["mask"], **test})
    return {"results": results, "keys": await km.list_keys()}


# ---------- logs ----------
@router.get("/logs")
async def logs(status: str | None = None, admin=Depends(require_admin)):
    q = {}
    if status:
        q["status"] = status
    docs = await requests.find(q, {"_id": 0, "result": 0}).sort("created_at", -1).limit(200).to_list(200)
    return docs


# ---------- settings ----------
@router.get("/settings")
async def read_settings(admin=Depends(require_admin)):
    return await get_settings()


@router.put("/settings")
async def write_settings(body: SettingsBody, admin=Depends(require_admin)):
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    await _audit(admin["sub"], "update_settings", meta={"fields": list(patch.keys())})
    return await update_settings(patch)


@router.post("/pause")
async def pause(admin=Depends(require_admin)):
    return await update_settings({"paused": True})


@router.post("/resume")
async def resume(admin=Depends(require_admin)):
    return await update_settings({"paused": False})


# ---------- client keys ----------
@router.get("/client-keys")
async def get_client_keys(admin=Depends(require_admin)):
    return await ck.list_client_keys()


@router.post("/client-keys")
async def create_client_key(body: ClientKeyBody, admin=Depends(require_admin)):
    pub, plaintext = await ck.create_client_key(body.name, body.rate_limit)
    await _audit(admin["sub"], "create_client_key", pub["id"])
    return {"client_key": pub, "plaintext": plaintext,
            "warning": "This is the only time the full key is shown. Store it securely."}


@router.post("/client-keys/{key_id}/revoke")
async def revoke_client_key(key_id: str, admin=Depends(require_admin)):
    await ck.revoke_client_key(key_id)
    await _audit(admin["sub"], "revoke_client_key", key_id)
    return {"revoked": True}


@router.delete("/client-keys/{key_id}")
async def delete_client_key(key_id: str, admin=Depends(require_admin)):
    ok = await ck.delete_client_key(key_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Client key not found")
    await _audit(admin["sub"], "delete_client_key", key_id)
    return {"deleted": True}


@router.post("/client-keys/{key_id}/rotate")
async def rotate_client_key(key_id: str, admin=Depends(require_admin)):
    pub, plaintext = await ck.rotate_client_key(key_id)
    if not pub:
        raise HTTPException(status_code=404, detail="Client key not found")
    await _audit(admin["sub"], "rotate_client_key", key_id)
    return {"client_key": pub, "plaintext": plaintext,
            "warning": "This is the only time the full key is shown. Store it securely."}
