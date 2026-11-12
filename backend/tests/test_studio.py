import pytest

from app.studio import render
from tests.job_fixtures import PROFILE, SDET_JD


async def _setup(client, auth):
    r = await client.put("/api/profile", headers=auth, json=PROFILE)
    assert r.status_code == 200, r.text


async def test_jd_analyzer_explains_fit_gaps_and_eligibility(client, auth):
    await _setup(client, auth)
    r = await client.post("/api/studio/analyze", headers=auth, json={"jd_text": SDET_JD, "title": "SDET II", "company": "Acme"})
    assert r.status_code == 200, r.text
    a = r.json()
    assert a["title"] == "SDET II" and a["company"] == "Acme"
    assert a["verdict"]["key"] in ("eligible", "partial", "not_yet")
    assert {c["label"] for c in a["eligibility"]} >= {"Required skills", "Experience", "Education"}
    have = [s["name"] for s in a["skills"]["required"] if s["have"]]
    assert have and set(have) <= set(a["keywords_to_use"])
    assert a["requirements"] and all(row["status"] in ("met", "not_met", "unknown") for row in a["requirements"])
    assert a["summary"].startswith("SDET II at Acme")
    bad = await client.post("/api/studio/analyze", headers=auth, json={"jd_text": "short"})
    assert bad.status_code == 422


async def test_generate_resume_preview_and_download_every_format(client, auth):
    await _setup(client, auth)
    tpl = (await client.get("/api/studio/templates", headers=auth)).json()
    assert len(tpl["templates"]) >= 4 and {f["id"] for f in tpl["formats"]} == {"pdf", "docx", "txt", "md", "html"}
    r = await client.post("/api/studio/resume", headers=auth,
                          json={"jd_text": SDET_JD, "title": "SDET II", "company": "Acme Corp", "template": "classic"})
    assert r.status_code == 201, r.text
    g = r.json()
    assert g["ats"]["score"] > 0 and "<h1>" in g["html"] and g["template"] == "classic"
    # nothing outside the verified profile is on the resume
    assert not set(g["ats"]["missing_required"]) & set(g["resume"]["skills"])
    rid = g["id"]
    listed = (await client.get("/api/studio/resumes", headers=auth)).json()
    assert listed[0]["id"] == rid and listed[0]["company"] == "Acme Corp"
    for fmt, magic in (("pdf", b"%PDF"), ("docx", b"PK"), ("txt", b""), ("md", b"# "), ("html", b"<!doctype")):
        d = await client.get(f"/api/studio/resumes/{rid}/download?format={fmt}&template=modern&on=2026-11-10", headers=auth)
        assert d.status_code == 200, d.text
        assert d.content.startswith(magic)
        cd = d.headers["content-disposition"]
        assert "Asha_Rao_2026-11-10_Acme_Corp." + fmt in cd
    one = (await client.get(f"/api/studio/resumes/{rid}?template=compact", headers=auth)).json()
    assert one["ats"]["score"] == g["ats"]["score"] and one["html"]


@pytest.mark.parametrize("tid", list(render.TEMPLATES))
def test_every_template_renders_every_format(tid):
    from app.schemas.resume import ParsedExperience, ParsedResume

    r = ParsedResume(name="Asha Rao", email="a@x.com", phone="+91 90000 00000", summary="QA engineer — automation (Selenium).",
                     skills=["Selenium", "Java", "API testing"],
                     experience=[ParsedExperience(company="Acme", title="SDET", start_date="2021-01", is_current=True,
                                                  responsibilities=["Built a Selenium framework " * 6])])
    for fmt in render.FORMATS:
        out = render.render(r, tid, fmt)
        assert len(out) > 200
    assert render.filename("Asha K Rao", "Acme & Co.", "2026-11-10", "pdf") == "Asha_Rao_2026-11-10_Acme_Co.pdf"


async def test_company_is_read_from_the_jd_and_experience_counts_from_dates(client, auth):
    from datetime import date

    profile = {**PROFILE, "knowledge": {**PROFILE["knowledge"], "experience": [
        {"company": "Acme Fintech", "title": "QA Engineer", "start_date": "July 2023", "is_current": True,
         "responsibilities": ["Tested payment flows with Selenium and Rest Assured."]}]}}
    assert (await client.put("/api/profile", headers=auth, json=profile)).status_code == 200
    jd = "About Razorpay\nRazorpay is India's leading payments company.\n" + SDET_JD
    g = (await client.post("/api/studio/resume", headers=auth, json={"jd_text": jd, "template": "banner"})).json()
    assert g["company"] == "Razorpay" and g["company_detected"] is True
    t = date.today()
    months = (t.year - 2023) * 12 + t.month - 7 + 1
    assert g["experience_years"] == round(months / 12, 1)
    assert "QA Engineer" in g["headline"] or "Senior QA Engineer" in g["headline"]
    assert "years experience · since" in g["headline"] and g["headline"] in g["html"]
    d = await client.get(f"/api/studio/resumes/{g['id']}/download?format=pdf&on=2026-11-11", headers=auth)
    assert "Asha_Rao_2026-11-11_Razorpay.pdf" in d.headers["content-disposition"]
    a = (await client.post("/api/studio/analyze", headers=auth, json={"jd_text": jd})).json()
    assert a["company"] == "Razorpay" and a["company_detected"] is True


def test_extract_company_patterns():
    from app.studio.analyzer import extract_company

    assert extract_company("Company: Infosys Limited\nRole: QA") == "Infosys"
    assert extract_company("At Freshworks, we build software. Apply at careers.freshworks.com") == "Freshworks"
    assert extract_company("Mail your CV to hr@zeptonow.com") == "Zeptonow"
    assert extract_company("Looking for a tester. You will test apps.") is None


def test_polish_repairs_imported_resume_artefacts():
    from app.schemas.resume import ParsedProject, ParsedResume
    from app.studio import polish
    from app.studio.analyzer import _guess_title

    raw = ["Java (Test Automation", "Page Object Model (POM", "Newman (Postman CLI", "Spike", "Testing", "Data", "Functional",
           "Cucumber BDD", "Cucumber", "BDD", "Java", "CI/CD", "MySQL", "Azure SQL"]
    r = ParsedResume(name="A", summary="SDET with 3+ years of experience. SDET with 3 years of experience in test automation and API testing.",
                     skills=raw, projects=[ParsedProject(name="P", highlights=["Automated UI tests for onboarding and", "transaction flows.",
                                                                                "Ran master–", "slave distributed tests."])])
    p = polish.polish(r)
    assert p.summary.count("years of experience") == 1
    assert "Page Object Model (POM)" in p.skills and "Newman (Postman CLI)" in p.skills and "Spike Testing" in p.skills
    assert "Functional Testing" in p.skills and "CI/CD" in p.skills and p.skills.count("Java") == 1
    assert not {"Testing", "Data", "Cucumber", "BDD", "Java (Test Automation"} & set(p.skills)
    assert p.projects[0].highlights == ["Automated UI tests for onboarding and transaction flows.", "Ran master–slave distributed tests."]
    groups = dict(polish.group_skills(p.skills))
    assert "MySQL" in groups["Databases"] and "Azure SQL" in groups["Databases"] and "Java" in groups["Languages"]
    assert _guess_title("I Do Not Accept I Accept\nWe are hiring a Senior QA Automation Engineer to join us.") == "Senior QA Automation Engineer"
    assert _guess_title("Job Title: SDET II\nLocation: Hyderabad") == "SDET II"
    assert _guess_title("Cookie settings\nAccept all") == ""
