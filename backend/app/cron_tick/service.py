"""Frequent tick (/api/cron/tick, called every ~15 minutes by a free external scheduler).

Each call, inside a time budget: (1) refresh job sources (feed + a slice of career portals) for the users whose data is
the most overdue, (2) send the "best-fit roles" email to users whose `careers.alert_hours` interval has elapsed.
A lock document with an expiry makes overlapping calls safe, and per-user state (`system_settings.job_tick`) makes
repeated calls idempotent: nothing is refreshed before it is due, and a job is emailed only once.
"""

import asyncio
import logging
import time
from datetime import UTC, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from app.automation.service import AutomationSettings, get_settings_doc, is_allowed
from app.careers import digest
from app.careers import service as careers
from app.config import get_settings
from app.database import collections as c
from app.email import outbound
from app.jobs import feed
from app.profiles.service import get_profile
from app.radar import service as radar
from app.services.agent_runs import agent_run
from app.services.audit import log_action
from app.services.notify import notify
from app.utils import as_utc, utcnow

log = logging.getLogger(__name__)

BUDGET_S = 45.0
LOCK_TTL = timedelta(seconds=90)
INACTIVE_AFTER = timedelta(days=30)
REFRESH_EVERY = timedelta(minutes=30)   # a user's sources are refreshed at most this often
DIGEST_SLACK = timedelta(minutes=10)    # the tick runs every 15 min, so "every 4 h" fires at the first tick after 3 h 50 min
MAIL_BACKOFF = timedelta(minutes=30)
FEED_TIMEOUT = 15.0
SCAN_BUDGET = 15.0
SCAN_BATCH = 30
DIGEST_MAX = 10
SENT_KEYS_MAX = 2000
LOCK_ID = "tick"


# ---------- lock ----------

async def acquire_lock(db: AsyncIOMotorDatabase, now: datetime | None = None) -> str | None:
    """Returns an owner token when the lock was taken, None when another call holds it (and it hasn't expired)."""
    now = now or utcnow()
    token = uuid4().hex
    fields = {"owner": token, "acquired_at": now, "expires_at": now + LOCK_TTL}
    res = await db[c.CRON_LOCKS].update_one({"_id": LOCK_ID, "expires_at": {"$lte": now}}, {"$set": fields})
    if res.matched_count:
        return token
    try:
        await db[c.CRON_LOCKS].insert_one({"_id": LOCK_ID, **fields})
        return token
    except DuplicateKeyError:
        return None


async def release_lock(db: AsyncIOMotorDatabase, token: str) -> None:
    await db[c.CRON_LOCKS].update_one({"_id": LOCK_ID, "owner": token}, {"$set": {"expires_at": datetime(1970, 1, 1, tzinfo=UTC)}})


# ---------- due logic ----------

def in_quiet_hours(now: datetime, tz: str, start: str, end: str) -> bool:
    """True when local time is inside [start, end); the window may wrap midnight (22:00-07:00)."""
    try:
        zone = ZoneInfo(tz)
    except Exception:  # noqa: BLE001 - unknown timezone: fall back to India time
        zone = ZoneInfo("Asia/Kolkata")
    cur = as_utc(now).astimezone(zone).strftime("%H:%M")
    if start == end:
        return False
    return start <= cur < end if start < end else (cur >= start or cur < end)


def digest_due(s: AutomationSettings, last_sent: datetime | None, now: datetime) -> bool:
    hours = s.careers.alert_hours
    if hours <= 0:
        return False
    if in_quiet_hours(now, s.schedules.timezone, s.careers.quiet_start, s.careers.quiet_end):
        return False
    return last_sent is None or now - as_utc(last_sent) >= timedelta(hours=hours) - DIGEST_SLACK


def refresh_due(last: datetime | None, now: datetime) -> bool:
    return last is None or now - as_utc(last) >= REFRESH_EVERY


