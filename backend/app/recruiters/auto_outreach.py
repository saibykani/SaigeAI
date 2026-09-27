"""Auto outreach mode (standing approval, like Happpy's "Auto Mode"): when the user turns it on, Saige
sends truth-checked messages from their Gmail without asking each time:
  - replies it drafted to recruiter emails,
  - follow-ups when an outreach email got no reply,
  - (optional) a cold email to HR contacts published in postings the user applied to.
Every message still passes the truth guard, the pauses, blocked companies and the caps (10/day,
3 people per company per week), and each send is notified in-app and on WhatsApp.
"""

from fastapi import HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database import collections as c
from app.recruiters import service as rs
from app.schemas.recruiter import DraftIn
from app.utils import utcnow


async def _send(db, uid: str, outreach_id: str) -> str:
    try:
        await rs.send_now(db, uid, outreach_id, approve_first=True)
        return "sent"
    except HTTPException as exc:
        return "cap" if exc.status_code == 429 else "skipped"


async def run(db: AsyncIOMotorDatabase, uid: str, s, now=None) -> dict:
    if s.outreach.mode != "auto":
        return {"skipped": "outreach is in manual mode"}
    if not await db[c.INTEGRATIONS].find_one({"user_id": uid, "provider": "gmail", "method": "app_password"}):
        return {"skipped": "connect Gmail with an App Password to send automatically"}
    now = now or utcnow()
    out = {"replies": 0, "followups": 0, "cold": 0, "held": 0}

    async def go(outreach_id: str, key: str) -> bool:
        r = await _send(db, uid, outreach_id)
        if r == "sent":
            out[key] += 1
        elif r == "cap":
            return False
        else:
            out["held"] += 1
        return True

    if s.outreach.send_replies:
        async for d in db[c.OUTREACH].find({"user_id": uid, "kind": "reply", "status": "draft", "validation.status": "PASSED"}).limit(20):
            if not await go(d["_id"], "replies"):
                return out

    if s.outreach.send_followups:
        async for f in db[c.FOLLOWUPS].find({"user_id": uid, "kind": "outreach_followup", "status": {"$in": ["scheduled", "due"]},
                                             "due_at": {"$lte": now}}).limit(20):
            parent = await db[c.OUTREACH].find_one({"_id": f.get("outreach_id"), "user_id": uid})
            if not parent or parent["status"] != "sent":  # replied / bounced: no follow-up
                await rs.complete_followup(db, uid, f["_id"])
                continue
            try:
                draft = await rs.create_draft(db, uid, DraftIn(contact_id=parent["contact_id"], kind="followup", parent_id=parent["_id"],
                                                               job_id=parent.get("job_id")))
            except HTTPException:
                continue
            await rs.complete_followup(db, uid, f["_id"])
            if not await go(draft["id"], "followups"):
                return out

    if s.outreach.cold_email_jobs:
        async for a in db[c.APPLICATIONS].find({"user_id": uid, "status": {"$in": ["APPLIED", "APPLYING", "READY_TO_APPLY"]}}).limit(40):
            key = rs.company_key(a["company"])
            ct = await db[c.RECRUITER_CONTACTS].find_one({"user_id": uid, "company_key": key, "email": {"$ne": None},
                                                          "last_contacted_at": None, "unsubscribed": {"$ne": True}})
            if not ct or await db[c.OUTREACH].find_one({"user_id": uid, "contact_id": ct["_id"]}):
                continue
            try:
                draft = await rs.create_draft(db, uid, DraftIn(contact_id=ct["_id"], kind="cold", job_id=a.get("job_id")))
            except HTTPException:
                continue
            if not await go(draft["id"], "cold"):
                return out
    return out
