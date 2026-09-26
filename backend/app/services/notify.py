"""Notification creation helper (spec section 38)."""

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database import collections as c
from app.utils import new_id, utcnow


async def notify(
    db: AsyncIOMotorDatabase, *, user_id: str, kind: str, title: str, body: str = "",
    link: str | None = None,
) -> str:
    doc = {
        "_id": new_id(), "user_id": user_id, "kind": kind, "title": title, "body": body,
        "link": link, "read": False, "created_at": utcnow(),
    }
    await db[c.NOTIFICATIONS].insert_one(doc)
    return doc["_id"]
