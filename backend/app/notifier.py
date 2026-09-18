import logging

from app import telegram

logger = logging.getLogger("router.notifier")


async def notify(text: str):
    await telegram.notify_admins(text)


async def notify_failover(job_id, from_mask, to_mask, reason):
    await notify(f"🔄 <b>FAILOVER</b>\n\nJob {job_id}\n{from_mask} → {to_mask}\nReason: {reason}")


async def notify_exhausted(mask, to_mask):
    dest = f"\n\nAutomatically switched to:\n{to_mask}" if to_mask else ""
    await notify(f"🚨 <b>KEY EXHAUSTED</b>\n\n{mask} has become unavailable.{dest}")


async def notify_auth_error(mask):
    await notify(f"⚠️ <b>KEY ERROR</b>\n\n{mask} authentication failed.\nKey has been disabled.")


async def notify_no_keys():
    await notify("⛔️ <b>NO HEALTHY KEYS</b>\n\nAll eligible keys are unavailable. Requests are failing.")
