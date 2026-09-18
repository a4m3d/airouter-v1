import os

# Default router settings. Persisted in DB (settings collection) and editable via admin API.
DEFAULT_SETTINGS = {
    "routing_strategy": "priority",      # priority | round_robin | lru
    "retry_count": 2,                    # same-key retries for transient errors
    "cooldown_seconds": 300,             # cooldown after credit exhaustion
    "rate_limit_cooldown_seconds": 60,   # cooldown after a rate limit
    "request_timeout": 120,              # seconds for a provider request
    "max_concurrent_jobs": 20,
    "health_check_interval": 0,          # 0 = disabled auto checks (avoid spend); manual only
    "logging_level": "INFO",
    "paused": False,
    "notifications": {
        "on_failover": True,
        "on_key_exhausted": True,
        "on_key_auth_error": True,
        "on_no_healthy_keys": True,
    },
}

SUPPORTED_MODELS = {
    "openai": [
        "gpt-5.4", "gpt-5.4-mini", "gpt-5.2", "gpt-5", "gpt-5-mini",
        "gpt-4o", "gpt-4.1", "gpt-4.1-mini", "o3", "o4-mini",
    ],
    "anthropic": [
        "claude-sonnet-4-6", "claude-opus-4-7", "claude-haiku-4-5-20251001",
        "claude-sonnet-4-5-20250929",
    ],
    "gemini": [
        "gemini-3.1-pro-preview", "gemini-3-flash-preview",
        "gemini-2.5-pro", "gemini-2.5-flash",
    ],
}

DEFAULT_PROVIDER = "openai"
DEFAULT_MODEL = "gpt-5.4"


def admin_ids() -> set:
    raw = os.environ.get("TELEGRAM_ADMIN_IDS", "") or ""
    ids = set()
    for part in raw.replace(" ", "").split(","):
        if part.strip():
            ids.add(str(part.strip()))
    return ids
