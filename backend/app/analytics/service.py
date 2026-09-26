"""Pipeline analytics (spec sections 34, 52): which sources, roles, resumes and messages work.

Every figure is a count or ratio of stored records. Rates are None when nothing was sent, never a
guess. An application "responded" once it reached any stage that needs a human on the other side
(a reply, screening, assessment, interview, offer or rejection).
"""

import re
from collections import defaultdict
from datetime import datetime, timedelta

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database import collections as c
from app.utils import as_utc, utcnow

RESPONSE = {"RECRUITER_REPLIED", "SCREENING", "ASSESSMENT", "INTERVIEW_SCHEDULED", "INTERVIEW_COMPLETED", "OFFER", "REJECTED"}
INTERVIEW = {"INTERVIEW_SCHEDULED", "INTERVIEW_COMPLETED", "OFFER"}
SOURCE_LABEL = {"manual": "Pasted", "capture": "Browser capture", "greenhouse": "Greenhouse", "lever": "Lever",
                "ashby": "Ashby", "url": "Job link", "referral": "Referral"}
MATCH_BUCKETS = [(85, "85%+"), (75, "75–84%"), (60, "60–74%"), (0, "Under 60%")]
RESPONSE_BUCKETS = [(2, "0–2 days"), (7, "3–7 days"), (14, "8–14 days"), (10_000, "15+ days")]


def role_family(title: str) -> str:
    t = title.lower()
    if re.search(r"perf|load|jmeter", t):
        return "Performance"
    if re.search(r"sdet|automation|\bset\b", t):
        return "SDET / Automation"
    if re.search(r"\bqa\b|quality|test", t):
        return "QA / Testing"
    if re.search(r"developer|engineer|software|backend|frontend", t):
        return "Engineering"
    return "Other"


def rate(part: int, whole: int) -> int | None:
    return round(100 * part / whole) if whole else None


def metrics(rows: list[dict]) -> dict:
    sent = [r for r in rows if r["sent"]]
    responses = sum(1 for r in sent if r["responded"])
    interviews = sum(1 for r in sent if r["interviewed"])
    offers = sum(1 for r in sent if r["offer"])
    return {"applications": len(rows), "sent": len(sent), "responses": responses, "interviews": interviews,
            "offers": offers, "response_rate": rate(responses, len(sent)), "interview_rate": rate(interviews, len(sent)),
            "offer_rate": rate(offers, len(sent))}


