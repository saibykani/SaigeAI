from app.schemas.profile import Profile
from app.schemas.resume import ParsedExperience, ParsedProject, ParsedResume
from app.studio import instruct


def _resume():
    return ParsedResume(summary="QA engineer with 4 years. Strong in Java. Healthcare domain. Loves testing.",
                        skills=["Java", "Selenium", "Healthcare", "Playwright", "SaaS"],
                        experience=[ParsedExperience(company="PayCo", title="SDET",
                                                     achievements=["Built Selenium suites", "Tested Healthcare APIs"])],
                        projects=[ParsedProject(name="Payment Gateway Automation"), ParsedProject(name="Portal")])


def test_chat_edits_remove_move_shorten_and_never_invent():
    p = Profile()
    p.skills.primary = ["Java", "Selenium", "Playwright", "Postman"]
    r, _ = instruct.apply(_resume(), p, "remove Healthcare and SaaS. move Playwright to top. shorten summary. remove the Payment Gateway project")
    assert "Healthcare" not in r.skills and "SaaS" not in r.skills and r.skills[0] == "Playwright"
    assert all("Healthcare" not in b for b in r.experience[0].achievements)
    assert r.summary.count(".") <= 2
    assert [x.name for x in r.projects] == ["Portal"]
    r2, ch2 = instruct.apply(r, p, "add Postman, Kubernetes")
    assert "Postman" in r2.skills and "Kubernetes" not in r2.skills and any("isn't in your verified profile" in c for c in ch2)
    r3, _ = instruct.apply(r2, p, "remove projects section")
    assert r3.projects == []
