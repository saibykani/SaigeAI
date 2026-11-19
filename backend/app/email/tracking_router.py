from datetime import datetime

from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import DESCENDING

from app.auth.deps import db_dep, get_current_user
from app.database import collections as c
from app.email import tracking
from app.profiles.service import get_profile
from app.services.audit import log_action

router = APIRouter(prefix="/email-tracking", tags=["email-tracking"])


@router.get("/sent")
async def list_sent(kind: str | None = Query(default=None, pattern="^(outreach|apply|auto_apply|bulk|thank_you)$"),
                    status: str | None = Query(default=None, pattern="^(sent|replied|bounced)$"),
                    template: str | None = Query(default=None, max_length=120), company: str | None = Query(default=None, max_length=120),
                    since: datetime | None = None, until: datetime | None = None, page: int = Query(default=1, ge=1),
                    page_size: int = Query(default=25, ge=1, le=100), user: dict = Depends(get_current_user),
                    db: AsyncIOMotorDatabase = Depends(db_dep)):
    q = tracking.build_query(user["_id"], kind=kind, status=status, template=template, company=company, since=since, until=until)
    total = await db[c.SENT_EMAILS].count_documents(q)
    rows = await db[c.SENT_EMAILS].find(q).sort("sent_at", DESCENDING).skip((page - 1) * page_size).limit(page_size).to_list(page_size)
    return {"items": [tracking.sent_out(r) for r in rows], "total": total, "page": page, "page_size": page_size}


@router.get("/stats")
async def get_stats(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    profile = await get_profile(db, user["_id"])
    return await tracking.stats(db, user["_id"], profile.preferences.timezone or "Asia/Kolkata")


@router.post("/backfill")
async def backfill(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    """Link past sends and already-synced emails (read-only: uses mail already in Saige)."""
    out = await tracking.backfill(db, user["_id"])
    await log_action(db, user_id=user["_id"], action="email_tracking.backfill", entity="sent_emails", details=out)
    return out
