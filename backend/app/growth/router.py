"""Career growth (/api/growth): ghosting alerts, weekly goals, salary insight and role suggestions.

Everything is computed from the user's own records and public job postings Saige already fetched.
Glassdoor and AmbitionBox have no public API and forbid scraping, so salary pages there are offered
as links the user opens; the numbers Saige shows come only from postings that list a salary."""

import re
from collections import Counter
from datetime import timedelta
from statistics import median
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.auth.deps import db_dep, get_current_user
from app.database import collections as c
from app.jobs.discover import title_matches
from app.profiles.service import get_profile
from app.services.audit import log_action
from app.services.notify import notify
from app.utils import utcnow

router = APIRouter(prefix="/growth", tags=["growth"])

GHOST_DAYS = 10
WAITING = ("APPLIED", "RECRUITER_CONTACTED")


def _naive(d):
    return d.replace(tzinfo=None) if d else None


# ------------------------------------------------------------------ ghosting


async def ghosted(db: AsyncIOMotorDatabase, uid: str, days: int = GHOST_DAYS) -> list[dict]:
    now = _naive(utcnow())
    out = []
    async for a in db[c.APPLICATIONS].find({"user_id": uid, "status": {"$in": list(WAITING)}}):
        last = _naive(a.get("last_contact_at") or a.get("applied_at") or a.get("updated_at"))
        if not last or (now - last).days < days:
            continue
        job = await db[c.JOBS].find_one({"_id": a.get("job_id")}, {"title": 1, "company": 1}) or {}
        out.append({"id": a["_id"], "title": job.get("title") or "Application", "company": job.get("company") or "",
                    "status": a["status"], "silent_days": (now - last).days, "link": f"/applications/{a['_id']}",
                    "suggestion": "Send a short, polite follow-up" if (now - last).days < 21 else "Follow up once more, then move on"})
    return sorted(out, key=lambda x: -x["silent_days"])


