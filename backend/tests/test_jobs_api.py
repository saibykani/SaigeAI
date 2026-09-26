"""API tests: import, dedupe, matching, sources (mocked official ATS APIs), pause, isolation."""

import httpx
import pytest

from app.database import collections as c
from app.jobs import sources
from app.jobs.router import sync_limiter
from tests.conftest import register
from tests.job_fixtures import PROFILE, SDET_JD


@pytest.fixture(autouse=True)
def _reset_limits():
    sync_limiter.reset()


async def _setup_profile(client, auth):
    r = await client.put("/api/profile", headers=auth, json=PROFILE)
    assert r.status_code == 200, r.text


def _job(**kw):
    return {"title": "Senior SDET", "company": "PayCo Technologies", "location": "Bengaluru",
            "description": SDET_JD, "application_url": "https://payco.example/careers/sdet-1",
            "source": "manual", **kw}


async def test_import_scores_and_notifies(client, db, auth):
    await _setup_profile(client, auth)
    r = await client.post("/api/jobs/import", headers=auth, json=_job())
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["duplicate"] is False
    job = body["job"]
    assert job["score"] >= 85 and job["classification"] == "Highly Relevant"
    assert job["country"] == "India" and job["salary_max"] == 2800000
    assert "Playwright" in job["match"]["missing_preferred_skills"]
    notes = (await client.get("/api/notifications", headers=auth)).json()
    assert notes and notes[0]["title"].startswith("High-match job")
    dash = (await client.get("/api/analytics/dashboard", headers=auth)).json()
    assert dash["today"]["jobs_found"] == 1 and dash["today"]["relevant_jobs"] == 1
    assert dash["high_match_jobs"][0]["id"] == job["id"]
    actions = {a["action"] for a in (await client.get("/api/audit", headers=auth)).json()}
    assert {"job.discovered", "jd.analyzed", "job.match_calculated"} <= actions


async def test_duplicate_from_second_source_is_merged(client, db, auth):
    await _setup_profile(client, auth)
    first = (await client.post("/api/jobs/import", headers=auth, json=_job())).json()["job"]
    r = await client.post("/api/jobs/import", headers=auth, json=_job(
        title="Sr. SDET", company="PayCo", source="naukri",
        application_url="https://www.naukri.com/job-listings-sdet-payco-123"))
    assert r.json()["duplicate"] is True
    assert r.json()["job"]["id"] == first["id"]
    assert set(r.json()["job"]["sources"]) == {"manual", "naukri"}
    assert await db[c.JOBS].count_documents({}) == 1
    # Same source again is idempotent
    await client.post("/api/jobs/import", headers=auth, json=_job())
    detail = (await client.get(f"/api/jobs/{first['id']}", headers=auth)).json()
    assert len(detail["source_refs"]) == 2


async def test_list_filter_status_and_rematch(client, auth):
    await _setup_profile(client, auth)
    strong = (await client.post("/api/jobs/import", headers=auth, json=_job())).json()["job"]
    weak = (await client.post("/api/jobs/import", headers=auth, json=_job(
        title="Data Scientist", company="OtherCo", location="Berlin",
        description="Requirements\n- 6+ years of Python, Spark and machine learning research. " * 2,
        application_url=None))).json()["job"]
    listed = (await client.get("/api/jobs", headers=auth)).json()
    assert [j["id"] for j in listed["items"]] == [strong["id"], weak["id"]]
    assert (await client.get("/api/jobs", headers=auth, params={"min_score": 85})).json()["total"] == 1
    assert (await client.get("/api/jobs", headers=auth, params={"q": "othercorp"})).json()["total"] == 0
    assert (await client.get("/api/jobs", headers=auth, params={"q": "OtherCo"})).json()["total"] == 1

    r = await client.post(f"/api/jobs/{weak['id']}/status", headers=auth, json={"status": "archived"})
    assert r.json()["status"] == "archived"
    assert (await client.get("/api/jobs", headers=auth)).json()["total"] == 1
    assert (await client.get("/api/jobs", headers=auth, params={"status": "archived"})).json()["total"] == 1

    # Profile change -> rematch lowers the score (Java removed)
    await client.put("/api/profile", headers=auth, json={"skills": {"programming_languages": []}})
    assert (await client.post("/api/jobs/rematch-all", headers=auth)).json() == {"rescored": 1}
    after = (await client.get(f"/api/jobs/{strong['id']}", headers=auth)).json()
    assert after["score"] < strong["score"]
    assert "Java" in after["match"]["missing_required_skills"]


