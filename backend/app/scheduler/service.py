"""Daily scheduler (spec sections 33-35, 55).

A cron call (Vercel Cron, or any external scheduler) hits `/api/cron/daily`; `run_due_jobs` walks
users in batches and runs each daily job that is due in the user's own timezone. Every job run is
claimed in `scheduler_jobs` under a deterministic id (user, job, local date), so repeated cron calls
never run a job twice on the same day.

Nothing here acts on LinkedIn or Naukri directly: the profile jobs prepare truthful, copy-ready
changes and notify the user, who applies them.
"""

import logging
from datetime import date, datetime, time, timedelta
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError

from app.automation.service import AutomationSettings, get_settings_doc, is_allowed
from app.database import collections as c
from app.services.agent_runs import agent_run
from app.services.notify import notify
from app.utils import utcnow

logger = logging.getLogger("saige.scheduler")

Job = Literal["profile_refresh", "naukri_freshness", "job_discovery", "gmail_sync", "followups", "morning_report"]
JOBS: tuple[str, ...] = ("profile_refresh", "naukri_freshness", "job_discovery", "gmail_sync", "followups",
                         "morning_report")
LABELS = {
    "profile_refresh": "LinkedIn & Naukri optimisation",
    "naukri_freshness": "Naukri daily freshness",
    "job_discovery": "Job board sync",
    "gmail_sync": "Gmail sync",
    "followups": "Follow-up check",
    "morning_report": "Morning report",
}


def user_tz(settings: AutomationSettings) -> ZoneInfo:
    try:
        return ZoneInfo(settings.schedules.timezone)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("Asia/Kolkata")


def _hhmm(value: str, default: str = "08:00") -> time:
    try:
        h, m = (int(x) for x in (value or default).split("-")[0].strip().split(":"))
        return time(h, m)
    except ValueError:
        return _hhmm(default) if value != default else time(8, 0)


def job_time(job: str, s: AutomationSettings) -> time:
    if job in ("profile_refresh", "naukri_freshness", "morning_report"):
        return _hhmm(s.profile_schedule.refresh_time)
    if job == "job_discovery":
        return _hhmm(s.schedules.job_discovery_time, "07:00")
    if job == "followups":
        return _hhmm(s.schedules.followup_time, "09:00")
    return time(0, 0)  # gmail_sync: any time of day


def is_due(job: str, s: AutomationSettings, local: datetime) -> bool:
    if s.paused_all:
        return False
    ps = s.profile_schedule
    if job in ("profile_refresh", "naukri_freshness") and local.weekday() not in ps.days:
        return False
    if job == "profile_refresh" and not (ps.linkedin_enabled or ps.naukri_enabled):
        return False
    if job == "naukri_freshness" and not (ps.naukri_enabled and ps.naukri_daily_freshness):
        return False
    return local.time() >= job_time(job, s)


def next_run(job: str, s: AutomationSettings, now: datetime) -> str | None:
    """Next local datetime (ISO) the job becomes due, for display."""
    tz = user_tz(s)
    local = now.astimezone(tz)
    at = job_time(job, s)
    for offset in range(8):
        day = local.date() + timedelta(days=offset)
        candidate = datetime.combine(day, at, tzinfo=tz)
        if candidate <= local:
            continue
        if job in ("profile_refresh", "naukri_freshness") and day.weekday() not in s.profile_schedule.days:
            continue
        return candidate.isoformat()
    return None


# ------------------------------------------------------------------ run records

async def _claim(db: AsyncIOMotorDatabase, user_id: str, job: str, run_date: date, trigger: str,
                 suffix: str = "") -> str | None:
    doc_id = f"{user_id}:{job}:{run_date.isoformat()}{suffix}"
    try:
        await db[c.SCHEDULER_JOBS].insert_one({
            "_id": doc_id, "user_id": user_id, "job": job, "run_date": run_date.isoformat(), "trigger": trigger,
            "status": "running", "started_at": utcnow(), "finished_at": None, "result": None,
        })
    except DuplicateKeyError:
        return None
    return doc_id


async def _finish(db: AsyncIOMotorDatabase, doc_id: str, status: str, result: dict[str, Any]) -> None:
    await db[c.SCHEDULER_JOBS].update_one({"_id": doc_id}, {"$set": {
        "status": status, "result": result, "finished_at": utcnow()}})


def run_out(d: dict) -> dict:
    return {
        "id": d["_id"], "job": d["job"], "label": LABELS.get(d["job"], d["job"]), "run_date": d["run_date"],
        "trigger": d.get("trigger", "cron"), "status": d["status"], "result": d.get("result") or {},
        "started_at": d["started_at"].isoformat() if d.get("started_at") else None,
        "finished_at": d["finished_at"].isoformat() if d.get("finished_at") else None,
    }


# ------------------------------------------------------------------ job runners

