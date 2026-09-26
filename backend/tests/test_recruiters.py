"""Phase 7: recruiter contacts, referral / cold outreach, caps, follow-ups and reply detection."""

from datetime import timedelta

from app.database import collections as c
from app.utils import utcnow
from tests.job_fixtures import PROFILE, SDET_JD

CONTACT = {"name": "Priya Nair", "company": "PayCo", "email": "priya@payco.com", "role": "referral"}


async def _setup(client, auth):
    assert (await client.put("/api/profile", headers=auth, json=PROFILE)).status_code == 200
    job = (await client.post("/api/jobs/import", headers=auth, json={
        "title": "Senior SDET", "company": "PayCo Technologies", "location": "Bengaluru", "description": SDET_JD})).json()["job"]
    contact = (await client.post("/api/recruiters", headers=auth, json=CONTACT)).json()
    return job, contact


async def _sent(client, auth, contact_id, job_id=None, kind="referral"):
    d = (await client.post("/api/outreach/draft", headers=auth,
                           json={"contact_id": contact_id, "job_id": job_id, "kind": kind})).json()
    assert (await client.post(f"/api/outreach/{d['id']}/approve", headers=auth)).status_code == 200
    r = await client.post(f"/api/outreach/{d['id']}/mark-sent", headers=auth)
    return d, r


async def test_contacts_crud_and_duplicates(client, auth):
    r = await client.post("/api/recruiters", headers=auth, json=CONTACT)
    assert r.status_code == 201 and r.json()["company"] == "PayCo"
    dup = await client.post("/api/recruiters", headers=auth, json={**CONTACT, "name": "P. Nair", "email": "PRIYA@payco.com"})
    assert dup.status_code == 409
    li = await client.post("/api/recruiters", headers=auth, json={"name": "Ravi", "company": "Acme",
                                                                  "linkedin_url": "linkedin.com/in/ravi-k"})
    assert li.json()["linkedin_url"] == "https://linkedin.com/in/ravi-k"
    again = await client.post("/api/recruiters", headers=auth, json={"name": "Ravi K", "company": "Acme",
                                                                     "linkedin_url": "https://www.linkedin.com/in/Ravi-K/"})
    assert again.status_code == 409
    cid = r.json()["id"]
    assert (await client.put(f"/api/recruiters/{cid}", headers=auth, json={"title": "EM"})).json()["title"] == "EM"
    assert len((await client.get("/api/recruiters", headers=auth, params={"q": "acme"})).json()) == 1
    comps = (await client.get("/api/recruiters/companies", headers=auth)).json()
    assert {x["company"] for x in comps} == {"PayCo", "Acme"}
    assert (await client.delete(f"/api/recruiters/{cid}", headers=auth)).status_code == 204


async def test_csv_import(client, auth):
    csv = ("Name,Company,Email,Title,Role\nAnu,Globex,anu@globex.com,Recruiter,recruiter\n"
           "Anu again,Globex,anu@globex.com,,\nBad,,x@y.com,,\nSam,Initech,not-an-email,,\n")
    r = (await client.post("/api/recruiters/import-csv", headers=auth, json={"csv": csv})).json()
    assert r["created"] == 1 and r["duplicates"] == 1 and len(r["errors"]) == 2
    linkedin = ('Notes:\n"When exporting your connection data, you may notice that some email addresses are missing."\n\n'
                "First Name,Last Name,URL,Email Address,Company,Position,Connected On\n"
                "Kiran,Rao,https://www.linkedin.com/in/kiran-rao,,Initech,QA Manager,01 Jan 2026\n")
    r2 = (await client.post("/api/recruiters/import-csv", headers=auth, json={"csv": linkedin})).json()
    assert r2["created"] == 1, r2
    kiran = next(x for x in (await client.get("/api/recruiters", headers=auth)).json() if x["company"] == "Initech")
    assert kiran["name"] == "Kiran Rao" and kiran["title"] == "QA Manager" and kiran["linkedin_url"].endswith("kiran-rao")
    bad = await client.post("/api/recruiters/import-csv", headers=auth, json={"csv": "email\nx@y.com\n"})
    assert bad.status_code == 422


