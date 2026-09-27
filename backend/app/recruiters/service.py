"""Recruiter contacts, referral and cold outreach, follow-ups (spec sections 24-26).

Rules enforced here, never in the UI alone:
- contacts come only from the user (manual, CSV, their own inbox, a job's posted contact);
- every draft is truth-checked against the verified profile before it can be approved;
- nothing is sent by Saige: the user sends from their own mail client or LinkedIn and marks it sent;
- a message must be approved before it can be marked sent;
- at most 10 messages a day (or the user's lower limit) and 3 per company per 7 days;
- follow-ups (day 3, 7, 14) stop on a reply, bounce, unsubscribe or cancel.
"""

import csv
import io
import re
from datetime import datetime, timedelta
from urllib.parse import quote

from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import DESCENDING

from app.automation.service import get_settings_doc, is_allowed
from app.database import collections as c
from app.jobs.dedupe import company_key
from app.profiles.service import get_profile
from app.schemas.profile import Profile
from app.schemas.recruiter import ContactIn, ContactUpdate, DraftIn
from app.services.audit import log_action
from app.services.notify import notify
from app.services.skills_vocab import normalize_key
from app.services.truth_guard import GeneratedClaims, validate_claims
from app.utils import as_utc, new_id, utcnow

HARD_DAILY_CAP = 10
PER_COMPANY_WEEKLY_CAP = 3
FOLLOWUP_DAYS = (3, 7, 14)
FOLLOWUP_KINDS = ("referral", "cold", "hiring_manager", "employee_intro")  # first-touch emails
TEMPLATE_INFO = [
    ("cold", "Cold email to HR / recruiter", "HR · recruiter", "Introduce yourself for a specific role or the team's openings."),
    ("hiring_manager", "Email to a hiring manager", "Hiring manager", "Short, direct note to the person who leads the team."),
    ("referral", "Ask an employee for a referral", "Employee", "For someone you know at the company. Add how you know them."),
    ("employee_intro", "Informational chat with an employee", "Employee", "Ask for 15 minutes of perspective, with no referral request."),
    ("linkedin_note", "LinkedIn connection note", "Anyone", "Fits LinkedIn's 300-character limit for connection requests."),
    ("followup", "Follow-up", "Anyone you've emailed", "A polite nudge 3–7 days after your first message."),
    ("thank_you", "Thank-you note", "Interviewer · recruiter", "Send within a day of a call or interview."),
]
OPEN = ("draft", "approved")
FINAL = ("replied", "bounced", "unsubscribed", "cancelled", "no_response")
GENERIC_DOMAINS = {"gmail.com", "googlemail.com", "yahoo.com", "outlook.com", "hotmail.com", "live.com",
                   "icloud.com", "proton.me", "protonmail.com", "rediffmail.com", "aol.com"}


def email_key(email: str | None) -> str | None:
    return email.strip().lower() if email else None


def linkedin_key(url: str | None) -> str | None:
    if not url:
        return None
    m = re.search(r"linkedin\.com/in/([^/?#]+)", url, re.I)
    return m.group(1).lower() if m else url.strip().lower().rstrip("/")


def contact_out(d: dict) -> dict:
    return {
        "id": d["_id"], "name": d["name"], "company": d["company"], "email": d.get("email"), "phone": d.get("phone"),
        "linkedin_url": d.get("linkedin_url"), "title": d.get("title"), "role": d.get("role", "recruiter"),
        "tags": d.get("tags", []), "notes": d.get("notes"), "source": d.get("source", "manual"),
        "unsubscribed": d.get("unsubscribed", False),
        "last_contacted_at": d["last_contacted_at"].isoformat() if d.get("last_contacted_at") else None,
        "created_at": d["created_at"].isoformat(),
    }


# ------------------------------------------------------------------ contacts

def phone_key(phone: str | None) -> str | None:
    digits = re.sub(r"\D", "", phone or "")
    return digits[-10:] if len(digits) >= 10 else None


async def find_duplicate(db: AsyncIOMotorDatabase, user_id: str, email: str | None, linkedin: str | None,
                         exclude_id: str | None = None, *, phone: str | None = None, name: str | None = None,
                         company: str | None = None) -> dict | None:
    ors: list[dict] = []
    if email_key(email):
        ors.append({"email_key": email_key(email)})
    if linkedin_key(linkedin):
        ors.append({"linkedin_key": linkedin_key(linkedin)})
    if phone_key(phone):
        ors.append({"phone_key": phone_key(phone)})
    if not ors and name and company:  # portal recruiters may come with only a name and company
        ors.append({"name": name, "company_key": company_key(company)})
    if not ors:
        return None
    q: dict = {"user_id": user_id, "$or": ors}
    if exclude_id:
        q["_id"] = {"$ne": exclude_id}
    return await db[c.RECRUITER_CONTACTS].find_one(q)


