"""Phase 5: email classification, extraction, automatic status updates, Gmail connection."""

import base64
from datetime import UTC, datetime

import httpx
import pytest

from app.database import collections as c
from app.email import classifier, gmail
from app.services import crypto
from tests.job_fixtures import SDET_JD
from tests.test_resume_ai import PROFILE

# ------------------------------------------------------------------ classifier

@pytest.mark.parametrize(("subject", "body", "expected"), [
    ("Thank you for applying to PayCo", "We have received your application for Senior SDET.", "Application Confirmation"),
    ("Your application", "Unfortunately, we have decided to move forward with other candidates.", "Rejection"),
    ("Interview invitation - Senior SDET", "We'd like to invite you to a technical interview.", "Interview Invitation"),
    ("Interview rescheduled", "We need to reschedule your interview to a new time.", "Interview Reschedule"),
    ("Next step", "Please complete the HackerRank coding test within 3 days.", "Coding Test"),
    ("Take-home assessment", "Please find the take-home assignment attached.", "Assessment"),
    ("Offer letter", "We are pleased to extend an offer for the role.", "Offer"),
    ("Opportunity", "I came across your profile - are you open to new roles?", "Recruiter Outreach"),
    ("Checking in", "Just following up on my last note.", "Follow-up"),
    ("Newsletter", "Top 10 productivity tips", "Other"),
])
def test_classification(subject, body, expected):
    assert classifier.classify(subject, body)[0] == expected


def test_offer_beats_interview_wording():
    assert classifier.classify("Offer", "After your final interview we are pleased to offer you the role.")[0] == "Offer"


def test_extraction_datetime_meeting_and_round():
    ex = classifier.extract(
        "Technical round - Senior SDET",
        "Your Technical Round is on Monday, October 5, 2026 at 3:00 PM IST. Join: https://meet.google.com/abc-defg-hij.",
        "Priya from PayCo <priya@payco.com>")
    assert ex["interview_at"] == "2026-10-05T09:30:00+00:00"  # 15:00 IST -> 09:30 UTC
    assert ex["timezone"] == "Asia/Kolkata"
    assert ex["meeting_url"] == "https://meet.google.com/abc-defg-hij"
    assert ex["interview_round"] == "Technical Round"
    assert (ex["sender_name"], ex["sender_domain"]) == ("Priya from PayCo", "payco.com")


def test_extraction_numeric_date_24h_and_default_tz():
    when, tz = classifier.extract_datetime("Scheduled for 2026-10-07 14:30", "Asia/Kolkata")
    assert tz == "Asia/Kolkata" and when == datetime(2026, 10, 7, 9, 0, tzinfo=UTC)
    assert classifier.extract_datetime("Let's talk soon", "Asia/Kolkata")[0] is None


# ------------------------------------------------------------------ automatic status updates

async def _app(client, auth, company="PayCo"):
    await client.put("/api/profile", headers=auth, json=PROFILE)
    job = (await client.post("/api/jobs/import", headers=auth, json={
        "title": "Senior SDET", "company": company, "location": "Bengaluru", "description": SDET_JD,
        "application_url": "https://payco.example/careers/sdet"})).json()["job"]
    return (await client.post("/api/applications", headers=auth, json={"job_id": job["id"]})).json()


async def _email(client, auth, subject, body, sender="Talent Team <careers@payco.com>"):
    r = await client.post("/api/emails/import", headers=auth, json={"sender": sender, "subject": subject, "body": body})
    assert r.status_code == 201, r.text
    return r.json()


async def test_confirmation_marks_applied_with_traceability(client, db, auth):
    a = await _app(client, auth)
    e = await _email(client, auth, "Thank you for applying", "We received your application for Senior SDET at PayCo.")
    assert e["category"] == "Application Confirmation" and e["application_id"] == a["id"]
    assert e["action"] == "status:APPLIED"
    detail = (await client.get(f"/api/applications/{a['id']}", headers=auth)).json()
    assert detail["status"] == "APPLIED" and detail["followups"]
    last = [ev for ev in detail["events"] if ev["type"] == "status_change"][-1]
    assert last["source"] == "gmail" and last["email_id"] == e["id"]


async def test_interview_email_creates_interview_then_reschedule(client, auth):
    await _app(client, auth)
    await _email(client, auth, "Thank you for applying", "Application received for PayCo.")
    e = await _email(client, auth, "Interview - Senior SDET at PayCo",
                     "We'd like to invite you to a technical interview on October 12, 2026 at 11:00 AM IST. "
                     "Zoom: https://payco.zoom.us/j/123456")
    assert e["action"] == "status:INTERVIEW_SCHEDULED"
    ivs = (await client.get("/api/interviews", headers=auth)).json()
    iv = ivs["upcoming"][0]
    assert iv["source"] == "gmail" and iv["meeting_url"] == "https://payco.zoom.us/j/123456"
    assert iv["scheduled_at"].startswith("2026-10-12T05:30")
    r = await _email(client, auth, "Interview rescheduled - PayCo", "We need to reschedule to October 14, 2026 at 4:00 PM IST.")
    assert r["action"] == "interview_rescheduled"
    ivs = (await client.get("/api/interviews", headers=auth)).json()
    assert ivs["rescheduled"][0]["scheduled_at"].startswith("2026-10-14T10:30")
    ics = await client.get(f"/api/interviews/{iv['id']}.ics", headers=auth)
    assert ics.status_code == 200 and "BEGIN:VEVENT" in ics.text and "DTSTART:20261014T103000Z" in ics.text


