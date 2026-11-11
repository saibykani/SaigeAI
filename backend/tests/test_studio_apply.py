from app.database import collections as c
from app.email import smtp
from app.studio import apply
from tests.job_fixtures import PROFILE, SDET_JD
from tests.test_discover_send import FakeIMAP, FakeSMTP

POST = ("We're hiring! SDET at Acme Labs, Bengaluru. 3+ years with Selenium, Java and API testing. "
        "Share your resume to careers@acmelabs.io with current CTC, expected CTC and notice period. "
        "Use subject line \"SDET Application - Bengaluru\". No DMs please.\n\n" + SDET_JD)


def test_post_parsing():
    assert apply.emails_in("ping noreply@x.com or john@acme.io or hr@acme.io") == ["hr@acme.io", "john@acme.io"]
    assert apply.subject_asked(POST) == "SDET Application - Bengaluru"
    assert apply.coerce({"current_ctc": "12.5 LPA", "notice_period_days": "30", "bogus": "x", "phone": " "}) == {
        "current_ctc": 12.5, "notice_period_days": 30}


async def test_apply_by_email_asks_drafts_and_sends(client, auth, db, monkeypatch):
    FakeSMTP.sent = []
    from app.email import imap

    monkeypatch.setattr(smtp, "SMTP_FACTORY", FakeSMTP)
    monkeypatch.setattr(imap, "IMAP_FACTORY", FakeIMAP)
    profile = {**PROFILE, "personal": {k: v for k, v in PROFILE["personal"].items()
                                       if k not in ("current_ctc", "expected_ctc", "notice_period_days")}}
    assert (await client.put("/api/profile", headers=auth, json=profile)).status_code == 200
    r = (await client.post("/api/studio/apply/draft", headers=auth, json={"jd_text": POST, "title": "SDET"})).json()
    assert r["status"] == "needs_details" and r["emails_found"][0] == "careers@acmelabs.io"
    assert {"current_ctc", "expected_ctc", "notice_period_days"} <= {q["key"] for q in r["questions"]}
    answers = {"current_ctc": "12", "expected_ctc": "18", "notice_period_days": "30", "current_location": "Bengaluru", "phone": "+91 90000 00000"}
    r = await client.post("/api/studio/apply/draft", headers=auth, json={"jd_text": POST, "title": "SDET", "answers": answers})
    d = r.json()
    assert d["status"] == "ready", d
    assert d["to"] == "careers@acmelabs.io" and d["subject"] == "SDET Application - Bengaluru"
    assert "Expected CTC: 18 LPA" in d["body"] and "Notice period: 30 days" in d["body"]
    # facts typed in are saved, so the next post doesn't ask again
    assert (await client.get("/api/profile", headers=auth)).json()["personal"]["expected_ctc"] == 18
    send = {"resume_id": d["id"], "to": d["to"], "subject": d["subject"], "body": d["body"], "on": "2026-11-11"}
    assert (await client.post("/api/studio/apply/send", headers=auth, json=send)).status_code == 409  # Gmail not linked
    await client.post("/api/auth/connect/gmail-app-password", headers=auth,
                      json={"email": "asha@gmail.com", "app_password": FakeSMTP.password})
    s = await client.post("/api/studio/apply/send", headers=auth, json=send)
    assert s.status_code == 200, s.text
    msg = FakeSMTP.sent[0]
    assert msg["To"] == "careers@acmelabs.io" and msg["Subject"] == "SDET Application - Bengaluru"
    att = next(msg.iter_attachments())
    assert "_2026-11-11_Acme" in att.get_filename() and att.get_content().startswith(b"%PDF")
    assert await db[c.AGENT_RUNS].find_one({"agent_name": "apply_by_email", "status": "succeeded"})
    assert await db[c.NOTIFICATIONS].find_one({"kind": "application_emailed"})
    # a made-up claim in an edited email is blocked by the truth guard
    bad = {**send, "body": d["body"] + "\nI also have 15 years of Kubernetes and Rust experience at Google."}
    assert (await client.post("/api/studio/apply/send", headers=auth, json=bad)).status_code == 422


async def test_confirmed_skills_raise_the_ats_score(client, auth):
    assert (await client.put("/api/profile", headers=auth, json=PROFILE)).status_code == 200
    first = (await client.post("/api/studio/resume", headers=auth, json={"jd_text": SDET_JD, "title": "SDET", "company": "Acme"})).json()
    missing = first["ats"]["missing_required"] + first["ats"]["missing_preferred"]
    assert all(k in first["resume"]["skills"] for k in first["ats"]["matched_keywords"] if k not in missing)
    if not missing:
        return
    r = await client.post("/api/studio/skills/confirm", headers=auth, json={"skills": missing})
    assert r.status_code == 200 and r.json()["added"]
    again = (await client.post("/api/studio/resume", headers=auth, json={"jd_text": SDET_JD, "title": "SDET", "company": "Acme"})).json()
    assert again["ats"]["required_coverage"] == 100 and again["ats"]["score"] > first["ats"]["score"]