async def create_contact(db: AsyncIOMotorDatabase, user_id: str, body: ContactIn) -> tuple[dict, bool]:
    """Returns (contact, created). An existing contact with the same email or LinkedIn is returned as-is."""
    dup = await find_duplicate(db, user_id, body.email, body.linkedin_url, phone=body.phone, name=body.name, company=body.company)
    if dup:
        return dup, False
    now = utcnow()
    doc = {"_id": new_id(), "user_id": user_id, **body.model_dump(mode="json"),
           "email_key": email_key(body.email), "linkedin_key": linkedin_key(body.linkedin_url), "phone_key": phone_key(body.phone),
           "company_key": company_key(body.company), "unsubscribed": False, "last_contacted_at": None,
           "created_at": now, "updated_at": now}
    await db[c.RECRUITER_CONTACTS].insert_one(doc)
    await log_action(db, user_id=user_id, action="recruiter.added", entity="recruiter_contact", entity_id=doc["_id"],
                     details={"company": body.company, "source": body.source})
    return doc, True


async def get_contact(db: AsyncIOMotorDatabase, user_id: str, contact_id: str) -> dict:
    doc = await db[c.RECRUITER_CONTACTS].find_one({"_id": contact_id, "user_id": user_id})
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contact not found")
    return doc


async def update_contact(db: AsyncIOMotorDatabase, user_id: str, contact_id: str, body: ContactUpdate) -> dict:
    await get_contact(db, user_id, contact_id)
    patch = body.model_dump(mode="json", exclude_unset=True)
    if ("email" in patch or "linkedin_url" in patch) and await find_duplicate(
            db, user_id, patch.get("email"), patch.get("linkedin_url"), exclude_id=contact_id):
        raise HTTPException(status.HTTP_409_CONFLICT, "Another contact already has this email or LinkedIn URL")
    if "email" in patch:
        patch["email_key"] = email_key(patch["email"])
    if "linkedin_url" in patch:
        patch["linkedin_key"] = linkedin_key(patch["linkedin_url"])
    if "phone" in patch:
        patch["phone_key"] = phone_key(patch["phone"])
    if patch.get("company"):
        patch["company_key"] = company_key(patch["company"])
    await db[c.RECRUITER_CONTACTS].update_one({"_id": contact_id}, {"$set": {**patch, "updated_at": utcnow()}})
    return await get_contact(db, user_id, contact_id)


CSV_ALIASES = {
    "name": ("name", "full name", "contact", "contact name"),
    "company": ("company", "organisation", "organization", "employer"),
    "email": ("email", "email address", "e-mail"),
    "linkedin_url": ("linkedin", "linkedin url", "linkedin_url", "profile", "profile url", "url"),
    "title": ("title", "position", "designation", "job title"),
    "role": ("role", "type"),
    "notes": ("notes", "note"),
}


async def import_csv(db: AsyncIOMotorDatabase, user_id: str, text: str) -> dict:
    text = text.lstrip("﻿")
    # LinkedIn's "Export connections" file starts with a few "Notes:" lines before the header row.
    lines = text.splitlines()
    for i, line in enumerate(lines[:10]):
        first = line.lower().split(",")[0].strip()
        if first in ("first name", "name", "full name", "contact", "contact name"):
            text = "\n".join(lines[i:])
            break
    reader = csv.DictReader(io.StringIO(text))
    headers = {h.strip().lower(): h for h in (reader.fieldnames or [])}
    colmap = {field: headers[a] for field, aliases in CSV_ALIASES.items() for a in aliases if a in headers}
    split_name = "name" not in colmap and "first name" in headers
    if (not split_name and "name" not in colmap) or "company" not in colmap:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "CSV needs at least 'name' and 'company' columns")
    result = {"created": 0, "duplicates": 0, "errors": []}
    for i, row in enumerate(reader, start=2):
        if i > 2001:
            result["errors"].append("Stopped after 2000 rows")
            break
        data = {f: (row.get(col) or "").strip() or None for f, col in colmap.items()}
        if split_name:
            full = f"{row.get(headers['first name']) or ''} {row.get(headers.get('last name', ''), '') or ''}".strip()
            data["name"] = full or None
        role = (data.pop("role", None) or "recruiter").lower().replace(" ", "_")
        try:
            body = ContactIn(**{k: v for k, v in data.items() if v is not None}, source="csv",
                             role=role if role in ("recruiter", "hiring_manager", "referral", "alumni") else "other")
        except ValueError as exc:
            result["errors"].append(f"Row {i}: {str(exc).splitlines()[0][:120]}")
            continue
        _, created = await create_contact(db, user_id, body)
        result["created" if created else "duplicates"] += 1
    return result


def _company_from_domain(domain: str) -> str | None:
    if not domain or domain in GENERIC_DOMAINS:
        return None
    base = domain.split(".")
    core = base[-3] if len(base) >= 3 and base[-2] in ("co", "com") else base[-2] if len(base) >= 2 else base[0]
    return core.capitalize()


async def import_from_inbox(db: AsyncIOMotorDatabase, user_id: str) -> dict:
    """Create contacts from recruiters who emailed the user (already imported mail only)."""
    result = {"created": 0, "duplicates": 0, "skipped": 0}
    cats = ["Recruiter Outreach", "Recruiter Reply", "Interview Invitation", "Assessment"]  # portal mail is handled in email.service
    async for e in db[c.EMAILS].find({"user_id": user_id, "category": {"$in": cats}}):
        ex = e.get("extracted") or {}
        addr = ex.get("sender_email")
        if not addr or re.match(r"(no-?reply|notifications?|jobs|careers|mailer-daemon|postmaster)@", addr):
            result["skipped"] += 1
            continue
        company = None
        if e.get("application_id"):
            app = await db[c.APPLICATIONS].find_one({"_id": e["application_id"]}, {"company": 1})
            company = app and app.get("company")
        company = company or _company_from_domain(ex.get("sender_domain") or "")
        if not company:
            result["skipped"] += 1
            continue
        name = ex.get("sender_name") or addr.split("@")[0].replace(".", " ").title()
        _, created = await create_contact(db, user_id, ContactIn(name=name[:120], company=company, email=addr,
                                                                 source="gmail", role="recruiter"))
        result["created" if created else "duplicates"] += 1
    return result


EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
NON_PERSONAL = re.compile(r"^(no-?reply|donotreply|notifications?|privacy|support|help|info|legal|security|abuse)@", re.I)


async def import_from_jobs(db: AsyncIOMotorDatabase, user_id: str) -> dict:
    """Contacts that job postings publish for applicants (e.g. "send your CV to hr@acme.com")."""
    result = {"created": 0, "duplicates": 0}
    async for j in db[c.JOBS].find({"user_id": user_id, "description": {"$regex": "@"}}, {"company": 1, "description": 1}):
        for addr in dict.fromkeys(EMAIL_RE.findall(j.get("description") or "")):
            addr = addr.lower().rstrip(".")
            if NON_PERSONAL.match(addr) or addr.endswith((".png", ".jpg")):
                continue
            local = addr.split("@")[0]
            generic = bool(re.match(r"^(hr|careers?|jobs?|recruit(ing|ment)?|talent|hiring|resumes?|cv)(?![a-z])", local))
            name = f"{j['company']} {'Hiring team' if generic else local.replace('.', ' ').title()}"[:120]
            _, created = await create_contact(db, user_id, ContactIn(name=name, company=j["company"], email=addr,
                                                                     source="job", role="recruiter"))
            result["created" if created else "duplicates"] += 1
    return result


async def import_from_feed(db: AsyncIOMotorDatabase, user_id: str) -> dict:
    """HR emails published in postings in Jobs for you (public postings for the user's roles)."""
    result = {"created": 0, "duplicates": 0}
    doc = await db[c.JOB_FEED].find_one({"_id": user_id}, {"items.hr_emails": 1, "items.company": 1}) or {}
    for it in doc.get("items", []):
        for addr in it.get("hr_emails") or []:
            company = (it.get("company") or _company_from_domain(addr.split("@")[-1]) or "").strip()
            if not company:
                continue
            local = addr.split("@")[0]
            generic = bool(re.match(r"^(hr|careers?|jobs?|recruit(ing|ment)?|talent|hiring|resumes?|cv)(?![a-z])", local))
            name = f"{company} {'Hiring team' if generic else local.replace('.', ' ').title()}"[:120]
            _, created = await create_contact(db, user_id, ContactIn(name=name, company=company[:200], email=addr,
                                                                     source="job", role="recruiter"))
            result["created" if created else "duplicates"] += 1
    return result


async def sync_contacts(db: AsyncIOMotorDatabase, user_id: str) -> dict:
    inbox = await import_from_inbox(db, user_id)
    jobs = await import_from_jobs(db, user_id)
    feed = await import_from_feed(db, user_id)
    return {"created": inbox["created"] + jobs["created"] + feed["created"], "from_inbox": inbox["created"],
            "from_jobs": jobs["created"] + feed["created"],
            "duplicates": inbox["duplicates"] + jobs["duplicates"] + feed["duplicates"]}


# ------------------------------------------------------------------ drafts

def _first_name(name: str) -> str:
    if name.startswith("["):  # template placeholder, e.g. "[First name]"
        return name
    return name.split()[0] if name.strip() else "there"


def _matching_skills(profile: Profile, job: dict | None, limit: int = 4) -> list[str]:
    """Verified skills, those the job asks for first. Never a skill the profile lacks."""
    verified = list(profile.skills.all())
    if job:
        wanted = {normalize_key(s) for s in job.get("skills", [])}
        first = [s for s in verified if normalize_key(s) in wanted]
        verified = first + [s for s in verified if s not in first]
    seen, out = set(), []
    for s in verified:
        if normalize_key(s) not in seen:
            seen.add(normalize_key(s))
            out.append(s)
    return out[:limit]


def _intro(profile: Profile) -> str:
    p = profile.personal
    name = p.name or "a candidate"
    role = p.current_designation
    yrs = p.total_experience_years
    if role and yrs:
        return f"I'm {name}, a {role} with {yrs:g} years of experience"
    if role:
        return f"I'm {name}, a {role}"
    return f"I'm {name}"


