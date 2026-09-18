"""Failover / job-continuity unit tests with a mocked provider (no network, no DB).

We monkeypatch the engine's key_manager, job_manager, settings and adapter so the
control-flow (retry policy, failover across keys, job continuity, idempotency,
no-failover-on-invalid) is verified deterministically.
"""
import asyncio

import app.engine as engine
from app.providers.errors import ErrorClass


class Boom(Exception):
    def __init__(self, msg, status=None):
        super().__init__(msg)
        if status is not None:
            self.status_code = status


def install_fakes(monkeypatch, keys, adapter_behaviour):
    """keys: ordered list of key dicts. adapter_behaviour: dict key_id -> callable()."""
    state = {"selected": [], "failures": [], "failovers": [], "requests": {}}

    async def select_key(strategy="priority", exclude=None):
        exclude = exclude or set()
        for k in keys:
            if k["id"] not in exclude and k.get("_available", True):
                state["selected"].append(k["id"])
                return k
        return None

    async def get_secret(kid):
        return f"secret-{kid}"

    async def record_success(kid, latency):
        state.setdefault("success", []).append(kid)

    async def record_failure(kid, ec, c, r):
        state["failures"].append((kid, ec.value))
        if ec in (ErrorClass.CREDIT_EXHAUSTED, ErrorClass.AUTH_FAILED):
            for k in keys:
                if k["id"] == kid:
                    k["_available"] = False

    async def record_failover(kid):
        state["failovers"].append(kid)

    async def _public_one(kid):
        return {"mask": f"••••{kid}"}

    monkeypatch.setattr(engine.km, "select_key", select_key)
    monkeypatch.setattr(engine.km, "get_secret", get_secret)
    monkeypatch.setattr(engine.km, "record_success", record_success)
    monkeypatch.setattr(engine.km, "record_failure", record_failure)
    monkeypatch.setattr(engine.km, "record_failover", record_failover)
    monkeypatch.setattr(engine.km, "_public_one", _public_one)

    async def get_or_create_job(session_id, client_id, provider, model):
        return {"id": "job_test", "session_id": session_id, "current_step": 0}

    async def next_step(job_id):
        return 1

    async def create_request(job_id, session_id, client_id, provider, model, idem):
        return {"id": "req_test", "job_id": job_id}

    async def update_request(rid, **f):
        state["requests"][rid] = f

    async def update_job(jid, **f):
        pass

    async def log_failover(*a, **k):
        pass

    async def find_completed_by_idempotency(client_id, idem):
        return None

    monkeypatch.setattr(engine.jm, "get_or_create_job", get_or_create_job)
    monkeypatch.setattr(engine.jm, "next_step", next_step)
    monkeypatch.setattr(engine.jm, "create_request", create_request)
    monkeypatch.setattr(engine.jm, "update_request", update_request)
    monkeypatch.setattr(engine.jm, "update_job", update_job)
    monkeypatch.setattr(engine.jm, "log_failover", log_failover)
    monkeypatch.setattr(engine.jm, "find_completed_by_idempotency", find_completed_by_idempotency)

    async def get_settings():
        return {"paused": False, "routing_strategy": "priority", "retry_count": 2,
                "request_timeout": 30, "cooldown_seconds": 300, "rate_limit_cooldown_seconds": 60,
                "notifications": {"on_failover": True, "on_key_exhausted": True,
                                  "on_key_auth_error": True, "on_no_healthy_keys": True}}

    monkeypatch.setattr(engine, "get_settings", get_settings)

    for name in ("notify_failover", "notify_exhausted", "notify_auth_error", "notify_no_keys", "notify"):
        async def _noop(*a, **k):
            return None
        monkeypatch.setattr(engine.notifier, name, _noop)

    class FakeAdapter:
        async def chat(self, *, api_key, session_id, messages, provider, model, timeout, max_tokens=None):
            kid = api_key.replace("secret-", "")
            return adapter_behaviour[kid]()

    monkeypatch.setattr(engine, "adapter", FakeAdapter())
    return state


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_success_first_key(monkeypatch):
    keys = [{"id": "k1", "mask": "••••k1"}]
    state = install_fakes(monkeypatch, keys, {"k1": lambda: "OK"})
    content, meta = run(engine.run_chat(client_id="c", session_id="s1", provider="openai",
                                        model="gpt-5.4", messages=[{"role": "user", "content": "hi"}]))
    assert content == "OK"
    assert state["selected"] == ["k1"]


