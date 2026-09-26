"""Phase 4: application engine, question answering, interviews."""

from datetime import UTC, date, datetime, timedelta

import pytest

from app.applications.answers import answer_question, years_with_skill
from app.database import collections as c
from app.schemas.profile import Profile
from tests.job_fixtures import SDET_JD
from tests.test_resume_ai import PROFILE

TODAY = date(2026, 9, 26)


@pytest.fixture
def profile() -> Profile:
    data = {**PROFILE,
            "personal": {**PROFILE["personal"], "current_ctc": 1500000, "ctc_currency": "INR",
                         "current_location": "Hyderabad", "github_url": "https://github.com/asha"},
            "preferences": {**PROFILE["preferences"], "relocation": True}}
    data["knowledge"] = {**data["knowledge"], "experience": [
        {**data["knowledge"]["experience"][0], "start_date": "Jan 2022", "is_current": True},
        {"company": "Globex", "title": "QA Engineer", "start_date": "Jul 2019", "end_date": "Dec 2021",
         "responsibilities": ["Manual and Selenium regression testing"], "technologies": ["JIRA"]}]}
    return Profile.model_validate(data)


# ------------------------------------------------------------------ question answering (spec 20)

def test_years_with_skill_sums_dated_roles(profile):
    # Selenium: Jan 2022 -> Sep 2026 (4y8m) + Jul 2019 -> Dec 2021 (2y5m) = 7y1m -> 7.0
    assert years_with_skill(profile, "Selenium", TODAY) == 7.0
    assert years_with_skill(profile, "Rest Assured", TODAY) == 4.5  # only the current role
    assert years_with_skill(profile, "Kubernetes", TODAY) is None


@pytest.mark.parametrize(("question", "answer", "confidence", "status"), [
    ("How many years of Selenium experience do you have?", "7", "HIGH", "ANSWERED"),
    ("How many years of total experience?", "5", "HIGH", "ANSWERED"),
    ("What is your notice period?", "30 days", "HIGH", "ANSWERED"),
    ("Do you have experience with Rest Assured?", "Yes", "HIGH", "ANSWERED"),
    ("Are you willing to relocate?", "Yes", "HIGH", "ANSWERED"),
    ("Please share your GitHub profile", "https://github.com/asha", "HIGH", "ANSWERED"),
    ("What is your highest qualification?", "B.Tech, JNTU", "HIGH", "ANSWERED"),
    ("Are you ISTQB Foundation Level certified?", "Yes", "HIGH", "ANSWERED"),
])
def test_answers_from_knowledge_base(profile, question, answer, confidence, status):
    a = answer_question(question, profile, TODAY)
    assert (a["answer"], a["confidence"], a["status"]) == (answer, confidence, status)
    assert "Knowledge Base" in a["source"]


@pytest.mark.parametrize("question", [
    "How many years of Kubernetes experience do you have?",
    "Do you have experience with Playwright?",
    "Are you AWS certified?",
    "Why do you want to work here?",
    "Do you require visa sponsorship?",
])
def test_never_fabricates_review_required(profile, question):
    a = answer_question(question, profile, TODAY)
    assert a["answer"] is None and a["status"] == "REVIEW_REQUIRED" and a["confidence"] == "LOW"


def test_salary_answers_are_sensitive_and_need_review(profile):
    exp = answer_question("What is your expected CTC?", profile, TODAY)
    cur = answer_question("What is your current CTC?", profile, TODAY)
    assert exp["answer"] == "2,000,000 INR" and exp["sensitive"] and exp["status"] == "REVIEW_REQUIRED"
    assert cur["answer"] == "1,500,000 INR" and cur["sensitive"]


# ------------------------------------------------------------------ application lifecycle

async def _setup(client, auth):
    await client.put("/api/profile", headers=auth, json=PROFILE)
    job = (await client.post("/api/jobs/import", headers=auth, json={
        "title": "Senior SDET", "company": "PayCo", "location": "Bengaluru", "description": SDET_JD,
        "application_url": "https://payco.example/careers/sdet"})).json()["job"]
    await client.post(f"/api/jobs/{job['id']}/tailor-resume", headers=auth, json={})
    await client.post(f"/api/jobs/{job['id']}/cover-letter", headers=auth)
    return job


async def test_create_bundles_tailored_documents(client, db, auth):
    job = await _setup(client, auth)
    r = await client.post("/api/applications", headers=auth, json={"job_id": job["id"]})
    assert r.status_code == 201, r.text
    a = r.json()
    assert a["status"] == "READY_TO_APPLY" and a["resume_id"] and a["cover_letter_id"]
    assert a["match_score"] == job["score"]
    tailored = await db[c.RESUMES].find_one({"_id": a["resume_id"]})
    assert tailored["job_id"] == job["id"]
    assert (await client.get(f"/api/jobs/{job['id']}", headers=auth)).json()["status"] == "shortlisted"
    dup = await client.post("/api/applications", headers=auth, json={"job_id": job["id"]})
    assert dup.status_code == 409


