"""Recruiter side. Recruiters post jobs (/api/hiring/jobs) and search candidates who opted in with
"Let recruiters find me" (/api/talent/settings, default off). Search shows only verified profile facts
(name, role, years, skills, location, published portfolio) and never email or phone. A recruiter sends an
interest request; the candidate is notified and only sees their contact shared when they accept."""

import re

from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.auth.deps import db_dep, get_current_user
from app.auth.roles import effective_role, require_recruiter
from app.database import collections as c
from app.jobs.matching import _skill_key, candidate_skills
from app.profiles.service import get_profile
from app.services.audit import log_action
from app.services.notify import notify
from app.services.skills_vocab import canonical, find_skills
from app.utils import as_utc, new_id, start_of_today, utcnow

router = APIRouter(tags=["hiring"])

DAILY_REQUEST_CAP = 50


def _iso(v) -> str | None:
    return as_utc(v).isoformat() if v else None


# ---------------------------------------------------------------- jobs

class JobIn(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    company: str = Field(min_length=1, max_length=160)
    location: str = Field(default="", max_length=160)
    description: str = Field(default="", max_length=20000)
    skills: list[str] = Field(default=[], max_length=40)


def _job_out(j: dict) -> dict:
    return {"id": j["_id"], "title": j["title"], "company": j["company"], "location": j.get("location", ""),
            "description": j.get("description", ""), "skills": j.get("skills", []), "status": j.get("status", "open"),
            "created_at": _iso(j.get("created_at"))}


@router.post("/hiring/jobs", status_code=201)
async def create_job(body: JobIn, user: dict = Depends(require_recruiter), db: AsyncIOMotorDatabase = Depends(db_dep)):
    skills = [canonical(s.strip()) for s in body.skills if s.strip()]
    if not skills:
        skills = find_skills(f"{body.title}\n{body.description}")
    skills = list(dict.fromkeys(skills))[:40]
    doc = {"_id": new_id(), "user_id": user["_id"], **body.model_dump(), "skills": skills, "status": "open", "created_at": utcnow()}
    await db[c.RECRUITER_JOBS].insert_one(doc)
    await log_action(db, user_id=user["_id"], action="hiring.job_posted", entity="recruiter_job", entity_id=doc["_id"],
                     details={"title": body.title, "company": body.company})
    return _job_out(doc)


@router.get("/hiring/jobs")
async def list_jobs(user: dict = Depends(require_recruiter), db: AsyncIOMotorDatabase = Depends(db_dep)):
    rows = await db[c.RECRUITER_JOBS].find({"user_id": user["_id"]}).sort("created_at", -1).to_list(length=200)
    return [_job_out(j) for j in rows]


@router.delete("/hiring/jobs/{job_id}", status_code=204)
async def delete_job(job_id: str, user: dict = Depends(require_recruiter), db: AsyncIOMotorDatabase = Depends(db_dep)):
    res = await db[c.RECRUITER_JOBS].delete_one({"_id": job_id, "user_id": user["_id"]})
    if not res.deleted_count:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    await log_action(db, user_id=user["_id"], action="hiring.job_deleted", entity="recruiter_job", entity_id=job_id)


# ---------------------------------------------------------------- candidate search

async def _candidate_card(db: AsyncIOMotorDatabase, u: dict) -> tuple[dict, set[str]]:
    profile = await get_profile(db, u["_id"])
    p = profile.personal
    portfolio = await db[c.PORTFOLIOS].find_one({"_id": u["_id"], "published": True}, {"slug": 1})
    skills = list(dict.fromkeys(profile.skills.all()))
    card = {"id": u["_id"], "name": p.name or u.get("name") or "Candidate", "role": p.current_designation,
            "years": p.total_experience_years, "location": p.current_location, "skills": skills[:30],
            "portfolio_url": f"/p/{portfolio['slug']}" if portfolio and portfolio.get("slug") else None}
    return card, candidate_skills(profile)


@router.get("/hiring/candidates")
async def search_candidates(job_id: str | None = None, q: str = Query("", max_length=200), limit: int = Query(50, ge=1, le=200),
                            user: dict = Depends(require_recruiter), db: AsyncIOMotorDatabase = Depends(db_dep)):
    wanted: list[str] = []
    if job_id:
        job = await db[c.RECRUITER_JOBS].find_one({"_id": job_id, "user_id": user["_id"]})
        if not job:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
        wanted = job.get("skills", [])
    extra = [s.strip() for s in re.split(r"[,;]", q) if s.strip()]
    wanted = list(dict.fromkeys(wanted + [canonical(s) for s in extra]))
    keys = {_skill_key(s): s for s in wanted}
    pool = await db[c.USERS].find({"discoverable": True, "is_active": True, "_id": {"$ne": user["_id"]}}).to_list(length=2000)
    results = []
    for u in pool:
        if effective_role(u) != "jobseeker":
            continue
        card, have = await _candidate_card(db, u)
        matched = [label for k, label in keys.items() if k in have]
        if extra and not job_id and not matched:
            text = f"{card['name']} {card['role'] or ''} {card['location'] or ''}".lower()
            if not any(t.lower() in text for t in extra):
                continue
        card["matched_skills"] = matched
        card["missing_skills"] = [label for k, label in keys.items() if k not in have]
        card["match"] = round(100 * len(matched) / len(keys)) if keys else None
        results.append(card)
    results.sort(key=lambda r: (r["match"] or 0, r["years"] or 0), reverse=True)
    return results[:limit]


# ---------------------------------------------------------------- interest requests

class RequestIn(BaseModel):
    candidate_id: str = Field(min_length=1, max_length=64)
    job_id: str | None = Field(default=None, max_length=64)
    message: str = Field(default="", max_length=1000)


async def _contact(db: AsyncIOMotorDatabase, candidate_id: str) -> dict:
    u = await db[c.USERS].find_one({"_id": candidate_id}, {"email": 1, "name": 1})
    profile = await get_profile(db, candidate_id)
    return {"email": profile.personal.email or (u or {}).get("email"), "phone": profile.personal.phone}


@router.post("/hiring/requests", status_code=201)
async def send_request(body: RequestIn, user: dict = Depends(require_recruiter), db: AsyncIOMotorDatabase = Depends(db_dep)):
    cand = await db[c.USERS].find_one({"_id": body.candidate_id, "discoverable": True, "is_active": True})
    if not cand or effective_role(cand) != "jobseeker":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Candidate not found")
    job = None
    if body.job_id:
        job = await db[c.RECRUITER_JOBS].find_one({"_id": body.job_id, "user_id": user["_id"]})
        if not job:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    if await db[c.TALENT_REQUESTS].find_one({"user_id": user["_id"], "candidate_id": cand["_id"], "job_id": body.job_id}):
        raise HTTPException(status.HTTP_409_CONFLICT, "You already sent this candidate a request for this job")
    if await db[c.TALENT_REQUESTS].count_documents({"user_id": user["_id"], "created_at": {"$gte": start_of_today()}}) >= DAILY_REQUEST_CAP:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, f"Daily limit of {DAILY_REQUEST_CAP} interest requests reached")
    doc = {"_id": new_id(), "user_id": user["_id"], "candidate_id": cand["_id"], "job_id": body.job_id,
           "job_title": job["title"] if job else None, "company": job["company"] if job else None,
           "recruiter_name": user.get("name") or "A recruiter", "message": body.message.strip(), "status": "pending", "created_at": utcnow()}
    await db[c.TALENT_REQUESTS].insert_one(doc)
    await log_action(db, user_id=user["_id"], action="hiring.interest_sent", entity="talent_request", entity_id=doc["_id"],
                     details={"job_id": body.job_id})
    what = f" for {doc['job_title']} at {doc['company']}" if job else ""
    await notify(db, user_id=cand["_id"], kind="recruiter_interest", title=f"{doc['recruiter_name']} is interested in you{what}",
                 body="Accept to share your contact details, or decline. Nothing is shared until you accept.", link="/settings?tab=recruiters")
    return {"id": doc["_id"], "status": "pending"}


