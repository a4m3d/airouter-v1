import asyncio
import logging
import os

import requests as http

logger = logging.getLogger("router.notifier")


def _admin_chat_ids():
    raw = os.environ.get("TELEGRAM_ADMIN_IDS", "") or ""
    return [p.strip() for p in raw.replace(" ", "").split(",") if p.strip()]


def _send_sync(text: str):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        return  # bot not configured; skip silently (still logged internally, redacted)
    for chat_id in _admin_chat_ids():
        try:
            http.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
                timeout=10,
            )
        except Exception:
            logger.warning("Failed to deliver Telegram notification")


async def notify(text: str):
    # Never include credentials in notifications.
    await asyncio.get_event_loop().run_in_executor(None, _send_sync, text)


async def notify_failover(job_id, from_mask, to_mask, reason):
    await notify(f"🔄 <b>FAILOVER</b>\n\nJob {job_id}\n{from_mask} → {to_mask}\nReason: {reason}")


async def notify_exhausted(mask, to_mask):
    dest = f"\n\nAutomatically switched to:\n{to_mask}" if to_mask else ""
    await notify(f"🚨 <b>KEY EXHAUSTED</b>\n\n{mask} has become unavailable.{dest}")


async def notify_auth_error(mask):
    await notify(f"⚠️ <b>KEY ERROR</b>\n\n{mask} authentication failed.\nKey has been disabled.")


async def notify_no_keys():
    await notify("⛔️ <b>NO HEALTHY KEYS</b>\n\nAll eligible keys are unavailable. Requests are failing.")
