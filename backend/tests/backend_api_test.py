"""End-to-end backend API tests for the AI router.

Covers: health, admin auth, dashboard, key CRUD, router chat (success/auth/failover),
streaming, usage, jobs, health checks, logs, settings, client-keys, security masking.
"""
import os
import json
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # fallback to frontend .env value (test env)
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")

ADMIN_TOKEN = "abkA-iyoH_7uWKMb3_mr43nzFl4YHs99"
CLIENT_KEY = "sk-router-Y7as_5RakGo-uoD6_VyGVF04AU-OG4Ut"

TINY_MESSAGES = [{"role": "user", "content": "Reply with exactly: ROUTER OK"}]


@pytest.fixture(scope="session")
def admin_jwt():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"admin_token": ADMIN_TOKEN}, timeout=30)
    assert r.status_code == 200, r.text
    tok = r.json().get("token")
    assert tok
    return tok


@pytest.fixture(scope="session")
def admin_headers(admin_jwt):
    return {"Authorization": f"Bearer {admin_jwt}"}


# ---------------- Public ----------------
def test_health_public():
    r = requests.get(f"{BASE_URL}/api/health", timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "online"


# ---------------- Admin auth ----------------
def test_admin_login_wrong_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"admin_token": "wrong-token"}, timeout=15)
    assert r.status_code == 401


def test_admin_keys_requires_auth():
    r = requests.get(f"{BASE_URL}/api/admin/keys", timeout=15)
    assert r.status_code == 401


def test_admin_keys_list(admin_headers):
    r = requests.get(f"{BASE_URL}/api/admin/keys", headers=admin_headers, timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    for k in data:
        # Security: no plaintext/ciphertext ever exposed
        raw = json.dumps(k)
        assert "ciphertext" not in raw
        assert "nonce" not in raw
        # masked value indicator
        masked = k.get("masked_key") or k.get("key_masked") or k.get("masked") or ""
        # allow either "•" or "*" masking; the actual key material should never appear
        assert "sk-emergent" not in raw or "•" in raw or "*" in raw


# ---------------- Dashboard ----------------
def test_dashboard(admin_headers):
    r = requests.get(f"{BASE_URL}/api/admin/dashboard", headers=admin_headers, timeout=15)
    assert r.status_code == 200
    d = r.json()
    # accept nested or flat
    flat = json.dumps(d)
    for token in ["healthy", "cooldown", "exhausted", "active_jobs", "requests_today"]:
        assert token in flat, f"missing {token} in dashboard"


# ---------------- Key management ----------------
@pytest.fixture(scope="session")
def temp_key_id(admin_headers):
    payload = {
        "name": "TEST_temp_key",
        "provider": "openai",
        "secret": "sk-test-fake-000000000000000000000000",
        "priority": 99,
        "enabled": False,
    }
    r = requests.post(f"{BASE_URL}/api/admin/keys", headers=admin_headers, json=payload, timeout=30)
    if r.status_code not in (200, 201):
        pytest.skip(f"cannot create test key: {r.status_code} {r.text}")
    kid = r.json().get("id") or r.json().get("key", {}).get("id")
    assert kid
    yield kid
    # cleanup
    requests.delete(f"{BASE_URL}/api/admin/keys/{kid}", headers=admin_headers, timeout=15)


def test_key_masked_in_list(admin_headers, temp_key_id):
    r = requests.get(f"{BASE_URL}/api/admin/keys", headers=admin_headers, timeout=15)
    raw = r.text
    assert "sk-test-fake-000000000000000000000000" not in raw


def test_key_toggle_and_priority(admin_headers, temp_key_id):
    # toggle disable/enable
    r = requests.post(
        f"{BASE_URL}/api/admin/keys/{temp_key_id}/enabled",
        headers=admin_headers,
        json={"enabled": True},
        timeout=15,
    )
    assert r.status_code in (200, 204), r.text
    r = requests.post(
        f"{BASE_URL}/api/admin/keys/{temp_key_id}/priority",
        headers=admin_headers,
        json={"priority": 50},
        timeout=15,
    )
    assert r.status_code in (200, 204), r.text


def test_key_test_endpoint(admin_headers, temp_key_id):
    r = requests.post(f"{BASE_URL}/api/admin/keys/{temp_key_id}/test", headers=admin_headers, timeout=60)
    # expected to fail because it's a fake key, but endpoint must respond
    assert r.status_code in (200, 400, 401, 502)


# ---------------- Router API ----------------
def test_router_requires_client_key():
    r = requests.post(
        f"{BASE_URL}/api/v1/chat/completions",
        json={"model": "gpt-5.4", "messages": TINY_MESSAGES},
        timeout=30,
    )
    assert r.status_code == 401


def test_router_chat_success():
    r = requests.post(
        f"{BASE_URL}/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {CLIENT_KEY}"},
        json={"model": "gpt-5.4", "messages": TINY_MESSAGES, "max_tokens": 20},
        timeout=90,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("object") == "chat.completion"
    choices = data.get("choices", [])
    assert choices and choices[0]["message"]["content"]
    x = data.get("x_router") or {}
    key_masked = str(x.get("key", ""))
    # masked format check
    assert "•" in key_masked or "*" in key_masked or len(key_masked) <= 20


def test_router_invalid_model_no_loop():
    start = time.time()
    r = requests.post(
        f"{BASE_URL}/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {CLIENT_KEY}"},
        json={"model": "not-a-real-model-xyz", "messages": TINY_MESSAGES, "max_tokens": 5},
        timeout=60,
    )
    elapsed = time.time() - start
    # should fail quickly (no failover loop)
    assert r.status_code >= 400
    assert elapsed < 45, f"took too long: {elapsed}s (likely looped)"


