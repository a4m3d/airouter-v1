# 🤖 AI Router Control Centre

A production-ready, security-focused **multi-key AI API router** with a **Telegram Bot + Telegram Web App** control centre. It presents a single **OpenAI-compatible endpoint** to your coding agents (Cline, Roo Code, Cursor, etc.) and transparently fails over between multiple legitimately-authorized provider keys — **without restarting the logical job**.

```
Your App / Cline  →  Router API (OpenAI-compatible)  →  Routing + Failover Engine
                                                          ├─ Key #1  (Emergent Universal Key)
                                                          ├─ Key #2
                                                          └─ Key #N
```

> **Provider integration:** models are served via the official `emergentintegrations` library (OpenAI / Anthropic / Gemini). No undocumented endpoints, headers, models, or error codes are invented. The provider does **not** expose a reliable programmatic credit-balance endpoint, so the dashboard shows request/success/failure/failover counters and **never fabricates balances**.

---

## Features
- **OpenAI-compatible API** — `POST /api/v1/chat/completions` (streaming + non-streaming), `GET /api/v1/models`.
- **Multi-key pool** — priority, round-robin, LRU; enable/disable, test, change priority.
- **Automatic failover** with per-error-class policy (see below).
- **Job/session continuity** — failover keeps the same logical job; steps are tracked.
- **Idempotency** — `Idempotency-Key` header replays a completed non-streaming result.
- **AES-256-GCM** credential encryption; master key stays server-side only.
- **Telegram control** — bot commands + a polished Telegram Web App dashboard.
- **Structured logs** with automatic credential redaction.
- **Portable** — Docker + docker-compose + Supabase/Postgres migrations + Redis.

### Error classification → action
| Class | Action |
|---|---|
| `CREDIT_EXHAUSTED` | mark key exhausted (cooldown) → **failover** |
| `RATE_LIMIT` | short cooldown → **failover** |
| `AUTH_FAILED` | **disable** key + notify admin → failover |
| `PROVIDER_ERROR` / `TIMEOUT` / `NETWORK` | retry same key (`retry_count`) → failover |
| `INVALID_REQUEST` | **return error** (never blindly retried across keys) |
| `UNKNOWN` | conservative retry → failover |

---

## Repository layout
```
backend/            FastAPI app (app/ package) + bot/ (aiogram)
  app/
    providers/      provider adapter + error classifier
    routes/         auth, admin, OpenAI-compatible router API
    security/       AES-256-GCM crypto, Telegram auth, JWT/client auth
    engine.py       routing + failover engine
    key_manager.py  encrypted key pool, health, selection
    job_manager.py  job/session state, recovery, idempotency
  bot/bot.py        Telegram control bot
frontend/           React Telegram Web App dashboard
migrations/         Supabase/PostgreSQL schema (001_init.sql)
tests/              pytest unit + mocked-failover tests
Dockerfile, docker-compose.yml, .env.example, SECURITY.md
```

---

## 1) Local development
```bash
# Backend (requires MongoDB locally for the demo stack, or Postgres for portable)
cd backend
pip install --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/ -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8001 --reload

# Frontend
cd ../frontend
yarn install && yarn start
```

## 2) Supabase / PostgreSQL setup (portable)
1. Create a Supabase project.
2. Run `migrations/001_init.sql` in the SQL editor.
3. Put `DATABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` in `.env` (**backend only**).
   RLS is enabled with no permissive anon policies; the backend uses the service-role key.

## 3) Redis setup
Portable job-state/locking uses Redis (`REDIS_URL`). The live demo uses in-process
durable state persisted to the database. `docker-compose` ships a `redis` service.

## 4) Telegram Bot setup
1. Talk to **@BotFather** → `/newbot` → copy the token into `TELEGRAM_BOT_TOKEN`.
2. Set `TELEGRAM_ADMIN_IDS` to your numeric Telegram id(s) (comma-separated). Get yours from **@userinfobot**.
3. Run the bot: `python -m bot.bot` (or the `bot` compose service).

