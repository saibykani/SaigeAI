"""/api/careers: career-portal jobs (scan, filter, fit + resume advice, save, email digest, settings)."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.auth.deps import db_dep, get_current_user
from app.automation.service import AutomationSettings, CareerPortals, get_settings_doc, is_allowed
from app.automation.service import save as save_settings
from app.careers import catalog, digest, service
from app.services.rate_limit import RateLimiter

router = APIRouter(prefix="/careers", tags=["careers"])
scan_limiter = RateLimiter(6, 3600)  # manual scans per user per hour


class ScanIn(BaseModel):
    companies: list[str] = Field(default=[], max_length=200)  # empty: your selection


class DigestIn(BaseModel):
    test: bool = False


def _csv(v: str | None) -> list[str]:
    return [x.strip() for x in (v or "").split(",") if x.strip()][:100]


@router.post("/scan")
async def scan(body: ScanIn, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    uid = user["_id"]
    if not await is_allowed(db, uid, "job_discovery"):
        raise HTTPException(409, "Job discovery is paused in Automation settings.")
    if not scan_limiter.hit(f"careers:{uid}"):
        raise HTTPException(429, "You've scanned a lot this hour. Saige also scans every day on its own.")
    unknown = [i for i in body.companies if i not in catalog.BY_ID and ":" not in i]
    if unknown:
        raise HTTPException(422, f"Unknown company: {', '.join(unknown[:5])}")
    return service.scan_out(await service.scan(db, uid, trigger="manual", only=body.companies or None))


@router.get("/scan")
async def scan_status(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    from app.database import collections as c

    return service.scan_out(await db[c.CAREER_SCANS].find_one({"_id": user["_id"]}))


@router.get("/jobs")
async def list_jobs(
    q: str | None = Query(None, max_length=80), companies: str | None = None, tiers: str | None = None,
    countries: str | None = None, location: str | None = Query(None, max_length=60), scopes: str | None = None,
    fits: str | None = None, min_score: int = Query(0, ge=0, le=100), remote: bool = False,
    posted_days: int | None = Query(None, ge=1, le=365), new_days: int | None = Query(None, ge=1, le=90),
    max_exp: float | None = Query(None, ge=0, le=50), include_closed: bool = False,
    sort: Literal["score", "recent", "new", "company"] = "score",
    page: int = Query(1, ge=1, le=1000), page_size: int = Query(25, ge=5, le=100),
    user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep),
):
    f = {"q": q, "companies": _csv(companies), "tiers": _csv(tiers), "countries": _csv(countries), "location": location,
         "scopes": _csv(scopes), "fits": _csv(fits), "min_score": min_score, "remote": remote, "posted_days": posted_days,
         "new_days": new_days, "max_exp": max_exp, "include_closed": include_closed, "sort": sort, "page": page, "page_size": page_size}
    return await service.query(db, user["_id"], f)


@router.get("/jobs/{job_id}")
async def job_detail(job_id: str, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    return await service.detail(db, user["_id"], job_id)


@router.post("/jobs/{job_id}/save")
async def save_job(job_id: str, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    return await service.save(db, user["_id"], job_id)


@router.get("/portals")
async def portals(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    return await service.portals(db, user["_id"])


@router.get("/settings", response_model=CareerPortals)
async def get_careers_settings(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    return (await get_settings_doc(db, user["_id"])).careers


@router.put("/settings", response_model=CareerPortals)
async def put_careers_settings(body: CareerPortals, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    bad = [t for t in body.tiers if t not in catalog.TIERS] + [i for i in body.companies if i not in catalog.BY_ID]
    if bad:
        raise HTTPException(422, f"Unknown tier or company: {', '.join(bad[:5])}")
    current = await get_settings_doc(db, user["_id"])
    merged = AutomationSettings.model_validate({**current.model_dump(), "careers": body.model_dump()})
    await save_settings(db, user["_id"], merged, "careers.settings_updated", {"careers": body.model_dump()})
    return merged.careers


@router.post("/digest")
async def send_digest(body: DigestIn, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    return await digest.send(db, user["_id"], trigger="manual", test=body.test)


@router.post("/watch")
async def watch_tick(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    """Live watch tick from the open app (every 30 s): scans the next slice of portals and emails new matches."""
    from app.careers import watch

    return await watch.tick(db, user["_id"])