async def test_referral_draft_is_truthful_and_job_specific(client, auth):
    job, contact = await _setup(client, auth)
    found = (await client.get(f"/api/recruiters/for-job/{job['id']}", headers=auth)).json()
    assert [x["id"] for x in found["contacts"]] == [contact["id"]]  # "PayCo" matches "PayCo Technologies"
    d = (await client.post("/api/outreach/draft", headers=auth, json={
        "contact_id": contact["id"], "job_id": job["id"], "kind": "referral",
        "context": "We met at the Bengaluru testing meetup"})).json()
    assert d["status"] == "draft" and d["validation"]["status"] == "PASSED"
    assert d["subject"] == "Referral request: Senior SDET at PayCo Technologies"
    assert d["body"].startswith("Hi Priya,") and "testing meetup" in d["body"]
    assert "Kubernetes" not in d["body"]  # never claims a skill the profile lacks
    assert d["mailto"].startswith("mailto:priya@payco.com") and d["gmail_compose"]
    # Editing in an unverified claim is refused.
    bad = await client.put(f"/api/outreach/{d['id']}", headers=auth,
                           json={"subject": d["subject"], "body": d["body"] + "\nI have 12 years of Kubernetes experience."})
    assert bad.status_code == 422


async def test_send_requires_approval_and_schedules_followups(client, auth, db):
    job, contact = await _setup(client, auth)
    d = (await client.post("/api/outreach/draft", headers=auth, json={"contact_id": contact["id"], "job_id": job["id"]})).json()
    assert (await client.post(f"/api/outreach/{d['id']}/mark-sent", headers=auth)).status_code == 409
    await client.post(f"/api/outreach/{d['id']}/approve", headers=auth)
    r = await client.post(f"/api/outreach/{d['id']}/mark-sent", headers=auth)
    assert r.status_code == 200 and r.json()["status"] == "sent"
    fus = await db[c.FOLLOWUPS].find({"outreach_id": d["id"]}).to_list(10)
    assert sorted(f["sequence"] for f in fus) == [1, 2, 3]
    # Make the first follow-up due and check it's listed.
    await db[c.FOLLOWUPS].update_one({"outreach_id": d["id"], "sequence": 1}, {"$set": {"due_at": utcnow() - timedelta(hours=1)}})
    st = (await client.get("/api/outreach/stats", headers=auth)).json()
    assert st["sent_today"] == 1 and st["remaining_today"] == 9 and len(st["followups_due"]) == 1
    follow = (await client.post("/api/outreach/draft", headers=auth, json={
        "contact_id": contact["id"], "kind": "followup", "parent_id": d["id"]})).json()
    assert follow["subject"].startswith("Re: Referral request")


async def test_daily_and_company_caps(client, auth, db):
    await _setup(client, auth)
    # Three people at PayCo is the weekly limit per company.
    ids = []
    for i in range(4):
        ct = (await client.post("/api/recruiters", headers=auth,
                                json={"name": f"P{i}", "company": "PayCo", "email": f"p{i}@payco.com"})).json()
        ids.append(ct["id"])
    for cid in ids[:3]:
        assert (await _sent(client, auth, cid, kind="cold"))[1].status_code == 200
    _, r = await _sent(client, auth, ids[3], kind="cold")
    assert r.status_code == 429 and "this week" in r.json()["detail"]
    # Daily cap: the user's limit (never above 10).
    await client.put("/api/automation/settings", headers=auth, json={"limits": {
        "daily_application_limit": 20, "daily_email_limit": 20, "daily_recruiter_contact_limit": 4, "min_match_score": 70}})
    other = (await client.post("/api/recruiters", headers=auth, json={"name": "Z", "company": "Zeta", "email": "z@zeta.io"})).json()
    assert (await _sent(client, auth, other["id"], kind="cold"))[1].status_code == 200
    other2 = (await client.post("/api/recruiters", headers=auth, json={"name": "Y", "company": "Yotta", "email": "y@yotta.io"})).json()
    _, r = await _sent(client, auth, other2["id"], kind="cold")
    assert r.status_code == 429 and "Daily outreach limit" in r.json()["detail"]


async def test_pause_blocks_sending(client, auth):
    _, contact = await _setup(client, auth)
    await client.put("/api/automation/settings", headers=auth, json={"pauses": {"recruiter_outreach": True}})
    _, r = await _sent(client, auth, contact["id"])
    assert r.status_code == 423


