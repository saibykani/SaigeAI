"""Portal emails in the Inbox, portal recruiters, IMAP All Mail + fallback, auto-reply drafts,
sign-up details, resume health, live tick, activity, blocked companies and WhatsApp alert preferences."""

import imaplib

from app.database import collections as c
from app.email import imap, portal, smtp
from app.email.auto_reply import detect
from tests.job_fixtures import PROFILE
from tests.test_discover_send import FakeSMTP
from tests.test_resumes import upload

NAUKRI_INVITE = ("Naukri <info@naukri.com>", "Priya Sharma from Acme Corp has invited you to apply",
                 "Priya Sharma, Talent Acquisition at Acme Corp\nhas invited you to apply for SDET - Bengaluru.\n"
                 "Call +91 98765 43210 for details.\nhttps://www.naukri.com/job-listings-sdet-acme-123")


def test_portal_classification_and_recruiter():
    assert portal.category(*NAUKRI_INVITE) == "Portal Invite"
    assert portal.category("LinkedIn <jobalerts-noreply@linkedin.com>", "12 new jobs for SDET", "") == "Job Alert"
    assert portal.category("LinkedIn <messages-noreply@linkedin.com>", "Ravi sent you a message", "") == "Portal Message"
    assert portal.category("Naukri <info@naukri.com>", "Recruiters viewed your profile", "") == "Profile View"
    assert portal.category("friend@example.com", "hello", "") is None
    r = portal.recruiter(*NAUKRI_INVITE)
    assert r["name"] == "Priya Sharma" and r["company"] == "Acme Corp" and r["title"].startswith("Talent Acquisition")
    assert r["phone"] == "+919876543210" and r["portal"] == "naukri"
    assert portal.phones("call 9876543210 or 040-1234") == ["9876543210"]


async def test_portal_mail_shows_in_inbox_adds_recruiter_and_never_moves_applications(client, auth, db):
    sender, subject, body = NAUKRI_INVITE
    r = await client.post("/api/emails/import", headers=auth, json={"sender": sender, "subject": subject, "body": body})
    assert r.status_code == 201 and r.json()["category"] == "Portal Invite"
    contacts = (await client.get("/api/recruiters", headers=auth)).json()
    assert len(contacts) == 1 and contacts[0]["source"] == "portal" and contacts[0]["phone"] == "+919876543210"
    # the same recruiter again is not duplicated (name + company, phone)
    await client.post("/api/emails/import", headers=auth, json={"sender": sender, "subject": subject + " (reminder)", "body": body})
    assert len((await client.get("/api/recruiters", headers=auth)).json()) == 1
    assert not await db[c.OUTREACH].find_one({"kind": "reply"})  # no auto-reply to portal notifications


class AllMailIMAP:
    """Gmail search returns nothing (as on the user's account); the SINCE fallback finds the mail."""
    searches: list = []

    def __init__(self, host, port, timeout=None):
        pass

    def login(self, user, pw):
        return "OK", [b"ok"]

    def list(self):
        return "OK", [b'(\\HasNoChildren) "/" "INBOX"', b'(\\All \\HasNoChildren) "/" "[Gmail]/All Mail"']

    def select(self, box, readonly=False):
        AllMailIMAP.box = box
        return "OK", [b"1"]

    def uid(self, cmd, *args):
        if cmd == "SEARCH":
            AllMailIMAP.searches.append(args)
            return ("OK", [b""]) if args[0] == "X-GM-RAW" else ("OK", [b"5 6"])
        raw = (b"From: Me <asha@gmail.com>\r\nSubject: sent\r\n\r\nmine" if args[0] == b"6" else
               b"From: HR <hr@payco.com>\r\nSubject: Hello\r\nDate: Mon, 28 Sep 2026 10:00:00 +0530\r\n\r\nAre you open to roles?")
        n = args[0].decode()
        # real Gmail often lists X-GM-THRID before X-GM-MSGID (this broke imports on a live account)
        return "OK", [(f"{n} (X-GM-THRID 1 X-GM-MSGID 17800000000000000{n} UID {n} BODY[] {{10}}".encode(), raw), b")"]

    def logout(self):
        return "BYE", []


