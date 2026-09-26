"""Job pipeline: normalize -> analyze JD -> deduplicate -> match -> store (spec section 2)."""

import re

from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import DESCENDING

from app.agents.jd_agent import analyze_job
from app.database import collections as c
from app.jobs.dedupe import canonical_url, company_key, is_duplicate
from app.jobs.matching import compute_match, role_similarity
from app.profiles.service import get_profile
from app.schemas.job import JDAnalysis, JobIn, MatchWeights
from app.schemas.profile import Profile
from app.services.audit import log_action
from app.services.notify import notify
from app.services.skills_vocab import canonical, normalize_key
from app.utils import new_id, utcnow

HIGH_MATCH = 85

_INDIA_CITIES = ("hyderabad", "bangalore", "bengaluru", "chennai", "pune", "mumbai", "delhi",
                 "noida", "gurgaon", "gurugram", "kolkata", "ahmedabad", "kochi", "coimbatore",
                 "jaipur", "chandigarh", "indore", "trivandrum", "thiruvananthapuram", "mysore")
_COUNTRIES = {"india": "India", "united states": "USA", "usa": "USA", "us": "USA", "canada": "Canada",
              "united kingdom": "UK", "uk": "UK", "london": "UK", "germany": "Germany",
              "berlin": "Germany", "netherlands": "Netherlands", "amsterdam": "Netherlands",
              "ireland": "Ireland", "dublin": "Ireland", "singapore": "Singapore",
              "australia": "Australia", "sydney": "Australia", "uae": "UAE", "dubai": "UAE",
              "new york": "USA", "san francisco": "USA", "toronto": "Canada", "remote": None}


def infer_country(location: str | None) -> str | None:
    if not location:
        return None
    low = location.lower()
    if any(city in low for city in _INDIA_CITIES):
        return "India"
    for key, country in _COUNTRIES.items():
        if re.search(rf"\b{re.escape(key)}\b", low):
            return country
    return None


async def get_weights(db: AsyncIOMotorDatabase, user_id: str) -> MatchWeights:
    doc = await db[c.SYSTEM_SETTINGS].find_one({"user_id": user_id})
    return MatchWeights.model_validate((doc or {}).get("matching", {}))


async def save_weights(db: AsyncIOMotorDatabase, user_id: str, weights: MatchWeights) -> MatchWeights:
    await db[c.SYSTEM_SETTINGS].update_one(
        {"user_id": user_id},
        {"$set": {"matching": weights.model_dump(), "updated_at": utcnow()},
         "$setOnInsert": {"_id": new_id(), "user_id": user_id}},
        upsert=True,
    )
    await log_action(db, user_id=user_id, action="matching.weights_updated",
                     details=weights.model_dump())
    return weights


def _source_ref(job: JobIn, url_key: str | None) -> dict:
    return {"source": job.source, "source_job_id": job.source_job_id,
            "url": str(job.application_url) if job.application_url else None,
            "url_key": url_key, "first_seen": utcnow().isoformat()}


def normalize(job: JobIn, jd: JDAnalysis, user_id: str) -> dict:
    """Canonical job record (spec section 13 fields, snake_case)."""
    now = utcnow()
    url = str(job.application_url) if job.application_url else None
    url_key = canonical_url(url)
    return {
        "_id": new_id(), "user_id": user_id,
        "source": job.source, "source_job_id": job.source_job_id,
        "company": job.company.strip(), "company_key": company_key(job.company),
        "title": job.title.strip(), "location": job.location,
        "country": infer_country(job.location),
        "remote": job.remote if job.remote is not None else jd.remote,
        "employment_type": job.employment_type or jd.employment_type,
        "salary_min": job.salary_min if job.salary_min is not None else jd.salary_min,
        "salary_max": job.salary_max if job.salary_max is not None else jd.salary_max,
        "currency": job.currency or jd.currency,
        "experience_required": jd.experience_text,
        "skills": jd.skills, "description": job.description,
        "requirements": jd.requirements, "nice_to_have": jd.nice_to_have,
        "application_url": url, "url_key": url_key,
        "posted_date": job.posted_date, "deadline": job.deadline,
        "sources": [_source_ref(job, url_key)],
        "analysis": jd.model_dump(), "match": None, "status": "new",
        "created_at": now, "updated_at": now,
    }


