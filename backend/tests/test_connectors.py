from datetime import timedelta

import httpx

from app.connectors import router as conn
from app.database import collections as c
from app.utils import utcnow
from tests.job_fixtures import PROFILE

REPOS = [{"name": "rwa-mobile-automation", "description": "Appium suite for a residential welfare app", "language": "Java",
          "topics": ["appium", "cucumber"], "html_url": "https://github.com/asha/rwa-mobile-automation", "fork": False},
         {"name": "forked-lib", "fork": True, "html_url": "https://github.com/asha/forked-lib"}]


def _fake(monkeypatch, status_code=200):
    def handler(request):
        return httpx.Response(status_code, json=REPOS if status_code == 200 else {"message": "x"})
    monkeypatch.setattr(conn, "github_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)))


async def test_github_import_adds_own_repos_as_projects(client, auth, monkeypatch):
    assert (await client.put("/api/profile", headers=auth, json=PROFILE)).status_code == 200
    _fake(monkeypatch)
    r = (await client.get("/api/connectors/github/repos?username=asha", headers=auth)).json()
    assert [x["name"] for x in r["repos"]] == ["rwa-mobile-automation"]  # forks skipped
    out = (await client.post("/api/connectors/github/import", headers=auth, json={"username": "asha", "repos": ["rwa-mobile-automation"]})).json()
    assert out["added"] == ["Rwa Mobile Automation"]
    p = (await client.get("/api/profile", headers=auth)).json()
    pr = next(x for x in p["knowledge"]["projects"] if x["name"] == "Rwa Mobile Automation")
    assert "Java" in pr["technologies"] and "appium" in pr["technologies"]
    again = (await client.post("/api/connectors/github/import", headers=auth, json={"username": "asha", "repos": ["rwa-mobile-automation"]})).json()
    assert again["added"] == []
    _fake(monkeypatch, 404)
    assert (await client.get("/api/connectors/github/repos?username=nobody", headers=auth)).status_code == 404


async def test_calendar_feed_is_private_and_lists_interviews(client, auth, db):
    url = (await client.get("/api/connectors/calendar", headers=auth)).json()["url"]
    token = url.rsplit("/", 1)[1]
    uid = (await db[c.USERS].find_one({}))["_id"]
    await db[c.INTERVIEWS].insert_one({"_id": "i1", "user_id": uid, "role": "SDET", "company": "Acme", "scheduled_at": utcnow() + timedelta(days=2)})
    ics = await client.get(f"/api/calendar/{token}")
    assert ics.status_code == 200 and "SUMMARY:Interview: SDET at Acme" in ics.text
    new = (await client.post("/api/connectors/calendar/rotate", headers=auth)).json()["url"]
    assert new != url and (await client.get(f"/api/calendar/{token}")).status_code == 404
