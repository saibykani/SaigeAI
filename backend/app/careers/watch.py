"""Live watch: rescan company career portals every `careers.watch_seconds` (30 s minimum) and email new matches.

A full scan of every portal takes ~40 s, so each tick scans the next slice of `BATCH` companies (a rotating
cursor); the whole catalogue is covered every few ticks. Ticks come from `/api/cron/careers` (an external
pinger such as cron-job.org, every 30 s) and from the app's live tick while Saige is open. The email goes to
the user's own address only, holds only postings never emailed before, and nothing is sent when nothing is new.
"""

from datetime import timedelta

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.automation.service import get_settings_doc, is_allowed
from app.careers import digest
from app.careers import service as careers
from app.database import collections as c
from app.utils import as_utc, utcnow

BATCH = 30
BUDGET = 20.0


async def tick(db: AsyncIOMotorDatabase, uid: str, *, force: bool = False) -> dict:
    s = await get_settings_doc(db, uid)
    if not (s.careers.enabled and s.careers.watch) and not force:
        return {"skipped": "live watch off"}
    if not await is_allowed(db, uid, "job_discovery"):
        return {"skipped": "job discovery paused"}
    doc = await db[c.SYSTEM_SETTINGS].find_one({"user_id": uid}, {"careers_watch": 1}) or {}
    state = doc.get("careers_watch") or {}
    now = utcnow()
    if not force and state.get("last") and now - as_utc(state["last"]) < timedelta(seconds=s.careers.watch_seconds - 2):
        return {"skipped": "not due"}
    # Claim the tick first so overlapping pingers don't scan the same slice twice.
    pool = await careers.companies_for(db, uid, s)
    if not pool:
        return {"skipped": "no companies selected"}
    start = int(state.get("cursor", 0)) % len(pool)
    ids = [co.id for co in (pool + pool)[start:start + min(BATCH, len(pool))]]
    await db[c.SYSTEM_SETTINGS].update_one({"user_id": uid}, {"$set": {"careers_watch": {
        "last": now, "cursor": (start + len(ids)) % len(pool)}}}, upsert=True)
    report = await careers.scan(db, uid, trigger="watch", only=ids, budget=BUDGET)
    if report.get("status") == "needs_profile":
        return {"skipped": report["error"]}
    mail = await digest.send(db, uid, trigger="watch")
    return {"scanned": len(ids), "new": report.get("new", 0), "email": mail}


async def tick_all(db: AsyncIOMotorDatabase) -> list[dict]:
    out = []
    async for d in db[c.SYSTEM_SETTINGS].find({"automation.careers.watch": True}, {"user_id": 1}):
        try:
            out.append({"user": d["user_id"], **await tick(db, d["user_id"])})
        except Exception as exc:  # noqa: BLE001 - one user's failure must not stop the others
            out.append({"user": d["user_id"], "error": str(exc)[:200]})
    return out
