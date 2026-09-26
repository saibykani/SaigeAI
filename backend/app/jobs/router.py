from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field
from pymongo import DESCENDING

from app.auth.deps import db_dep, get_current_user
from app.automation.service import is_allowed
from app.database import collections as c
from app.jobs import service, sources
from app.jobs.sources import SourceError
from app.profiles.service import get_profile
from app.schemas.job import ImportUrlIn, JobIn, JobSourceIn, JobStatusIn, MatchWeights
from app.services.agent_runs import agent_run
from app.services.audit import log_action
from app.services.rate_limit import RateLimiter
from app.utils import new_id, utcnow

router = APIRouter(prefix="/jobs", tags=["jobs"])
sync_limiter = RateLimiter(max_calls=10, window_seconds=60)
MAX_JOBS_PER_SYNC = 200


def _source_error(exc: SourceError) -> HTTPException:
    return HTTPException(exc.status, str(exc))


# ------------------------------------------------------------ import

@router.post("/import", status_code=201)
async def import_job(body: JobIn, user: dict = Depends(get_current_user),
                     db: AsyncIOMotorDatabase = Depends(db_dep)):
    """Import a job the user pasted (works for any site, including LinkedIn/Naukri postings)."""
    job, created = await service.ingest(db, user["_id"], body)
    return {"job": service.job_detail(job), "duplicate": not created}


@router.post("/import-url", status_code=201,
             dependencies=[Depends(sync_limiter.dependency("job_import_url"))])
async def import_job_url(body: ImportUrlIn, user: dict = Depends(get_current_user),
                         db: AsyncIOMotorDatabase = Depends(db_dep)):
    try:
        async with sources.http_client() as client:
            job_in = await sources.job_from_url(client, str(body.url))
    except SourceError as exc:
        raise _source_error(exc) from exc
    job, created = await service.ingest(db, user["_id"], job_in)
    return {"job": service.job_detail(job), "duplicate": not created}


# ------------------------------------------------------------ ATS board sources

def _source_out(s: dict) -> dict:
    return {"id": s["_id"], "provider": s["provider"], "board": s["board"],
            "company_name": s.get("company_name"), "last_synced_at": s.get("last_synced_at"),
            "last_result": s.get("last_result")}


