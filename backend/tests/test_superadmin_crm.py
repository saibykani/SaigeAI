# ruff: noqa: E501
from datetime import timedelta

from app.database import collections as c
from app.superadmin import metrics as m
from app.utils import new_id, utcnow
from tests.conftest import CSRF
from tests.test_admin_hiring import _reg, _uid

OWNER = "saibykani07@gmail.com"


def test_health_score_and_lifecycle_definitions():
    assert m.health_score(0, 30, 5) == 100
    assert m.health_score(30, 0, 0) == 0
    assert m.health_score(15, 15, 0) == round(20 + 17.5)
    assert m.health_label(70) == "healthy" and m.health_label(40) == "fair" and m.health_label(39) == "low"
    kw = {"activated": True, "events_30d": 12, "features_30d": 3}
    assert m.lifecycle_stage(idle_days=1, **kw) == "engaged"
    assert m.lifecycle_stage(idle_days=1, activated=True, events_30d=2, features_30d=1) == "activated"
    assert m.lifecycle_stage(idle_days=1, activated=False, events_30d=2, features_30d=1) == "new"
    assert m.lifecycle_stage(idle_days=14, **kw) == "at_risk"
    assert m.lifecycle_stage(idle_days=30, **kw) == "churned"


async def _seed(db, email, *, created_days_ago, resume_after_days=None):
    r = await db[c.USERS].find_one({"email": email})
    uid = r["_id"]
    created = utcnow() - timedelta(days=created_days_ago)
    await db[c.USERS].update_one({"_id": uid}, {"$set": {"created_at": created}})
    if resume_after_days is not None:
        await db[c.RESUMES].insert_one({"_id": new_id(), "user_id": uid, "kind": "Master Resume", "created_at": created + timedelta(days=resume_after_days)})
    return uid


async def test_funnel_and_activation(client, db):
    owner = await _reg(client, OWNER)
    for e in ("a@example.com", "b@example.com", "c@example.com"):
        await _reg(client, e)
    a = await _seed(db, "a@example.com", created_days_ago=5, resume_after_days=1)
    b = await _seed(db, "b@example.com", created_days_ago=5, resume_after_days=1)
    await _seed(db, "c@example.com", created_days_ago=5, resume_after_days=None)
    await db[c.JOBS].insert_one({"_id": new_id(), "user_id": a, "created_at": utcnow()})
    await db[c.APPLICATIONS].insert_one({"_id": new_id(), "user_id": a, "company": "Acme", "role": "Dev", "status": "INTERVIEW_SCHEDULED",
                                         "created_at": utcnow(), "applied_at": utcnow()})
    await db[c.APPLICATIONS].insert_one({"_id": new_id(), "user_id": b, "company": "acme", "role": "dev", "status": "APPLIED",
                                         "created_at": utcnow(), "applied_at": utcnow()})
    st = (await client.get("/api/superadmin/funnel?days=10", headers=owner)).json()["stages"]
    users = {s["stage"]: s["users"] for s in st}
    # owner registered "now" falls in range too: 4 signups; a reached interview (so also reply/application/saved/resume), b applied, c nothing
    assert users == {"Signed up": 4, "Profile / resume": 2, "First job saved": 2, "First application": 2, "First reply": 1, "Interview": 1}
    assert all(st[i]["users"] >= st[i + 1]["users"] for i in range(len(st) - 1))
    ov = (await client.get("/api/superadmin/overview?days=10", headers=owner)).json()["kpis"]
    # activation: a, b uploaded within 7 days, c did not; owner (signup today) has no resume -> 2 of 4
    assert ov["activation_rate"]["value"] == 50.0 and ov["signups"]["value"] == 4 and ov["applications_sent"]["value"] == 2
    assert len(ov["signups"]["series"]) == len(ov["dau"]["series"]) >= 10
    top = (await client.get("/api/superadmin/breakdowns?days=10", headers=owner)).json()
    assert top["companies"][0]["count"] == 2 and top["companies"][0]["users"] == 2


