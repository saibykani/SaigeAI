"""Offline quality harness: five realistic job posts against one verified profile. No network, no LLM."""

import re

import pytest

from app.jobs.jd_parser import analyze_jd
from app.resumes import craft, tailor
from app.resumes.ai_router import _matched
from app.schemas.profile import Profile
from app.services.truth_guard import GeneratedClaims, validate_claims
from app.studio import analyzer, apply
from app.studio.router import _surface_verified
from tests.quality_fixtures import JDS, PROFILE

PROFILE_OBJ = Profile.model_validate(PROFILE)
MIN_MATCHED = {"perf": 3, "sdet": 3, "data": 2, "java": 3, "hashtag": 3}
WEAK = re.compile(r"^(worked|responsible|involved|helped|handled|participated|assisted|did)\b", re.I)
REPEAT = re.compile(r"\b(\w+) \1\b", re.I)


def build(key: str):
    j = JDS[key]
    role = analyzer.clean_role(j["title"])
    jd = analyze_jd(role, j["text"])
    matched = _matched(PROFILE_OBJ, jd)
    summary = tailor.template_summary(PROFILE_OBJ, role, matched, j["text"])
    parsed, _ = tailor.tailor_resume(PROFILE_OBJ, jd, {"title": role, "company": j["company"]}, None, summary)
    parsed = _surface_verified(parsed, PROFILE_OBJ, jd, j["text"])
    return j, role, jd, matched, summary, parsed


@pytest.mark.parametrize("key", list(JDS))
def test_role_and_summary(key):
    j, role, _, matched, summary, _ = build(key)
    assert role == j["role"]
    assert summary.startswith(role) and "4.5 years" in summary
    assert "directly relevant" not in summary and "We're" not in summary and "#" not in summary
    said = [s for s in matched if re.search(rf"(?<![A-Za-z]){re.escape(s)}(?![A-Za-z])", summary)]
    assert len(said) >= MIN_MATCHED[key]
    have = {s.lower() for s in PROFILE_OBJ.skills.all()}
    assert all(s.lower() in have or s == "Rest Assured" for s in said)
    assert 2 <= len(re.findall(r"[.!?](?:\s|$)", summary)) <= 5
    assert not REPEAT.search(summary)


def test_extract_title_from_hashtag_posts():
    assert analyzer.extract_title(JDS["perf"]["text"]) == "Performance Test Engineer"
    assert analyzer.extract_title(JDS["hashtag"]["text"]) == "SDET"


@pytest.mark.parametrize("key", list(JDS))
def test_nothing_unverified_anywhere(key):
    j, role, jd, matched, summary, parsed = build(key)
    report = tailor.ats_report(parsed, jd)
    _, body = apply.draft(PROFILE_OBJ, role, j["company"], report["matched_keywords"], j["text"])
    letter, _ = tailor.template_cover_letter(PROFILE_OBJ, {"title": role, "company": j["company"]}, jd, matched)
    text = tailor.resume_text(parsed)
    for t in (text, body, letter, summary):
        res = validate_claims(GeneratedClaims(text=t), PROFILE_OBJ)
        assert res.passed, res.violations
    # gaps are reported, never inserted
    assert not any(re.search(rf"(?<![A-Za-z]){re.escape(m)}(?![A-Za-z])", text) for m in report["missing_required"])


@pytest.mark.parametrize("key", list(JDS))
def test_bullets_use_action_verbs_and_are_capped(key):
    parsed = build(key)[5]
    for i, e in enumerate(parsed.experience):
        bullets = e.achievements + e.responsibilities
        assert len(bullets) <= craft.bullet_cap(i) <= 6
        assert all(craft.starts_with_action_verb(b) and not WEAK.match(b) for b in bullets), bullets
        assert all(len(b) <= 260 for b in bullets)
        assert e.technologies == PROFILE["knowledge"]["experience"][i]["technologies"]


