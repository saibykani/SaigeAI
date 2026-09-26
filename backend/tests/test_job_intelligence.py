"""Unit tests: JD parsing, matching, dedupe, LLM output verification."""

import pytest

from app.agents.jd_agent import LLMJobExtraction, analyze_job, verify_extraction
from app.agents.llm import set_provider
from app.jobs.dedupe import canonical_url, company_key, is_duplicate
from app.jobs.jd_parser import analyze_jd, html_to_text
from app.jobs.matching import compute_match, role_similarity
from app.jobs.service import infer_country
from app.schemas.job import MatchWeights
from app.schemas.profile import Profile
from tests.job_fixtures import PROFILE, SDET_JD

# ------------------------------------------------------------------ JD parser

def test_jd_sections_and_skills():
    jd = analyze_jd("Senior SDET", SDET_JD)
    for s in ("Java", "Selenium", "Rest Assured", "Postman", "Jenkins"):
        assert s in jd.required_skills, s
    for s in ("Playwright", "Cypress", "JMeter", "Kubernetes"):
        assert s in jd.preferred_skills, s
        assert s not in jd.required_skills
    assert any("3-5 years" in r for r in jd.requirements)
    assert len(jd.responsibilities) == 3


def test_jd_numbers_and_flags():
    jd = analyze_jd("Senior SDET", SDET_JD)
    assert (jd.experience_min, jd.experience_max) == (3, 5)
    assert (jd.salary_min, jd.salary_max, jd.currency) == (1800000, 2800000, "INR")
    assert jd.hybrid is True and jd.remote is None
    assert jd.employment_type == "Full-time"
    assert jd.seniority == "Senior"
    assert jd.notice_period_max_days == 30
    assert "Fintech" in jd.domains
    assert jd.education and "Bachelor" in jd.education[0]


def test_jd_degree_pattern_ignores_common_words():
    jd = analyze_jd("QA Engineer", "You will be part of a team. Let me know. " * 3)
    assert jd.education == []


def test_jd_usd_salary_and_remote_and_visa():
    text = ("Fully remote role. Salary $120k - $150k. 5+ years with Playwright and TypeScript. "
            "We are unable to sponsor visas.")
    jd = analyze_jd("QA Engineer", text)
    assert (jd.salary_min, jd.salary_max, jd.currency) == (120000, 150000, "USD")
    assert jd.remote is True
    assert jd.experience_min == 5 and jd.experience_max is None
    assert jd.no_visa_sponsorship is True
    assert set(jd.required_skills) >= {"Playwright", "TypeScript"}


def test_html_to_text_keeps_bullets():
    raw = ("&lt;h3&gt;Requirements&lt;/h3&gt;&lt;ul&gt;&lt;li&gt;Java&lt;/li&gt;"
           "&lt;li&gt;Selenium&lt;/li&gt;&lt;/ul&gt;")
    text = html_to_text(raw)
    assert "Requirements" in text and "- Java" in text and "- Selenium" in text


def test_infer_country():
    assert infer_country("Bengaluru, Karnataka") == "India"
    assert infer_country("London, UK") == "UK"
    assert infer_country("Remote") is None


# ------------------------------------------------------------------ matching

@pytest.fixture
def profile() -> Profile:
    return Profile.model_validate(PROFILE)


def _job(**kw):
    return {"title": "Senior SDET", "company": "PayCo", "location": "Bengaluru", **kw}


def test_strong_match(profile):
    jd = analyze_jd("Senior SDET", SDET_JD)
    m = compute_match(profile, _job(), jd)
    # Every required skill is matched except Agile, which the profile genuinely lacks.
    # Rest Assured/Postman imply "API Testing" and Jenkins implies "CI/CD".
    assert m.missing_required_skills == ["Agile"]
    assert m.breakdown.skills == pytest.approx((0.8 * 7 / 8 + 0.2 * 2 / 5) * 100, abs=0.1)
    assert m.breakdown.experience == 100.0
    assert m.breakdown.location == 100.0  # Bengaluru == Bangalore alias
    assert m.breakdown.salary == 100.0
    assert m.breakdown.domain == 100.0
    assert m.breakdown.notice_period == 100.0
    assert m.overall >= 85 and m.classification == "Highly Relevant"
    assert "Playwright" in m.missing_preferred_skills
    assert "JMeter" in m.matched_skills and "Performance Testing" in m.matched_skills


def test_skills_score_uses_required_and_preferred(profile):
    jd = analyze_jd("Senior SDET", SDET_JD)
    jd = jd.model_copy(update={"required_skills": ["Java", "Go", "Kotlin", "Selenium"]})
    m = compute_match(profile, _job(), jd)
    assert m.missing_required_skills == ["Go", "Kotlin"]
    # 0.8 * 2/4 required + 0.2 * 2/5 preferred (JMeter, Performance Testing implied by it)
    assert m.breakdown.skills == pytest.approx((0.8 * 0.5 + 0.2 * 0.4) * 100, abs=0.1)


def test_experience_gap_and_unknown(profile):
    jd = analyze_jd("SDET", "Requirements\n- 8+ years of automation experience with Java")
    m = compute_match(profile, _job(), jd)
    assert m.breakdown.experience == 25.0 and "3 year(s) short" in m.experience_gap
    unknown = Profile.model_validate({**PROFILE, "personal": {"current_designation": "QA"}})
    m2 = compute_match(unknown, _job(), jd)
    assert m2.breakdown.experience is None
    assert any("UNKNOWN" in i for i in m2.issues)