async def test_cohort_retention(client, db):
    owner = await _reg(client, OWNER)
    await _reg(client, "x@example.com")
    await _reg(client, "y@example.com")
    now = utcnow()
    monday = (now - timedelta(days=now.weekday())).replace(hour=12, minute=0, second=0, microsecond=0)
    start = monday - timedelta(weeks=2)  # signup two weeks ago
    x = await _seed(db, "x@example.com", created_days_ago=0)
    y = await _seed(db, "y@example.com", created_days_ago=0)
    await db[c.USERS].update_many({"_id": {"$in": [x, y]}}, {"$set": {"created_at": start}})
    await db[c.AUDIT_LOGS].insert_one({"_id": new_id(), "user_id": x, "action": "jobs.saved", "timestamp": start + timedelta(weeks=1, days=1)})
    await db[c.AUDIT_LOGS].insert_one({"_id": new_id(), "user_id": y, "action": "superadmin.x", "timestamp": start + timedelta(weeks=1, days=1)})  # admin noise
    rows = (await client.get("/api/superadmin/cohorts?weeks=4", headers=owner)).json()["weeks"]
    row = next(r for r in rows if r["week"] == start.replace(hour=0, minute=0, second=0, microsecond=0).date().isoformat())
    assert row["size"] == 2 and row["retention"][1] == 50.0 and row["retention"][2] == 100.0  # both signed in again today (this week)
    assert row["retention"][8] is None


async def test_crm_list_lifecycle_notes_tags_bulk(client, db):
    owner = await _reg(client, OWNER)
    h = {**owner, **CSRF}
    await _reg(client, "eng@example.com")
    await _reg(client, "gone@example.com")
    eng = await _seed(db, "eng@example.com", created_days_ago=20, resume_after_days=0)
    gone = await _seed(db, "gone@example.com", created_days_ago=60, resume_after_days=0)
    await db[c.AUDIT_LOGS].delete_many({"user_id": gone})  # drop the real sign-up events: this user has been silent for 45 days
    await db[c.USERS].update_one({"_id": gone}, {"$set": {"last_active_at": utcnow() - timedelta(days=45)}})
    await db[c.USERS].update_one({"_id": eng}, {"$set": {"last_active_at": utcnow()}})
    for i, act in enumerate(["jobs.a", "resumes.b", "applications.c"] * 4):
        await db[c.AUDIT_LOGS].insert_one({"_id": new_id(), "user_id": eng, "action": act, "timestamp": utcnow() - timedelta(hours=i)})
    r = (await client.get("/api/superadmin/users", headers=owner)).json()
    by = {u["email"]: u for u in r["items"]}
    assert by["eng@example.com"]["lifecycle"] == "engaged" and by["gone@example.com"]["lifecycle"] == "churned"
    assert by["eng@example.com"]["health"] > by["gone@example.com"]["health"] and by["eng@example.com"]["source"] == "email"
    assert (await client.get("/api/superadmin/users?lifecycle=churned", headers=owner)).json()["total"] == 1
    # tags + notes
    assert (await client.put(f"/api/superadmin/users/{eng}/tags", json={"tags": ["VIP", "vip", "Tester!"]}, headers=h)).json()["tags"] == ["vip", "tester"]
    n = await client.post(f"/api/superadmin/users/{eng}/notes", json={"text": "Asked about pricing"}, headers=h)
    assert n.status_code == 201
    assert (await client.get("/api/superadmin/users?tag=vip", headers=owner)).json()["total"] == 1
    d = (await client.get(f"/api/superadmin/users/{eng}", headers=owner)).json()
    assert d["tags"] == ["vip", "tester"] and d["notes_count"] == 1 and d["lifecycle"] == "engaged" and "password" not in str(d)
    assert (await client.get(f"/api/superadmin/users/{eng}/notes", headers=owner)).json()["items"][0]["author"] == OWNER
    tl = (await client.get(f"/api/superadmin/users/{eng}/timeline?kind=audit", headers=owner)).json()["items"]
    assert len(tl) >= 12 and all(t["kind"] == "audit" for t in tl)
    # notes are not in the user's own export; bulk skips the owner; csv guards formulas
    exp = await client.get("/api/privacy/export", headers=await _login(client, "eng@example.com"))
    assert "Asked about pricing" not in exp.text
    b = await client.post("/api/superadmin/users-bulk", json={"ids": [eng, gone, (await _uid(db, OWNER))], "action": "disable"}, headers=h)
    assert b.json() == {"updated": 2, "skipped": 1}
    csv_r = await client.get("/api/superadmin/users-export.csv?state=disabled", headers=owner)
    assert "eng@example.com" in csv_r.text and OWNER not in csv_r.text
    # deleting the user removes notes + tags
    ok = await client.post(f"/api/superadmin/users/{eng}/delete", json={"confirm_email": "eng@example.com"}, headers=h)
    assert ok.status_code == 200
    assert await db[c.ADMIN_NOTES].count_documents({"user_id": eng}) == 0 and await db[c.USER_TAGS].count_documents({"user_id": eng}) == 0


