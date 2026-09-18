import asyncio
import uuid
from datetime import datetime, timezone

from app.db import api_keys, health_checks
from app.providers.errors import ErrorClass
from app.security.crypto import encrypt, decrypt, mask

_select_lock = asyncio.Lock()


def _now():
    return datetime.now(timezone.utc)


def _iso(dt=None):
    return (dt or _now()).isoformat()


def public_key(doc: dict) -> dict:
    """Return a key document safe for the frontend/Telegram (NO credential)."""
    total = doc.get("request_count", 0)
    success = doc.get("success_count", 0)
    success_rate = round((success / total) * 100, 1) if total else None
    return {
        "id": doc["id"],
        "label": doc.get("label"),
        "provider": doc.get("provider", "emergent"),
        "mask": doc.get("mask"),
        "enabled": doc.get("enabled", True),
        "health_status": doc.get("health_status", "unknown"),
        "priority": doc.get("priority", 100),
        "request_count": total,
        "success_count": success,
        "failure_count": doc.get("failure_count", 0),
        "failover_count": doc.get("failover_count", 0),
        "success_rate": success_rate,
        "avg_latency_ms": doc.get("avg_latency_ms"),
        "last_used_at": doc.get("last_used_at"),
        "last_error_at": doc.get("last_error_at"),
        "last_error_type": doc.get("last_error_type"),
        "cooldown_until": doc.get("cooldown_until"),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }


async def list_keys():
    docs = await api_keys.find({}, {"_id": 0}).sort("priority", 1).to_list(1000)
    return [public_key(d) for d in docs]


async def add_key(secret: str, label: str, priority: int = None, provider: str = "emergent"):
    enc = encrypt(secret)
    if priority is None:
        count = await api_keys.count_documents({})
        priority = count + 1
    doc = {
        "id": str(uuid.uuid4()),
        "label": label or f"Key #{priority}",
        "provider": provider,
        "ciphertext": enc["ciphertext"],
        "nonce": enc["nonce"],
        "mask": mask(secret),
        "enabled": True,
        "health_status": "unknown",
        "priority": priority,
        "request_count": 0,
        "success_count": 0,
        "failure_count": 0,
        "failover_count": 0,
        "avg_latency_ms": None,
        "last_used_at": None,
        "last_error_at": None,
        "last_error_type": None,
        "cooldown_until": None,
        "created_at": _iso(),
        "updated_at": _iso(),
    }
    await api_keys.insert_one(dict(doc))
    return public_key(doc)


async def get_secret(key_id: str):
    doc = await api_keys.find_one({"id": key_id}, {"_id": 0})
    if not doc:
        return None
    return decrypt(doc["ciphertext"], doc["nonce"])


async def delete_key(key_id: str):
    res = await api_keys.delete_one({"id": key_id})
    return res.deleted_count > 0


async def set_enabled(key_id: str, enabled: bool):
    await api_keys.update_one(
        {"id": key_id},
        {"$set": {"enabled": enabled, "updated_at": _iso(),
                  **({"health_status": "unknown", "cooldown_until": None} if enabled else {})}},
    )
    return await _public_one(key_id)


async def set_priority(key_id: str, priority: int):
    await api_keys.update_one({"id": key_id}, {"$set": {"priority": priority, "updated_at": _iso()}})
    return await _public_one(key_id)


async def _public_one(key_id: str):
    doc = await api_keys.find_one({"id": key_id}, {"_id": 0})
    return public_key(doc) if doc else None


def _is_available(doc: dict) -> bool:
    if not doc.get("enabled", False):
        return False
    cd = doc.get("cooldown_until")
    if cd:
        try:
            if datetime.fromisoformat(cd) > _now():
                return False
        except ValueError:
            pass
    return doc.get("health_status") not in ("unhealthy",)


