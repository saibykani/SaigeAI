"""Phase 6: daily scheduler and LinkedIn/Naukri refresh."""

from datetime import UTC, datetime, timedelta

import pytest

from app.automation.service import AutomationSettings
from app.config import get_settings
from app.database import collections as c
from app.profiles import optimizer as opt
from app.profiles.service import get_profile
from app.scheduler import service as sched
from app.schemas.platform import NaukriProfile
from app.services.truth_guard import GeneratedClaims, validate_claims
from tests.test_profile_sync import _seed

# 04:00 UTC = 09:30 IST, after the default 08:00/09:00 job times; 01:00 UTC = 06:30 IST, before them.
AFTER = datetime(2026, 9, 28, 4, 0, tzinfo=UTC)  # a Monday
BEFORE = datetime(2026, 9, 28, 1, 0, tzinfo=UTC)


async def _uid(db) -> str:
    return (await db[c.USERS].find_one({}))["_id"]


def test_due_times_follow_user_timezone():
    s = AutomationSettings()
    ist = sched.user_tz(s)
    assert sched.is_due("profile_refresh", s, AFTER.astimezone(ist))
    assert not sched.is_due("profile_refresh", s, BEFORE.astimezone(ist))
    ny = AutomationSettings.model_validate({"schedules": {"timezone": "America/New_York"}})
    # 04:00 UTC is 00:00 in New York: before 08:00 local.
    assert not sched.is_due("profile_refresh", ny, AFTER.astimezone(sched.user_tz(ny)))
    # 14:00 UTC is 10:00 in New York: due.
    assert sched.is_due("profile_refresh", ny, AFTER.replace(hour=14).astimezone(sched.user_tz(ny)))
    bogus = AutomationSettings.model_validate({"schedules": {"timezone": "Mars/Base"}})
    assert str(sched.user_tz(bogus)) == "Asia/Kolkata"


def test_days_toggles_and_pause_respected():
    s = AutomationSettings.model_validate({"profile_schedule": {"days": [5, 6]}})  # weekends only
    local = AFTER.astimezone(sched.user_tz(s))
    assert not sched.is_due("profile_refresh", s, local)
    assert sched.is_due("job_discovery", s, local)
    s2 = AutomationSettings.model_validate({"profile_schedule": {"naukri_daily_freshness": False}})
    assert not sched.is_due("naukri_freshness", s2, local)
    assert not sched.is_due("followups", AutomationSettings(paused_all=True), local)
    nxt = sched.next_run("profile_refresh", s, AFTER)
    assert nxt and datetime.fromisoformat(nxt).weekday() == 5


def test_refresh_time_is_validated():
    with pytest.raises(ValueError):
        AutomationSettings.model_validate({"profile_schedule": {"refresh_time": "25:00"}})


async def test_cron_runs_once_per_day(client, auth, db):
    await _seed(client, auth)
    uid = await _uid(db)
    first = await sched.run_for_user(db, uid, AFTER)
    jobs = {r["job"]: r for r in first}
    assert {"profile_refresh", "naukri_freshness", "followups", "morning_report", "job_discovery"} <= set(jobs)
    assert jobs["profile_refresh"]["status"] == "succeeded"
    assert jobs["profile_refresh"]["result"]["changes_created"] > 0
    assert jobs["gmail_sync"]["status"] == "skipped"
    changes = await db[c.PROFILE_CHANGES].count_documents({"user_id": uid})
    # Same day again: nothing runs and nothing new is created.
    assert await sched.run_for_user(db, uid, AFTER + timedelta(hours=2)) == []
    assert await db[c.PROFILE_CHANGES].count_documents({"user_id": uid}) == changes
    # Early next morning only the any-time job (Gmail) is due; profile jobs wait for 08:00.
    early = await sched.run_for_user(db, uid, BEFORE + timedelta(days=1))
    assert [r["job"] for r in early] == ["gmail_sync"]
    report = await db[c.NOTIFICATIONS].find_one({"user_id": uid, "kind": "morning_report"})
    assert report and "profile suggestion" in report["body"]


async def test_profile_pause_blocks_profile_jobs(client, auth, db):
    await _seed(client, auth)
    await client.put("/api/automation/settings", headers=auth, json={"pauses": {"profile_updates": True}})
    uid = await _uid(db)
    res = {r["job"]: r for r in await sched.run_for_user(db, uid, AFTER)}
    assert res["profile_refresh"]["status"] == "skipped"
    assert await db[c.PROFILE_CHANGES].count_documents({"user_id": uid}) == 0


