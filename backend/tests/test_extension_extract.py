"""Extension 2.1: /ext/extract (feed vs post vs job view vs Naukri vs JSON-LD text), /ext/chat, /ext/read-image, drafts and send-email."""

import base64

import pytest

from app.agents import llm
from app.database import collections as c
from app.extension import panel
from tests.job_fixtures import PROFILE, SDET_JD

FEED = """Feed post
Yale SOM
Yale School of Management · 2d
Congratulations to our newest graduates on completing the program. We are proud of every one of you!
Like Comment Repost Send
Rahul Mehta
Product Manager at Zoho
Excited to share that I completed my 5 year journey in product. Thanks to everyone who helped.
Like Comment Repost Send
Promoted
Learn Python in 30 days with our cohort based bootcamp. Enroll now and get a certificate.
Like Comment Repost Send
Sneha Iyer
Great webinar yesterday on leadership. Sharing my notes below for the community.
Like Comment Repost Send
""" * 2

HIRING_POST = """Acme Labs
We're hiring! SDET at Acme Labs, Bengaluru.
3-5 years with Selenium, Java and API testing. Immediate joiners preferred.
Send your CV to careers@acmelabs.com with subject: SDET Application"""

LINKEDIN_JOB = """Senior QA Automation Engineer
PayCo · Bengaluru, Karnataka, India (Hybrid)
About the job
Responsibilities
- Build Selenium frameworks in Java
Requirements
- 4+ years of experience in test automation
- Strong Java, Selenium, Jenkins and Postman skills"""

NAUKRI_JD = """Job description
Role: Performance Test Engineer
Company: Zenith Systems
Location: Pune
Experience: 3-6 years
Key skills: JMeter, LoadRunner, Java, SQL
Responsibilities
- Design load tests with JMeter and analyse results
Requirements
- 3-6 years of experience in performance testing"""

JSONLD_TEXT = """Software Development Engineer in Test
Responsibilities
- Own API automation with Rest Assured and Postman
Requirements
- 2+ years of experience with Java and Selenium
Location: Hyderabad"""


async def _pat(client, auth):
    await client.put("/api/profile", headers=auth, json=PROFILE)
    r = await client.post("/api/auth/tokens", headers=auth, json={"name": "Chrome extension"})
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_clean_title_strips_counters_and_suffixes():
    assert panel.clean_title("(23) Feed | LinkedIn") == "Feed"
    assert panel.clean_title("(3) Senior SDET - LinkedIn") == "Senior SDET"
    assert panel.clean_title("QA Engineer | Naukri.com") == "QA Engineer"


def test_feed_dump_is_not_a_job():
    r = panel.extract_fields(FEED, hint_title="(23) Feed | LinkedIn")
    assert r["is_job"] is False and r["role"] == ""


def test_hiring_post():
    r = panel.extract_fields(HIRING_POST)
    assert r["is_job"] and r["role"] == "SDET" and r["company"] == "Acme Labs"
    assert r["emails"] == ["careers@acmelabs.com"] and "Bengaluru" in r["location"] and "3" in r["experience"]


def test_linkedin_job_view():
    r = panel.extract_fields(LINKEDIN_JOB, hint_title="Senior QA Automation Engineer", hint_company="PayCo")
    assert r["is_job"] and r["role"] == "Senior QA Automation Engineer" and r["company"] == "PayCo" and "4" in r["experience"]


def test_naukri_jd():
    r = panel.extract_fields(NAUKRI_JD)
    assert r["is_job"] and r["role"] == "Performance Test Engineer" and r["company"] == "Zenith Systems"
    assert r["location"] == "Pune" and "3-6" in r["experience"].replace(" ", "")


def test_jsonld_style_text_and_hint():
    r = panel.extract_fields(JSONLD_TEXT, hint_title="Software Development Engineer in Test | LinkedIn", hint_company="Globex")
    assert r["is_job"] and r["role"] == "Software Development Engineer in Test" and r["company"] == "Globex"
    assert "Hyderabad" in r["location"]


