"""Mobile pulse (replies + approvals for notifications) and feed swipe hide/unhide."""

from datetime import timedelta

from app.database import collections as c
from app.utils import utcnow
from tests.conftest import CSRF, register


async def _uid(db, email="asha@example.com"):
    return (await db[c.USERS].find_one({"email": email}))["_id"]


async def test_pulse_replies_and_approvals(client, db):
    auth = await register(client)
    uid = await _uid(db)
    now = utcnow()
    await db[c.SENT_EMAILS].insert_many([
        {"_id": "s1", "user_id": uid, "status": "replied", "to": "hr@payco.com", "company": "PayCo", "subject": "SDET",
         "replied_at": now, "reply_snippet": "Can we talk?", "reply_category": "Recruiter Reply"},
        {"_id": "s2", "user_id": uid, "status": "replied", "replied_at": now - timedelta(days=10)},
        {"_id": "s3", "user_id": uid, "status": "sent", "sent_at": now},
        {"_id": "s4", "user_id": "other", "status": "replied", "replied_at": now},
    ])
    await db[c.RECRUITER_CONTACTS].insert_many([
        {"_id": "k1", "user_id": uid, "name": "Priya", "company": "PayCo", "email": "priya@payco.com"},
        {"_id": "k2", "user_id": uid, "name": "NoMail", "company": "X"},
    ])
    await db[c.OUTREACH].insert_many([
        {"_id": "o1", "user_id": uid, "contact_id": "k1", "status": "draft", "kind": "email", "subject": "Hi", "body": "Hello",
         "validation": {"status": "PASSED"}, "created_at": now},
        {"_id": "o2", "user_id": uid, "contact_id": "k1", "status": "draft", "kind": "email", "validation": {"status": "FAILED"}, "created_at": now},
        {"_id": "o3", "user_id": uid, "contact_id": "k2", "status": "draft", "kind": "email", "validation": {"status": "PASSED"}, "created_at": now},
        {"_id": "o4", "user_id": uid, "contact_id": "k1", "status": "draft", "kind": "linkedin_note", "validation": {"status": "PASSED"}},
    ])
    await db[c.JOBS].insert_one({"_id": "j1", "user_id": uid, "title": "Senior SDET", "company": "PayCo"})
    await db[c.APPLICATIONS].insert_many([
        {"_id": "a1", "user_id": uid, "job_id": "j1", "status": "READY_TO_APPLY", "apply_email": "jobs@payco.com", "created_at": now},
        {"_id": "a2", "user_id": uid, "job_id": "j1", "status": "READY_TO_APPLY", "created_at": now},
        {"_id": "a3", "user_id": uid, "job_id": "j1", "status": "APPLIED", "apply_email": "jobs@payco.com", "created_at": now},
    ])
    r = await client.get("/api/mobile/pulse", headers=auth)
    assert r.status_code == 200, r.text
    d = r.json()
    assert [x["id"] for x in d["replies"]] == ["s1"] and d["replies"][0]["snippet"] == "Can we talk?"
    assert {(x["type"], x["id"]) for x in d["approvals"]} == {("outreach", "o1"), ("application", "a1")}
    app = next(x for x in d["approvals"] if x["type"] == "application")
    assert app["title"] == "Apply: Senior SDET" and "jobs@payco.com" in app["subject"]

    later = (now + timedelta(minutes=1)).isoformat()
    r = await client.get("/api/mobile/pulse", params={"since": later}, headers=auth)
    assert r.json()["replies"] == []


