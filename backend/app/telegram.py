"""Lightweight Telegram integration (no aiogram — avoids the pydantic/Gemini SDK
conflict in this runtime). Handles outbound messages, webhook setup, and inbound
command handling for the live control bot. The portable bundle uses bot/bot.py (aiogram).
"""
import asyncio
import logging
import os
import time

import requests as http

from app.db import jobs, requests as req_col, failovers, telegram_seen
from app.settings_store import effective_admin_ids, get_settings, update_settings
from app import key_manager as km

logger = logging.getLogger("router.telegram")

API = "https://api.telegram.org/bot{token}/{method}"


def _token():
    return os.environ.get("TELEGRAM_BOT_TOKEN")


def _call_sync(method: str, payload: dict):
    token = _token()
    if not token:
        return {"ok": False, "error": "no_token"}
    try:
        r = http.post(API.format(token=token, method=method), json=payload, timeout=15)
        return r.json()
    except Exception:
        logger.warning("Telegram API call failed: %s", method)
        return {"ok": False}


async def call(method: str, payload: dict):
    return await asyncio.get_event_loop().run_in_executor(None, _call_sync, method, payload)


async def send_message(chat_id, text: str):
    return await call("sendMessage", {"chat_id": chat_id, "text": text, "parse_mode": "HTML"})


async def get_me():
    return await call("getMe", {})


async def webhook_info():
    return await call("getWebhookInfo", {})


async def set_webhook():
    base = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
    secret = os.environ.get("ROUTER_INTERNAL_SECRET", "")
    if not base or not _token():
        return {"ok": False, "error": "missing base url or token"}
    url = f"{base}/api/telegram/webhook"
    return await call("setWebhook", {"url": url, "secret_token": secret,
                                     "allowed_updates": ["message"]})


async def notify_admins(text: str):
    ids = await effective_admin_ids()
    for chat_id in ids:
        await send_message(chat_id, text)


ICON = {"healthy": "🟢", "cooldown": "🟡", "exhausted": "🔴", "unhealthy": "🔴", "unknown": "⚪️"}


async def _status_text():
    kc = await km.counts()
    active = await jobs.count_documents({"status": "running"})
    today = time.strftime("%Y-%m-%d", time.gmtime())
    total = await req_col.count_documents({"created_at": {"$regex": f"^{today}"}})
    ok = await req_col.count_documents({"created_at": {"$regex": f"^{today}"}, "status": "success"})
    fail = await req_col.count_documents({"created_at": {"$regex": f"^{today}"}, "status": "failed"})
    fo = await failovers.count_documents({"created_at": {"$regex": f"^{today}"}})
    s = await get_settings()
    return (f"🟢 <b>System {'Online' if not s.get('paused') else 'Paused'}</b>\n\n"
            f"🔑 Keys: {kc['total']}\n🟢 Healthy: {kc['healthy']}\n🟡 Cooldown: {kc['cooldown']}\n🔴 Exhausted: {kc['exhausted']}\n\n"
            f"🚀 Active Jobs: {active}\n\nRequests Today: {total}\nSuccessful: {ok}\nFailed: {fail}\nFailovers: {fo}")


async def _keys_text():
    keys = await km.list_keys()
    if not keys:
        return "No keys configured. Use /addkey &lt;key&gt;."
    return "\n\n".join(f"{ICON.get(k['health_status'], '⚪️')} <b>{k['label']}</b>\nPriority: {k['priority']}\nMasked: {k['mask']}"
                       for k in keys)