def build_draft(kind: str, profile: Profile, contact: dict, job: dict | None, parent: dict | None,
                context: str | None) -> tuple[str, str]:
    name = profile.personal.name or ""
    hi = f"Hi {_first_name(contact['name'])},"
    skills = _matching_skills(profile, job)
    skill_line = f" My background covers {', '.join(skills)}." if skills else ""
    ctx = f"{context.strip().rstrip('.')}.\n\n" if context and context.strip() else ""
    role = job["title"] if job else None
    company = job["company"] if job else contact["company"]
    link = f" ({job['application_url']})" if job and job.get("application_url") else ""
    phone = f"\n{profile.personal.phone}" if profile.personal.phone else ""
    sign = f"\n\nThanks,\n{name}{phone}" if name else "\n\nThanks"

    if kind == "referral":
        subject = f"Referral request: {role} at {company}" if role else f"Referral request at {company}"
        target = f"the {role} role at {company}{link}" if role else f"open roles at {company}"
        body = (f"{hi}\n\n{ctx}{_intro(profile)}. I came across {target} and it lines up with my experience."
                f"{skill_line}\n\nWould you be open to referring me, or pointing me to the right person? "
                f"I'm happy to share my resume and anything else that helps.{sign}")
    elif kind == "cold":
        subject = f"{role} at {company}" if role else f"Opportunities at {company}"
        target = f"the {role} role{link}" if role else "relevant openings on your team"
        body = (f"{hi}\n\n{ctx}{_intro(profile)}. I'm interested in {target} at {company}.{skill_line}\n\n"
                f"If there's a fit, I'd love to share my resume and have a quick chat.{sign}")
    elif kind == "hiring_manager":
        subject = f"{role} · {name}" if role and name else (f"{role} at {company}" if role else f"Your team at {company}")
        target = f"the {role} opening{link}" if role else "your team"
        body = (f"{hi}\n\n{ctx}{_intro(profile)}. I'm reaching out directly because {target} at {company} matches "
                f"the work I do.{skill_line}\n\nWould you be open to a 15-minute call, or could you point me to the "
                f"right recruiter? I've applied through the careers page as well.{sign}")
    elif kind == "employee_intro":
        subject = f"Quick question about working at {company}"
        body = (f"{hi}\n\n{ctx}{_intro(profile)}. I'm exploring roles at {company}"
                f"{f' such as {role}' if role else ''} and would really value your perspective on the team and culture."
                f"\n\nWould you have 15 minutes for a quick chat sometime this week or next? Happy to work around "
                f"your schedule.{sign}")
    elif kind == "linkedin_note":
        # LinkedIn connection notes are limited to 300 characters.
        subject = "LinkedIn connection note"
        about = f" for the {role} role" if role else ""
        first_skill = f" with {skills[0]}" if skills else ""
        designation = profile.personal.current_designation
        intro = f"I'm {name}, a {designation}" if designation and name else (f"I'm {name}" if name else "I")
        body = (f"Hi {_first_name(contact['name'])}, {intro}{first_skill}. I'm interested in {company}{about} "
                f"and would love to connect.")[:300]
    elif kind == "followup":
        when = as_utc(parent["sent_at"]).strftime("%d %b") if parent and parent.get("sent_at") else "earlier"
        about = f" about {parent['subject']}" if parent else ""
        subject = f"Re: {parent['subject']}" if parent else f"Following up · {company}"
        body = (f"{hi}\n\nJust following up on my note from {when}{about}. I'm still very interested and "
                f"happy to share anything that helps.{sign}")
    else:  # thank_you
        subject = f"Thank you · {company}"
        body = (f"{hi}\n\n{ctx}Thank you for your time. I appreciated learning more about {company}"
                f"{f' and the {role} role' if role else ''}, and I'm keen to stay in touch.{sign}")
    return subject[:200], body[:5000]


def templates(profile: Profile) -> list[dict]:
    """Every template rendered with the user's verified profile and placeholder contact details."""
    sample = {"name": "[First name]", "company": "[Company]"}
    job = {"title": "[Role]", "company": "[Company]", "skills": [], "application_url": None}
    parent = {"subject": "[your earlier subject]", "sent_at": None}
    out = []
    for kind, name, audience, when in TEMPLATE_INFO:
        subject, body = build_draft(kind, profile, sample, job if kind != "employee_intro" else None,
                                    parent if kind == "followup" else None, None)
        out.append({"kind": kind, "name": name, "audience": audience, "description": when, "subject": subject,
                    "body": body, "channel": "linkedin" if kind == "linkedin_note" else "email"})
    for kind, name, audience, when in WHATSAPP_INFO:
        text = whatsapp_text(kind, profile, sample, "[Role]", "[Company]")
        out.append({"kind": kind, "name": name, "audience": audience, "description": when, "subject": "",
                    "body": text, "channel": "whatsapp", "wa_link": f"https://wa.me/?text={quote(text)}"})
    for kind, name, audience, when in WHATSAPP_INFO[:3]:  # SMS: the same short messages, sent from your phone
        text = whatsapp_text(kind, profile, sample, "[Role]", "[Company]")
        out.append({"kind": kind.replace("wa_", "sms_"), "name": name.replace("WhatsApp", "SMS"), "audience": audience,
                    "description": when, "subject": "", "body": text, "channel": "sms", "sms_link": f"sms:?body={quote(text)}"})
    return out


WHATSAPP_INFO = [
    ("wa_hr", "WhatsApp to HR / recruiter", "HR · recruiter", "When a recruiter shares a WhatsApp number or a posting lists one."),
    ("wa_referral", "WhatsApp referral ask", "Friend · ex-colleague", "For someone you already know at the company."),
    ("wa_followup", "WhatsApp follow-up", "Recruiter you've spoken to", "A short nudge 3–5 days after applying or talking."),
    ("wa_thanks", "WhatsApp thank-you", "Interviewer · recruiter", "Same day, after a call or interview."),
]


