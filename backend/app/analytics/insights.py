"""Company insights: the user's own reply and interview rates per company and per source.

Only applications the user actually sent (``applied_at`` set) count. An application is
- replied: it reached a status that needs a human on the other side (RESPONSE), or a linked email
  was classified as a recruiter reply, interview, assessment, rejection or offer;
- interviewed: an interview status, a linked Interview Invitation email or an interview record;
- ghosted: still waiting (APPLIED / RECRUITER_CONTACTED), no reply, and silent for GHOST_DAYS+ days
  (the same rule as /api/growth/ghosting).
Rates are None with no sent applications. Best / worst sources need MIN_SAMPLE sent applications.
"""

from collections import defaultdict
from datetime import timedelta
from statistics import median

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.analytics.service import INTERVIEW, RESPONSE, SOURCE_LABEL, rate
from app.database import collections as c
from app.growth.router import GHOST_DAYS, WAITING
from app.utils import as_utc, utcnow

MIN_SAMPLE = 3
REPLY_EMAILS = {"Recruiter Reply", "Interview Invitation", "Interview Reschedule", "Assessment", "Coding Test", "Rejection", "Offer"}
INTERVIEW_EMAILS = {"Interview Invitation", "Interview Reschedule"}


def _u(d):
    return as_utc(d) if d else None


async def _app_rows(db: AsyncIOMotorDatabase, uid: str, days: int | None) -> list[dict]:
    now = utcnow()
    query: dict = {"user_id": uid, "applied_at": {"$ne": None}}
    if days:
        query["applied_at"] = {"$gte": now - timedelta(days=days)}
    apps = await db[c.APPLICATIONS].find(query).to_list(5000)
    if not apps:
        return []
    ids = [a["_id"] for a in apps]
    reached: dict[str, dict] = defaultdict(dict)
    last_event: dict[str, object] = {}
    async for e in db[c.APPLICATION_EVENTS].find({"application_id": {"$in": ids}}).sort("at", 1):
        at = _u(e.get("at"))
        if e.get("to") and at:
            reached[e["application_id"]].setdefault(e["to"], at)
        if at:
            last_event[e["application_id"]] = at
    mails: dict[str, list[tuple[str, object]]] = defaultdict(list)
    async for m in db[c.EMAILS].find({"user_id": uid, "application_id": {"$in": ids}}, {"application_id": 1, "category": 1, "received_at": 1}):
        mails[m["application_id"]].append((m.get("category") or "", _u(m.get("received_at"))))
    interviews: dict[str, object] = {}
    async for i in db[c.INTERVIEWS].find({"user_id": uid, "application_id": {"$in": ids}}, {"application_id": 1, "created_at": 1}):
        interviews.setdefault(i["application_id"], _u(i.get("created_at")))
    jobs = {j["_id"]: j async for j in db[c.JOBS].find({"_id": {"$in": [a.get("job_id") for a in apps]}}, {"source": 1, "company": 1})}
    referred = {o["job_id"] async for o in db[c.OUTREACH].find(
        {"user_id": uid, "kind": "referral", "job_id": {"$ne": None}, "sent_at": {"$ne": None}}, {"job_id": 1})}

    rows = []
    for a in apps:
        aid, job = a["_id"], jobs.get(a.get("job_id"), {})
        seen = reached.get(aid, {})
        statuses = set(seen) | {a.get("status")}
        cats = {cat for cat, _ in mails.get(aid, [])}
        applied = _u(a["applied_at"])
        resp_times = [t for s, t in seen.items() if s in RESPONSE] + [t for cat, t in mails.get(aid, []) if cat in REPLY_EMAILS and t]
        first = min((t for t in resp_times if t >= applied), default=None)
        replied = bool(statuses & RESPONSE) or bool(cats & REPLY_EMAILS)
        activity = [t for t in (applied, _u(a.get("updated_at")), _u(a.get("last_contact_at")), last_event.get(aid)) if t]
        activity += [t for _, t in mails.get(aid, []) if t]
        last = max(activity)
        silent_from = _u(a.get("last_contact_at")) or applied
        source = "referral" if a.get("job_id") in referred else (job.get("source") or a.get("source") or "manual")
        rows.append({
            "company": (a.get("company") or job.get("company") or "Unknown").strip() or "Unknown",
            "source": SOURCE_LABEL.get(source, str(source).replace("_", " ").title()),
            "replied": replied,
            "interviewed": bool(statuses & INTERVIEW) or bool(cats & INTERVIEW_EMAILS) or aid in interviews,
            "offer": "OFFER" in statuses or "Offer" in cats,
            "rejected": "REJECTED" in statuses or "Rejection" in cats,
            "ghosted": a.get("status") in WAITING and not replied and (now - silent_from).days >= GHOST_DAYS,
            "response_days": (first - applied).total_seconds() / 86400 if first else None,
            "last_activity": last,
            "silent_days": (now - silent_from).days,
        })
    return rows