async def test_imap_uses_all_mail_and_falls_back_to_date_search(monkeypatch):
    AllMailIMAP.searches = []
    monkeypatch.setattr(imap, "IMAP_FACTORY", AllMailIMAP)
    stats: dict = {}
    msgs = await imap.fetch_messages("asha@gmail.com", "abcdefghijklmnop", stats=stats)
    assert AllMailIMAP.box == '"[Gmail]/All Mail"'
    assert stats == {"mailbox": "[Gmail]/All Mail", "matched": 2, "fallback": True, "fetched": 1,
                     "skipped": {"known": 0, "own": 1, "unreadable": 0}}
    assert [m["subject"] for m in msgs] == ["Hello"]  # your own sent mail is skipped
    assert AllMailIMAP.searches[1][:2] == (None, "SINCE")
    assert isinstance(imaplib.IMAP4_SSL, type)


def test_auto_reply_detects_questions():
    asks = detect("SDET opportunity", "Please share your current CTC, notice period and updated resume. Are you available for a call?")
    assert {"ctc", "notice", "resume", "call"} <= set(asks)


async def test_auto_reply_draft_uses_verified_facts_and_attaches_resume(client, auth, db, monkeypatch):
    FakeSMTP.sent = []
    from tests.test_gmail_imap import FakeIMAP
    monkeypatch.setattr(smtp, "SMTP_FACTORY", FakeSMTP)
    monkeypatch.setattr(imap, "IMAP_FACTORY", FakeIMAP)
    await client.put("/api/profile", headers=auth, json=PROFILE)
    await upload(client, auth)
    await client.post("/api/emails/import", headers=auth, json={
        "sender": "Meera Iyer <meera@globex.com>", "subject": "SDET role at Globex",
        "body": "Hi, I'm a recruiter at Globex. Could you share your expected CTC, notice period and your CV?"})
    drafts = [o for o in (await client.get("/api/outreach", headers=auth)).json() if o["kind"] == "reply"]
    assert len(drafts) == 1
    d = drafts[0]
    assert d["subject"] == "Re: SDET role at Globex" and d["attach_resume"] is True
    assert "₹20 LPA" in d["body"] and "Notice period: 30 days." in d["body"] and "Asha Rao" in d["body"]
    assert await db[c.NOTIFICATIONS].find_one({"kind": "reply_drafted"})
    await client.post("/api/auth/connect/gmail-app-password", headers=auth, json={"email": "asha@gmail.com", "app_password": "abcdefghijklmnop"})
    sent = await client.post(f"/api/outreach/{d['id']}/send", headers=auth, params={"approve": "true"})
    assert sent.status_code == 200, sent.text
    msg = FakeSMTP.sent[-1]
    assert msg["To"] == "meera@globex.com" and any(p.get_filename() for p in msg.iter_attachments())
    # replies don't use the manual draft endpoint
    ct = (await client.get("/api/recruiters", headers=auth)).json()[0]
    assert (await client.post("/api/outreach/draft", headers=auth, json={"contact_id": ct["id"], "kind": "reply"})).status_code == 422


async def test_auto_reply_can_be_turned_off(client, auth, db):
    await client.put("/api/automation/settings", headers=auth, json={"auto_reply": {"enabled": False}})
    await client.post("/api/emails/import", headers=auth, json={
        "sender": "Meera <meera@globex.com>", "subject": "Opportunity", "body": "I came across your profile, open to new roles?"})
    assert not await db[c.OUTREACH].find_one({"kind": "reply"})


