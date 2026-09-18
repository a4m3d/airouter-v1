import asyncio
from enum import Enum


class ErrorClass(str, Enum):
    CREDIT_EXHAUSTED = "CREDIT_EXHAUSTED"
    RATE_LIMIT = "RATE_LIMIT"
    AUTH_FAILED = "AUTH_FAILED"
    INVALID_REQUEST = "INVALID_REQUEST"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    TIMEOUT = "TIMEOUT"
    NETWORK = "NETWORK"
    UNKNOWN = "UNKNOWN"


# Classes that should immediately fail over to another key (not retry the same key).
FAILOVER_IMMEDIATELY = {
    ErrorClass.CREDIT_EXHAUSTED,
    ErrorClass.RATE_LIMIT,
    ErrorClass.AUTH_FAILED,
}
# Classes safe to retry on the SAME key a few times before failing over.
RETRYABLE_SAME_KEY = {
    ErrorClass.PROVIDER_ERROR,
    ErrorClass.TIMEOUT,
    ErrorClass.NETWORK,
    ErrorClass.UNKNOWN,
}
# Never retry/failover: the request itself is bad; return the error to the caller.
NO_FAILOVER = {ErrorClass.INVALID_REQUEST}


def _status_code(exc: Exception):
    for attr in ("status_code", "code", "http_status", "status"):
        val = getattr(exc, attr, None)
        if isinstance(val, int):
            return val
    resp = getattr(exc, "response", None)
    if resp is not None:
        sc = getattr(resp, "status_code", None)
        if isinstance(sc, int):
            return sc
    return None


def classify_error(exc: Exception) -> ErrorClass:
    """Best-effort classification of provider/library errors.

    We do not invent provider error codes: we inspect the exception type, any HTTP
    status code it carries, and its message text. When ambiguous we return UNKNOWN
    and apply conservative retry/failover rules.
    """
    if isinstance(exc, (asyncio.TimeoutError,)):
        return ErrorClass.TIMEOUT

    name = type(exc).__name__.lower()
    msg = (str(exc) or "").lower()
    status = _status_code(exc)

    # Timeouts
    if "timeout" in name or "timeout" in msg or "timed out" in msg:
        return ErrorClass.TIMEOUT

    # Network / connection
    if any(k in name for k in ("connection", "connect")) or any(
        k in msg for k in ("connection error", "connection refused", "failed to establish", "network")
    ):
        return ErrorClass.NETWORK

    # Credit / quota / billing exhaustion
    if status == 402 or any(
        k in msg for k in ("insufficient", "quota", "credit", "billing", "exceeded your current quota", "payment required")
    ):
        return ErrorClass.CREDIT_EXHAUSTED

    # Rate limit
    if status == 429 or "rate limit" in msg or "too many requests" in name or "toomany" in name:
        return ErrorClass.RATE_LIMIT

    # Authentication / permission
    if status in (401, 403) or any(
        k in msg for k in ("authentication", "invalid api key", "incorrect api key", "unauthorized", "permission", "forbidden", "invalid_api_key")
    ) or "auth" in name:
        return ErrorClass.AUTH_FAILED

    # Invalid request (bad model, malformed body, not found)
    if status in (400, 404, 422) or any(
        k in msg for k in ("invalid request", "bad request", "not found", "model_not_found", "does not exist", "unsupported", "validation")
    ):
        return ErrorClass.INVALID_REQUEST

    # Provider server errors
    if (status is not None and 500 <= status <= 599) or any(
        k in msg for k in ("internal server error", "overloaded", "service unavailable", "bad gateway", "server error")
    ):
        return ErrorClass.PROVIDER_ERROR

    return ErrorClass.UNKNOWN