def _funnel(label: str, rows: list[dict]) -> dict:
    n = len(rows)
    replied = sum(r["replied"] for r in rows)
    interviews = sum(r["interviewed"] for r in rows)
    times = [r["response_days"] for r in rows if r["response_days"] is not None]
    return {"label": label, "applied": n, "replied": replied, "interviews": interviews,
            "offers": sum(r["offer"] for r in rows), "rejections": sum(r["rejected"] for r in rows),
            "ghosted": sum(r["ghosted"] for r in rows), "reply_rate": rate(replied, n), "interview_rate": rate(interviews, n),
            "median_response_days": round(median(times), 1) if times else None,
            "last_activity": max(r["last_activity"] for r in rows).isoformat()}


def company_tip(g: dict, rows: list[dict]) -> str:
    n, med = g["applied"], g["median_response_days"]
    if g["offers"]:
        return "Offer received here. Keep the conversation warm."
    if g["interviews"]:
        return f"{g['interviews']} interview(s) from {n} application(s). Prepare well for this company."
    if g["replied"] and med is not None and med <= 3:
        return f"Replies fast: median {med:g} days."
    if g["rejections"] and g["rejections"] == g["replied"]:
        return "Only rejections so far. Tailor the resume closer to their JDs before the next one."
    if not g["replied"]:
        silent = min(r["silent_days"] for r in rows)
        if silent >= GHOST_DAYS:
            return f"{n} application(s), no reply in {silent} days. Try a referral or a recruiter message."
        return f"{n} application(s), waiting {silent} day(s). Give it until day {GHOST_DAYS} before following up."
    return f"{g['replied']} of {n} got a reply" + (f", median {med:g} days." if med is not None else ".")


def _pick(groups: list[dict], key: str, best: bool) -> dict | None:
    pool = [g for g in groups if g["applied"] >= MIN_SAMPLE and g[key] is not None]
    if len(pool) < 2:
        return None
    pick = (max if best else min)(pool, key=lambda g: (g[key], g["applied"] if best else -g["applied"]))
    return {"label": pick["label"], key: pick[key], "applied": pick["applied"]}


async def insights_by(db: AsyncIOMotorDatabase, uid: str, days: int | None = None) -> dict:
    rows = await _app_rows(db, uid, days)
    by_co: dict[str, list[dict]] = defaultdict(list)
    by_src: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_co[r["company"]].append(r)
        by_src[r["source"]].append(r)

    out_q: dict = {"user_id": uid, "sent_at": {"$ne": None}}
    if days:
        out_q["sent_at"] = {"$gte": utcnow() - timedelta(days=days)}
    outreach: dict[str, dict] = defaultdict(lambda: {"sent": 0, "replied": 0})
    async for o in db[c.OUTREACH].find(out_q, {"company": 1, "status": 1, "replied_at": 1}):
        k = outreach[(o.get("company") or "Unknown").strip().lower()]
        k["sent"] += 1
        k["replied"] += o.get("status") == "replied" or bool(o.get("replied_at"))

    companies = []
    for name, grp in by_co.items():
        g = _funnel(name, grp)
        o = outreach.get(name.lower(), {"sent": 0, "replied": 0})
        g.update(outreach_sent=o["sent"], outreach_replied=o["replied"], tip=company_tip(g, grp))
        companies.append(g)
    companies.sort(key=lambda g: (-g["applied"], g["label"].lower()))
    sources = sorted((_funnel(k, v) for k, v in by_src.items()), key=lambda g: (-g["applied"], g["label"]))

    return {
        "days": days, "min_sample": MIN_SAMPLE,
        "overall": _funnel("All", rows) if rows else {"label": "All", "applied": 0, "replied": 0, "interviews": 0, "offers": 0,
                                                      "rejections": 0, "ghosted": 0, "reply_rate": None, "interview_rate": None,
                                                      "median_response_days": None, "last_activity": None},
        "companies": companies, "sources": sources,
        "best_source": _pick(sources, "reply_rate", True), "worst_source": _pick(sources, "reply_rate", False),
        "best_interview_source": _pick(sources, "interview_rate", True),
        "enough_data": len(rows) >= MIN_SAMPLE,
    }
