"""/api/cron/tick: lock, time budget, due logic, quiet hours, digest frequency, no repeats."""

from datetime import timedelta

import pytest

from app.automation.service import AutomationSettings
from app.config import get_settings
from app.cron_tick import service as tick
from app.database import collections as c
from app.email import outbound
from app.utils import utcnow
from tests.job_fixtures import PROFILE

SECRET = {"Authorization": "Bearer s3cret-value"}
IST_NOON = "2026-11-24T06:30:00+00:00"  # 12:00 in Asia/Kolkata


def _ist(h: int, m: int = 0):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    return datetime(2026, 11, 24, h, m, tzinfo=ZoneInfo("Asia/Kolkata"))


@pytest.fixture
def sent(monkeypatch):
    """No network: job refreshes are stubbed and mail is captured."""
    calls: list[dict] = []

    async def fake_build(db, uid, **k):
        return {"items": [1, 2]}

    async def fake_scan(db, uid, **k):
        return {"new": 0}

    async def fake_sender(db, uid):
        return {"email": "saige@example.com", "system": True}

    async def fake_send(integ, from_name, to, subject, body, attachments=None, html=None):
        calls.append({"to": to, "subject": subject, "body": body})
        return "<mid@x>"

    monkeypatch.setattr(tick, "utcnow", lambda: _ist(12))  # fixed clock: noon IST, outside quiet hours
    monkeypatch.setattr(tick.feed, "build", fake_build)
    monkeypatch.setattr(tick.careers, "scan", fake_scan)
    monkeypatch.setattr(outbound, "find_digest_sender", fake_sender)
    monkeypatch.setattr(outbound, "send", fake_send)
    return calls


async def _user(client, auth, db):
    await client.put("/api/profile", headers=auth, json=PROFILE)
    return (await db[c.USERS].find_one({}))["_id"]


async def _jobs(db, uid, *ids):
    await db[c.CAREER_JOBS].insert_many([
        {"_id": i, "user_id": uid, "active": True, "title": f"SDET {i}", "company": f"Co{i}", "location": "Hyderabad",
         "url": f"https://x.example/{i}", "score": 90 - n, "fit": "strong", "source": "greenhouse", "scope": "country",
         "matched_skills": ["Java"], "missing_skills": []} for n, i in enumerate(ids)])


# ---------- pure due logic ----------

def test_quiet_hours_wrap_midnight_ist():
    q = lambda h, m=0: tick.in_quiet_hours(_ist(h, m), "Asia/Kolkata", "22:00", "07:00")  # noqa: E731
    assert q(22) and q(23, 59) and q(0) and q(6, 59)
    assert not q(7) and not q(12) and not q(21, 59)
    assert not tick.in_quiet_hours(_ist(3), "Asia/Kolkata", "09:00", "09:00")  # empty window
    assert tick.in_quiet_hours(_ist(10), "Asia/Kolkata", "09:00", "17:00")  # non-wrapping window


def test_digest_frequency_due_logic():
    now = _ist(12)
    s = AutomationSettings()
    assert s.careers.alert_hours == 4  # default
    assert tick.digest_due(s, None, now)
    assert not tick.digest_due(s, now - timedelta(hours=2), now)
    assert tick.digest_due(s, now - timedelta(hours=3, minutes=55), now)  # a 15-min tick never skips a cycle
    s.careers.alert_hours = 12
    assert not tick.digest_due(s, now - timedelta(hours=6), now)
    s.careers.alert_hours = 0
    assert not tick.digest_due(s, None, now)  # off
    s.careers.alert_hours = 4
    assert not tick.digest_due(s, None, _ist(23))  # quiet hours
    with pytest.raises(ValueError):
        AutomationSettings.model_validate({"careers": {"alert_hours": 5}})


def test_refresh_due():
    now = utcnow()
    assert tick.refresh_due(None, now)
    assert not tick.refresh_due(now - timedelta(minutes=10), now)
    assert tick.refresh_due(now - timedelta(minutes=31), now)


# ---------- lock ----------

