# Test Credentials
# Agent writes here when creating/modifying auth credentials (admin accounts, test users).
# Testing agent reads this before auth tests. Fork/continuation agents read on startup.

## Admin dashboard login (frontend + Telegram Web App fallback)
- Login method: POST /api/auth/login  body: {"admin_token": "<ADMIN_DASHBOARD_TOKEN>"}
- ADMIN_DASHBOARD_TOKEN: abkA-iyoH_7uWKMb3_mr43nzFl4YHs99
- On the login screen, paste this into the "Administrator Token" field.

## Router client API key (for OpenAI-compatible endpoint, e.g. Cline)
- Header: Authorization: Bearer sk-router-Y7as_5RakGo-uoD6_VyGVF04AU-OG4Ut
- Base URL for agents: {REACT_APP_BACKEND_URL}/api/v1
- Endpoints: POST /api/v1/chat/completions , GET /api/v1/models

## Seeded provider key
- "Emergent Universal Key #1" is auto-seeded from EMERGENT_LLM_KEY (priority 1, healthy).
- Additional keys are added via the dashboard (API KEYS → Add Key) or bot /addkey.

## Telegram (LIVE)
- Bot: @theairouterbot (TELEGRAM_BOT_TOKEN set in backend/.env)
- Webhook: {PUBLIC_BASE_URL}/api/telegram/webhook (auto-registered on startup, secret = ROUTER_INTERNAL_SECRET)
- Admin IDs: managed in dashboard Settings → Telegram (stored in settings.telegram_admin_ids), merged with env TELEGRAM_ADMIN_IDS.
- To authorize yourself: message the bot /start → it replies your numeric ID → paste into Settings → Telegram → Save.
- Telegram WebApp HMAC login uses this same admin allowlist.
