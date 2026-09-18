import asyncio

from app.providers.errors import classify_error, ErrorClass


class E(Exception):
    def __init__(self, msg="", status=None):
        super().__init__(msg)
        if status is not None:
            self.status_code = status


def test_credit_exhausted():
    assert classify_error(E("You have insufficient credits", 402)) == ErrorClass.CREDIT_EXHAUSTED
    assert classify_error(E("exceeded your current quota")) == ErrorClass.CREDIT_EXHAUSTED


def test_rate_limit():
    assert classify_error(E("Rate limit reached", 429)) == ErrorClass.RATE_LIMIT


def test_auth_failed():
    assert classify_error(E("Invalid API key", 401)) == ErrorClass.AUTH_FAILED
    assert classify_error(E("unauthorized", 403)) == ErrorClass.AUTH_FAILED


def test_invalid_request():
    assert classify_error(E("model_not_found", 404)) == ErrorClass.INVALID_REQUEST
    assert classify_error(E("bad request", 400)) == ErrorClass.INVALID_REQUEST


def test_provider_error():
    assert classify_error(E("internal server error", 500)) == ErrorClass.PROVIDER_ERROR
    assert classify_error(E("overloaded", 503)) == ErrorClass.PROVIDER_ERROR


def test_timeout_and_network():
    assert classify_error(asyncio.TimeoutError()) == ErrorClass.TIMEOUT
    assert classify_error(E("Connection refused")) == ErrorClass.NETWORK


def test_unknown():
    assert classify_error(E("something weird happened")) == ErrorClass.UNKNOWN