async def test_lock_blocks_overlap_and_expires(db):
    now = utcnow()
    a = await tick.acquire_lock(db, now)
    assert a
    assert await tick.acquire_lock(db, now + timedelta(seconds=10)) is None  # held
    assert await tick.acquire_lock(db, now + tick.LOCK_TTL + timedelta(seconds=1))  # expired: a crashed call can't block forever
    b = await tick.acquire_lock(db, now + timedelta(days=1))
    await tick.release_lock(db, b)
    assert await tick.acquire_lock(db, utcnow() + timedelta(days=1, seconds=1))


async def test_overlapping_tick_is_skipped(db):
    token = await tick.acquire_lock(db)
    assert token
    assert await tick.run_tick(db) == {"skipped": "another tick is running"}
    await tick.release_lock(db, token)
    assert "skipped" not in await tick.run_tick(db)


# ---------- endpoint ----------

async def test_endpoint_auth_and_methods(client, auth, db, monkeypatch, sent):
    settings = get_settings()
    monkeypatch.setattr(settings, "cron_secret", None)
    assert (await client.get("/api/cron/tick")).status_code == 503
    monkeypatch.setattr(settings, "cron_secret", "s3cret-value")
    assert (await client.get("/api/cron/tick")).status_code == 401
    assert (await client.post("/api/cron/tick", headers={"Authorization": "Bearer nope"})).status_code == 401
    r = await client.get("/api/cron/tick", headers=SECRET)
    assert r.status_code == 200 and r.json()["users"] == 1
    assert (await client.post("/api/cron/tick", headers=SECRET)).status_code == 200


# ---------- the tick ----------

async def test_tick_refreshes_then_is_idempotent(client, auth, db, sent):
    uid = await _user(client, auth, db)
    first = await tick.run_tick(db)
    assert first["refreshed"] == 1
    assert await db[c.AGENT_RUNS].count_documents({"agent_name": "job_refresh_tick", "user_id": uid}) == 1
    again = await tick.run_tick(db)  # 15 minutes later in real life: not due yet
    assert again["refreshed"] == 0


async def test_tick_skips_inactive_and_paused_users(client, auth, db, sent):
    uid = await _user(client, auth, db)
    # use the tick's (fixed) clock, not the real one, so this doesn't break as the calendar moves on
    await db[c.USERS].update_one({"_id": uid}, {"$set": {"last_active_at": tick.utcnow() - timedelta(days=31)}})
    assert (await tick.run_tick(db))["users"] == 0
    await db[c.USERS].update_one({"_id": uid}, {"$set": {"last_active_at": tick.utcnow()}})
    r = await client.put("/api/automation/settings", headers=auth, json={"pauses": {"job_discovery": True}})
    assert r.status_code == 200
    out = await tick.run_tick(db)
    assert out["users"] == 1 and out["refreshed"] == 0
    assert await db[c.AGENT_RUNS].count_documents({"agent_name": "job_refresh_tick"}) == 0


async def test_refresh_round_robin_most_overdue_first(client, auth, db, sent, monkeypatch):
    uid = await _user(client, auth, db)
    other = "u-other"
    await db[c.USERS].insert_one({"_id": other, "email": "b@example.com", "last_active_at": tick.utcnow(), "is_active": True})
    now = tick.utcnow()
    await db[c.SYSTEM_SETTINGS].insert_one({"user_id": uid, "job_tick": {"refreshed_at": now - timedelta(hours=1)}})
    rows = await tick._active_users(db, now)
    assert [r["uid"] for r in rows] == [other, uid]  # never refreshed first, then the oldest
    order: list[str] = []

    async def fake_refresh(db_, u, state, now_, budget):
        order.append(u)
        return {"feed": 1}

    monkeypatch.setattr(tick, "refresh_user", fake_refresh)
    await tick.run_tick(db)
    assert order == [other, uid]


async def test_time_budget_stops_the_refresh_loop(client, auth, db, sent, monkeypatch):
    await _user(client, auth, db)
    for i in range(3):
        await db[c.USERS].insert_one({"_id": f"u{i}", "email": f"u{i}@example.com", "last_active_at": utcnow(), "is_active": True})
    calls: list[str] = []

    async def slow_refresh(db_, u, state, now_, budget):
        calls.append(u)
        import asyncio

        await asyncio.sleep(0.12)
        return {"feed": 1}

    monkeypatch.setattr(tick, "refresh_user", slow_refresh)
    out = await tick.run_tick(db, budget=0.3)  # refresh phase gets ~0.2 s: only two users fit
    assert 1 <= len(calls) < 4 and out["refreshed"] == len(calls)