def whatsapp_text(kind: str, profile: Profile, contact: dict, role: str | None, company: str) -> str:
    """Short WhatsApp messages from verified facts only (no claims beyond the profile)."""
    first = _first_name(contact["name"])
    skills = _matching_skills(profile, None, 3)
    about = f" ({', '.join(skills)})" if skills else ""
    role_txt = f"the {role} role" if role else "open roles"
    if kind == "wa_hr":
        return (f"Hi {first}, {_intro(profile)}{about}. I saw {role_txt} at {company} and would love to be considered. "
                f"May I share my resume here? Thank you!")
    if kind == "wa_referral":
        return (f"Hi {first}! Hope you're doing well. {company} has {role_txt} that fits my experience{about}. "
                f"Would you be comfortable referring me? I can send my resume and the job link.")
    if kind == "wa_followup":
        return (f"Hi {first}, following up on {role_txt} at {company}. I'm still very interested, "
                f"happy to share anything else you need. Thanks!")
    return (f"Hi {first}, thank you for your time today. I enjoyed learning more about {company}"
            f"{f' and the {role} role' if role else ''}. Looking forward to the next steps!")


def _profile_values(profile: Profile) -> list[str]:
    """Exact renderings of verified profile numbers (CTC, notice, experience) that replies may quote."""
    from app.email.auto_reply import _money

    p = profile.personal
    vals = [_money(p.current_ctc, p.ctc_currency), _money(p.expected_ctc, p.ctc_currency),
            f"{p.notice_period_days} days" if p.notice_period_days is not None else None,
            f"{p.total_experience_years:g} years" if p.total_experience_years else None, p.phone]
    return [v for v in vals if v]


TEMPLATE_VARS = ("firstName", "fullName", "companyName", "jobTitle", "jobLink", "myName", "myRole", "myPhone")


def fill_template(tpl: str, profile: Profile, contact: dict, job: dict | None) -> str:
    """Replace {{variables}} in a user-written template. Unknown variables are left visible so they get noticed."""
    values = {"firstName": _first_name(contact.get("name") or ""), "fullName": contact.get("name") or "",
              "companyName": (job or {}).get("company") or contact.get("company") or "",
              "jobTitle": (job or {}).get("title") or "the role", "jobLink": (job or {}).get("application_url") or "",
              "myName": profile.personal.name or "", "myRole": profile.personal.current_designation or "",
              "myPhone": profile.personal.phone or ""}
    return re.sub(r"\{\{\s*(\w+)\s*\}\}", lambda m: values.get(m.group(1), m.group(0)), tpl)[:5000]


def check_truth(profile: Profile, body: str) -> dict:
    titles = [profile.personal.current_designation] if profile.personal.current_designation else []
    for v in _profile_values(profile):  # the user's own verified numbers are not invented metrics
        body = body.replace(v, "")
    result = validate_claims(GeneratedClaims(text=body, titles=titles), profile)
    return {"status": result.status, "violations": [v.model_dump() for v in result.violations]}


def outreach_out(d: dict, contact: dict | None = None) -> dict:
    to = (contact or {}).get("email")
    subject, body = d["subject"], d["body"]
    return {
        "id": d["_id"], "contact_id": d["contact_id"], "job_id": d.get("job_id"), "parent_id": d.get("parent_id"),
        "kind": d["kind"], "status": d["status"], "subject": subject, "body": body,
        "company": d.get("company"), "contact_name": (contact or {}).get("name") or d.get("contact_name"),
        "channel_hint": "email" if to else "linkedin",
        "validation": d.get("validation"), "attach_resume": bool(d.get("attach_resume")), "asks": d.get("asks", []),
        "mailto": f"mailto:{to}?subject={quote(subject)}&body={quote(body)}" if to else None,
        "gmail_compose": (f"https://mail.google.com/mail/?view=cm&fs=1&to={quote(to)}&su={quote(subject)}"
                          f"&body={quote(body)}") if to else None,
        "linkedin_url": (contact or {}).get("linkedin_url"),
        "approved_at": d["approved_at"].isoformat() if d.get("approved_at") else None,
        "sent_at": d["sent_at"].isoformat() if d.get("sent_at") else None,
        "sent_via": d.get("sent_via"),
        "replied_at": d["replied_at"].isoformat() if d.get("replied_at") else None,
        "created_at": d["created_at"].isoformat(), "updated_at": d["updated_at"].isoformat(),
    }


async def create_draft(db: AsyncIOMotorDatabase, user_id: str, body: DraftIn) -> dict:
    if body.kind == "reply":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Replies are drafted automatically from the recruiter's email.")
    contact = await get_contact(db, user_id, body.contact_id)
    if contact.get("unsubscribed"):
        raise HTTPException(status.HTTP_409_CONFLICT, "This contact asked not to be contacted")
    job = await db[c.JOBS].find_one({"_id": body.job_id, "user_id": user_id}) if body.job_id else None
    if body.job_id and not job:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    parent = await get_outreach(db, user_id, body.parent_id) if body.parent_id else None
    profile = await get_profile(db, user_id)
    subject, text = build_draft(body.kind, profile, contact, job, parent, body.context)
    custom = (await get_settings_doc(db, user_id)).outreach.templates.get(body.kind)
    if custom and custom.strip():  # the user's own template, with variables filled in
        text = fill_template(custom, profile, contact, job)
    validation = check_truth(profile, text)
    now = utcnow()
    doc = {"_id": new_id(), "user_id": user_id, "contact_id": contact["_id"], "contact_name": contact["name"],
           "company": contact["company"], "company_key": contact.get("company_key"), "job_id": body.job_id,
           "parent_id": body.parent_id, "kind": body.kind, "status": "draft", "subject": subject, "body": text,
           "validation": validation, "approved_at": None, "sent_at": None, "replied_at": None,
           "created_at": now, "updated_at": now}
    await db[c.OUTREACH].insert_one(doc)
    await log_action(db, user_id=user_id, action="outreach.drafted", entity="outreach", entity_id=doc["_id"],
                     details={"kind": body.kind, "company": contact["company"]})
    return outreach_out(doc, contact)


