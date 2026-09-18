import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from app.db import create_indexes, close, api_keys, client_keys  # noqa: E402
from app.logging_setup import setup_logging  # noqa: E402
from app.settings_store import ensure_settings, get_settings  # noqa: E402
from app import key_manager as km  # noqa: E402
from app import client_keys as ck  # noqa: E402
from app import job_manager as jm  # noqa: E402
from app.routes.auth_routes import router as auth_router  # noqa: E402
from app.routes.admin_routes import router as admin_router  # noqa: E402
from app.routes.router_api import router as router_api  # noqa: E402
from app.routes.telegram_routes import webhook_router, admin_tg_router  # noqa: E402
from app import telegram  # noqa: E402

logger = setup_logging(os.environ.get("LOG_LEVEL", "INFO"))

app = FastAPI(title="AI Router Control Centre", version="1.0.0")


@app.get("/api/")
async def root():
    return {"service": "AI Router Control Centre", "status": "ok"}


@app.get("/api/health")
async def public_health():
    s = await get_settings()
    return {"status": "online", "paused": s.get("paused", False)}


app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(router_api)
app.include_router(webhook_router)
app.include_router(admin_tg_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _seed():
    await ensure_settings()

    # Seed the demo router client key (hash only stored; plaintext lives in env).
    demo_client = os.environ.get("DEMO_CLIENT_KEY")
    if demo_client and await client_keys.count_documents({}) == 0:
        await ck.create_client_key("Default Client (Cline)", plaintext=demo_client)
        logger.info("Seeded default router client key")

    # Seed the Emergent Universal Key as the first provider key (user-owned, in env).
    if os.environ.get("SEED_EMERGENT_KEY", "false").lower() == "true":
        emergent = os.environ.get("EMERGENT_LLM_KEY")
        if emergent and await api_keys.count_documents({}) == 0:
            await km.add_key(emergent, "Emergent Universal Key #1", priority=1, provider="emergent")
            logger.info("Seeded Emergent Universal Key as provider key #1")


@app.on_event("startup")
async def on_startup():
    await create_indexes()
    await _seed()
    recovered = await jm.recover_stale_jobs()
    if recovered:
        logger.info("Recovery: marked %s in-flight request(s) as interrupted", recovered)
    if os.environ.get("TELEGRAM_BOT_TOKEN"):
        res = await telegram.set_webhook()
        logger.info("Telegram webhook setup: %s", "ok" if res.get("ok") else "skipped/failed")
    logger.info("AI Router Control Centre started")


@app.on_event("shutdown")
async def on_shutdown():
    close()
