"""Mobile app endpoints: the "pulse" the app polls for notifications, and swipe actions on the job feed.

The pulse only reads records already in Saige (sent_emails, outreach drafts, prepared applications). Nothing is sent
from here: approving still goes through the normal endpoints (/outreach/{id}/send?approve=true, /applications/approve-bulk),
so the truth guard, pauses and daily caps all apply.
"""

import secrets
from datetime import UTC, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field
from pymongo import DESCENDING

from app.auth.deps import db_dep, get_current_user
from app.database import collections as c
from app.extension.router import PAT_PREFIX, _hash, scoped_user
from app.services.audit import log_action
from app.utils import new_id, utcnow

router = APIRouter(prefix="/mobile", tags=["mobile"])
_bearer = HTTPBearer(auto_error=False)

APPROVABLE_APPS = ["READY_TO_APPLY", "APPROVAL_REQUIRED"]
LIMIT = 20


def _iso(d) -> str | None:
    return d.isoformat() if isinstance(d, datetime) else d


@router.post("/pulse-token", status_code=201)
async def pulse_token(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    """A read-only token the phone uses for background checks (it can only read /mobile/pulse/bg). One per user: creating
    a new one revokes the old one. Kept apart from the login session so background checks never rotate it."""
    uid = user["_id"]
    await db[c.API_TOKENS].update_many({"user_id": uid, "scopes": "pulse", "revoked": False}, {"$set": {"revoked": True, "revoked_at": utcnow()}})
    token = PAT_PREFIX + secrets.token_urlsafe(32)
    await db[c.API_TOKENS].insert_one({"_id": new_id(), "user_id": uid, "name": "Phone alerts", "token_hash": _hash(token),
                                       "prefix": token[: len(PAT_PREFIX) + 4], "scopes": ["pulse"], "revoked": False,
                                       "created_at": utcnow(), "last_used_at": None})
    await log_action(db, user_id=uid, action="api_token.created", entity="api_token", details={"name": "Phone alerts"})
    return {"token": token}


@router.delete("/pulse-token", status_code=204)
async def revoke_pulse_token(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    await db[c.API_TOKENS].update_many({"user_id": user["_id"], "scopes": "pulse", "revoked": False},
                                       {"$set": {"revoked": True, "revoked_at": utcnow()}})


async def pulse_user(creds: HTTPAuthorizationCredentials | None = Depends(_bearer), db: AsyncIOMotorDatabase = Depends(db_dep)) -> dict:
    return await scoped_user(creds, db, "pulse")


@router.get("/pulse/bg")
async def pulse_bg(since: datetime | None = None, user: dict = Depends(pulse_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    """Same as /pulse, for the phone's background check (pulse token only)."""
    return await _pulse(db, user["_id"], since)


@router.get("/pulse")
async def pulse(since: datetime | None = None, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    """New replies/bounces since `since` (default: last 3 days) and everything waiting for the user's approval."""
    return await _pulse(db, user["_id"], since)


async def _pulse(db: AsyncIOMotorDatabase, uid: str, since: datetime | None) -> dict:
    since = since or utcnow() - timedelta(days=3)
    replies = []
    q = {"user_id": uid, "status": {"$in": ["replied", "bounced"]}, "$or": [{"replied_at": {"$gt": since}}, {"updated_at": {"$gt": since}}]}
    async for s in db[c.SENT_EMAILS].find(q).sort("replied_at", DESCENDING).limit(LIMIT):
        replies.append({"id": s["_id"], "status": s["status"], "to": s.get("to"), "company": s.get("company"), "subject": s.get("subject"),
                        "category": s.get("reply_category"), "snippet": s.get("reply_snippet"), "email_id": s.get("reply_email_id"),
                        "at": _iso(s.get("replied_at") or s.get("updated_at"))})

    approvals = []
    drafts = await db[c.OUTREACH].find({"user_id": uid, "status": "draft", "kind": {"$ne": "linkedin_note"},
                                        "validation.status": "PASSED"}).sort("created_at", DESCENDING).limit(LIMIT).to_list(LIMIT)
    cids = list({d.get("contact_id") for d in drafts if d.get("contact_id")})
    contacts = {x["_id"]: x async for x in db[c.RECRUITER_CONTACTS].find({"_id": {"$in": cids}, "user_id": uid},
                                                                          {"name": 1, "company": 1, "email": 1})}
    for d in drafts:
        ct = contacts.get(d.get("contact_id")) or {}
        if not ct.get("email"):
            continue  # can't be emailed from a notification; needs the app
        approvals.append({"type": "outreach", "id": d["_id"], "title": f"Email {ct.get('name') or ct.get('email')}",
                          "company": ct.get("company"), "subject": d.get("subject"), "preview": (d.get("body") or "")[:200],
                          "at": _iso(d.get("created_at"))})

    apps = await db[c.APPLICATIONS].find({"user_id": uid, "status": {"$in": APPROVABLE_APPS}, "apply_email": {"$nin": [None, ""]}}
                                         ).sort("created_at", DESCENDING).limit(LIMIT).to_list(LIMIT)
    jids = [a["job_id"] for a in apps if a.get("job_id")]
    jobs = {j["_id"]: j async for j in db[c.JOBS].find({"_id": {"$in": jids}, "user_id": uid}, {"title": 1, "company": 1})}
    for a in apps:
        j = jobs.get(a.get("job_id")) or {}
        approvals.append({"type": "application", "id": a["_id"], "title": f"Apply: {j.get('title') or 'job'}", "company": j.get("company"),
                          "subject": f"Email your resume to {a['apply_email']}", "preview": None, "at": _iso(a.get("created_at"))})

    return {"now": utcnow().isoformat(), "replies": replies, "approvals": approvals,
            "counts": {"replies": len(replies), "approvals": len(approvals)}}


class HideIn(BaseModel):
    id: str = Field(min_length=1, max_length=200)


@router.post("/feed/hide")
async def hide(body: HideIn, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    """Swipe left: hide a feed job for this user (it stays hidden after the feed refreshes)."""
    uid = user["_id"]
    doc = await db[c.JOB_FEED].find_one({"_id": uid}, {"items": 1}) or {}
    it = next((i for i in doc.get("items", []) if i.get("id") == body.id), None)
    if not it:
        raise HTTPException(404, "That job is no longer in your feed.")
    await db[c.FEED_HIDDEN].update_one({"_id": f"{uid}:{body.id}"}, {"$set": {
        "user_id": uid, "item_id": body.id, "title": it.get("title"), "company": it.get("company"), "at": utcnow()}}, upsert=True)
    await log_action(db, user_id=uid, action="jobs.feed_hidden", entity="job_feed", details={"id": body.id})
    return {"hidden": body.id}


@router.post("/feed/unhide")
async def unhide(body: HideIn, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    """Undo a swipe left."""
    await db[c.FEED_HIDDEN].delete_one({"_id": f"{user['_id']}:{body.id}"})
    return {"unhidden": body.id}


async def hidden_ids(db: AsyncIOMotorDatabase, uid: str) -> set[str]:
    return {h["item_id"] async for h in db[c.FEED_HIDDEN].find({"user_id": uid}, {"item_id": 1})}


# ------------------------------------------------------------------ daily goal + streak

IST = timezone(timedelta(hours=5, minutes=30))
STREAK_LOOKBACK_DAYS = 400
_STREAK_SOURCES = [(c.APPLICATIONS, ["created_at", "applied_at", "approved_at"]), (c.OUTREACH, ["sent_at"]),
                   (c.INTERVIEWS, ["created_at"]), (c.MOCK_INTERVIEWS, ["created_at"])]


def _ist_day(d: datetime):
    if d.tzinfo is None:
        d = d.replace(tzinfo=UTC)
    return d.astimezone(IST).date()


async def activity_by_day(db: AsyncIOMotorDatabase, uid: str, since: datetime) -> dict:
    """Real actions per IST day: applications created/applied/approved, outreach sent, interviews logged, mock interviews."""
    counts: dict = {}
    for coll, fields in _STREAK_SOURCES:
        # one action per (record, field) so an application created and approved the same day counts twice only if both happened
        query = {"user_id": uid, "$or": [{f: {"$gte": since}} for f in fields]}
        async for doc in db[coll].find(query, {f: 1 for f in fields}):
            days = {_ist_day(doc[f]) for f in fields if isinstance(doc.get(f), datetime) and doc[f] >= since}
            for day in days:
                counts[day] = counts.get(day, 0) + 1
    return counts


@router.get("/streak")
async def streak(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    """Daily goal and streak from real activity only (IST days). Goal = weekly goal for applications+outreach / 7, rounded up, min 1."""
    from app.growth.router import DEFAULT_GOALS

    uid = user["_id"]
    today = _ist_day(utcnow())
    counts = await activity_by_day(db, uid, utcnow() - timedelta(days=STREAK_LOOKBACK_DAYS))
    active = set(counts)

    cur = 0
    day = today if today in active else today - timedelta(days=1)
    while day in active:
        cur += 1
        day -= timedelta(days=1)
    best = run = 0
    prev = None
    for d in sorted(active):
        run = run + 1 if prev is not None and (d - prev).days == 1 else 1
        best = max(best, run)
        prev = d

    doc = await db[c.GOALS].find_one({"_id": uid}) or {}
    weekly = int(doc.get("applications", DEFAULT_GOALS["applications"])) + int(doc.get("outreach", DEFAULT_GOALS["outreach"]))
    goal = max(1, -(-weekly // 7)) if weekly > 0 else 1
    return {"current": cur, "best": best, "today": counts.get(today, 0), "goal": goal,
            "goal_met": counts.get(today, 0) >= goal,
            "last7": [{"date": (today - timedelta(days=i)).isoformat(), "active": (today - timedelta(days=i)) in active} for i in range(6, -1, -1)]}