async def get_outreach(db: AsyncIOMotorDatabase, user_id: str, outreach_id: str) -> dict:
    doc = await db[c.OUTREACH].find_one({"_id": outreach_id, "user_id": user_id})
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Message not found")
    return doc


async def edit_draft(db: AsyncIOMotorDatabase, user_id: str, outreach_id: str, subject: str, text: str) -> dict:
    doc = await get_outreach(db, user_id, outreach_id)
    if doc["status"] not in OPEN:
        raise HTTPException(status.HTTP_409_CONFLICT, "Only drafts can be edited")
    validation = check_truth(await get_profile(db, user_id), text)
    if validation["status"] != "PASSED":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, {"status": "VALIDATION FAILED", **validation})
    # Any edit sends the message back to draft so it is approved again as written.
    await db[c.OUTREACH].update_one({"_id": outreach_id}, {"$set": {
        "subject": subject, "body": text, "validation": validation, "status": "draft", "approved_at": None,
        "edited_by_user": True, "updated_at": utcnow()}})
    return await out_with_contact(db, user_id, outreach_id)


async def out_with_contact(db: AsyncIOMotorDatabase, user_id: str, outreach_id: str) -> dict:
    doc = await get_outreach(db, user_id, outreach_id)
    contact = await db[c.RECRUITER_CONTACTS].find_one({"_id": doc["contact_id"], "user_id": user_id})
    return outreach_out(doc, contact)


# ------------------------------------------------------------------ approval, caps, sending

async def approve(db: AsyncIOMotorDatabase, user_id: str, outreach_id: str) -> dict:
    doc = await get_outreach(db, user_id, outreach_id)
    if doc["status"] != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, f"Cannot approve a message that is {doc['status']}")
    if (doc.get("validation") or {}).get("status") != "PASSED":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            "This draft contains claims not in your verified profile. Edit it first.")
    await db[c.OUTREACH].update_one({"_id": outreach_id}, {"$set": {
        "status": "approved", "approved_at": utcnow(), "updated_at": utcnow()}})
    await log_action(db, user_id=user_id, action="outreach.approved", entity="outreach", entity_id=outreach_id)
    return await out_with_contact(db, user_id, outreach_id)


async def local_day_start(db: AsyncIOMotorDatabase, user_id: str, now: datetime) -> datetime:
    from app.scheduler.service import user_tz

    tz = user_tz(await get_settings_doc(db, user_id))
    local = now.astimezone(tz)
    return local.replace(hour=0, minute=0, second=0, microsecond=0)


async def daily_limit(db: AsyncIOMotorDatabase, user_id: str) -> int:
    s = await get_settings_doc(db, user_id)
    return max(0, min(HARD_DAILY_CAP, s.limits.daily_recruiter_contact_limit))


async def sent_today(db: AsyncIOMotorDatabase, user_id: str, now: datetime | None = None) -> int:
    now = now or utcnow()
    start = await local_day_start(db, user_id, now)
    return await db[c.OUTREACH].count_documents({"user_id": user_id, "sent_at": {"$gte": start}})


async def _preflight(db: AsyncIOMotorDatabase, user_id: str, doc: dict, now) -> dict:
    """Every rule a message must pass before it is sent (by Saige or by the user). Returns the contact."""
    if doc["status"] != "approved":
        raise HTTPException(status.HTTP_409_CONFLICT, "Approve the message before sending it")
    if not await is_allowed(db, user_id, "recruiter_outreach"):
        raise HTTPException(status.HTTP_423_LOCKED, "Recruiter outreach is paused. Resume it in Automation settings.")
    contact = await get_contact(db, user_id, doc["contact_id"])
    if contact.get("unsubscribed"):
        raise HTTPException(status.HTTP_409_CONFLICT, "This contact asked not to be contacted")
    if doc["kind"] == "reply":  # answering someone who wrote to you first: no cold-outreach caps
        return contact
    from app.automation.service import is_blocked

    if is_blocked(await get_settings_doc(db, user_id), doc.get("company")):
        raise HTTPException(status.HTTP_409_CONFLICT, f"{doc.get('company')} is in your blocked companies (Settings → Agent).")
    limit = await daily_limit(db, user_id)
    if await sent_today(db, user_id, now) >= limit:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            f"Daily outreach limit reached ({limit}). Quality beats volume: try again tomorrow.")
    if doc.get("company_key") and await db[c.OUTREACH].count_documents({
            "user_id": user_id, "company_key": doc["company_key"], "sent_at": {"$gte": now - timedelta(days=7)}}
    ) >= PER_COMPANY_WEEKLY_CAP:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            f"You've already contacted {PER_COMPANY_WEEKLY_CAP} people at {doc['company']} this week.")
    return contact


