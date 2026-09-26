"""Dashboard, automation controls, notifications, privacy and health."""

import json

from app.automation.service import is_allowed
from app.database import collections as c
from app.services.notify import notify
from tests.conftest import CSRF
from tests.test_resumes import upload


async def test_health(client):
    r = await client.get("/api/health")
    assert r.status_code == 200 and r.json()["database"] is True
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Request-ID"]


async def test_dashboard_reports_real_counts(client, db, auth):
    await upload(client, auth)
    me = (await client.get("/api/auth/me", headers=auth)).json()
    await db[c.APPLICATIONS].insert_many([
        {"_id": "a1", "user_id": me["id"], "status": "APPLIED"},
        {"_id": "a2", "user_id": me["id"], "status": "INTERVIEW_SCHEDULED"},
        {"_id": "a3", "user_id": me["id"], "status": "APPROVAL_REQUIRED"},
        {"_id": "a4", "user_id": "someone-else", "status": "OFFER"},
    ])
    r = await client.get("/api/analytics/dashboard", headers=auth)
    assert r.status_code == 200
    d = r.json()
    assert d["totals"]["resumes"] == 1
    assert d["totals"]["applications"] == 3
    assert d["today"]["offers"] == 0
    assert d["action_required"]["applications_need_approval"] == 1
    funnel = {f["stage"]: f["count"] for f in d["funnel"]}
    assert funnel["Shortlisted"] == 3 and funnel["Applied"] == 2 and funnel["Interview"] == 1
    assert d["automation"] == {"mode": "conservative", "paused_all": False}


async def test_pause_all_blocks_every_capability(client, db, auth):
    me = (await client.get("/api/auth/me", headers=auth)).json()
    assert await is_allowed(db, me["id"], "applications")
    r = await client.post("/api/automation/pause-all", headers=auth)
    assert r.json()["paused_all"] is True
    for cap in ("job_discovery", "applications", "emails", "recruiter_outreach",
                "profile_updates", "gmail_sync"):
        assert not await is_allowed(db, me["id"], cap)
    await client.post("/api/automation/resume-all", headers=auth)
    assert await is_allowed(db, me["id"], "applications")


async def test_individual_pause_and_settings(client, db, auth):
    me = (await client.get("/api/auth/me", headers=auth)).json()
    r = await client.put("/api/automation/settings", headers=auth, json={
        "mode": "balanced", "pauses": {"recruiter_outreach": True},
        "limits": {"daily_application_limit": 5, "daily_email_limit": 5,
                   "daily_recruiter_contact_limit": 2, "min_match_score": 80}})
    assert r.status_code == 200
    assert r.json()["mode"] == "balanced"
    assert r.json()["schedules"]["timezone"] == "Asia/Kolkata"
    assert not await is_allowed(db, me["id"], "recruiter_outreach")
    assert await is_allowed(db, me["id"], "job_discovery")
    bad = await client.put("/api/automation/settings", headers=auth, json={"mode": "yolo"})
    assert bad.status_code == 422


async def test_notifications(client, db, auth):
    me = (await client.get("/api/auth/me", headers=auth)).json()
    nid = await notify(db, user_id=me["id"], kind="profile", title="Profile optimization ready")
    items = (await client.get("/api/notifications", headers=auth)).json()
    assert items[0]["title"] == "Profile optimization ready" and not items[0]["read"]
    assert (await client.post(f"/api/notifications/{nid}/read", headers=auth)).status_code == 200
    assert (await client.get("/api/notifications", headers=auth,
                             params={"unread_only": True})).json() == []


async def test_export_excludes_secrets(client, auth):
    await upload(client, auth)
    r = await client.get("/api/privacy/export", headers=auth)
    assert r.status_code == 200
    data = json.loads(r.content)
    assert "password_hash" not in data["user"]
    assert c.REFRESH_TOKENS not in data and c.RESUME_FILES not in data
    assert len(data[c.RESUMES]) == 1


async def test_delete_account_removes_everything(client, db, auth):
    await upload(client, auth)
    await client.put("/api/profile", headers=auth, json={"personal": {"name": "Asha"}})
    assert (await client.delete("/api/privacy/account", headers=auth)).status_code == 403
    r = await client.delete("/api/privacy/account", headers={**auth, **CSRF})
    assert r.status_code == 204
    for coll in (c.USERS, c.RESUMES, c.RESUME_FILES, c.RESUME_VERSIONS, c.CANDIDATE_PROFILES,
                 c.AUDIT_LOGS, c.REFRESH_TOKENS):
        assert await db[coll].count_documents({}) == 0, coll
    assert (await client.get("/api/auth/me", headers=auth)).status_code == 401


async def test_audit_endpoint(client, auth):
    await upload(client, auth)
    actions = [x["action"] for x in (await client.get("/api/audit", headers=auth)).json()]
    assert "resume.uploaded" in actions and "user.registered" in actions