def test_failover_on_credit_exhaustion(monkeypatch):
    keys = [{"id": "k1", "mask": "••••k1"}, {"id": "k2", "mask": "••••k2"}]

    def k1():
        raise Boom("insufficient credits", 402)

    state = install_fakes(monkeypatch, keys, {"k1": k1, "k2": lambda: "OK2"})
    content, meta = run(engine.run_chat(client_id="c", session_id="s2", provider="openai",
                                        model="gpt-5.4", messages=[{"role": "user", "content": "hi"}]))
    assert content == "OK2"
    assert state["selected"] == ["k1", "k2"]
    assert ("k1", "CREDIT_EXHAUSTED") in state["failures"]
    assert state["failovers"] == ["k1"]


def test_auth_failure_disables_and_failsover(monkeypatch):
    keys = [{"id": "k1", "mask": "••••k1"}, {"id": "k2", "mask": "••••k2"}]

    def k1():
        raise Boom("Invalid API key", 401)

    state = install_fakes(monkeypatch, keys, {"k1": k1, "k2": lambda: "OK2"})
    content, _ = run(engine.run_chat(client_id="c", session_id="s3", provider="openai",
                                     model="gpt-5.4", messages=[{"role": "user", "content": "hi"}]))
    assert content == "OK2"
    assert ("k1", "AUTH_FAILED") in state["failures"]


def test_invalid_request_no_failover(monkeypatch):
    keys = [{"id": "k1", "mask": "••••k1"}, {"id": "k2", "mask": "••••k2"}]

    def k1():
        raise Boom("model_not_found", 404)

    state = install_fakes(monkeypatch, keys, {"k1": k1, "k2": lambda: "SHOULD_NOT_RUN"})
    try:
        run(engine.run_chat(client_id="c", session_id="s4", provider="openai",
                            model="bad", messages=[{"role": "user", "content": "hi"}]))
        assert False, "expected RouterError"
    except engine.RouterError as e:
        assert e.error_class == ErrorClass.INVALID_REQUEST
    assert state["selected"] == ["k1"]  # never tried k2


def test_provider_error_retries_same_key_then_failsover(monkeypatch):
    keys = [{"id": "k1", "mask": "••••k1"}, {"id": "k2", "mask": "••••k2"}]
    calls = {"n": 0}

    def k1():
        calls["n"] += 1
        raise Boom("internal server error", 500)

    state = install_fakes(monkeypatch, keys, {"k1": k1, "k2": lambda: "OK2"})
    content, _ = run(engine.run_chat(client_id="c", session_id="s5", provider="openai",
                                     model="gpt-5.4", messages=[{"role": "user", "content": "hi"}]))
    assert content == "OK2"
    assert calls["n"] == 3          # 1 initial + 2 retries on same key
    assert state["selected"] == ["k1", "k2"]


def test_no_healthy_keys(monkeypatch):
    keys = [{"id": "k1", "mask": "••••k1"}]

    def k1():
        raise Boom("insufficient credits", 402)

    install_fakes(monkeypatch, keys, {"k1": k1})
    try:
        run(engine.run_chat(client_id="c", session_id="s6", provider="openai",
                            model="gpt-5.4", messages=[{"role": "user", "content": "hi"}]))
        assert False, "expected RouterError"
    except engine.RouterError as e:
        assert e.http_status == 503
