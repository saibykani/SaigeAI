"""Interview day brief: everything shown comes from the user's own interview, saved job and verified profile (never invented)."""

from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.auth.deps import db_dep, get_current_user
from app.database import collections as c
from app.jobs.dedupe import company_key
from app.mock_interview import questions as qs
from app.profiles.service import get_profile
from app.services.skills_vocab import normalize_key

router = APIRouter(tags=["interviews"])

CHECKLIST = [
    "Test the meeting link, camera and microphone 15 minutes before",
    "Keep your resume and the job description open",
    "Sit somewhere quiet with good light and keep water nearby",
    "Prepare 2 questions to ask the interviewer (team, expectations for the first 90 days, next steps)",
    "Have a pen and paper ready for notes",
]


def _line(*parts) -> str:
    for p in parts:
        if isinstance(p, str) and p.strip():
            return p.strip()[:220]
    return ""


def matching(profile, jd_skills: list[str]) -> list[dict]:
    wanted = {normalize_key(s) for s in jd_skills}
    out = []
    for p in profile.knowledge.projects:
        hit = [t for t in p.technologies if normalize_key(t) in wanted]
        if hit:
            out.append({"kind": "project", "name": p.name, "role": p.role, "skills": hit,
                        "line": _line(*(p.highlights or []), p.description)})
    for e in profile.knowledge.experience:
        hit = [t for t in e.technologies if normalize_key(t) in wanted]
        if hit:
            out.append({"kind": "experience", "name": f"{e.title} at {e.company}", "role": e.title, "skills": hit,
                        "line": _line(*(e.achievements or []), *(e.responsibilities or []))})
    return out[:6]


async def _find_job(db: AsyncIOMotorDatabase, uid: str, app_doc: dict | None, company: str | None) -> dict | None:
    if app_doc and app_doc.get("job_id"):
        job = await db[c.JOBS].find_one({"_id": app_doc["job_id"], "user_id": uid})
        if job:
            return job
    if company:
        return await db[c.JOBS].find_one({"user_id": uid, "company_key": company_key(company)}, sort=[("updated_at", -1)])
    return None


async def build_brief(db: AsyncIOMotorDatabase, uid: str, *, company: str | None, role: str | None, scheduled_at: str | None,
                      meeting_url: str | None, round_: str | None, app_doc: dict | None, source: dict) -> dict:
    job = await _find_job(db, uid, app_doc, company)
    analysis = (job or {}).get("analysis") or {}
    jd_skills = list(dict.fromkeys((job or {}).get("skills") or analysis.get("skills") or []))
    role_name = role or (job or {}).get("title") or ""
    profile = await get_profile(db, uid)
    ctx = qs.context(profile, role_name, (job or {}).get("description") or "", jd_skills)
    questions = [{"text": q["text"], "kind": q["kind"], "skill": q.get("skill")}
                 for q in qs.generate(ctx, "mixed", "medium", 8, seed=1)]
    return {
        **source, "company": company, "role": role_name or None, "scheduled_at": scheduled_at, "meeting_url": meeting_url,
        "round": round_, "job_id": (job or {}).get("_id"), "has_job": bool(job),
        "requirements": ((job or {}).get("requirements") or analysis.get("requirements") or [])[:8],
        "skills": ctx["jd_skills"], "matching": matching(profile, ctx["jd_skills"]) if ctx["jd_skills"] else [],
        "brush_up": ctx["miss"], "questions": questions, "checklist": CHECKLIST,
    }


@router.get("/interviews/brief")
async def brief_from_email(email_id: str = Query(min_length=1), user: dict = Depends(get_current_user),
                           db: AsyncIOMotorDatabase = Depends(db_dep)):
    uid = user["_id"]
    e = await db[c.EMAILS].find_one({"_id": email_id, "user_id": uid})
    if not e:
        raise HTTPException(404, "Email not found")
    ex = e.get("extracted") or {}
    company = ex.get("company") or ex.get("sender_name") or None
    app_doc = await db[c.APPLICATIONS].find_one({"_id": e["application_id"], "user_id": uid}) if e.get("application_id") else None
    if app_doc:
        company = app_doc.get("company") or company
    return await build_brief(db, uid, company=company, role=(app_doc or {}).get("role") or e.get("subject"),
                             scheduled_at=ex.get("interview_at"), meeting_url=ex.get("meeting_url"),
                             round_=ex.get("interview_round"), app_doc=app_doc, source={"email_id": email_id})


@router.get("/interviews/{interview_id}/brief")
async def brief(interview_id: str, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    uid = user["_id"]
    i = await db[c.INTERVIEWS].find_one({"_id": interview_id, "user_id": uid})
    if not i:
        raise HTTPException(404, "Interview not found")
    app_doc = await db[c.APPLICATIONS].find_one({"_id": i["application_id"], "user_id": uid}) if i.get("application_id") else None
    return await build_brief(db, uid, company=i.get("company"), role=i.get("role"), scheduled_at=i["scheduled_at"].isoformat(),
                             meeting_url=i.get("meeting_url"), round_=i.get("round"), app_doc=app_doc,
                             source={"interview_id": interview_id})
