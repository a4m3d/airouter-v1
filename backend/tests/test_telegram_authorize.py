"""Targeted tests for Telegram webhook capture + admin authorize flow."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")

ADMIN_TOKEN = "abkA-iyoH_7uWKMb3_mr43nzFl4YHs99"
WEBHOOK_SECRET = "drtV-juucTIVWDZpGlN60GFam5GuW33zfvhJtxH1XfU"
FAKE_TG_ID = 700100200


@pytest.fixture(scope="module")
def admin_headers():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"admin_token": ADMIN_TOKEN}, timeout=15)
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="module", autouse=True)
def cleanup_admin_id(admin_headers):
    yield
    # remove FAKE_TG_ID from admin_ids if present
    try:
        cur = requests.get(f"{BASE_URL}/api/admin/settings", headers=admin_headers, timeout=15).json()
        ids = cur.get("telegram_admin_ids", []) or []
        new_ids = [i for i in ids if str(i) != str(FAKE_TG_ID)]
        if new_ids != ids:
            cur["telegram_admin_ids"] = new_ids
            requests.put(f"{BASE_URL}/api/admin/settings", headers=admin_headers, json=cur, timeout=15)
    except Exception:
        pass


def _tg_status(admin_headers):
    return requests.get(f"{BASE_URL}/api/admin/telegram", headers=admin_headers, timeout=15)


def test_status_basic(admin_headers):
    r = _tg_status(admin_headers)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("token_configured") is True
    assert d.get("bot", {}).get("username") == "theairouterbot"
    assert d.get("webhook", {}).get("url")


def test_webhook_wrong_secret_ignored(admin_headers):
    # Ensure the fake id isn't in pending yet, or note current state
    before = _tg_status(admin_headers).json()
    before_pending = {str(u["id"]) for u in (before.get("pending_users") or [])}

    body = {
        "update_id": 9002,
        "message": {
            "message_id": 8,
            "from": {"id": 999999999, "first_name": "Bad", "username": "baduser"},
            "chat": {"id": 999999999},
            "text": "/start",
        },
    }
    r = requests.post(
        f"{BASE_URL}/api/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "WRONG-SECRET"},
        json=body,
        timeout=15,
    )
    # spec says returns 200 but no-op. Accept 200/401/403 - key thing: no pending user created.
    assert r.status_code in (200, 401, 403)
    time.sleep(1)
    after = _tg_status(admin_headers).json()
    after_pending = {str(u["id"]) for u in (after.get("pending_users") or [])}
    assert "999999999" not in (after_pending - before_pending)


def test_webhook_capture_then_authorize(admin_headers):
    # 1. Simulate inbound telegram message
    body = {
        "update_id": 9001,
        "message": {
            "message_id": 7,
            "from": {"id": FAKE_TG_ID, "first_name": "QA", "username": "qatester"},
            "chat": {"id": FAKE_TG_ID},
            "text": "/start",
        },
    }
    r = requests.post(
        f"{BASE_URL}/api/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": WEBHOOK_SECRET},
        json=body,
        timeout=15,
    )
    assert r.status_code == 200, r.text

    # 2. Verify pending_users contains our fake id
    time.sleep(1)
    st = _tg_status(admin_headers).json()
    pending = st.get("pending_users") or []
    found = next((u for u in pending if str(u["id"]) == str(FAKE_TG_ID)), None)
    assert found, f"expected pending user {FAKE_TG_ID} in {pending}"
    assert found.get("name") == "QA"
    assert found.get("username") == "qatester"

    # 3. Authorize
    ra = requests.post(
        f"{BASE_URL}/api/admin/telegram/authorize",
        headers=admin_headers,
        json={"id": str(FAKE_TG_ID)},
        timeout=15,
    )
    assert ra.status_code == 200, ra.text
    assert ra.json().get("ok") is True

    # 4. Verify moved to admin_ids and no longer pending
    time.sleep(1)
    st2 = _tg_status(admin_headers).json()
    admin_ids = [str(x) for x in (st2.get("admin_ids") or [])]
    assert str(FAKE_TG_ID) in admin_ids, f"admin_ids={admin_ids}"
    pending2 = [str(u["id"]) for u in (st2.get("pending_users") or [])]
    assert str(FAKE_TG_ID) not in pending2
