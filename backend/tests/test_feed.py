"""Jobs for you (auto-fetched feed), job-alert emails, walk-ins, auto-applier, email applications, ATS scorer, portals."""

import pytest

from app.database import collections as c
from app.email import smtp
from app.jobs import alerts, discover, feed
from tests.job_fixtures import PROFILE, SDET_JD
from tests.test_discover_send import FakeResponse, FakeSMTP

WALKIN_JD = SDET_JD + """
Walk-in drive for QA Automation Engineers on 12th October 2026, 10 AM - 2 PM.
Venue: Tech Park, Hitec City, Hyderabad
Interested candidates can also send your resume to talent@payco.in
"""


class FeedClient:
    """Canned job APIs + one Greenhouse career page; everything else is unreachable."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, url, params=None):
        if "himalayas" in url:
            assert params["country"] == "India"
            if params.get("offset"):
                return FakeResponse({"jobs": []})
            return FakeResponse({"jobs": [
                {"title": "Senior SDET", "companyName": "PayCo", "locationRestrictions": ["India"], "guid": "https://h.example/1",
                 "applicationLink": "https://h.example/1", "pubDate": "1790368259", "description": WALKIN_JD},
                {"title": "QA Automation Engineer", "companyName": "EuroSoft", "locationRestrictions": ["Germany"],
                 "guid": "https://h.example/2", "applicationLink": "https://h.example/2", "description": SDET_JD},
            ]})
        if "greenhouse.io/v1/boards/stripe/jobs/77" in url:
            return FakeResponse({"content": "&lt;p&gt;" + SDET_JD + "&lt;/p&gt;"})
        if "greenhouse.io/v1/boards/stripe/jobs" in url:
            return FakeResponse({"jobs": [
                {"id": 77, "title": "Software Engineer in Test", "location": {"name": "Bengaluru, India"},
                 "absolute_url": "https://stripe.example/77"},
                {"id": 78, "title": "Account Executive", "location": {"name": "Bengaluru, India"}, "absolute_url": "https://stripe.example/78"},
            ]})
        raise RuntimeError("unreachable")


@pytest.fixture
def feed_client(monkeypatch):
    monkeypatch.setattr(discover, "http_client", lambda: FeedClient())
    monkeypatch.setattr(feed, "CAREER_BOARDS", [("greenhouse", "stripe", "Stripe")])


def test_scope_and_walk_in_detection():
    assert feed.scope("Bengaluru, Karnataka", None, "India") == "country"
    assert feed.scope("Remote (worldwide)", True, "India") == "remote"
    assert feed.scope("Remote · Germany", True, "India") == "abroad"
    assert feed.scope("Berlin", None, "India") == "abroad"
    w = feed.walk_in("QA Engineer", WALKIN_JD)
    assert w and "12th October" in w["date"] and w["time"].lower().startswith("10 am") and "Hitec City" in w["venue"]
    assert feed.walk_in("QA Engineer", SDET_JD) is None
    assert feed.contact_emails("mail hr@acme.com or noreply@acme.com") == ["hr@acme.com"]


def test_job_alert_email_parsing():
    body = """Your job alert for SDET in Hyderabad
Senior SDET
Acme Corp
Hyderabad, Telangana, India
View job: https://www.linkedin.com/comm/jobs/view/4012345678/?trackingId=abc

