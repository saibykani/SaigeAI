"""Extension v2: side-panel endpoints (analyze JD, generate resume, application email draft, company contacts, save draft)."""

from app.database import collections as c
from tests.job_fixtures import PROFILE, SDET_JD

POST = ("We're hiring! SDET at Acme Labs, Bengaluru. 3+ years with Selenium, Java and API testing. "
        "Contact: Priya Sharma. Send your CV to careers@acmelabs.com with subject: SDET Application - Bengaluru")


async def _pat(client, auth) -> dict:
    r = await client.post("/api/auth/tokens", headers=auth, json={"name": "Chrome extension"})
    return {"Authorization": f"Bearer {r.json()['token']}"}


async def _ready(client, auth) -> dict:
    await client.put("/api/profile", headers=auth, json=PROFILE)
    return await _pat(client, auth)


async def test_v2_endpoints_need_a_pat(client, auth):
    for method, path in (("post", "/api/ext/analyze-jd"), ("post", "/api/ext/generate-resume"), ("post", "/api/ext/draft-application-email"),
                         ("get", "/api/ext/company-contacts"), ("post", "/api/ext/save-draft")):
        assert (await getattr(client, method)(path, headers=auth)).status_code == 401, path


async def test_analyze_jd_detects_post_and_saves_nothing(client, auth, db):
    pat = await _ready(client, auth)
    r = (await client.post("/api/ext/analyze-jd", headers=pat, json={"text": POST})).json()
    assert r["emails"] == ["careers@acmelabs.com"] and r["is_hiring_post"] and r["contact_first_name"] == "Priya"
    assert r["company"] and "Selenium" in r["have"] and 0 <= r["score"] <= 100
    jd = (await client.post("/api/ext/analyze-jd", headers=pat, json={"text": SDET_JD, "title": "Senior SDET", "company": "PayCo"})).json()
    assert not jd["is_hiring_post"] and "Selenium" in jd["have"] and "Kubernetes" in jd["missing"] and jd["eligibility"]
    assert await db[c.JOBS].count_documents({}) == 0 and await db[c.RESUMES].count_documents({}) == 0


async def test_generate_resume_returns_downloads(client, auth):
    pat = await _ready(client, auth)
    r = await client.post("/api/ext/generate-resume", headers=pat, json={"text": SDET_JD, "title": "Senior SDET", "company": "PayCo"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert set(body["downloads"]) == {"pdf", "docx"}
    pdf = await client.get(body["downloads"]["pdf"], headers=pat)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")


async def test_application_email_is_truth_checked_and_never_sent(client, auth, db):
    pat = await _ready(client, auth)
    r = await client.post("/api/ext/draft-application-email", headers=pat, json={"text": POST, "title": "SDET"})
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["to"] == "careers@acmelabs.com" and b["subject"] == "SDET Application - Bengaluru"
    assert b["body"].startswith("Hi Priya,") and "Asha Rao" in b["body"] and b["validation"]["status"] == "PASSED"
    assert b["gmail_compose"].startswith("https://mail.google.com/") and b["mailto"].startswith("mailto:careers")
    assert b["downloads"]["pdf"] and await db[c.OUTREACH].count_documents({}) == 0
    assert await db[c.AGENT_RUNS].count_documents({"agent_name": "extension_application_email"}) == 1
    again = await client.post("/api/ext/draft-application-email", headers=pat,
                              json={"text": POST, "title": "SDET", "resume_id": b["resume_id"], "to": "hr@acmelabs.com"})
    assert again.json()["resume_id"] == b["resume_id"] and again.json()["to"] == "hr@acmelabs.com"
    assert (await client.post("/api/ext/draft-application-email", headers=pat,
                              json={"text": POST, "resume_id": "nope"})).status_code == 404


async def test_company_contacts_only_own_data_with_caps(client, auth, db):
    pat = await _ready(client, auth)
    mine = await client.post("/api/recruiters", headers=auth, json={"name": "Priya Sharma", "company": "Acme Labs", "email": "priya@acmelabs.com"})
    assert mine.status_code in (200, 201), mine.text
    await client.post("/api/recruiters", headers=auth, json={"name": "Raj", "company": "Other Co", "email": "raj@other.com"})
    r = (await client.get("/api/ext/company-contacts", headers=pat, params={"company": "Acme Labs Pvt Ltd"})).json()
    assert [x["email"] for x in r["contacts"]] == ["priya@acmelabs.com"]
    assert r["caps"]["daily_limit"] <= 10 and r["caps"]["company_week_cap"] == 3 and r["caps"]["can_send_more"]
    assert (await client.get("/api/ext/company-contacts", headers=pat, params={"company": "Nobody"})).json()["contacts"] == []


async def test_save_draft_waits_for_approval(client, auth, db):
    pat = await _ready(client, auth)
    r = await client.post("/api/ext/save-draft", headers=pat, json={"company": "Acme Labs", "email": "careers@acmelabs.com", "kind": "cold"})
    assert r.status_code == 201, r.text
    d = r.json()["draft"]
    assert d["status"] == "draft" and d["validation"]["status"] == "PASSED" and d["gmail_compose"]
    doc = await db[c.OUTREACH].find_one({"_id": d["id"]})
    assert doc["sent_at"] is None and doc["approved_at"] is None
    assert await db[c.RECRUITER_CONTACTS].count_documents({"email": "careers@acmelabs.com"}) == 1
    # reusing the contact + edited wording that invents a skill is rejected by the truth guard
    bad = await client.post("/api/ext/save-draft", headers=pat, json={
        "company": "Acme Labs", "email": "careers@acmelabs.com", "subject": "Hello",
        "body": "I improved coverage by 85% and cut release time by 60% at Google."})
    assert bad.status_code == 422
    assert await db[c.OUTREACH].count_documents({"status": "draft"}) == 1  # the failed attempt left nothing behind
    ok = await client.post("/api/ext/save-draft", headers=pat, json={
        "company": "Acme Labs", "email": "careers@acmelabs.com", "subject": "SDET role",
        "body": "Hi, I work with Selenium and Java. Thanks, Asha Rao"})
    assert ok.status_code == 201 and ok.json()["draft"]["subject"] == "SDET role"
    assert (await client.post("/api/ext/save-draft", headers=pat, json={"company": "Acme"})).status_code == 422
