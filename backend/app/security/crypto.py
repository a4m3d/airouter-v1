import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# AES-256-GCM authenticated encryption for provider credentials.
# The master key lives ONLY in the backend environment (ENCRYPTION_MASTER_KEY),
# never in the database, frontend, logs, Telegram or Git.


def _master_key() -> bytes:
    raw = os.environ.get("ENCRYPTION_MASTER_KEY")
    if not raw:
        raise RuntimeError("ENCRYPTION_MASTER_KEY is not configured")
    try:
        key = base64.b64decode(raw)
    except Exception as exc:
        raise RuntimeError("ENCRYPTION_MASTER_KEY must be base64-encoded") from exc
    if len(key) != 32:
        raise RuntimeError("ENCRYPTION_MASTER_KEY must decode to 32 bytes (AES-256)")
    return key


def encrypt(plaintext: str) -> dict:
    nonce = os.urandom(12)
    ct = AESGCM(_master_key()).encrypt(nonce, plaintext.encode("utf-8"), None)
    return {
        "ciphertext": base64.b64encode(ct).decode("ascii"),
        "nonce": base64.b64encode(nonce).decode("ascii"),
    }


def decrypt(ciphertext_b64: str, nonce_b64: str) -> str:
    ct = base64.b64decode(ciphertext_b64)
    nonce = base64.b64decode(nonce_b64)
    return AESGCM(_master_key()).decrypt(nonce, ct, None).decode("utf-8")


def mask(secret: str) -> str:
    if not secret:
        return "••••••••"
    tail = secret[-4:] if len(secret) >= 4 else secret
    return "••••••••" + tail


def hash_client_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()