## 5) Telegram Web App setup
1. Deploy the frontend over HTTPS; set `WEBAPP_URL` to that URL.
2. In @BotFather → Bot Settings → **Menu Button / Web App** → set the URL.
3. Opening it inside Telegram auto-authenticates via signed `initData` (verified server-side).
   Outside Telegram, admins use the dashboard admin token.

## 6) Environment variables
See `.env.example`. Server-only secrets (never sent to the frontend):
`ENCRYPTION_MASTER_KEY`, `ADMIN_JWT_SECRET`, `ADMIN_DASHBOARD_TOKEN`, `ROUTER_INTERNAL_SECRET`,
`SUPABASE_SERVICE_ROLE_KEY`, `TELEGRAM_BOT_TOKEN`, `EMERGENT_LLM_KEY`.

Generate secrets:
```bash
python -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())"   # ENCRYPTION_MASTER_KEY
python -c "import secrets;print(secrets.token_urlsafe(32))"                      # JWT / tokens
```

## 7) Provider configuration
Models come from `backend/app/config.py::SUPPORTED_MODELS`. Add/remove models there — the
`/api/v1/models` list and validation follow it. Only models supported by the configured
integration are exposed.

## 8) Adding API keys
- **Telegram Web App** → API KEYS → *Add Key* → paste the Universal Key. It is validated,
  encrypted (AES-256-GCM), then stored. Only a masked value (`••••••••A91F`) is ever shown again.
- **Bot**: `/addkey <key>` (the message is deleted after processing).

## 9) Using the router from a coding agent (Cline)
In Cline → OpenAI-Compatible provider:
- **Base URL:** `https://<your-host>/api/v1`
- **API Key:** a router client key (`sk-router-…`) created under **CLIENT KEYS**
- **Model:** e.g. `gpt-5.4`, `claude-sonnet-4-6`, `gemini-3.1-pro-preview`

```bash
curl -s https://<your-host>/api/v1/chat/completions \
  -H "Authorization: Bearer sk-router-XXXX" \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-5.4","messages":[{"role":"user","content":"Hello"}]}'
```
Optional headers: `X-Session-Id` (job continuity), `Idempotency-Key` (safe replay).

## 10) Running tests
```bash
cd /app && python -m pytest tests/ -q
```
Covers: error classification, AES-GCM roundtrip, credential masking, Telegram auth
(valid/tampered/wrong-token), log redaction, message flattening, and mocked failover
scenarios (credit exhaustion, auth failure, invalid-request no-failover, 5xx retry, no-healthy-keys).

## 11) Docker deployment
```bash
cp .env.example .env    # fill in secrets
docker compose up -d --build
# backend :8001  frontend :3000  redis :6379  bot (polling)
```

## 12) Production deployment / HTTPS
Put the backend and frontend behind a reverse proxy (nginx/Caddy/Traefik) with TLS.
Route `https://host/api/*` → backend:8001 and `https://host/*` → frontend:3000.
Keep `X-Accel-Buffering: no` for the SSE streaming route (already set by the app).

## 13) Secret management
Secrets live only in environment/secret storage. `.env` is git-ignored. The master
encryption key and Supabase service-role key must never be committed, logged, sent to
the frontend, or shown in Telegram. Rotate `ADMIN_JWT_SECRET`/client keys periodically.

## 14) Backup & recovery
Back up the database regularly (Supabase automated backups or `pg_dump`). On restart the
backend marks in-flight requests as `interrupted` (a partially-streamed response cannot be
safely resumed); completed requests with an idempotency key remain replayable.

## Provider compliance
Use only provider keys/accounts you are legitimately authorized to use. This router does
**not** implement anything to bypass provider security, account restrictions, rate limits,
or terms — it fails over across keys you own and applies cooldowns that respect provider signals.

See **SECURITY.md** for the full security report (protections, residual risks, production hardening).
