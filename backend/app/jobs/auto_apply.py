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
from app.email import outbound
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
    from app.email.gmail import GmailError
    from app.resumes.docx_export import resume_docx
    from app.schemas.resume import ParsedResume
    from app.services.truth_guard import GeneratedClaims, validate_claims

    integ = await outbound.find_sender(db, uid)
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
        mid = await outbound.send(integ, profile.personal.name or "",
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


# ------------------------------------------------------------------ "Auto-apply to selected": really apply by email

def _norm(s: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


async def _already_applied(db: AsyncIOMotorDatabase, uid: str, company: str, role: str) -> bool:
    """Never email the same company + role twice."""
    key = (_norm(company), _norm(role))
    async for a in db[c.APPLICATIONS].find({"user_id": uid, "$or": [{"applied_at": {"$ne": None}}, {"applied_via": "email"}]},
                                           {"company": 1, "role": 1}):
        if (_norm(a.get("company")), _norm(a.get("role"))) == key:
            return True
    return False


async def apply_feed(db: AsyncIOMotorDatabase, uid: str, ids: list[str]) -> dict:
    """Run only after the user's explicit confirm. Jobs with a published HR/recruiter email get a tailored ATS resume and a
    truth-checked application email sent from the user's Gmail. Jobs without one are saved and returned with their real link."""
    from app.applications import service as apps
    from app.automation.service import is_blocked
    from app.services.agent_runs import agent_run
    from app.studio import apply as studio_apply
    from app.studio import router as studio
    from app.studio.router import ApplySendIn, ResumeIn

    integ = await outbound.find_sender(db, uid)
    if not integ:
        raise HTTPException(409, "Connect Gmail in Settings > Integrations so Saige can send applications from your account.")
    if not await is_allowed(db, uid, "applications"):
        raise HTTPException(423, "Applications are paused in Automation settings.")
    if not await is_allowed(db, uid, "emails"):
        raise HTTPException(423, "Sending email is paused in Automation settings.")
    s = await get_settings_doc(db, uid)
    sent_today = await db[c.APPLICATIONS].count_documents({"user_id": uid, "feed_apply": True, "applied_at": {"$gte": start_of_today()}})
    room = max(0, s.auto_apply.daily_max - sent_today)
    doc = await db[c.JOB_FEED].find_one({"_id": uid}) or {}
    by_id = {i["id"]: i for i in doc.get("items", [])}
    profile = await get_profile(db, uid)
    weights = await jobs.get_weights(db, uid)
    results: list[dict] = []
    async with agent_run(db, "feed_auto_apply", uid, {"selected": len(ids)}) as run:
        for fid in dict.fromkeys(ids):
            it = by_id.get(fid)
            if not it:
                results.append({"id": fid, "status": "skipped", "company": "", "role": "",
                                "message": "No longer in your feed. Refresh and try again."})
                continue
            row = {"id": fid, "company": it["company"], "role": it["title"]}
            link = it.get("application_url") or it.get("url")
            try:
                if not feed.valid_item(it):
                    results.append({**row, "status": "skipped", "message": "The posting has no valid link, so it was left out."})
                    continue
                if is_blocked(s, it["company"]):
                    results.append({**row, "status": "skipped", "message": "This company is on your blocked list."})
                    continue
                job, _ = await jobs.ingest(db, uid, discover.to_job_in(it), profile=profile, weights=weights)  # saved either way
                emails = it.get("hr_emails") or []
                if not emails:
                    results.append({**row, "status": "no_contact", "url": link, "message": "No contact email — apply on the career site"})
                    continue
                if await _already_applied(db, uid, it["company"], it["title"]):
                    results.append({**row, "status": "skipped", "to": emails[0], "url": link,
                                    "message": "Already applied to this company and role."})
                    continue
                if sum(r["status"] == "sent" for r in results) >= room:
                    results.append({**row, "status": "skipped", "to": emails[0], "url": link,
                                    "message": f"Today's limit of {s.auto_apply.daily_max} auto-applications is reached."})
                    continue
                text = it.get("description") or job.get("description") or ""
                out = await studio._build(db, uid, ResumeIn(jd_text=text, title=it["title"], company=it["company"], job_id=job["_id"]),
                                          text, it["title"], it["company"])
                subject, mail = studio_apply.draft(profile, out["title"], it["company"], out["ats"].get("matched_keywords", []), text)
                try:
                    a = await apps.create(db, uid, job["_id"], out["id"], None)
                except HTTPException:
                    a = await db[c.APPLICATIONS].find_one({"user_id": uid, "job_id": job["_id"]})
                    await db[c.APPLICATIONS].update_one({"_id": a["_id"]}, {"$set": {"resume_id": out["id"]}})
                to = emails[0]
                await studio.apply_send(ApplySendIn(resume_id=out["id"], to=to, subject=subject, body=mail, format="pdf",
                                                    template=out.get("template")), user={"_id": uid}, db=db)
                mid = ((await db[c.RESUMES].find_one({"_id": out["id"]}) or {}).get("sent") or [{}])[-1].get("message_id")
                await db[c.APPLICATIONS].update_one({"_id": a["_id"]}, {"$set": {
                    "applied_via": "email", "apply_email": to, "apply_message_id": mid, "feed_apply": True,
                    "email_record": {"to": to, "subject": subject, "message_id": mid, "resume_id": out["id"], "at": utcnow()}}})
                a = await db[c.APPLICATIONS].find_one({"_id": a["_id"]})
                await apps.mark_applied(db, a, source="email")
                run.actions.append(f"Emailed {to} for {it['title']} at {it['company']}")
                results.append({**row, "status": "sent", "to": to, "url": link, "message": f"Emailed {to} with your tailored resume attached"})
            except HTTPException as exc:
                d = exc.detail
                detail = d if isinstance(d, str) else (d or {}).get("message") or (d or {}).get("status") or "Failed"
                run.errors.append(f"{it['company']}: {detail}")
                results.append({**row, "status": "error", "url": link, "message": str(detail)})
            except ValueError as exc:
                results.append({**row, "status": "error", "url": link, "message": str(exc)})
        run.output = {"sent": sum(r["status"] == "sent" for r in results)}
    counts = {k: sum(r["status"] == k for r in results) for k in ("sent", "no_contact", "skipped", "error")}
    await log_action(db, user_id=uid, action="jobs.feed_apply", entity="application", details=counts)
    await notify(db, user_id=uid, kind="feed_auto_apply",
                 title=f"Auto-apply: {counts['sent']} emailed, {counts['no_contact']} to apply on career sites",
                 body=f"{counts['skipped']} skipped, {counts['error']} failed.", link="/applications",
                 details=[{"platform": r["company"], "field": r["role"], "after": r["message"]} for r in results])
    return {"results": results, **counts}
