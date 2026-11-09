"""Career jobs: company career-portal scan (Greenhouse, Workday, Amazon), filters, fit + resume advice,
closing postings, save to Jobs, email digest, settings and the daily scheduler job."""

from datetime import UTC, datetime

import pytest

from app.careers import catalog, providers, service
from app.database import collections as c
from app.email import smtp
from tests.job_fixtures import PROFILE, SDET_JD
from tests.test_discover_send import FakeResponse, FakeSMTP
from tests.test_gmail_imap import FakeIMAP

ROLES_JD = SDET_JD.replace("Location: Bengaluru (Hybrid). Full-time.", "")


STRIPE_JOBS = [
    {"id": 77, "title": "Software Engineer in Test", "location": {"name": "Bengaluru, India"},
     "absolute_url": "https://stripe.example/77", "first_published": "2026-11-01T00:00:00Z"},
    {"id": 78, "title": "Account Executive", "location": {"name": "Bengaluru, India"}, "absolute_url": "https://stripe.example/78"},
    {"id": 79, "title": "QA Automation Engineer", "location": {"name": "Berlin, Germany"}, "absolute_url": "https://stripe.example/79"},
]


class CareerClient:
    """Canned career APIs: Stripe (Greenhouse), NVIDIA (Workday), Amazon Jobs. Cloudflare is down."""

    stripe_jobs: list[dict] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, url, params=None):
        if "greenhouse.io/v1/boards/stripe/jobs/" in url:
            return FakeResponse({"content": "&lt;p&gt;" + ROLES_JD + "&lt;/p&gt;"})
        if "greenhouse.io/v1/boards/stripe/jobs" in url:
            return FakeResponse({"jobs": CareerClient.stripe_jobs})
        if "myworkdayjobs.com/wday/cxs/nvidia/NVIDIAExternalCareerSite/job/" in url:
            return FakeResponse({"jobPostingInfo": {"jobDescription": f"<p>{ROLES_JD}</p>", "location": "India, Hyderabad",
                                                    "startDate": "2026-11-05", "timeType": "Full time",
                                                    "externalUrl": "https://nvidia.wd5.myworkdayjobs.com/job/sdet_JR1"}})
        if "amazon.jobs" in url:
            assert params["base_query"] in ("SDET", "QA Automation Engineer")
            return FakeResponse({"jobs": [{"id_icims": "555", "title": "SDET II, Payments", "normalized_location": "Hyderabad, Telangana, IND",
                                           "job_path": "/en/jobs/555/sdet-ii", "posted_date": "November  2, 2026",
                                           "description": "Build test automation.", "basic_qualifications": "- 3+ years of Java<br/>- Selenium",
                                           "job_schedule_type": "full-time"}]})
        raise RuntimeError("unreachable")

    async def post(self, url, json=None):
        assert "nvidia.wd5.myworkdayjobs.com/wday/cxs/nvidia/NVIDIAExternalCareerSite/jobs" in url
        if json["offset"]:
            return FakeResponse({"jobPostings": []})
        return FakeResponse({"total": 2, "jobPostings": [
            {"title": "Senior SDET", "externalPath": "/job/India-Hyderabad/Senior-SDET_JR1", "locationsText": "India, Hyderabad",
             "postedOn": "Posted 3 Days Ago", "bulletFields": ["JR1"]},
            {"title": "Chip Designer", "externalPath": "/job/US-Santa-Clara/Chip_JR2", "locationsText": "US, CA, Santa Clara",
             "postedOn": "Posted Today", "bulletFields": ["JR2"]}]})


@pytest.fixture
def careers(monkeypatch):
    CareerClient.stripe_jobs = list(STRIPE_JOBS)
    monkeypatch.setattr(providers, "http_client", lambda: CareerClient())
    pool = [catalog.BY_ID[i] for i in ("stripe", "nvidia", "amazon", "cloudflare")]
    monkeypatch.setattr(catalog, "select", lambda *a, **k: list(pool))


async def _setup(client, auth):
    r = await client.put("/api/profile", headers=auth, json=PROFILE)
    assert r.status_code == 200, r.text


def test_catalogue_and_portal_links():
    assert catalog.BY_ID["meta"].provider == "portal" and not catalog.BY_ID["meta"].is_api
    link = catalog.portal_link(catalog.BY_ID["google"], "QA Engineer", "Hyderabad")
    assert link.startswith("https://www.google.com/about/careers/") and "q=QA+Engineer" in link and "location=Hyderabad" in link
    faang = {co.id for co in catalog.select(["faang"])}
    assert {"amazon", "meta", "google", "apple", "netflix", "microsoft"} <= faang
    assert all(co.is_api for co in catalog.select(["faang"], api_only=True))
    assert providers.workday_posted("Posted 30+ Days Ago") and providers.amazon_posted("November  2, 2026") == "2026-11-02"
    assert service.fit_for(85) == "strong" and service.fit_for(70) == "good" and service.fit_for(55) == "stretch"


