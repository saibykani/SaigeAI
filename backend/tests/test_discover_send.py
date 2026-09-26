"""Job discovery (official APIs), approve-and-send from Gmail, and recruiter sync."""

import smtplib

import pytest

from app.config import get_settings
from app.database import collections as c
from app.email import smtp
from app.jobs import discover
from tests.job_fixtures import PROFILE, SDET_JD
from tests.test_gmail_imap import FakeIMAP


class FakeResponse:
    status_code = 200

    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        return None

    def json(self):
        return self._data


class FakeClient:
    """Stands in for httpx: returns canned Adzuna / Remotive / Arbeitnow payloads."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, url, params=None):
        if "adzuna" in url:
            assert params["where"] == "Bengaluru" and params["what"]
            return FakeResponse({"results": [
                {"id": 1, "title": "Senior SDET", "company": {"display_name": "PayCo"}, "location": {"display_name": "Bengaluru"},
                 "redirect_url": "https://adzuna.example/1", "description": SDET_JD, "created": "2026-09-20T00:00:00Z"},
                {"id": 2, "title": "Pastry Chef", "company": {"display_name": "Cafe"}, "location": {"display_name": "Bengaluru"},
                 "redirect_url": "https://adzuna.example/2", "description": "Bake bread and pastries every morning for our cafe."}]})
        if "remotive" in url:
            return FakeResponse({"jobs": [{"id": 9, "title": "QA Automation Engineer", "company_name": "Remote Co",
                                           "candidate_required_location": "Worldwide", "url": "https://remotive.example/9",
                                           "publication_date": "2026-09-21T00:00:00", "description": f"<p>{SDET_JD}</p>"}]})
        if "himalayas" in url or "jobicy" in url:
            return FakeResponse({"jobs": []})
        raise RuntimeError("arbeitnow down")  # one provider failing must not break the search


@pytest.fixture
def providers(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "adzuna_app_id", "id")
    monkeypatch.setattr(s, "adzuna_app_key", "key")
    monkeypatch.setattr(discover, "http_client", lambda: FakeClient())


async def test_discover_scores_without_saving_then_saves_selected(client, auth, db, providers):
    await client.put("/api/profile", headers=auth, json=PROFILE)
    r = await client.post("/api/jobs/discover", headers=auth, json={"query": "SDET", "location": "Bengaluru"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["errors"] == {"arbeitnow": "unavailable right now"}
    titles = [x["title"] for x in body["results"]]
    assert titles[0] in ("Senior SDET", "QA Automation Engineer") and "Pastry Chef" in titles
    assert body["results"][0]["score"] >= body["results"][-1]["score"]
    assert await db[c.JOBS].count_documents({}) == 0  # nothing saved yet

    pick = [x for x in body["results"] if x["title"] != "Pastry Chef"]
    saved = await client.post("/api/jobs/discover/save", headers=auth, json={"items": pick, "prepare_applications": True})
    assert saved.status_code == 201 and saved.json()["saved"] == 2 and saved.json()["applications_prepared"] == 2
    again = (await client.post("/api/jobs/discover", headers=auth, json={"query": "SDET", "location": "Bengaluru"})).json()
    assert sum(1 for x in again["results"] if x["saved_job_id"]) == 2


class FakeSMTP:
    sent: list = []
    password = "abcdefghijklmnop"

    def __init__(self, host, port, timeout=None):
        assert (host, port) == ("smtp.gmail.com", 465)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def login(self, user, pw):
        if pw != self.password:
            raise smtplib.SMTPAuthenticationError(535, b"bad")

    def send_message(self, msg):
        FakeSMTP.sent.append(msg)


async def test_approve_and_send_from_gmail(client, auth, db, monkeypatch):
    from app.email import imap

    FakeSMTP.sent = []
    monkeypatch.setattr(smtp, "SMTP_FACTORY", FakeSMTP)
    monkeypatch.setattr(imap, "IMAP_FACTORY", FakeIMAP)
    await client.put("/api/profile", headers=auth, json=PROFILE)
    ct = (await client.post("/api/recruiters", headers=auth, json={"name": "Priya Nair", "company": "PayCo", "email": "priya@payco.com"})).json()
    d = (await client.post("/api/outreach/draft", headers=auth, json={"contact_id": ct["id"], "kind": "cold"})).json()

    # Without an App Password connection, Saige explains how to send.
    no = await client.post(f"/api/outreach/{d['id']}/send", headers=auth, params={"approve": "true"})
    assert no.status_code == 409 and "App Password" in no.json()["detail"]
    assert not FakeSMTP.sent

    await client.post("/api/auth/connect/gmail-app-password", headers=auth,
                      json={"email": "asha@gmail.com", "app_password": "abcdefghijklmnop"})
    assert (await client.get("/api/outreach/stats", headers=auth)).json()["can_send_from_saige"] is True
    r = await client.post(f"/api/outreach/{d['id']}/send", headers=auth, params={"approve": "true"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "sent" and r.json()["sent_via"] == "gmail"
    msg = FakeSMTP.sent[0]
    assert msg["To"] == "priya@payco.com" and "asha@gmail.com" in msg["From"] and msg["Subject"] == d["subject"]
    assert await db[c.FOLLOWUPS].count_documents({"outreach_id": d["id"]}) == 3
    assert await db[c.NOTIFICATIONS].find_one({"kind": "outreach_sent"})
    # Caps still apply to Saige-sent mail.
    await client.put("/api/automation/settings", headers=auth, json={"pauses": {"recruiter_outreach": True}})
    d2 = (await client.post("/api/outreach/draft", headers=auth, json={"contact_id": ct["id"], "kind": "thank_you"})).json()
    assert (await client.post(f"/api/outreach/{d2['id']}/send", headers=auth, params={"approve": "true"})).status_code == 423
    assert len(FakeSMTP.sent) == 1


async def test_recruiter_sync_from_job_postings(client, auth, db):
    jd = SDET_JD + "\nInterested? Send your CV to hr@payco.com or reach Ravi at ravi.kumar@payco.com. noreply@payco.com"
    await client.post("/api/jobs/import", headers=auth, json={"title": "Senior SDET", "company": "PayCo", "description": jd})
    r = (await client.post("/api/recruiters/sync", headers=auth)).json()
    assert r["from_jobs"] == 2
    contacts = {x["email"]: x for x in (await client.get("/api/recruiters", headers=auth, params={"source": "job"})).json()}
    assert set(contacts) == {"hr@payco.com", "ravi.kumar@payco.com"}
    assert contacts["hr@payco.com"]["name"] == "PayCo Hiring team" and contacts["ravi.kumar@payco.com"]["name"] == "PayCo Ravi Kumar"
    assert (await client.post("/api/recruiters/sync", headers=auth)).json()["created"] == 0
    stats = (await client.get("/api/outreach/stats", headers=auth)).json()
    assert stats["contacts_by_source"] == {"job": 2}


def test_title_matching_uses_role_families():
    assert discover.title_matches("QA Automation Engineer", "SDET")
    assert discover.title_matches("Senior SDET II", "sdet")
    assert discover.title_matches("Software Development Engineer in Test", "Test automation")
    assert not discover.title_matches("Content Reviewer - United States", "QA automation")
    assert not discover.title_matches("Remote Office Assistant", "SDET")
    assert discover.title_matches("Backend Developer (Python)", "Software engineer")
    assert not discover.title_matches("Automation Engineer - PLC / Plant Control", "QA Automation Engineer")
    assert not discover.title_matches("Senior Staff Software Engineer- Search Quality", "SDET")
    assert discover.title_matches("Quality Assurance Engineer", "QA Automation Engineer")
    assert not discover.title_matches("Staff Information Security Analyst - Security Assurance", "SDET")