async def test_register_with_details_starts_profile(client):
    r = await client.post("/api/auth/register", json={
        "email": "new@example.com", "password": "long-password-1", "name": "Ravi Kumar", "phone": "+91 90000 00000",
        "current_designation": "QA Engineer", "total_experience_years": 4, "target_role": "SDET, QA Automation Engineer",
        "current_location": "Pune", "country": "India", "notice_period_days": 30})
    assert r.status_code == 201
    auth = {"Authorization": f"Bearer {r.json()['access_token']}"}
    p = (await client.get("/api/profile", headers=auth)).json()
    assert p["personal"]["country"] == "India" and p["personal"]["notice_period_days"] == 30
    assert p["preferences"]["target_roles"] == ["SDET", "QA Automation Engineer"] and p["preferences"]["preferred_locations"] == ["Pune"]


async def test_resume_health(client, auth):
    rid = (await upload(client, auth)).json()["id"]
    r = await client.get(f"/api/resumes/{rid}/health", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert 0 <= body["score"] <= 100 and {s["area"] for s in body["sections"]} >= {"Quantified impact", "Repetition", "Contact details"}


async def test_live_tick_refreshes_feed_and_activity(client, auth, monkeypatch):
    from app.jobs import feed

    async def fake_build(db, uid, **kw):
        await db[c.JOB_FEED].replace_one({"_id": uid}, {"_id": uid, "built_at": __import__("app.utils").utils.utcnow(), "items": []},
                                         upsert=True)
        return {"items": []}

    monkeypatch.setattr(feed, "build", fake_build)
    r = (await client.post("/api/live/tick", headers=auth)).json()
    assert r["gmail"] is None and isinstance(r["scheduled"], list)
    assert r["feed"] == {"jobs": 0} or "job_discovery" in r["scheduled"]  # the daily job may have built it already
    assert (await client.post("/api/live/tick", headers=auth)).json()["feed"] is None  # fresh: not rebuilt
    await client.put("/api/profile", headers=auth, json=PROFILE)
    act = (await client.get("/api/activity", headers=auth)).json()
    assert act["items"] and act["items"][0]["group"] == "profile"
    assert (await client.get("/api/activity/referrals", headers=auth)).json() == []


async def test_blocked_companies_stop_outreach(client, auth):
    ct = (await client.post("/api/recruiters", headers=auth, json={"name": "Priya Nair", "company": "PayCo", "email": "priya@payco.com"})).json()
    await client.put("/api/profile", headers=auth, json=PROFILE)
    d = (await client.post("/api/outreach/draft", headers=auth, json={"contact_id": ct["id"], "kind": "cold"})).json()
    await client.put("/api/automation/settings", headers=auth, json={"blocked_companies": ["PayCo Pvt Ltd"]})
    await client.post(f"/api/outreach/{d['id']}/approve", headers=auth)
    r = await client.post(f"/api/outreach/{d['id']}/mark-sent", headers=auth)
    assert r.status_code == 409 and "blocked" in r.json()["detail"]
    runs = (await client.get("/api/activity/referrals", headers=auth)).json()
    assert runs[0]["company"] == "PayCo" and runs[0]["status"] == "draft"


async def test_whatsapp_alert_preferences(client, auth, db, monkeypatch):
    from app.services import whatsapp

    sent = []

    async def fake_send(phone, key, text):
        sent.append(text)

    monkeypatch.setattr(whatsapp, "send", fake_send)
    assert (await client.put("/api/integrations/whatsapp/prefs", headers=auth, json={"muted": ["jobs"]})).status_code == 404
    await client.put("/api/integrations/whatsapp", headers=auth, json={"phone": "+91 98765 43210", "apikey": "1234567", "enabled": True})
    r = await client.put("/api/integrations/whatsapp/prefs", headers=auth, json={"muted": ["jobs", "bogus"]})
    assert r.json() == {"muted": ["jobs"]}
    from app.services.notify import notify

    uid = (await db[c.USERS].find_one())["_id"]
    n = len(sent)
    await notify(db, user_id=uid, kind="job_feed", title="5 strong matches")
    await notify(db, user_id=uid, kind="application_submitted", title="Applied: SDET at PayCo")
    assert len(sent) == n + 1 and "Applied" in sent[-1]
    assert whatsapp.group_for("auto_apply") == "applications" and whatsapp.group_for("reply_drafted") == "emails"
