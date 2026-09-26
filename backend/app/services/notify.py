"""Notification creation helper (spec section 38)."""

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database import collections as c
from app.utils import new_id, utcnow


async def notify(
    db: AsyncIOMotorDatabase, *, user_id: str, kind: str, title: str, body: str = "",
    link: str | None = None, details: list[dict] | None = None,
) -> str:
    """`details`: optional structured rows shown under the notification, e.g. profile field changes
    as {"platform", "field", "before", "after"}."""
    doc = {
        "_id": new_id(), "user_id": user_id, "kind": kind, "title": title, "body": body,
        "link": link, "details": (details or [])[:10], "read": False, "created_at": utcnow(),
    }
    await db[c.NOTIFICATIONS].insert_one(doc)
    from app.services.whatsapp import mirror  # local import keeps this helper dependency-light

    await mirror(db, user_id, title, body, doc["details"], link, kind)
    return doc["_id"]