def test_performance_resume_prioritises_jd_material():
    _, _, jd, _, _, parsed = build("perf")
    first = parsed.experience[0]
    assert "JMeter" in first.achievements[0]
    assert parsed.projects[0].name == "Load Test Suite"
    assert {"JMeter", "Performance Testing"} <= set(parsed.skills[:6])
    # a JD phrase supported by verified skills ("API Testing" + "RestAssured") is used; unsupported tools are only gaps
    assert "REST API testing" in parsed.skills
    report = tailor.ats_report(parsed, jd)
    assert {"Kubernetes", "Gatling"} <= set(report["missing_required"]) | set(report["missing_preferred"])
    assert "Gatling" not in tailor.resume_text(parsed)


def test_skills_dedupe_near_duplicates():
    assert craft.dedupe_skills(["Rest Assured", "RestAssured", "Postman", "postman", "CI/CD", "Java"]) == ["Rest Assured", "Postman", "CI/CD", "Java"]
    skills = build("sdet")[5].skills
    assert sum("restassured" in re.sub(r"\W", "", s.lower()) for s in skills) == 1


def test_strengthen_weak_openers_keeps_facts():
    assert craft.strengthen("Worked on load testing of 40 APIs") == "Contributed to load testing of 40 APIs"
    assert craft.strengthen("Responsible for creating Selenium suites") == "Created Selenium suites"
    assert craft.strengthen("Involved in Jenkins setup") == "Contributed to Jenkins setup"
    assert craft.strengthen("Handled API testing with Postman") == "Managed API testing with Postman"
    assert craft.strengthen("Reduced latency by 35%") == "Reduced latency by 35%"
    long = "Built a framework. " + "Added reporting and dashboards for the whole team, " * 6 + "and more."
    assert len(craft.condense(long, 150)) < len(long) and craft.condense(long, 150).startswith("Built a framework.")


@pytest.mark.parametrize("key", list(JDS))
def test_email_is_short_specific_and_truthful(key):
    j, role, jd, _, _, parsed = build(key)
    sub, body = apply.draft(PROFILE_OBJ, role, j["company"], tailor.ats_report(parsed, jd)["matched_keywords"], j["text"])
    assert len(body.split()) < 170
    assert role in body and j["company"] in body
    assert role in sub
    assert "express my interest" not in body.lower() and "I am writing" not in body
    assert not REPEAT.search(body)
    assert "+91 90000 00000" in body and "linkedin.com/in/asharao" in body
    assert "Current CTC" not in body  # the post does not ask for it


def test_email_greeting_and_subject_format():
    sub, body = apply.draft(PROFILE_OBJ, "Performance Test Engineer", "Acme Pay", ["JMeter"], JDS["perf"]["text"])
    assert body.startswith("Hi Priya,")
    assert apply.draft(PROFILE_OBJ, "SDET", "Umbrella", ["Selenium"], JDS["hashtag"]["text"])[0] == "Application for SDET - Asha Rao"
    assert apply.subject_asked("Please use subject: Application - [Job Title] - Name", "QA Lead") == "Application - QA Lead - Name"
    assert apply.subject_asked('Use subject line "Hiring: [Role]"', "SDET") == "Hiring: SDET"
    assert apply.subject_asked("No format given", "SDET") is None
    assert apply.draft(PROFILE_OBJ, "SDET", "Umbrella", ["Selenium"], "Mail resume to jobs@x.io")[1].startswith("Hello Hiring Team,")


def test_email_includes_asked_facts_only():
    post = JDS["perf"]["text"] + "\nShare current CTC, expected CTC and notice period."
    body = apply.draft(PROFILE_OBJ, "Performance Test Engineer", "Acme Pay", ["JMeter"], post)[1]
    assert "Current CTC: 12 LPA" in body and "Expected CTC: 18 LPA" in body and "Notice period: 30 days" in body


def test_cover_letter_uses_role_company_and_own_words():
    j = JDS["perf"]
    jd = analyze_jd("Performance Test Engineer", j["text"])
    body, greeting = tailor.template_cover_letter(PROFILE_OBJ, {"title": j["title"], "company": "Acme Pay"}, jd, _matched(PROFILE_OBJ, jd))
    assert "Performance Test Engineer role at Acme Pay" in body and "We're" not in body and "excited" not in body
    assert "JMeter" in body and "4.5 years" in body and greeting == "Dear Hiring Team at Acme Pay,"