async def test_questions_gate_approval_then_handoff_and_followups(client, db, auth):
    job = await _setup(client, auth)
    app_id = (await client.post("/api/applications", headers=auth, json={"job_id": job["id"]})).json()["id"]
    answers = (await client.post(f"/api/applications/{app_id}/prepare", headers=auth, json={"questions": [
        "What is your notice period?", "Why do you want to join PayCo?"]})).json()
    assert [x["status"] for x in answers] == ["ANSWERED", "REVIEW_REQUIRED"]
    detail = (await client.get(f"/api/applications/{app_id}", headers=auth)).json()
    assert detail["status"] == "APPROVAL_REQUIRED"

    blocked = await client.post(f"/api/applications/{app_id}/approve", headers=auth)
    assert blocked.status_code == 409  # unresolved review item

    await client.put(f"/api/applications/{app_id}/answers/{answers[1]['id']}", headers=auth,
                     json={"answer": "I build payment test automation and PayCo's UPI focus matches my experience."})
    assert (await client.get(f"/api/applications/{app_id}", headers=auth)).json()["status"] == "READY_TO_APPLY"

    ok = (await client.post(f"/api/applications/{app_id}/approve", headers=auth)).json()
    assert ok["submission"] == "HUMAN_APPROVAL_REQUIRED" and ok["handoff_url"] == "https://payco.example/careers/sdet"
    assert ok["application"]["status"] == "APPLYING"

    applied = (await client.post(f"/api/applications/{app_id}/mark-applied", headers=auth)).json()
    assert applied["status"] == "APPLIED" and applied["applied_at"] and applied["next_followup_at"]
    detail = (await client.get(f"/api/applications/{app_id}", headers=auth)).json()
    assert [(f["kind"], f["sequence"]) for f in detail["followups"]] == [("followup", 1), ("followup", 2), ("close", 3)]
    due = datetime.fromisoformat(detail["followups"][0]["due_at"])
    assert timedelta(days=2.9) < due.replace(tzinfo=due.tzinfo or UTC) - datetime.now(UTC) < timedelta(days=3.1)
    assert [e["to"] for e in detail["events"] if e["type"] == "status_change"][-3:] == [
        "READY_TO_APPLY", "APPLYING", "APPLIED"]
    dash = (await client.get("/api/analytics/dashboard", headers=auth)).json()
    assert dash["today"]["applications_submitted"] == 1 and dash["totals"]["applications"] == 1


async def test_pause_and_daily_limit_block_approve(client, auth):
    job = await _setup(client, auth)
    app_id = (await client.post("/api/applications", headers=auth, json={"job_id": job["id"]})).json()["id"]
    await client.put("/api/automation/settings", headers=auth, json={"pauses": {"applications": True}})
    assert (await client.post(f"/api/applications/{app_id}/approve", headers=auth)).status_code == 423
    await client.put("/api/automation/settings", headers=auth, json={
        "pauses": {"applications": False},
        "limits": {"daily_application_limit": 0, "daily_email_limit": 5, "daily_recruiter_contact_limit": 5,
                   "min_match_score": 70}})
    assert (await client.post(f"/api/applications/{app_id}/approve", headers=auth)).status_code == 429


async def test_status_pipeline_offer_cancels_followups(client, db, auth):
    job = await _setup(client, auth)
    app_id = (await client.post("/api/applications", headers=auth, json={"job_id": job["id"]})).json()["id"]
    await client.post(f"/api/applications/{app_id}/mark-applied", headers=auth)
    for s in ("RECRUITER_REPLIED", "SCREENING", "OFFER"):
        r = await client.post(f"/api/applications/{app_id}/status", headers=auth, json={"status": s})
        assert r.json()["status"] == s
    assert await db[c.FOLLOWUPS].count_documents({"application_id": app_id, "status": "scheduled"}) == 0
    notes = [n["title"] for n in (await client.get("/api/notifications", headers=auth)).json()]
    assert any(t.startswith("Offer received") for t in notes)
    bad = await client.post(f"/api/applications/{app_id}/status", headers=auth, json={"status": "HIRED"})
    assert bad.status_code == 422


async def test_interviews_lifecycle(client, auth):
    job = await _setup(client, auth)
    app_id = (await client.post("/api/applications", headers=auth, json={"job_id": job["id"]})).json()["id"]
    when = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    iv = (await client.post("/api/interviews", headers=auth, json={
        "application_id": app_id, "round": "Technical 1", "scheduled_at": when,
        "meeting_url": "https://meet.example/abc", "interview_type": "Video"})).json()
    assert iv["company"] == "PayCo" and iv["status"] == "upcoming"
    assert (await client.get(f"/api/applications/{app_id}", headers=auth)).json()["status"] == "INTERVIEW_SCHEDULED"
    later = (datetime.now(UTC) + timedelta(days=2)).isoformat()
    moved = (await client.patch(f"/api/interviews/{iv['id']}", headers=auth, json={"scheduled_at": later})).json()
    assert moved["status"] == "rescheduled"
    done = (await client.patch(f"/api/interviews/{iv['id']}", headers=auth, json={"status": "completed"})).json()
    assert done["status"] == "completed"
    assert (await client.get(f"/api/applications/{app_id}", headers=auth)).json()["status"] == "INTERVIEW_COMPLETED"
    grouped = (await client.get("/api/interviews", headers=auth)).json()
    assert len(grouped["completed"]) == 1 and grouped["upcoming"] == []
    bad = await client.post("/api/interviews", headers=auth, json={"scheduled_at": when})
    assert bad.status_code == 422


async def test_applications_isolated(client, auth):
    from tests.conftest import register
    job = await _setup(client, auth)
    app_id = (await client.post("/api/applications", headers=auth, json={"job_id": job["id"]})).json()["id"]
    other = await register(client, email="ravi@example.com", name="Ravi")
    assert (await client.get(f"/api/applications/{app_id}", headers=other)).status_code == 404
    assert (await client.get("/api/applications", headers=other)).json() == []