async def _record_sent(db: AsyncIOMotorDatabase, user_id: str, doc: dict, contact: dict, now, *,
                       via: str, message_id: str | None = None) -> None:
    outreach_id = doc["_id"]
    await db[c.OUTREACH].update_one({"_id": outreach_id}, {"$set": {
        "status": "sent", "sent_at": now, "sent_via": via, "message_id": message_id, "updated_at": now}})
    await db[c.RECRUITER_CONTACTS].update_one({"_id": contact["_id"]}, {"$set": {"last_contacted_at": now}})
    fu = (await get_settings_doc(db, user_id)).followups
    if doc["kind"] in FOLLOWUP_KINDS and fu.enabled:
        for i, days in enumerate(fu.days or FOLLOWUP_DAYS, start=1):
            await db[c.FOLLOWUPS].insert_one({
                "_id": new_id(), "user_id": user_id, "outreach_id": outreach_id, "contact_id": contact["_id"],
                "kind": "outreach_followup", "sequence": i, "due_at": now + timedelta(days=days),
                "status": "scheduled", "created_at": now})
    if doc.get("job_id"):
        await db[c.APPLICATIONS].update_many(
            {"user_id": user_id, "job_id": doc["job_id"], "status": {"$in": ["APPLIED", "SHORTLISTED", "READY_TO_APPLY"]}},
            {"$set": {"recruiter_id": contact["_id"], "last_contact_at": now}})
    await log_action(db, user_id=user_id, action="outreach.sent", entity="outreach", entity_id=outreach_id,
                     details={"company": doc["company"], "kind": doc["kind"], "via": via})


async def mark_sent(db: AsyncIOMotorDatabase, user_id: str, outreach_id: str) -> dict:
    """The user sent the message themselves (Gmail, mail app or LinkedIn)."""
    doc = await get_outreach(db, user_id, outreach_id)
    now = utcnow()
    contact = await _preflight(db, user_id, doc, now)
    await _record_sent(db, user_id, doc, contact, now, via="manual")
    return await out_with_contact(db, user_id, outreach_id)


async def resume_attachment(db: AsyncIOMotorDatabase, user_id: str) -> list[tuple[str, bytes, str]]:
    """The master resume as a DOCX attachment (empty when there is no resume)."""
    from app.profiles.sync_service import master_resume
    from app.resumes.docx_export import resume_docx
    from app.schemas.resume import ParsedResume

    r = await master_resume(db, user_id)
    v = r and await db[c.RESUME_VERSIONS].find_one({"_id": r.get("current_version_id")})
    if not v:
        return []
    parsed = ParsedResume.model_validate(v["parsed"])
    name = re.sub(r"[^A-Za-z0-9 _-]", "", parsed.name or "Resume").strip() or "Resume"
    return [(f"{name} - Resume.docx", resume_docx(parsed),
             "application/vnd.openxmlformats-officedocument.wordprocessingml.document")]


async def send_now(db: AsyncIOMotorDatabase, user_id: str, outreach_id: str, *, approve_first: bool = False) -> dict:
    """Send an approved message from the user's Gmail (App Password connection) and record it."""
    from app.email import smtp
    from app.email.gmail import GmailError
    from app.services import crypto

    doc = await get_outreach(db, user_id, outreach_id)
    if approve_first and doc["status"] == "draft":
        await approve(db, user_id, outreach_id)
        doc = await get_outreach(db, user_id, outreach_id)
    if doc["kind"] == "linkedin_note":
        raise HTTPException(status.HTTP_409_CONFLICT, "LinkedIn notes can't be emailed. Copy it into LinkedIn, then mark it sent.")
    now = utcnow()
    contact = await _preflight(db, user_id, doc, now)
    if not contact.get("email"):
        raise HTTPException(status.HTTP_409_CONFLICT, "This contact has no email address. Add one, or send on LinkedIn.")
    integ = await db[c.INTEGRATIONS].find_one({"user_id": user_id, "provider": "gmail", "method": "app_password"})
    if not integ:
        raise HTTPException(status.HTTP_409_CONFLICT, "Connect Gmail with an App Password (Integrations) so Saige can "
                                                      "send for you, or open it in Gmail and send it yourself.")
    user = await db[c.USERS].find_one({"_id": user_id}, {"name": 1})
    attachments = await resume_attachment(db, user_id) if doc.get("attach_resume") else []
    try:
        message_id = await smtp.send(integ["email"], crypto.decrypt(integ["app_password_enc"]), (user or {}).get("name") or "",
                                     contact["email"], doc["subject"], doc["body"], attachments)
    except GmailError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    await _record_sent(db, user_id, doc, contact, now, via="gmail", message_id=message_id)
    await notify(db, user_id=user_id, kind="outreach_sent", title=f"Email sent to {contact['name']}",
                 body=f"{doc['subject']} · {contact['company']}. Follow-ups are scheduled and stop if they reply.",
                 link="/recruiters")
    return await out_with_contact(db, user_id, outreach_id)


async def _stop_followups(db: AsyncIOMotorDatabase, user_id: str, outreach_ids: list[str]) -> None:
    await db[c.FOLLOWUPS].update_many(
        {"user_id": user_id, "outreach_id": {"$in": outreach_ids}, "status": {"$in": ["scheduled", "due"]}},
        {"$set": {"status": "cancelled"}})