def grouped(rows: list[dict], key: str) -> list[dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        groups[r[key]].append(r)
    out = [{"label": k, **metrics(v)} for k, v in groups.items()]
    return sorted(out, key=lambda g: (-g["sent"], -g["applications"], g["label"]))


def week_start(dt: datetime) -> datetime:
    d = as_utc(dt)
    return (d - timedelta(days=d.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)


async def _rows(db: AsyncIOMotorDatabase, uid: str) -> list[dict]:
    apps = await db[c.APPLICATIONS].find({"user_id": uid}).to_list(5000)
    if not apps:
        return []
    ids = [a["_id"] for a in apps]
    reached: dict[str, dict[str, datetime]] = defaultdict(dict)  # app -> status -> first time reached
    async for e in db[c.APPLICATION_EVENTS].find({"application_id": {"$in": ids}, "to": {"$ne": None}}).sort("at", 1):
        reached[e["application_id"]].setdefault(e["to"], as_utc(e["at"]))
    job_ids = [a["job_id"] for a in apps if a.get("job_id")]
    jobs = {j["_id"]: j async for j in db[c.JOBS].find({"_id": {"$in": job_ids}}, {"source": 1, "title": 1})}
    resume_ids = [a["resume_id"] for a in apps if a.get("resume_id")]
    resumes = {r["_id"]: r async for r in db[c.RESUMES].find({"_id": {"$in": resume_ids}}, {"name": 1, "kind": 1})}
    referred = {o["job_id"] async for o in db[c.OUTREACH].find(
        {"user_id": uid, "kind": "referral", "job_id": {"$ne": None}, "sent_at": {"$ne": None}}, {"job_id": 1})}
    interview_apps = {i.get("application_id") async for i in db[c.INTERVIEWS].find({"user_id": uid}, {"application_id": 1})}

    rows = []
    for a in apps:
        seen = reached.get(a["_id"], {})
        statuses = set(seen) | {a["status"]}
        first_response = min((t for s, t in seen.items() if s in RESPONSE), default=None)
        source = "referral" if a.get("job_id") in referred else (jobs.get(a.get("job_id"), {}).get("source") or a.get("source") or "manual")
        resume = resumes.get(a.get("resume_id"))
        applied = as_utc(a["applied_at"]) if a.get("applied_at") else None
        rows.append({
            "sent": applied is not None,
            "applied_at": applied,
            "responded": bool(statuses & RESPONSE),
            "interviewed": bool(statuses & INTERVIEW) or a["_id"] in interview_apps,
            "offer": "OFFER" in statuses,
            "offer_at": seen.get("OFFER"),
            "first_response_at": first_response,
            "source": SOURCE_LABEL.get(source, source.title()),
            "family": role_family(a["role"]),
            "resume": (resume["name"] if resume else "No resume attached"),
            "resume_kind": (resume or {}).get("kind"),
            "match": a.get("match_score"),
        })
    return rows


async def breakdowns(db: AsyncIOMotorDatabase, uid: str, weeks: int = 8) -> dict:
    rows = await _rows(db, uid)
    now = utcnow()

    # Weekly activity (applications sent, interviews scheduled, offers) for the last `weeks` weeks.
    start = week_start(now) - timedelta(weeks=weeks - 1)
    buckets = [start + timedelta(weeks=i) for i in range(weeks)]
    weekly = {b: {"applied": 0, "responses": 0, "interviews": 0, "offers": 0} for b in buckets}
    for r in rows:
        for key, at in (("applied", r["applied_at"]), ("responses", r["first_response_at"]), ("offers", r["offer_at"])):
            if at and at >= start:
                weekly[week_start(at)][key] += 1
    async for i in db[c.INTERVIEWS].find({"user_id": uid, "scheduled_at": {"$gte": start}}, {"scheduled_at": 1}):
        wk = week_start(i["scheduled_at"])
        if wk in weekly:
            weekly[wk]["interviews"] += 1

    # Days from applying to the first human response.
    ttr = {label: 0 for _, label in RESPONSE_BUCKETS}
    for r in rows:
        if r["applied_at"] and r["first_response_at"] and r["first_response_at"] >= r["applied_at"]:
            days = (r["first_response_at"] - r["applied_at"]).days
            label = next(lbl for limit, lbl in RESPONSE_BUCKETS if days <= limit)
            ttr[label] += 1

    # Match score against outcome: does a higher score actually lead to interviews?
    for r in rows:
        m = r["match"]
        r["match_bucket"] = "No score" if m is None else next(lbl for floor, lbl in MATCH_BUCKETS if m >= floor)
    order = [lbl for _, lbl in MATCH_BUCKETS] + ["No score"]
    by_match = sorted(grouped(rows, "match_bucket"), key=lambda g: order.index(g["label"]))

    outreach: dict[str, dict] = {}
    async for o in db[c.OUTREACH].find({"user_id": uid, "sent_at": {"$ne": None}}, {"kind": 1, "status": 1}):
        k = outreach.setdefault(o["kind"], {"kind": o["kind"], "sent": 0, "replied": 0})
        k["sent"] += 1
        k["replied"] += o["status"] == "replied"
    for k in outreach.values():
        k["reply_rate"] = rate(k["replied"], k["sent"])

    return {
        "overall": metrics(rows),
        "by_source": grouped(rows, "source"),
        "by_role_family": grouped(rows, "family"),
        "by_resume": grouped(rows, "resume"),
        "by_match": by_match,
        "weekly": [{"week": b.date().isoformat(), **weekly[b]} for b in buckets],
        "time_to_response": [{"bucket": k, "count": v} for k, v in ttr.items()],
        "outreach": sorted(outreach.values(), key=lambda k: -k["sent"]),
    }
