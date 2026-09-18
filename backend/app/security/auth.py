import os
import time

import jwt
from fastapi import Depends, Header, HTTPException

from app.db import client_keys
from app.security.crypto import hash_client_key

ALGO = "HS256"


def _jwt_secret() -> str:
    secret = os.environ.get("ADMIN_JWT_SECRET")
    if not secret:
        raise RuntimeError("ADMIN_JWT_SECRET not configured")
    return secret


def create_admin_token(subject: str, source: str) -> str:
    payload = {
        "sub": str(subject),
        "src": source,          # "telegram" | "admin_token"
        "role": "admin",
        "iat": int(time.time()),
        "exp": int(time.time()) + 12 * 3600,
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=ALGO)


async def require_admin(authorization: str = Header(None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing admin token")
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = jwt.decode(token, _jwt_secret(), algorithms=[ALGO])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid admin token")
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    return payload


async def require_client(authorization: str = Header(None)) -> dict:
    """Authenticate an external application/coding-agent by its router client key."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing router API key")
    key = authorization.split(" ", 1)[1].strip()
    doc = await client_keys.find_one({"key_hash": hash_client_key(key)}, {"_id": 0})
    if not doc or not doc.get("enabled", False) or doc.get("revoked_at"):
        raise HTTPException(status_code=401, detail="Invalid or revoked router API key")
    return doc