async def set_outcome(db: AsyncIOMotorDatabase, user_id: str, outreach_id: str, outcome: str) -> dict:
    """replied / bounced / no_response / unsubscribed / cancelled."""
    doc = await get_outreach(db, user_id, outreach_id)
    if outcome == "cancelled" and doc["status"] not in OPEN:
        raise HTTPException(status.HTTP_409_CONFLICT, "Only unsent messages can be cancelled")
    if outcome != "cancelled" and doc["status"] != "sent" and not (outcome == "unsubscribed" and doc["status"] in FINAL):
        raise HTTPException(status.HTTP_409_CONFLICT, "Mark the message as sent first")
    now = utcnow()
    patch = {"status": outcome, "updated_at": now}
    if outcome == "replied":
        patch["replied_at"] = now
    await db[c.OUTREACH].update_one({"_id": outreach_id}, {"$set": patch})
    # A reply, bounce or unsubscribe ends every follow-up to this contact, not just this thread.
    ids = [d["_id"] async for d in db[c.OUTREACH].find({"user_id": user_id, "contact_id": doc["contact_id"]}, {"_id": 1})]
    await _stop_followups(db, user_id, ids if outcome != "no_response" else [outreach_id])
    if outcome == "unsubscribed":
        await db[c.RECRUITER_CONTACTS].update_one({"_id": doc["contact_id"]}, {"$set": {"unsubscribed": True}})
        await db[c.OUTREACH].update_many({"user_id": user_id, "contact_id": doc["contact_id"], "status": {"$in": list(OPEN)}},
                                         {"$set": {"status": "cancelled", "updated_at": now}})
    await log_action(db, user_id=user_id, action=f"outreach.{outcome}", entity="outreach", entity_id=outreach_id)
    return await out_with_contact(db, user_id, outreach_id)


async def on_inbound_email(db: AsyncIOMotorDatabase, user_id: str, sender_email: str | None, body: str) -> str | None:
    """Called for every ingested email: detect replies from contacts and bounces of sent messages."""
    if not sender_email:
        return None
    sender = sender_email.lower()
    if re.match(r"(mailer-daemon|postmaster)@", sender):
        async for o in db[c.OUTREACH].find({"user_id": user_id, "status": "sent"}):
            contact = await db[c.RECRUITER_CONTACTS].find_one({"_id": o["contact_id"]})
            if contact and contact.get("email_key") and contact["email_key"] in body.lower():
                await set_outcome(db, user_id, o["_id"], "bounced")
                return "bounced"
        return None
    contact = await db[c.RECRUITER_CONTACTS].find_one({"user_id": user_id, "email_key": sender})
    if not contact:
        return None
    last = await db[c.OUTREACH].find_one({"user_id": user_id, "contact_id": contact["_id"], "status": "sent"},
                                        sort=[("sent_at", DESCENDING)])
    if not last:
        return None
    await set_outcome(db, user_id, last["_id"], "replied")
    await notify(db, user_id=user_id, kind="outreach_reply", title=f"{contact['name']} replied",
                 body=f"{contact['company']} · follow-ups stopped automatically.", link="/recruiters")
    return "replied"


# ------------------------------------------------------------------ overview

async def stats(db: AsyncIOMotorDatabase, user_id: str) -> dict:
    by_status: dict[str, int] = {}
    async for row in db[c.OUTREACH].aggregate([{"$match": {"user_id": user_id}},
                                               {"$group": {"_id": "$status", "n": {"$sum": 1}}}]):
        by_status[row["_id"]] = row["n"]
    delivered = sum(by_status.get(k, 0) for k in ("sent", "replied", "no_response", "unsubscribed"))
    limit = await daily_limit(db, user_id)
    today = await sent_today(db, user_id)
    due = []
    async for f in db[c.FOLLOWUPS].find({"user_id": user_id, "kind": "outreach_followup",
                                         "status": {"$in": ["scheduled", "due"]}, "due_at": {"$lte": utcnow()}}
                                        ).sort("due_at", 1).limit(20):
        o = await db[c.OUTREACH].find_one({"_id": f["outreach_id"]})
        if o:
            due.append({"followup_id": f["_id"], "outreach_id": o["_id"], "contact_id": o["contact_id"],
                        "contact_name": o.get("contact_name"), "company": o.get("company"), "subject": o["subject"],
                        "sequence": f["sequence"], "due_at": as_utc(f["due_at"]).isoformat()})
    can_send = bool(await db[c.INTEGRATIONS].find_one({"user_id": user_id, "provider": "gmail", "method": "app_password"}))
    by_source: dict[str, int] = {}
    async for row in db[c.RECRUITER_CONTACTS].aggregate([{"$match": {"user_id": user_id}},
                                                         {"$group": {"_id": "$source", "n": {"$sum": 1}}}]):
        by_source[row["_id"] or "manual"] = row["n"]
    return {
        "can_send_from_saige": can_send, "contacts_by_source": by_source,
        "sent_today": today, "daily_limit": limit, "remaining_today": max(0, limit - today),
        "by_status": by_status, "contacts": await db[c.RECRUITER_CONTACTS].count_documents({"user_id": user_id}),
        "reply_rate": round(100 * by_status.get("replied", 0) / delivered) if delivered else None,
        "followups_due": due,
    }


async def complete_followup(db: AsyncIOMotorDatabase, user_id: str, followup_id: str) -> None:
    await db[c.FOLLOWUPS].update_one({"_id": followup_id, "user_id": user_id}, {"$set": {"status": "done"}})