async def test_feed_hide_unhide(client, db):
    auth = await register(client)
    uid = await _uid(db)
    await db[c.JOB_FEED].insert_one({"_id": uid, "built_at": utcnow(), "roles": ["SDET"], "items": [
        {"id": "f1", "title": "SDET", "company": "PayCo", "url": "https://x.example/1", "scope": "country", "source_label": "Himalayas",
         "score": 80},
        {"id": "f2", "title": "QA", "company": "Bee", "url": "https://x.example/2", "scope": "remote", "source_label": "Himalayas", "score": 70},
    ]})
    r = await client.post("/api/mobile/feed/hide", json={"id": "f1"}, headers={**auth, **CSRF})
    assert r.status_code == 200, r.text
    assert (await client.post("/api/mobile/feed/hide", json={"id": "nope"}, headers={**auth, **CSRF})).status_code == 404
    r = await client.get("/api/jobs/feed", headers=auth)
    assert [i["id"] for i in r.json()["items"]] == ["f2"]
    await client.post("/api/mobile/feed/unhide", json={"id": "f1"}, headers={**auth, **CSRF})
    r = await client.get("/api/jobs/feed", headers=auth)
    assert {i["id"] for i in r.json()["items"]} == {"f1", "f2"}


async def test_pulse_token_is_read_only(client, db):
    auth = await register(client)
    r = await client.post("/api/mobile/pulse-token", headers={**auth, **CSRF})
    assert r.status_code == 201
    tok = {"Authorization": f"Bearer {r.json()['token']}"}
    assert (await client.get("/api/mobile/pulse/bg", headers=tok)).status_code == 200
    # cannot use extension endpoints or normal session endpoints
    assert (await client.get("/api/ext/me", headers=tok)).status_code == 401
    assert (await client.get("/api/mobile/pulse", headers=tok)).status_code == 401
    # not listed with extension tokens, and a new one revokes the old
    assert (await client.get("/api/auth/tokens", headers=auth)).json() == []
    await client.post("/api/mobile/pulse-token", headers={**auth, **CSRF})
    assert (await client.get("/api/mobile/pulse/bg", headers=tok)).status_code == 401
    # an extension token can't read the background pulse
    ext = (await client.post("/api/auth/tokens", json={}, headers={**auth, **CSRF})).json()["token"]
    assert (await client.get("/api/mobile/pulse/bg", headers={"Authorization": f"Bearer {ext}"})).status_code == 401


async def test_streak_from_real_activity(client, db):
    auth = await register(client)
    uid = await _uid(db)
    r = await client.get("/api/mobile/streak", headers=auth)
    assert r.status_code == 200, r.text
    d = r.json()
    assert (d["current"], d["best"], d["today"], d["goal"]) == (0, 0, 0, 3) and len(d["last7"]) == 7
    assert not any(x["active"] for x in d["last7"])

    now = utcnow()
    await db[c.OUTREACH].insert_one({"_id": "o1", "user_id": uid, "status": "sent", "sent_at": now})
    await db[c.APPLICATIONS].insert_one({"_id": "a1", "user_id": uid, "status": "APPLIED", "created_at": now - timedelta(days=1)})
    await db[c.MOCK_INTERVIEWS].insert_one({"_id": "m1", "user_id": uid, "created_at": now - timedelta(days=2)})
    await db[c.INTERVIEWS].insert_one({"_id": "i1", "user_id": uid, "created_at": now - timedelta(days=5)})
    await db[c.INTERVIEWS].insert_one({"_id": "i2", "user_id": "other", "created_at": now - timedelta(days=3)})
    d = (await client.get("/api/mobile/streak", headers=auth)).json()
    assert d["current"] == 3 and d["best"] == 3 and d["today"] == 1 and d["goal_met"] is False
    assert [x["active"] for x in d["last7"]] == [False, True, False, False, True, True, True]

    # today inactive: streak still counts through yesterday
    await db[c.OUTREACH].delete_many({})
    d = (await client.get("/api/mobile/streak", headers=auth)).json()
    assert d["current"] == 2 and d["today"] == 0


async def test_streak_goal_from_weekly_goal(client, db):
    auth = await register(client)
    uid = await _uid(db)
    await db[c.GOALS].insert_one({"_id": uid, "applications": 2, "outreach": 1})
    assert (await client.get("/api/mobile/streak", headers=auth)).json()["goal"] == 1
    await db[c.GOALS].update_one({"_id": uid}, {"$set": {"applications": 20, "outreach": 5}})
    assert (await client.get("/api/mobile/streak", headers=auth)).json()["goal"] == 4
