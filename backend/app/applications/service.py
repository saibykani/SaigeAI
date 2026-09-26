"""Application engine (spec sections 18-20, 26, 42, 44)."""

from datetime import timedelta

from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import DESCENDING

from app.applications.answers import answer_question
from app.automation.service import get_settings_doc
from app.database import collections as c
from app.profiles.service import get_profile
from app.services.audit import log_action
from app.services.notify import notify
from app.utils import new_id, start_of_today, utcnow

# No job board or ATS offers a permitted, candidate-side "submit application" API today, so the
# final submit is always a human hand-off (spec 19: HUMAN APPROVAL REQUIRED).
PERMITTED_SUBMIT_INTEGRATIONS: set[str] = set()
FOLLOWUP_DAYS = (3, 7)
CLOSE_AFTER_DAYS = 14
ACTIVE = {"SHORTLISTED", "READY_TO_APPLY", "APPROVAL_REQUIRED", "APPLYING", "APPLIED", "RECRUITER_CONTACTED",
          "RECRUITER_REPLIED", "SCREENING", "ASSESSMENT", "INTERVIEW_SCHEDULED", "INTERVIEW_COMPLETED"}


def _iso(dt) -> str | None:
    return dt.isoformat() if dt else None


def app_out(a: dict) -> dict:
    return {
        "id": a["_id"], "job_id": a.get("job_id"), "company": a["company"], "role": a["role"],
        "source": a.get("source"), "application_url": a.get("application_url"), "match_score": a.get("match_score"),
        "resume_id": a.get("resume_id"), "cover_letter_id": a.get("cover_letter_id"), "status": a["status"],
        "applied_at": _iso(a.get("applied_at")), "last_contact_at": _iso(a.get("last_contact_at")),
        "next_followup_at": _iso(a.get("next_followup_at")), "recruiter_id": a.get("recruiter_id"),
        "interview_id": a.get("interview_id"), "created_at": _iso(a["created_at"]), "updated_at": _iso(a["updated_at"]),
        "auto": bool(a.get("auto")), "apply_email": a.get("apply_email"), "applied_via": a.get("applied_via"),
        "walk_in": a.get("walk_in"),
    }


async def get_owned(db: AsyncIOMotorDatabase, user_id: str, app_id: str) -> dict:
    a = await db[c.APPLICATIONS].find_one({"_id": app_id, "user_id": user_id})
    if not a:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    return a


async def add_event(db: AsyncIOMotorDatabase, a: dict, *, kind: str, note: str | None = None,
                    from_status: str | None = None, to_status: str | None = None, source: str = "user",
                    email_id: str | None = None) -> None:
    await db[c.APPLICATION_EVENTS].insert_one({
        "_id": new_id(), "user_id": a["user_id"], "application_id": a["_id"], "type": kind, "note": note,
        "from": from_status, "to": to_status, "source": source, "email_id": email_id, "at": utcnow(),
    })


async def set_status(db: AsyncIOMotorDatabase, a: dict, new_status: str, *, note: str | None = None,
                     source: str = "user", email_id: str | None = None, extra: dict | None = None) -> dict:
    old = a["status"]
    update = {"status": new_status, "updated_at": utcnow(), **(extra or {})}
    await db[c.APPLICATIONS].update_one({"_id": a["_id"]}, {"$set": update})
    await add_event(db, a, kind="status_change", note=note, from_status=old, to_status=new_status, source=source,
                    email_id=email_id)
    await log_action(db, user_id=a["user_id"], action="application.status_changed", entity="application",
                     entity_id=a["_id"], details={"from": old, "to": new_status, "source": source, "email_id": email_id})
    return await db[c.APPLICATIONS].find_one({"_id": a["_id"]})


async def create(db: AsyncIOMotorDatabase, user_id: str, job_id: str, resume_id: str | None,
                 cover_letter_id: str | None) -> dict:
    job = await db[c.JOBS].find_one({"_id": job_id, "user_id": user_id})
    if not job:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    existing = await db[c.APPLICATIONS].find_one({"user_id": user_id, "job_id": job_id})
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, {"message": "Application already exists", "id": existing["_id"]})
    if not resume_id:
        tailored = await db[c.RESUMES].find_one({"user_id": user_id, "job_id": job_id, "status": "active"},
                                                sort=[("created_at", DESCENDING)])
        from app.profiles.sync_service import master_resume
        chosen = tailored or await master_resume(db, user_id)
        resume_id = chosen["_id"] if chosen else None
    if not cover_letter_id:
        letter = await db[c.COVER_LETTERS].find_one({"user_id": user_id, "job_id": job_id},
                                                    sort=[("created_at", DESCENDING)])
        cover_letter_id = letter["_id"] if letter else None
    now = utcnow()
    a = {
        "_id": new_id(), "user_id": user_id, "job_id": job_id, "candidate_id": user_id,
        "company": job["company"], "role": job["title"], "source": job.get("source"),
        "application_url": job.get("application_url"), "match_score": (job.get("match") or {}).get("overall"),
        "resume_id": resume_id, "cover_letter_id": cover_letter_id,
        "status": "READY_TO_APPLY" if resume_id else "SHORTLISTED",
        "applied_at": None, "last_contact_at": None, "next_followup_at": None, "recruiter_id": None,
        "interview_id": None, "created_at": now, "updated_at": now,
    }
    await db[c.APPLICATIONS].insert_one(a)
    await db[c.JOBS].update_one({"_id": job_id}, {"$set": {"status": "shortlisted", "updated_at": now}})
    await add_event(db, a, kind="created", to_status=a["status"], note="Application prepared")
    await log_action(db, user_id=user_id, action="application.prepared", entity="application", entity_id=a["_id"],
                     details={"job_id": job_id, "resume_id": resume_id, "cover_letter_id": cover_letter_id})
    if a["status"] == "READY_TO_APPLY":
        await notify(db, user_id=user_id, kind="application_ready", title=f"Application ready: {a['role']} at {a['company']}",
                     link=f"/applications/{a['_id']}")
    return a


