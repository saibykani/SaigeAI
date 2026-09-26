"""Application-question answering from the verified knowledge base (spec section 20).

Every answer carries its source and a confidence. Anything the knowledge base cannot support is
REVIEW_REQUIRED with no answer - the system never guesses "Yes" or invents a number. Salary and
similar fields are marked sensitive so they always need the user's approval (spec section 44).
"""

import re
from datetime import date

from app.jobs.matching import candidate_skills
from app.schemas.profile import Profile
from app.services.skills_vocab import canonical, find_skills, normalize_key

_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}


def _parse_date(value: str | None, *, today: date) -> date | None:
    if not value:
        return None
    v = value.strip().lower()
    if v in {"present", "current", "now", "till date"}:
        return today
    m = re.match(r"([a-z]{3})[a-z]*\.?\s*[,'’]?\s*(\d{2,4})", v)
    if m and m.group(1) in _MONTHS:
        year = int(m.group(2))
        year += 2000 if year < 100 else 0
        return date(year, _MONTHS[m.group(1)], 1)
    m = re.match(r"(\d{1,2})[/-](\d{2,4})", v)
    if m:
        year = int(m.group(2))
        year += 2000 if year < 100 else 0
        return date(year, max(1, min(12, int(m.group(1)))), 1)
    m = re.match(r"((?:19|20)\d{2})", v)
    return date(int(m.group(1)), 1, 1) if m else None


def years_with_skill(profile: Profile, skill: str, today: date | None = None) -> float | None:
    """Sum of dated roles whose verified technologies/bullets mention the skill."""
    today = today or date.today()
    key = normalize_key(canonical(skill))
    months = 0
    for e in profile.knowledge.experience:
        mentioned = {normalize_key(canonical(t)) for t in e.technologies}
        mentioned |= {normalize_key(s) for s in find_skills(" ".join(e.responsibilities + e.achievements))}
        if key not in mentioned:
            continue
        start = _parse_date(e.start_date, today=today)
        end = today if e.is_current else _parse_date(e.end_date, today=today)
        if not start or not end or end < start:
            continue  # undated role: its duration can't be counted
        months += (end.year - start.year) * 12 + end.month - start.month
    if months:
        return round(months / 12 * 2) / 2  # nearest half year
    return None


def _ans(question: str, answer: str | None, source: str, confidence: str, *, sensitive: bool = False,
         note: str | None = None) -> dict:
    status = "ANSWERED" if answer is not None and confidence != "LOW" and not sensitive else "REVIEW_REQUIRED"
    return {"question": question, "answer": answer, "source": source, "confidence": confidence,
            "status": status, "sensitive": sensitive, "note": note}


