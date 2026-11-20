"""Career Wrapped aggregates. Every figure is a count of stored records; nothing is estimated."""

from collections import Counter
from datetime import UTC, date, datetime, timedelta

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.analytics.service import INTERVIEW, RESPONSE, rate
from app.database import collections as c
from app.utils import as_utc, utcnow

IST = timedelta(hours=5, minutes=30)
PERIOD_DAYS = {"all": None, "month": 30, "week": 7}


def ist_day(dt: datetime) -> date:
    return (as_utc(dt) + IST).date()


def longest_streak(days: set[date]) -> int:
    best = run = 0
    prev: date | None = None
    for d in sorted(days):
        run = run + 1 if prev and d - prev == timedelta(days=1) else 1
        best = max(best, run)
        prev = d
    return best


def personality(m: dict) -> dict:
    """First matching rule wins. The rule text is returned so the user can see why."""
    sent, span, streak = m["applications"], m["span_days"], m["longest_streak"]
    if sent == 0 and m["outreach_sent"] == 0:
        return {"label": "The Starter", "rule": "No applications or outreach yet in this period."}
    if m["offers"] >= 1:
        return {"label": "The Closer", "rule": f"You received {m['offers']} offer(s)."}
    if sent >= 10 and span <= 14:
        return {"label": "The Sprinter", "rule": f"{sent} applications within {span} days (10+ in 14 days or less)."}
    if streak >= 5:
        return {"label": "The Streaker", "rule": f"Active {streak} days in a row (5+ needed)."}
    if sent >= 5 and (m["reply_rate"] or 0) >= 30:
        return {"label": "The Magnet", "rule": f"{m['reply_rate']}% reply rate on {sent} applications (30%+ with 5+ sent)."}
    if m["outreach_sent"] >= 5 and m["outreach_sent"] >= sent:
        return {"label": "The Networker", "rule": f"{m['outreach_sent']} outreach messages, at least as many as applications."}
    if sent >= 10:
        return {"label": "The Marathoner", "rule": f"{sent} applications spread over {span} days."}
    return {"label": "The Explorer", "rule": f"{sent} application(s) so far (fewer than 10)."}


def _top(counter: Counter) -> list[dict]:
    return [{"name": k, "count": v} for k, v in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))[:5]]


async def build(db: AsyncIOMotorDatabase, uid: str, period: str) -> dict:
    days = PERIOD_DAYS[period]
    since = utcnow() - timedelta(days=days) if days else None

    def in_period(dt: datetime | None) -> bool:
        return dt is not None and (since is None or as_utc(dt) >= since)

    apps = await db[c.APPLICATIONS].find({"user_id": uid}).to_list(5000)
    ids = [a["_id"] for a in apps]
    reached: dict[str, set[str]] = {}
    if ids:
        async for e in db[c.APPLICATION_EVENTS].find({"application_id": {"$in": ids}, "to": {"$ne": None}}, {"application_id": 1, "to": 1}):
            reached.setdefault(e["application_id"], set()).add(e["to"])
    interview_apps = {i.get("application_id") async for i in db[c.INTERVIEWS].find({"user_id": uid}, {"application_id": 1})}
    job_ids = [a["job_id"] for a in apps if a.get("job_id")]
    jobs = {j["_id"]: j async for j in db[c.JOBS].find({"_id": {"$in": job_ids}}, {"match": 1})} if job_ids else {}

    sent = [a for a in apps if in_period(a.get("applied_at"))]
    activity: set[date] = set()
    per_day: Counter = Counter()
    responded = interviewed = offers = 0
    companies: Counter = Counter()
    skills: Counter = Counter()
    for a in sent:
        d = ist_day(a["applied_at"])
        activity.add(d)
        per_day[d] += 1
        st = reached.get(a["_id"], set()) | {a["status"]}
        responded += bool(st & RESPONSE)
        interviewed += bool(st & INTERVIEW) or a["_id"] in interview_apps
        offers += "OFFER" in st
        if a.get("company"):
            companies[a["company"].strip()] += 1
        for s in ((jobs.get(a.get("job_id")) or {}).get("match") or {}).get("matched_skills") or []:
            skills[s] += 1

    outreach = 0
    async for o in db[c.OUTREACH].find({"user_id": uid, "sent_at": {"$ne": None}}, {"sent_at": 1}):
        if in_period(o["sent_at"]):
            outreach += 1
            activity.add(ist_day(o["sent_at"]))
    resumes = 0
    async for r in db[c.RESUMES].find({"user_id": uid, "kind": {"$ne": "Master Resume"}}, {"created_at": 1}):
        if in_period(r.get("created_at")):
            resumes += 1
            activity.add(ist_day(r["created_at"]))

    busiest = None
    if per_day:
        d, n = min(per_day.items(), key=lambda kv: (-kv[1], kv[0]))
        busiest = {"date": d.isoformat(), "count": n}
    span = (max(per_day) - min(per_day)).days + 1 if per_day else 0
    m = {"applications": len(sent), "replies": responded, "interviews": interviewed, "offers": offers,
         "reply_rate": rate(responded, len(sent)), "busiest_day": busiest, "longest_streak": longest_streak(activity),
         "top_skills": _top(skills), "top_companies": _top(companies),
         "resumes_generated": resumes, "outreach_sent": outreach, "span_days": span}
    m["personality"] = personality(m)
    m["empty"] = not (len(sent) or outreach or resumes)
    m["period"] = period
    m["generated_at"] = datetime.now(UTC).isoformat()
    return m