async def answer_questions(db: AsyncIOMotorDatabase, a: dict, questions: list[str]) -> list[dict]:
    profile = await get_profile(db, a["user_id"])
    out = []
    for q in questions:
        q = q.strip()
        if not q:
            continue
        ans = answer_question(q, profile)
        doc = {"_id": new_id(), "user_id": a["user_id"], "application_id": a["_id"], **ans,
               "created_at": utcnow(), "updated_at": utcnow()}
        await db[c.APPLICATION_ANSWERS].insert_one(doc)
        out.append(doc)
    if any(x["status"] == "REVIEW_REQUIRED" for x in out) and a["status"] == "READY_TO_APPLY":
        await set_status(db, a, "APPROVAL_REQUIRED", note="Some answers need your review", source="system")
    return out


def answer_out(d: dict) -> dict:
    return {"id": d["_id"], "question": d["question"], "answer": d.get("answer"), "source": d.get("source"),
            "confidence": d.get("confidence"), "status": d["status"], "sensitive": d.get("sensitive", False),
            "note": d.get("note")}


async def approve_and_apply(db: AsyncIOMotorDatabase, user_id: str, a: dict) -> dict:
    """Semi-automatic mode's APPROVE & APPLY. Submission happens on the employer's site unless a
    permitted integration exists; none does today, so this is always a human hand-off."""
    pending = await db[c.APPLICATION_ANSWERS].count_documents(
        {"application_id": a["_id"], "status": "REVIEW_REQUIRED"})
    if pending:
        raise HTTPException(status.HTTP_409_CONFLICT, f"{pending} answer(s) still need your review before applying.")
    settings = await get_settings_doc(db, user_id)
    if settings.paused_all or settings.pauses.applications:
        raise HTTPException(status.HTTP_423_LOCKED, "Applications are paused. Resume them in Automation settings.")
    today = await db[c.APPLICATIONS].count_documents(
        {"user_id": user_id, "applied_at": {"$gte": start_of_today()}})
    if today >= settings.limits.daily_application_limit:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            f"Daily application limit ({settings.limits.daily_application_limit}) reached.")
    if not a.get("application_url"):
        raise HTTPException(status.HTTP_409_CONFLICT, "This job has no application link. Add one on the job, or apply directly.")
    channel = (a.get("source") or "manual").lower()
    a = await set_status(db, a, "APPLYING", note="Approved by user; opened employer application page")
    return {
        "application": app_out(a),
        "submission": "HUMAN_APPROVAL_REQUIRED" if channel not in PERMITTED_SUBMIT_INTEGRATIONS else "AUTOMATIC",
        "handoff_url": a["application_url"],
        "message": "HUMAN APPROVAL REQUIRED: submit the application on the employer's site (it may ask for a login, "
                   "CAPTCHA or answers Saige can't verify), then click 'I've submitted'.",
    }


async def mark_applied(db: AsyncIOMotorDatabase, a: dict, *, source: str = "user", email_id: str | None = None) -> dict:
    now = utcnow()
    first = now + timedelta(days=FOLLOWUP_DAYS[0])
    a = await set_status(db, a, "APPLIED", note="Application submitted", source=source, email_id=email_id,
                         extra={"applied_at": a.get("applied_at") or now, "next_followup_at": first})
    await db[c.FOLLOWUPS].delete_many({"application_id": a["_id"], "status": {"$in": ["scheduled", "due"]}})
    for i, days in enumerate(FOLLOWUP_DAYS, start=1):
        await db[c.FOLLOWUPS].insert_one({
            "_id": new_id(), "user_id": a["user_id"], "application_id": a["_id"], "kind": "followup", "sequence": i,
            "due_at": now + timedelta(days=days), "status": "scheduled", "created_at": now})
    await db[c.FOLLOWUPS].insert_one({
        "_id": new_id(), "user_id": a["user_id"], "application_id": a["_id"], "kind": "close", "sequence": 3,
        "due_at": now + timedelta(days=CLOSE_AFTER_DAYS), "status": "scheduled", "created_at": now})
    await notify(db, user_id=a["user_id"], kind="application_submitted",
                 title=f"Applied: {a['role']} at {a['company']}", body="Follow-ups scheduled for day 3 and day 7.",
                 link=f"/applications/{a['_id']}")
    return a
