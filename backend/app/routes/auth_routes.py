import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.security.auth import create_admin_token
from app.security.telegram_auth import verify_webapp_init_data
from app.settings_store import effective_admin_ids

router = APIRouter(prefix="/api/auth")


class LoginRequest(BaseModel):
    init_data: str | None = None      # Telegram Web App initData (production path)
    admin_token: str | None = None    # Dashboard admin token (demo / direct access)


@router.post("/login")
async def login(body: LoginRequest):
    # Path 1: Telegram Web App — verify HMAC server-side, then check admin allowlist.
    if body.init_data:
        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        if not bot_token:
            raise HTTPException(status_code=503, detail="Telegram bot not configured")
        user = verify_webapp_init_data(body.init_data, bot_token)
        if not user:
            raise HTTPException(status_code=401, detail="Telegram authentication failed")
        uid = str(user.get("id"))
        allow = await effective_admin_ids()
        if not allow:
            raise HTTPException(status_code=403,
                                detail="No administrators configured yet. Add your Telegram ID in Settings → Telegram.")
        if uid not in allow:
            raise HTTPException(status_code=403, detail="Not an authorized administrator")
        return {"token": create_admin_token(uid, "telegram"),
                "admin": {"id": uid, "name": user.get("first_name")}}

    # Path 2: Admin dashboard token (server-only secret).
    if body.admin_token:
        expected = os.environ.get("ADMIN_DASHBOARD_TOKEN")
        if not expected or body.admin_token != expected:
            raise HTTPException(status_code=401, detail="Invalid admin token")
        return {"token": create_admin_token("dashboard-admin", "admin_token"),
                "admin": {"id": "dashboard-admin", "name": "Administrator"}}

    raise HTTPException(status_code=400, detail="Provide init_data or admin_token")
