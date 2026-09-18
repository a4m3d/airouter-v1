import hashlib
import hmac
import time
from urllib.parse import urlencode

from app.security.crypto import encrypt, decrypt, mask, hash_client_key
from app.security.telegram_auth import verify_webapp_init_data
from app.logging_setup import scrub


def test_encrypt_decrypt_roundtrip():
    secret = "sk-emergent-SUPERSECRETVALUE123"
    blob = encrypt(secret)
    assert blob["ciphertext"] != secret
    assert secret not in blob["ciphertext"]
    assert decrypt(blob["ciphertext"], blob["nonce"]) == secret


def test_mask_hides_value():
    m = mask("sk-emergent-abcdEF12A91F")
    assert m.endswith("A91F")
    assert "abcd" not in m
    assert m.startswith("••••")


def test_client_key_hash_is_stable_and_opaque():
    k = "sk-router-abc"
    assert hash_client_key(k) == hash_client_key(k)
    assert k not in hash_client_key(k)


def _build_init_data(bot_token, user_id=42, valid=True):
    fields = {"user": '{"id": %d, "first_name": "Admin"}' % user_id,
              "auth_date": str(int(time.time()))}
    dcs = "\n".join(f"{k}={fields[k]}" for k in sorted(fields))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    h = hmac.new(secret, dcs.encode(), hashlib.sha256).hexdigest()
    if not valid:
        h = "deadbeef"
    fields["hash"] = h
    return urlencode(fields)


def test_telegram_auth_accepts_valid():
    token = "123:ABC"
    user = verify_webapp_init_data(_build_init_data(token, 42, True), token)
    assert user and str(user["id"]) == "42"


def test_telegram_auth_rejects_tampered():
    token = "123:ABC"
    assert verify_webapp_init_data(_build_init_data(token, 42, False), token) is None


def test_telegram_auth_rejects_wrong_token():
    good = _build_init_data("123:ABC", 42, True)
    assert verify_webapp_init_data(good, "999:XYZ") is None


def test_log_redaction():
    line = "Authorization: Bearer sk-emergent-LEAKME123 api_key=sk-router-LEAKME"
    out = scrub(line)
    assert "LEAKME" not in out
    assert "REDACTED" in out