async def test_digest_sent_once_only_new_jobs(client, auth, db, sent):
    uid = await _user(client, auth, db)
    await _jobs(db, uid, "a", "b")
    out = await tick.run_tick(db)
    assert out["digests_sent"] == 1 and len(sent) == 1
    assert sent[0]["to"] == "asha@example.com" and sent[0]["subject"].startswith("Your best-fit roles")
    assert "SDET a" in sent[0]["body"] and "SDET b" in sent[0]["body"]
    assert await db[c.AUDIT_LOGS].count_documents({"action": "job_alerts.digest_sent"}) == 1
    assert await db[c.AGENT_RUNS].count_documents({"agent_name": "job_alert_digest", "status": "succeeded"}) == 1
    assert (await db[c.CAREER_JOBS].find_one({"_id": "a"}))["emailed_at"] is not None
    # Same cycle: not due again, and nothing repeats.
    assert (await tick.run_tick(db))["digests_sent"] == 0 and len(sent) == 1
    # Next cycle (4 h later) with one new job: only that job is emailed; with none new: skipped.
    await db[c.SYSTEM_SETTINGS].update_one({"user_id": uid}, {"$set": {"job_tick.digest_at": tick.utcnow() - timedelta(hours=5)}})
    await _jobs(db, uid, "c")
    state = (await db[c.SYSTEM_SETTINGS].find_one({"user_id": uid}))["job_tick"]
    res = await tick.send_digest(db, uid, state, tick.utcnow())
    assert res["sent"] == 1 and "SDET c" in sent[-1]["body"] and "SDET a" not in sent[-1]["body"]
    state = (await db[c.SYSTEM_SETTINGS].find_one({"user_id": uid}))["job_tick"]
    assert (await tick.send_digest(db, uid, state, tick.utcnow()))["reason"] == "nothing new"
    assert len(sent) == 2


async def test_digest_respects_pause_off_and_quiet_hours(client, auth, db, sent, monkeypatch):
    uid = await _user(client, auth, db)
    await _jobs(db, uid, "a")
    await client.put("/api/automation/settings", headers=auth, json={"pauses": {"emails": True}})
    assert (await tick.run_tick(db))["digests_sent"] == 0 and not sent
    await client.put("/api/automation/settings", headers=auth, json={"pauses": {"emails": False}, "careers": {"alert_hours": 0}})
    await db[c.SYSTEM_SETTINGS].update_one({"user_id": uid}, {"$unset": {"job_tick.refreshed_at": ""}})
    assert (await tick.run_tick(db))["digests_sent"] == 0 and not sent  # off
    await client.put("/api/automation/settings", headers=auth, json={"careers": {"alert_hours": 4}})
    monkeypatch.setattr(tick, "utcnow", lambda: _ist(23))
    assert (await tick.run_tick(db))["digests_sent"] == 0 and not sent  # quiet hours (23:00 IST)
    monkeypatch.setattr(tick, "utcnow", lambda: _ist(12))
    assert (await tick.run_tick(db))["digests_sent"] == 1 and len(sent) == 1


async def test_mail_error_backs_off(client, auth, db, sent, monkeypatch):
    from app.email.gmail import GmailError

    uid = await _user(client, auth, db)
    await _jobs(db, uid, "a")

    async def boom(*a, **k):
        raise GmailError("refused")

    monkeypatch.setattr(outbound, "send", boom)
    assert (await tick.run_tick(db))["digests_sent"] == 0
    state = (await db[c.SYSTEM_SETTINGS].find_one({"user_id": uid}))["job_tick"]
    assert state["retry_after"] and not state.get("digest_at") and not state.get("sent_keys")
    assert (await tick.send_digest(db, uid, state, tick.utcnow()))["skipped"] == "waiting after a mail error"
