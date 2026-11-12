"""Portfolio content, taken ONLY from the verified master profile (no invented claims)."""

import calendar
import re

from app.profiles.experience import parse_month
from app.resumes.tailor import experience_phrase
from app.schemas.profile import Profile
from app.studio.polish import group_skills


def _month(v: str | None) -> str:
    ym = parse_month(v) if v else None
    return f"{calendar.month_abbr[ym[1]]} {ym[0]}" if ym else (v or "")


def build(profile: Profile, settings: dict) -> dict:
    p, k = profile.personal, profile.knowledge
    skills = list(dict.fromkeys([*profile.skills.primary, *profile.skills.all()]))[:40]
    role = (p.current_designation or (profile.preferences.target_roles or [""])[0] or "").strip()
    exp = [{"title": e.title, "company": e.company, "location": e.location or "",
            "dates": f"{_month(e.start_date)} – {'Present' if e.is_current else _month(e.end_date)}".strip(" –"),
            "bullets": [b for b in (e.achievements or []) + (e.responsibilities or []) if b][:5], "tech": e.technologies[:8]}
           for e in k.experience]
    projects = [{"name": pr.name, "description": pr.description or "", "highlights": pr.highlights[:3], "tech": pr.technologies[:8],
                 "url": str(pr.url) if pr.url else ""} for pr in k.projects][:8]
    edu = [{"degree": " in ".join(x for x in (ed.degree, ed.field) if x), "school": ed.institution or "",
            "years": "–".join(str(y) for y in (ed.start_year, ed.end_year) if y)} for ed in k.education]
    certs = [{"name": c.name, "issuer": c.issuer or "", "url": str(c.credential_url) if c.credential_url else ""} for c in k.certifications]
    links = [(lbl, str(u)) for lbl, u in (("LinkedIn", p.linkedin_url), ("GitHub", p.github_url), ("Portfolio", p.portfolio_url)) if u]
    name = (p.name or "").strip() or "Your Name"
    return {
        "name": name, "first": name.split()[0], "initials": "".join(w[0] for w in name.split()[:2]).upper(),
        "role": role or "Professional", "tagline": (settings.get("tagline") or "").strip(),
        "summary": k.professional_summary or "", "location": p.current_location or "",
        "experience_text": experience_phrase(profile) or "",
        "email": p.email if settings.get("show_email", True) and p.email else "",
        "phone": p.phone if settings.get("show_phone") and p.phone else "",
        "links": links, "skills": skills, "skill_groups": group_skills(skills), "experience": exp, "projects": projects,
        "education": edu, "certifications": certs, "domains": k.domains[:6],
        "open_to_work": bool(settings.get("open_to_work", True)),
        "years": (m.group(0) if (m := re.match(r"[\d.]+", experience_phrase(profile) or "")) else ""),
    }