async def select_key(strategy: str = "priority", exclude: set = None):
    """Atomically select an available key and stamp last_used_at to avoid races."""
    exclude = exclude or set()
    async with _select_lock:
        docs = await api_keys.find({"enabled": True}, {"_id": 0}).to_list(1000)
        # Auto-clear expired cooldowns
        candidates = []
        for d in docs:
            if d["id"] in exclude:
                continue
            cd = d.get("cooldown_until")
            if cd:
                try:
                    if datetime.fromisoformat(cd) <= _now():
                        await api_keys.update_one(
                            {"id": d["id"]},
                            {"$set": {"cooldown_until": None, "health_status": "unknown", "updated_at": _iso()}},
                        )
                        d["cooldown_until"] = None
                        d["health_status"] = "unknown"
                except ValueError:
                    pass
            if _is_available(d):
                candidates.append(d)

        if not candidates:
            return None

        if strategy == "round_robin" or strategy == "lru":
            candidates.sort(key=lambda d: (d.get("last_used_at") or "", d.get("priority", 100)))
        else:  # priority (default)
            candidates.sort(key=lambda d: (d.get("priority", 100), d.get("last_used_at") or ""))

        chosen = candidates[0]
        await api_keys.update_one({"id": chosen["id"]}, {"$set": {"last_used_at": _iso()}})
        return chosen


async def record_success(key_id: str, latency_ms: int):
    doc = await api_keys.find_one({"id": key_id}, {"_id": 0})
    prev = doc.get("avg_latency_ms") if doc else None
    new_latency = latency_ms if prev is None else int(prev * 0.7 + latency_ms * 0.3)
    await api_keys.update_one(
        {"id": key_id},
        {
            "$inc": {"request_count": 1, "success_count": 1},
            "$set": {
                "health_status": "healthy",
                "cooldown_until": None,
                "last_used_at": _iso(),
                "avg_latency_ms": new_latency,
                "updated_at": _iso(),
            },
        },
    )


async def record_failure(key_id: str, error_class: ErrorClass, cooldown_seconds: int, rate_cooldown_seconds: int):
    from datetime import timedelta

    update_set = {
        "last_error_at": _iso(),
        "last_error_type": error_class.value,
        "updated_at": _iso(),
    }
    inc = {"request_count": 1, "failure_count": 1}

    if error_class == ErrorClass.CREDIT_EXHAUSTED:
        update_set["health_status"] = "exhausted"
        update_set["cooldown_until"] = _iso(_now() + timedelta(seconds=cooldown_seconds))
    elif error_class == ErrorClass.RATE_LIMIT:
        update_set["health_status"] = "cooldown"
        update_set["cooldown_until"] = _iso(_now() + timedelta(seconds=rate_cooldown_seconds))
    elif error_class == ErrorClass.AUTH_FAILED:
        update_set["health_status"] = "unhealthy"
        update_set["enabled"] = False  # auto-disable a key whose credential is rejected

    await api_keys.update_one({"id": key_id}, {"$set": update_set, "$inc": inc})


async def record_failover(key_id: str):
    await api_keys.update_one({"id": key_id}, {"$inc": {"failover_count": 1}})


async def record_health_check(key_id: str, ok: bool, error_type=None, latency_ms=None):
    await health_checks.insert_one({
        "id": str(uuid.uuid4()),
        "key_id": key_id,
        "ok": ok,
        "error_type": error_type,
        "latency_ms": latency_ms,
        "created_at": _iso(),
    })


async def counts():
    docs = await api_keys.find({}, {"_id": 0}).to_list(1000)
    healthy = cooldown = exhausted = 0
    for d in docs:
        if not d.get("enabled"):
            continue
        st = d.get("health_status", "unknown")
        if st == "cooldown":
            cooldown += 1
        elif st == "exhausted":
            exhausted += 1
        elif st in ("healthy", "unknown"):
            healthy += 1
    return {"total": len(docs), "healthy": healthy, "cooldown": cooldown, "exhausted": exhausted}