def test_opening_at_pattern():
    r = panel.extract_fields("Exciting news! Data Engineer opening at Nimbus Cloud in Pune. Apply: jobs@nimbus.io. "
                             "2+ years of experience with SQL and Python.")
    assert r["role"] == "Data Engineer" and r["company"] == "Nimbus Cloud" and r["emails"] == ["jobs@nimbus.io"]


async def test_extract_endpoint_caps_text_and_needs_pat(client, auth):
    assert (await client.post("/api/ext/extract", headers=auth, json={"text": "x"})).status_code == 401
    pat = await _pat(client, auth)
    r = await client.post("/api/ext/extract", headers=pat, json={"text": HIRING_POST + "\n" + "filler " * 5000, "title": "(9) Feed | LinkedIn"})
    assert r.status_code == 200 and r.json()["role"] == "SDET" and r.json()["engine"] == "rules"
    feed = (await client.post("/api/ext/extract", headers=pat, json={"text": FEED, "title": "(23) Feed"})).json()
    assert feed["is_job"] is False


class FakeLLM:
    name = "fake"

    def __init__(self, reply):
        self.reply, self.calls = reply, []

    async def chat(self, *, system, messages):
        self.calls.append((system, messages))
        return self.reply


async def test_extract_uses_llm_only_for_facts_in_the_text(client, auth):
    pat = await _pat(client, auth)
    text = "Join our growing QA family! We need a Quality Wizard for Foo Corp. Email talent@foo.io."
    llm.set_provider(FakeLLM('{"is_job": true, "role": "Quality Wizard", "company": "Invented Inc", "location": "", "experience": "", '
                             '"emails": ["talent@foo.io", "x@y.com"]}'))
    try:
        r = (await client.post("/api/ext/extract", headers=pat, json={"text": text})).json()
    finally:
        llm.set_provider(None)
    assert r["engine"] == "llm" and r["role"] == "Quality Wizard" and r["company"] != "Invented Inc" and "x@y.com" not in r["emails"]


# ------------------------------------------------------------------ chat

async def test_chat_builtin_grounded_in_jd(client, auth, db):
    pat = await _pat(client, auth)
    r = await client.post("/api/ext/chat", headers=pat, json={"message": "What's missing?",
                                                              "job": {"role": "Senior SDET", "company": "PayCo", "text": SDET_JD}})
    assert r.status_code == 200, r.text
    assert "Kubernetes" in r.json()["reply"] and r.json()["engine"] == "builtin"
    iv = (await client.post("/api/ext/chat", headers=pat, json={"message": "Interview questions", "job": {"role": "SDET", "text": SDET_JD}})).json()
    assert "Selenium" in iv["reply"]
    assert await db[c.AGENT_RUNS].count_documents({"agent_name": "extension_chat"}) == 2


async def test_chat_truth_guard_drops_unverified_claims(client, auth):
    pat = await _pat(client, auth)
    llm.set_provider(FakeLLM("You have 9 years of Kubernetes experience.\nYou have Selenium and Java skills.\nThe role also asks for Kubernetes."))
    try:
        r = (await client.post("/api/ext/chat", headers=pat, json={"message": "Am I a fit?", "job": {"text": SDET_JD, "role": "SDET"}})).json()
    finally:
        llm.set_provider(None)
    assert r["engine"] == "claude" and r["guarded"] is True
    assert "9 years" not in r["reply"] and "Selenium and Java" in r["reply"] and "The role also asks for Kubernetes" in r["reply"]


# ------------------------------------------------------------------ images

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


async def test_read_image_without_key_uses_alt_text(client, auth):
    pat = await _pat(client, auth)
    r = (await client.post("/api/ext/read-image", headers=pat,
                           json={"image_url": "https://media.licdn.com/a.png", "alt": "Hiring SDET at Acme"})).json()
    assert r["available"] is False and r["text"] == "Hiring SDET at Acme" and "AI key" in r["message"]