@router.get("/hiring/requests")
async def sent_requests(user: dict = Depends(require_recruiter), db: AsyncIOMotorDatabase = Depends(db_dep)):
    rows = await db[c.TALENT_REQUESTS].find({"user_id": user["_id"]}).sort("created_at", -1).to_list(length=500)
    out = []
    for r in rows:
        cand = await db[c.USERS].find_one({"_id": r["candidate_id"]}, {"name": 1})
        item = {"id": r["_id"], "candidate_id": r["candidate_id"], "candidate_name": (cand or {}).get("name") or "Candidate",
                "job_title": r.get("job_title"), "status": r["status"], "created_at": _iso(r.get("created_at")), "contact": None}
        if r["status"] == "accepted":
            item["contact"] = await _contact(db, r["candidate_id"])
        out.append(item)
    return out


# ---------------------------------------------------------------- candidate side

class TalentSettings(BaseModel):
    discoverable: bool


@router.get("/talent/settings")
async def get_talent_settings(user: dict = Depends(get_current_user)):
    return {"discoverable": bool(user.get("discoverable"))}


@router.put("/talent/settings")
async def put_talent_settings(body: TalentSettings, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    await db[c.USERS].update_one({"_id": user["_id"]}, {"$set": {"discoverable": body.discoverable, "updated_at": utcnow()}})
    await log_action(db, user_id=user["_id"], action="talent.visibility_changed", entity="user", entity_id=user["_id"],
                     details={"discoverable": body.discoverable})
    return {"discoverable": body.discoverable}


@router.get("/talent/requests")
async def incoming_requests(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    rows = await db[c.TALENT_REQUESTS].find({"candidate_id": user["_id"]}).sort("created_at", -1).to_list(length=200)
    return [{"id": r["_id"], "recruiter_name": r.get("recruiter_name"), "job_title": r.get("job_title"), "company": r.get("company"),
             "message": r.get("message", ""), "status": r["status"], "created_at": _iso(r.get("created_at"))} for r in rows]


class RespondIn(BaseModel):
    accept: bool


@router.post("/talent/requests/{request_id}/respond")
async def respond(request_id: str, body: RespondIn, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    r = await db[c.TALENT_REQUESTS].find_one({"_id": request_id, "candidate_id": user["_id"]})
    if not r:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Request not found")
    if r["status"] != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, "Already answered")
    new_status = "accepted" if body.accept else "declined"
    await db[c.TALENT_REQUESTS].update_one({"_id": request_id}, {"$set": {"status": new_status, "responded_at": utcnow()}})
    await log_action(db, user_id=user["_id"], action=f"talent.request_{new_status}", entity="talent_request", entity_id=request_id)
    name = user.get("name") or "A candidate"
    await notify(db, user_id=r["user_id"], kind="talent_response",
                 title=f"{name} {'accepted' if body.accept else 'declined'} your request",
                 body="Their contact details are now visible on your Recruiter page." if body.accept else "", link="/recruiter")
    return {"id": request_id, "status": new_status}