async def test_projects_from_every_uploaded_resume_reach_the_ats_resume(client, auth, db):
    from app.utils import new_id, utcnow

    assert (await client.put("/api/profile", headers=auth, json=PROFILE)).status_code == 200
    me = await db[c.USERS].find_one({"email": "asha@example.com"})
    for projects in ([{"name": "Video Customer Identification Platform", "highlights": ["Automated KYC with Selenium."]}],
                     [{"name": "Video Customer Identification Platform (VCIP)", "highlights": ["Ran JMeter load tests on VCIP APIs."]},
                      {"name": "NGO Project Management System (PPMS)", "highlights": ["Automated donor onboarding with Selenium."]},
                      {"name": "Residential Welfare Association Platform", "highlights": ["Automated visitor management with Cucumber."]}]):
        rid, vid = new_id(), new_id()
        await db[c.RESUMES].insert_one({"_id": rid, "user_id": me["_id"], "name": "Upload", "kind": "Master", "status": "active",
                                        "current_version_id": vid, "created_at": utcnow()})
        await db[c.RESUME_VERSIONS].insert_one({"_id": vid, "resume_id": rid, "parsed": {"projects": projects}})
    r = (await client.post("/api/studio/resume", headers=auth, json={"jd_text": SDET_JD, "title": "SDET", "company": "Acme"})).json()
    names = [p["name"] for p in r["resume"]["projects"]]
    assert "Video Customer Identification Platform (VCIP)" in names and "NGO Project Management System (PPMS)" in names
    assert sum("Video Customer" in n for n in names) == 1
    vcip = next(p for p in r["resume"]["projects"] if "VCIP" in p["name"])
    assert len(vcip["highlights"]) == 2
    prof = (await client.get("/api/profile", headers=auth)).json()
    assert len([p for p in prof["knowledge"]["projects"] if "Video" in p["name"]]) == 1


async def test_gmail_api_is_used_when_oauth_can_send(db, monkeypatch):
    from app.email import gmail, outbound
    from app.services import crypto

    sent = []

    async def token(rt):
        return "tok"

    async def send_raw(tok, raw):
        sent.append(raw)
        return "gid"

    monkeypatch.setattr(gmail, "access_token", token)
    monkeypatch.setattr(gmail, "send_raw", send_raw)
    await db[c.INTEGRATIONS].insert_one({"user_id": "u1", "provider": "gmail", "email": "me@gmail.com",
                                         "refresh_token_enc": crypto.encrypt("rt"), "scopes": [outbound.SEND_SCOPE]})
    integ = await outbound.find_sender(db, "u1")
    assert integ and (await outbound.send(integ, "Me", "hr@x.com", "Hi", "Body text")).startswith("<")
    assert len(sent) == 1
    await db[c.INTEGRATIONS].insert_one({"user_id": "u2", "provider": "gmail", "email": "x@gmail.com", "refresh_token_enc": "e", "scopes": []})
    assert await outbound.find_sender(db, "u2") is None


async def test_inbox_keeps_only_job_mail(client, auth, db):
    from app.email.classifier import is_job_related as job

    assert job("Rahul HR <r@gmail.com>", "Re: Application for QA Automation Engineer", "Please share your CTC")
    assert job("Priya <p@acme.com>", "Quick chat?", "We are hiring for an SDET position. Are you open?")
    assert not job("SBI <sbi@communications.sbi.co.in>", "Activate Your UPI on YONO SBI", "Your bank account")
    assert not job("Google <no-reply@accounts.google.com>", "Security alert", "New sign-in to your account")
    assert not job("Team Scaler <hello@scaler.com>", "Become an FDE", "Our hiring partners love this course. Unsubscribe")
    junk = {"sender": "Amazon <order@amazon.in>", "subject": "Your order has shipped", "body": "Track your package"}
    r = await client.post("/api/emails/import", headers=auth, json=junk)
    assert r.status_code == 201 and r.json()["category"] == "Skipped"
    keep = {"sender": "HR <hr@acme.com>", "subject": "Your application for SDET", "body": "We received your application."}
    assert (await client.post("/api/emails/import", headers=auth, json=keep)).status_code == 201
    await db[c.EMAILS].insert_one({"_id": "old", "user_id": (await db[c.USERS].find_one({}))["_id"], "sender": "SBI <a@sbi.co.in>",
                                   "subject": "Statement ready", "body": "Bank statement", "category": "Other", "application_id": None,
                                   "received_at": __import__("datetime").datetime(2026, 11, 1), "confidence": 0.3})
    subjects = [e["subject"] for e in (await client.get("/api/emails", headers=auth)).json()]
    assert subjects == ["Your application for SDET"]