async def test_freshness_edit_is_truthful_and_rotates(client, auth, db):
    await _seed(client, auth)
    uid = await _uid(db)
    profile = await get_profile(db, uid)
    trends, _ = await opt.skill_trends(db, uid, profile)
    nk = NaukriProfile(headline="QA", key_skills=["Selenium", "Java", "TestNG"], summary="old")
    fields = set()
    for day in range(6):
        edit = opt.naukri_freshness_edit(profile, nk, trends, day)
        assert edit is not None
        fields.add(edit["field"])
        claims = (GeneratedClaims(skills=edit["after"]) if isinstance(edit["after"], list)
                  else GeneratedClaims(text=edit["after"], titles=[profile.personal.current_designation or ""]))
        assert validate_claims(claims, profile).status == "PASSED", edit
    assert fields == {"headline", "key_skills", "summary"}
    # A field with a pending suggestion is skipped.
    edit = opt.naukri_freshness_edit(profile, nk, trends, 0, frozenset({"headline"}))
    assert edit and edit["field"] != "headline"


async def test_run_now_status_and_history(client, auth, db):
    await _seed(client, auth)
    r = await client.post("/api/scheduler/run-now/profile_refresh", headers=auth)
    assert r.status_code == 200 and r.json()["status"] == "succeeded"
    # A manual run doesn't consume the day's scheduled slot.
    r2 = await client.post("/api/scheduler/run-now/profile_refresh", headers=auth)
    assert r2.status_code == 200
    assert (await client.post("/api/scheduler/run-now/nope", headers=auth)).status_code == 422
    hist = (await client.get("/api/scheduler/history", headers=auth)).json()
    assert len(hist) == 2 and hist[0]["trigger"] == "manual"
    st = (await client.get("/api/scheduler/status", headers=auth)).json()
    assert st["timezone"] == "Asia/Kolkata" and st["naukri_streak"] == 0
    job = next(j for j in st["jobs"] if j["job"] == "profile_refresh")
    assert job["last_run"]["status"] == "succeeded" and job["next_run"]


async def test_naukri_streak_counts_consecutive_days(client, auth, db):
    uid = (await client.get("/api/auth/me", headers=auth)).json()["id"]
    now = datetime.now(UTC)
    for d in (0, 1, 2, 4):
        await db[c.PROFILE_CHANGES].insert_one({"_id": f"x{d}", "user_id": uid, "platform": "naukri",
                                                 "applied_at": now - timedelta(days=d)})
    assert await sched.naukri_streak(db, uid, AutomationSettings(), now) == 3


async def test_cron_endpoint_auth(client, auth, db, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "cron_secret", None)
    assert (await client.get("/api/cron/daily")).status_code == 503
    monkeypatch.setattr(settings, "cron_secret", "s3cret-value")
    assert (await client.get("/api/cron/daily")).status_code == 401
    assert (await client.get("/api/cron/daily", headers={"Authorization": "Bearer wrong"})).status_code == 401
    r = await client.get("/api/cron/daily", headers={"Authorization": "Bearer s3cret-value"})
    assert r.status_code == 200 and r.json()["users"] == 1 and r.json()["next_cursor"] is None


async def test_completion_notifications_list_field_changes(client, auth, db):
    await _seed(client, auth)
    uid = await _uid(db)
    res = {r["job"]: r for r in await sched.run_for_user(db, uid, AFTER)}
    changes = res["profile_refresh"]["result"]["changes"]
    assert changes and {"platform", "field", "before", "after"} <= set(changes[0])
    n = await db[c.NOTIFICATIONS].find_one({"user_id": uid, "kind": "profile_optimization"})
    assert "refresh done" in n["title"] and n["details"] and n["details"][0]["field"]
    fresh = await db[c.NOTIFICATIONS].find_one({"user_id": uid, "kind": "naukri_freshness"})
    assert fresh is None or fresh["details"][0]["platform"] == "Naukri"
    # Nothing new on a re-run: still a completion notice.
    await sched.run_for_user(db, uid, AFTER, only="profile_refresh", trigger="manual")
    latest = await db[c.NOTIFICATIONS].find({"user_id": uid, "kind": "profile_optimization"}).sort("created_at", -1).to_list(1)
    assert "refresh done" in latest[0]["title"]
    # Marking a change applied notifies with the new value.
    ch = (await client.get("/api/profile-changes", headers=auth, params={"platform": "linkedin"})).json()[0]
    await client.post(f"/api/profile-changes/{ch['id']}/applied", headers=auth)
    applied = await db[c.NOTIFICATIONS].find_one({"user_id": uid, "kind": "profile_change_applied"})
    assert applied["title"].startswith("LinkedIn updated") and applied["details"][0]["after"]
