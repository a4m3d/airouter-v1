import uuid
from datetime import datetime, timezone

from app.db import jobs, requests, failovers


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


async def get_or_create_job(session_id: str, client_id: str, provider: str, model: str):
    """A logical job is keyed by session_id + client. Failover does NOT create a new job."""
    existing = await jobs.find_one({"session_id": session_id, "client_id": client_id}, {"_id": 0})
    if existing and existing.get("status") not in ("failed",):
        return existing
    doc = {
        "id": new_id("job"),
        "session_id": session_id,
        "client_id": client_id,
        "provider": provider,
        "model": model,
        "current_key_id": None,
        "current_step": existing.get("current_step", 0) if existing else 0,
        "status": "running",
        "retry_count": 0,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    await jobs.insert_one(dict(doc))
    return doc


async def next_step(job_id: str) -> int:
    doc = await jobs.find_one_and_update(
        {"id": job_id},
        {"$inc": {"current_step": 1}, "$set": {"updated_at": _now_iso()}},
        return_document=True,
    )
    return doc.get("current_step", 1) if doc else 1


async def update_job(job_id: str, **fields):
    fields["updated_at"] = _now_iso()
    await jobs.update_one({"id": job_id}, {"$set": fields})


async def create_request(job_id, session_id, client_id, provider, model, idempotency_key):
    doc = {
        "id": new_id("req"),
        "job_id": job_id,
        "session_id": session_id,
        "client_id": client_id,
        "provider": provider,
        "model": model,
        "idempotency_key": idempotency_key,
        "key_id": None,
        "status": "pending",
        "error_type": None,
        "action": None,
        "next_key_id": None,
        "latency_ms": None,
        "attempts": 0,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "result": None,  # cached only when idempotency_key provided
    }
    await requests.insert_one(dict(doc))
    return doc


async def find_completed_by_idempotency(client_id: str, idempotency_key: str):
    if not idempotency_key:
        return None
    return await requests.find_one(
        {"client_id": client_id, "idempotency_key": idempotency_key, "status": "success"},
        {"_id": 0},
    )


async def update_request(request_id: str, **fields):
    fields["updated_at"] = _now_iso()
    await requests.update_one({"id": request_id}, {"$set": fields})


async def log_failover(job_id, request_id, from_key_id, to_key_id, reason):
    await failovers.insert_one({
        "id": new_id("fo"),
        "job_id": job_id,
        "request_id": request_id,
        "from_key_id": from_key_id,
        "to_key_id": to_key_id,
        "reason": reason,
        "created_at": _now_iso(),
    })


async def recover_stale_jobs():
    """On restart, mark orphaned running requests as failed (cannot be safely resumed
    mid-flight). Completed requests with idempotency keys remain replayable."""
    n = await requests.update_many(
        {"status": {"$in": ["pending", "running"]}},
        {"$set": {"status": "interrupted", "updated_at": _now_iso(),
                  "action": "INTERRUPTED_ON_RESTART"}},
    )
    return n.modified_count
