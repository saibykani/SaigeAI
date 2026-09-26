"""Phase 3 endpoints: tailored resumes, ATS checks, cover letters, DOCX export."""

from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field
from pymongo import DESCENDING

from app.auth.deps import db_dep, get_current_user
from app.database import collections as c
from app.jobs import service as jobs
from app.jobs.matching import candidate_skills
from app.profiles.service import get_profile
from app.resumes import service as resumes
from app.resumes import tailor
from app.resumes.docx_export import letter_docx, resume_docx
from app.schemas.job import JDAnalysis
from app.schemas.resume import ParsedResume
from app.services.audit import log_action
from app.services.skills_vocab import canonical, normalize_key
from app.services.truth_guard import GeneratedClaims, validate_claims
from app.utils import new_id, utcnow

router = APIRouter(tags=["resume-ai"])


class TailorIn(BaseModel):
    base_resume_id: str | None = None


class AtsIn(BaseModel):
    resume_id: str
    version_id: str | None = None


class CoverLetterEdit(BaseModel):
    text: str = Field(min_length=20, max_length=8000)


def _docx_response(data: bytes, filename: str) -> Response:
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
                 "X-Content-Type-Options": "nosniff"},
    )


def _matched(profile, jd: JDAnalysis) -> list[str]:
    have = candidate_skills(profile)
    return [canonical(s) for s in dict.fromkeys(jd.required_skills + jd.preferred_skills)
            if normalize_key(canonical(s)) in have]


async def _base_parsed(db, user_id: str, base_resume_id: str | None) -> tuple[dict | None, ParsedResume | None]:
    base = None
    if base_resume_id:
        base = await resumes.get_owned(db, user_id, base_resume_id)
    else:
        from app.profiles.sync_service import master_resume
        base = await master_resume(db, user_id)
    if not base:
        return None, None
    cur = await resumes.current_version(db, base)
    return base, ParsedResume.model_validate(cur["parsed"]) if cur else None


@router.post("/jobs/{job_id}/tailor-resume", status_code=201)
async def tailor_resume(job_id: str, body: TailorIn, user: dict = Depends(get_current_user),
                        db: AsyncIOMotorDatabase = Depends(db_dep)):
    uid = user["_id"]
    job = await jobs.get_owned(db, uid, job_id)
    jd = JDAnalysis.model_validate(job["analysis"])
    profile = await get_profile(db, uid)
    base, base_parsed = await _base_parsed(db, uid, body.base_resume_id)
    matched = _matched(profile, jd)
    summary_fallback = tailor.template_summary(profile, job["title"], matched)
    summary, engine = (await tailor.llm_polish("summary", profile, job["title"], job["company"], matched,
                                               summary_fallback)) if summary_fallback else (None, "deterministic")
    try:
        parsed, changes = tailor.tailor_resume(profile, jd, job, base_parsed, summary)
    except tailor.TailorError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    validation = tailor.validate_resume(parsed, profile)
    if validation["status"] != "PASSED":
        await log_action(db, user_id=uid, action="resume.tailor_blocked", entity="job", entity_id=job_id,
                         details={"violations": validation["violations"]})
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            {"status": "VALIDATION FAILED", "violations": validation["violations"]})
    ats = tailor.ats_report(parsed, jd)
    now = utcnow()
    doc = {"_id": new_id(), "user_id": uid, "name": f"{job['title']} · {job['company']}"[:120],
           "kind": "Tailored Resume", "status": "active", "file_id": None, "filename": None,
           "content_type": None, "size": None, "job_id": job_id, "base_resume_id": base["_id"] if base else None,
           "current_version_id": None, "version_count": 0, "created_at": now, "updated_at": now,
           "ats": ats, "engine": engine}
    await db[c.RESUMES].insert_one(doc)
    await resumes.add_version(db, doc, parsed=parsed, raw_text=tailor.resume_text(parsed), source="tailored",
                              changes=changes or ["Generated for this job"], base_resume_id=doc["base_resume_id"],
                              job_id=job_id)
    await log_action(db, user_id=uid, action="resume.generated", entity="resume", entity_id=doc["_id"],
                     details={"job_id": job_id, "ats_score": ats["score"], "engine": engine})
    fresh = await resumes.get_owned(db, uid, doc["_id"])
    cur = await resumes.current_version(db, fresh)
    return {"resume": {**resumes.resume_out(fresh), "current_version": resumes.version_out(cur)},
            "ats": ats, "validation": validation, "engine": engine}