async def test_scan_filters_advice_save_and_closing(client, auth, db, careers):
    await _setup(client, auth)
    r = await client.post("/api/careers/scan", headers=auth, json={})
    assert r.status_code == 200, r.text
    rep = r.json()
    by = {x["id"]: x for x in rep["companies"]}
    assert by["cloudflare"]["status"] == "error" and by["stripe"]["status"] == "ok" and rep["status"] == "partial"
    assert by["nvidia"]["found"] == 1 and by["amazon"]["found"] == 1 and by["stripe"]["found"] == 2  # role filter drops non-QA titles
    assert rep["new"] == 4 and await db[c.CAREER_JOBS].count_documents({}) == 4
    assert await db[c.AGENT_RUNS].count_documents({"agent_name": "career_portal_scan"}) == 1

    jobs = (await client.get("/api/careers/jobs", headers=auth)).json()
    assert jobs["total"] == 4 and jobs["items"][0]["score"] >= jobs["items"][-1]["score"]
    assert {f["value"] for f in jobs["facets"]["companies"]} == {"stripe", "nvidia", "amazon"}
    assert "description" not in jobs["items"][0] and jobs["items"][0]["url"]

    india = (await client.get("/api/careers/jobs", headers=auth, params={"countries": "India"})).json()
    assert india["total"] == 3 and all(i["country"] == "India" for i in india["items"])
    hyd = (await client.get("/api/careers/jobs", headers=auth, params={"location": "hyderabad", "companies": "nvidia"})).json()
    assert [i["title"] for i in hyd["items"]] == ["Senior SDET"]
    assert (await client.get("/api/careers/jobs", headers=auth, params={"scopes": "abroad"})).json()["total"] == 1
    assert (await client.get("/api/careers/jobs", headers=auth, params={"tiers": "faang"})).json()["total"] == 1
    assert (await client.get("/api/careers/jobs", headers=auth, params={"q": "payments"})).json()["total"] == 1

    jid = next(i["id"] for i in india["items"] if i["company"] == "Stripe")
    d = (await client.get(f"/api/careers/jobs/{jid}", headers=auth)).json()
    assert d["fit"] in service.FITS and d["description"] and d["resume_changes"]
    kinds = {x["kind"] for x in d["resume_changes"]}
    assert "info" in kinds  # no resume uploaded yet
    gap = next((x for x in d["resume_changes"] if x["kind"] == "nice"), None)
    assert gap is None or all(s not in ("Java", "Selenium") for s in gap["items"])  # never flags skills she has

    s1 = (await client.post(f"/api/careers/jobs/{jid}/save", headers=auth)).json()
    s2 = (await client.post(f"/api/careers/jobs/{jid}/save", headers=auth)).json()
    assert s1["job_id"] == s2["job_id"] and s2["duplicate"] and await db[c.JOBS].count_documents({}) == 1

    # Stripe removes one posting: the next scan closes it; failing Cloudflare closes nothing.
    CareerClient.stripe_jobs = [j for j in CareerClient.stripe_jobs if j["id"] != 79]
    rep2 = (await client.post("/api/careers/scan", headers=auth, json={})).json()
    assert rep2["new"] == 0 and rep2["closed"] == 1
    assert (await client.get("/api/careers/jobs", headers=auth)).json()["total"] == 3
    assert (await client.get("/api/careers/jobs", headers=auth, params={"include_closed": True})).json()["total"] == 4


async def test_blocked_company_and_missing_roles(client, auth, db, careers):
    r = await client.post("/api/careers/scan", headers=auth, json={})
    assert r.json()["status"] == "needs_profile"
    await _setup(client, auth)
    await client.put("/api/automation/settings", headers=auth, json={"blocked_companies": ["Amazon"]})
    await client.post("/api/careers/scan", headers=auth, json={})
    assert await db[c.CAREER_JOBS].count_documents({"company": "Amazon"}) == 0


async def test_settings_portals_and_digest_email(client, auth, db, careers, monkeypatch):
    from app.email import imap

    FakeSMTP.sent = []
    monkeypatch.setattr(smtp, "SMTP_FACTORY", FakeSMTP)
    monkeypatch.setattr(imap, "IMAP_FACTORY", FakeIMAP)
    await _setup(client, auth)
    bad = await client.put("/api/careers/settings", headers=auth, json={"tiers": ["nope"]})
    assert bad.status_code == 422
    ok = await client.put("/api/careers/settings", headers=auth, json={"min_score": 0, "locations": ["Hyderabad", "Bengaluru"]})
    assert ok.status_code == 200 and ok.json()["min_score"] == 0
    p = (await client.get("/api/careers/portals", headers=auth)).json()
    meta = next(x for x in p["companies"] if x["id"] == "meta")
    assert not meta["api"] and meta["role_links"][0]["url"].startswith("https://www.metacareers.com/jobs?q=SDET")

    await client.post("/api/careers/scan", headers=auth, json={})
    # Without an App Password the digest becomes an in-app notification.
    no = (await client.post("/api/careers/digest", headers=auth, json={})).json()
    assert no["sent"] == 0 and "App Password" in no["error"] and not FakeSMTP.sent

    await client.post("/api/auth/connect/gmail-app-password", headers=auth, json={"email": "asha@gmail.com", "app_password": "abcdefghijklmnop"})
    sent = (await client.post("/api/careers/digest", headers=auth, json={})).json()
    assert sent["sent"] == 3 and sent["to"] == "asha@example.com"  # Berlin is filtered out by location
    msg = FakeSMTP.sent[-1]
    assert "career pages" in msg["Subject"] and msg["To"] == "asha@example.com"
    html = msg.get_body(("html",)).get_content()
    assert "Senior SDET" in html and "nvidia.wd5.myworkdayjobs.com" in html
    again = (await client.post("/api/careers/digest", headers=auth, json={})).json()
    assert again["sent"] == 0  # each posting is emailed once
    assert await db[c.AUDIT_LOGS].count_documents({"action": "careers.digest_sent"}) == 1