QA Automation Lead
Globex
Bengaluru
https://www.linkedin.com/comm/jobs/view/4099999999/
"""
    items = alerts.parse("LinkedIn Job Alerts <jobalerts-noreply@linkedin.com>", "SDET jobs", body)
    assert [(i["title"], i["company"], i["location"]) for i in items] == [
        ("Senior SDET", "Acme Corp", "Hyderabad, Telangana, India"), ("QA Automation Lead", "Globex", "Bengaluru")]
    assert items[0]["source"] == "linkedin" and items[0]["url"].startswith("https://www.linkedin.com/comm/jobs/view/4012345678")
    assert alerts.parse("friend@example.com", "hi", body) == []
    assert "linkedin.com" in alerts.ALERT_QUERY and "naukri.com" in alerts.ALERT_QUERY


async def test_feed_lists_country_jobs_with_filters_data(client, auth, db, feed_client):
    await client.put("/api/profile", headers=auth, json={**PROFILE, "personal": {**PROFILE["personal"], "country": "India"}})
    await db[c.JOB_ALERTS].insert_one({"_id": "a1", "user_id": (await db[c.USERS].find_one())["_id"], "gmail_id": "g1",
                                       "portal": "naukri", "created_at": __import__("app.utils").utils.utcnow(),
                                       "items": [{"source": "naukri", "title": "Automation Test Engineer", "company": "Infy",
                                                  "location": "Pune", "url": "https://www.naukri.com/job-listings-automation-123",
                                                  "description": "Automation Test Engineer\nInfy\nPune"}]})
    r = await client.get("/api/jobs/feed", headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["country"] == "India" and body["roles"] == ["SDET", "QA Automation Engineer"]
    by_title = {i["title"]: i for i in body["items"]}
    assert "Account Executive" not in by_title  # career page roles are filtered to your target roles
    assert by_title["Senior SDET"]["scope"] == "country" and by_title["Senior SDET"]["walk_in"]["venue"]
    assert by_title["Senior SDET"]["hr_emails"] == ["talent@payco.in"] and by_title["Senior SDET"]["apply_by_email"]
    assert by_title["Software Engineer in Test"]["source_label"] == "Career page"
    assert by_title["QA Automation Engineer"]["scope"] == "abroad"
    assert by_title["Automation Test Engineer"]["source_label"] == "Naukri alert"
    assert "description" not in by_title["Senior SDET"]  # list view gets a snippet only
    assert body["counts"]["walk_in"] == 1 and body["counts"]["alerts"] == 1 and body["counts"]["careers"] == 1
    assert body["items"][-1]["scope"] == "abroad"  # abroad jobs sort last

    # Select-all save, preparing applications; the walk-in posting that asks for CVs by email gets an apply address.
    ids = [i["id"] for i in body["items"] if i["scope"] != "abroad"]
    saved = (await client.post("/api/jobs/feed/save", headers=auth, json={"ids": ids, "prepare_applications": True})).json()
    assert saved["saved"] == len(ids) and saved["applications_prepared"] == len(ids)
    apps = (await client.get("/api/applications", headers=auth)).json()
    payco = next(a for a in (apps if isinstance(apps, list) else apps["items"]) if a["company"] == "PayCo")
    assert payco["apply_email"] == "talent@payco.in" and payco["walk_in"]["date"]
    again = (await client.get("/api/jobs/feed", headers=auth)).json()
    assert sum(1 for i in again["items"] if i["saved_job_id"]) == len(ids)

    # Recruiter sync picks up HR emails published in feed postings.
    sync = (await client.post("/api/recruiters/sync", headers=auth)).json()
    assert sync["from_jobs"] >= 1
    assert any(x["email"] == "talent@payco.in" for x in (await client.get("/api/recruiters", headers=auth)).json())


async def test_auto_apply_prepares_then_bulk_approve_sends_email_application(client, auth, db, feed_client, monkeypatch):
    from app.email import imap
    from tests.test_gmail_imap import FakeIMAP

    FakeSMTP.sent = []
    monkeypatch.setattr(smtp, "SMTP_FACTORY", FakeSMTP)
    monkeypatch.setattr(imap, "IMAP_FACTORY", FakeIMAP)
    await client.put("/api/profile", headers=auth, json={**PROFILE, "personal": {**PROFILE["personal"], "country": "India"}})
    await client.put("/api/automation/settings", headers=auth,
                     json={"auto_apply": {"enabled": True, "min_score": 50, "daily_max": 2, "scopes": ["country"]}})
    r = (await client.post("/api/jobs/auto-apply/run", headers=auth)).json()
    assert r["prepared"] == 2 and r["threshold"] == 50
    assert (await client.post("/api/jobs/auto-apply/run", headers=auth)).json()["prepared"] == 0  # daily max reached
    note = await db[c.NOTIFICATIONS].find_one({"kind": "auto_apply"})
    assert note and len(note["details"]) == 2

    await client.post("/api/auth/connect/gmail-app-password", headers=auth, json={"email": "asha@gmail.com", "app_password": "abcdefghijklmnop"})
    out = (await client.post("/api/applications/approve-bulk", headers=auth, json={"ids": r["application_ids"]})).json()
    assert out["sent"] == 1 and out["open"] == 1, out
    msg = FakeSMTP.sent[0]
    assert msg["To"] == "talent@payco.in" and msg["Subject"].startswith("Application: Senior SDET")
    assert "Asha Rao" in msg.get_body(preferencelist=("plain",)).get_content()
    sent_app = await db[c.APPLICATIONS].find_one({"apply_email": "talent@payco.in"})
    assert sent_app["status"] == "APPLIED" and sent_app["applied_via"] == "email"
    assert await db[c.NOTIFICATIONS].find_one({"kind": "applications_approved"})


async def test_ats_score_against_pasted_jd(client, auth):
    from tests.test_resume_ai import upload

    await client.put("/api/profile", headers=auth, json=PROFILE)
    rid = (await upload(client, auth)).json()["id"]
    r = await client.post("/api/resumes/ats-score", headers=auth, json={"resume_id": rid, "jd_text": SDET_JD, "title": "SDET"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert 0 < body["score"] <= 100 and body["job"] == "SDET" and isinstance(body["tips"], list)
    assert "Selenium" in body["matched_keywords"]
    bad = await client.post("/api/resumes/ats-score", headers=auth, json={"resume_id": rid, "jd_text": "short"})
    assert bad.status_code == 422


async def test_portals_catalog_and_link(client, auth):
    r = (await client.get("/api/integrations/portals", headers=auth)).json()
    keys = {p["key"]: p for p in r["portals"]}
    assert keys["himalayas"]["state"] == "connected" and keys["naukri"]["method"] == "alerts" and keys["naukri"]["state"] == "setup"
    ok = await client.put("/api/integrations/portals/naukri", headers=auth,
                          json={"profile_url": "https://www.naukri.com/mnjuser/profile", "alerts_on": True})
    assert ok.status_code == 200
    n = next(p for p in (await client.get("/api/integrations/portals", headers=auth)).json()["portals"] if p["key"] == "naukri")
    assert n["state"] == "needs_gmail" and n["profile_url"].startswith("https://www.naukri.com")
    assert (await client.put("/api/integrations/portals/nope", headers=auth, json={})).status_code == 404
