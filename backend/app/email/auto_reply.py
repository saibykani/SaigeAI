"""Auto-reply drafts: when a recruiter emails you, Saige drafts the answer to what they asked
(CTC, notice period, location, experience, resume, availability, job details) using only verified
profile facts, and puts it in Recruiters → Queue with the resume attached when they asked for one.
You approve it and it's sent from your Gmail. Nothing unverified is ever stated: unknown values are
left for you to fill in.
"""

import re

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.automation.service import get_settings_doc
from app.database import collections as c
from app.profiles.service import get_profile
from app.services.audit import log_action
from app.services.notify import notify
from app.utils import new_id, utcnow

ASKS: dict[str, re.Pattern[str]] = {
    "ctc": re.compile(r"\b(ctc|salary|compensation|package|lpa|expected (pay|salary))\b", re.I),
    "notice": re.compile(r"\bnotice( period)?\b|\bjoin(ing)? (date|time)|how soon can you join|last working day", re.I),
    "location": re.compile(r"\b(current location|where are you (based|located)|relocat\w*|preferred location|work from office|hybrid)\b", re.I),
    "experience": re.compile(r"\b(years of experience|total experience|relevant experience|how many years)\b", re.I),
    "resume": re.compile(r"\b(resume|cv|curriculum vitae|updated profile)\b", re.I),
    "call": re.compile(r"\b(call|chat|connect|discuss|availability|available|schedule|slot|interview)\b", re.I),
    "job": re.compile(r"\b(job id|requisition|role|position|opening|opportunity|jd|job description)\b", re.I),
}


def detect(subject: str, body: str) -> list[str]:
    text = f"{subject}\n{body[:4000]}"
    return [k for k, pat in ASKS.items() if pat.search(text)]


def _money(v: float | None, cur: str | None) -> str | None:
    if not v:
        return None
    if (cur or "INR").upper() == "INR" and v >= 100000:
        return f"₹{v / 100000:g} LPA"
    return f"{cur or ''} {v:,.0f}".strip()


def compose(profile, asks: list[str], s, sender_first: str, subject: str) -> tuple[str, str, bool]:
    """(subject, body, attach_resume) from verified facts only."""
    p, pref = profile.personal, profile.preferences
    lines: list[str] = []
    if s.talent_details:
        if "experience" in asks and p.total_experience_years:
            lines.append(f"Total experience: {p.total_experience_years:g} years"
                         + (f", currently {p.current_designation}" if p.current_designation else "")
                         + (f" at {p.current_company}" if p.current_company else "") + ".")
        if "ctc" in asks:
            cur, exp = _money(p.current_ctc, p.ctc_currency), _money(p.expected_ctc, p.ctc_currency)
            if cur or exp:
                lines.append("CTC: " + ", ".join(x for x in (f"current {cur}" if cur else "", f"expected {exp}" if exp else "") if x) + ".")
            else:
                lines.append("CTC: [add your current and expected CTC].")
        if "notice" in asks:
            lines.append(f"Notice period: {p.notice_period_days} days." if p.notice_period_days is not None
                         else "Notice period: [add your notice period].")
        if "location" in asks:
            loc = p.current_location or "[your current location]"
            extra = f"; open to {', '.join(pref.preferred_locations[:3])}" if pref.preferred_locations else ""
            reloc = "; open to relocation" if pref.relocation else ""
            lines.append(f"Location: {loc}{extra}{reloc}.")
    attach = s.resume and "resume" in asks
    if attach:
        lines.append("I've attached my latest resume.")
    if s.next_step and "call" in asks:
        lines.append("I'm happy to have a call. Please share a couple of time slots that work for you.")
    if s.job_details and "job" in asks and not re.search(r"job id|requisition|https?://", subject, re.I):
        lines.append("Could you share the job ID or the posting link, so I can review the role and apply through the right channel?")
    if not lines:
        lines.append("Thank you for reaching out. I'm interested and would be glad to learn more about the role.")
    hi = f"Hi {sender_first}," if sender_first else "Hi,"
    facts = [f"• {x}" for x in lines if re.match(r"^[A-Z][A-Za-z ]{1,20}:", x)]
    notes = [x for x in lines if not re.match(r"^[A-Z][A-Za-z ]{1,20}:", x)]
    parts = [hi, "", "Thank you for reaching out."]
    if facts:
        parts += ["", "Here are my details:", *facts]
    if notes:
        parts += ["", *notes]
    body = "\n".join([*parts, "", "Best regards,", p.name or ""] + ([p.phone] if p.phone else []))
    subj = subject if subject.lower().startswith("re:") else f"Re: {subject}"
    return subj[:200], body.strip()[:5000], attach


async def draft_reply(db: AsyncIOMotorDatabase, user_id: str, email: dict) -> dict | None:
    """Create a reply draft for an inbound recruiter email (once per email)."""
    from app.recruiters.service import _company_from_domain, check_truth, create_contact
    from app.schemas.recruiter import ContactIn

    s = await get_settings_doc(db, user_id)
    if not s.auto_reply.enabled:
        return None
    ex = email.get("extracted") or {}
    addr = ex.get("sender_email")
    if not addr or re.match(r"(no-?reply|donotreply|notifications?|jobs|careers|mailer-daemon|postmaster)@", addr, re.I):
        return None
    if await db[c.OUTREACH].find_one({"user_id": user_id, "email_id": email["_id"]}):
        return None
    asks = detect(email["subject"], email["body"])
    company = _company_from_domain(ex.get("sender_domain") or "") or ex.get("company") or "Recruiter"
    name = ex.get("sender_name") or addr.split("@")[0].replace(".", " ").title()
    contact, _ = await create_contact(db, user_id, ContactIn(name=name[:120], company=company[:160], email=addr,
                                                             source="gmail", role="recruiter"))
    profile = await get_profile(db, user_id)
    subject, body, attach = compose(profile, asks, s.auto_reply, name.split()[0] if name else "", email["subject"])
    now = utcnow()
    doc = {"_id": new_id(), "user_id": user_id, "contact_id": contact["_id"], "contact_name": contact["name"],
           "company": contact["company"], "company_key": contact.get("company_key"), "job_id": None, "parent_id": None,
           "email_id": email["_id"], "kind": "reply", "status": "draft", "subject": subject, "body": body,
           "attach_resume": attach, "asks": asks, "validation": check_truth(profile, body),
           "approved_at": None, "sent_at": None, "replied_at": None, "created_at": now, "updated_at": now}
    await db[c.OUTREACH].insert_one(doc)
    await log_action(db, user_id=user_id, action="outreach.reply_drafted", entity="outreach", entity_id=doc["_id"],
                     details={"asks": asks, "company": contact["company"]})
    await notify(db, user_id=user_id, kind="reply_drafted", title=f"Reply ready for {contact['name']}",
                 body=f"They asked about: {', '.join(asks) or 'the role'}. Review and send it from Recruiters.",
                 link="/recruiters")
    return doc
