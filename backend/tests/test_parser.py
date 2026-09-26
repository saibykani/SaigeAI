from app.resumes.parser import parse_resume
from tests.fixtures import SAMPLE_RESUME


def test_contact_details():
    r = parse_resume(SAMPLE_RESUME)
    assert r.name == "Asha Rao"
    assert r.email == "asha.rao@example.com"
    assert r.phone and r.phone.replace(" ", "").endswith("9876543210")
    assert r.links.linkedin == "https://linkedin.com/in/asha-rao"
    assert r.links.github == "https://github.com/asharao"


def test_sections_and_summary():
    r = parse_resume(SAMPLE_RESUME)
    assert {"summary", "skills", "experience", "projects", "education",
            "certifications"} <= set(r.sections_found)
    assert r.summary.startswith("QA Automation Engineer with 5 years")


def test_skills_are_canonicalised():
    r = parse_resume(SAMPLE_RESUME)
    for skill in ("Java", "Python", "Selenium", "TestNG", "Rest Assured", "Postman", "JMeter",
                  "Jenkins", "Git", "CI/CD"):
        assert skill in r.skills, skill
    assert "Jenkins" in r.tools


def test_experience_entries():
    r = parse_resume(SAMPLE_RESUME)
    assert len(r.experience) == 2
    first, second = r.experience
    assert first.title == "Senior QA Engineer"
    assert first.company == "Acme Technologies"
    assert first.location == "Hyderabad"
    assert first.is_current and first.end_date is None
    assert first.start_date == "Jan 2022"
    assert any("40%" in a for a in first.achievements)
    assert "Rest Assured" in first.technologies
    assert second.company == "Globex Corp"
    assert second.end_date == "Dec 2021"


def test_education_projects_certifications():
    r = parse_resume(SAMPLE_RESUME)
    assert r.education[0].degree == "B.Tech"
    assert r.education[0].field == "Computer Science"
    assert r.education[0].institution == "JNTU Hyderabad University"
    assert (r.education[0].start_year, r.education[0].end_year) == (2015, 2019)
    assert r.projects[0].name == "Payments Regression Suite"
    assert "TestNG" in r.projects[0].technologies
    assert r.certifications == ["ISTQB Certified Tester Foundation Level"]


def test_missing_data_is_unknown_not_invented():
    r = parse_resume("Some text without any structure at all.")
    assert r.name is None and r.email is None and r.phone is None
    assert r.experience == [] and r.certifications == []
    assert any("UNKNOWN" in w for w in r.warnings)


def test_alternate_experience_layout():
    text = """EXPERIENCE
Initech Solutions, Pune
Test Lead    March 2018 to Present
- Led a team of 6 testers
"""
    r = parse_resume(text)
    assert len(r.experience) == 1
    exp = r.experience[0]
    assert exp.title == "Test Lead"
    assert exp.company == "Initech Solutions"
    assert exp.is_current
