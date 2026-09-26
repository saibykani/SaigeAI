"""Deterministic job-description analysis.

Every extracted value is read from the JD text itself; nothing is inferred beyond simple,
documented rules. An optional LLM pass (app.agents.jd_agent) may add to this, but its output is
verified against the same text.
"""

import html
import re

from app.schemas.job import JDAnalysis
from app.services.skills_vocab import find_skills

_SECTIONS: dict[str, tuple[str, ...]] = {
    "requirements": ("requirements", "qualifications", "what you'll need", "what you will need",
                     "must have", "must-have", "what we're looking for", "what we are looking for",
                     "you have", "skills required", "required skills", "basic qualifications",
                     "minimum qualifications", "who you are", "your profile", "skills and experience",
                     "desired profile", "candidate profile", "key skills", "technical skills"),
    "nice_to_have": ("nice to have", "nice-to-have", "preferred", "preferred qualifications",
                     "bonus", "good to have", "good-to-have", "plus", "bonus points", "added advantage"),
    "responsibilities": ("responsibilities", "what you'll do", "what you will do",
                         "key responsibilities", "the role", "your role", "duties",
                         "role and responsibilities",
                         "in this role", "day to day", "what you’ll do"),
}

_BULLET = re.compile(r"^\s*(?:[•●▪◦‣∙·*\-–—>]|\d+[.)])\s+")
_EXP_RANGE = re.compile(
    r"(\d{1,2}(?:\.\d)?)\s*(?:\+\s*)?(?:-|–|—|to)\s*(\d{1,2}(?:\.\d)?)\s*\+?\s*(?:years?|yrs?)", re.I)
_EXP_MIN = re.compile(
    r"(?:minimum|min\.?|at least|over)?\s*(\d{1,2}(?:\.\d)?)\s*\+?\s*(?:years?|yrs?)(?:\s+of)?", re.I)
_LPA = re.compile(
    r"(?:₹|inr|rs\.?)?\s*(\d{1,3}(?:\.\d+)?)\s*(?:-|–|to)\s*(\d{1,3}(?:\.\d+)?)\s*(?:lpa|lakhs?|l\b)",
    re.I)
_USD = re.compile(
    r"(\$|usd|€|eur|£|gbp)\s*(\d{2,3}(?:,\d{3})*(?:\.\d+)?)\s*(k)?\s*(?:-|–|to)\s*(?:\$|usd|€|eur|£|gbp)?\s*"
    r"(\d{2,3}(?:,\d{3})*(?:\.\d+)?)\s*(k)?", re.I)
# Stricter than the resume pattern: abbreviations need their dots so "be"/"me" never match.
_JD_DEGREE = re.compile(
    r"\b(B\.\s?Tech|M\.\s?Tech|BTech|MTech|B\.E\.|M\.E\.|B\.Sc|M\.Sc|BCA|MCA|MBA|Ph\.?D|"
    r"Bachelor(?:'s)?(?:\s+degree)?|Master(?:'s)?\s+degree|Master's|"
    r"(?:university\s+)?degree\s+in\s+[A-Za-z ]{3,40})",
    re.I,
)
_CURRENCY = {"$": "USD", "usd": "USD", "€": "EUR", "eur": "EUR", "£": "GBP", "gbp": "GBP"}
_NOTICE = re.compile(r"(?:notice period|join(?:ing)?)\D{0,30}?(\d{1,3})\s*days", re.I)
_IMMEDIATE = re.compile(r"immediate\s+joiners?|join\s+immediately", re.I)
_NO_VISA = re.compile(
    r"(no|not|unable to|cannot|can't|do not|don't)\s+(?:provide\s+|offer\s+)?(?:visa\s+)?sponsor|"
    r"sponsorship\s+(?:is\s+)?not\s+(?:available|provided)|must be (?:legally )?authori[sz]ed to work", re.I)

_DOMAINS = {
    "Fintech": ("fintech", "payments", "payment gateway", "upi"), "Banking": ("banking", "bank "),
    "Insurance": ("insurance", "insurtech"), "Healthcare": ("healthcare", "health tech", "medical", "pharma"),
    "E-commerce": ("e-commerce", "ecommerce", "online retail", "marketplace"), "Retail": ("retail",),
    "Telecom": ("telecom",), "Gaming": ("gaming",), "SaaS": ("saas", "b2b software"),
    "EdTech": ("edtech", "education technology"), "Logistics": ("logistics", "supply chain"),
    "Automotive": ("automotive",), "Travel": ("travel", "hospitality"), "Media": ("media", "streaming"),
}
_SENIORITY = [("intern", "Intern"), ("trainee", "Intern"), ("junior", "Junior"), ("jr", "Junior"),
              ("principal", "Principal"), ("staff", "Staff"), ("lead", "Lead"), ("head", "Head"),
              ("manager", "Manager"), ("senior", "Senior"), ("sr", "Senior"), ("associate", "Associate")]
_EMPLOYMENT = [("internship", "Internship"), ("part-time", "Part-time"), ("part time", "Part-time"),
               ("contract", "Contract"), ("freelance", "Freelance"), ("temporary", "Temporary"),
               ("full-time", "Full-time"), ("full time", "Full-time"), ("permanent", "Full-time")]


