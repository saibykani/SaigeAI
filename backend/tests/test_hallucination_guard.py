"""Spec section 58: the AI must never be able to emit fabricated candidate information."""

import pytest

from app.schemas.profile import Profile
from app.services.truth_guard import GeneratedClaims, validate_claims


@pytest.fixture
def profile() -> Profile:
    return Profile.model_validate({
        "personal": {"name": "Asha Rao", "current_company": "Acme Technologies Pvt Ltd",
                     "current_designation": "Senior QA Engineer", "total_experience_years": 5,
                     "current_ctc": 1200000, "expected_ctc": 1800000},
        "skills": {"primary": ["Java", "Selenium"], "api_testing": ["Rest Assured", "Postman"],
                   "performance_testing": ["JMeter"]},
        "knowledge": {
            "professional_summary": "QA engineer focused on test automation.",
            "experience": [{
                "company": "Acme Technologies Pvt Ltd", "title": "Senior QA Engineer",
                "achievements": ["Reduced regression time by 40% using parallel execution"],
                "responsibilities": ["Built Selenium framework with TestNG"],
                "technologies": ["TestNG", "Jenkins"],
            }, {"company": "Globex", "title": "QA Engineer"}],
            "projects": [{"name": "Payments Regression Suite", "technologies": ["Cucumber"]}],
            "education": [{"degree": "B.Tech", "institution": "JNTU Hyderabad"}],
            "certifications": [{"name": "ISTQB Foundation Level"}],
        },
    })


def _types(result) -> set[str]:
    return {v.type for v in result.violations}


def test_truthful_content_passes(profile):
    claims = GeneratedClaims(
        text="Senior QA Engineer with 5 years in Java, Selenium, TestNG and JMeter. "
             "Reduced regression time by 40% using parallel execution.",
        skills=["Java", "selenium webdriver", "Rest-Assured", "Jenkins", "Cucumber"],
        companies=["Acme Technologies", "Globex Inc"],
        titles=["Senior QA Engineer"],
        certifications=["ISTQB Foundation Level"],
        projects=["Payments Regression Suite"],
        education=["B.Tech"],
        experience_years=5,
        salary=1800000,
    )
    result = validate_claims(claims, profile)
    assert result.status == "PASSED", result.violations


def test_fake_company_blocked(profile):
    r = validate_claims(GeneratedClaims(companies=["Google"]), profile)
    assert r.status == "VALIDATION FAILED" and _types(r) == {"company"}


def test_fake_employment_title_blocked(profile):
    r = validate_claims(GeneratedClaims(titles=["QA Director"]), profile)
    assert _types(r) == {"title"}


def test_fake_project_blocked(profile):
    r = validate_claims(GeneratedClaims(projects=["Mars Rover Test Harness"]), profile)
    assert _types(r) == {"project"}


def test_fake_certification_blocked(profile):
    r = validate_claims(GeneratedClaims(certifications=["AWS Certified Solutions Architect"]),
                        profile)
    assert _types(r) == {"certification"}


def test_fake_skill_declared_blocked(profile):
    r = validate_claims(GeneratedClaims(skills=["Playwright"]), profile)
    assert _types(r) == {"skill"}


def test_fake_skill_in_free_text_blocked(profile):
    r = validate_claims(GeneratedClaims(text="Expert in Playwright and Kubernetes."), profile)
    assert {v.value for v in r.violations} == {"Playwright", "Kubernetes"}


def test_fake_experience_blocked(profile):
    assert _types(validate_claims(GeneratedClaims(experience_years=9), profile)) == {"experience"}
    r = validate_claims(GeneratedClaims(text="Over 10+ years of testing experience."), profile)
    assert _types(r) == {"experience"}


def test_unknown_experience_cannot_be_claimed():
    r = validate_claims(GeneratedClaims(experience_years=2), Profile())
    assert r.status == "VALIDATION FAILED"
    assert "UNKNOWN" in r.violations[0].reason


def test_fake_salary_blocked(profile):
    assert _types(validate_claims(GeneratedClaims(salary=2500000), profile)) == {"salary"}


def test_fake_achievement_metric_blocked(profile):
    r = validate_claims(GeneratedClaims(text="Cut defect leakage by 75% and saved $2M."), profile)
    assert _types(r) == {"metric"}
    assert len(r.violations) == 2


def test_fake_education_blocked(profile):
    assert _types(validate_claims(GeneratedClaims(education=["MBA"]), profile)) == {"education"}


def test_common_words_not_mistaken_for_skills(profile):
    text = "Go-live support; helped teams react quickly to production issues."
    assert validate_claims(GeneratedClaims(text=text), profile).status == "PASSED"


def test_umbrella_skill_implied_by_concrete_tool(profile):
    # Rest Assured / Postman are verified -> "API Testing" is truthful; JMeter -> "Performance Testing"
    r = validate_claims(GeneratedClaims(text="API Testing and Performance Testing", skills=["API Testing"]), profile)
    assert r.status == "PASSED"


def test_umbrella_not_granted_without_a_concrete_tool():
    bare = Profile.model_validate({"skills": {"primary": ["Java"]}})
    r = validate_claims(GeneratedClaims(skills=["API Testing"], text="Strong CI/CD background"), bare)
    assert {v.value for v in r.violations} == {"API Testing", "CI/CD"}