class FakeVision(FakeLLM):
    def __init__(self, out):
        super().__init__("")
        self.out, self.seen = out, None

    async def describe_image(self, *, data, media_type, prompt):
        self.seen = (len(data), media_type)
        return self.out


async def test_read_image_with_mocked_llm(client, auth, monkeypatch):
    pat = await _pat(client, auth)
    fake = FakeVision("Role: SDET\nCompany: Acme\nEmail: hr@acme.com")
    llm.set_provider(fake)

    async def fetch(url):
        return PNG, "image/png"

    monkeypatch.setattr(panel, "_fetch_image", fetch)
    try:
        r = (await client.post("/api/ext/read-image", headers=pat, json={"image_url": "https://media.licdn.com/a.png"})).json()
        assert r["engine"] == "claude" and "hr@acme.com" in r["text"] and fake.seen[1] == "image/png"
        b64 = (await client.post("/api/ext/read-image", headers=pat, json={"base64": base64.b64encode(PNG).decode()})).json()
        assert b64["text"].startswith("Role: SDET")
        bad = await client.post("/api/ext/read-image", headers=pat, json={"base64": base64.b64encode(b"not an image at all").decode()})
        assert bad.status_code == 422
        fake.out = "NO_JOB_INFO"
        none = (await client.post("/api/ext/read-image", headers=pat, json={"base64": base64.b64encode(PNG).decode(), "alt": "logo"})).json()
        assert none["text"] == "logo" and "couldn't find" in none["message"]
    finally:
        llm.set_provider(None)


@pytest.mark.parametrize("url", ["http://media.licdn.com/a.png", "https://127.0.0.1/a.png", "https://localhost/a.png", "https://10.0.0.5/a.png",
                                 "https://169.254.169.254/latest", "https://example.com:8443/a.png"])
def test_image_urls_must_be_public_https(url):
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        panel._public_https(url)


# ------------------------------------------------------------------ drafts + send

POST = ("We're hiring! SDET at Acme Labs, Bengaluru. 3+ years with Selenium, Java and API testing. "
        "Send your CV to careers@acmelabs.com")


@pytest.fixture
def mail(monkeypatch):
    from app.email import outbound

    sent = []

    async def find_sender(db, uid):
        return {"email": "asha@gmail.com", "app_password_enc": "x"}

    async def send(integ, name, to, subject, body, attachments=None, html=None):
        sent.append({"to": to, "subject": subject, "body": body, "attachments": [a[0] for a in (attachments or [])]})
        return f"<mid{len(sent)}@gmail.com>"

    monkeypatch.setattr(outbound, "find_sender", find_sender)
    monkeypatch.setattr(outbound, "send", send)
    return sent


async def _draft(client, pat, company="Acme Labs"):
    r = await client.post("/api/ext/draft-application-email", headers=pat, json={"text": POST, "title": "SDET", "company": company})
    assert r.status_code == 200, r.text
    return r.json()


async def test_send_requires_confirm_and_gmail(client, auth, db):
    pat = await _pat(client, auth)
    b = await _draft(client, pat)
    payload = {"to": b["to"], "subject": b["subject"], "body": b["body"], "company": "Acme Labs", "attach_resume_id": b["resume_id"]}
    assert (await client.post("/api/ext/send-email", headers=pat, json=payload)).status_code == 422  # no confirm, no send
    no = await client.post("/api/ext/send-email", headers=pat, json={**payload, "confirm": True})
    assert no.status_code == 409 and "Connect Gmail" in no.json()["detail"]


