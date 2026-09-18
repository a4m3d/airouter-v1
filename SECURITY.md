# Security Report — AI Router Control Centre

This document is intentionally honest. The system is **not** claimed to be "100% secure."
Below are the protections implemented, the residual risks, and recommended production hardening.

## 1) Protections implemented

### Credential storage & privacy
- Provider keys are encrypted with **AES-256-GCM** (authenticated encryption) before storage; only ciphertext + a 96-bit nonce are persisted.
- The **master key** (`ENCRYPTION_MASTER_KEY`) exists only in backend environment; it is never stored in the DB, frontend, logs, Telegram, or Git.
- Keys are decrypted **only** at the moment of an outbound provider call.
- API responses and the frontend receive only a **masked** value (`••••••••A91F`) — never the full credential.
- Router client keys are stored as **SHA-256 hashes**; the plaintext `sk-router-…` is shown exactly once on creation/rotation.

### Authentication & authorization
- **Telegram Web App** auth is verified **server-side** using Telegram's official HMAC scheme over `initData`; the browser-supplied user id is never trusted without it. Admin allowlist via `TELEGRAM_ADMIN_IDS`.
- Alternative admin access uses a server-only `ADMIN_DASHBOARD_TOKEN`, exchanged for a short-lived (12h) **JWT**.
- Every admin endpoint requires the admin JWT; every router endpoint requires a valid, non-revoked client key.

### Secret-leakage prevention
- A logging **redaction filter** scrubs `sk-…`, `Bearer …`, and `key/token/secret/password=…` patterns from all log records.
- Structured logs record request id, key id, error class, and action — **never** prompts, responses, or credentials.
- Telegram notifications and callback data never contain credentials; `/addkey` deletes the message carrying the secret.

### Transport / platform
- CORS configurable via `CORS_ORIGINS`.
- SSE streaming sets `X-Accel-Buffering: no` to avoid proxy buffering (not a data risk, correctness).
- Postgres schema enables **Row Level Security**; the frontend never talks to the DB directly.

### Reliability / correctness
- Error classifier maps provider errors to conservative retry/failover policies.
- `INVALID_REQUEST` is returned immediately (never blindly replayed across every key).
- Idempotency keys prevent duplicate completion of the same non-streaming request.
- Atomic key selection (lock + `last_used` stamp) reduces double-selection races.

## 2) Remaining risks / limitations
- **Mid-stream failover is impossible**: once tokens are emitted, a provider failure cannot be transparently transferred to another key. The stream ends with an error event (documented). Pre-first-token failover *is* supported.
- **No programmatic balance**: the provider exposes no reliable balance endpoint; "exhaustion" is inferred from error signals, so a key may be tried once before being marked exhausted.
- **Single-process locking** in the live demo: cross-process/worker safety requires the Redis/Postgres locking path in the portable deployment.
- **Rate limiting** on the router API itself is coarse (per-client counters); add a proper limiter (e.g. Redis token bucket) for hostile environments.
- **Admin token auth** is a shared secret; prefer Telegram-verified admin access in production and rotate the token.
- **Token usage counts** are reported as zero (the library does not surface token accounting here); do not rely on them for billing.

## 3) Recommended production configuration
1. Serve everything behind TLS (Caddy/nginx/Traefik). Terminate HTTPS; forward `/api/*` → backend.
2. Set a strict `CORS_ORIGINS` (your dashboard origin only), not `*`.
3. Use Telegram-verified admin auth; keep `ADMIN_DASHBOARD_TOKEN` for break-glass only and rotate it.
4. Store all secrets in a managed secret store (Docker/K8s secrets, Vault, cloud secret manager); never in the image.
5. Use the Postgres/Supabase + Redis path for multi-worker deployments; run `migrations/001_init.sql` and keep RLS on.
6. Add a Redis-backed rate limiter and per-client quotas.
7. Enable DB backups + periodic key rotation; monitor `audit_logs`.
8. Run `pip-audit` / dependency scanning in CI; pin and update dependencies.
9. Restrict egress from the backend to the provider endpoints (SSRF containment).

## 4) Checklist vs. requested audit areas
| Area | Status |
|---|---|
| Authentication | Telegram HMAC + JWT + client keys |
| Authorization | admin-only endpoints, admin allowlist |
| Secret storage | env-only master key; no plaintext secrets in DB |
| Encryption | AES-256-GCM |
| DB security | RLS enabled, service-role backend-only |
| Telegram Web App auth | verified server-side |
| API auth | client key required, revocable/rotatable |
| Rate limiting | basic per-client counters (harden in prod) |
| Input validation | pydantic models + explicit checks |
| SQL injection | parameterized (SQLAlchemy/Supabase) / Mongo driver |
| Command injection | none: no shell exec on user input |
| XSS | React escaping; no `dangerouslySetInnerHTML` |
| SSRF | no user-controlled outbound URLs; restrict egress in prod |
| Sensitive logging | redaction filter |
| Error leakage | generic error messages, no stack traces to clients |
| Dependency vulns | run scanner in CI (recommended) |
| CORS | configurable; tighten in prod |
| Exposed ports | only 8001/3000/6379 via compose; put behind proxy |
| Docker config | slim base, `.dockerignore`, no secrets baked in |
| GitHub secret leakage | `.env` git-ignored; `.env.example` only |
