"""Auto-applier: every day, prepare applications for the strongest matches in Jobs for you.

What it does automatically: pick jobs at or above the user's match threshold (in their country or
remote), save them, attach the best resume and prepare the application, then notify the user
(in-app and WhatsApp). What still needs one click: approving. After approval,
- a posting that asks for CVs by email gets the application email (cover note + resume attached)
  sent from the user's own Gmail,
- any other posting opens the employer's application page to submit there (Saige never submits
  forms on third-party sites or logs into them).
"""

import re

from fastapi import HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.automation.service import get_settings_doc, is_allowed
from app.database import collections as c
from app.jobs import discover, feed
from app.jobs import service as jobs
from app.profiles.service import get_profile
from app.services.audit import log_action
from app.services.notify import notify
from app.utils import start_of_today, utcnow


async def prepared_today(db: AsyncIOMotorDatabase, uid: str) -> int:
    return await db[c.APPLICATIONS].count_documents({"user_id": uid, "auto": True, "created_at": {"$gte": start_of_today()}})


def pick(items: list[dict], s, room: int) -> list[dict]:
    a = s.auto_apply
    out = []
    for it in items:
        if it.get("saved_job_id") or it["score"] < a.min_score or it["scope"] not in a.scopes:
            continue
        if it.get("walk_in") and not a.include_walk_in:
            continue
        from app.automation.service import is_blocked

        if is_blocked(s, it.get("company")):
            continue
        out.append(it)
        if len(out) >= room:
            break
    return out


async def run(db: AsyncIOMotorDatabase, uid: str, *, trigger: str = "manual") -> dict:
    from app.applications import service as apps

    s = await get_settings_doc(db, uid)
    if trigger == "schedule" and not s.auto_apply.enabled:
        return {"skipped": "auto-apply is off"}
    if not await is_allowed(db, uid, "applications"):
        return {"skipped": "applications are paused"}
    room = max(0, s.auto_apply.daily_max - await prepared_today(db, uid))
    if not room:
        return {"prepared": 0, "skipped": f"today's limit of {s.auto_apply.daily_max} is reached"}
    doc = await feed.get(db, uid)
    items = doc.get("items", [])
    await feed.mark_saved(db, uid, items)
    profile = await get_profile(db, uid)
    weights = await jobs.get_weights(db, uid)
    prepared: list[dict] = []
    for it in pick(items, s, room):
        try:
            job, _ = await jobs.ingest(db, uid, discover.to_job_in(it), profile=profile, weights=weights)
            a = await apps.create(db, uid, job["_id"], None, None)
        except (ValueError, HTTPException):
            continue
        extra = {"auto": True, "walk_in": it.get("walk_in")}
        if it.get("apply_by_email") and it.get("hr_emails"):
            extra["apply_email"] = it["hr_emails"][0]
        await db[c.APPLICATIONS].update_one({"_id": a["_id"]}, {"$set": extra})
        prepared.append({**it, "application_id": a["_id"]})
    if prepared:
        await notify(db, user_id=uid, kind="auto_apply",
                     title=f"Auto-applier prepared {len(prepared)} application(s)",
                     body="Resumes are attached and answers drafted. Approve them in Applications.",
                     link="/applications?tab=auto",
                     details=[{"platform": p["company"], "field": p["title"], "after": f"{p['score']}% match"} for p in prepared])
    await log_action(db, user_id=uid, action="auto_apply.run", entity="application",
                     details={"trigger": trigger, "prepared": len(prepared)})
    return {"prepared": len(prepared), "application_ids": [p["application_id"] for p in prepared],
            "threshold": s.auto_apply.min_score}


# ------------------------------------------------------------------ approval + email applications