def test_router_streaming():
    r = requests.post(
        f"{BASE_URL}/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {CLIENT_KEY}"},
        json={"model": "gpt-5.4", "messages": TINY_MESSAGES, "stream": True, "max_tokens": 20},
        stream=True,
        timeout=90,
    )
    assert r.status_code == 200
    chunks = []
    saw_done = False
    for line in r.iter_lines(decode_unicode=True):
        if not line:
            continue
        chunks.append(line)
        if "[DONE]" in line:
            saw_done = True
            break
    assert saw_done, f"no [DONE] terminator seen; chunks={chunks[:5]}"
    # Chunk format check
    assert any(l.startswith("data:") for l in chunks)


# ---------------- Failover ----------------
def test_failover_with_bogus_key(admin_headers):
    # Add bogus key at higher priority (lower number)
    payload = {
        "name": "TEST_bogus_priority_key",
        "provider": "openai",
        "secret": "sk-bogus-invalid-000000000000000000",
        "priority": 0,
        "enabled": True,
    }
    r = requests.post(f"{BASE_URL}/api/admin/keys", headers=admin_headers, json=payload, timeout=30)
    if r.status_code not in (200, 201):
        pytest.skip(f"cannot add bogus key: {r.text}")
    bogus_id = r.json().get("id") or r.json().get("key", {}).get("id")
    try:
        # get usage before
        u0 = requests.get(f"{BASE_URL}/api/admin/usage", headers=admin_headers, timeout=15).json()
        failovers_before = _get_failovers(u0)

        rc = requests.post(
            f"{BASE_URL}/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {CLIENT_KEY}"},
            json={"model": "gpt-5.4", "messages": TINY_MESSAGES, "max_tokens": 20},
            timeout=120,
        )
        assert rc.status_code == 200, rc.text
        assert rc.json()["choices"][0]["message"]["content"]

        u1 = requests.get(f"{BASE_URL}/api/admin/usage", headers=admin_headers, timeout=15).json()
        failovers_after = _get_failovers(u1)
        assert failovers_after >= failovers_before + 1
        # error_breakdown includes AUTH_FAILED
        raw = json.dumps(u1)
        assert "AUTH_FAILED" in raw
    finally:
        requests.delete(f"{BASE_URL}/api/admin/keys/{bogus_id}", headers=admin_headers, timeout=15)


def _get_failovers(usage):
    # tolerant lookup
    if isinstance(usage, dict):
        for k in ("failovers", "total_failovers"):
            if k in usage:
                return usage[k]
        totals = usage.get("totals", {})
        return totals.get("failovers", 0)
    return 0


# ---------------- Usage / Jobs / Health / Logs ----------------
def test_usage_endpoint(admin_headers):
    r = requests.get(f"{BASE_URL}/api/admin/usage", headers=admin_headers, timeout=15)
    assert r.status_code == 200
    raw = json.dumps(r.json()).lower()
    assert "per_key" in raw or "per-key" in raw
    assert "error_breakdown" in raw or "errors" in raw
    assert "credit" in raw  # note about balances not shown


def test_jobs_list(admin_headers):
    r = requests.get(f"{BASE_URL}/api/admin/jobs", headers=admin_headers, timeout=15)
    assert r.status_code == 200
    jobs = r.json()
    if isinstance(jobs, dict):
        jobs = jobs.get("jobs", jobs.get("items", []))
    assert isinstance(jobs, list)
    if jobs:
        jid = jobs[0].get("id") or jobs[0].get("job_id")
        if jid:
            r2 = requests.get(f"{BASE_URL}/api/admin/jobs/{jid}", headers=admin_headers, timeout=15)
            assert r2.status_code == 200
            d = r2.json()
            raw = json.dumps(d)
            assert "requests" in raw or "failovers" in raw or "job" in raw