@router.post("/jobs/{job_id}/ats-check")
async def ats_check(job_id: str, body: AtsIn, user: dict = Depends(get_current_user),
                    db: AsyncIOMotorDatabase = Depends(db_dep)):
    uid = user["_id"]
    job = await jobs.get_owned(db, uid, job_id)
    resume = await resumes.get_owned(db, uid, body.resume_id)
    vid = body.version_id or resume.get("current_version_id")
    v = await db[c.RESUME_VERSIONS].find_one({"_id": vid, "resume_id": resume["_id"]})
    if not v:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resume version not found")
    return tailor.ats_report(ParsedResume.model_validate(v["parsed"]), JDAnalysis.model_validate(job["analysis"]))


class AtsScoreIn(BaseModel):
    resume_id: str
    version_id: str | None = None
    job_id: str | None = None
    jd_text: str | None = Field(default=None, max_length=60000)
    title: str | None = Field(default=None, max_length=200)


@router.post("/resumes/ats-score")
async def ats_score(body: AtsScoreIn, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    """ATS resume scorer: any resume against a saved job or a pasted job description, with fixes to make."""
    from app.jobs.jd_parser import analyze_jd

    uid = user["_id"]
    resume = await resumes.get_owned(db, uid, body.resume_id)
    v = await db[c.RESUME_VERSIONS].find_one({"_id": body.version_id or resume.get("current_version_id"), "resume_id": resume["_id"]})
    if not v:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resume version not found")
    if body.job_id:
        job = await jobs.get_owned(db, uid, body.job_id)
        jd, title = JDAnalysis.model_validate(job["analysis"]), f"{job['title']} at {job['company']}"
    elif body.jd_text and len(body.jd_text.strip()) >= 30:
        title = (body.title or "Pasted job description").strip()
        jd = analyze_jd(title, body.jd_text)
    else:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Choose a saved job or paste a job description (30+ characters).")
    report = tailor.ats_report(ParsedResume.model_validate(v["parsed"]), jd)
    tips = [f"Add “{s}” if you have used it — the job lists it as required." for s in report["missing_required"][:6]]
    fixes = {"Email present": "Add your email address at the top.", "Phone present": "Add your phone number at the top.",
             "Professional summary": "Add a 2–3 line professional summary.", "Skills section": "List at least 5 skills in a Skills section.",
             "Dated work experience": "Give every job a start date (and end date or Present).",
             "Achievement bullets": "Add bullet points under each job describing what you did.",
             "Education listed": "Add your education.", "Length 250-1200 words": "Aim for 250–1,200 words (about 1–2 pages)."}
    tips += [fixes.get(ch["check"], f"Fix: {ch['check']}.") for ch in report["checks"] if not ch["passed"]]
    if report["score"] < 80:
        tips.append("Use Jobs → a job → Tailor resume to create a version aimed at this job (only verified facts are used).")
    return {**report, "job": title, "resume": resume["name"], "tips": tips[:10]}


@router.get("/resumes/{resume_id}/health")
async def resume_health(resume_id: str, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    """Resume health report (no job needed): impact, repetition, bullet length, contact details, structure."""
    resume = await resumes.get_owned(db, user["_id"], resume_id)
    v = await db[c.RESUME_VERSIONS].find_one({"_id": resume.get("current_version_id"), "resume_id": resume["_id"]})
    if not v:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resume version not found")
    return {**tailor.health_report(ParsedResume.model_validate(v["parsed"])), "resume": resume["name"]}


# ------------------------------------------------------------------ cover letters

def _letter_out(d: dict) -> dict:
    return {"id": d["_id"], "job_id": d["job_id"], "resume_id": d.get("resume_id"), "text": d["text"],
            "validation": d.get("validation"), "engine": d.get("engine"),
            "created_at": d["created_at"].isoformat(), "updated_at": d["updated_at"].isoformat()}


def _validate_letter(text: str, profile) -> dict:
    titles = [profile.personal.current_designation] if profile.personal.current_designation else []
    companies = [profile.personal.current_company] if profile.personal.current_company else []
    r = validate_claims(GeneratedClaims(text=text, titles=titles, companies=companies), profile)
    return {"status": r.status, "violations": [v.model_dump() for v in r.violations]}


@router.post("/jobs/{job_id}/cover-letter", status_code=201)
async def cover_letter(job_id: str, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    uid = user["_id"]
    job = await jobs.get_owned(db, uid, job_id)
    jd = JDAnalysis.model_validate(job["analysis"])
    profile = await get_profile(db, uid)
    if not profile.personal.name and not profile.knowledge.experience:
        raise HTTPException(status.HTTP_409_CONFLICT, "Complete your master profile first.")
    matched = _matched(profile, jd)
    body, greeting = tailor.template_cover_letter(profile, job, jd, matched)
    body, engine = await tailor.llm_polish("letter", profile, job["title"], job["company"], matched, body)
    text = tailor.cover_letter_text(greeting, body, profile.personal.name)
    validation = _validate_letter(text, profile)
    if validation["status"] != "PASSED":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            {"status": "VALIDATION FAILED", "violations": validation["violations"]})
    tailored = await db[c.RESUMES].find_one({"user_id": uid, "job_id": job_id}, sort=[("created_at", DESCENDING)])
    now = utcnow()
    doc = {"_id": new_id(), "user_id": uid, "job_id": job_id, "resume_id": tailored["_id"] if tailored else None,
           "text": text, "validation": validation, "engine": engine, "created_at": now, "updated_at": now}
    await db[c.COVER_LETTERS].insert_one(doc)
    await log_action(db, user_id=uid, action="cover_letter.generated", entity="cover_letter", entity_id=doc["_id"],
                     details={"job_id": job_id, "engine": engine})
    return _letter_out(doc)


async def _owned_letter(db, uid: str, letter_id: str) -> dict:
    d = await db[c.COVER_LETTERS].find_one({"_id": letter_id, "user_id": uid})
    if not d:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cover letter not found")
    return d


@router.get("/cover-letters/{letter_id}")
async def get_letter(letter_id: str, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    return _letter_out(await _owned_letter(db, user["_id"], letter_id))


@router.put("/cover-letters/{letter_id}")
async def edit_letter(letter_id: str, body: CoverLetterEdit, user: dict = Depends(get_current_user),
                      db: AsyncIOMotorDatabase = Depends(db_dep)):
    await _owned_letter(db, user["_id"], letter_id)
    validation = _validate_letter(body.text, await get_profile(db, user["_id"]))
    if validation["status"] != "PASSED":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            {"status": "VALIDATION FAILED", "violations": validation["violations"]})
    await db[c.COVER_LETTERS].update_one({"_id": letter_id}, {"$set": {
        "text": body.text, "validation": validation, "updated_at": utcnow()}})
    return _letter_out(await _owned_letter(db, user["_id"], letter_id))


@router.delete("/cover-letters/{letter_id}", status_code=204)
async def delete_letter(letter_id: str, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    await _owned_letter(db, user["_id"], letter_id)
    await db[c.COVER_LETTERS].delete_one({"_id": letter_id})
    return Response(status_code=204)


@router.get("/cover-letters/{letter_id}/docx")
async def letter_download(letter_id: str, user: dict = Depends(get_current_user),
                          db: AsyncIOMotorDatabase = Depends(db_dep)):
    d = await _owned_letter(db, user["_id"], letter_id)
    return _docx_response(letter_docx(d["text"]), "cover-letter.docx")


@router.get("/jobs/{job_id}/documents")
async def job_documents(job_id: str, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    uid = user["_id"]
    await jobs.get_owned(db, uid, job_id)
    rs = await db[c.RESUMES].find({"user_id": uid, "job_id": job_id}).sort("created_at", DESCENDING).to_list(50)
    ls = await db[c.COVER_LETTERS].find({"user_id": uid, "job_id": job_id}).sort("created_at", DESCENDING).to_list(50)
    return {"resumes": [{**resumes.resume_out(r), "ats": r.get("ats"), "engine": r.get("engine")} for r in rs],
            "cover_letters": [_letter_out(x) for x in ls]}


@router.get("/resumes/{resume_id}/export.docx")
async def export_resume(resume_id: str, version_id: str | None = None, user: dict = Depends(get_current_user),
                        db: AsyncIOMotorDatabase = Depends(db_dep)):
    resume = await resumes.get_owned(db, user["_id"], resume_id)
    v = await db[c.RESUME_VERSIONS].find_one({"_id": version_id or resume.get("current_version_id"),
                                              "resume_id": resume_id})
    if not v:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resume version not found")
    safe = "".join(ch if ch.isalnum() or ch in " -_" else "_" for ch in resume["name"])[:80] or "resume"
    return _docx_response(resume_docx(ParsedResume.model_validate(v["parsed"])), f"{safe}.docx")
