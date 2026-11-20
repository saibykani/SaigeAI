"""Career Wrapped: real aggregates only, zero-safe."""

from datetime import date, timedelta

from app.database import collections as c
from app.main import app
from app.utils import new_id, utcnow
from app.wrapped.router import router as wrapped_router
from app.wrapped.service import longest_streak, personality

# Until main.py registers the router, mount it for these tests.
if not any(getattr(r, "path", "") == "/api/wrapped" for r in app.routes):
    app.include_router(wrapped_router, prefix="/api")


async def _uid(client, auth) -> str:
    return (await client.get("/api/auth/me", headers=auth)).json()["id"]


async def _app(db, uid, company, days_ago, path=(), skills=()):
    now = utcnow()
    job_id, app_id = new_id(), new_id()
    await db[c.JOBS].insert_one({"_id": job_id, "user_id": uid, "title": "QA", "company": company, "created_at": now,
                                 "match": {"matched_skills": list(skills)}})
    applied = now - timedelta(days=days_ago)
    await db[c.APPLICATIONS].insert_one({"_id": app_id, "user_id": uid, "job_id": job_id, "company": company, "role": "QA",
                                         "status": path[-1] if path else "APPLIED", "applied_at": applied,
                                         "created_at": now, "updated_at": now})
    for st in path:
        await db[c.APPLICATION_EVENTS].insert_one({"_id": new_id(), "user_id": uid, "application_id": app_id, "to": st,
                                                   "at": applied + timedelta(days=1)})


def test_streak_and_personality():
    assert longest_streak(set()) == 0
    assert longest_streak({date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 4)}) == 2
    base = {"applications": 12, "span_days": 5, "longest_streak": 2, "offers": 0, "reply_rate": 0, "outreach_sent": 0}
    assert personality(base)["label"] == "The Sprinter"
    assert personality({**base, "offers": 1})["label"] == "The Closer"
    assert personality({**base, "applications": 2, "span_days": 2})["label"] == "The Explorer"


async def test_wrapped_empty(client, auth):
    r = await client.get("/api/wrapped", headers=auth)
    assert r.status_code == 200
    d = r.json()
    assert d["empty"] is True
    assert d["applications"] == 0 and d["busiest_day"] is None and d["reply_rate"] is None
    assert d["top_skills"] == [] and d["longest_streak"] == 0


async def test_wrapped_requires_auth_and_valid_period(client, auth):
    assert (await client.get("/api/wrapped")).status_code in (401, 403)
    assert (await client.get("/api/wrapped?period=year", headers=auth)).status_code == 422


async def test_wrapped_counts_and_periods(client, auth, db):
    uid = await _uid(client, auth)
    await _app(db, uid, "Acme", 1, ["APPLIED", "RECRUITER_REPLIED", "INTERVIEW_SCHEDULED"], ["Selenium", "Python"])
    await _app(db, uid, "Acme", 1, ["APPLIED"], ["Python"])
    await _app(db, uid, "Beta", 2, ["APPLIED", "OFFER"], ["Python"])
    await _app(db, uid, "Old", 90, ["APPLIED"])
    await db[c.OUTREACH].insert_one({"_id": new_id(), "user_id": uid, "kind": "referral", "sent_at": utcnow()})
    await db[c.RESUMES].insert_one({"_id": new_id(), "user_id": uid, "kind": "Tailored", "created_at": utcnow()})
    await db[c.RESUMES].insert_one({"_id": new_id(), "user_id": uid, "kind": "Master Resume", "created_at": utcnow()})

    d = (await client.get("/api/wrapped?period=week", headers=auth)).json()
    assert d["empty"] is False
    assert (d["applications"], d["replies"], d["interviews"], d["offers"]) == (3, 2, 2, 1)
    assert d["reply_rate"] == 67
    assert d["busiest_day"]["count"] == 2
    assert d["top_companies"][0] == {"name": "Acme", "count": 2}
    assert d["top_skills"][0] == {"name": "Python", "count": 3}
    assert d["resumes_generated"] == 1 and d["outreach_sent"] == 1
    assert d["longest_streak"] >= 2
    assert d["personality"]["label"] == "The Closer" and d["personality"]["rule"]

    assert (await client.get("/api/wrapped?period=all", headers=auth)).json()["applications"] == 4
