# ruff: noqa: E501  (fixture payloads)
import pytest

from app.portfolio import data as pdata
from app.portfolio import templates as tpl
from app.schemas.profile import Profile
from tests.job_fixtures import PROFILE

FULL = Profile.model_validate({**PROFILE, "personal": {**PROFILE["personal"], "name": "Asha <script>alert(1)</script> Rao"},
                               "knowledge": {**PROFILE["knowledge"], "projects": [
                                   {"name": "VCIP", "description": "KYC video platform", "technologies": ["Selenium"], "highlights": ["Automated KYC"],
                                    "url": "https://github.com/asha/vcip"}]}})
EMPTY = Profile.model_validate({"personal": {"name": "Ravi"}})


@pytest.mark.parametrize("tid", list(tpl.TEMPLATES))
def test_every_template_renders_escaped(tid):
    for prof in (FULL, EMPTY):
        html = tpl.render(tid, pdata.build(prof, {"show_phone": False}))
        assert html.startswith("<!doctype html>") and "</html>" in html
        assert "<script>alert" not in html  # the user's name is escaped; only Saige's own scripts run
        if prof is FULL:
            assert "&lt;script&gt;" in html
    assert "VCIP" in tpl.render(tid, pdata.build(FULL, {}))


def test_at_least_25_templates():
    assert len(tpl.TEMPLATES) >= 25


async def test_publish_flow_public_url_and_privacy(client, auth, other_auth=None):
    assert (await client.put("/api/profile", headers=auth, json=PROFILE)).status_code == 200
    s = (await client.get("/api/portfolio", headers=auth)).json()
    assert s["slug"] and not s["published"]
    prev = await client.get("/api/portfolio/preview?template=terminal", headers=auth)
    assert prev.status_code == 200 and "zsh" in prev.text
    assert (await client.get(f"/api/p/{s['slug']}")).status_code == 404  # not published yet
    body = {"template": "bento", "slug": "asha-rao", "tagline": "I break things so users don't", "show_email": True, "show_phone": False}
    r = await client.post("/api/portfolio/publish", headers=auth, json=body)
    assert r.status_code == 200 and r.json()["published"]
    pub = await client.get("/api/p/asha-rao")
    assert pub.status_code == 200 and "I break things" in pub.text
    phone = PROFILE["personal"].get("phone")
    if phone:
        assert phone not in pub.text
    assert (await client.get("/api/portfolio", headers=auth)).json()["views"] == 1
    bad = await client.put("/api/portfolio", headers=auth, json={**body, "slug": "API"})
    assert bad.status_code == 422
    await client.post("/api/portfolio/unpublish", headers=auth)
    assert (await client.get("/api/p/asha-rao")).status_code == 404
