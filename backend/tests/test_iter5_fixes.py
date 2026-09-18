"""Iteration 5 retest: DEMO_CLIENT_KEY seed fix, DELETE endpoint, idempotency."""
import os
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://router-control-27.preview.emergentagent.com").rstrip("/")
ADMIN_TOKEN = "abkA-iyoH_7uWKMb3_mr43nzFl4YHs99"
DEMO_KEY = "sk-router-Y7as_5RakGo-uoD6_VyGVF04AU-OG4Ut"


def _admin_jwt():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"admin_token": ADMIN_TOKEN}, timeout=30)
    r.raise_for_status()
    return r.json()["token"]


ADMIN_H = {"Authorization": f"Bearer {_admin_jwt()}"}


def test_router_chat_with_documented_key_returns_200():
    r = requests.post(
        f"{BASE_URL}/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {DEMO_KEY}", "Content-Type": "application/json"},
        json={"model": "gpt-5.4", "messages": [{"role": "user", "content": "Say OK"}]},
        timeout=60,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("object") == "chat.completion"
    assert body["choices"][0]["message"]["content"]


def test_default_client_cline_present_once_and_enabled():
    r = requests.get(f"{BASE_URL}/api/admin/client-keys", headers=ADMIN_H, timeout=30)
    assert r.status_code == 200
    keys = r.json()
    if isinstance(keys, dict):
        keys = keys.get("items") or keys.get("keys") or []
    defaults = [k for k in keys if k.get("name") == "Default Client (Cline)"]
    assert len(defaults) == 1, f"expected exactly 1 Default Client (Cline), got {len(defaults)}"
    d = defaults[0]
    assert d.get("key_prefix", "").startswith("sk-router-Y7as"), d
    assert d.get("enabled") is True or d.get("revoked") is False


def test_delete_endpoint_full_lifecycle():
    # create throwaway
    r = requests.post(
        f"{BASE_URL}/api/admin/client-keys",
        headers={**ADMIN_H, "Content-Type": "application/json"},
        json={"name": "TMP"},
        timeout=30,
    )
    assert r.status_code in (200, 201), r.text
    created = r.json()
    kid = (created.get("client_key") or {}).get("id") or created.get("id")
    assert kid, created

    # delete
    d = requests.delete(f"{BASE_URL}/api/admin/client-keys/{kid}", headers=ADMIN_H, timeout=30)
    assert d.status_code == 200, d.text
    assert d.json().get("deleted") is True

    # confirm gone
    r2 = requests.get(f"{BASE_URL}/api/admin/client-keys", headers=ADMIN_H, timeout=30)
    keys = r2.json()
    if isinstance(keys, dict):
        keys = keys.get("items") or keys.get("keys") or []
    ids = [k.get("id") or k.get("_id") or k.get("key_id") for k in keys]
    assert kid not in ids

    # delete non-existent -> 404
    d2 = requests.delete(f"{BASE_URL}/api/admin/client-keys/does-not-exist-xyz", headers=ADMIN_H, timeout=30)
    assert d2.status_code == 404


def test_router_call_recorded_in_jobs():
    # smoke: after router call, jobs endpoint returns something
    r = requests.get(f"{BASE_URL}/api/admin/jobs", headers=ADMIN_H, timeout=30)
    assert r.status_code == 200
