"""Browser extension API (Phase 9).

The extension authenticates with a personal access token (PAT) the user creates in Settings. A PAT
is stored only as a SHA-256 hash, can be revoked at any time, and works ONLY on the /ext endpoints
below (score, save, suggest answers). It can't read the profile, send anything or change settings.

The extension reads only the page the user is looking at, when they click it. It never submits
application forms: answers are suggestions the user inserts.
"""

import hashlib
import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field, HttpUrl
from pymongo import DESCENDING

from app.agents.jd_agent import analyze_job
from app.auth.deps import db_dep, get_current_user
from app.database import collections as c
from app.jobs import service as jobs
from app.jobs.dedupe import canonical_url
from app.jobs.matching import compute_match
from app.profiles.service import get_profile
from app.schemas.job import JobIn
from app.services.audit import log_action
from app.utils import new_id, utcnow

router = APIRouter(tags=["extension"])
_bearer = HTTPBearer(auto_error=False)

PAT_PREFIX = "saige_pat_"
MAX_TOKENS = 5


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def token_out(d: dict) -> dict:
    return {"id": d["_id"], "name": d["name"], "prefix": d["prefix"], "created_at": d["created_at"].isoformat(),
            "last_used_at": d["last_used_at"].isoformat() if d.get("last_used_at") else None}


class TokenIn(BaseModel):
    name: str = Field(default="Chrome extension", min_length=1, max_length=60)


class PageIn(BaseModel):
    url: HttpUrl | None = None
    title: str = Field(min_length=2, max_length=200)
    company: str = Field(default="", max_length=200)
    location: str | None = Field(default=None, max_length=200)
    text: str = Field(min_length=30, max_length=60000)


# ------------------------------------------------------------------ token management (signed-in web app)

