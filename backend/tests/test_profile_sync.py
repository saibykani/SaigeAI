"""Phase 7: LinkedIn / Naukri profile optimization, change control and consistency."""

from app.database import collections as c
from tests.job_fixtures import PROFILE, SDET_JD
from tests.test_resumes import upload

PERF_JD = "Requirements\n- 4+ years with JMeter and Gatling load testing\n- Java, Jenkins, AWS\nNice to have\n- k6, Kubernetes"
FULL_PROFILE = {
    **PROFILE,
    "personal": {**PROFILE["personal"], "name": "Asha Rao", "current_company": "Acme Technologies"},
    "knowledge": {
        **PROFILE["knowledge"],
        "professional_summary": "QA engineer focused on test automation for payment products.",
        "experience": [{"company": "Acme Technologies", "title": "Senior QA Engineer", "domain": "Fintech",
                        "achievements": ["Reduced regression time by 40% using parallel execution"],
                        "technologies": ["TestNG"]}],
        "certifications": [{"name": "ISTQB Foundation Level"}],
    },
}


async def _seed(client, auth):
    assert (await client.put("/api/profile", headers=auth, json=FULL_PROFILE)).status_code == 200
    for i, (title, jd) in enumerate([("Senior SDET", SDET_JD), ("QA Automation Engineer", SDET_JD),
                                     ("Performance Test Engineer", PERF_JD)]):
        r = await client.post("/api/jobs/import", headers=auth,
                              json={"title": title, "company": f"Co{i}", "location": "Bengaluru", "description": jd})
        assert r.status_code == 201, r.text


async def test_snapshots_roundtrip_and_limits(client, auth):
    r = await client.put("/api/profile/linkedin", headers=auth, json={"headline": "QA Engineer", "skills": ["Java"]})
    assert r.status_code == 200 and r.json()["headline"] == "QA Engineer"
    assert (await client.get("/api/profile/linkedin", headers=auth)).json()["skills"] == ["Java"]
    too_long = await client.put("/api/profile/linkedin", headers=auth, json={"headline": "x" * 221})
    assert too_long.status_code == 422
    r = await client.put("/api/profile/naukri", headers=auth, json={"key_skills": ["Selenium"], "notice_period_days": 60})
    assert r.json()["notice_period_days"] == 60


