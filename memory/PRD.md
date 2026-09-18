# PRD — AI Router Control Centre

## Original problem statement
Build a production-ready, security-focused multi-key AI API router with a Telegram Bot + Telegram Web App control centre. A single OpenAI-compatible endpoint for the user's apps/coding agents (Cline), routing across multiple legitimately-authorized Emergent Universal Keys with automatic failover that preserves the logical job/session. Highest priorities: credential security (never plaintext, never in frontend/logs/Git), correct error classification, reliable failover, job continuity, portability (Docker/Supabase/Redis), and a polished Telegram Web App.

## User choices (discovery)
- Provider integration via the official `emergentintegrations` library (OpenAI/Anthropic/Gemini).
- Support all three providers, selectable per request.
- Start with the Emergent Universal Key seeded; add more keys later via the UI.
- Deliver BOTH a live demo here (MongoDB + in-process durable state) AND a portable Docker/Supabase/Redis bundle.
- Telegram credentials to be added later (bot module built, not running live).
- Deployment target: generic VPS/Docker.
- Phase 1 = router/agent backend only (not the full app-builder UI).

## Architecture
- **API Gateway**: OpenAI-compatible `POST /api/v1/chat/completions` (+ streaming), `GET /api/v1/models`; client-key auth.
- **Provider adapter** (`providers/emergent.py`) + **error classifier** (`providers/errors.py`).
- **Key manager**: AES-256-GCM encrypted pool, health/cooldown, priority/round-robin/LRU selection (atomic).
- **Router engine** (`engine.py`): per-error-class retry/failover, job continuity.
- **Job manager**: session/job state, steps, idempotency, restart recovery.
- **Security**: env-only master key, log redaction, Telegram HMAC + admin JWT + client keys.
- **Telegram bot** (`bot/bot.py`, aiogram) + **React Telegram Web App** dashboard.
- **Storage**: MongoDB (live) / Supabase Postgres migrations + Redis (portable).

## Core requirements (static)
1. Keys never exposed to frontend / never plaintext / never in logs / never in Git.
2. Telegram auth verified server-side; unauthorized users rejected.
3. Provider errors classified; exhausted keys fail over; logical job continues.
4. No blind duplicate submission; idempotency where possible.
5. Portable outside Emergent; no bypass of provider restrictions.

## Implemented (2026-06-18)
- OpenAI-compatible router API (non-stream + SSE streaming) with client-key auth. ✅
- Multi-key manager with AES-256-GCM encryption, masking, health, cooldown, selection strategies. ✅
- Automatic failover with per-class policy (credit/rate/auth/5xx/timeout/network/invalid/unknown). ✅ (verified: bogus key → real key)
- Job/session continuity + steps + failover log + restart recovery + idempotency replay. ✅
- Admin API: dashboard, keys CRUD/test/priority, usage, jobs, health check, logs, settings, pause/resume, client keys create/rotate/revoke. ✅
- Auth: Telegram WebApp HMAC verification + admin JWT + admin-token demo path. ✅
- Telegram control bot (aiogram) module with full command set. ✅ (not running live — no token yet)
- React Telegram Web App dashboard (7 panels, dark command-center UI). ✅
- Portable bundle: Dockerfile, frontend Dockerfile, docker-compose, migrations/001_init.sql, .env.example, .gitignore, README, SECURITY report. ✅
- Tests: 24 unit/mocked-failover pytest pass; testing agent 21/21 backend + frontend flows pass. ✅

## Backlog (P1/P2 — not built)
- P1: Redis-backed job queue/locks wired into the live path (currently portable-only).
- P1: Real Telegram bot run + admin notifications end-to-end (needs bot token + admin IDs).
- P1: Redis token-bucket rate limiter + per-client quotas enforcement.
- P2: Live Postgres/Supabase driver in the running backend (currently Mongo live / SQL migrations for export).
- P2: Weighted-random routing strategy; auto background health checks.
- P2: Phase 2 — app-builder orchestrator (sandboxes, file ops, previews, git, deploy).

## Next tasks
- Collect TELEGRAM_BOT_TOKEN + TELEGRAM_ADMIN_IDS to activate the bot + admin alerts.
- Optionally add more Universal Keys to demonstrate multi-key failover with real credits.
