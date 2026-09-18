import secrets
import uuid
from datetime import datetime, timezone

from app.db import client_keys
from app.security.crypto import hash_client_key

def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _public(doc: dict) -> dict:
    return {
        "id": doc["id"],
        "name": doc.get("name"),
        "key_prefix": doc.get("key_prefix"),
        "enabled": doc.get("enabled", True),
        "revoked_at": doc.get("revoked_at"),
        "request_count": doc.get("request_count", 0),
        "rate_limit": doc.get("rate_limit"),
        "created_at": doc.get("created_at"),
    }


async def list_client_keys():
    docs = await client_keys.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return [_public(d) for d in docs]


async def create_client_key(name: str, rate_limit: int = None, plaintext: str = None):
    """Returns (public_doc, plaintext). Plaintext is shown ONCE and never stored."""
    plaintext = plaintext or ("sk-router-" + secrets.token_urlsafe(24))
    doc = {
        "id": str(uuid.uuid4()),
        "name": name or "client",
        "key_hash": hash_client_key(plaintext),
        "key_prefix": plaintext[:14],
        "enabled": True,
        "revoked_at": None,
        "request_count": 0,
        "rate_limit": rate_limit,
        "created_at": _now_iso(),
    }
    await client_keys.insert_one(dict(doc))
    return _public(doc), plaintext


async def revoke_client_key(key_id: str):
    await client_keys.update_one(
        {"id": key_id}, {"$set": {"enabled": False, "revoked_at": _now_iso()}}
    )


async def delete_client_key(key_id: str):
    res = await client_keys.delete_one({"id": key_id})
    return res.deleted_count > 0


async def rotate_client_key(key_id: str):
    doc = await client_keys.find_one({"id": key_id}, {"_id": 0})
    if not doc:
        return None, None
    plaintext = "sk-router-" + secrets.token_urlsafe(24)
    await client_keys.update_one(
        {"id": key_id},
        {"$set": {"key_hash": hash_client_key(plaintext), "key_prefix": plaintext[:14],
                  "enabled": True, "revoked_at": None}},
    )
    updated = await client_keys.find_one({"id": key_id}, {"_id": 0})
    return _public(updated), plaintext


async def touch_usage(key_id: str):
    await client_keys.update_one({"id": key_id}, {"$inc": {"request_count": 1}})
