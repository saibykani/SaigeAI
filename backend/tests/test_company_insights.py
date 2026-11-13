"""Company insights: per-company and per-source reply / interview rates from the user's own records."""

from datetime import timedelta

from app.database import collections as c
from app.utils import new_id, utcnow


async def _uid(client, auth) -> str:
    return (await client.get("/api/auth/me", headers=auth)).json()["id"]


async def _app(db, uid, company, source, days_ago, status="APPLIED", events=(), email=None):
    now = utcnow()
    job_id, app_id = new_id(), new_id()
    applied = now - timedelta(days=days_ago)
    await db[c.JOBS].insert_one({"_id": job_id, "user_id": uid, "title": "QA Engineer", "company": company, "source": source, "created_at": now})
    await db[c.APPLICATIONS].insert_one({"_id": app_id, "user_id": uid, "job_id": job_id, "company": company, "role": "QA Engineer",
                                         "status": status, "applied_at": applied, "created_at": applied, "updated_at": applied})
    for i, (st, after) in enumerate(events):
        await db[c.APPLICATION_EVENTS].insert_one({"_id": new_id(), "user_id": uid, "application_id": app_id, "to": st,
                                                   "at": applied + timedelta(days=after, minutes=i)})
    if email:
        cat, after = email
        await db[c.EMAILS].insert_one({"_id": new_id(), "user_id": uid, "application_id": app_id, "category": cat,
                                       "received_at": applied + timedelta(days=after)})
    return app_id


async def test_company_and_source_insights(client, auth, db):
    uid = await _uid(client, auth)
    await _app(db, uid, "Acme", "greenhouse", 20, "INTERVIEW_SCHEDULED", events=[("RECRUITER_REPLIED", 2), ("INTERVIEW_SCHEDULED", 4)])
    await _app(db, uid, "Acme", "greenhouse", 15, email=("Recruiter Reply", 1))
    await _app(db, uid, "Acme", "greenhouse", 12)
    for _ in range(3):
        await _app(db, uid, "Globex", "lever", 25)
    await _app(db, "someone-else", "Acme", "lever", 5, "OFFER", events=[("OFFER", 1)])

    r = (await client.get("/api/analytics/companies", headers=auth)).json()
    assert r["overall"]["applied"] == 6 and r["enough_data"]
    acme = next(g for g in r["companies"] if g["label"] == "Acme")
    assert (acme["applied"], acme["replied"], acme["interviews"], acme["offers"]) == (3, 2, 1, 0)
    assert acme["reply_rate"] == 67 and acme["interview_rate"] == 33
    assert acme["median_response_days"] == 1.5
    assert acme["ghosted"] == 1 and "interview" in acme["tip"]
    globex = next(g for g in r["companies"] if g["label"] == "Globex")
    assert globex["ghosted"] == 3 and globex["reply_rate"] == 0 and "referral" in globex["tip"]
    assert r["best_source"]["label"] == "Greenhouse" and r["worst_source"]["label"] == "Lever"

    recent = (await client.get("/api/analytics/companies?days=14", headers=auth)).json()
    assert recent["overall"]["applied"] == 1 and not recent["enough_data"]
    assert recent["best_source"] is None


async def test_no_winner_below_min_sample(client, auth, db):
    uid = await _uid(client, auth)
    await _app(db, uid, "A", "greenhouse", 3, email=("Offer", 1))
    await _app(db, uid, "B", "lever", 3)
    r = (await client.get("/api/analytics/companies", headers=auth)).json()
    assert r["best_source"] is None and r["worst_source"] is None
    assert next(g for g in r["companies"] if g["label"] == "A")["offers"] == 1