async def _login(client, email):
    r = await client.post("/api/auth/login", json={"email": email, "password": "correct-horse-battery"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_non_super_forbidden_on_crm(client, db):
    await _reg(client, OWNER)
    h = await _reg(client, "plain@example.com")
    uid = await _uid(db, "plain@example.com")
    for method, path in (("GET", f"/users/{uid}"), ("GET", f"/users/{uid}/notes"), ("GET", "/tags"), ("GET", "/users-export.csv"),
                         ("GET", "/audit/summary"), ("GET", "/breakdowns")):
        assert (await client.request(method, "/api/superadmin" + path, headers=h)).status_code == 403
    assert (await client.put(f"/api/superadmin/users/{uid}/tags", json={"tags": ["x"]}, headers={**h, **CSRF})).status_code == 403
    assert (await client.post("/api/superadmin/users-bulk", json={"ids": [uid], "action": "disable"}, headers={**h, **CSRF})).status_code == 403


async def test_login_records_platform_and_sessions(client, db):
    owner = await _reg(client, OWNER)
    await _reg(client, "m@example.com")
    r = await client.post("/api/auth/login", json={"email": "m@example.com", "password": "correct-horse-battery"},
                          headers={"User-Agent": "Dart/3.4 (dart:io)"})
    assert r.status_code == 200
    uid = await _uid(db, "m@example.com")
    log = await db[c.AUDIT_LOGS].find_one({"user_id": uid, "action": "auth.login"})
    assert log["details"]["platform"] == "app"
    await client.post("/api/auth/login", json={"email": "m@example.com", "password": "correct-horse-battery"},
                      headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0) Chrome/120"})
    d = (await client.get(f"/api/superadmin/users/{uid}", headers=owner)).json()
    assert {s["platform"] for s in d["sessions"]} >= {"app", "web"}
    plat = (await client.get("/api/superadmin/breakdowns?days=7", headers=owner)).json()["platforms"]
    assert {p["name"] for p in plat} >= {"app", "web"}
    ev = (await client.get("/api/superadmin/audit?feature=auth&days=7", headers=owner)).json()
    assert ev["total"] >= 2 and ev["items"][0]["feature"] == "auth"
    summ = (await client.get("/api/superadmin/audit/summary?days=7", headers=owner)).json()
    assert summ["total"] >= 2 and summ["by_feature"][0]["name"] == "auth"
    assert (await client.get("/api/superadmin/search?q=m@exa", headers=owner)).json()["users"][0]["email"] == "m@example.com"
    assert (await client.get("/api/superadmin/live", headers=owner)).json()["items"]
    f = (await client.get("/api/superadmin/features?days=7", headers=owner)).json()
    assert "agents" in f and f["active_users"] >= 1


async def test_announcement_audience_and_schedule(client):
    owner = await _reg(client, OWNER)
    seeker = await _reg(client, "s@example.com")
    rec = await _reg(client, "r@example.com", role="recruiter")
    h = {**owner, **CSRF}
    soon = (utcnow() + timedelta(days=1)).isoformat()
    for body in ({"title": "All", "message": "m"}, {"title": "Seekers", "message": "m", "audience": "jobseeker"},
                 {"title": "Later", "message": "m", "starts_at": soon}):
        assert (await client.post("/api/superadmin/announcements", json=body, headers=h)).status_code == 201
    bad = await client.post("/api/superadmin/announcements", json={"title": "x", "message": "m", "starts_at": soon, "ends_at": utcnow().isoformat()}, headers=h)
    assert bad.status_code == 422
    assert {a["title"] for a in (await client.get("/api/announcements", headers=seeker)).json()} == {"All", "Seekers"}
    assert {a["title"] for a in (await client.get("/api/announcements", headers=rec)).json()} == {"All"}
    assert {a["status"] for a in (await client.get("/api/superadmin/announcements", headers=owner)).json()} == {"live", "scheduled"}