async def test_run_creates_truthful_suggestions(client, db, auth):
    await _seed(client, auth)
    await client.put("/api/profile/linkedin", headers=auth, json={"headline": "QA Engineer", "skills": ["Java"]})
    await client.put("/api/profile/naukri", headers=auth,
                     json={"key_skills": ["Selenium"], "notice_period_days": 60, "resume_updated_on": "2020-01-01"})
    r = await client.post("/api/profile-sync/run", headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["jobs_analyzed"] == 3
    trend = {t["skill"]: t for t in body["trends"]}
    assert trend["Java"]["pct"] == 100.0 and trend["Java"]["candidate_has"] is True
    assert trend["Kubernetes"]["candidate_has"] is False  # demand the candidate can't claim
    assert "Kubernetes" in body["linkedin"]["skills_in_demand_you_lack"]

    changes = (await client.get("/api/profile-changes", headers=auth)).json()
    by = {(ch["platform"], ch["field"]): ch for ch in changes}
    head = by[("linkedin", "headline")]
    assert head["after"].startswith("Senior QA Engineer (5+ years)")
    assert "Java" in head["after"] and "Kubernetes" not in head["after"]
    assert head["approval_status"] == "USER_APPROVAL_REQUIRED" and head["action"] == "COPY_TO_LINKEDIN"
    assert head["validation"]["status"] == "PASSED" and len(head["source_jobs"]) == 3
    li_skills = by[("linkedin", "skills")]["after"]
    assert "JMeter" in li_skills and "Kubernetes" not in li_skills and "Gatling" not in li_skills
    about = by[("linkedin", "about")]["after"]
    assert "Reduced regression time by 40%" in about  # verified achievement, verbatim
    assert by[("naukri", "notice_period_days")]["after"] == 30
    assert ("naukri", "resume_updated_on") in by
    assert all(ch["validation"]["status"] == "PASSED" for ch in changes)
    notes = (await client.get("/api/notifications", headers=auth)).json()
    assert any("Profile optimization ready" in n["title"] for n in notes)

    # Re-running updates pending changes instead of duplicating them.
    await client.post("/api/profile-sync/run", headers=auth)
    assert len((await client.get("/api/profile-changes", headers=auth)).json()) == len(changes)


async def test_edit_is_truth_checked(client, auth):
    await _seed(client, auth)
    await client.post("/api/profile-sync/run", headers=auth)
    head = next(ch for ch in (await client.get("/api/profile-changes", headers=auth)).json()
                if ch["platform"] == "linkedin" and ch["field"] == "headline")
    bad = await client.put(f"/api/profile-changes/{head['id']}", headers=auth,
                           json={"after": "Senior QA Engineer | Kubernetes expert | 12 years"})
    assert bad.status_code == 422
    assert bad.json()["detail"]["status"] == "VALIDATION FAILED"
    ok = await client.put(f"/api/profile-changes/{head['id']}", headers=auth,
                          json={"after": "Senior QA Engineer | Java | Selenium | API Testing"})
    assert ok.status_code == 200 and ok.json()["after"].endswith("API Testing")


async def test_approve_apply_updates_snapshot_and_reject_is_remembered(client, auth):
    await _seed(client, auth)
    await client.put("/api/profile/linkedin", headers=auth, json={"headline": "QA Engineer"})
    await client.post("/api/profile-sync/run", headers=auth)
    changes = (await client.get("/api/profile-changes", headers=auth, params={"platform": "linkedin"})).json()
    head = next(ch for ch in changes if ch["field"] == "headline")
    otw = next(ch for ch in changes if ch["field"] == "open_to_work.titles")

    assert (await client.post(f"/api/profile-changes/{head['id']}/approve", headers=auth)).json()[
        "approval_status"] == "USER_APPROVED"
    applied = (await client.post(f"/api/profile-changes/{head['id']}/applied", headers=auth)).json()
    assert applied["applied_at"]
    assert (await client.get("/api/profile/linkedin", headers=auth)).json()["headline"] == head["after"]

    assert (await client.post(f"/api/profile-changes/{otw['id']}/reject", headers=auth)).json()[
        "approval_status"] == "USER_REJECTED"
    assert (await client.post(f"/api/profile-changes/{otw['id']}/applied", headers=auth)).status_code == 409
    await client.post("/api/profile-sync/run", headers=auth)
    again = (await client.get("/api/profile-changes", headers=auth,
                              params={"platform": "linkedin", "status": "USER_APPROVAL_REQUIRED"})).json()
    assert not any(ch["field"] == "open_to_work.titles" for ch in again)  # rejection respected
    assert not any(ch["field"] == "headline" for ch in again)  # already applied


async def test_resume_change_creates_new_version(client, auth):
    await _seed(client, auth)
    rid = (await upload(client, auth, content=b"ASHA RAO\nasha@example.com\nSKILLS\nJava\n")).json()["id"]
    await client.post("/api/profile-sync/run", headers=auth)
    ch = next(ch for ch in (await client.get("/api/profile-changes", headers=auth, params={"platform": "resume"})).json())
    assert "Selenium" in ch["after"] and ch["action"] == "UPDATE_MASTER_RESUME"
    await client.post(f"/api/profile-changes/{ch['id']}/applied", headers=auth)
    detail = (await client.get(f"/api/resumes/{rid}", headers=auth)).json()
    assert detail["version_count"] == 2
    assert "Selenium" in detail["current_version"]["parsed"]["skills"]
    assert detail["current_version"]["source"] == "optimization"


async def test_consistency_check(client, auth):
    await _seed(client, auth)
    await client.put("/api/profile/naukri", headers=auth, json={
        "current_designation": "QA Lead", "total_experience_years": 5, "notice_period_days": 90,
        "key_skills": ["Java", "SQL", "Selenium", "Rest Assured", "Postman", "Jenkins", "JMeter"]})
    cons = (await client.get("/api/profile-sync/overview", headers=auth)).json()["consistency"]
    fields = {ch["field"]: ch for ch in cons["checks"]}
    assert fields["Designation"]["consistent"] is False and fields["Designation"]["mismatched"] == ["naukri"]
    assert fields["Total experience"]["consistent"] is True
    assert fields["Notice period (days)"]["consistent"] is False
    assert fields["Skills on naukri"]["consistent"] is True
    assert 0 < cons["score"] < 100
    assert {d["field"] for d in cons["discrepancies"]} >= {"Designation", "Notice period (days)"}


async def test_pause_blocks_profile_agent(client, auth):
    await client.put("/api/automation/settings", headers=auth, json={"pauses": {"profile_updates": True}})
    assert (await client.post("/api/profile-sync/run", headers=auth)).status_code == 423


async def test_platform_update_endpoint_is_honest(client, auth):
    r = (await client.post("/api/profile/naukri/update", headers=auth)).json()
    assert r["status"] == "MANUAL_ACTION_REQUIRED" and r["action"] == "COPY_TO_NAUKRI"


async def test_blocked_proposals_never_surface(client, db, auth):
    """A proposal that fails truth validation is dropped and audited, never shown."""
    from app.profiles import sync_service as svc
    from app.profiles.service import get_profile

    await _seed(client, auth)
    me = (await client.get("/api/auth/me", headers=auth)).json()
    profile = await get_profile(db, me["id"])
    created = await svc.upsert_changes(db, me["id"], "linkedin", [
        {"field": "headline", "before": None, "after": "Kubernetes Architect with 15 years", "reason": "x",
         "confidence": 0.5}], profile, [])
    assert created == 0
    assert await db[c.PROFILE_CHANGES].count_documents({"after": "Kubernetes Architect with 15 years"}) == 0
    assert await db[c.AUDIT_LOGS].count_documents({"action": "profile_change.blocked"}) == 1
