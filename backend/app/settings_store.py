from datetime import datetime, timezone

from app.config import DEFAULT_SETTINGS, admin_ids as env_admin_ids
from app.db import settings_col


async def effective_admin_ids() -> set:
    """Merge env TELEGRAM_ADMIN_IDS with the dashboard-managed list in settings."""
    ids = set(env_admin_ids())
    doc = await settings_col.find_one({"id": "singleton"}, {"_id": 0, "telegram_admin_ids": 1})
    for x in (doc or {}).get("telegram_admin_ids", []) or []:
        if str(x).strip():
            ids.add(str(x).strip())
    return ids


async def ensure_settings():
    doc = await settings_col.find_one({"id": "singleton"}, {"_id": 0})
    if not doc:
        doc = {"id": "singleton", **DEFAULT_SETTINGS,
               "updated_at": datetime.now(timezone.utc).isoformat()}
        await settings_col.insert_one(dict(doc))
    return doc


async def get_settings():
    doc = await settings_col.find_one({"id": "singleton"}, {"_id": 0})
    if not doc:
        return await ensure_settings()
    merged = {**DEFAULT_SETTINGS, **{k: v for k, v in doc.items() if k in DEFAULT_SETTINGS}}
    merged["id"] = "singleton"
    return merged


async def update_settings(patch: dict):
    allowed = {k: v for k, v in patch.items() if k in DEFAULT_SETTINGS}
    allowed["updated_at"] = datetime.now(timezone.utc).isoformat()
    await settings_col.update_one({"id": "singleton"}, {"$set": allowed}, upsert=True)
    return await get_settings()
