import hmac
import time

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import DESCENDING

from app.auth.deps import db_dep, get_current_user
from app.config import get_settings
from app.database import collections as c
from app.scheduler import service
from app.scheduler.service import Job
from app.services.rate_limit import RateLimiter

router = APIRouter(tags=["scheduler"])
run_now_limiter = RateLimiter(max_calls=6, window_seconds=60)

CRON_TIME_BUDGET_S = 50  # Vercel functions are cut off at 60 s on Hobby


def _check_cron_auth(authorization: str | None) -> None:
    secret = get_settings().cron_secret
    if not secret:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "CRON_SECRET is not configured")
    if not authorization or not hmac.compare_digest(authorization, f"Bearer {secret}"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid cron credentials")


@router.get("/cron/daily")
async def cron_daily(authorization: str | None = Header(default=None), cursor: str | None = None,
                     db: AsyncIOMotorDatabase = Depends(db_dep)):
    """Called by Vercel Cron (it sends `Authorization: Bearer $CRON_SECRET`) or any external cron."""
    _check_cron_auth(authorization)
    start = time.monotonic()
    users = jobs = 0
    while True:
        batch = await service.run_due_jobs(db, after=cursor)
        users += batch["users"]
        jobs += batch["jobs_run"]
        cursor = batch["next_cursor"]
        if cursor is None or time.monotonic() - start > CRON_TIME_BUDGET_S:
            break
    # A non-null cursor means time ran out: call again with ?cursor=... to continue.
    return {"users": users, "jobs_run": jobs, "next_cursor": cursor}


@router.post("/live/tick")
async def live_tick(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    """Called every minute while Saige is open: syncs Gmail (portal alerts, invites, recruiter mail) when the
    last sync is a minute old, and refreshes Jobs for you when it is over 5 minutes old."""
    from datetime import timedelta

    from app.automation.service import is_allowed
    from app.email.router import run_sync
    from app.jobs import feed
    from app.utils import as_utc, utcnow

    uid, now, out = user["_id"], utcnow(), {"gmail": None, "feed": None}
    integ = await db[c.INTEGRATIONS].find_one({"user_id": uid, "provider": "gmail"})
    if integ and await is_allowed(db, uid, "gmail_sync") and (
            not integ.get("last_sync_at") or now - as_utc(integ["last_sync_at"]) > timedelta(seconds=55)):
        try:
            r = await run_sync(db, uid, integ)
            out["gmail"] = {"fetched": r.get("fetched", 0), "alert_jobs": r.get("alert_jobs", 0)}
        except Exception as exc:  # noqa: BLE001 - a failed background sync is reported, not raised
            out["gmail"] = {"error": str(exc)[:200]}
    doc = await db[c.JOB_FEED].find_one({"_id": uid}, {"built_at": 1})
    if await is_allowed(db, uid, "job_discovery") and (not doc or now - as_utc(doc["built_at"]) > feed.FEED_TTL):
        try:
            built = await feed.build(db, uid)
            out["feed"] = {"jobs": len(built.get("items", []))}
        except Exception as exc:  # noqa: BLE001
            out["feed"] = {"error": str(exc)[:200]}
    return out


@router.get("/scheduler/status")
async def scheduler_status(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    return await service.status(db, user["_id"])


@router.get("/scheduler/history")
async def scheduler_history(limit: int = Query(30, ge=1, le=100), user: dict = Depends(get_current_user),
                            db: AsyncIOMotorDatabase = Depends(db_dep)):
    from app.profiles.sync_service import change_states

    docs = await db[c.SCHEDULER_JOBS].find({"user_id": user["_id"]}).sort("started_at", DESCENDING).to_list(limit)
    out = []
    for d in docs:
        row = service.run_out(d)
        changes = (row["result"] or {}).get("changes")
        if row["job"] in ("profile_refresh", "naukri_freshness") and changes:
            # Saige can't edit LinkedIn / Naukri itself: show whether each edit is really on the site yet.
            states = await change_states(db, user["_id"], changes)
            row["result"] = {**row["result"], "changes": states}
            row["applied"] = sum(x["state"] == "applied" for x in states)
            row["waiting"] = sum(x["state"] == "waiting" for x in states)
        out.append(row)
    return out


@router.post("/scheduler/run-now/{job}")
async def run_now(job: Job, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    if not run_now_limiter.hit(f"run_now:{user['_id']}"):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many manual runs. Try again in a minute.")
    results = await service.run_for_user(db, user["_id"], only=job, trigger="manual")
    return results[0]
