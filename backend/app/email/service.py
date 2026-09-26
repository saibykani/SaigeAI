"""Email ingestion: classify, link to an application and update its status (spec sections 21-23).

Status only ever moves forward through the pipeline (a late confirmation email never drags an
interviewing application back to APPLIED); rejection and offer can close any active application.
Every automatic change records the email id and timestamp for traceability.
"""

import re
from datetime import UTC, datetime

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.applications import service as apps
from app.database import collections as c
from app.email import classifier
from app.jobs.dedupe import company_key
from app.profiles.service import get_profile
from app.services.audit import log_action
from app.services.notify import notify
from app.utils import new_id, utcnow

STAGE_RANK = {s: i for i, s in enumerate([
    "DISCOVERED", "SHORTLISTED", "READY_TO_APPLY", "APPROVAL_REQUIRED", "APPLYING", "APPLICATION_FAILED", "APPLIED",
    "RECRUITER_CONTACTED", "RECRUITER_REPLIED", "SCREENING", "ASSESSMENT", "INTERVIEW_SCHEDULED",
    "INTERVIEW_COMPLETED", "OFFER"])}
CLOSED = {"REJECTED", "WITHDRAWN", "CLOSED", "OFFER"}
TARGET = {"Application Confirmation": "APPLIED", "Recruiter Reply": "RECRUITER_REPLIED",
          "Assessment": "ASSESSMENT", "Coding Test": "ASSESSMENT", "Interview Invitation": "INTERVIEW_SCHEDULED",
          "Rejection": "REJECTED", "Offer": "OFFER"}


def email_out(e: dict) -> dict:
    return {"id": e["_id"], "gmail_id": e.get("gmail_id"), "sender": e["sender"], "subject": e["subject"],
            "snippet": e.get("snippet") or e["body"][:200], "received_at": e["received_at"].isoformat(),
            "category": e["category"], "confidence": e["confidence"], "extracted": e.get("extracted", {}),
            "application_id": e.get("application_id"), "action": e.get("action"), "source": e.get("source")}


async def match_application(db: AsyncIOMotorDatabase, user_id: str, subject: str, body: str,
                            extracted: dict) -> dict | None:
    text = f"{subject}\n{body}".lower()
    sender_bits = f"{extracted.get('sender_name') or ''} {extracted.get('sender_domain') or ''}".lower()
    best, best_score = None, 0
    async for a in db[c.APPLICATIONS].find({"user_id": user_id}).sort("updated_at", -1).limit(300):
        name = a["company"].lower()
        key = company_key(a["company"])
        score = 0
        if re.search(rf"(?<![a-z0-9]){re.escape(name)}(?![a-z0-9])", text):
            score += 3
        if key and len(key) >= 3 and key in re.sub(r"[^a-z0-9]", "", sender_bits):
            score += 3
        if a["role"].lower() in text:
            score += 2
        if a["status"] in CLOSED and a["status"] != "OFFER":
            score -= 1
        if score > best_score:
            best, best_score = a, score
    return best if best_score >= 3 else None


async def ingest(db: AsyncIOMotorDatabase, user_id: str, msg: dict, *, source: str) -> dict:
    if msg.get("gmail_id"):
        existing = await db[c.EMAILS].find_one({"user_id": user_id, "gmail_id": msg["gmail_id"]})
        if existing:
            return existing
    profile = await get_profile(db, user_id)
    tz = profile.preferences.timezone or "Asia/Kolkata"
    from app.email import portal

    portal_cat = portal.category(msg["sender"], msg["subject"], msg["body"])
    category, confidence, signals = classifier.classify(msg["subject"], msg["body"])
    extracted = classifier.extract(msg["subject"], msg["body"], msg["sender"], tz)
    received = (datetime.fromtimestamp(msg["received_ms"] / 1000, tz=UTC) if msg.get("received_ms")
                else utcnow())
    if portal_cat:  # LinkedIn / Naukri / Indeed mail: never used to move an application's status
        category, confidence, signals, app = portal_cat, 0.9, ["portal sender"], None
        extracted["portal"] = portal.portal_for(msg["sender"])
    else:
        app = await match_application(db, user_id, msg["subject"], msg["body"], extracted)
    if category == "Recruiter Outreach" and app:
        category = "Recruiter Reply"  # a recruiter writing about a job you're already pursuing
    doc = {"_id": new_id(), "user_id": user_id, "gmail_id": msg.get("gmail_id"), "thread_id": msg.get("thread_id"),
           "sender": msg["sender"], "subject": msg["subject"], "body": msg["body"][:20000],
           "snippet": msg.get("snippet"), "received_at": received, "category": category,
           "confidence": round(confidence, 2), "signals": signals, "extracted": extracted,
           "application_id": app["_id"] if app else None, "action": None, "source": source, "created_at": utcnow()}
    await db[c.EMAILS].insert_one(doc)
    await db[c.EMAIL_CLASSIFICATIONS].insert_one({"_id": new_id(), "user_id": user_id, "email_id": doc["_id"],
                                                  "category": category, "confidence": doc["confidence"],
                                                  "signals": signals, "created_at": utcnow()})
    action = await apply_to_application(db, user_id, doc, app) if app else None
    from app.recruiters.service import on_inbound_email  # local import avoids a cycle

    outreach = await on_inbound_email(db, user_id, extracted.get("sender_email"), msg["body"])
    if outreach and not action:
        action = f"outreach_{outreach}"
    if not app and category in {"Recruiter Outreach", "Interview Invitation", "Offer", "Portal Invite", "Portal Message"}:
        await notify(db, user_id=user_id, kind="recruiter_email", title=f"{category}: {msg['subject'][:80]}", link="/inbox")
    if portal_cat in ("Portal Invite", "Portal Message"):
        await portal_recruiter(db, user_id, msg)
    if category in ("Recruiter Outreach", "Recruiter Reply", "Interview Invitation", "Assessment") and not portal_cat:
        from app.email.auto_reply import draft_reply

        await draft_reply(db, user_id, doc)
    if action:
        await db[c.EMAILS].update_one({"_id": doc["_id"]}, {"$set": {"action": action}})
        doc["action"] = action
    await log_action(db, user_id=user_id, action="email.received", entity="email", entity_id=doc["_id"],
                     details={"category": category, "application_id": doc["application_id"], "action": action})
    return doc


