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
        assert "Acme_Corp_2026-11-10." + fmt in cd and "Asha" in cd
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
    assert render.filename("Asha Rao", "Acme & Co.", "2026-11-10", "pdf") == "Asha_Rao_Acme_Co_2026-11-10.pdf"
