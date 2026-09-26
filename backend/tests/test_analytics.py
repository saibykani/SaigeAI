"""Phase 8: pipeline analytics and the notification centre."""

from datetime import timedelta

from app.analytics.service import role_family
from app.database import collections as c
from app.utils import new_id, utcnow


async def _uid(client, auth) -> str:
    return (await client.get("/api/auth/me", headers=auth)).json()["id"]


async def _app(db, uid, *, title, source, resume, match, applied_days_ago=None, path=(), reply_after_days=None):
    now = utcnow()
    job_id, app_id = new_id(), new_id()
    await db[c.JOBS].insert_one({"_id": job_id, "user_id": uid, "title": title, "company": "Co", "source": source,
                                 "created_at": now})
    applied = now - timedelta(days=applied_days_ago) if applied_days_ago is not None else None
    status = path[-1] if path else ("APPLIED" if applied else "SHORTLISTED")
    await db[c.APPLICATIONS].insert_one({"_id": app_id, "user_id": uid, "job_id": job_id, "company": "Co", "role": title,
                                         "status": status, "resume_id": resume, "match_score": match,
                                         "applied_at": applied, "created_at": now, "updated_at": now})
    for i, st in enumerate(path):
        at = applied + timedelta(days=reply_after_days if reply_after_days is not None else 1, hours=i)
        await db[c.APPLICATION_EVENTS].insert_one({"_id": new_id(), "user_id": uid, "application_id": app_id,
                                                   "type": "status_change", "to": st, "at": at})
    return job_id, app_id


def test_role_families():
    assert role_family("Senior SDET") == "SDET / Automation"
    assert role_family("Performance Test Engineer") == "Performance"
    assert role_family("QA Analyst") == "QA / Testing"
    assert role_family("Backend Developer") == "Engineering"
    assert role_family("Product Manager") == "Other"


async def test_breakdowns_by_source_role_resume_and_match(client, auth, db):
    uid = await _uid(client, auth)
    await db[c.RESUMES].insert_many([{"_id": "r1", "user_id": uid, "name": "Master", "kind": "Master Resume"},
                                     {"_id": "r2", "user_id": uid, "name": "Tailored · Senior SDET", "kind": "Tailored"}])
    await _app(db, uid, title="Senior SDET", source="greenhouse", resume="r2", match=90, applied_days_ago=10,
               path=["APPLIED", "RECRUITER_REPLIED", "INTERVIEW_SCHEDULED"], reply_after_days=2)
    await _app(db, uid, title="QA Engineer", source="greenhouse", resume="r1", match=70, applied_days_ago=9,
               path=["APPLIED", "REJECTED"], reply_after_days=9)
    await _app(db, uid, title="QA Engineer II", source="capture", resume="r1", match=65, applied_days_ago=3,
               path=["APPLIED"])
    ref_job, _ = await _app(db, uid, title="Automation Engineer", source="manual", resume="r2", match=88,
                            applied_days_ago=5, path=["APPLIED", "OFFER"], reply_after_days=4)
    await _app(db, uid, title="Performance Engineer", source="lever", resume=None, match=None)  # never sent
    await db[c.OUTREACH].insert_many([
        {"_id": "o1", "user_id": uid, "kind": "referral", "job_id": ref_job, "status": "replied", "sent_at": utcnow()},
        {"_id": "o2", "user_id": uid, "kind": "cold", "job_id": None, "status": "sent", "sent_at": utcnow()}])

    b = (await client.get("/api/analytics/breakdowns", headers=auth)).json()
    o = b["overall"]
    assert (o["applications"], o["sent"], o["responses"], o["interviews"], o["offers"]) == (5, 4, 3, 2, 1)
    assert o["response_rate"] == 75 and o["interview_rate"] == 50 and o["offer_rate"] == 25

    src = {g["label"]: g for g in b["by_source"]}
    assert src["Greenhouse"]["sent"] == 2 and src["Greenhouse"]["response_rate"] == 100
    assert src["Referral"]["offers"] == 1  # a sent referral request re-labels the application's source
    assert src["Lever"]["sent"] == 0 and src["Lever"]["response_rate"] is None
    fam = {g["label"]: g for g in b["by_role_family"]}
    assert fam["QA / Testing"]["sent"] == 2 and fam["SDET / Automation"]["interviews"] == 2
    res = {g["label"]: g for g in b["by_resume"]}
    assert res["Tailored · Senior SDET"]["interview_rate"] == 100 and res["Master"]["interview_rate"] == 0
    assert [g["label"] for g in b["by_match"]] == ["85%+", "60–74%", "No score"]
    ttr = {x["bucket"]: x["count"] for x in b["time_to_response"]}
    assert ttr == {"0–2 days": 1, "3–7 days": 1, "8–14 days": 1, "15+ days": 0}
    assert len(b["weekly"]) == 8 and sum(w["applied"] for w in b["weekly"]) == 4
    kinds = {k["kind"]: k for k in b["outreach"]}
    assert kinds["referral"]["reply_rate"] == 100 and kinds["cold"]["reply_rate"] == 0


async def test_breakdowns_empty_and_private(client, auth):
    b = (await client.get("/api/analytics/breakdowns", headers=auth)).json()
    assert b["overall"]["sent"] == 0 and b["overall"]["response_rate"] is None
    assert b["by_source"] == [] and all(w["applied"] == 0 for w in b["weekly"])


async def test_notification_centre(client, auth, db):
    uid = await _uid(client, auth)
    for i in range(3):
        await db[c.NOTIFICATIONS].insert_one({"_id": f"n{i}", "user_id": uid, "kind": "x", "title": f"T{i}",
                                              "read": False, "created_at": utcnow()})
    await db[c.NOTIFICATIONS].insert_one({"_id": "other", "user_id": "someone-else", "kind": "x", "title": "no",
                                          "read": False, "created_at": utcnow()})
    assert (await client.get("/api/notifications/unread-count", headers=auth)).json()["unread"] == 3
    assert (await client.post("/api/notifications/n0/read", headers=auth)).status_code == 200
    assert (await client.post("/api/notifications/read-all", headers=auth)).json()["updated"] == 2
    assert (await client.get("/api/notifications/unread-count", headers=auth)).json()["unread"] == 0
    assert (await db[c.NOTIFICATIONS].find_one({"_id": "other"}))["read"] is False