@router.get("/ghosting")
async def ghosting(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    return await ghosted(db, user["_id"])


async def notify_ghosting(db: AsyncIOMotorDatabase, uid: str) -> int:
    """Daily: one notification listing applications with no reply for 10+ days."""
    items = await ghosted(db, uid)
    if items:
        names = ", ".join(f"{i['company'] or i['title']} ({i['silent_days']}d)" for i in items[:4])
        await notify(db, user_id=uid, kind="followup_due", title=f"{len(items)} application(s) with no reply for {GHOST_DAYS}+ days",
                     body=f"Time to follow up: {names}", link="/applications")
    return len(items)


# ------------------------------------------------------------------ weekly goals

DEFAULT_GOALS = {"applications": 10, "outreach": 5, "resumes": 3, "prep": 2}
GOAL_LABELS = {"applications": "Applications sent", "outreach": "Recruiters contacted", "resumes": "Tailored resumes", "prep": "Interview preps"}


class GoalsIn(BaseModel):
    applications: int = Field(ge=0, le=200)
    outreach: int = Field(ge=0, le=70)
    resumes: int = Field(ge=0, le=100)
    prep: int = Field(ge=0, le=50)


def week_start():
    now = utcnow()
    return (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)


async def goals_view(db: AsyncIOMotorDatabase, uid: str) -> dict:
    doc = await db[c.GOALS].find_one({"_id": uid}) or {}
    targets = {k: int(doc.get(k, v)) for k, v in DEFAULT_GOALS.items()}
    start = week_start()
    done = {
        "applications": await db[c.APPLICATIONS].count_documents({"user_id": uid, "applied_at": {"$gte": start}}),
        "outreach": await db[c.OUTREACH].count_documents({"user_id": uid, "sent_at": {"$gte": start}}),
        "resumes": await db[c.RESUMES].count_documents({"user_id": uid, "kind": "ATS Resume", "created_at": {"$gte": start}}),
        "prep": await db[c.AUDIT_LOGS].count_documents({"user_id": uid, "action": "job.interview_prep", "timestamp": {"$gte": start}}),
    }
    return {"week_of": start.date().isoformat(),
            "goals": [{"key": k, "label": GOAL_LABELS[k], "target": targets[k], "done": done[k],
                       "pct": 100 if not targets[k] else min(100, round(100 * done[k] / targets[k]))} for k in DEFAULT_GOALS]}


@router.get("/goals")
async def get_goals(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    return await goals_view(db, user["_id"])


@router.put("/goals")
async def put_goals(body: GoalsIn, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    uid = user["_id"]
    await db[c.GOALS].update_one({"_id": uid}, {"$set": {**body.model_dump(), "user_id": uid, "updated_at": utcnow()}}, upsert=True)
    await log_action(db, user_id=uid, action="goals.updated", entity="goals", details=body.model_dump())
    return await goals_view(db, uid)


# ------------------------------------------------------------------ salary insight


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def salary_links(company: str, role: str) -> list[dict]:
    q = quote(f"{company} {role}".strip())
    return [{"label": "AmbitionBox", "url": f"https://www.ambitionbox.com/salaries/{_slug(company)}-salaries"},
            {"label": "Glassdoor", "url": f"https://www.glassdoor.co.in/Search/results.htm?keyword={q}"}]


def _lpa(lo, hi, cur) -> float | None:
    vals = [v for v in (lo, hi) if isinstance(v, (int, float)) and v > 0]
    if not vals or (cur and cur.upper() not in ("INR", "₹")):
        return None
    v = sum(vals) / len(vals)
    return round(v / 100000, 1) if v > 1000 else round(v, 1)  # yearly rupees -> LPA


@router.get("/salary")
async def salary(role: str | None = Query(None, max_length=120), user: dict = Depends(get_current_user),
                 db: AsyncIOMotorDatabase = Depends(db_dep)):
    uid = user["_id"]
    p = await get_profile(db, uid)
    role = (role or (p.preferences.target_roles or [p.personal.current_designation or ""])[0] or "").strip()
    rows: list[tuple[str, str, float]] = []
    hide = [w.lower() for w in p.preferences.excluded_title_words if w.strip()]

    def wanted(title: str) -> bool:
        return (not role or title_matches(title, role)) and not any(w in title.lower() for w in hide)

    inr = {"user_id": uid, "salary_lpa": {"$ne": None}, "salary_currency": "INR"}  # foreign pay isn't comparable to a CTC in LPA
    async for d in db[c.CAREER_JOBS].find(inr, {"title": 1, "company": 1, "salary_lpa": 1}).limit(3000):
        if wanted(d.get("title") or ""):
            rows.append((d.get("company") or "", d.get("title") or "", float(d["salary_lpa"])))
    async for j in db[c.JOBS].find({"user_id": uid}, {"title": 1, "company": 1, "salary_min": 1, "salary_max": 1, "currency": 1}).limit(2000):
        v = _lpa(j.get("salary_min"), j.get("salary_max"), j.get("currency"))
        if v and wanted(j.get("title") or ""):
            rows.append((j.get("company") or "", j.get("title") or "", v))
    by: dict[str, list[float]] = {}
    for co, _, v in rows:
        by.setdefault(co, []).append(v)
    companies = sorted(({"company": co, "min": min(v), "max": max(v), "median": round(median(v), 1), "postings": len(v),
                         "links": salary_links(co, role)} for co, v in by.items() if co), key=lambda x: -x["median"])[:20]
    vals = [v for *_, v in rows]
    exp = p.personal.expected_ctc
    overall = {"min": min(vals), "median": round(median(vals), 1), "max": max(vals), "postings": len(vals)} if vals else None
    verdict = None
    if overall and exp:
        verdict = ("below the market median: you could ask for more" if exp < overall["median"] * 0.9
                   else "above most listed ranges: be ready to justify it" if exp > overall["max"]
                   else "within the market range")
    # Companies the user tracks without a listed salary still get research links.
    tracked = {co for co, *_ in rows}
    extra = [co async for co in _companies(db, uid) if co not in tracked][:10]
    return {"role": role, "currency": "INR (LPA)", "overall": overall, "expected_ctc": exp, "current_ctc": p.personal.current_ctc,
            "verdict": verdict, "companies": companies, "research": [{"company": co, "links": salary_links(co, role)} for co in extra]}


async def _companies(db: AsyncIOMotorDatabase, uid: str):
    seen = set()
    async for j in db[c.JOBS].find({"user_id": uid}, {"company": 1}).sort("_id", -1).limit(200):
        co = j.get("company")
        if co and co not in seen:
            seen.add(co)
            yield co


# ------------------------------------------------------------------ role suggestions

FAMILIES: list[tuple[tuple[str, ...], list[str], list[str]]] = [
    # (trigger words, related roles, title words to hide)
    (("sdet", "automation", "test automation"), ["SDET", "QA Automation Engineer", "Test Automation Engineer", "Software Engineer in Test",
                                                 "Automation Test Engineer", "Quality Engineer", "Senior SDET"], ["manual"]),
    (("performance",), ["Performance Test Engineer", "Performance Engineer", "Load Test Engineer", "SRE"], ["manual"]),
    (("qa", "test", "quality"), ["QA Engineer", "Test Engineer", "QA Automation Engineer", "Quality Analyst", "SDET"], []),
    (("frontend", "react", "angular"), ["Frontend Developer", "React Developer", "UI Engineer", "Full Stack Developer"], []),
    (("java", "backend", "spring"), ["Java Developer", "Backend Engineer", "Software Engineer", "Full Stack Developer"], []),
    (("python", "django"), ["Python Developer", "Backend Engineer", "Software Engineer", "Data Engineer"], []),
    (("data analyst", "analyst", "bi"), ["Data Analyst", "Business Analyst", "BI Analyst", "Product Analyst"], []),
    (("data scien", "machine learning", "ml", "ai"), ["Data Scientist", "ML Engineer", "AI Engineer", "Applied Scientist"], []),
    (("devops", "sre", "cloud"), ["DevOps Engineer", "SRE", "Cloud Engineer", "Platform Engineer"], []),
    (("product",), ["Product Manager", "Product Owner", "Associate Product Manager", "Business Analyst"], []),
    (("business analyst",), ["Business Analyst", "Product Owner", "Functional Consultant", "Data Analyst"], []),
]
_TITLE_NOISE = re.compile(r"\s*[\(\[\-–|,].*$")


@router.get("/roles")
async def roles(q: str = Query("", max_length=200), user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(db_dep)):
    """Related roles for what the user does, the real titles companies use for it, and words to hide (e.g. manual testing)."""
    uid = user["_id"]
    p = await get_profile(db, uid)
    picked = [r.strip() for r in q.split(",") if r.strip()] or p.preferences.target_roles or [p.personal.current_designation or ""]
    low = " ".join(picked).lower()
    related: list[str] = []
    hide: list[str] = []
    for keys, rel, h in FAMILIES:
        if any(k in low for k in keys):
            related += rel
            hide += h
    # Titles companies actually use for these roles (from career portals and jobs the user has).
    seen: Counter[str] = Counter()
    for coll in (c.CAREER_JOBS, c.JOBS):
        async for d in db[coll].find({"user_id": uid}, {"title": 1}).limit(3000):
            t = _TITLE_NOISE.sub("", d.get("title") or "").strip()
            if 4 < len(t) < 60 and any(title_matches(t, r) for r in picked if r) and "manual" not in t.lower():
                seen[t.title() if t.islower() else t] += 1
    from_companies = [t for t, _ in seen.most_common(12)]
    chosen = {r.lower() for r in picked}
    return {"picked": [r for r in picked if r], "related": [r for r in dict.fromkeys(related) if r.lower() not in chosen][:10],
            "from_companies": [t for t in from_companies if t.lower() not in chosen][:10],
            "hide_words": list(dict.fromkeys(hide)), "hidden_now": p.preferences.excluded_title_words}
