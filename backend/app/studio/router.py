"""/api/studio: JD analyzer and job-specific ATS resumes with templates and multi-format downloads."""

import re
from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field
from pymongo import DESCENDING

from app.auth.deps import db_dep, get_current_user
from app.database import collections as c
from app.jobs.jd_parser import analyze_jd
from app.profiles.service import get_profile
from app.resumes import service as resumes
from app.resumes import tailor
from app.resumes.ai_router import _base_parsed, _matched
from app.schemas.resume import ParsedResume
from app.services.audit import log_action
from app.studio import analyzer, polish, render
from app.utils import new_id, utcnow

router = APIRouter(prefix="/studio", tags=["studio"])
KIND = "ATS Resume"


class JDIn(BaseModel):
    jd_text: str | None = Field(default=None, max_length=60000)
    title: str = Field(default="", max_length=200)
    company: str = Field(default="", max_length=120)
    career_job_id: str | None = Field(default=None, max_length=200)
    job_id: str | None = Field(default=None, max_length=64)


class ResumeIn(JDIn):
    template: str = Field(default="modern", max_length=30)
    base_resume_id: str | None = None


async def _jd_source(db: AsyncIOMotorDatabase, uid: str, body: JDIn) -> tuple[str, str, str]:
    """(jd_text, title, company) from pasted text, a Career portals job or a saved job."""
    if body.career_job_id:
        from app.careers import service as careers

        d = await careers.get_owned(db, uid, body.career_job_id)
        if not d.get("has_description"):
            await careers.enrich(db, uid, [d])
            d = await careers.get_owned(db, uid, body.career_job_id)
        text = d.get("description") or ""
        if len(text) < 30:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "This career page doesn't share its job description. Paste it instead.")
        return text, body.title or d["title"], body.company or d["company"]
    if body.job_id:
        from app.jobs import service as jobs

        j = await jobs.get_owned(db, uid, body.job_id)
        return j.get("description") or "", body.title or j["title"], body.company or j["company"]
    text = (body.jd_text or "").strip()
    if len(text) < 30:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Paste the job description (at least a few lines).")
    return text, body.title.strip(), body.company.strip() or (analyzer.extract_company(text) or "")


def _headline(profile) -> str | None:
    """Current role and experience counted from the role dates, e.g. "Senior QA Engineer · 3 yrs 5 mo experience"."""
    from app.profiles.experience import describe

    p, roles = profile.personal, profile.knowledge.experience
    role = p.current_designation or next((e.title for e in roles if e.is_current), None) or (roles[0].title if roles else None)
    yrs = describe(p.total_experience_years) if p.total_experience_years else None
    return " · ".join(x for x in (role, f"{yrs} experience" if yrs else None) if x) or None


async def _learn(db: AsyncIOMotorDatabase, uid: str, career_job_id: str | None, kind: str) -> None:
    """Analysing or building a resume for a Career portals job tells Saige learning you want jobs like it."""
    if not career_job_id:
        return
    from app.careers import service as careers

    try:
        await careers._learn(db, uid, await careers.get_owned(db, uid, career_job_id), kind)
    except HTTPException:
        return


@router.get("/templates")
async def templates():
    return {"templates": [{"id": t.id, "name": t.name, "description": t.description} for t in render.TEMPLATES.values()],
            "formats": [{"id": "pdf", "name": "PDF"}, {"id": "docx", "name": "Word (DOCX)"}, {"id": "txt", "name": "Plain text (ATS)"},
                        {"id": "md", "name": "Markdown"}, {"id": "html", "name": "HTML"}]}


