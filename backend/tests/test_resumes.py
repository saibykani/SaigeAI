import io

from docx import Document

from app.database import collections as c
from tests.conftest import register
from tests.fixtures import SAMPLE_RESUME


async def upload(client, auth, *, content: bytes = SAMPLE_RESUME.encode(),
                 filename="asha.txt", ctype="text/plain", name="Master", kind="Master Resume"):
    return await client.post("/api/resumes", headers=auth,
                             files={"file": (filename, content, ctype)},
                             data={"name": name, "kind": kind})


def _docx_bytes() -> bytes:
    doc = Document()
    for line in SAMPLE_RESUME.splitlines():
        doc.add_paragraph(line)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


async def test_upload_and_parse_txt(client, auth):
    r = await upload(client, auth)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["version_count"] == 1
    parsed = body["current_version"]["parsed"]
    assert parsed["name"] == "Asha Rao"
    assert len(parsed["experience"]) == 2


async def test_upload_docx(client, auth):
    r = await upload(client, auth, content=_docx_bytes(), filename="asha.docx",
                     ctype="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    assert r.status_code == 201, r.text
    assert "Selenium" in r.json()["current_version"]["parsed"]["skills"]


async def test_rejects_disguised_file(client, auth):
    r = await upload(client, auth, content=b"MZ\x90\x00binary", filename="evil.pdf",
                     ctype="application/pdf")
    assert r.status_code == 415
    r = await upload(client, auth, content=b"x", filename="script.exe",
                     ctype="application/octet-stream")
    assert r.status_code == 415


async def test_rejects_oversized_file(client, auth):
    r = await upload(client, auth, content=b"a" * (5 * 1024 * 1024 + 10))
    assert r.status_code == 413


async def test_list_edit_version_compare(client, auth):
    rid = (await upload(client, auth)).json()["id"]
    detail = (await client.get(f"/api/resumes/{rid}", headers=auth)).json()
    parsed = detail["current_version"]["parsed"]
    parsed["skills"] = [s for s in parsed["skills"] if s != "Python"] + ["Appium"]
    parsed["summary"] = "Edited summary"

    r = await client.put(f"/api/resumes/{rid}", headers=auth,
                         json={"name": "SDET Resume", "kind": "SDET Resume", "parsed": parsed})
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "SDET Resume" and body["version_count"] == 2
    assert "Skills added: Appium" in body["current_version"]["changes"]

    versions = (await client.get(f"/api/resumes/{rid}/versions", headers=auth)).json()
    assert [v["version"] for v in versions] == [2, 1]
    cmp = (await client.get(f"/api/resumes/{rid}/compare", headers=auth,
                            params={"a": versions[1]["id"], "b": versions[0]["id"]})).json()
    assert cmp["skills_added"] == ["Appium"] and cmp["skills_removed"] == ["Python"]
    assert cmp["summary_changed"] is True

    listed = (await client.get("/api/resumes", headers=auth)).json()
    assert [x["name"] for x in listed] == ["SDET Resume"]


async def test_duplicate_archive_download_delete(client, db, auth):
    rid = (await upload(client, auth)).json()["id"]
    dup = await client.post(f"/api/resumes/{rid}/duplicate", headers=auth,
                            params={"name": "API Testing Resume"})
    assert dup.status_code == 201
    dup_id = dup.json()["id"]
    assert dup.json()["current_version"]["base_resume_id"] == rid

    assert (await client.post(f"/api/resumes/{rid}/archive", headers=auth)).json()["status"] == \
        "archived"
    assert [x["id"] for x in (await client.get("/api/resumes", headers=auth)).json()] == [dup_id]
    all_ = (await client.get("/api/resumes", headers=auth,
                             params={"include_archived": True})).json()
    assert len(all_) == 2

    dl = await client.get(f"/api/resumes/{dup_id}/download", headers=auth)
    assert dl.status_code == 200 and dl.content == SAMPLE_RESUME.encode()

    assert (await client.delete(f"/api/resumes/{rid}", headers=auth)).status_code == 204
    # The shared file survives because the duplicate still references it.
    assert (await client.get(f"/api/resumes/{dup_id}/download", headers=auth)).status_code == 200
    assert (await client.delete(f"/api/resumes/{dup_id}", headers=auth)).status_code == 204
    assert await db[c.RESUME_FILES].count_documents({}) == 0
    assert await db[c.RESUME_VERSIONS].count_documents({}) == 0


async def test_other_users_cannot_access(client, auth):
    rid = (await upload(client, auth)).json()["id"]
    other = await register(client, email="ravi@example.com", name="Ravi")
    for method, path in (("get", f"/api/resumes/{rid}"), ("get", f"/api/resumes/{rid}/download"),
                         ("delete", f"/api/resumes/{rid}")):
        r = await getattr(client, method)(path, headers=other)
        assert r.status_code == 404
    assert (await client.get("/api/resumes", headers=other)).json() == []


async def test_import_fills_empty_fields_but_never_overwrites(client, auth):
    await client.put("/api/profile", headers=auth,
                     json={"personal": {"name": "Asha R. Rao"}, "skills": {"primary": ["Java"]}})
    rid = (await upload(client, auth)).json()["id"]
    r = await client.post(f"/api/resumes/{rid}/import-to-profile", headers=auth)
    assert r.status_code == 200, r.text
    result = r.json()
    assert any(s.startswith("personal.name") for s in result["skipped"])
    assert "personal.email" in result["applied"]

    profile = (await client.get("/api/profile", headers=auth)).json()
    assert profile["personal"]["name"] == "Asha R. Rao"  # verified value kept
    assert profile["personal"]["email"] == "asha.rao@example.com"
    assert profile["skills"]["primary"] == ["Java"]
    assert "Selenium" in profile["skills"]["automation"]
    assert {e["company"] for e in profile["knowledge"]["experience"]} == \
        {"Acme Technologies", "Globex Corp"}

    # Re-import is idempotent.
    again = (await client.post(f"/api/resumes/{rid}/import-to-profile", headers=auth)).json()
    assert not any(a.startswith("knowledge.experience") for a in again["applied"])
    profile2 = (await client.get("/api/profile", headers=auth)).json()
    assert len(profile2["knowledge"]["experience"]) == 2


async def test_windows_ansi_text_resume_is_accepted(client, auth):
    r = await upload(client, auth, content=SAMPLE_RESUME.encode("cp1252"))
    assert r.status_code == 201, r.text
    exp = r.json()["current_version"]["parsed"]["experience"]
    assert exp[1]["end_date"] == "Dec 2021"  # en-dash range decoded correctly


async def test_binary_disguised_as_text_rejected(client, auth):
    r = await upload(client, auth, content=b"\x00\x01\x02binary", filename="x.txt")
    assert r.status_code == 415


async def test_import_into_brand_new_profile_persists_everything(client, auth):
    rid = (await upload(client, auth)).json()["id"]
    result = (await client.post(f"/api/resumes/{rid}/import-to-profile", headers=auth)).json()
    profile = (await client.get("/api/profile", headers=auth)).json()
    kb = profile["knowledge"]
    assert len(kb["experience"]) == 2
    assert len(kb["education"]) == 1
    assert kb["certifications"][0]["name"] == "ISTQB Certified Tester Foundation Level"
    assert "Java" in profile["skills"]["programming_languages"]
    assert "Skills" not in profile["unknown_fields"]
    assert result["completeness"] == profile["completeness"]


def test_years_from_roles_merges_overlaps():
    from app.resumes.service import _years_from_roles
    from app.schemas.resume import ParsedExperience, ParsedResume
    r = ParsedResume(experience=[
        ParsedExperience(company="A", title="QA", start_date="Jan 2020", end_date="Dec 2021"),
        ParsedExperience(company="B", title="QA", start_date="Jan 2021", end_date="Jan 2022"),  # overlaps A
    ])
    assert _years_from_roles(r) == 2.0
    undated = ParsedResume(experience=[ParsedExperience(company="A", title="QA")])
    assert _years_from_roles(undated) is None