@router.get("/sources")
async def list_sources(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    docs = await db[c.JOB_SOURCES].find({"user_id": user["_id"]}).to_list(length=200)
    return [_source_out(s) for s in docs]


@router.post("/sources", status_code=201)
async def add_source(body: JobSourceIn, user: dict = Depends(get_current_user),
                     db: AsyncIOMotorDatabase = Depends(db_dep)):
    if await db[c.JOB_SOURCES].find_one({"user_id": user["_id"], "provider": body.provider,
                                         "board": body.board.lower()}):
        raise HTTPException(status.HTTP_409_CONFLICT, "This job board is already added")
    doc = {"_id": new_id(), "user_id": user["_id"], "provider": body.provider,
           "board": body.board.lower(), "company_name": body.company_name, "created_at": utcnow()}
    await db[c.JOB_SOURCES].insert_one(doc)
    await log_action(db, user_id=user["_id"], action="job_source.added", entity="job_source",
                     entity_id=doc["_id"], details={"provider": body.provider, "board": doc["board"]})
    return _source_out(doc)


@router.delete("/sources/{source_id}", status_code=204)
async def delete_source(source_id: str, user: dict = Depends(get_current_user),
                        db: AsyncIOMotorDatabase = Depends(db_dep)):
    res = await db[c.JOB_SOURCES].delete_one({"_id": source_id, "user_id": user["_id"]})
    if not res.deleted_count:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Source not found")
    return Response(status_code=204)


@router.post("/sources/{source_id}/sync", dependencies=[Depends(sync_limiter.dependency("job_sync"))])
async def sync_source(source_id: str, user: dict = Depends(get_current_user),
                      db: AsyncIOMotorDatabase = Depends(db_dep)):
    uid = user["_id"]
    src = await db[c.JOB_SOURCES].find_one({"_id": source_id, "user_id": uid})
    if not src:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Source not found")
    if not await is_allowed(db, uid, "job_discovery"):
        raise HTTPException(status.HTTP_423_LOCKED,
                            "Job discovery is paused. Resume it in Automation settings.")

    try:
        return await run_board_sync(db, uid, src)
    except SourceError as exc:
        raise _source_error(exc) from exc


async def run_board_sync(db: AsyncIOMotorDatabase, uid: str, src: dict, trigger: str = "manual") -> dict:
    """Fetch one followed ATS board and ingest relevant postings. Raises SourceError on fetch failure."""
    source_id = src["_id"]
    async with agent_run(db, "job_discovery_agent", uid,
                         {"provider": src["provider"], "board": src["board"], "trigger": trigger}) as run:
        try:
            async with sources.http_client() as client:
                fetch = sources.BOARD_FETCHERS[src["provider"]]
                postings = await fetch(client, src["board"], src.get("company_name"))
        except SourceError as exc:
            run.errors.append(str(exc))
            await db[c.JOB_SOURCES].update_one({"_id": source_id}, {"$set": {
                "last_synced_at": utcnow().isoformat(), "last_result": {"error": str(exc)}}})
            raise

        profile = await get_profile(db, uid)
        weights = await service.get_weights(db, uid)
        # Filter by target role first, then cap, so relevant postings deep in a large board
        # are not lost to the per-sync limit.
        relevant = [p for p in postings if service.title_relevant(p.title, profile)]
        result = {"fetched": len(postings), "new": 0, "duplicates": 0,
                  "skipped_irrelevant": len(postings) - len(relevant),
                  "truncated": max(0, len(relevant) - MAX_JOBS_PER_SYNC)}
        for posting in relevant[:MAX_JOBS_PER_SYNC]:
            job, created = await service.ingest(db, uid, posting, profile=profile, weights=weights)
            result["new" if created else "duplicates"] += 1
            run.action(f"{'discovered' if created else 'merged'}: {job['title']} ({job['_id']})")
        run.output = result
    await db[c.JOB_SOURCES].update_one({"_id": source_id}, {"$set": {
        "last_synced_at": utcnow().isoformat(), "last_result": result}})
    return result


# ------------------------------------------------------------ discover (search official job APIs, then choose)

class DiscoverIn(BaseModel):
    query: str | None = Field(default=None, max_length=120)
    location: str | None = Field(default=None, max_length=120)


class DiscoverItem(BaseModel):
    source: str = Field(max_length=40)
    source_job_id: str | None = Field(default=None, max_length=200)
    title: str = Field(min_length=2, max_length=200)
    company: str = Field(default="", max_length=200)
    location: str | None = Field(default=None, max_length=200)
    remote: bool | None = None
    url: str | None = Field(default=None, max_length=2000)
    description: str = Field(default="", max_length=60000)
    salary_min: float | None = None
    salary_max: float | None = None


class DiscoverSaveIn(BaseModel):
    items: list[DiscoverItem] = Field(min_length=1, max_length=60)
    prepare_applications: bool = False


@router.post("/discover", dependencies=[Depends(sync_limiter.dependency("job_discover"))])
async def discover_jobs(body: DiscoverIn, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    from app.jobs import discover

    uid = user["_id"]
    if not await is_allowed(db, uid, "job_discovery"):
        raise HTTPException(status.HTTP_423_LOCKED, "Job discovery is paused. Resume it in Automation settings.")
    profile = await get_profile(db, uid)
    query = (body.query or "").strip() or ", ".join(profile.preferences.target_roles[:1]) or profile.personal.current_designation
    if not query:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Add a target role in your profile, or type what to search for.")
    location = (body.location or "").strip() or (profile.preferences.preferred_locations[0] if profile.preferences.preferred_locations else None)
    result = await discover.search(query, location, profile, await service.get_weights(db, uid))
    # Mark results already in your jobs list.
    urls = [r["url"] for r in result["results"] if r.get("url")]
    known = {}
    if urls:
        from app.jobs.dedupe import canonical_url
        keys = {canonical_url(u): u for u in urls}
        async for j in db[c.JOBS].find({"user_id": uid, "sources.url_key": {"$in": list(keys)}}, {"sources": 1}):
            for s_ in j.get("sources", []):
                if s_.get("url_key") in keys:
                    known[keys[s_["url_key"]]] = j["_id"]
    for r in result["results"]:
        r["saved_job_id"] = known.get(r.get("url"))
    return result


@router.post("/discover/save", status_code=201)
async def discover_save(body: DiscoverSaveIn, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    """Save the jobs the user picked; optionally prepare an application (resume + answers) for each."""
    from app.applications import service as apps
    from app.jobs import discover

    uid = user["_id"]
    profile = await get_profile(db, uid)
    weights = await service.get_weights(db, uid)
    saved, prepared, skipped = [], 0, 0
    for item in body.items:
        try:
            job_in = discover.to_job_in(item.model_dump())
        except ValueError:
            skipped += 1
            continue
        job, _ = await service.ingest(db, uid, job_in, profile=profile, weights=weights)
        saved.append(job["_id"])
        if body.prepare_applications:
            try:
                await apps.create(db, uid, job["_id"], None, None)
                prepared += 1
            except HTTPException:  # already has an application
                pass
    await log_action(db, user_id=uid, action="jobs.discover_saved", entity="job",
                     details={"saved": len(saved), "prepared": prepared})
    return {"saved": len(saved), "job_ids": saved, "applications_prepared": prepared, "skipped": skipped}


# ------------------------------------------------------------ matching config

@router.get("/matching/config", response_model=MatchWeights)
async def get_matching_config(user: dict = Depends(get_current_user),
                              db: AsyncIOMotorDatabase = Depends(db_dep)):
    return await service.get_weights(db, user["_id"])


@router.put("/matching/config", response_model=MatchWeights)
async def put_matching_config(body: MatchWeights, user: dict = Depends(get_current_user),
                              db: AsyncIOMotorDatabase = Depends(db_dep)):
    if sum(body.model_dump().values()) <= 0:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "At least one weight must be positive")
    return await service.save_weights(db, user["_id"], body)


@router.post("/rematch-all")
async def rematch_all(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    """Re-score every job - use after editing the profile or weights."""
    uid = user["_id"]
    profile = await get_profile(db, uid)
    weights = await service.get_weights(db, uid)
    async with agent_run(db, "matching_agent", uid, {"scope": "all"}) as run:
        n = 0
        async for job in db[c.JOBS].find({"user_id": uid, "status": {"$nin": ["archived", "rejected"]}}):
            await service.score_job(db, uid, job, profile, weights)
            n += 1
        run.output = {"rescored": n}
    return {"rescored": n}


# ------------------------------------------------------------ jobs

@router.get("")
async def list_jobs(
    status_: Literal["new", "saved", "shortlisted", "archived", "rejected"] | None = Query(
        None, alias="status"),
    classification: str | None = None, q: str | None = Query(None, max_length=80),
    min_score: int | None = Query(None, ge=0, le=100),
    sort: Literal["score", "recent"] = "score",
    limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep),
):
    return await service.list_jobs(db, user["_id"], status_=status_, classification=classification,
                                   q=q, min_score=min_score, sort=sort, limit=limit, offset=offset)


@router.get("/{job_id}")
async def get_job(job_id: str, user: dict = Depends(get_current_user),
                  db: AsyncIOMotorDatabase = Depends(db_dep)):
    job = await service.get_owned(db, user["_id"], job_id)
    return {**service.job_detail(job),
            "recommended_resume": await service.recommend_resume(db, user["_id"], job)}


@router.post("/{job_id}/match")
async def match_job(job_id: str, user: dict = Depends(get_current_user),
                    db: AsyncIOMotorDatabase = Depends(db_dep)):
    job = await service.get_owned(db, user["_id"], job_id)
    job = await service.score_job(db, user["_id"], job)
    return job["match"]


@router.post("/{job_id}/status")
async def set_status(job_id: str, body: JobStatusIn, user: dict = Depends(get_current_user),
                     db: AsyncIOMotorDatabase = Depends(db_dep)):
    job = await service.get_owned(db, user["_id"], job_id)
    await db[c.JOBS].update_one({"_id": job_id}, {"$set": {"status": body.status, "updated_at": utcnow()}})
    await log_action(db, user_id=user["_id"], action="job.status_changed", entity="job", entity_id=job_id,
                     details={"before": job.get("status"), "after": body.status})
    return service.job_summary(await service.get_owned(db, user["_id"], job_id))


@router.delete("/{job_id}", status_code=204)
async def delete_job(job_id: str, user: dict = Depends(get_current_user),
                     db: AsyncIOMotorDatabase = Depends(db_dep)):
    await service.get_owned(db, user["_id"], job_id)
    await db[c.JOBS].delete_one({"_id": job_id})
    await log_action(db, user_id=user["_id"], action="job.deleted", entity="job", entity_id=job_id)
    return Response(status_code=204)


agent_router = APIRouter(prefix="/automation", tags=["automation"])


@agent_router.get("/runs")
async def agent_runs(limit: int = Query(20, ge=1, le=100), user: dict = Depends(get_current_user),
                     db: AsyncIOMotorDatabase = Depends(db_dep)):
    docs = await db[c.AGENT_RUNS].find({"user_id": user["_id"]}).sort("start_time", DESCENDING).to_list(limit)
    return [{"id": d["_id"], "agent_name": d["agent_name"], "status": d["status"],
             "start_time": d["start_time"].isoformat(),
             "end_time": d["end_time"].isoformat() if d.get("end_time") else None,
             "duration_ms": d.get("duration_ms"), "output": d.get("output"),
             "errors": d.get("errors", []), "actions": d.get("actions", [])[:50]} for d in docs]
