"""Metric definitions for the super admin console. Pure functions (lifecycle, health, ranges) plus the shared
aggregations every dashboard widget builds on. All numbers are computed from the database; nothing is sampled."""

import re
from datetime import date, datetime, timedelta

from fastapi import HTTPException, status

from app.database import collections as c
from app.utils import as_utc, utcnow

NOT_ADMIN_ACTION = re.compile(r"^superadmin\.")  # admin actions are not user activity
SENT_STATUSES = ("sent", "replied", "no_response", "bounced")
REPLY_APP = ("RECRUITER_REPLIED", "SCREENING", "ASSESSMENT", "INTERVIEW_SCHEDULED", "INTERVIEW_COMPLETED", "OFFER")
INTERVIEW_APP = ("INTERVIEW_SCHEDULED", "INTERVIEW_COMPLETED", "OFFER")
LIFECYCLE = ("new", "activated", "engaged", "at_risk", "churned")


# ---------------------------------------------------------------- pure definitions

def health_score(idle_days: float, events_30d: int, features_30d: int) -> int:
    """0-100: recency (40, linear over 30 idle days) + frequency (35, 30+ events in 30d = full) + breadth (25, 5+ features = full)."""
    return round(max(0.0, 1 - idle_days / 30) * 40 + min(events_30d, 30) / 30 * 35 + min(features_30d, 5) / 5 * 25)


def health_label(score: int) -> str:
    return "healthy" if score >= 70 else "fair" if score >= 40 else "low"


def lifecycle_stage(*, idle_days: float, activated: bool, events_30d: int, features_30d: int) -> str:
    """churned: no activity 30d+. at_risk: none for 14d+. new: not activated (no resume yet). engaged: 10+ events and 3+ features
    in 30d. activated: has a resume but lighter use."""
    if idle_days >= 30:
        return "churned"
    if idle_days >= 14:
        return "at_risk"
    if not activated:
        return "new"
    return "engaged" if events_30d >= 10 and features_30d >= 3 else "activated"


def pct(part: int | float, whole: int | float) -> float | None:
    return round(part / whole * 100, 1) if whole else None


def change_pct(value: float | None, previous: float | None) -> float | None:
    if value is None or not previous:
        return None
    return round((value - previous) / previous * 100, 1)


def feature_of(action: str) -> str:
    return (action or "").split(".")[0] or "other"


def day_list(start: datetime, end: datetime) -> list[date]:
    d, last, out = start.date(), (end - timedelta(microseconds=1)).date(), []
    while d <= last:
        out.append(d)
        d += timedelta(days=1)
    return out


def parse_range(days: int = 30, date_from: str = "", date_to: str = "") -> tuple[datetime, datetime]:
    """(start, end) with end exclusive. Custom dates are YYYY-MM-DD (inclusive); otherwise the last `days` days up to now."""
    now = utcnow()
    try:
        end = min(as_utc(datetime.fromisoformat(date_to)) + timedelta(days=1), now) if date_to else now
        start = as_utc(datetime.fromisoformat(date_from)) if date_from else end - timedelta(days=days)
    except ValueError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Dates must be YYYY-MM-DD") from None
    if start >= end or (end - start).days > 366:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Pick a range of 1 to 366 days")
    return start, end


def previous_range(start: datetime, end: datetime) -> tuple[datetime, datetime]:
    return start - (end - start), start


# ---------------------------------------------------------------- shared aggregations

async def user_days(db, start: datetime, end: datetime) -> set[tuple[str, date]]:
    """(user, day) pairs with any user activity: audit events (excluding admin actions) or agent runs."""
    out: set[tuple[str, date]] = set()
    for coll, field, extra in ((c.AUDIT_LOGS, "timestamp", {"action": {"$not": NOT_ADMIN_ACTION}}), (c.AGENT_RUNS, "start_time", {})):
        rows = await db[coll].aggregate([
            {"$match": {field: {"$gte": start, "$lt": end}, "user_id": {"$ne": None}, **extra}},
            {"$group": {"_id": {"u": "$user_id", "d": {"$dateToString": {"format": "%Y-%m-%d", "date": f"${field}"}}}}},
        ]).to_list(length=None)
        out |= {(r["_id"]["u"], date.fromisoformat(r["_id"]["d"])) for r in rows}
    return out


