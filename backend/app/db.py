import os
from motor.motor_asyncio import AsyncIOMotorClient

_client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = _client[os.environ["DB_NAME"]]

# Collections (mirror the portable Supabase/Postgres schema in /migrations)
api_keys = db.api_keys
client_keys = db.client_keys
jobs = db.jobs
requests = db.requests
failovers = db.failovers
health_checks = db.health_checks
settings_col = db.settings
audit_logs = db.audit_logs
telegram_seen = db.telegram_seen


async def create_indexes():
    await api_keys.create_index("id", unique=True)
    await api_keys.create_index([("enabled", 1), ("priority", 1)])
    await client_keys.create_index("id", unique=True)
    await client_keys.create_index("key_hash", unique=True)
    await jobs.create_index("id", unique=True)
    await jobs.create_index("session_id")
    await requests.create_index("id", unique=True)
    await requests.create_index("job_id")
    await requests.create_index("idempotency_key")
    await failovers.create_index("job_id")
    await health_checks.create_index("key_id")
    await audit_logs.create_index([("created_at", -1)])


def close():
    _client.close()