def html_to_text(raw: str) -> str:
    """Convert ATS HTML (possibly entity-escaped) to plain text with bullets and line breaks."""
    text = html.unescape(html.unescape(raw))
    text = re.sub(r"(?is)<(script|style).*?</\1>", " ", text)
    text = re.sub(r"(?i)<li[^>]*>", "\n- ", text)
    text = re.sub(r"(?i)<br\s*/?>|</(p|div|h[1-6]|ul|ol|li|tr)>", "\n", text)
    text = re.sub(r"(?i)<(h[1-6])[^>]*>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[ \t\xa0]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n\n", "\n".join(line.strip() for line in text.splitlines())).strip()


def _heading(line: str) -> str | None:
    s = re.sub(r"[:\-–—*#]+$", "", line.strip()).strip().lower()
    if not s or len(s) > 60 or _BULLET.match(line):
        return None
    for section, names in _SECTIONS.items():
        if any(s == n or s.startswith(n + " ") or s.endswith(" " + n) for n in names):
            return section
    return None


def split_sections(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {"intro": []}
    current = "intro"
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        sec = _heading(line)
        if sec:
            current = sec
            sections.setdefault(sec, [])
            continue
        sections.setdefault(current, []).append(_BULLET.sub("", line).strip())
    return sections


def _experience(text: str) -> tuple[float | None, float | None, str | None]:
    m = _EXP_RANGE.search(text)
    if m:
        lo, hi = float(m.group(1)), float(m.group(2))
        if lo <= hi <= 40:
            return lo, hi, m.group(0).strip()
    for m in _EXP_MIN.finditer(text):
        yrs = float(m.group(1))
        if 0 < yrs <= 30:
            return yrs, None, m.group(0).strip()
    return None, None, None


def _salary(text: str) -> tuple[float | None, float | None, str | None]:
    m = _LPA.search(text)
    if m:
        return float(m.group(1)) * 100000, float(m.group(2)) * 100000, "INR"
    m = _USD.search(text)
    if m:
        cur = _CURRENCY[m.group(1).lower()]
        lo = float(m.group(2).replace(",", "")) * (1000 if m.group(3) else 1)
        hi = float(m.group(4).replace(",", "")) * (1000 if (m.group(5) or m.group(3)) else 1)
        if lo <= hi:
            return lo, hi, cur
    return None, None, None


def analyze_jd(title: str, description: str) -> JDAnalysis:
    text = description
    low = f"{title}\n{text}".lower()
    sections = split_sections(text)
    req_lines = sections.get("requirements", [])
    pref_lines = sections.get("nice_to_have", [])
    resp_lines = sections.get("responsibilities", [])

    all_skills = find_skills(f"{title}\n{text}")
    preferred = find_skills("\n".join(pref_lines))
    if req_lines or resp_lines:
        required = find_skills("\n".join([title] + req_lines + resp_lines))
    else:
        # No recognisable sections: every skill outside the nice-to-have block is required.
        required = [s for s in all_skills if s not in preferred]
    preferred = [s for s in preferred if s not in required]
    # Skills mentioned only in the intro/company blurb count as preferred, not required.
    for s in all_skills:
        if s not in required and s not in preferred:
            preferred.append(s)

    exp_min, exp_max, exp_text = _experience("\n".join(req_lines) or text)
    sal_min, sal_max, cur = _salary(text)

    notice = None
    m = _NOTICE.search(text)
    if m:
        notice = int(m.group(1))
    elif _IMMEDIATE.search(text):
        notice = 0

    seniority = next((label for key, label in _SENIORITY
                      if re.search(rf"\b{key}\b", title.lower())), None)
    employment = next((label for key, label in _EMPLOYMENT if key in low), None)
    remote_rx = r"\b(fully remote|remote[- ]first|100% remote|work from home|wfh|remote)\b"
    remote = True if re.search(remote_rx, low) else None
    hybrid = True if "hybrid" in low else None
    if remote and hybrid:
        remote = None  # "hybrid" roles often mention remote days; don't treat as fully remote
    if re.search(r"\b(on-?site|in[- ]office|work from office|wfo)\b", low) and not remote:
        remote = False

    return JDAnalysis(
        skills=all_skills,
        required_skills=required,
        preferred_skills=preferred,
        requirements=req_lines[:40],
        nice_to_have=pref_lines[:30],
        responsibilities=resp_lines[:40],
        experience_min=exp_min, experience_max=exp_max, experience_text=exp_text,
        seniority=seniority,
        remote=remote, hybrid=hybrid,
        employment_type=employment,
        salary_min=sal_min, salary_max=sal_max, currency=cur,
        education=list(dict.fromkeys(m.group(0).strip() for m in _JD_DEGREE.finditer(text)))[:5],
        domains=[d for d, keys in _DOMAINS.items() if any(k in low for k in keys)],
        notice_period_max_days=notice,
        no_visa_sponsorship=bool(_NO_VISA.search(text)),
    )
