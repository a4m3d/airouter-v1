import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl


def verify_webapp_init_data(init_data: str, bot_token: str, max_age_seconds: int = 86400):
    """Verify Telegram Web App initData server-side per Telegram's official HMAC scheme.

    Returns the parsed `user` dict on success, or None on failure. The browser-supplied
    user id is NEVER trusted without this cryptographic verification.
    """
    if not init_data or not bot_token:
        return None
    try:
        parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    except Exception:
        return None

    received_hash = parsed.pop("hash", None)
    if not received_hash:
        return None

    data_check_string = "\n".join(f"{k}={parsed[k]}" for k in sorted(parsed.keys()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calc_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calc_hash, received_hash):
        return None

    auth_date = parsed.get("auth_date")
    if auth_date:
        try:
            if (time.time() - int(auth_date)) > max_age_seconds:
                return None
        except ValueError:
            return None

    try:
        return json.loads(parsed.get("user", "{}"))
    except Exception:
        return None