@router.get("/auth/tokens")
async def list_tokens(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    q = {"user_id": user["_id"], "revoked": False, "scopes": {"$ne": "pulse"}}
    docs = await db[c.API_TOKENS].find(q).sort("created_at", DESCENDING).to_list(20)
    return [token_out(d) for d in docs]


@router.post("/auth/tokens", status_code=201)
async def create_token(body: TokenIn, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    if await db[c.API_TOKENS].count_documents({"user_id": user["_id"], "revoked": False, "scopes": {"$ne": "pulse"}}) >= MAX_TOKENS:
        raise HTTPException(status.HTTP_409_CONFLICT, f"You can have at most {MAX_TOKENS} active tokens. Revoke one first.")
    token = PAT_PREFIX + secrets.token_urlsafe(32)
    doc = {"_id": new_id(), "user_id": user["_id"], "name": body.name, "token_hash": _hash(token),
           "prefix": token[: len(PAT_PREFIX) + 4], "scopes": ["extension"], "revoked": False,
           "created_at": utcnow(), "last_used_at": None}
    await db[c.API_TOKENS].insert_one(doc)
    await log_action(db, user_id=user["_id"], action="api_token.created", entity="api_token", entity_id=doc["_id"],
                     details={"name": body.name})
    return {**token_out(doc), "token": token}  # shown once, never retrievable again


@router.delete("/auth/tokens/{token_id}", status_code=204)
async def revoke_token(token_id: str, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    res = await db[c.API_TOKENS].update_one({"_id": token_id, "user_id": user["_id"], "revoked": False},
                                            {"$set": {"revoked": True, "revoked_at": utcnow()}})
    if not res.matched_count:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Token not found")
    await log_action(db, user_id=user["_id"], action="api_token.revoked", entity="api_token", entity_id=token_id)
    return Response(status_code=204)


# ------------------------------------------------------------------ extension endpoints (PAT only)

async def scoped_user(creds: HTTPAuthorizationCredentials | None, db: AsyncIOMotorDatabase, scope: str) -> dict:
    """User behind a personal access token that carries `scope` (old tokens without scopes are extension tokens)."""
    bad = HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or revoked token", headers={"WWW-Authenticate": "Bearer"})
    if creds is None or not creds.credentials.startswith(PAT_PREFIX):
        raise bad
    tok = await db[c.API_TOKENS].find_one({"token_hash": _hash(creds.credentials), "revoked": False})
    if not tok or scope not in (tok.get("scopes") or ["extension"]):
        raise bad
    user = await db[c.USERS].find_one({"_id": tok["user_id"], "is_active": True})
    if not user:
        raise bad
    await db[c.API_TOKENS].update_one({"_id": tok["_id"]}, {"$set": {"last_used_at": utcnow()}})
    return user


async def token_user(creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
                     db: AsyncIOMotorDatabase = Depends(db_dep)) -> dict:
    return await scoped_user(creds, db, "extension")


def _job_in(page: PageIn) -> JobIn:
    return JobIn(title=page.title, company=page.company.strip() or "Unknown company", description=page.text,
                 location=page.location, application_url=page.url, source="extension")


async def _existing(db: AsyncIOMotorDatabase, uid: str, url: HttpUrl | None) -> dict | None:
    key = canonical_url(str(url)) if url else None
    return await db[c.JOBS].find_one({"user_id": uid, "sources.url_key": key}) if key else None


@router.get("/ext/me")
async def ext_me(user: dict = Depends(token_user)):
    return {"name": user.get("name"), "email": user["email"]}


@router.post("/ext/analyze")
async def ext_analyze(page: PageIn, user: dict = Depends(token_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    """Score the posting on screen against the verified profile, without saving anything."""
    uid = user["_id"]
    existing = await _existing(db, uid, page.url)
    if existing and existing.get("match"):
        m = existing["match"]
    else:
        job_in = _job_in(page)
        jd = await analyze_job(job_in.title, job_in.description)
        cand = jobs.normalize(job_in, jd, uid)
        m = compute_match(await get_profile(db, uid), cand, jd, await jobs.get_weights(db, uid)).model_dump()
    return {"score": m["overall"], "classification": m["classification"], "matched_skills": m["matched_skills"][:12],
            "missing_skills": m["missing_required_skills"][:8], "issues": m["issues"][:4],
            "saved_job_id": existing["_id"] if existing else None}


@router.post("/ext/save", status_code=201)
async def ext_save(page: PageIn, user: dict = Depends(token_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    job, created = await jobs.ingest(db, user["_id"], _job_in(page))
    return {"job_id": job["_id"], "created": created, "score": (job.get("match") or {}).get("overall"),
            "path": f"/jobs/{job['_id']}"}


@router.get("/ext/answers")
async def ext_answers(url: HttpUrl, user: dict = Depends(token_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    """Prepared answers for the application on this page, for the user to insert one by one."""
    job = await _existing(db, user["_id"], url)
    if not job:
        return {"job_id": None, "application_id": None, "answers": []}
    app = await db[c.APPLICATIONS].find_one({"user_id": user["_id"], "job_id": job["_id"]})
    if not app:
        return {"job_id": job["_id"], "application_id": None, "answers": []}
    answers = await db[c.APPLICATION_ANSWERS].find({"application_id": app["_id"]}).to_list(100)
    return {"job_id": job["_id"], "application_id": app["_id"],
            "answers": [{"question": a["question"], "answer": a.get("answer"), "confidence": a.get("confidence"),
                         "needs_review": a.get("sensitive", False) or a.get("status") == "REVIEW_REQUIRED"} for a in answers
                        if a.get("answer")]}


# ------------------------------------------------------------------ fill helpers (user-triggered, never submit)

def _text_value(v) -> str:
    return ", ".join(map(str, v)) if isinstance(v, list) else ("" if v is None else str(v))


@router.get("/ext/autofill")
async def ext_autofill(url: HttpUrl | None = None, user: dict = Depends(token_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    """Everything the extension may type into an application form when the user clicks "Fill": verified
    profile fields, prepared answers for this job, and which resume to attach. The user reviews and submits."""
    uid = user["_id"]
    p = await get_profile(db, uid)
    per = p.personal
    parts = (per.name or "").split()
    fields = {
        "full_name": per.name, "first_name": parts[0] if parts else None, "last_name": " ".join(parts[1:]) or None,
        "email": per.email or user["email"], "phone": per.phone, "location": per.current_location, "country": per.country,
        "linkedin": str(per.linkedin_url) if per.linkedin_url else None, "github": str(per.github_url) if per.github_url else None,
        "portfolio": str(per.portfolio_url) if per.portfolio_url else None, "current_company": per.current_company,
        "current_title": per.current_designation,
        "years_experience": f"{per.total_experience_years:g}" if per.total_experience_years else None,
        "notice_period": f"{per.notice_period_days}" if per.notice_period_days is not None else None,
        "expected_ctc": f"{per.expected_ctc:g}" if per.expected_ctc else None,
        "current_ctc": f"{per.current_ctc:g}" if per.current_ctc else None,
    }
    job = await _existing(db, uid, url) if url else None
    answers: list[dict] = []
    resume_name = None
    if job:
        app = await db[c.APPLICATIONS].find_one({"user_id": uid, "job_id": job["_id"]})
        if app:
            answers = [{"question": a["question"], "answer": a.get("answer")} async for a in
                       db[c.APPLICATION_ANSWERS].find({"application_id": app["_id"], "status": {"$ne": "REVIEW_REQUIRED"}})
                       if a.get("answer")]
    from app.profiles.sync_service import master_resume

    r = await master_resume(db, uid)
    if r:
        resume_name = f"{(per.name or 'Resume').replace(' ', '_')}_Resume.docx"
    return {"fields": {k: v for k, v in fields.items() if v}, "answers": answers, "resume": resume_name,
            "job_id": job["_id"] if job else None}


@router.get("/ext/resume.docx")
async def ext_resume(url: HttpUrl | None = None, user: dict = Depends(token_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    """The resume to attach: the tailored one for this job if it exists, else the master resume (DOCX)."""
    from app.profiles.sync_service import master_resume
    from app.resumes.docx_export import resume_docx
    from app.schemas.resume import ParsedResume

    uid = user["_id"]
    job = await _existing(db, uid, url) if url else None
    r = (await db[c.RESUMES].find_one({"user_id": uid, "job_id": job["_id"], "status": "active"}, sort=[("created_at", DESCENDING)])
         if job else None) or await master_resume(db, uid)
    v = r and await db[c.RESUME_VERSIONS].find_one({"_id": r.get("current_version_id")})
    if not v:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No resume in Saige yet")
    return Response(content=resume_docx(ParsedResume.model_validate(v["parsed"])),
                    media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")


@router.get("/ext/profile-edits")
async def ext_profile_edits(platform: str | None = None, user: dict = Depends(token_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    """Prepared LinkedIn / Naukri edits waiting to be put on the site."""
    from app.profiles.sync_service import FIELD_NAME, PENDING, PLATFORM_NAME

    q: dict = {"user_id": user["_id"], "approval_status": PENDING}
    if platform in ("linkedin", "naukri"):
        q["platform"] = platform
    docs = await db[c.PROFILE_CHANGES].find(q).sort("updated_at", DESCENDING).to_list(40)
    return [{"id": d["_id"], "platform": d["platform"], "platform_name": PLATFORM_NAME.get(d["platform"], d["platform"]),
             "field": d["field"], "field_name": FIELD_NAME.get(d["field"], d["field"]), "text": _text_value(d.get("after"))}
            for d in docs]


@router.post("/ext/profile-edits/{change_id}/applied")
async def ext_edit_applied(change_id: str, user: dict = Depends(token_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    from app.profiles.sync_service import mark_applied

    await mark_applied(db, user["_id"], change_id)
    return {"ok": True}


class ExtComments(BaseModel):
    comments: list[dict] = Field(min_length=1, max_length=30)


@router.post("/ext/comment-replies")
async def ext_comment_replies(body: ExtComments, user: dict = Depends(token_user)):
    """Draft replies to the comments visible on the user's own LinkedIn post (the user posts each one)."""
    from app.linkedin_posts.router import reply_to

    first = (user.get("name") or "").split(" ")[0]
    return {"replies": [{"author": str(x.get("author", ""))[:80], "comment": str(x.get("text", ""))[:500],
                         "reply": reply_to(str(x.get("author", "")), str(x.get("text", "")), first)} for x in body.comments]}


class PageResumeIn(PageIn):
    template: str = Field(default="modern", max_length=30)


@router.post("/ext/resume", status_code=201)
async def ext_build_resume(page: PageResumeIn, user: dict = Depends(token_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    """ATS resume for the posting on screen, built only from the verified profile (same engine as ATS Studio)."""
    from app.studio import router as studio

    body = studio.ResumeIn(jd_text=page.text, title=page.title, company=page.company, template=page.template)
    r = await studio._build(db, user["_id"], body, page.text, page.title, page.company.strip())
    return {"id": r["id"], "title": r["title"], "company": r["company"], "score": r["ats"]["score"],
            "missing": (r["ats"]["missing_required"] + r["ats"]["missing_preferred"])[:8], "improve": r["improve"][:3],
            "verdict": r["verdict"]["label"], "path": "/studio"}


@router.get("/ext/studio/{resume_id}/download")
async def ext_resume_download(resume_id: str, format: str = "pdf", on: str | None = None,
                              user: dict = Depends(token_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    from app.studio import router as studio

    if format not in ("pdf", "docx"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "format must be pdf or docx")
    data, fname = await studio.file_for(db, user["_id"], resume_id, format, None, on)
    return studio.file_response(data, fname, format)


# ------------------------------------------------------------------ extension v2: side panel (user-triggered, never sends)

class JDPageIn(BaseModel):
    """The job (or hiring post) text the user has open. Title and company are optional: they are detected."""
    url: HttpUrl | None = None
    title: str = Field(default="", max_length=200)
    company: str = Field(default="", max_length=200)
    location: str | None = Field(default=None, max_length=200)
    text: str = Field(min_length=30, max_length=60000)
    template: str = Field(default="modern", max_length=30)


def _hiring_info(body: JDPageIn) -> dict:
    from app.studio import analyzer, apply

    title = body.title.strip() or analyzer.extract_title(body.text) or ""
    company = body.company.strip() or analyzer.extract_company(body.text) or ""
    return {"title": title, "company": company, "emails": apply.emails_in(body.text)[:5], "contact_first_name": apply.contact_name(body.text)}


@router.post("/ext/analyze-jd")
async def ext_analyze_jd(body: JDPageIn, user: dict = Depends(token_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    """Match score, have/missing skills, eligibility and the post's emails/company/role. Saves nothing."""
    from app.studio import analyzer

    info = _hiring_info(body)
    a = analyzer.analyze(await get_profile(db, user["_id"]), body.text, info["title"], info["company"])
    existing = await _existing(db, user["_id"], body.url)
    sk = a["skills"]
    both = sk["required"] + sk["preferred"]
    return {**info, "title": a["title"], "score": a["score"], "classification": a["classification"], "verdict": a["verdict"],
            "have": [s["name"] for s in both if s["have"]][:16], "missing": [s["name"] for s in both if not s["have"]][:12],
            "missing_required": [s["name"] for s in sk["required"] if not s["have"]][:8],
            "eligibility": a["eligibility"], "strengths": a["strengths"][:4], "gaps": a["gaps"][:4], "summary": a["summary"],
            "is_hiring_post": bool(info["emails"]), "saved_job_id": existing["_id"] if existing else None}


def _downloads(resume_id: str) -> dict:
    return {fmt: f"/api/ext/studio/{resume_id}/download?format={fmt}" for fmt in ("pdf", "docx")}


@router.post("/ext/generate-resume", status_code=201)
async def ext_generate_resume(body: JDPageIn, user: dict = Depends(token_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    """ATS resume for this JD (ATS Studio engine, verified profile only) plus download paths for PDF and DOCX."""
    info = _hiring_info(body)
    out = await ext_build_resume(PageResumeIn(url=body.url, title=info["title"] or "Target role", company=info["company"], text=body.text,
                                              template=body.template), user, db)
    return {**out, "downloads": _downloads(out["id"])}


class ApplicationEmailIn(JDPageIn):
    resume_id: str | None = Field(default=None, max_length=64)  # reuse a resume generated a moment ago
    to: str | None = Field(default=None, max_length=200, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@router.post("/ext/draft-application-email")
async def ext_draft_application_email(body: ApplicationEmailIn, user: dict = Depends(token_user),
                                      db: AsyncIOMotorDatabase = Depends(db_dep)):
    """Tailored resume + a truth-checked application email (same drafter as ATS Studio "apply by email").
    Nothing is sent: the user opens the draft in their own mail client and attaches the downloaded resume."""
    from urllib.parse import quote

    from app.services.agent_runs import agent_run
    from app.services.truth_guard import GeneratedClaims, validate_claims
    from app.studio import apply
    from app.studio import router as studio

    uid = user["_id"]
    info = _hiring_info(body)
    profile = await get_profile(db, uid)
    async with agent_run(db, "extension_application_email", uid, {"company": info["company"], "title": info["title"]}) as run:
        if body.resume_id:
            r = await db[c.RESUMES].find_one({"_id": body.resume_id, "user_id": uid})
            if not r:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "Resume not found")
            out = {"id": r["_id"], "title": r.get("target_title") or info["title"], "ats": r.get("ats") or {}}
        else:
            out = await studio._build(db, uid, studio.ResumeIn(jd_text=body.text, title=info["title"], company=info["company"],
                                                               template=body.template), body.text, info["title"], info["company"])
        subject, mail = apply.draft(profile, out["title"], info["company"], out["ats"].get("matched_keywords", []), body.text)
        check = validate_claims(GeneratedClaims(text=mail), profile)
        if not check.passed:
            run.errors.append("truth guard blocked the draft")
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, {"status": "VALIDATION FAILED", "violations": [
                v.model_dump() if hasattr(v, "model_dump") else v for v in check.violations]})
        to = body.to or (info["emails"][0] if info["emails"] else "")
        run.actions.append(f"Drafted application email for {info['company'] or 'this role'} (not sent)")
        run.output = {"resume_id": out["id"], "to": to}
    await log_action(db, user_id=uid, action="extension.application_drafted", entity="resume", entity_id=out["id"],
                     details={"company": info["company"], "to": to})
    to_q = quote(to) if to else ""
    return {"resume_id": out["id"], "score": out["ats"].get("score"), "title": out["title"], "company": info["company"],
            "to": to, "emails_found": info["emails"], "subject": subject, "body": mail, "validation": {"status": "PASSED"},
            "downloads": _downloads(out["id"]), "attach_note": "Attach the downloaded resume before sending.",
            "mailto": f"mailto:{to_q}?subject={quote(subject)}&body={quote(mail)}",
            "gmail_compose": f"https://mail.google.com/mail/?view=cm&fs=1&to={to_q}&su={quote(subject)}&body={quote(mail)}"}


async def _caps(db: AsyncIOMotorDatabase, uid: str, company: str) -> dict:
    from app.jobs.dedupe import company_key
    from app.recruiters import service as rec

    now = utcnow()
    limit = await rec.daily_limit(db, uid)
    today = await rec.sent_today(db, uid, now)
    week = await db[c.OUTREACH].count_documents({"user_id": uid, "company_key": company_key(company),
                                                 "sent_at": {"$gte": now - timedelta(days=7)}}) if company else 0
    return {"daily_limit": limit, "sent_today": today, "company_week_cap": rec.PER_COMPANY_WEEKLY_CAP, "company_sent_this_week": week,
            "can_send_more": today < limit and week < rec.PER_COMPANY_WEEKLY_CAP}


@router.get("/ext/company-contacts")
async def ext_company_contacts(company: str, user: dict = Depends(token_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    """The user's OWN contacts at this company (added by them, from their inbox, or from postings they saved). Nothing is looked up
    on the web and no address is guessed."""
    from app.jobs.dedupe import company_key
    from app.recruiters import service as rec

    uid = user["_id"]
    key = company_key(company)
    if not key:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Company name required")
    await rec.sync_contacts(db, uid)  # only already-imported mail and saved jobs
    docs = await db[c.RECRUITER_CONTACTS].find({"user_id": uid, "company_key": key}).sort("created_at", DESCENDING).to_list(30)
    return {"company": company, "contacts": [rec.contact_out(d) for d in docs if not d.get("unsubscribed")],
            "caps": await _caps(db, uid, company)}


class SaveDraftIn(BaseModel):
    company: str = Field(min_length=1, max_length=160)
    outreach_id: str | None = Field(default=None, max_length=64)  # re-save the user's edits to a draft saved a moment ago
    contact_id: str | None = Field(default=None, max_length=64)
    name: str | None = Field(default=None, max_length=120)  # a contact seen on the page (e.g. the email in a hiring post)
    email: str | None = Field(default=None, max_length=200, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    kind: str = Field(default="cold", pattern="^(cold|referral|hiring_manager|employee_intro)$")
    page: PageIn | None = None  # the job on screen; saved to Saige so the draft can name the role
    context: str | None = Field(default=None, max_length=600)
    subject: str | None = Field(default=None, max_length=200)  # the user's edited wording, if any
    body: str | None = Field(default=None, max_length=5000)


@router.post("/ext/save-draft", status_code=201)
async def ext_save_draft(body: SaveDraftIn, user: dict = Depends(token_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    """Save a truth-checked outreach DRAFT in Saige (Outreach). It waits for the user's approval; nothing is sent, and the
    10/day + 3/company/week caps are applied when it is sent later."""
    from app.recruiters import service as rec
    from app.schemas.recruiter import ContactIn, DraftIn

    uid = user["_id"]
    if body.outreach_id:
        if not (body.subject and body.body):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Subject and body required to update a draft")
        out = await rec.edit_draft(db, uid, body.outreach_id, body.subject, body.body)
        return {"draft": out, "caps": await _caps(db, uid, body.company), "path": "/recruiters",
                "note": "Draft updated. Still waiting for your approval."}
    if body.contact_id:
        contact = await rec.get_contact(db, uid, body.contact_id)
    elif body.email:
        contact, _ = await rec.create_contact(db, uid, ContactIn(
            name=(body.name or body.email.split("@")[0].replace(".", " ").title())[:120], company=body.company, email=body.email,
            source="job", role="recruiter"))
    else:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Pick a contact or give an email address")
    job_id = None
    if body.page:
        job, _ = await jobs.ingest(db, uid, _job_in(body.page))
        job_id = job["_id"]
    out = await rec.create_draft(db, uid, DraftIn(contact_id=contact["_id"], kind=body.kind, job_id=job_id, context=body.context))
    if body.subject and body.body:  # the user's edited wording, truth-checked again
        try:
            out = await rec.edit_draft(db, uid, out["id"], body.subject, body.body)
        except HTTPException:
            await db[c.OUTREACH].delete_one({"_id": out["id"], "user_id": uid, "status": "draft"})  # no half-saved draft
            raise
    await log_action(db, user_id=uid, action="extension.draft_saved", entity="outreach", entity_id=out["id"],
                     details={"company": body.company, "kind": body.kind})
    return {"draft": out, "caps": await _caps(db, uid, body.company), "path": "/recruiters",
            "note": "Saved as a draft. Approve it in Saige (Outreach) before it can be sent."}