def application_email(profile, a: dict, job: dict) -> tuple[str, str]:
    """Short, truthful application email built only from the verified profile."""
    from app.jobs.matching import candidate_skills
    from app.services.skills_vocab import normalize_key

    p = profile.personal
    have = candidate_skills(profile)
    skills = [s for s in (job.get("analysis") or {}).get("required_skills", []) if normalize_key(s) in have][:4]
    yrs = f" with {int(p.total_experience_years)}+ years of experience" if p.total_experience_years else ""
    lines = ["Dear Hiring Team,", "",
             f"I'd like to apply for the {a['role']} role at {a['company']}."
             + (f" I'm currently a {p.current_designation}{yrs}." if p.current_designation else "")]
    if skills:
        lines.append(f"My experience includes {', '.join(skills)}, which the role calls for.")
    lines += ["My resume is attached. I'd welcome the chance to talk.", "", "Thank you,", p.name or ""]
    if p.phone:
        lines.append(p.phone)
    subject = f"Application: {a['role']} – {p.name or 'candidate'}"
    return subject[:200], "\n".join(lines).strip()


async def send_application_email(db: AsyncIOMotorDatabase, uid: str, a: dict) -> dict:
    from app.email import smtp
    from app.email.gmail import GmailError
    from app.resumes.docx_export import resume_docx
    from app.schemas.resume import ParsedResume
    from app.services import crypto
    from app.services.truth_guard import GeneratedClaims, validate_claims

    integ = await db[c.INTEGRATIONS].find_one({"user_id": uid, "provider": "gmail", "method": "app_password"})
    if not integ:
        raise HTTPException(409, "Connect Gmail with an App Password to send email applications.")
    profile = await get_profile(db, uid)
    job = await db[c.JOBS].find_one({"_id": a["job_id"]}) or {}
    subject, body = application_email(profile, a, job)
    check = validate_claims(GeneratedClaims(text=body), profile)
    if not check.passed:
        raise HTTPException(409, "The application email didn't pass the truth check. Review the job and send it yourself.")
    attachments = []
    if a.get("resume_id"):
        r = await db[c.RESUMES].find_one({"_id": a["resume_id"]})
        v = r and await db[c.RESUME_VERSIONS].find_one({"_id": r.get("current_version_id")})
        if v:
            name = re.sub(r"[^A-Za-z0-9 _-]", "", profile.personal.name or "Resume").strip() or "Resume"
            attachments.append((f"{name} - Resume.docx", resume_docx(ParsedResume.model_validate(v["parsed"])),
                                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))
    try:
        mid = await smtp.send(integ["email"], crypto.decrypt(integ["app_password_enc"]), profile.personal.name or "",
                              a["apply_email"], subject, body, attachments)
    except GmailError as exc:
        raise HTTPException(502, str(exc)) from exc
    await db[c.APPLICATIONS].update_one({"_id": a["_id"]}, {"$set": {"applied_via": "email", "apply_message_id": mid,
                                                                     "updated_at": utcnow()}})
    return {"to": a["apply_email"], "subject": subject, "attached_resume": bool(attachments)}


async def approve_many(db: AsyncIOMotorDatabase, uid: str, ids: list[str]) -> dict:
    from app.applications import service as apps

    s = await get_settings_doc(db, uid)
    results = []
    for app_id in ids:
        a = await db[c.APPLICATIONS].find_one({"_id": app_id, "user_id": uid})
        if not a:
            results.append({"id": app_id, "status": "error", "message": "Not found"})
            continue
        row = {"id": app_id, "company": a["company"], "role": a["role"]}
        try:
            if a.get("apply_email") and s.auto_apply.email_apply:
                sent = await send_application_email(db, uid, a)
                await apps.mark_applied(db, a, source="email")
                results.append({**row, "status": "sent", "message": f"Emailed {sent['to']}"})
                continue
            out = await apps.approve_and_apply(db, uid, a)
            results.append({**row, "status": "open", "url": out["handoff_url"], "message": "Open the employer's page to submit"})
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, str) else (exc.detail or {}).get("message", "Failed")
            results.append({**row, "status": "error", "message": detail})
    sent = sum(r["status"] == "sent" for r in results)
    opened = sum(r["status"] == "open" for r in results)
    if sent or opened:
        await notify(db, user_id=uid, kind="applications_approved",
                     title=f"{sent + opened} application(s) approved",
                     body=f"{sent} sent by email from your Gmail. {opened} ready to submit on the employer's site.",
                     link="/applications",
                     details=[{"platform": r["company"], "field": r["role"], "after": r["message"]} for r in results if r["status"] != "error"])
    return {"results": results, "sent": sent, "open": opened, "errors": sum(r["status"] == "error" for r in results)}