async def test_matching_config_roundtrip(client, auth):
    cfg = (await client.get("/api/jobs/matching/config", headers=auth)).json()
    assert cfg["skills"] == 35
    cfg["skills"] = 60
    assert (await client.put("/api/jobs/matching/config", headers=auth, json=cfg)).json()["skills"] == 60
    zero = {k: 0 for k in cfg}
    assert (await client.put("/api/jobs/matching/config", headers=auth, json=zero)).status_code == 422


async def test_recommended_resume(client, auth):
    await _setup_profile(client, auth)
    from tests.test_resumes import upload
    await upload(client, auth)
    job = (await client.post("/api/jobs/import", headers=auth, json=_job())).json()["job"]
    detail = (await client.get(f"/api/jobs/{job['id']}", headers=auth)).json()
    assert detail["recommended_resume"]["name"] == "Master"
    assert detail["recommended_resume"]["overlap"] >= 5


async def test_jobs_isolated_between_users(client, auth):
    job = (await client.post("/api/jobs/import", headers=auth, json=_job())).json()["job"]
    other = await register(client, email="ravi@example.com", name="Ravi")
    assert (await client.get(f"/api/jobs/{job['id']}", headers=other)).status_code == 404
    assert (await client.get("/api/jobs", headers=other)).json()["total"] == 0
    # Same posting imported by another user is not a duplicate of the first user's job
    assert (await client.post("/api/jobs/import", headers=other, json=_job())).json()["duplicate"] is False


# ------------------------------------------------------------------ official ATS APIs (mocked)

GH_BOARD = {"name": "PayCo"}
GH_JOBS = {"jobs": [
    {"id": 101, "title": "SDET II", "location": {"name": "Bengaluru, India"},
     "absolute_url": "https://boards.greenhouse.io/payco/jobs/101", "updated_at": "2026-09-20T10:00:00Z",
     "content": "&lt;h3&gt;Requirements&lt;/h3&gt;&lt;ul&gt;"
                "&lt;li&gt;4+ years with Java and Selenium&lt;/li&gt;"
                "&lt;li&gt;Rest Assured API testing&lt;/li&gt;&lt;/ul&gt;"},
    {"id": 102, "title": "Senior Product Designer", "location": {"name": "Remote"},
     "absolute_url": "https://boards.greenhouse.io/payco/jobs/102", "content": "Figma expert wanted. " * 5},
]}


def _mock(handler):
    def factory():
        return httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return factory


def _gh_handler(request: httpx.Request) -> httpx.Response:
    assert request.url.host == "boards-api.greenhouse.io"
    path = request.url.path
    if path == "/v1/boards/payco":
        return httpx.Response(200, json=GH_BOARD)
    if path == "/v1/boards/payco/jobs":
        return httpx.Response(200, json=GH_JOBS)
    if path == "/v1/boards/payco/jobs/101":
        return httpx.Response(200, json=GH_JOBS["jobs"][0])
    return httpx.Response(404)


async def test_greenhouse_sync_filters_by_target_role(client, db, auth, monkeypatch):
    monkeypatch.setattr(sources, "http_client", _mock(_gh_handler))
    await _setup_profile(client, auth)
    src = (await client.post("/api/jobs/sources", headers=auth,
                             json={"provider": "greenhouse", "board": "payco"})).json()
    r = await client.post(f"/api/jobs/sources/{src['id']}/sync", headers=auth)
    assert r.status_code == 200, r.text
    assert r.json() == {"fetched": 2, "new": 1, "duplicates": 0, "skipped_irrelevant": 1, "truncated": 0}
    jobs = (await client.get("/api/jobs", headers=auth)).json()["items"]
    assert (jobs[0]["title"], jobs[0]["company"], jobs[0]["source"]) == ("SDET II", "PayCo", "greenhouse")
    # Second sync: everything already known
    again = (await client.post(f"/api/jobs/sources/{src['id']}/sync", headers=auth)).json()
    assert again["new"] == 0 and again["duplicates"] == 1
    runs = (await client.get("/api/automation/runs", headers=auth)).json()
    assert runs[0]["agent_name"] == "job_discovery_agent" and runs[0]["status"] == "succeeded"
    listed = (await client.get("/api/jobs/sources", headers=auth)).json()
    assert listed[0]["last_result"]["duplicates"] == 1


