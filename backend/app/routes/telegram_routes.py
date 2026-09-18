import os

from fastapi import APIRouter, Depends, Header, Request

from app import telegram
from app.security.auth import require_admin
from app.settings_store import effective_admin_ids

# Public webhook (verified by Telegram secret token header)
webhook_router = APIRouter(prefix="/api/telegram")

# Admin management endpoints
admin_tg_router = APIRouter(prefix="/api/admin/telegram")


@webhook_router.post("/webhook")
async def telegram_webhook(request: Request,
                           x_telegram_bot_api_secret_token: str = Header(None)):
    expected = os.environ.get("ROUTER_INTERNAL_SECRET", "")
    if expected and x_telegram_bot_api_secret_token != expected:
        # Silently accept to avoid retries storms, but do nothing.
        return {"ok": True}
    try:
        update = await request.json()
        await telegram.process_update(update)
    except Exception:
        pass
    return {"ok": True}


@admin_tg_router.get("")
async def telegram_status(admin=Depends(require_admin)):
    token_set = bool(os.environ.get("TELEGRAM_BOT_TOKEN"))
    me = await telegram.get_me() if token_set else {"ok": False}
    info = await telegram.webhook_info() if token_set else {"ok": False}
    return {
        "token_configured": token_set,
        "bot": me.get("result") if me.get("ok") else None,
        "webhook": info.get("result") if info.get("ok") else None,
        "admin_ids": sorted(await effective_admin_ids()),
        "public_base_url": os.environ.get("PUBLIC_BASE_URL", ""),
    }


@admin_tg_router.post("/set-webhook")
async def set_webhook(admin=Depends(require_admin)):
    return await telegram.set_webhook()


@admin_tg_router.post("/test")
async def test_notification(admin=Depends(require_admin)):
    ids = await effective_admin_ids()
    if not ids:
        return {"ok": False, "detail": "No admin IDs configured yet."}
    await telegram.notify_admins("✅ <b>Test alert</b>\nTelegram notifications are working.")
    return {"ok": True, "sent_to": sorted(ids)}
