-- AI Router Control Centre — Supabase / PostgreSQL schema (portable deployment)
-- The live Emergent demo uses MongoDB collections mirroring these tables.
-- Credentials are stored ONLY as AES-256-GCM ciphertext (+ nonce). Plaintext keys
-- and the master key are NEVER stored here.

create extension if not exists pgcrypto;

create table if not exists users (
    id uuid primary key default gen_random_uuid(),
    telegram_id text unique not null,
    display_name text,
    is_admin boolean not null default false,
    created_at timestamptz not null default now()
);

create table if not exists api_keys (
    id uuid primary key default gen_random_uuid(),
    label text not null,
    provider text not null default 'emergent',
    ciphertext text not null,          -- AES-256-GCM ciphertext (base64)
    nonce text not null,               -- 96-bit nonce (base64)
    mask text not null,                -- e.g. ••••••••A91F
    enabled boolean not null default true,
    health_status text not null default 'unknown',  -- healthy|cooldown|exhausted|unhealthy|unknown
    priority integer not null default 100,
    request_count integer not null default 0,
    success_count integer not null default 0,
    failure_count integer not null default 0,
    failover_count integer not null default 0,
    avg_latency_ms integer,
    last_used_at timestamptz,
    last_error_at timestamptz,
    last_error_type text,
    cooldown_until timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create index if not exists idx_api_keys_enabled_priority on api_keys (enabled, priority);

create table if not exists client_keys (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    key_hash text unique not null,     -- sha256 of the router client key; plaintext never stored
    key_prefix text not null,
    enabled boolean not null default true,
    rate_limit integer,
    request_count integer not null default 0,
    revoked_at timestamptz,
    created_at timestamptz not null default now()
);

create table if not exists jobs (
    id text primary key,
    session_id text not null,
    client_id uuid references client_keys(id) on delete set null,
    provider text,
    model text,
    current_key_id uuid references api_keys(id) on delete set null,
    current_step integer not null default 0,
    status text not null default 'running',   -- running|success|failed
    retry_count integer not null default 0,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create index if not exists idx_jobs_session on jobs (session_id);

create table if not exists requests (
    id text primary key,
    job_id text references jobs(id) on delete cascade,
    session_id text,
    client_id uuid,
    provider text,
    model text,
    idempotency_key text,
    key_id uuid references api_keys(id) on delete set null,
    status text not null default 'pending',   -- pending|running|success|failed|interrupted
    error_type text,
    action text,
    next_key_id uuid,
    latency_ms integer,
    attempts integer not null default 0,
    step integer,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create index if not exists idx_requests_job on requests (job_id);
create index if not exists idx_requests_idem on requests (client_id, idempotency_key);

create table if not exists failovers (
    id text primary key,
    job_id text references jobs(id) on delete cascade,
    request_id text,
    from_key_id uuid,
    to_key_id uuid,
    reason text,
    created_at timestamptz not null default now()
);

create table if not exists health_checks (
    id uuid primary key default gen_random_uuid(),
    key_id uuid references api_keys(id) on delete cascade,
    ok boolean not null,
    error_type text,
    latency_ms integer,
    created_at timestamptz not null default now()
);

create table if not exists settings (
    id text primary key default 'singleton',
    routing_strategy text not null default 'priority',
    retry_count integer not null default 2,
    cooldown_seconds integer not null default 300,
    rate_limit_cooldown_seconds integer not null default 60,
    request_timeout integer not null default 120,
    max_concurrent_jobs integer not null default 20,
    health_check_interval integer not null default 0,
    logging_level text not null default 'INFO',
    paused boolean not null default false,
    notifications jsonb not null default '{}'::jsonb,
    updated_at timestamptz not null default now()
);

create table if not exists audit_logs (
    id uuid primary key default gen_random_uuid(),
    actor text,
    action text not null,
    target text,
    meta jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

-- Row Level Security: only the backend service-role key touches these tables.
-- The anon key has no access; the frontend only ever calls the backend API.
alter table api_keys enable row level security;
alter table client_keys enable row level security;
alter table jobs enable row level security;
alter table requests enable row level security;
alter table failovers enable row level security;
alter table health_checks enable row level security;
alter table settings enable row level security;
alter table audit_logs enable row level security;
-- No permissive policies are created for anon/authenticated roles by design.
-- The service-role key bypasses RLS and is used exclusively by the backend.