async def handle_command(text: str, chat_id, user_id):
    """Handle an inbound command from an authorized admin."""
    parts = (text or "").strip().split(maxsplit=1)
    cmd = parts[0].lower().lstrip("/").split("@")[0]
    arg = parts[1].strip() if len(parts) > 1 else ""

    if cmd == "start":
        base = os.environ.get("PUBLIC_BASE_URL", "")
        return (f"🤖 <b>AI ROUTER CONTROL CENTRE</b>\n\nYou are authorized ✅\n\n"
                f"Commands: /status /keys /addkey /usage /health /jobs /logs /pause /resume\n\n"
                f"Dashboard: {base}")
    if cmd == "status":
        return await _status_text()
    if cmd == "keys":
        return await _keys_text()
    if cmd == "usage":
        total = await req_col.count_documents({})
        ok = await req_col.count_documents({"status": "success"})
        fail = await req_col.count_documents({"status": "failed"})
        fo = await failovers.count_documents({})
        return (f"📊 <b>Usage</b>\nTotal: {total} · ✓ {ok} · ✗ {fail} · 🔄 {fo}\n\n"
                f"Credit balances are not shown (provider has no reliable balance endpoint).")
    if cmd == "jobs":
        docs = await jobs.find({}, {"_id": 0}).sort("updated_at", -1).limit(10).to_list(10)
        return "🚀 <b>Recent jobs</b>\n" + ("\n".join(f"{j['id']} · step {j['current_step']} · {j['status']}" for j in docs) or "none")
    if cmd == "logs":
        docs = await req_col.find({}, {"_id": 0, "result": 0}).sort("created_at", -1).limit(10).to_list(10)
        return "📋 <b>Logs</b>\n" + ("\n".join(f"{l['id']} · {l['status']} · {l.get('error_type') or ''}→{l.get('action') or ''}" for l in docs) or "none")
    if cmd == "pause":
        await update_settings({"paused": True})
        return "⏸ Router paused."
    if cmd == "resume":
        await update_settings({"paused": False})
        return "▶️ Router resumed."
    if cmd == "addkey":
        if not arg:
            return "Send: <code>/addkey &lt;your-universal-key&gt;</code>"
        from app.routes.admin_routes import _test_secret
        test = await _test_secret(arg, "emergent")
        key = await km.add_key(arg, None, None, "emergent")
        if test.get("ok"):
            await km.record_success(key["id"], test.get("latency_ms", 0))
        return f"✅ Key added: {key['mask']} · validation: {'OK' if test.get('ok') else test.get('error_type')}\n(Delete the message above containing your key.)"
    if cmd in ("remove_key", "enable_key", "disable_key", "test_key", "settings", "health"):
        if cmd == "health":
            keys = await km.list_keys()
            lines = []
            for k in keys:
                secret = await km.get_secret(k["id"])
                from app.routes.admin_routes import _test_secret
                t = await _test_secret(secret, k.get("provider", "emergent"))
                if t.get("ok"):
                    await km.record_success(k["id"], t.get("latency_ms", 0))
                lines.append(f"{k['mask']}: {'🟢 OK' if t.get('ok') else '🔴 ' + str(t.get('error_type'))}")
            return "❤️ <b>Health</b>\n" + ("\n".join(lines) or "no keys")
        return "Manage keys from the dashboard (API KEYS tab)."
    return "Unknown command. Try /status or /keys."


async def process_update(update: dict):
    msg = update.get("message") or update.get("edited_message")
    if not msg:
        return
    text = msg.get("text", "")
    chat_id = msg.get("chat", {}).get("id")
    frm = msg.get("from", {})
    user_id = str(frm.get("id"))
    if not text.startswith("/"):
        return

    # Remember whoever messages the bot so the admin can one-tap authorize them.
    name = (frm.get("first_name", "") + (" " + frm.get("last_name", "") if frm.get("last_name") else "")).strip()
    try:
        await telegram_seen.update_one(
            {"id": user_id},
            {"$set": {"id": user_id, "name": name or "Unknown",
                      "username": frm.get("username"), "chat_id": chat_id,
                      "last_seen": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}},
            upsert=True,
        )
    except Exception:
        pass

    admins = await effective_admin_ids()
    if user_id not in admins:
        # Help the user discover their ID so an admin can authorize them in the dashboard.
        await send_message(chat_id,
                           f"⛔️ Not authorized.\n\nYour Telegram ID is: <code>{user_id}</code>\n\n"
                           f"Add this ID under Settings → Telegram in the dashboard to grant access.")
        return

    reply = await handle_command(text, chat_id, user_id)
    if reply:
        await send_message(chat_id, reply)
