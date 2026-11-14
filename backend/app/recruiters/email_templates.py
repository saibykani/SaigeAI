"""Recruiter email templates and their rendering.

Placeholders are filled ONLY from the verified profile and the contact record. A placeholder with no verified value is
removed (its whole line is dropped), never invented. {{hr_name}} falls back to "Hiring Team".
"""

import re

from app.schemas.profile import Profile

PLACEHOLDERS = ("hr_name", "company", "my_name", "my_role", "years", "top_skills", "phone", "linkedin", "portfolio")

BUILTIN: list[dict] = [
    {"id": "builtin:application", "name": "Job application (with resume)", "kind": "cold", "attach_resume": True,
     "subject": "Application for opportunities at {{company}} - {{my_name}}",
     "body": ("Dear {{hr_name}},\n\nI am writing to express my interest in opportunities at {{company}}. "
              "I work as {{my_role}}.\n\nExperience: {{years}} years\nKey skills: {{top_skills}}\n\n"
              "My resume is attached for your review. I would be glad to discuss how I can contribute to your team.\n\n"
              "Phone: {{phone}}\nLinkedIn: {{linkedin}}\nPortfolio: {{portfolio}}\n\nThank you for your time.\n\nBest regards,\n{{my_name}}")},
    {"id": "builtin:referral", "name": "Referral request", "kind": "referral", "attach_resume": False,
     "subject": "Referral request at {{company}}",
     "body": ("Hi {{hr_name}},\n\nI hope you are doing well. I am {{my_name}}, {{my_role}}, and I am interested in roles at {{company}}.\n\n"
              "Key skills: {{top_skills}}\n\nIf there is an opening that fits my background, would you be open to referring me "
              "or pointing me to the right person? I can share my resume and any details you need.\n\n"
              "LinkedIn: {{linkedin}}\n\nThank you for considering this.\n\nBest regards,\n{{my_name}}")},
    {"id": "builtin:cold_intro", "name": "Open to opportunities / cold intro", "kind": "cold", "attach_resume": False,
     "subject": "{{my_role}} open to opportunities at {{company}}",
     "body": ("Hello {{hr_name}},\n\nI am {{my_name}}, {{my_role}}. I am exploring new opportunities and {{company}} is high on my list.\n\n"
              "Experience: {{years}} years\nKey skills: {{top_skills}}\n\nIf you have a suitable opening now or in the near future, "
              "I would appreciate hearing from you. Happy to share my resume.\n\nPhone: {{phone}}\nLinkedIn: {{linkedin}}\n\n"
              "Warm regards,\n{{my_name}}")},
    {"id": "builtin:followup", "name": "Follow-up", "kind": "followup", "attach_resume": False,
     "subject": "Following up - {{my_name}}",
     "body": ("Hi {{hr_name}},\n\nI wanted to follow up on my earlier note about opportunities at {{company}}. "
              "I remain very interested and would be glad to share anything that helps.\n\nThank you for your time.\n\n"
              "Best regards,\n{{my_name}}\n{{phone}}")},
    {"id": "builtin:thank_you", "name": "Thank you", "kind": "thank_you", "attach_resume": False,
     "subject": "Thank you - {{my_name}}",
     "body": ("Hi {{hr_name}},\n\nThank you for your time and for the opportunity to connect about {{company}}. "
              "I appreciate it and look forward to staying in touch.\n\nBest regards,\n{{my_name}}")},
]

_PH = re.compile(r"\{\{\s*(\w+)\s*\}\}")
_HR_GENERIC = re.compile(r"^\s*(hr|human resources|talent acquisition|recruitment|recruiting|careers|hiring)\b.*(team|desk|dept|department)?", re.I)


def hr_name(contact: dict) -> str:
    """The contact's first name, or "Hiring Team" for generic names such as "HR Team (Acme)"."""
    name = (contact.get("name") or "").strip()
    if not name or name.startswith("[") or _HR_GENERIC.match(name) or re.search(r"\b(team|desk|department)\b", name, re.I):
        return "Hiring Team"
    return name.split()[0]


def values(profile: Profile, contact: dict) -> dict[str, str]:
    p = profile.personal
    skills = profile.skills.primary or profile.skills.all()
    years = f"{p.total_experience_years:g}" if p.total_experience_years else ""
    return {"hr_name": hr_name(contact), "company": (contact.get("company") or "").strip(), "my_name": p.name or "",
            "my_role": p.current_designation or "", "years": years, "top_skills": ", ".join(skills[:5]), "phone": p.phone or "",
            "linkedin": str(p.linkedin_url or ""), "portfolio": str(p.portfolio_url or "")}


def _tidy(text: str) -> str:
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\s+([,.;:])", r"\1", text)
    return text.strip(" -|,;:")


def render(tpl: str, vals: dict[str, str], *, subject: bool = False) -> str:
    """Fill placeholders. Unknown placeholders and ones without a verified value are removed; a body line that
    loses a value is dropped entirely (a subject just loses the fragment)."""
    if subject:
        return _tidy(_PH.sub(lambda m: vals.get(m.group(1), ""), tpl))
    out: list[str] = []
    for line in tpl.splitlines():
        missing = any(not vals.get(m.group(1)) for m in _PH.finditer(line))
        if missing:
            continue
        out.append(_PH.sub(lambda m: vals[m.group(1)], line))
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


def render_for(tpl: dict, profile: Profile, contact: dict) -> tuple[str, str]:
    vals = values(profile, contact)
    return render(tpl["subject"], vals, subject=True), render(tpl["body"], vals)


def template_out(d: dict, builtin: bool = False) -> dict:
    return {"id": d["id"] if builtin else d["_id"], "name": d["name"], "subject": d["subject"], "body": d["body"], "kind": d["kind"],
            "attach_resume": bool(d.get("attach_resume")), "builtin": builtin}