@router.post("/analyze")
async def analyze(body: JDIn, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    """Read a JD and explain it: requirements, what you have and don't, eligibility, where you fit most."""
    uid = user["_id"]
    text, title, company = await _jd_source(db, uid, body)
    out = analyzer.analyze(await get_profile(db, uid), text, title, company)
    await _learn(db, uid, body.career_job_id, "analyzed")
    out["company_detected"] = bool(company) and not body.company.strip() and not body.career_job_id
    await log_action(db, user_id=uid, action="studio.jd_analyzed", entity="jd",
                     details={"title": out["title"], "company": company, "score": out["score"], "verdict": out["verdict"]["key"]})
    return out


def _improve(report: dict, analysis: dict) -> list[str]:
    tips = []
    if report["missing_required"]:
        tips.append(f"The JD requires {', '.join(report['missing_required'][:6])}. They aren't in your verified profile, so they are not on "
                    "this resume. If you have really used them, add them in Profile and generate again: the score goes up.")
    if report["missing_preferred"]:
        tips.append(f"Nice-to-have skills not on the resume: {', '.join(report['missing_preferred'][:5])}.")
    fixes = {"Email present": "Add your email in Profile.", "Phone present": "Add your phone number in Profile.",
             "Professional summary": "Add a professional summary in Profile.", "Skills section": "Add at least 5 skills in Profile.",
             "Dated work experience": "Give every role a start date in Profile.",
             "Achievement bullets": "Add bullet points to your roles in Profile.",
             "Education listed": "Add your education in Profile.",
             "Length 250-1200 words": "Add more detail to your roles and projects (250+ words)."}
    tips += [fixes.get(ch["check"], ch["check"]) for ch in report["checks"] if not ch["passed"]]
    return tips


@router.post("/resume", status_code=201)
async def generate(body: ResumeIn, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    """A resume aimed at this JD, built only from your verified profile, scored against the JD."""
    return await _build(db, user["_id"], body, *(await _jd_source(db, user["_id"], body)))


async def _build(db: AsyncIOMotorDatabase, uid: str, body: ResumeIn, text: str, title: str, company: str) -> dict:
    title = title or analyzer._guess_title(text)
    jd = analyze_jd(title, text)
    profile = await get_profile(db, uid)
    base, base_parsed = await _base_parsed(db, uid, body.base_resume_id)
    matched = _matched(profile, jd)
    fallback = tailor.template_summary(profile, title, matched)
    summary, engine = (await tailor.llm_polish("summary", profile, title, company or "the company", matched, fallback)
                       ) if fallback else (None, "deterministic")
    title = title or "Target role"
    try:
        parsed, changes = tailor.tailor_resume(profile, jd, {"_id": None, "title": title, "company": company}, base_parsed, summary)
    except tailor.TailorError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    validation = tailor.validate_resume(parsed, profile)
    own = tailor.resume_text(base_parsed).lower() if base_parsed else ""
    bad = [v for v in validation["violations"] if str(v.get("value", "")).lower() not in own]
    if bad:
        await log_action(db, user_id=uid, action="studio.resume_blocked", entity="resume", details={"violations": bad})
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, {"status": "VALIDATION FAILED", "violations": bad})
    # Repair import artefacts (split skills, broken bullets, repeated sentences) in the user's own content, then score it.
    parsed = polish.polish(parsed)
    await _learn(db, uid, body.career_job_id, "resume")
    report = tailor.ats_report(parsed, jd)
    analysis = analyzer.analyze(profile, text, title, company)
    template = body.template if body.template in render.TEMPLATES else "modern"
    headline = _headline(profile)
    now = utcnow()
    doc = {"_id": new_id(), "user_id": uid, "name": f"{title} · {company}"[:120] if company else title[:120], "kind": KIND,
           "status": "active", "file_id": None, "filename": None, "content_type": None, "size": None, "job_id": body.job_id,
           "career_job_id": body.career_job_id, "company": company or None, "target_title": title, "template": template,
           "jd_text": text[:20000], "headline": headline,
           "base_resume_id": base["_id"] if base else None, "current_version_id": None, "version_count": 0,
           "created_at": now, "updated_at": now, "ats": report, "engine": engine}
    await db[c.RESUMES].insert_one(doc)
    await resumes.add_version(db, doc, parsed=parsed, raw_text=tailor.resume_text(parsed), source="studio",
                              changes=changes or ["Generated for this job"], base_resume_id=doc["base_resume_id"], job_id=body.job_id)
    await log_action(db, user_id=uid, action="studio.resume_generated", entity="resume", entity_id=doc["_id"],
                     details={"title": title, "company": company, "ats_score": report["score"], "template": template})
    return {"id": doc["_id"], "name": doc["name"], "company": company, "title": title, "template": template, "engine": engine,
            "resume": parsed.model_dump(), "ats": report, "changes": changes, "improve": _improve(report, analysis),
            "verdict": analysis["verdict"], "headline": headline, "experience_years": profile.personal.total_experience_years,
            "company_detected": bool(company) and not body.company.strip() and not body.career_job_id,
            "html": render.to_html(parsed, render.TEMPLATES[template], headline)}


def _out(d: dict) -> dict:
    return {"id": d["_id"], "name": d["name"], "company": d.get("company"), "title": d.get("target_title"), "template": d.get("template"),
            "ats_score": (d.get("ats") or {}).get("score"), "created_at": d["created_at"].isoformat()}


@router.get("/resumes")
async def list_resumes(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    rows = await db[c.RESUMES].find({"user_id": user["_id"], "kind": KIND, "status": {"$ne": "deleted"}}).sort(
        "created_at", DESCENDING).to_list(100)
    return [_out(d) for d in rows]


async def _parsed(db: AsyncIOMotorDatabase, uid: str, resume_id: str) -> tuple[dict, ParsedResume]:
    d = await resumes.get_owned(db, uid, resume_id)
    cur = await resumes.current_version(db, d)
    if not cur:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resume version not found")
    return d, ParsedResume.model_validate(cur["parsed"])


@router.get("/resumes/{resume_id}")
async def get_resume(resume_id: str, template: str | None = None, user: dict = Depends(get_current_user),
                     db: AsyncIOMotorDatabase = Depends(db_dep)):
    d, parsed = await _parsed(db, user["_id"], resume_id)
    t = render.TEMPLATES.get(template or d.get("template") or "modern", render.TEMPLATES["modern"])
    return {**_out(d), "ats": d.get("ats"), "resume": parsed.model_dump(), "headline": d.get("headline"),
            "html": render.to_html(parsed, t, d.get("headline"))}


@router.get("/resumes/{resume_id}/previews")
async def previews(resume_id: str, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    """The same resume rendered in every template, for the template gallery."""
    d, parsed = await _parsed(db, user["_id"], resume_id)
    return {"templates": [{"id": t.id, "name": t.name, "description": t.description, "html": render.to_html(parsed, t, d.get("headline"))}
                          for t in render.TEMPLATES.values()]}


@router.post("/resumes/{resume_id}/template")
async def set_template(resume_id: str, body: dict, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    """Remember the template picked in the gallery (used by default for downloads)."""
    tid = str(body.get("template") or "")
    if tid not in render.TEMPLATES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown template")
    await resumes.get_owned(db, user["_id"], resume_id)
    await db[c.RESUMES].update_one({"_id": resume_id, "user_id": user["_id"]}, {"$set": {"template": tid, "updated_at": utcnow()}})
    return {"template": tid}


@router.get("/resumes/{resume_id}/download")
async def download(resume_id: str, format: str = Query("pdf", pattern="^(pdf|docx|txt|md|html)$"),
                   template: str | None = Query(None, max_length=30), on: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
                   user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    """The file is named First_Last_YYYY-MM-DD_Company.<ext> (`on` is the date in your timezone)."""
    d, parsed = await _parsed(db, user["_id"], resume_id)
    tid = template if template in render.TEMPLATES else d.get("template") or "modern"
    data = render.render(parsed, tid, format, d.get("headline"))
    profile = await get_profile(db, user["_id"])
    name = profile.personal.name or parsed.name
    fname = render.filename(name, d.get("company"), on or date.today().isoformat(), format)
    await log_action(db, user_id=user["_id"], action="studio.resume_downloaded", entity="resume", entity_id=resume_id,
                     details={"format": format, "template": tid})
    return Response(content=data, media_type=render.FORMATS[format],
                    headers={"Content-Disposition": f"attachment; filename=\"{re.sub(r'[^A-Za-z0-9_.-]', '_', fname)}\"; "
                                                    f"filename*=UTF-8''{quote(fname)}", "X-Content-Type-Options": "nosniff"})


# ------------------------------------------------------------------ apply by email (JD or LinkedIn hiring post)

SEND_CAP = 25  # application emails per day from ATS Studio


class ApplyDraftIn(ResumeIn):
    to: str | None = Field(default=None, max_length=200)
    answers: dict[str, str] = Field(default_factory=dict)


class ApplySendIn(BaseModel):
    resume_id: str = Field(max_length=64)
    to: str = Field(max_length=200, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    subject: str = Field(min_length=3, max_length=200)
    body: str = Field(min_length=20, max_length=8000)
    format: str = Field(default="pdf", pattern="^(pdf|docx)$")
    template: str | None = Field(default=None, max_length=30)
    on: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")


async def _gmail(db: AsyncIOMotorDatabase, uid: str) -> dict | None:
    return await db[c.INTEGRATIONS].find_one({"user_id": uid, "provider": "gmail", "method": "app_password"})


@router.post("/apply/draft")
async def apply_draft(body: ApplyDraftIn, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    """Paste a JD or LinkedIn hiring post: Saige asks for any missing facts, then builds the resume and drafts the email."""
    from app.profiles.service import update_profile
    from app.schemas.profile import ProfileUpdate
    from app.studio import apply

    uid = user["_id"]
    text, title, company = await _jd_source(db, uid, body)
    patch = apply.coerce(body.answers)
    if patch:  # facts the user typed in when asked are saved to the profile, so they're asked only once
        await update_profile(db, uid, ProfileUpdate.model_validate({"personal": patch}), source="user")
    profile = await get_profile(db, uid)
    found = apply.emails_in(text)
    gmail = await _gmail(db, uid)
    need = apply.questions(profile, text)
    if need:
        return {"status": "needs_details", "questions": need, "emails_found": found, "company": company,
                "gmail": gmail["email"] if gmail else None}
    out = await _build(db, uid, body, text, title, company)
    subject, mail = apply.draft(profile, out["title"], company, out["ats"].get("matched_keywords", []), text)
    await log_action(db, user_id=uid, action="studio.application_drafted", entity="resume", entity_id=out["id"],
                     details={"company": company, "to": body.to or (found[0] if found else None)})
    return {**out, "status": "ready", "to": body.to or (found[0] if found else ""), "emails_found": found,
            "subject": subject, "body": mail, "gmail": gmail["email"] if gmail else None}


@router.post("/apply/send")
async def apply_send(body: ApplySendIn, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    """Send the reviewed email from your Gmail with the resume attached. Runs only on your click."""
    from datetime import timedelta

    from app.automation.service import is_allowed
    from app.email import smtp
    from app.email.gmail import GmailError
    from app.services import crypto
    from app.services.agent_runs import agent_run
    from app.services.notify import notify
    from app.services.truth_guard import GeneratedClaims, validate_claims

    uid = user["_id"]
    gmail = await _gmail(db, uid)
    if not gmail:
        raise HTTPException(status.HTTP_409_CONFLICT, "Connect Gmail with an App Password in Settings → Integrations to send from Saige.")
    if not await is_allowed(db, uid, "emails"):
        raise HTTPException(status.HTTP_423_LOCKED, "Sending email is paused in Automation settings.")
    since = utcnow() - timedelta(days=1)
    if await db[c.AUDIT_LOGS].count_documents({"user_id": uid, "action": "studio.application_sent", "timestamp": {"$gte": since}}) >= SEND_CAP:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, f"Daily limit of {SEND_CAP} application emails reached. Try again tomorrow.")
    profile = await get_profile(db, uid)
    check = validate_claims(GeneratedClaims(text=body.body), profile)
    if not check.passed:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, {"status": "VALIDATION FAILED", "violations": [
            v.model_dump() if hasattr(v, "model_dump") else v for v in check.violations]})
    d, parsed = await _parsed(db, uid, body.resume_id)
    tid = body.template if body.template in render.TEMPLATES else d.get("template") or "modern"
    data = render.render(parsed, tid, body.format, d.get("headline"))
    fname = render.filename(profile.personal.name or parsed.name, d.get("company"), body.on or date.today().isoformat(), body.format)
    async with agent_run(db, "apply_by_email", uid, {"resume_id": body.resume_id, "to": body.to}) as run:
        try:
            mid = await smtp.send(gmail["email"], crypto.decrypt(gmail["app_password_enc"]), profile.personal.name or "",
                                  body.to, body.subject, body.body, [(fname, data, render.FORMATS[body.format])])
        except GmailError as exc:
            run.errors.append(str(exc))
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
        run.actions.append(f"Emailed {body.to} with {fname}")
        run.output = {"message_id": mid}
    now = utcnow()
    await db[c.RESUMES].update_one({"_id": d["_id"]}, {"$push": {"sent": {"to": body.to, "subject": body.subject, "at": now,
                                                                         "message_id": mid, "file": fname}}})
    await log_action(db, user_id=uid, action="studio.application_sent", entity="resume", entity_id=d["_id"],
                     details={"to": body.to, "company": d.get("company"), "file": fname})
    await notify(db, user_id=uid, kind="application_emailed", title=f"Application sent to {body.to}",
                 body=f"{d.get('target_title') or 'Resume'}{' at ' + d['company'] if d.get('company') else ''}: {fname} attached.",
                 link="/studio/apply")
    return {"status": "sent", "to": body.to, "from": gmail["email"], "file": fname, "message_id": mid}