async def portal_recruiter(db: AsyncIOMotorDatabase, user_id: str, msg: dict) -> None:
    """Add the recruiter a LinkedIn / Naukri invite or message names (with any phone or email it contains)."""
    from app.email import portal
    from app.recruiters.service import create_contact
    from app.schemas.recruiter import ContactIn

    r = portal.recruiter(msg["sender"], msg["subject"], msg["body"])
    if not r:
        return
    try:
        await create_contact(db, user_id, ContactIn(
            name=r["name"], company=r["company"], email=r["email"], phone=r["phone"], title=r["title"], role="recruiter",
            source="portal", tags=[r["portal"]], notes=f"From your {r['portal'].title()} notification: {msg['subject'][:150]}"))
    except ValueError:
        pass


async def apply_to_application(db: AsyncIOMotorDatabase, user_id: str, email: dict, app: dict) -> str | None:
    category, ex = email["category"], email["extracted"]
    note = f"From email: {email['subject'][:120]}"
    await db[c.APPLICATIONS].update_one({"_id": app["_id"]}, {"$set": {"last_contact_at": email["received_at"]}})

    if category == "Interview Reschedule":
        iv = await db[c.INTERVIEWS].find_one({"application_id": app["_id"], "status": {"$in": ["upcoming", "rescheduled"]}},
                                             sort=[("scheduled_at", -1)])
        if iv and ex.get("interview_at"):
            await db[c.INTERVIEWS].update_one({"_id": iv["_id"]}, {"$set": {
                "scheduled_at": datetime.fromisoformat(ex["interview_at"]), "status": "rescheduled",
                "meeting_url": ex.get("meeting_url") or iv.get("meeting_url"), "updated_at": utcnow()}})
            await notify(db, user_id=user_id, kind="interview_rescheduled", title=f"Interview rescheduled: {app['role']} at {app['company']}",
                         link="/interviews")
            return "interview_rescheduled"
        return None

    target = TARGET.get(category)
    if not target:
        await apps.add_event(db, app, kind="email", note=note, source="gmail", email_id=email["_id"])
        return None
    current = app["status"]
    terminal = target in {"REJECTED", "OFFER"}
    if current in CLOSED or (not terminal and STAGE_RANK.get(target, 0) <= STAGE_RANK.get(current, 0)):
        await apps.add_event(db, app, kind="email", note=note, source="gmail", email_id=email["_id"])
        return None

    if target == "APPLIED":
        await apps.mark_applied(db, app, source="gmail", email_id=email["_id"])
        return "status:APPLIED"
    if terminal:
        await db[c.FOLLOWUPS].update_many({"application_id": app["_id"], "status": "scheduled"}, {"$set": {"status": "cancelled"}})
    extra = {}
    if target == "INTERVIEW_SCHEDULED" and ex.get("interview_at"):
        iv = {"_id": new_id(), "user_id": user_id, "application_id": app["_id"], "company": app["company"],
              "role": app["role"], "round": ex.get("interview_round"),
              "scheduled_at": datetime.fromisoformat(ex["interview_at"]), "timezone": ex.get("timezone"),
              "duration_minutes": 60, "meeting_url": ex.get("meeting_url"), "interviewer": ex.get("sender_name"),
              "interview_type": "Video" if ex.get("meeting_url") else None, "status": "upcoming", "notes": note,
              "source": "gmail", "email_id": email["_id"], "created_at": utcnow(), "updated_at": utcnow()}
        await db[c.INTERVIEWS].insert_one(iv)
        extra["interview_id"] = iv["_id"]
    await apps.set_status(db, app, target, note=note, source="gmail", email_id=email["_id"], extra=extra)
    titles = {"REJECTED": "Rejection received", "OFFER": "Offer received", "INTERVIEW_SCHEDULED": "Interview scheduled",
              "ASSESSMENT": "Assessment received", "RECRUITER_REPLIED": "Recruiter replied"}
    await notify(db, user_id=user_id, kind=target.lower(), title=f"{titles[target]}: {app['role']} at {app['company']}",
                 body="Detected from Gmail", link=f"/applications/{app['_id']}")
    return f"status:{target}"
