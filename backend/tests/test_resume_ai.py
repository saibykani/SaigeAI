"""Phase 3: JD-tailored resumes, ATS checks, cover letters and DOCX export."""

import io

from docx import Document

from app.agents.llm import set_provider
from app.database import collections as c
from tests.job_fixtures import SDET_JD
from tests.test_profile_sync import FULL_PROFILE
from tests.test_resumes import upload

PROFILE = {
    **FULL_PROFILE,
    "personal": {**FULL_PROFILE["personal"], "email": "asha@example.com", "phone": "+91 98765 43210"},
    "knowledge": {
        **FULL_PROFILE["knowledge"],
        "experience": [{
            "company": "Acme Technologies", "title": "Senior QA Engineer", "start_date": "Jan 2022", "is_current": True,
            "responsibilities": ["Mentored two junior testers", "Built Selenium framework with Java and TestNG",
                                 "Automated REST API tests with Rest Assured"],
            "achievements": ["Reduced regression time by 40% using parallel execution on Jenkins"],
            "technologies": ["TestNG"]}],
        "projects": [{"name": "Internal Wiki", "highlights": ["Wrote onboarding docs"]},
                     {"name": "Payments Regression Suite", "highlights": ["Selenium + Rest Assured suite for UPI"],
                      "technologies": ["Selenium", "Rest Assured"]}],
    },
}


async def _job(client, auth, jd=SDET_JD, title="Senior SDET"):
    r = await client.post("/api/jobs/import", headers=auth,
                          json={"title": title, "company": "PayCo", "location": "Bengaluru", "description": jd})
    return r.json()["job"]


async def test_tailor_requires_profile(client, auth):
    job = await _job(client, auth)
    r = await client.post(f"/api/jobs/{job['id']}/tailor-resume", headers=auth, json={})
    assert r.status_code == 409


async def test_tailored_resume_orders_verified_facts_and_never_adds_gaps(client, db, auth):
    await client.put("/api/profile", headers=auth, json=PROFILE)
    job = await _job(client, auth)
    r = await client.post(f"/api/jobs/{job['id']}/tailor-resume", headers=auth, json={})
    assert r.status_code == 201, r.text
    body = r.json()
    parsed = body["resume"]["current_version"]["parsed"]
    assert body["validation"]["status"] == "PASSED" and body["engine"] == "deterministic"
    assert body["resume"]["job_id"] == job["id"] and body["resume"]["kind"] == "Tailored Resume"

    # JD-required verified skills lead; gaps (Playwright, Cypress, Kubernetes) never appear
    assert parsed["skills"][:2] == ["Java", "Selenium"]
    for gap in ("Playwright", "Cypress", "Kubernetes"):
        assert gap not in parsed["skills"]
    # Most relevant bullet first; irrelevant one sinks
    resp = parsed["experience"][0]["responsibilities"]
    assert resp[-1] == "Mentored two junior testers"
    assert parsed["projects"][0]["name"] == "Payments Regression Suite"
    changes = body["resume"]["current_version"]["changes"]
    assert any("Skills reordered" in ch for ch in changes)
    assert any(ch.startswith("Not added") and "Agile" in ch for ch in changes)  # required but unverified
    assert "Agile" not in parsed["skills"]

    ats = body["ats"]
    assert 0 < ats["score"] <= 100 and "Agile" in ats["missing_required"]
    assert {"check": "Email present", "passed": True} in ats["checks"]
    version = await db[c.RESUME_VERSIONS].find_one({"_id": body["resume"]["current_version_id"]})
    assert version["job_id"] == job["id"] and version["source"] == "tailored"


async def test_tailor_uses_base_resume_link_and_docx_export(client, auth):
    await client.put("/api/profile", headers=auth, json=PROFILE)
    base_id = (await upload(client, auth)).json()["id"]
    job = await _job(client, auth)
    body = (await client.post(f"/api/jobs/{job['id']}/tailor-resume", headers=auth, json={"base_resume_id": base_id})).json()
    assert body["resume"]["base_resume_id"] == base_id
    rid = body["resume"]["id"]
    dl = await client.get(f"/api/resumes/{rid}/export.docx", headers=auth)
    assert dl.status_code == 200
    assert dl.headers["content-type"].startswith("application/vnd.openxmlformats")
    text = "\n".join(p.text for p in Document(io.BytesIO(dl.content)).paragraphs)
    assert "Asha Rao" in text and "PROFESSIONAL SUMMARY" in text and "Reduced regression time by 40%" in text
    docs = (await client.get(f"/api/jobs/{job['id']}/documents", headers=auth)).json()
    assert docs["resumes"][0]["id"] == rid and docs["resumes"][0]["ats"]["score"] > 0


