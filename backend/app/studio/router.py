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
from app.studio import analyzer, render
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
    uid = user["_id"]
    text, title, company = await _jd_source(db, uid, body)
    title = title or analyzer._guess_title(text)
    jd = analyze_jd(title, text)
    profile = await get_profile(db, uid)
    base, base_parsed = await _base_parsed(db, uid, body.base_resume_id)
    matched = _matched(profile, jd)
    fallback = tailor.template_summary(profile, title, matched)
    summary, engine = (await tailor.llm_polish("summary", profile, title, company or "the company", matched, fallback)
                       ) if fallback else (None, "deterministic")
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