async def _find_duplicate(db: AsyncIOMotorDatabase, user_id: str, cand: dict) -> tuple[dict | None, str]:
    or_: list[dict] = [{"company_key": cand["company_key"]}]
    if cand.get("url_key"):
        or_.append({"sources.url_key": cand["url_key"]})
    if cand.get("source_job_id"):
        or_.append({"sources.source_job_id": cand["source_job_id"]})
    async for existing in db[c.JOBS].find({"user_id": user_id, "$or": or_}).limit(500):
        dup, reason = is_duplicate({**cand, "url_key": cand.get("url_key")}, existing)
        if dup:
            return existing, reason
    return None, ""


async def score_job(db: AsyncIOMotorDatabase, user_id: str, job: dict, profile: Profile | None = None,
                    weights: MatchWeights | None = None) -> dict:
    profile = profile or await get_profile(db, user_id)
    weights = weights or await get_weights(db, user_id)
    jd = JDAnalysis.model_validate(job["analysis"])
    match = compute_match(profile, job, jd, weights).model_dump()
    previous = (job.get("match") or {}).get("overall")
    await db[c.JOBS].update_one({"_id": job["_id"]},
                                {"$set": {"match": match, "updated_at": utcnow()}})
    job["match"] = match
    await log_action(db, user_id=user_id, action="job.match_calculated", entity="job",
                     entity_id=job["_id"], details={"overall": match["overall"],
                                                    "classification": match["classification"]})
    if match["overall"] >= HIGH_MATCH and (previous is None or previous < HIGH_MATCH):
        await notify(db, user_id=user_id, kind="high_match_job",
                     title=f"High-match job: {job['title']} at {job['company']} ({match['overall']}%)",
                     link=f"/jobs/{job['_id']}")
    return job


async def ingest(db: AsyncIOMotorDatabase, user_id: str, job_in: JobIn, *,
                 profile: Profile | None = None, weights: MatchWeights | None = None) -> tuple[dict, bool]:
    """Returns (job, is_new). Duplicates merge into the existing canonical job."""
    jd = await analyze_job(job_in.title, job_in.description)
    cand = normalize(job_in, jd, user_id)
    existing, reason = await _find_duplicate(db, user_id, cand)
    if existing:
        ref = cand["sources"][0]
        known = any((s.get("source"), s.get("source_job_id"), s.get("url_key")) ==
                    (ref["source"], ref["source_job_id"], ref["url_key"]) for s in existing["sources"])
        fill = {k: cand[k] for k in ("salary_min", "salary_max", "currency", "deadline",
                                     "employment_type", "application_url", "location", "country")
                if existing.get(k) in (None, "") and cand.get(k) not in (None, "")}
        update: dict = {"$set": {**fill, "updated_at": utcnow()}}
        if not known:
            update["$push"] = {"sources": ref}
        await db[c.JOBS].update_one({"_id": existing["_id"]}, update)
        await log_action(db, user_id=user_id, action="job.duplicate_merged", entity="job",
                         entity_id=existing["_id"], details={"reason": reason, "source": job_in.source})
        return await db[c.JOBS].find_one({"_id": existing["_id"]}), False

    await db[c.JOBS].insert_one(cand)
    await log_action(db, user_id=user_id, action="job.discovered", entity="job", entity_id=cand["_id"],
                     details={"source": job_in.source, "title": cand["title"], "company": cand["company"]})
    await log_action(db, user_id=user_id, action="jd.analyzed", entity="job", entity_id=cand["_id"],
                     details={"extraction": jd.extraction, "skills": len(jd.skills)})
    return await score_job(db, user_id, cand, profile, weights), True