def active_users(ud: set[tuple[str, date]], first: date, last: date) -> set[str]:
    return {u for u, d in ud if first <= d <= last}


async def daily_counts(db, coll: str, field: str, match: dict, start: datetime, end: datetime) -> dict[date, int]:
    rows = await db[coll].aggregate([
        {"$match": {**match, field: {"$gte": start, "$lt": end}}},
        {"$group": {"_id": {"$dateToString": {"format": "%Y-%m-%d", "date": f"${field}"}}, "n": {"$sum": 1}}},
    ]).to_list(length=None)
    return {date.fromisoformat(r["_id"]): r["n"] for r in rows if r["_id"]}


async def distinct_users(db, coll: str, match: dict, within) -> set[str]:
    ids = list(within)
    if not ids:
        return set()
    return {u for u in await db[coll].distinct("user_id", {**match, "user_id": {"$in": ids}}) if u}


async def signup_cohort(db, start: datetime, end: datetime) -> dict[str, datetime]:
    rows = await db[c.USERS].find({"created_at": {"$gte": start, "$lt": end}}, {"created_at": 1}).to_list(length=None)
    return {r["_id"]: as_utc(r["created_at"]) for r in rows}


async def activated_ids(db, cohort: dict[str, datetime]) -> set[str]:
    """Signups who uploaded a resume within 7 days of signing up."""
    if not cohort:
        return set()
    rows = await db[c.RESUMES].aggregate([
        {"$match": {"user_id": {"$in": list(cohort)}}}, {"$group": {"_id": "$user_id", "first": {"$min": "$created_at"}}},
    ]).to_list(length=None)
    return {r["_id"] for r in rows if r.get("first") and as_utc(r["first"]) <= cohort[r["_id"]] + timedelta(days=7)}


async def funnel(db, start: datetime, end: datetime) -> list[dict]:
    """Furthest-stage funnel for users who signed up in [start, end): each stage counts users who reached it or any later stage."""
    cohort = set(await signup_cohort(db, start, end))

    async def apps_in(sts) -> set[str]:
        return await distinct_users(db, c.APPLICATIONS, {"status": {"$in": list(sts)}}, cohort)

    interview = await distinct_users(db, c.INTERVIEWS, {}, cohort) | await apps_in(INTERVIEW_APP)
    reply = interview | await distinct_users(db, c.OUTREACH, {"status": "replied"}, cohort) | await apps_in(REPLY_APP)
    application = reply | await distinct_users(db, c.APPLICATIONS, {}, cohort)
    saved = application | await distinct_users(db, c.JOBS, {}, cohort)
    resume = saved | await distinct_users(db, c.RESUMES, {}, cohort)
    stages = [("Signed up", cohort), ("Profile / resume", resume), ("First job saved", saved), ("First application", application),
              ("First reply", reply), ("Interview", interview)]
    base, prev, out = len(cohort), len(cohort), []
    for name, ids in stages:
        n = len(ids)
        out.append({"stage": name, "users": n, "pct_of_signups": pct(n, base), "pct_of_previous": pct(n, prev)})
        prev = n
    return out


