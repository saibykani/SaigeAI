import pytest

from app.config import get_settings
from app.database import collections as c
from tests.conftest import CSRF, register

BOSS = "boss@example.com"


@pytest.fixture(autouse=True)
def _super_admin(monkeypatch):
    monkeypatch.setattr(get_settings(), "super_admin_email", BOSS)


async def _reg(client, email, role=None, name="User"):
    body = {"email": email, "password": "correct-horse-battery", "name": name}
    if role:
        body["role"] = role
    r = await client.post("/api/auth/register", json=body)
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _uid(db, email):
    return (await db[c.USERS].find_one({"email": email}))["_id"]


# ---------------------------------------------------------------- roles

async def test_default_role_and_me(client):
    h = await register(client)
    me = (await client.get("/api/auth/me", headers=h)).json()
    assert me["role"] == "jobseeker" and me["is_super_admin"] is False and me["discoverable"] is False


async def test_recruiter_signup_and_admin_role_rejected(client):
    h = await _reg(client, "rec@example.com", "recruiter")
    assert (await client.get("/api/auth/me", headers=h)).json()["role"] == "recruiter"
    r = await client.post("/api/auth/register", json={"email": "x@example.com", "password": "correct-horse-battery", "name": "X", "role": "admin"})
    assert r.status_code == 422


async def test_super_admin_from_env(client):
    h = await _reg(client, BOSS)
    me = (await client.get("/api/auth/me", headers=h)).json()
    assert me["role"] == "admin" and me["is_super_admin"] is True


# ---------------------------------------------------------------- admin

async def test_admin_requires_admin(client):
    h = await register(client)
    for path in ("/api/admin/overview", "/api/admin/users", "/api/admin/activity"):
        assert (await client.get(path, headers=h)).status_code == 403
    assert (await client.get("/api/admin/overview")).status_code == 401


async def test_admin_overview_users_activity(client, db):
    boss = await _reg(client, BOSS)
    await _reg(client, "rec@example.com", "recruiter")
    await register(client)
    ov = (await client.get("/api/admin/overview", headers=boss)).json()
    k = ov["kpis"]
    assert k["total_users"] == 3 and k["recruiters"] == 1 and k["jobseekers"] == 1 and k["admins"] == 1
    assert k["new_today"] == 3 and k["active_24h"] == 3
    assert len(ov["signups"]) == 30 and ov["signups"][-1]["count"] == 3
    assert any(a["name"] == "user.registered" for a in ov["action_usage"])
    users = (await client.get("/api/admin/users?q=rec", headers=boss)).json()
    assert [u["email"] for u in users] == ["rec@example.com"]
    assert "password_hash" not in users[0]
    act = (await client.get("/api/admin/activity", headers=boss)).json()
    assert act and {"email", "action", "at"} <= act[0].keys() and "details" not in act[0]


async def test_role_changes_and_disable(client, db):
    boss = await _reg(client, BOSS)
    await _reg(client, "admin2@example.com")
    seeker = await register(client)
    a2, sid = await _uid(db, "admin2@example.com"), await _uid(db, "asha@example.com")
    # super admin promotes an admin
    r = await client.patch(f"/api/admin/users/{a2}", json={"role": "admin"}, headers=boss)
    assert r.json()["role"] == "admin"
    login = await client.post("/api/auth/login", json={"email": "admin2@example.com", "password": "correct-horse-battery"})
    a2h = {"Authorization": f"Bearer {login.json()['access_token']}"}
    # a normal admin can switch jobseeker <-> recruiter but not grant admin
    assert (await client.patch(f"/api/admin/users/{sid}", json={"role": "recruiter"}, headers=a2h)).status_code == 200
    assert (await client.patch(f"/api/admin/users/{sid}", json={"role": "admin"}, headers=a2h)).status_code == 403
    boss_id = await _uid(db, BOSS)
    assert (await client.patch(f"/api/admin/users/{boss_id}", json={"is_active": False}, headers=a2h)).status_code == 403
    # disable blocks the session and login
    assert (await client.patch(f"/api/admin/users/{sid}", json={"is_active": False}, headers=a2h)).status_code == 200
    assert (await client.get("/api/auth/me", headers=seeker)).status_code == 401
    r = await client.post("/api/auth/login", json={"email": "asha@example.com", "password": "correct-horse-battery"})
    assert r.status_code == 401
    assert await db[c.AUDIT_LOGS].count_documents({"action": "admin.user_updated"}) == 3