def test_location_salary_and_excluded(profile):
    jd = analyze_jd("SDET", "Java and Selenium. Salary 10-12 LPA.")
    m = compute_match(profile, _job(location="Pune"), jd)
    assert m.breakdown.location == 30.0 and any("Location issue" in i for i in m.issues)
    assert m.breakdown.salary == 60.0 and any("Salary issue" in i for i in m.issues)
    excluded = profile.model_copy(deep=True)
    excluded.preferences.excluded_companies = ["PayCo"]
    assert compute_match(excluded, _job(), jd).overall <= 20


def test_unknown_dimensions_are_excluded_from_average(profile):
    jd = analyze_jd("SDET", "We need Java and Selenium.")
    m = compute_match(profile, _job(location=None), jd)
    assert m.breakdown.salary is None and m.breakdown.domain is None
    assert set(m.weights) == {"skills", "role"}
    assert abs(sum(m.weights.values()) - 1) < 0.01


def test_weights_are_configurable(profile):
    jd = analyze_jd("SDET", "Java, Selenium, Kotlin, Go. Location Pune.")
    base = compute_match(profile, _job(location="Pune"), jd)
    only_role = compute_match(profile, _job(location="Pune"), jd,
                              MatchWeights(skills=0, location=0, experience=0, salary=0, domain=0,
                                           notice_period=0, education=0, work_authorization=0))
    assert set(only_role.weights) == {"role"} and only_role.overall != base.overall


def test_role_similarity():
    assert role_similarity("Senior SDET", ["SDET"]) >= 80
    assert role_similarity("QA Automation Engineer II", ["QA Automation Engineer"]) >= 80
    assert role_similarity("Software Test Engineer", ["SDET"]) >= 45  # test/sdet -> qa synonym
    assert role_similarity("Marketing Manager", ["SDET"]) < 30
    assert role_similarity("Anything", []) is None


# ------------------------------------------------------------------ dedupe

def _cand(**kw):
    base = {"title": "Senior SDET", "company_key": company_key("PayCo Technologies Pvt Ltd"),
            "location": "Bengaluru", "description": SDET_JD, "source": "manual",
            "source_job_id": None, "url_key": None}
    return {**base, **kw}


def test_canonical_url_and_company_key():
    assert canonical_url("https://www.Example.com/jobs/123/?utm_source=x#apply") == \
        "https://example.com/jobs/123"
    assert company_key("PayCo Technologies Pvt. Ltd.") == company_key("payco")


def test_duplicate_by_url_and_source_id():
    existing = {**_cand(), "sources": [{"source": "lever", "source_job_id": "abc",
                                        "url_key": "https://jobs.lever.co/payco/abc"}]}
    assert is_duplicate(_cand(url_key="https://jobs.lever.co/payco/abc", company_key="x"), existing)[0]
    assert is_duplicate(_cand(source="lever", source_job_id="abc", company_key="x"), existing)[0]


def test_duplicate_across_sources_by_content():
    existing = {**_cand(title="Sr. SDET (Hybrid)"), "sources": []}
    tweaked = SDET_JD.replace("Apply now", "") + "\nApply via our careers page."
    dup, reason = is_duplicate(_cand(description=tweaked, source="naukri"), existing)
    assert dup and "same company" in reason


def test_not_duplicate_different_role_or_company():
    existing = {**_cand(), "sources": []}
    assert not is_duplicate(_cand(title="Engineering Manager", description="Lead a team " * 40),
                            existing)[0]
    assert not is_duplicate(_cand(company_key="othercorp"), existing)[0]


# ------------------------------------------------------------------ LLM verification

class FakeProvider:
    name = "fake"

    def __init__(self, result):
        self.result = result

    async def extract(self, *, system, prompt, schema):
        return self.result


def test_verify_drops_ungrounded_llm_output():
    ext = LLMJobExtraction(
        required_skills=["Java", "Kubernetes Operators", "Rust"],
        preferred_skills=["Playwright"],
        requirements=["Strong Java and Selenium WebDriver skills", "10 years of Rust experience"],
        nice_to_have=[], responsibilities=[], experience_min=3, experience_max=12,
    )
    v = verify_extraction(ext, SDET_JD)
    assert v["required_skills"] == ["Java"]
    assert v["requirements"] == ["Strong Java and Selenium WebDriver skills"]
    assert v["experience_min"] == 3 and v["experience_max"] is None  # 12 never appears


async def test_analyze_job_merges_verified_llm_output():
    set_provider(FakeProvider(LLMJobExtraction(
        required_skills=["Selenium", "Blockchain"], preferred_skills=["Kubernetes"],
        requirements=[], nice_to_have=[], responsibilities=[], experience_min=None, experience_max=None)))
    try:
        jd = await analyze_job("Senior SDET", SDET_JD)
    finally:
        set_provider(None)
    assert jd.extraction == "deterministic+fake"
    assert "Blockchain" not in jd.skills and "Blockchain" not in jd.required_skills


async def test_analyze_job_without_provider_is_deterministic():
    set_provider(None)
    jd = await analyze_job("Senior SDET", SDET_JD)
    assert jd.extraction == "deterministic"


async def test_llm_failure_falls_back():
    set_provider(FakeProvider(None))
    try:
        jd = await analyze_job("Senior SDET", SDET_JD)
    finally:
        set_provider(None)
    assert jd.extraction == "deterministic" and "Java" in jd.required_skills


def test_no_skills_signal_caps_score(profile):
    jd = analyze_jd("QA Automation Engineer",
                    "Join our team in Bengaluru. Great culture and benefits for everyone.")
    assert jd.required_skills == [] and jd.preferred_skills == []
    m = compute_match(profile, _job(title="QA Automation Engineer"), jd)
    assert m.breakdown.skills is None
    assert m.overall <= 60 and m.classification in {"Potential Match", "Low Match", "Not Relevant"}
    assert any("No recognizable skills" in i for i in m.issues)