async def _active_users(db: AsyncIOMotorDatabase, now: datetime) -> list[dict]:
    """Active users (signed in within 30 days) with their tick state, most overdue for a refresh first."""
    since = now - INACTIVE_AFTER
    users = await db[c.USERS].find({"is_active": {"$ne": False}, "last_active_at": {"$gte": since}}, {"email": 1}).to_list(1000)
    ids = [u["_id"] for u in users]
    states = {d["user_id"]: d.get("job_tick") or {}
              async for d in db[c.SYSTEM_SETTINGS].find({"user_id": {"$in": ids}}, {"user_id": 1, "job_tick": 1})}
    rows = [{"uid": u["_id"], "state": states.get(u["_id"], {})} for u in users]
    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    rows.sort(key=lambda r: as_utc(r["state"]["refreshed_at"]) if r["state"].get("refreshed_at") else epoch)
    return rows


async def _set_state(db: AsyncIOMotorDatabase, uid: str, fields: dict) -> None:
    await db[c.SYSTEM_SETTINGS].update_one({"user_id": uid}, {"$set": {f"job_tick.{k}": v for k, v in fields.items()}}, upsert=True)


# ---------- refresh ----------

async def refresh_user(db: AsyncIOMotorDatabase, uid: str, state: dict, now: datetime, budget: float) -> dict:
    s = await get_settings_doc(db, uid)
    if s.paused_all or not await is_allowed(db, uid, "job_discovery"):
        return {"skipped": "job discovery paused"}
    await _set_state(db, uid, {"refreshed_at": now})  # claim first: an overlapping call must not refresh the same user again
    out: dict = {}
    async with agent_run(db, "job_refresh_tick", uid, {"trigger": "cron_tick"}) as run:
        started = time.monotonic()
        try:
            built = await asyncio.wait_for(feed.build(db, uid), timeout=min(FEED_TIMEOUT, max(budget, 1.0)))
            out["feed"] = len(built.get("items", []))
        except TimeoutError:
            run.errors.append("feed refresh timed out")
            out["feed"] = "timeout"
        except Exception as exc:  # noqa: BLE001 - one source failing must not stop the rest
            run.errors.append(f"feed: {str(exc)[:150]}")
            out["feed"] = "error"
        remaining = budget - (time.monotonic() - started)
        if s.careers.enabled and remaining > 4:
            pool = await careers.companies_for(db, uid, s)
            if pool:
                start = int(state.get("cursor", 0)) % len(pool)
                ids = [co.id for co in (pool + pool)[start:start + min(SCAN_BATCH, len(pool))]]
                await _set_state(db, uid, {"cursor": (start + len(ids)) % len(pool)})
                try:
                    rep = await careers.scan(db, uid, trigger="watch", only=ids, budget=min(SCAN_BUDGET, remaining))
                    out["careers"] = {"scanned": len(ids), "new": rep.get("new", 0)}
                except Exception as exc:  # noqa: BLE001
                    run.errors.append(f"careers: {str(exc)[:150]}")
                    out["careers"] = "error"
        run.output = out
    return out


# ---------- digest ----------

async def _mark_sent(db: AsyncIOMotorDatabase, uid: str, rows: list[dict], now: datetime) -> None:
    doc = await db[c.SYSTEM_SETTINGS].find_one({"user_id": uid}, {"job_tick": 1}) or {}
    keys = ((doc.get("job_tick") or {}).get("sent_keys") or []) + [radar._key(r) for r in rows]
    await _set_state(db, uid, {"digest_at": now, "sent_keys": keys[-SENT_KEYS_MAX:], "retry_after": None})
    career_ids = [r["id"] for r in rows if r.get("origin") == "careers"]
    if career_ids:  # the career-portal digest must not email the same posting again
        await db[c.CAREER_JOBS].update_many({"_id": {"$in": career_ids}, "user_id": uid}, {"$set": {"emailed_at": now}})