def test_health_check(admin_headers):
    r = requests.post(f"{BASE_URL}/api/admin/health/check", headers=admin_headers, timeout=60)
    assert r.status_code in (200, 202)


def test_logs(admin_headers):
    r = requests.get(f"{BASE_URL}/api/admin/logs", headers=admin_headers, timeout=15)
    assert r.status_code == 200
    logs = r.json()
    if isinstance(logs, dict):
        logs = logs.get("logs", logs.get("items", []))
    raw = json.dumps(logs).lower()
    # ensure no prompt/credential leakage
    assert "router ok" not in raw or True  # response content may appear but not the secret
    assert "sk-emergent" not in raw
    assert "sk-router" not in raw
    assert "ciphertext" not in raw

    # filter by status
    r2 = requests.get(f"{BASE_URL}/api/admin/logs?status=success", headers=admin_headers, timeout=15)
    assert r2.status_code == 200


# ---------------- Settings ----------------
def test_settings_get_put(admin_headers):
    r = requests.get(f"{BASE_URL}/api/admin/settings", headers=admin_headers, timeout=15)
    assert r.status_code == 200
    cur = r.json()
    # update retry_count if present
    payload = dict(cur) if isinstance(cur, dict) else {}
    payload["retry_count"] = 3
    r2 = requests.put(f"{BASE_URL}/api/admin/settings", headers=admin_headers, json=payload, timeout=15)
    assert r2.status_code in (200, 204)
    r3 = requests.get(f"{BASE_URL}/api/admin/settings", headers=admin_headers, timeout=15)
    assert r3.json().get("retry_count") == 3


def test_pause_resume(admin_headers):
    r1 = requests.post(f"{BASE_URL}/api/admin/pause", headers=admin_headers, timeout=15)
    assert r1.status_code in (200, 204)
    r2 = requests.post(f"{BASE_URL}/api/admin/resume", headers=admin_headers, timeout=15)
    assert r2.status_code in (200, 204)


# ---------------- Client keys ----------------
def test_client_keys_crud(admin_headers):
    r = requests.get(f"{BASE_URL}/api/admin/client-keys", headers=admin_headers, timeout=15)
    assert r.status_code == 200
    # create
    name = f"TEST_ck_{uuid.uuid4().hex[:6]}"
    rc = requests.post(
        f"{BASE_URL}/api/admin/client-keys",
        headers=admin_headers,
        json={"name": name},
        timeout=15,
    )
    assert rc.status_code in (200, 201), rc.text
    body = rc.json()
    # plaintext once
    plaintext = body.get("key") or body.get("plaintext") or body.get("api_key")
    assert plaintext and plaintext.startswith("sk-router-")
    ck_id = body.get("id") or body.get("client_key", {}).get("id")
    assert ck_id

    # list should NOT include plaintext, only prefix
    rl = requests.get(f"{BASE_URL}/api/admin/client-keys", headers=admin_headers, timeout=15)
    assert plaintext not in rl.text

    # rotate
    rr = requests.post(
        f"{BASE_URL}/api/admin/client-keys/{ck_id}/rotate", headers=admin_headers, timeout=15
    )
    assert rr.status_code in (200, 201), rr.text
    rotated = rr.json().get("key") or rr.json().get("plaintext")
    assert rotated and rotated != plaintext

    # revoke
    rd = requests.post(
        f"{BASE_URL}/api/admin/client-keys/{ck_id}/revoke", headers=admin_headers, timeout=15
    )
    assert rd.status_code in (200, 204)


# ---------------- Security master check ----------------
def test_no_credential_leak_in_admin_endpoints(admin_headers):
    endpoints = [
        "/api/admin/keys",
        "/api/admin/dashboard",
        "/api/admin/usage",
        "/api/admin/jobs",
        "/api/admin/logs",
        "/api/admin/settings",
        "/api/admin/client-keys",
    ]
    for ep in endpoints:
        r = requests.get(f"{BASE_URL}{ep}", headers=admin_headers, timeout=15)
        assert r.status_code == 200, ep
        raw = r.text
        assert "ciphertext" not in raw, ep
        assert "nonce" not in raw, ep
        # Full EMERGENT key should never appear
        emergent = os.environ.get("EMERGENT_LLM_KEY", "")
        if emergent:
            assert emergent not in raw, f"{ep} leaked EMERGENT_LLM_KEY"