async def test_scheduler_runs_career_scan(client, auth, db, careers):
    from app.scheduler import service as sched

    await _setup(client, auth)
    me = await db[c.USERS].find_one({"email": "asha@example.com"})
    res = await sched.run_for_user(db, me["_id"], datetime(2026, 11, 9, 6, 0, tzinfo=UTC), only="career_scan", trigger="manual")
    assert res[0]["status"] == "succeeded", res
    assert res[0]["result"]["found"] == 4 and "digest" in res[0]["result"]


class MultiClient:
    """Canned SmartRecruiters, SuccessFactors RSS and Oracle Recruiting Cloud responses."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, url, params=None, headers=None):
        if "api.smartrecruiters.com/v1/companies/Experian/postings/9" in url:
            return FakeResponse({"jobAd": {"sections": {"jobDescription": {"text": f"<p>{ROLES_JD}</p>"}}}})
        if "api.smartrecruiters.com/v1/companies/Experian/postings" in url:
            assert params["country"] == "in"
            return FakeResponse({"content": [{"id": "9", "name": "Senior SDET", "releasedDate": "2026-11-05T00:00:00Z",
                                              "location": {"fullLocation": "Hyderabad, , India", "remote": False},
                                              "typeOfEmployment": {"label": "Full-time"}}]})
        if "careers.wipro.com/services/rss/job/" in url:
            assert "xml" in headers["Accept"]
            rss = ("<rss><channel><item><title><![CDATA[QA Automation Engineer (Hyderabad, IND-36, IN, 500032)]]></title>"
                   f"<description><![CDATA[<p>{ROLES_JD}</p>]]></description><pubDate>Mon, 09 Nov 2026 2:00:00 GMT</pubDate>"
                   "<link>https://careers.wipro.com/job/Hyderabad-QA/123/?feedId=null&amp;utm_source=J2WRSS</link></item>"
                   "<item><title>Sales Manager (Pune, IN)</title><link>https://careers.wipro.com/job/x/9/</link></item></channel></rss>")

            class R(FakeResponse):
                content = rss.encode()
            return R({})
        if "jpmc.fa.oraclecloud.com" in url and "recruitingCEJobRequisitionDetails" in url:
            return FakeResponse({"items": [{"ExternalDescriptionStr": f"<p>{ROLES_JD}</p>"}]})
        if "jpmc.fa.oraclecloud.com" in url:
            assert "siteNumber=CX_1001" in url and "keyword=%22" in url
            return FakeResponse({"items": [{"requisitionList": [{"Id": "210", "Title": "SDET - Payments", "PostedDate": "2026-11-03",
                                                                 "PrimaryLocation": "Hyderabad, Telangana, India"}]}]})
        raise RuntimeError("unreachable")


async def test_smartrecruiters_successfactors_and_oracle_fetchers():
    roles = ["SDET", "QA Automation Engineer"]
    async with MultiClient() as cl:
        sr = await providers.fetch(cl, catalog.BY_ID["experian"], roles, "India")
        sf = await providers.fetch(cl, catalog.BY_ID["wipro"], roles)
        orc = await providers.fetch(cl, catalog.BY_ID["jpmorgan"], roles)
    assert sr[0]["location"] == "Hyderabad, India" and sr[0]["url"] == "https://jobs.smartrecruiters.com/Experian/9"
    assert "Selenium" in sr[0]["description"]
    assert len(sf) == 1 and sf[0]["title"] == "QA Automation Engineer" and sf[0]["location"] == "Hyderabad, IN"
    assert sf[0]["url"] == "https://careers.wipro.com/job/Hyderabad-QA/123/" and sf[0]["posted"] == "2026-11-09"
    assert orc[0]["url"].endswith("/sites/CX_1001/job/210") and "Selenium" in orc[0]["description"]
    assert {"infosys", "tcs", "cognizant", "cgi", "hcltech", "wipro", "capgemini", "accenture"} <= set(catalog.BY_ID)