async def _profile_refresh(db: AsyncIOMotorDatabase, uid: str, s: AutomationSettings, trigger: str) -> dict:
    from app.profiles import sync_service

    if not await is_allowed(db, uid, "profile_updates"):
        return {"skipped": "profile updates paused"}
    platforms = tuple(p for p, on in (("linkedin", s.profile_schedule.linkedin_enabled),
                                      ("naukri", s.profile_schedule.naukri_enabled)) if on)
    if not platforms:
        return {"skipped": "no platform enabled"}
    async with agent_run(db, "profile_agent", uid, {"trigger": trigger, "platforms": list(platforms)}) as run:
        result = await sync_service.analyze(db, uid, platforms)
        created = sum((result.get(p) or {}).get("changes_created", 0) for p in platforms)
        run.output = {"jobs_analyzed": result["jobs_analyzed"], "changes_created": created}
        run.action(f"created {created} profile change(s)")
    if created:
        names = " & ".join({"linkedin": "LinkedIn", "naukri": "Naukri"}[p] for p in platforms)
        await notify(db, user_id=uid, kind="profile_optimization",
                     title=f"{names}: {created} new suggestion(s) ready",
                     body="Review, copy the approved text to the site, then mark it applied.", link="/profiles")
    return {"platforms": list(platforms), "jobs_analyzed": result["jobs_analyzed"], "changes_created": created}


async def _naukri_freshness(db: AsyncIOMotorDatabase, uid: str, today: date) -> dict:
    from app.profiles import optimizer as opt
    from app.profiles import sync_service
    from app.profiles.service import get_profile

    if not await is_allowed(db, uid, "profile_updates"):
        return {"skipped": "profile updates paused"}
    profile = await get_profile(db, uid)
    nk = await sync_service.get_snapshot(db, uid, "naukri")
    trends, jobs = await opt.skill_trends(db, uid, profile)
    pending = {d["field"] async for d in db[c.PROFILE_CHANGES].find(
        {"user_id": uid, "platform": "naukri", "approval_status": sync_service.PENDING}, {"field": 1})}
    edit = opt.naukri_freshness_edit(profile, nk, trends, today.toordinal(), frozenset(pending))
    if not edit:
        return {"created": 0, "note": "nothing new to suggest today"}
    created = await sync_service.upsert_changes(db, uid, "naukri", [edit], profile, [j["_id"] for j in jobs])
    if created:
        await notify(db, user_id=uid, kind="naukri_freshness", title="Your 2-minute Naukri refresh is ready",
                     body="One small truthful edit keeps your profile near the top of recruiter searches.",
                     link="/profiles?tab=naukri")
    return {"created": created, "field": edit["field"]}


async def _job_discovery(db: AsyncIOMotorDatabase, uid: str, trigger: str) -> dict:
    from app.jobs.router import run_board_sync
    from app.jobs.sources import SourceError

    if not await is_allowed(db, uid, "job_discovery"):
        return {"skipped": "job discovery paused"}
    totals = {"boards": 0, "new": 0, "errors": 0}
    async for src in db[c.JOB_SOURCES].find({"user_id": uid}):
        totals["boards"] += 1
        try:
            r = await run_board_sync(db, uid, src, trigger=trigger)
            totals["new"] += r.get("new", 0)
        except SourceError:
            totals["errors"] += 1
    if totals["new"]:
        await notify(db, user_id=uid, kind="job_discovery", title=f"{totals['new']} new job(s) found on followed boards",
                     link="/jobs")
    return totals


async def _gmail_sync(db: AsyncIOMotorDatabase, uid: str) -> dict:
    from fastapi import HTTPException

    from app.email.router import run_sync

    integ = await db[c.INTEGRATIONS].find_one({"user_id": uid, "provider": "gmail"})
    if not integ:
        return {"skipped": "Gmail not connected"}
    if not await is_allowed(db, uid, "gmail_sync"):
        return {"skipped": "Gmail sync paused"}
    try:
        return await run_sync(db, uid, integ)
    except HTTPException as exc:
        return {"error": str(exc.detail)}


async def _followups(db: AsyncIOMotorDatabase, uid: str, now: datetime) -> dict:
    due = await db[c.FOLLOWUPS].update_many(
        {"user_id": uid, "status": "scheduled", "due_at": {"$lte": now}}, {"$set": {"status": "due"}})
    n = await db[c.FOLLOWUPS].count_documents({"user_id": uid, "status": "due"})
    if due.modified_count:
        await notify(db, user_id=uid, kind="followup_due", title=f"{n} follow-up(s) due today",
                     body="A short, polite check-in keeps your application top of mind.", link="/applications")
    return {"newly_due": due.modified_count, "due": n}


async def _morning_report(db: AsyncIOMotorDatabase, uid: str, run_date: date) -> dict:
    runs = await db[c.SCHEDULER_JOBS].find(
        {"user_id": uid, "run_date": run_date.isoformat(), "job": {"$ne": "morning_report"}}).to_list(20)
    pending = await db[c.PROFILE_CHANGES].count_documents({"user_id": uid, "approval_status": "USER_APPROVAL_REQUIRED"})
    lines = []
    for r in runs:
        res = r.get("result") or {}
        if r["job"] == "profile_refresh" and res.get("changes_created"):
            lines.append(f"{res['changes_created']} profile suggestion(s)")
        elif r["job"] == "naukri_freshness" and res.get("created"):
            lines.append("Naukri refresh ready")
        elif r["job"] == "job_discovery" and res.get("new"):
            lines.append(f"{res['new']} new job(s)")
        elif r["job"] == "followups" and res.get("due"):
            lines.append(f"{res['due']} follow-up(s) due")
        elif r["job"] == "gmail_sync" and res.get("status_updates"):
            lines.append(f"{res['status_updates']} email update(s)")
    body = " · ".join(lines) if lines else "All quiet. Nothing needs you right now."
    if pending:
        body += f" · {pending} suggestion(s) waiting for review"
    await notify(db, user_id=uid, kind="morning_report", title="Your Saige morning report", body=body, link="/")
    return {"summary": body}


