"""aiogram Telegram control bot for the AI Router.

Runs as a standalone service (see docker-compose). It authorizes admins by
TELEGRAM_ADMIN_IDS and drives the backend admin API. It never prints secrets.

Install:  pip install aiogram==3.15.0
Run:      python -m bot.bot
"""
import asyncio
import os

import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo,
)

BACKEND_URL = os.environ.get("BACKEND_INTERNAL_URL", "http://backend:8001")
ADMIN_TOKEN = os.environ.get("ADMIN_DASHBOARD_TOKEN", "")
WEBAPP_URL = os.environ.get("WEBAPP_URL", "")


def admin_ids() -> set:
    raw = os.environ.get("TELEGRAM_ADMIN_IDS", "") or ""
    return {p.strip() for p in raw.replace(" ", "").split(",") if p.strip()}


def is_admin(message: Message) -> bool:
    return str(message.from_user.id) in admin_ids()


class Api:
    def __init__(self):
        self._token = None

    async def _login(self, session):
        async with session.post(f"{BACKEND_URL}/api/auth/login",
                                json={"admin_token": ADMIN_TOKEN}) as r:
            data = await r.json()
            self._token = data["token"]

    async def get(self, path):
        async with aiohttp.ClientSession() as s:
            if not self._token:
                await self._login(s)
            async with s.get(f"{BACKEND_URL}{path}",
                             headers={"Authorization": f"Bearer {self._token}"}) as r:
                return await r.json()

    async def post(self, path, body=None):
        async with aiohttp.ClientSession() as s:
            if not self._token:
                await self._login(s)
            async with s.post(f"{BACKEND_URL}{path}", json=body or {},
                             headers={"Authorization": f"Bearer {self._token}"}) as r:
                return await r.json()


api = Api()
dp = Dispatcher()


@dp.message(Command("start"))
async def cmd_start(message: Message):
    if not is_admin(message):
        return await message.answer("⛔️ Unauthorized. This bot is restricted to administrators.")
    kb = None
    if WEBAPP_URL:
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🤖 Open Control Centre", web_app=WebAppInfo(url=WEBAPP_URL))
        ]])
    await message.answer("🤖 <b>AI ROUTER CONTROL CENTRE</b>\n\nUse /status, /keys, /usage, /health, /jobs, /logs, /pause, /resume.",
                         parse_mode="HTML", reply_markup=kb)


@dp.message(Command("status"))
async def cmd_status(message: Message):
    if not is_admin(message):
        return
    d = await api.get("/api/admin/dashboard")
    k = d["keys"]
    await message.answer(
        f"🟢 <b>System {'Online' if d['system_online'] else 'Paused'}</b>\n\n"
        f"🔑 Keys: {k['total']}\n🟢 Healthy: {k['healthy']}\n🟡 Cooldown: {k['cooldown']}\n🔴 Exhausted: {k['exhausted']}\n\n"
        f"🚀 Active Jobs: {d['active_jobs']}\n\n"
        f"Requests Today: {d['requests_today']}\nSuccessful: {d['successful_today']}\n"
        f"Failed: {d['failed_today']}\nFailovers: {d['failovers_today']}",
        parse_mode="HTML")


@dp.message(Command("keys"))
async def cmd_keys(message: Message):
    if not is_admin(message):
        return
    keys = await api.get("/api/admin/keys")
    if not keys:
        return await message.answer("No keys configured. Use /addkey.")
    icon = {"healthy": "🟢", "cooldown": "🟡", "exhausted": "🔴", "unhealthy": "🔴"}
    lines = [f"{icon.get(k['health_status'], '⚪️')} <b>{k['label']}</b>\nPriority: {k['priority']}\nMasked: {k['mask']}"
             for k in keys]
    await message.answer("\n\n".join(lines), parse_mode="HTML")


@dp.message(Command("addkey"))
async def cmd_addkey(message: Message):
    if not is_admin(message):
        return
    await message.answer("Send your Universal API Key as: <code>/addkey &lt;key&gt;</code>\n"
                         "The key is validated, encrypted (AES-256-GCM) and never shown again.",
                         parse_mode="HTML")
    parts = message.text.split(maxsplit=1)
    if len(parts) == 2 and parts[1].strip():
        res = await api.post("/api/admin/keys", {"secret": parts[1].strip()})
        v = res.get("validation", {})
        await message.answer(f"✅ Key added. Validation: {'OK' if v.get('ok') else v.get('error_type')}")
        # Attempt to delete the message containing the secret for hygiene
        try:
            await message.delete()
        except Exception:
            pass


@dp.message(Command("usage"))
async def cmd_usage(message: Message):
    if not is_admin(message):
        return
    u = await api.get("/api/admin/usage")
    await message.answer(f"📊 Total: {u['total_requests']} · ✓ {u['successful']} · ✗ {u['failed']} · 🔄 {u['failovers']}\n{u['note']}")


@dp.message(Command("health"))
async def cmd_health(message: Message):
    if not is_admin(message):
        return
    res = await api.post("/api/admin/health/check")
    lines = [f"{r['mask']}: {'🟢 OK' if r.get('ok') else '🔴 ' + str(r.get('error_type'))}" for r in res.get("results", [])]
    await message.answer("❤️ Health:\n" + ("\n".join(lines) or "no keys"))


@dp.message(Command("jobs"))
async def cmd_jobs(message: Message):
    if not is_admin(message):
        return
    jobs = await api.get("/api/admin/jobs")
    lines = [f"{j['id']} · step {j['current_step']} · {j['status']}" for j in jobs[:10]]
    await message.answer("🚀 Recent jobs:\n" + ("\n".join(lines) or "none"))


@dp.message(Command("logs"))
async def cmd_logs(message: Message):
    if not is_admin(message):
        return
    logs = await api.get("/api/admin/logs")
    lines = [f"{l['id']} · {l['status']} · {l.get('error_type') or ''} → {l.get('action') or ''}" for l in logs[:10]]
    await message.answer("📋 Logs:\n" + ("\n".join(lines) or "none"))


@dp.message(Command("pause"))
async def cmd_pause(message: Message):
    if not is_admin(message):
        return
    await api.post("/api/admin/pause")
    await message.answer("⏸ Router paused.")


@dp.message(Command("resume"))
async def cmd_resume(message: Message):
    if not is_admin(message):
        return
    await api.post("/api/admin/resume")
    await message.answer("▶️ Router resumed.")


async def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not set")
    bot = Bot(token)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
