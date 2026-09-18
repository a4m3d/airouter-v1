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

## Telegram
- TELEGRAM_BOT_TOKEN / TELEGRAM_ADMIN_IDS are empty in this demo (bot not running live).
- Telegram Web App HMAC verification path is implemented and unit-tested.