def answer_question(question: str, profile: Profile, today: date | None = None) -> dict:
    q = question.strip()
    ql = q.lower()
    p, kb, prefs = profile.personal, profile.knowledge, profile.preferences
    kb_src = "Candidate Knowledge Base"
    unknown = _ans(q, None, "Not in knowledge base", "LOW",
                   note="Saige won't guess. Answer this yourself or add the fact to your master profile.")

    # --- experience with a specific skill
    skills = find_skills(q)
    if re.search(r"\byears?\b|\bhow long\b", ql) and skills:
        skill = skills[0]
        if normalize_key(canonical(skill)) not in candidate_skills(profile):
            return _ans(q, None, kb_src, "LOW", note=f"{skill} is not in your verified skills.")
        yrs = years_with_skill(profile, skill, today)
        if yrs is None:
            return _ans(q, None, kb_src, "LOW",
                        note=f"You list {skill}, but no dated role mentions it - enter the years yourself.")
        return _ans(q, f"{yrs:g}", f"{kb_src} (dated roles mentioning {skill})", "HIGH")
    if re.search(r"\b(total|overall)?\s*(years?|yrs)\b.*\bexperience\b|\bexperience\b.*\byears?\b", ql):
        if p.total_experience_years is None:
            return unknown
        return _ans(q, f"{p.total_experience_years:g}", f"{kb_src} (total experience)", "HIGH")

    # --- yes/no skill experience
    if skills and re.search(r"\b(do you|have you|are you|experience (with|in)|familiar|proficient|worked)\b", ql):
        if all(normalize_key(canonical(s)) in candidate_skills(profile) for s in skills):
            return _ans(q, "Yes", f"{kb_src} (verified skills)", "HIGH")
        missing = [s for s in skills if normalize_key(canonical(s)) not in candidate_skills(profile)]
        return _ans(q, None, kb_src, "LOW", note=f"Not in your verified skills: {', '.join(missing)}.")

    # --- notice period / availability
    if "notice" in ql or "join" in ql and ("when" in ql or "how soon" in ql):
        if p.notice_period_days is None:
            return unknown
        return _ans(q, f"{p.notice_period_days} days", f"{kb_src} (notice period)", "HIGH")

    # --- compensation (sensitive: always needs approval)
    if re.search(r"\b(expected|expectation)\b.*\b(ctc|salary|compensation|pay)\b|\bexpected (ctc|salary)\b", ql):
        if p.expected_ctc is None:
            return unknown
        cur = f" {p.ctc_currency}" if p.ctc_currency else ""
        return _ans(q, f"{p.expected_ctc:,.0f}{cur}", f"{kb_src} (expected CTC)", "HIGH", sensitive=True)
    if re.search(r"\b(current|present)\b.*\b(ctc|salary|compensation|pay)\b|\bctc\b", ql):
        if p.current_ctc is None:
            return unknown
        cur = f" {p.ctc_currency}" if p.ctc_currency else ""
        return _ans(q, f"{p.current_ctc:,.0f}{cur}", f"{kb_src} (current CTC)", "HIGH", sensitive=True)

    # --- work authorization / visa (sensitive)
    if re.search(r"\b(visa|sponsor|authori[sz]ed|work permit|right to work)\b", ql):
        if not prefs.visa_requirement:
            return unknown
        return _ans(q, prefs.visa_requirement, f"{kb_src} (visa requirement)", "MEDIUM", sensitive=True)

    # --- relocation / location / remote
    if "relocat" in ql:
        if prefs.relocation is None:
            return unknown
        return _ans(q, "Yes" if prefs.relocation else "No", f"{kb_src} (relocation preference)", "HIGH")
    if re.search(r"\b(current(ly)?|where)\b.*\b(location|city|based|live)\b", ql):
        return unknown if not p.current_location else _ans(q, p.current_location, f"{kb_src} (current location)", "HIGH")
    if "remote" in ql:
        if prefs.remote_preference is None:
            return unknown
        return _ans(q, "Yes" if prefs.remote_preference else "No", f"{kb_src} (remote preference)", "HIGH")

    # --- links and contact
    for key, attr, label in (("linkedin", "linkedin_url", "LinkedIn"), ("github", "github_url", "GitHub"),
                             ("portfolio", "portfolio_url", "portfolio"), ("website", "portfolio_url", "portfolio")):
        if key in ql:
            v = getattr(p, attr)
            return unknown if not v else _ans(q, str(v), f"{kb_src} ({label} URL)", "HIGH")
    if "email" in ql:
        return unknown if not p.email else _ans(q, str(p.email), f"{kb_src} (email)", "HIGH")
    if re.search(r"\b(phone|mobile|contact number)\b", ql):
        return unknown if not p.phone else _ans(q, p.phone, f"{kb_src} (phone)", "HIGH")
    if re.search(r"\b(full name|your name)\b", ql):
        return unknown if not p.name else _ans(q, p.name, f"{kb_src} (name)", "HIGH")
    if re.search(r"\b(current (company|employer)|where do you work)\b", ql):
        return unknown if not p.current_company else _ans(q, p.current_company, f"{kb_src} (current company)", "HIGH")
    if re.search(r"\b(current (title|designation|role|position))\b", ql):
        return unknown if not p.current_designation else _ans(q, p.current_designation, f"{kb_src} (designation)", "HIGH")

    # --- education and certifications
    if re.search(r"\b(degree|qualification|education|graduat)\b", ql):
        if not kb.education:
            return unknown
        e = kb.education[0]
        text = ", ".join(x for x in (f"{e.degree} in {e.field}" if e.field else e.degree, e.institution,
                                     str(e.end_year) if e.end_year else None) if x)
        return _ans(q, text, f"{kb_src} (education)", "HIGH")
    if re.search(r"\b(certif|certified)\b", ql):
        names = [c.name for c in kb.certifications]
        asked = [n for n in names if n.lower() in ql]
        if asked:
            return _ans(q, "Yes", f"{kb_src} (certifications)", "HIGH")
        if names and re.search(r"\b(which|what|list)\b", ql):
            return _ans(q, ", ".join(names), f"{kb_src} (certifications)", "HIGH")
        return _ans(q, None, kb_src, "LOW", note="That certification is not in your profile.")

    return unknown