async def test_disabled_user_cannot_refresh(client, db):
    boss = await _reg(client, BOSS)
    await register(client)  # cookie jar now holds asha's refresh cookie
    sid = await _uid(db, "asha@example.com")
    await client.patch(f"/api/admin/users/{sid}", json={"is_active": False}, headers=boss)
    assert (await client.post("/api/auth/refresh", headers=CSRF)).status_code == 401


# ---------------------------------------------------------------- recruiter side

async def _seeker(client, db, email, name, skills, discoverable=True):
    h = await _reg(client, email, name=name)
    await client.put("/api/profile", headers=h, json={"personal": {"name": name, "phone": "+91 90000 00000", "current_designation": "QA Engineer",
                                                                  "total_experience_years": 4}, "skills": {"primary": skills}})
    if discoverable:
        assert (await client.put("/api/talent/settings", headers=h, json={"discoverable": True})).json()["discoverable"] is True
    return h


async def test_jobseeker_cannot_use_recruiter_endpoints(client):
    h = await register(client)
    assert (await client.get("/api/hiring/candidates", headers=h)).status_code == 403
    assert (await client.post("/api/hiring/jobs", headers=h, json={"title": "QA", "company": "Acme"})).status_code == 403


async def test_search_ranks_opted_in_only_and_hides_contact(client, db):
    rec = await _reg(client, "rec@example.com", "recruiter", name="Rita")
    await _seeker(client, db, "a@example.com", "Anil", ["Selenium", "Java", "Python"])
    await _seeker(client, db, "b@example.com", "Bina", ["Selenium"])
    await _seeker(client, db, "c@example.com", "Chetan", ["Selenium", "Java", "Python"], discoverable=False)
    body = {"title": "SDET", "company": "Acme", "skills": ["Selenium", "Java", "Python"]}
    job = (await client.post("/api/hiring/jobs", headers=rec, json=body)).json()
    assert job["skills"]
    res = (await client.get(f"/api/hiring/candidates?job_id={job['id']}", headers=rec)).json()
    assert [r["name"] for r in res] == ["Anil", "Bina"]
    assert res[0]["match"] == 100 and res[1]["match"] < 100
    assert "email" not in res[0] and "phone" not in res[0]


async def test_interest_request_flow(client, db):
    rec = await _reg(client, "rec@example.com", "recruiter", name="Rita")
    cand = await _seeker(client, db, "a@example.com", "Anil", ["Selenium"])
    cid = await _uid(db, "a@example.com")
    job = (await client.post("/api/hiring/jobs", headers=rec, json={"title": "SDET", "company": "Acme", "skills": ["Selenium"]})).json()
    r = await client.post("/api/hiring/requests", headers=rec, json={"candidate_id": cid, "job_id": job["id"], "message": "Hi"})
    assert r.status_code == 201
    assert (await client.post("/api/hiring/requests", headers=rec, json={"candidate_id": cid, "job_id": job["id"]})).status_code == 409
    assert await db[c.NOTIFICATIONS].count_documents({"user_id": cid, "kind": "recruiter_interest"}) == 1
    sent = (await client.get("/api/hiring/requests", headers=rec)).json()
    assert sent[0]["contact"] is None
    inc = (await client.get("/api/talent/requests", headers=cand)).json()
    assert inc[0]["company"] == "Acme"
    assert (await client.post(f"/api/talent/requests/{inc[0]['id']}/respond", headers=cand, json={"accept": True})).json()["status"] == "accepted"
    sent = (await client.get("/api/hiring/requests", headers=rec)).json()
    assert sent[0]["contact"]["email"] and sent[0]["contact"]["phone"]


async def test_request_to_hidden_candidate_rejected(client, db):
    rec = await _reg(client, "rec@example.com", "recruiter")
    await _seeker(client, db, "a@example.com", "Anil", ["Selenium"], discoverable=False)
    cid = await _uid(db, "a@example.com")
    assert (await client.post("/api/hiring/requests", headers=rec, json={"candidate_id": cid})).status_code == 404
