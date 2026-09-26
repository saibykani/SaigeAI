"""Audit logging for every important action (spec section 43)."""

from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database import collections as c
from app.utils import new_id, utcnow

# Keys whose values must never be written to the audit log.
_REDACT = {"password", "password_hash", "token", "refresh_token", "access_token", "secret", "otp"}


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: ("[REDACTED]" if k.lower() in _REDACT else redact(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


async def log_action(
    db: AsyncIOMotorDatabase,
    *,
    user_id: str | None,
    action: str,
    entity: str | None = None,
    entity_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> str:
    doc = {
        "_id": new_id(),
        "user_id": user_id,
        "action": action,
        "entity": entity,
        "entity_id": entity_id,
        "details": redact(details or {}),
        "timestamp": utcnow(),
    }
    await db[c.AUDIT_LOGS].insert_one(doc)
    return doc["_id"]