async def test_reply_email_stops_followups(client, auth, db):
    job, contact = await _setup(client, auth)
    d, _ = await _sent(client, auth, contact["id"], job["id"])
    r = await client.post("/api/emails/import", headers=auth, json={
        "sender": "Priya Nair <priya@payco.com>", "subject": "Re: Referral request", "body": "Happy to refer you!"})
    assert r.status_code == 201
    msg = (await client.get("/api/outreach", headers=auth)).json()[0]
    assert msg["status"] == "replied" and msg["replied_at"]
    assert await db[c.FOLLOWUPS].count_documents({"outreach_id": d["id"], "status": "scheduled"}) == 0
    assert await db[c.NOTIFICATIONS].find_one({"kind": "outreach_reply"})


async def test_bounce_and_unsubscribe(client, auth, db):
    job, contact = await _setup(client, auth)
    d, _ = await _sent(client, auth, contact["id"], job["id"])
    await client.post("/api/emails/import", headers=auth, json={
        "sender": "Mail Delivery Subsystem <mailer-daemon@googlemail.com>", "subject": "Delivery Status Notification",
        "body": "Address not found: priya@payco.com could not be delivered."})
    assert (await client.get("/api/outreach", headers=auth)).json()[0]["status"] == "bounced"
    r = await client.post(f"/api/outreach/{d['id']}/outcome/unsubscribed", headers=auth)
    assert r.status_code == 200
    assert (await client.get("/api/recruiters", headers=auth)).json()[0]["unsubscribed"] is True
    blocked = await client.post("/api/outreach/draft", headers=auth, json={"contact_id": contact["id"]})
    assert blocked.status_code == 409


async def test_import_contacts_from_inbox(client, auth):
    await client.post("/api/emails/import", headers=auth, json={
        "sender": "Meera Iyer <meera@globex.com>", "subject": "Opportunity: QA Lead at Globex",
        "body": "Hi, I'm a recruiter at Globex and came across your profile. Would you be interested in a QA Lead role?"})
    await client.post("/api/emails/import", headers=auth, json={
        "sender": "Jobs <noreply@naukri.com>", "subject": "Jobs for you", "body": "Would you be interested in these roles"})
    r = (await client.post("/api/recruiters/import-inbox", headers=auth)).json()
    assert r["created"] == 1
    contacts = (await client.get("/api/recruiters", headers=auth)).json()
    assert contacts[0]["company"] == "Globex" and contacts[0]["source"] == "gmail"
    again = (await client.post("/api/recruiters/import-inbox", headers=auth)).json()
    assert again["created"] == 0 and again["duplicates"] == 1


async def test_contacts_are_private(client, auth):
    from tests.conftest import register

    _, contact = await _setup(client, auth)
    other = await register(client, email="other@example.com")
    assert (await client.get("/api/recruiters", headers=other)).json() == []
    assert (await client.post("/api/outreach/draft", headers=other, json={"contact_id": contact["id"]})).status_code == 404


async def test_templates_and_new_kinds(client, auth, db):
    job, contact = await _setup(client, auth)
    tpls = (await client.get("/api/outreach/templates", headers=auth)).json()
    kinds = [t["kind"] for t in tpls]
    assert kinds == ["cold", "hiring_manager", "referral", "employee_intro", "linkedin_note", "followup", "thank_you"]
    by = {t["kind"]: t for t in tpls}
    assert by["cold"]["body"].startswith("Hi [First name],") and "[Company]" in by["cold"]["body"]
    assert len(by["linkedin_note"]["body"]) <= 300
    assert "Kubernetes" not in " ".join(t["body"] for t in tpls)
    for kind in ("hiring_manager", "employee_intro", "linkedin_note"):
        d = (await client.post("/api/outreach/draft", headers=auth,
                               json={"contact_id": contact["id"], "job_id": job["id"], "kind": kind})).json()
        assert d["validation"]["status"] == "PASSED", (kind, d["validation"])
    note = (await client.get("/api/outreach", headers=auth)).json()
    ln = next(o for o in note if o["kind"] == "linkedin_note")
    assert len(ln["body"]) <= 300
    await client.post(f"/api/outreach/{ln['id']}/approve", headers=auth)
    await client.post(f"/api/outreach/{ln['id']}/mark-sent", headers=auth)
    assert await db[c.FOLLOWUPS].count_documents({"outreach_id": ln["id"]}) == 0  # no email follow-ups for a LinkedIn note