async def test_sync_respects_pause(client, auth, monkeypatch):
    monkeypatch.setattr(sources, "http_client", _mock(_gh_handler))
    src = (await client.post("/api/jobs/sources", headers=auth,
                             json={"provider": "greenhouse", "board": "payco"})).json()
    await client.put("/api/automation/settings", headers=auth, json={"pauses": {"job_discovery": True}})
    r = await client.post(f"/api/jobs/sources/{src['id']}/sync", headers=auth)
    assert r.status_code == 423
    await client.put("/api/automation/settings", headers=auth, json={"pauses": {"job_discovery": False}})
    await client.post("/api/automation/pause-all", headers=auth)
    assert (await client.post(f"/api/jobs/sources/{src['id']}/sync", headers=auth)).status_code == 423


async def test_source_validation_and_duplicates(client, auth):
    bad = await client.post("/api/jobs/sources", headers=auth,
                            json={"provider": "greenhouse", "board": "../../etc"})
    assert bad.status_code == 422
    unsupported = await client.post("/api/jobs/sources", headers=auth,
                                    json={"provider": "linkedin", "board": "x"})
    assert unsupported.status_code == 422
    ok = await client.post("/api/jobs/sources", headers=auth, json={"provider": "lever", "board": "payco"})
    assert ok.status_code == 201
    dup = await client.post("/api/jobs/sources", headers=auth, json={"provider": "lever", "board": "PayCo"})
    assert dup.status_code == 409


async def test_import_url_greenhouse(client, auth, monkeypatch):
    monkeypatch.setattr(sources, "http_client", _mock(_gh_handler))
    r = await client.post("/api/jobs/import-url", headers=auth,
                          json={"url": "https://boards.greenhouse.io/payco/jobs/101?gh_src=abc"})
    assert r.status_code == 201, r.text
    job = r.json()["job"]
    assert job["title"] == "SDET II" and "Java" in job["skills"]
    assert job["source_refs"][0]["source_job_id"] == "101"


async def test_import_url_lever(client, auth, monkeypatch):
    posting = {"id": "abc-123", "text": "QA Automation Engineer",
               "categories": {"location": "Hyderabad", "commitment": "Full-time"},
               "descriptionPlain": "Build Playwright tests in TypeScript.", "lists": [
                   {"text": "Requirements", "content": "<li>3+ years of Playwright</li>"}],
               "hostedUrl": "https://jobs.lever.co/payco/abc-123", "workplaceType": "hybrid",
               "createdAt": 1790000000000}

    def handler(request):
        assert request.url.host == "api.lever.co"
        assert request.url.path == "/v0/postings/payco/abc-123"
        return httpx.Response(200, json=posting)

    monkeypatch.setattr(sources, "http_client", _mock(handler))
    r = await client.post("/api/jobs/import-url", headers=auth,
                          json={"url": "https://jobs.lever.co/payco/abc-123"})
    assert r.status_code == 201, r.text
    job = r.json()["job"]
    assert job["title"] == "QA Automation Engineer" and job["employment_type"] == "Full-time"
    assert job["analysis"]["experience_min"] == 3


async def test_import_url_refuses_platforms_that_prohibit_automation(client, auth, monkeypatch):
    def handler(request):  # must never be called
        raise AssertionError(f"unexpected request to {request.url}")

    monkeypatch.setattr(sources, "http_client", _mock(handler))
    for url in ("https://www.linkedin.com/jobs/view/123", "https://www.naukri.com/job-listings-x",
                "https://in.indeed.com/viewjob?jk=1"):
        r = await client.post("/api/jobs/import-url", headers=auth, json={"url": url})
        assert r.status_code == 422 and "paste" in r.json()["detail"].lower()
    other = await client.post("/api/jobs/import-url", headers=auth, json={"url": "https://example.com/job"})
    assert other.status_code == 422


async def test_board_errors_are_reported(client, auth, monkeypatch):
    monkeypatch.setattr(sources, "http_client", _mock(lambda r: httpx.Response(404)))
    src = (await client.post("/api/jobs/sources", headers=auth,
                             json={"provider": "ashby", "board": "missing"})).json()
    r = await client.post(f"/api/jobs/sources/{src['id']}/sync", headers=auth)
    assert r.status_code == 404
    runs = (await client.get("/api/automation/runs", headers=auth)).json()
    assert runs[0]["status"] == "failed" and runs[0]["errors"]