async def run_job(db: AsyncIOMotorDatabase, uid: str, job: str, s: AutomationSettings, now: datetime,
                  trigger: str) -> dict:
    today = now.astimezone(user_tz(s)).date()
    if job == "profile_refresh":
        return await _profile_refresh(db, uid, s, trigger)
    if job == "naukri_freshness":
        return await _naukri_freshness(db, uid, today)
    if job == "job_discovery":
        return await _job_discovery(db, uid, trigger)
    if job == "gmail_sync":
        return await _gmail_sync(db, uid)
    if job == "followups":
        return await _followups(db, uid, now)
    if job == "morning_report":
        return await _morning_report(db, uid, today)
    raise ValueError(f"unknown job {job}")


async def run_for_user(db: AsyncIOMotorDatabase, uid: str, now: datetime | None = None, *,
                       only: str | None = None, trigger: str = "cron") -> list[dict]:
    """Run every due job for one user (or just `only`, ignoring its time for manual runs)."""
    now = now or utcnow()
    s = await get_settings_doc(db, uid)
    local = now.astimezone(user_tz(s))
    results = []
    for job in ([only] if only else JOBS):
        if not only and not is_due(job, s, local):
            continue
        if only and s.paused_all:
            results.append({"job": job, "status": "skipped", "result": {"skipped": "all automation paused"}})
            continue
        # Cron runs claim the (user, job, day) slot; manual runs get their own record so the
        # scheduled run later that day still happens.
        suffix = f":manual:{int(now.timestamp() * 1000)}" if only else ""
        doc_id = await _claim(db, uid, job, local.date(), trigger, suffix)
        if doc_id is None:
            continue  # already ran today
        try:
            result = await run_job(db, uid, job, s, now, trigger)
            status = "skipped" if "skipped" in result else "failed" if "error" in result else "succeeded"
        except Exception as exc:  # noqa: BLE001 - one failing job must not stop the others
            logger.exception("scheduler job failed", extra={"job": job, "user_id": uid})
            result, status = {"error": f"{type(exc).__name__}: {exc}"}, "failed"
        await _finish(db, doc_id, status, result)
        results.append({"job": job, "status": status, "result": result})
    return results


async def run_due_jobs(db: AsyncIOMotorDatabase, now: datetime | None = None, *, after: str | None = None,
                       limit: int = 25) -> dict:
    """Process one batch of users (ordered by id, starting after `after`)."""
    now = now or utcnow()
    q: dict = {"_id": {"$gt": after}} if after else {}
    users = await db[c.USERS].find(q, {"_id": 1}).sort("_id", ASCENDING).to_list(limit)
    ran = 0
    for u in users:
        ran += len(await run_for_user(db, u["_id"], now))
    return {"users": len(users), "jobs_run": ran, "next_cursor": users[-1]["_id"] if len(users) == limit else None}


async def status(db: AsyncIOMotorDatabase, uid: str, now: datetime | None = None) -> dict:
    now = now or utcnow()
    s = await get_settings_doc(db, uid)
    last: dict[str, dict] = {}
    async for d in db[c.SCHEDULER_JOBS].find({"user_id": uid}).sort("started_at", DESCENDING).limit(60):
        last.setdefault(d["job"], run_out(d))
    return {
        "timezone": str(user_tz(s)),
        "paused_all": s.paused_all,
        "profile_schedule": s.profile_schedule.model_dump(),
        "jobs": [{"job": j, "label": LABELS[j], "next_run": next_run(j, s, now), "last_run": last.get(j)}
                 for j in JOBS],
        "naukri_streak": await naukri_streak(db, uid, s, now),
    }


async def naukri_streak(db: AsyncIOMotorDatabase, uid: str, s: AutomationSettings, now: datetime) -> int:
    """Consecutive local days (ending today or yesterday) on which a Naukri change was applied."""
    tz = user_tz(s)
    days = set()
    async for d in db[c.PROFILE_CHANGES].find(
            {"user_id": uid, "platform": "naukri", "applied_at": {"$ne": None}}, {"applied_at": 1}):
        at = d["applied_at"]
        if at.tzinfo is None:
            at = at.replace(tzinfo=ZoneInfo("UTC"))
        days.add(at.astimezone(tz).date())
    today = now.astimezone(tz).date()
    cur = today if today in days else today - timedelta(days=1)
    streak = 0
    while cur in days:
        streak += 1
        cur -= timedelta(days=1)
    return streak
