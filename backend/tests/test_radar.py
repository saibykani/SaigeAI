"""Job Match Radar: merged ranking of feed + career jobs, truthful reasons, own-address test digest."""

import httpx
import pytest
from fastapi import FastAPI

from app.database import collections as c
from app.email import smtp
from app.radar import router as radar_router
from app.radar import service
from app.utils import utcnow
from tests.job_fixtures import PROFILE
from tests.test_discover_send import FakeSMTP


@pytest.fixture
async def rclient(db):
    """The radar router mounted on a small app (main.py wires it in production)."""
    app = FastAPI()
    app.include_router(radar_router.router, prefix="/api")
    radar_router.digest_limiter.reset()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as cl:
        yield cl


async def _seed(db, uid):
    await db[c.JOB_FEED].replace_one({"_id": uid}, {"_id": uid, "user_id": uid, "built_at": utcnow(), "items": [
        {"id": "f1", "title": "SDET", "company": "PayCo", "location": "Hyderabad", "url": "https://h.example/1?utm=x", "score": 71,
         "source": "himalayas", "source_label": "Himalayas", "scope": "country", "classification": "Good match",
         "matched_skills": ["Selenium", "Java"], "missing_skills": ["Kubernetes"]},
        {"id": "f2", "title": "QA Lead", "company": "EuroSoft", "location": "Berlin", "url": "https://h.example/2", "score": 99,
         "scope": "abroad", "matched_skills": ["Java"]},
        {"id": "f3", "title": "QA Engineer", "company": "LowCo", "url": "https://h.example/3", "score": 40, "scope": "remote",
         "matched_skills": [], "missing_skills": ["Playwright", "Cypress"]},
    ], "errors": {}}, upsert=True)
    await db[c.CAREER_JOBS].insert_many([
        {"_id": "c1", "user_id": uid, "active": True, "title": "SDET", "company": "PayCo", "location": "Hyderabad",
         "url": "https://h.example/1", "score": 71, "fit": "good", "source": "greenhouse", "scope": "country", "ai_score": 80,
         "matched_skills": ["Selenium", "Java", "Jenkins"], "missing_skills": ["JMeter"]},
        {"_id": "c2", "user_id": uid, "active": True, "title": "SDET II", "company": "Stripe", "location": "Bengaluru",
         "url": "https://stripe.example/2", "score": 88, "fit": "strong", "source": "greenhouse", "scope": "country",
         "matched_skills": ["Selenium", "Rest Assured", "Java", "SQL", "Jenkins"], "missing_skills": ["Kafka", "Go", "Terraform", "AWS"]},
        {"_id": "c3", "user_id": uid, "active": False, "title": "Closed", "company": "Old", "url": "https://x.example/3", "score": 95},
    ])


async def _uid(client, auth, db):
    await client.put("/api/profile", headers=auth, json=PROFILE)
    return (await db[c.USERS].find_one({}))["_id"]


async def test_radar_ranks_merges_and_dedupes(client, rclient, auth, db):
    uid = await _uid(client, auth, db)
    await _seed(db, uid)
    r = await rclient.get("/api/radar", headers=auth)
    assert r.status_code == 200
    body = r.json()
    ids = [i["id"] for i in body["items"]]
    assert ids == ["c2", "c1", "f3"]  # abroad + closed dropped, tracking params deduped, career copy wins
    top = body["items"][0]
    assert top["company"] == "Stripe" and top["score"] == 88 and top["source"] == "Career page"
    assert len(top["reasons"]) <= 3 and top["reasons"][0].startswith("Your verified skills match: Selenium")
    assert top["missing_skills"][:2] == ["Kafka", "Go"]
    assert any("Saige learning" in x for x in body["items"][1]["reasons"])
    assert body["items"][2]["reasons"] == ["Open to remote work"]  # nothing invented without matched skills
    assert (await rclient.get("/api/radar?top=1", headers=auth)).json()["items"][0]["id"] == "c2"
    assert (await rclient.get("/api/radar?top=0", headers=auth)).status_code == 422
    assert (await rclient.get("/api/radar")).status_code == 401


async def test_radar_empty(client, rclient, auth, db):
    await _uid(client, auth, db)
    body = (await rclient.get("/api/radar", headers=auth)).json()
    assert body["items"] == [] and body["total"] == 0


def test_reasons_only_from_matching_output():
    assert service.reasons_for({}) == []
    got = service.reasons_for({"matched_skills": ["Java"], "fit": "strong", "scope": "remote", "ai_score": 90})
    assert got[0] == "Your verified skills match: Java" and len(got) == 3


async def test_digest_goes_only_to_own_address(client, rclient, auth, db, monkeypatch):
    from app.email import imap
    from tests.test_gmail_imap import FakeIMAP

    FakeSMTP.sent = []
    monkeypatch.setattr(smtp, "SMTP_FACTORY", FakeSMTP)
    monkeypatch.setattr(imap, "IMAP_FACTORY", FakeIMAP)
    uid = await _uid(client, auth, db)
    await _seed(db, uid)
    # No sender connected: in-app notification, no mail.
    no = (await rclient.post("/api/radar/digest/test", headers=auth)).json()
    assert no["sent"] == 0 and no["notified"] == 3 and not FakeSMTP.sent
    await client.post("/api/auth/connect/gmail-app-password", headers=auth, json={"email": "asha@gmail.com", "app_password": "abcdefghijklmnop"})
    ok = (await rclient.post("/api/radar/digest/test", headers=auth)).json()
    assert ok.get("error") is None and ok["sent"] == 3 and ok["to"] == "asha@example.com"
    msg = FakeSMTP.sent[-1]
    assert msg["To"] == "asha@example.com" and msg["Subject"].startswith("Job Match Radar")
    assert "Stripe" in msg.get_body(("html",)).get_content()
    assert await db[c.AUDIT_LOGS].count_documents({"action": "radar.digest_sent"}) == 1
    assert await db[c.AGENT_RUNS].count_documents({"agent_name": "job_match_radar", "status": "succeeded"}) == 2


async def test_digest_respects_email_pause(client, rclient, auth, db):
    uid = await _uid(client, auth, db)
    await _seed(db, uid)
    await client.put("/api/automation/settings", headers=auth, json={"paused_capabilities": ["emails"]})
    r = (await rclient.post("/api/radar/digest/test", headers=auth)).json()
    assert r["sent"] == 0
