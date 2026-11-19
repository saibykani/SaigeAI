"""Email reply tracking: header / thread / sender-window matching, bounces, template stats, user isolation."""

from datetime import UTC, datetime, timedelta

from app.database import collections as c
from app.email import service as svc
from app.email import tracking
from app.utils import utcnow
from tests.conftest import CSRF, register

SENT = utcnow() - timedelta(days=2)


async def _uid(db, email="asha@example.com"):
    return (await db[c.USERS].find_one({"email": email}))["_id"]


def _msg(sender="Priya <priya@payco.com>", subject="Re: Senior SDET at PayCo", body="Thanks, can we talk tomorrow?", **kw):
    return {"gmail_id": kw.pop("gmail_id", "g1"), "thread_id": kw.pop("thread_id", "t1"), "sender": sender, "subject": subject, "body": body,
            "received_ms": int(utcnow().timestamp() * 1000), "snippet": body[:100], **kw}


async def _sent(db, uid, mid="<abc@gmail.com>", **kw):
    return await tracking.record_sent(db, uid, kind=kw.pop("kind", "outreach"), to=kw.pop("to", "priya@payco.com"),
                                      subject=kw.pop("subject", "Senior SDET at PayCo"), message_id=mid, company="PayCo",
                                      sent_at=kw.pop("sent_at", SENT), **kw)


async def test_header_match(client, db):
    await register(client)
    uid = await _uid(db)
    await _sent(db, uid)
    # different sender and subject: only the In-Reply-To header links it
    await svc.ingest(db, uid, _msg(sender="Hiring <jobs@other.org>", subject="Your note",
                                   in_reply_to="<ABC@gmail.com>", references=""), source="gmail")
    s = await db[c.SENT_EMAILS].find_one({"user_id": uid})
    assert s["status"] == "replied" and s["thread_id"] == "t1" and s["reply_email_id"] and s["replied_at"]


async def test_thread_match(client, db):
    await register(client)
    uid = await _uid(db)
    await _sent(db, uid, thread_id="t9")
    await svc.ingest(db, uid, _msg(sender="Other <x@elsewhere.org>", subject="Hello", thread_id="t9"), source="gmail")
    assert (await db[c.SENT_EMAILS].find_one({"user_id": uid}))["status"] == "replied"


async def test_sender_window_match_and_limits(client, db):
    await register(client)
    uid = await _uid(db)
    await _sent(db, uid)
    await _sent(db, uid, mid="<old@gmail.com>", to="old@acme.com", subject="Old", sent_at=utcnow() - timedelta(days=45))
    # unrelated subject from a stranger does not match
    await svc.ingest(db, uid, _msg(sender="Bob <bob@payco.com>", subject="Lunch", gmail_id="g0", thread_id="tz"), source="gmail")
    assert await db[c.SENT_EMAILS].count_documents({"status": "replied"}) == 0
    # outside the 30 day window does not match
    await svc.ingest(db, uid, _msg(sender="old@acme.com", subject="Re: Old", gmail_id="g2", thread_id="t2"), source="gmail")
    assert await db[c.SENT_EMAILS].count_documents({"status": "replied"}) == 0
    # same sender with Re: matches
    await svc.ingest(db, uid, _msg(gmail_id="g3"), source="gmail")
    assert (await db[c.SENT_EMAILS].find_one({"message_id": "<abc@gmail.com>"}))["status"] == "replied"


async def test_bounce_detection(client, db):
    await register(client)
    uid = await _uid(db)
    await _sent(db, uid, to="gone@payco.com")
    await svc.ingest(db, uid, _msg(sender="Mail Delivery Subsystem <mailer-daemon@googlemail.com>", subject="Delivery Status Notification (Failure)",
                                   body="Your message wasn't delivered to gone@payco.com because the address couldn't be found.",
                                   gmail_id="gb", thread_id="tb"), source="gmail")
    s = await db[c.SENT_EMAILS].find_one({"user_id": uid})
    assert s["status"] == "bounced" and s["replied_at"] is None


async def test_stats_by_template_and_sample_flag(client, db):
    await register(client)
    uid = await _uid(db)
    for i in range(6):
        await _sent(db, uid, mid=f"<a{i}@gmail.com>", to=f"p{i}@x{i}.com", template_name="Warm intro", template_id="t1", kind="bulk")
    for i in range(2):
        await _sent(db, uid, mid=f"<b{i}@gmail.com>", to=f"q{i}@y{i}.com", template_name="Cold", kind="bulk")
    now = utcnow()
    await db[c.SENT_EMAILS].update_many({"message_id": {"$in": ["<a0@gmail.com>", "<a1@gmail.com>"]}}, {"$set": {
        "status": "replied", "replied_at": now, "reply_category": "Interview Invitation"}})
    await db[c.SENT_EMAILS].update_one({"message_id": "<b0@gmail.com>"}, {"$set": {"status": "bounced"}})
    st = await tracking.stats(db, uid)
    assert (st["sent"], st["replied"], st["bounced"]) == (8, 2, 1)
    warm = next(r for r in st["by_template"] if r["key"] == "Warm intro")
    cold = next(r for r in st["by_template"] if r["key"] == "Cold")
    assert warm["sent"] == 6 and warm["replies"] == 2 and warm["interviews"] == 2 and warm["rate"] == 33.3 and warm["enough_data"]
    assert cold["sent"] == 2 and not cold["enough_data"]
    assert st["median_reply_hours"] is not None


async def test_endpoints_isolation_and_backfill(client, db):
    h1 = await register(client)
    h2 = await register(client, email="other@example.com", name="Other")
    uid1, uid2 = await _uid(db), await _uid(db, "other@example.com")
    await _sent(db, uid1)
    await _sent(db, uid2, mid="<zzz@gmail.com>", to="someone@z.com")
    # an already-synced email from before tracking existed
    await db[c.EMAILS].insert_one({"_id": "e1", "user_id": uid1, "sender": "Priya <priya@payco.com>", "subject": "Re: Senior SDET at PayCo",
                                   "body": "Sure", "snippet": "Sure", "received_at": datetime.now(UTC), "category": "Recruiter Reply",
                                   "extracted": {"sender_email": "priya@payco.com"}, "thread_id": "tt"})
    r = await client.post("/api/email-tracking/backfill", headers={**h1, **CSRF})
    assert r.status_code == 200 and r.json()["linked"] == 1
    lst = (await client.get("/api/email-tracking/sent", headers=h1)).json()
    assert lst["total"] == 1 and lst["items"][0]["status"] == "replied" and lst["items"][0]["gmail_url"].endswith("/tt")
    assert lst["items"][0]["reply_category"] == "Recruiter Reply"
    other = (await client.get("/api/email-tracking/sent", headers=h2)).json()
    assert other["total"] == 1 and other["items"][0]["to_email"] == "someone@z.com"
    assert (await client.get("/api/email-tracking/stats", headers=h2)).json()["replied"] == 0
    assert (await client.get("/api/email-tracking/sent?status=replied", headers=h2)).json()["total"] == 0