async def test_status_never_moves_backwards_and_rejection_closes(client, auth):
    a = await _app(client, auth)
    await client.post(f"/api/applications/{a['id']}/status", headers=auth, json={"status": "SCREENING"})
    late = await _email(client, auth, "Thank you for applying", "Your application to PayCo was received.")
    assert late["action"] is None  # a late confirmation doesn't drag SCREENING back to APPLIED
    assert (await client.get(f"/api/applications/{a['id']}", headers=auth)).json()["status"] == "SCREENING"
    rej = await _email(client, auth, "Update from PayCo", "Unfortunately we will not be moving forward.")
    assert rej["action"] == "status:REJECTED"
    notes = [n["title"] for n in (await client.get("/api/notifications", headers=auth)).json()]
    assert any(t.startswith("Rejection received") for t in notes)


async def test_unmatched_email_is_stored_without_changes(client, auth):
    await _app(client, auth)
    e = await _email(client, auth, "Exciting opportunity", "I came across your profile, are you open to roles at Globex?",
                     sender="Recruiter <sam@globex-talent.com>")
    assert e["category"] == "Recruiter Outreach" and e["application_id"] is None and e["action"] is None
    listed = (await client.get("/api/emails", headers=auth, params={"category": "Recruiter Outreach"})).json()
    assert len(listed) == 1


# ------------------------------------------------------------------ Gmail connection & sync (mocked Google)

def _b64(s: str) -> str:
    return base64.urlsafe_b64encode(s.encode()).decode().rstrip("=")


def test_token_encryption_roundtrip():
    enc = crypto.encrypt("1//refresh-token")
    assert enc != "1//refresh-token" and crypto.decrypt(enc) == "1//refresh-token"


async def test_gmail_sync_with_mocked_google(client, db, auth, monkeypatch):
    a = await _app(client, auth)
    me = (await client.get("/api/auth/me", headers=auth)).json()
    await db[c.INTEGRATIONS].insert_one({"_id": "i1", "user_id": me["id"], "provider": "gmail", "email": "me@gmail.com",
                                         "refresh_token_enc": crypto.encrypt("rt"), "status": "connected", "last_sync_at": None})
    monkeypatch.setattr("app.email.gmail.get_settings", lambda: type("S", (), {
        "google_client_id": "cid", "google_client_secret": "sec", "google_redirect_uri": "http://x"})())

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/token":
            return httpx.Response(200, json={"access_token": "at"})
        assert request.headers["Authorization"] == "Bearer at"
        if request.url.path.endswith("/messages"):
            assert "newer_than:30d" in request.url.params["q"]
            return httpx.Response(200, json={"messages": [{"id": "m1"}]})
        if request.url.path.endswith("/messages/m1"):
            return httpx.Response(200, json={
                "id": "m1", "threadId": "t1", "internalDate": "1790000000000", "snippet": "Offer",
                "payload": {"headers": [{"name": "From", "value": "HR <hr@payco.com>"},
                                        {"name": "Subject", "value": "Offer letter - Senior SDET"}],
                            "mimeType": "multipart/alternative",
                            "parts": [{"mimeType": "text/plain", "body": {"data": _b64("We are pleased to extend an offer. PayCo")}}]}})
        return httpx.Response(404)

    monkeypatch.setattr(gmail, "http_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    r = await client.post("/api/emails/sync", headers=auth)
    assert r.status_code == 200, r.text
    assert r.json() == {"fetched": 1, "by_category": {"Offer": 1}, "status_updates": 1, "recruiters_added": 0, "alert_jobs": 0}
    assert (await client.get(f"/api/applications/{a['id']}", headers=auth)).json()["status"] == "OFFER"
    again = await client.post("/api/emails/sync", headers=auth)  # already-seen message is skipped
    assert again.json()["fetched"] == 0
    integ = (await client.get("/api/integrations", headers=auth)).json()
    assert integ["gmail"]["connected"] and integ["gmail"]["last_sync_at"]


async def test_gmail_sync_requires_connection_and_respects_pause(client, db, auth):
    assert (await client.post("/api/emails/sync", headers=auth)).status_code == 409
    me = (await client.get("/api/auth/me", headers=auth)).json()
    await db[c.INTEGRATIONS].insert_one({"_id": "i2", "user_id": me["id"], "provider": "gmail",
                                         "refresh_token_enc": crypto.encrypt("rt"), "status": "connected"})
    await client.put("/api/automation/settings", headers=auth, json={"pauses": {"gmail_sync": True}})
    assert (await client.post("/api/emails/sync", headers=auth)).status_code == 423


async def test_disconnect_deletes_tokens_and_optionally_emails(client, db, auth, monkeypatch):
    await _app(client, auth)
    await _email(client, auth, "Hello", "Some text about PayCo")
    me = (await client.get("/api/auth/me", headers=auth)).json()
    await db[c.INTEGRATIONS].insert_one({"_id": "i3", "user_id": me["id"], "provider": "gmail",
                                         "refresh_token_enc": crypto.encrypt("rt"), "status": "connected"})

    async def fake_revoke(token):
        assert token == "rt"

    monkeypatch.setattr(gmail, "revoke", fake_revoke)
    r = await client.delete("/api/auth/connect/gmail", headers=auth, params={"delete_emails": True})
    assert r.status_code == 204
    assert await db[c.INTEGRATIONS].count_documents({}) == 0 and await db[c.EMAILS].count_documents({}) == 0


async def test_connect_gmail_not_configured(client, auth):
    assert (await client.post("/api/auth/connect/gmail", headers=auth)).status_code == 503
