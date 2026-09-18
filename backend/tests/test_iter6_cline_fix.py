"""Iteration 6 - Cline compatibility fix verification (role-structured messages + max_tokens)."""
import os
import json
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://router-control-27.preview.emergentagent.com").rstrip("/")
ROUTER_KEY = "sk-router-Y7as_5RakGo-uoD6_VyGVF04AU-OG4Ut"
ADMIN_TOKEN = "abkA-iyoH_7uWKMb3_mr43nzFl4YHs99"

CHAT_URL = f"{BASE_URL}/api/v1/chat/completions"
ROUTER_H = {"Authorization": f"Bearer {ROUTER_KEY}", "Content-Type": "application/json"}

def _admin_jwt():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"admin_token": ADMIN_TOKEN}, timeout=30)
    r.raise_for_status()
    return r.json()["token"]

ADMIN_H = {"Authorization": f"Bearer {_admin_jwt()}", "Content-Type": "application/json"}


def test_cline_tool_call_wellformed():
    body = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "You are Cline. To write a file respond ONLY with <write_to_file><path>..</path><content>..</content></write_to_file>"},
            {"role": "user", "content": "Create hello.txt containing hi"},
        ],
    }
    r = requests.post(CHAT_URL, headers=ROUTER_H, json=body, timeout=90)
    assert r.status_code == 200, r.text
    data = r.json()
    content = data["choices"][0]["message"]["content"]
    print("CLINE CONTENT:", content)
    assert "<write_to_file>" in content and "</write_to_file>" in content
    assert "hello.txt" in content
    assert "hi" in content
    assert "x_router" in data and "job_id" in data["x_router"]


def test_multi_turn_role_preservation():
    body = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "user", "content": "My favorite color is blue."},
            {"role": "assistant", "content": "Got it, blue is your favorite."},
            {"role": "user", "content": "What is my favorite color? One word."},
        ],
    }
    r = requests.post(CHAT_URL, headers=ROUTER_H, json=body, timeout=60)
    assert r.status_code == 200, r.text
    content = r.json()["choices"][0]["message"]["content"].lower()
    print("MULTITURN:", content)
    assert "blue" in content


def test_streaming_sse():
    body = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": "Say hi"}],
        "stream": True,
    }
    r = requests.post(CHAT_URL, headers=ROUTER_H, json=body, stream=True, timeout=60)
    assert r.status_code == 200
    saw_done = False
    saw_chunk = False
    for line in r.iter_lines(decode_unicode=True):
        if not line:
            continue
        if line.startswith("data: "):
            payload = line[6:].strip()
            if payload == "[DONE]":
                saw_done = True
                break
            saw_chunk = True
            # verify JSON parses and has openai chunk shape
            obj = json.loads(payload)
            assert "choices" in obj
    assert saw_chunk and saw_done


def test_admin_settings_max_output_tokens_roundtrip():
    # GET
    r = requests.get(f"{BASE_URL}/api/admin/settings", headers=ADMIN_H, timeout=30)
    assert r.status_code == 200
    s = r.json()
    assert "max_output_tokens" in s
    original = s["max_output_tokens"]
    print("Original max_output_tokens:", original)

    # PUT 4096
    r = requests.put(f"{BASE_URL}/api/admin/settings", headers=ADMIN_H, json={"max_output_tokens": 4096}, timeout=30)
    assert r.status_code == 200, r.text

    r = requests.get(f"{BASE_URL}/api/admin/settings", headers=ADMIN_H, timeout=30)
    assert r.json()["max_output_tokens"] == 4096

    # Restore to 8192
    r = requests.put(f"{BASE_URL}/api/admin/settings", headers=ADMIN_H, json={"max_output_tokens": 8192}, timeout=30)
    assert r.status_code == 200
    r = requests.get(f"{BASE_URL}/api/admin/settings", headers=ADMIN_H, timeout=30)
    assert r.json()["max_output_tokens"] == 8192


def test_normal_completion_job_id():
    body = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": "Reply with the word: pong"}],
    }
    r = requests.post(CHAT_URL, headers=ROUTER_H, json=body, timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["choices"][0]["message"]["content"]
    assert data.get("x_router", {}).get("job_id")


def test_admin_health_check():
    r = requests.post(f"{BASE_URL}/api/admin/health/check", headers=ADMIN_H, timeout=120)
    assert r.status_code == 200, r.text
    data = r.json()
    print("HEALTH:", json.dumps(data)[:500])
    # Expect list/dict containing per-key ok statuses
    # Accept common shapes
    items = data if isinstance(data, list) else data.get("results") or data.get("keys") or []
    assert items, f"Empty health response: {data}"
    for entry in items:
        assert "ok" in entry or "status" in entry
