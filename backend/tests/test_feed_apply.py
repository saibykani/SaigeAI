"""Auto-apply to selected feed jobs: real email sends, no-contact list, confirm, caps, duplicates; feed validity + 15-minute refresh."""

from datetime import timedelta

from app.database import collections as c
from app.email import imap, smtp
from app.jobs import feed
from app.utils import utcnow
from tests.job_fixtures import PROFILE
from tests.test_discover_send import FakeSMTP
from tests.test_feed import feed_client  # noqa: F401  (fixture)
from tests.test_gmail_imap import FakeIMAP


async def _setup(client, auth, monkeypatch, gmail=True):
    FakeSMTP.sent = []
    monkeypatch.setattr(smtp, "SMTP_FACTORY", FakeSMTP)
    monkeypatch.setattr(imap, "IMAP_FACTORY", FakeIMAP)
    await client.put("/api/profile", headers=auth, json={**PROFILE, "personal": {**PROFILE["personal"], "country": "India"}})
    if gmail:
        await client.post("/api/auth/connect/gmail-app-password", headers=auth, json={"email": "asha@gmail.com", "app_password": "abcdefghijklmnop"})
    items = (await client.get("/api/jobs/feed", headers=auth)).json()["items"]
    return {i["company"]: i for i in items}


async def test_sends_only_to_jobs_with_email_and_lists_the_rest_with_links(client, auth, db, feed_client, monkeypatch):  # noqa: F811
    by = await _setup(client, auth, monkeypatch)
    ids = [by["PayCo"]["id"], by["Stripe"]["id"]]
    r = await client.post("/api/jobs/feed/apply", headers=auth, json={"ids": ids, "confirm": True})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["sent"] == 1 and out["no_contact"] == 1
    sent = next(x for x in out["results"] if x["status"] == "sent")
    assert sent["company"] == "PayCo" and sent["to"] == "talent@payco.in"
    nc = next(x for x in out["results"] if x["status"] == "no_contact")
    assert nc["url"] == "https://stripe.example/77" and "apply on the career site" in nc["message"]
    assert len(FakeSMTP.sent) == 1 and FakeSMTP.sent[0]["To"] == "talent@payco.in"
    att = next(FakeSMTP.sent[0].iter_attachments())
    assert att.get_filename().endswith(".pdf")
    a = await db[c.APPLICATIONS].find_one({"company": "PayCo"})
    assert a["status"] == "APPLIED" and a["applied_via"] == "email" and a["email_record"]["to"] == "talent@payco.in"
    assert await db[c.JOBS].find_one({"company": "Stripe"})  # the no-contact job is still saved
    assert not await db[c.APPLICATIONS].find_one({"company": "Stripe"})
    assert await db[c.AGENT_RUNS].find_one({"agent_name": "feed_auto_apply"})
    assert await db[c.AUDIT_LOGS].find_one({"action": "jobs.feed_apply"})

    # the same company + role is never emailed twice
    again = (await client.post("/api/jobs/feed/apply", headers=auth, json={"ids": [by["PayCo"]["id"]], "confirm": True})).json()
    assert again["sent"] == 0 and again["skipped"] == 1 and len(FakeSMTP.sent) == 1


async def test_confirm_gmail_and_pauses_are_required(client, auth, db, feed_client, monkeypatch):  # noqa: F811
    by = await _setup(client, auth, monkeypatch, gmail=False)
    ids = [by["PayCo"]["id"]]
    assert (await client.post("/api/jobs/feed/apply", headers=auth, json={"ids": ids})).status_code == 400  # no confirm
    assert (await client.post("/api/jobs/feed/apply", headers=auth, json={"ids": ids, "confirm": True})).status_code == 409  # no Gmail
    await client.post("/api/auth/connect/gmail-app-password", headers=auth, json={"email": "asha@gmail.com", "app_password": "abcdefghijklmnop"})
    await client.put("/api/automation/settings", headers=auth, json={"pauses": {"emails": True}})
    assert (await client.post("/api/jobs/feed/apply", headers=auth, json={"ids": ids, "confirm": True})).status_code == 423
    assert FakeSMTP.sent == []


async def test_daily_limit_is_respected(client, auth, db, feed_client, monkeypatch):  # noqa: F811
    by = await _setup(client, auth, monkeypatch)
    me = await db[c.USERS].find_one()
    await db[c.APPLICATIONS].insert_one({"_id": "old", "user_id": me["_id"], "feed_apply": True, "applied_at": utcnow(), "company": "X", "role": "Y"})
    await client.put("/api/automation/settings", headers=auth, json={"auto_apply": {"daily_max": 1}})
    out = (await client.post("/api/jobs/feed/apply", headers=auth, json={"ids": [by["PayCo"]["id"]], "confirm": True})).json()
    assert out["sent"] == 0 and "limit" in out["results"][0]["message"] and FakeSMTP.sent == []


def test_feed_drops_items_without_a_real_link_or_that_are_closed():
    ok = {"title": "SDET", "company": "Acme", "url": "https://acme.com/jobs/1"}
    assert feed.valid_item(ok)
    assert not feed.valid_item({**ok, "url": None})
    assert not feed.valid_item({**ok, "url": "javascript:alert(1)"})
    assert not feed.valid_item({**ok, "url": "ftp://acme.com/1"})
    assert not feed.valid_item({**ok, "company": ""})
    assert not feed.valid_item({**ok, "title": " "})
    assert not feed.valid_item({**ok, "status": "Closed"})
    assert not feed.valid_item({**ok, "expired": True})


async def test_live_feed_has_no_item_without_a_url(client, auth, feed_client, monkeypatch):  # noqa: F811
    by = await _setup(client, auth, monkeypatch, gmail=False)
    assert by and all(str(i["url"]).startswith("http") and i["title"] and i["company"] for i in by.values())


async def test_live_tick_rebuilds_feed_only_after_15_minutes(client, auth, db, feed_client, monkeypatch):  # noqa: F811
    await _setup(client, auth, monkeypatch, gmail=False)
    assert feed.FEED_TTL == timedelta(minutes=15)
    me = await db[c.USERS].find_one()
    t = (await client.post("/api/live/tick", headers=auth)).json()
    assert t["feed"] is None  # just built, nothing to do
    await db[c.JOB_FEED].update_one({"_id": me["_id"]}, {"$set": {"built_at": utcnow() - timedelta(minutes=10)}})
    assert (await client.post("/api/live/tick", headers=auth)).json()["feed"] is None
    await db[c.JOB_FEED].update_one({"_id": me["_id"]}, {"$set": {"built_at": utcnow() - timedelta(minutes=16)}})
    t = (await client.post("/api/live/tick", headers=auth)).json()
    assert t["feed"]["jobs"] > 0
    assert (utcnow() - (await db[c.JOB_FEED].find_one({"_id": me["_id"]}))["built_at"]).total_seconds() < 60
