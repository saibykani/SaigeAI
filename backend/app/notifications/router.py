from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import DESCENDING

from app.auth.deps import db_dep, get_current_user
from app.database import collections as c

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _out(n: dict) -> dict:
    return {"id": n["_id"], "kind": n["kind"], "title": n["title"], "body": n.get("body", ""),
            "link": n.get("link"), "read": n.get("read", False),
            "created_at": n["created_at"].isoformat()}


@router.get("")
async def list_notifications(unread_only: bool = False, user: dict = Depends(get_current_user),
                             db: AsyncIOMotorDatabase = Depends(db_dep)):
    q: dict = {"user_id": user["_id"]}
    if unread_only:
        q["read"] = False
    docs = await db[c.NOTIFICATIONS].find(q).sort("created_at", DESCENDING).to_list(length=100)
    return [_out(n) for n in docs]


@router.post("/{notification_id}/read")
async def mark_read(notification_id: str, user: dict = Depends(get_current_user),
                    db: AsyncIOMotorDatabase = Depends(db_dep)):
    res = await db[c.NOTIFICATIONS].update_one({"_id": notification_id, "user_id": user["_id"]},
                                               {"$set": {"read": True}})
    if not res.matched_count:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification not found")
    return {"ok": True}