async def cohorts(db, weeks: int) -> list[dict]:
    """Weekly signup cohorts (Mon-Sun, newest last). retention[k] = % of the cohort active in week k after signup (None = not reached)."""
    now = utcnow()
    this_monday = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    first = this_monday - timedelta(weeks=weeks - 1)
    users = await db[c.USERS].find({"created_at": {"$gte": first, "$lt": now}}, {"created_at": 1}).to_list(length=None)
    by_user: dict[str, set[date]] = {}
    for u, d in await user_days(db, first, now):
        by_user.setdefault(u, set()).add(d)
    out = []
    for i in range(weeks):
        cs = first + timedelta(weeks=i)
        ids = [u["_id"] for u in users if cs <= as_utc(u["created_at"]) < cs + timedelta(weeks=1)]
        row: dict = {"week": cs.date().isoformat(), "size": len(ids), "retention": []}
        for k in range(9):
            ws = cs + timedelta(weeks=k)
            if ws > now:
                row["retention"].append(None)
                continue
            days = {(ws + timedelta(days=j)).date() for j in range(7)}
            row["retention"].append(pct(sum(1 for u in ids if by_user.get(u, set()) & days), len(ids)))
        out.append(row)
    return out


async def user_rollup(db, now: datetime | None = None) -> dict[str, dict]:
    """Per-user counts for the CRM table, lifecycle and health: resumes, applications, emails sent, replies, 30d events + features,
    and the most recent activity (audit or agent run in the last 90 days)."""
    now = now or utcnow()
    d30, d90 = now - timedelta(days=30), now - timedelta(days=90)
    roll: dict[str, dict] = {}

    def row(uid: str) -> dict:
        return roll.setdefault(uid, {"resumes": 0, "applications": 0, "emails_sent": 0, "replies": 0, "events_30d": 0, "actions_30d": set(),
                                     "last_event": None})

    async def count(coll: str, match: dict, key: str):
        for r in await db[coll].aggregate([{"$match": match}, {"$group": {"_id": "$user_id", "n": {"$sum": 1}}}]).to_list(length=None):
            if r["_id"]:
                row(r["_id"])[key] += r["n"]

    await count(c.RESUMES, {}, "resumes")
    await count(c.APPLICATIONS, {}, "applications")
    await count(c.OUTREACH, {"status": {"$in": list(SENT_STATUSES)}}, "emails_sent")
    await count(c.OUTREACH, {"status": "replied"}, "replies")
    for coll, field, label in ((c.AUDIT_LOGS, "timestamp", "$action"), (c.AGENT_RUNS, "start_time", "$agent_name")):
        extra = {"action": {"$not": NOT_ADMIN_ACTION}} if coll == c.AUDIT_LOGS else {}
        rows = await db[coll].aggregate([
            {"$match": {field: {"$gte": d90}, "user_id": {"$ne": None}, **extra}},
            {"$group": {"_id": "$user_id", "last": {"$max": f"${field}"},
                        "recent": {"$push": {"$cond": [{"$gte": [f"${field}", d30]}, label, None]}}}},
        ]).to_list(length=None)
        for r in rows:
            x = row(r["_id"])
            acts = [a for a in r["recent"] if a]
            x["events_30d"] += len(acts)
            x["actions_30d"] |= {feature_of(a) if coll == c.AUDIT_LOGS else f"agent:{a}" for a in acts}
            if r["last"] and (x["last_event"] is None or as_utc(r["last"]) > x["last_event"]):
                x["last_event"] = as_utc(r["last"])
    return roll


def user_signals(u: dict, r: dict | None, now: datetime) -> dict:
    """Lifecycle + health for one user doc given its rollup row."""
    r = r or {}
    seen = [as_utc(t) for t in (u.get("last_active_at"), r.get("last_event")) if t]
    last_active = max(seen) if seen else None
    created = as_utc(u["created_at"]) if u.get("created_at") else now
    idle = (now - (last_active or created)).total_seconds() / 86400
    events, feats = r.get("events_30d", 0), len(r.get("actions_30d", ()))
    score = health_score(idle, events, feats)
    stage = lifecycle_stage(idle_days=idle, activated=r.get("resumes", 0) > 0, events_30d=events, features_30d=feats)
    return {"last_active": last_active, "idle_days": round(idle, 1), "events_30d": events, "features_30d": feats, "health": score,
            "health_label": health_label(score), "lifecycle": stage}
