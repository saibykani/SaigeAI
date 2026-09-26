"""Gmail via Google App Password (IMAP), the alternative to OAuth while the Google project is unverified."""

import imaplib

import pytest

from app.database import collections as c
from app.email import imap

RAW = (b"From: Talent Team <careers@payco.com>\r\nSubject: Interview invitation - Senior SDET\r\n"
       b"Date: Mon, 28 Sep 2026 10:00:00 +0530\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n"
       b"Hi Asha, we'd like to invite you to an interview for the Senior SDET role at PayCo on "
       b"2 October 2026 at 3:00 PM IST. Please confirm your availability.\r\n")


class FakeIMAP:
    password = "abcdefghijklmnop"
    calls: list = []

    def __init__(self, host, port, timeout=None):
        assert host == "imap.gmail.com" and port == 993

    def login(self, user, pw):
        if pw != self.password:
            raise imaplib.IMAP4.error("AUTHENTICATIONFAILED")
        return "OK", [b"ok"]

    def select(self, box, readonly=False):
        assert readonly is True  # never changes mailbox state
        return "OK", [b"1"]

    def uid(self, cmd, *args):
        FakeIMAP.calls.append((cmd, args))
        if cmd == "SEARCH":
            return "OK", [b"7"]
        if args[1] == "(X-GM-MSGID)":  # cheap id-only fetch used to skip mail already imported
            return "OK", [b"7 (X-GM-MSGID 1780000000000000001 UID 7)"]
        assert "BODY.PEEK[]" in args[1]  # PEEK: messages stay unread
        return "OK", [(b"7 (X-GM-MSGID 1780000000000000001 X-GM-THRID 1780000000000000000 BODY[] {300}", RAW), b")"]

    def logout(self):
        return "BYE", []


@pytest.fixture(autouse=True)
def fake_imap(monkeypatch):
    FakeIMAP.calls = []
    monkeypatch.setattr(imap, "IMAP_FACTORY", FakeIMAP)


async def test_connect_rejects_bad_password(client, auth, db):
    r = await client.post("/api/auth/connect/gmail-app-password", headers=auth,
                          json={"email": "asha@gmail.com", "app_password": "wrongwrongwrongw"})
    assert r.status_code == 400 and "App Password" in r.json()["detail"]
    assert await db[c.INTEGRATIONS].count_documents({}) == 0


async def test_connect_and_sync_updates_application(client, auth, db):
    from tests.test_email import _app

    a = await _app(client, auth)
    r = await client.post("/api/auth/connect/gmail-app-password", headers=auth,
                          json={"email": "Asha@Gmail.com", "app_password": "abcd efgh ijkl mnop"})  # spaces as Google shows them
    assert r.status_code == 200 and r.json()["email"] == "asha@gmail.com"
    integ = await db[c.INTEGRATIONS].find_one({"provider": "gmail"})
    assert integ["method"] == "app_password" and "abcdefghijklmnop" not in str(integ)  # stored encrypted
    info = (await client.get("/api/integrations", headers=auth)).json()["gmail"]
    assert info["connected"] and info["method"] == "app_password"

    s = await client.post("/api/emails/sync", headers=auth)
    assert s.status_code == 200, s.text
    assert s.json()["fetched"] == 1
    e = await db[c.EMAILS].find_one({"subject": "Interview invitation - Senior SDET"})
    assert e["gmail_id"] == format(1780000000000000001, "x") and e["category"] == "Interview Invitation"
    assert (await db[c.APPLICATIONS].find_one({"_id": a["id"]}))["status"] == "INTERVIEW_SCHEDULED"
    # Second sync skips what is already imported.
    assert (await client.post("/api/emails/sync", headers=auth)).json()["fetched"] == 0

    assert (await client.delete("/api/auth/connect/gmail", headers=auth)).status_code == 204
    assert await db[c.INTEGRATIONS].count_documents({}) == 0