async def test_ats_check_for_any_resume(client, auth):
    await client.put("/api/profile", headers=auth, json=PROFILE)
    job = await _job(client, auth)
    rid = (await upload(client, auth)).json()["id"]
    r = await client.post(f"/api/jobs/{job['id']}/ats-check", headers=auth, json={"resume_id": rid})
    assert r.status_code == 200
    assert "Java" in r.json()["matched_keywords"]


async def test_cover_letter_generation_edit_and_guard(client, auth):
    await client.put("/api/profile", headers=auth, json=PROFILE)
    job = await _job(client, auth)
    r = await client.post(f"/api/jobs/{job['id']}/cover-letter", headers=auth)
    assert r.status_code == 201, r.text
    letter = r.json()
    assert letter["text"].startswith("Dear Hiring Team at PayCo,")
    assert "Senior SDET position at PayCo" in letter["text"]
    assert "Reduced regression time by 40%" in letter["text"] and "Asha Rao" in letter["text"]
    assert letter["validation"]["status"] == "PASSED"

    bad = await client.put(f"/api/cover-letters/{letter['id']}", headers=auth,
                           json={"text": letter["text"] + " I also have 12 years of Kubernetes experience."})
    assert bad.status_code == 422 and bad.json()["detail"]["status"] == "VALIDATION FAILED"
    ok = await client.put(f"/api/cover-letters/{letter['id']}", headers=auth,
                          json={"text": letter["text"].replace("Thank you", "Many thanks")})
    assert ok.status_code == 200 and "Many thanks" in ok.json()["text"]
    dl = await client.get(f"/api/cover-letters/{letter['id']}/docx", headers=auth)
    assert dl.status_code == 200 and len(dl.content) > 1000


class _LyingProvider:
    """An LLM that embellishes: its output must be discarded by the truth guard."""
    name = "fake"

    async def extract(self, *, system, prompt, schema):
        field = next(iter(schema.model_fields))
        return schema(**{field: "Seasoned Kubernetes architect with 15 years at Google who boosted revenue 300%."})


class _HonestProvider:
    name = "fake"

    async def extract(self, *, system, prompt, schema):
        field = next(iter(schema.model_fields))
        return schema(**{field: "Senior QA Engineer building Selenium and Rest Assured automation in Java."})


async def test_llm_embellishment_is_rejected_and_honest_polish_kept(client, auth):
    await client.put("/api/profile", headers=auth, json=PROFILE)
    job = await _job(client, auth)
    set_provider(_LyingProvider())
    try:
        body = (await client.post(f"/api/jobs/{job['id']}/tailor-resume", headers=auth, json={})).json()
        letter = (await client.post(f"/api/jobs/{job['id']}/cover-letter", headers=auth)).json()
    finally:
        set_provider(None)
    summary = body["resume"]["current_version"]["parsed"]["summary"]
    assert "Kubernetes" not in summary and "Google" not in summary and body["engine"] == "deterministic"
    assert "Kubernetes" not in letter["text"] and letter["engine"] == "deterministic"

    set_provider(_HonestProvider())
    try:
        body2 = (await client.post(f"/api/jobs/{job['id']}/tailor-resume", headers=auth, json={})).json()
    finally:
        set_provider(None)
    assert body2["engine"] == "deterministic+fake"
    assert body2["resume"]["current_version"]["parsed"]["summary"].startswith("Senior QA Engineer building")


async def test_other_users_cannot_access_documents(client, auth):
    from tests.conftest import register
    await client.put("/api/profile", headers=auth, json=PROFILE)
    job = await _job(client, auth)
    letter = (await client.post(f"/api/jobs/{job['id']}/cover-letter", headers=auth)).json()
    other = await register(client, email="ravi@example.com", name="Ravi")
    assert (await client.get(f"/api/cover-letters/{letter['id']}", headers=other)).status_code == 404
    assert (await client.post(f"/api/jobs/{job['id']}/cover-letter", headers=other)).status_code == 404