async def test_send_application_email_full_flow(client, auth, db, mail):
    pat = await _pat(client, auth)
    b = await _draft(client, pat)
    payload = {"to": b["to"], "subject": b["subject"], "body": b["body"], "company": "Acme Labs", "role": "SDET",
               "attach_resume_id": b["resume_id"], "confirm": True}
    r = await client.post("/api/ext/send-email", headers=pat, json=payload)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["status"] == "sent" and out["sent_at"] and mail[0]["to"] == "careers@acmelabs.com" and mail[0]["attachments"][0].endswith(".pdf")
    assert await db[c.SENT_EMAILS].count_documents({"to_email": "careers@acmelabs.com"}) == 1
    audit = await db[c.AUDIT_LOGS].find_one({"action": "extension.email_sent"})
    assert "explicit_user_click" in audit["details"]["approval"]
    again = await client.post("/api/ext/send-email", headers=pat, json=payload)  # 14-day per-company guard
    assert again.status_code == 409 and "14 days" in again.json()["detail"] and len(mail) == 1


async def test_send_blocks_unverified_edit_and_pauses(client, auth, db, mail):
    pat = await _pat(client, auth)
    b = await _draft(client, pat)
    base = {"to": b["to"], "subject": b["subject"], "company": "Acme Labs", "confirm": True}
    bad = await client.post("/api/ext/send-email", headers=pat,
                            json={**base, "body": b["body"] + "\nI also have 8 years of Kubernetes and Terraform experience."})
    assert bad.status_code == 422 and not mail
    await client.put("/api/automation/settings", headers=auth, json={"pauses": {"emails": True}})
    paused = await client.post("/api/ext/send-email", headers=pat, json={**base, "body": b["body"]})
    assert paused.status_code == 423 and not mail


async def test_drafts_list_send_and_discard_outreach(client, auth, db, mail):
    pat = await _pat(client, auth)
    ct = (await client.post("/api/recruiters", headers=auth, json={"name": "Priya Nair", "company": "PayCo", "email": "priya@payco.com"})).json()
    d1 = (await client.post("/api/outreach/draft", headers=auth, json={"contact_id": ct["id"], "kind": "cold"})).json()
    d2 = (await client.post("/api/outreach/draft", headers=auth, json={"contact_id": ct["id"], "kind": "thank_you"})).json()
    data = (await client.get("/api/ext/drafts", headers=pat)).json()
    assert data["gmail_connected"] is True and {x["id"] for x in data["drafts"]} == {f"out:{d1['id']}", f"out:{d2['id']}"}
    item = next(x for x in data["drafts"] if x["id"] == f"out:{d1['id']}")
    r = await client.post("/api/ext/send-email", headers=pat, json={"draft_id": item["id"], "subject": item["subject"], "body": item["body"],
                                                                    "confirm": True})
    assert r.status_code == 200, r.text
    assert mail[0]["to"] == "priya@payco.com"
    sent = await db[c.OUTREACH].find_one({"_id": d1["id"]})
    assert sent["status"] == "sent" and await db[c.SENT_EMAILS].count_documents({"outreach_id": d1["id"]}) == 1
    assert (await client.post(f"/api/ext/drafts/out:{d2['id']}/discard", headers=pat)).status_code == 200
    assert (await db[c.OUTREACH].find_one({"_id": d2["id"]}))["status"] == "cancelled"
    assert (await client.get("/api/ext/drafts", headers=pat)).json()["drafts"] == []


async def test_outreach_send_respects_weekly_company_cap(client, auth, db, mail):
    pat = await _pat(client, auth)
    drafts = []
    for i in range(4):
        ct = (await client.post("/api/recruiters", headers=auth, json={"name": f"P{i} Nair", "company": "PayCo", "email": f"p{i}@payco.com"})).json()
        drafts.append((await client.post("/api/outreach/draft", headers=auth, json={"contact_id": ct["id"], "kind": "cold"})).json())
    codes = []
    for d in drafts:
        r = await client.post("/api/ext/send-email", headers=pat, json={"draft_id": f"out:{d['id']}", "subject": d["subject"], "body": d["body"],
                                                                        "confirm": True})
        codes.append(r.status_code)
    assert codes == [200, 200, 200, 429] and len(mail) == 3