def title_relevant(title: str, profile: Profile) -> bool:
    """Filter for bulk board sync: keep postings plausibly related to the user's target roles."""
    targets = profile.preferences.target_roles or (
        [profile.personal.current_designation] if profile.personal.current_designation else [])
    if not targets:
        return True
    score = role_similarity(title, targets)
    return score is not None and score >= 45


async def get_owned(db: AsyncIOMotorDatabase, user_id: str, job_id: str) -> dict:
    job = await db[c.JOBS].find_one({"_id": job_id, "user_id": user_id})
    if not job:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    return job


async def recommend_resume(db: AsyncIOMotorDatabase, user_id: str, job: dict) -> dict | None:
    wanted = {normalize_key(canonical(s)) for s in job.get("analysis", {}).get("skills", [])}
    if not wanted:
        return None
    best = None
    resumes = await db[c.RESUMES].find({"user_id": user_id, "status": "active"}).to_list(length=100)
    for r in resumes:
        v = await db[c.RESUME_VERSIONS].find_one({"_id": r.get("current_version_id")})
        if not v:
            continue
        have = {normalize_key(canonical(s)) for s in v["parsed"].get("skills", [])}
        overlap = len(wanted & have)
        if best is None or overlap > best["overlap"]:
            best = {"id": r["_id"], "name": r["name"], "kind": r["kind"], "overlap": overlap,
                    "of": len(wanted)}
    return best


def job_summary(j: dict) -> dict:
    m = j.get("match") or {}
    return {
        "id": j["_id"], "title": j["title"], "company": j["company"], "location": j.get("location"),
        "country": j.get("country"), "remote": j.get("remote"), "source": j.get("source"),
        "sources": sorted({s["source"] for s in j.get("sources", [])}),
        "salary_min": j.get("salary_min"), "salary_max": j.get("salary_max"),
        "currency": j.get("currency"), "experience_required": j.get("experience_required"),
        "status": j.get("status", "new"), "score": m.get("overall"),
        "classification": m.get("classification"), "posted_date": j.get("posted_date"),
        "created_at": j["created_at"].isoformat(),
    }


def job_detail(j: dict) -> dict:
    return {
        **job_summary(j),
        "employment_type": j.get("employment_type"), "description": j["description"],
        "requirements": j.get("requirements", []), "nice_to_have": j.get("nice_to_have", []),
        "skills": j.get("skills", []), "application_url": j.get("application_url"),
        "deadline": j.get("deadline"),
        "source_refs": [{k: s.get(k) for k in ("source", "source_job_id", "url", "first_seen")}
                        for s in j.get("sources", [])],
        "analysis": j.get("analysis"), "match": j.get("match"),
        "updated_at": j["updated_at"].isoformat(),
    }


async def list_jobs(db: AsyncIOMotorDatabase, user_id: str, *, status_: str | None,
                    classification: str | None, q: str | None, min_score: int | None,
                    sort: str, limit: int, offset: int) -> dict:
    query: dict = {"user_id": user_id}
    if status_:
        query["status"] = status_
    else:
        query["status"] = {"$nin": ["archived", "rejected"]}
    if classification:
        query["match.classification"] = classification
    if min_score is not None:
        query["match.overall"] = {"$gte": min_score}
    if q:
        rx = {"$regex": re.escape(q[:80]), "$options": "i"}
        query["$or"] = [{"title": rx}, {"company": rx}, {"location": rx}]
    order = [("match.overall", DESCENDING), ("created_at", DESCENDING)] if sort == "score" \
        else [("created_at", DESCENDING)]
    total = await db[c.JOBS].count_documents(query)
    docs = await db[c.JOBS].find(query).sort(order).skip(offset).limit(limit).to_list(length=limit)
    return {"total": total, "items": [job_summary(d) for d in docs]}