async def send_digest(db: AsyncIOMotorDatabase, uid: str, state: dict, now: datetime) -> dict:
    """Email the best new roles (feed + career portals, never emailed before). Skips when nothing is new."""
    from app.email.gmail import GmailError

    s = await get_settings_doc(db, uid)
    if not await is_allowed(db, uid, "emails"):
        return {"skipped": "emails paused"}
    if state.get("retry_after") and as_utc(state["retry_after"]) > now:
        return {"skipped": "waiting after a mail error"}
    sent = set(state.get("sent_keys") or [])
    top = (await radar.radar(db, uid, top=radar.MAX_TOP))["items"]
    fresh = [r for r in top if r["score"] >= s.careers.min_score and radar._key(r) not in sent][:DIGEST_MAX]
    if not fresh:
        return {"sent": 0, "reason": "nothing new"}
    user = await db[c.USERS].find_one({"_id": uid}, {"email": 1}) or {}
    to = (s.careers.digest_to or user.get("email") or "").strip()
    profile = await get_profile(db, uid)
    subject, text, body_html = digest.render(fresh, careers.roles_for(profile, s), get_settings().frontend_url.rstrip("/"))
    subject = "Your best-fit roles: " + subject
    async with agent_run(db, "job_alert_digest", uid, {"trigger": "cron_tick", "candidates": len(fresh)}) as run:
        integ = await outbound.find_digest_sender(db, uid)
        if not integ or not digest.EMAIL_RE.match(to):
            await notify(db, user_id=uid, kind="job_radar", title=f"{len(fresh)} new best-fit roles", link="/radar",
                         body="Connect Gmail with an App Password in Integrations to also get this by email.",
                         details=[{"platform": d["company"], "field": d["title"], "after": f"{d['score']}%"} for d in fresh[:5]])
            run.action("notified in app (no sender connected)")
            await _mark_sent(db, uid, fresh, now)
            return {"sent": 0, "notified": len(fresh)}
        try:
            mid = await outbound.send(integ, integ.get("from_name") or "Saige AI", to, subject, text, html=body_html)
        except GmailError as exc:
            run.errors.append(str(exc)[:200])
            await _set_state(db, uid, {"retry_after": now + MAIL_BACKOFF})
            return {"sent": 0, "error": str(exc)[:200]}
        run.action(f"emailed {len(fresh)} best-fit roles")
        run.output = {"jobs": len(fresh)}
        await _mark_sent(db, uid, fresh, now)
        await log_action(db, user_id=uid, action="job_alerts.digest_sent", entity="job_radar",
                         details={"to": to, "jobs": len(fresh), "trigger": "cron_tick", "message_id": mid})
    return {"sent": len(fresh), "to": to}


# ---------- the tick ----------

async def run_tick(db: AsyncIOMotorDatabase, budget: float = BUDGET_S) -> dict:
    start = time.monotonic()
    now = utcnow()
    token = await acquire_lock(db, now)
    if not token:
        return {"skipped": "another tick is running"}
    out: dict = {"refreshed": 0, "digests_sent": 0, "digests_checked": 0, "errors": 0}
    try:
        rows = await _active_users(db, now)
        refresh_deadline = budget * 0.65
        for r in rows:
            elapsed = time.monotonic() - start
            if elapsed >= refresh_deadline:
                break
            if not refresh_due(r["state"].get("refreshed_at"), now):
                break  # sorted by overdue: everyone after this one is fresher
            try:
                res = await refresh_user(db, r["uid"], r["state"], now, refresh_deadline - elapsed)
                if "skipped" not in res:
                    out["refreshed"] += 1
            except Exception:  # noqa: BLE001 - one user's failure must not stop the others
                out["errors"] += 1
                log.warning("tick refresh failed for %s", r["uid"], exc_info=True)
        for r in rows:
            if time.monotonic() - start >= budget:
                break
            try:
                s = await get_settings_doc(db, r["uid"])
                if s.paused_all or not digest_due(s, r["state"].get("digest_at"), now):
                    continue
                out["digests_checked"] += 1
                res = await send_digest(db, r["uid"], r["state"], now)
                if res.get("sent") or res.get("notified"):
                    out["digests_sent"] += 1
            except Exception:  # noqa: BLE001
                out["errors"] += 1
                log.warning("tick digest failed for %s", r["uid"], exc_info=True)
        out["users"] = len(rows)
        out["elapsed_s"] = round(time.monotonic() - start, 1)
        return out
    finally:
        await release_lock(db, token)
