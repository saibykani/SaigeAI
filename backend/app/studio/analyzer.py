"""JD analyzer: read a job description and explain it against the verified master profile.

Everything here is deterministic and grounded: "you have" means the skill is in the verified profile,
"you don't have" means it isn't (you may still have it; add it to the profile if so). Nothing about the
candidate is assumed. Unknown profile values are reported as unknown, never guessed.
"""

import re

from app.jobs.jd_parser import analyze_jd
from app.jobs.matching import _skill_key, candidate_skills, compute_match
from app.schemas.job import JDAnalysis
from app.schemas.profile import Profile
from app.services.skills_vocab import canonical, find_skills

DEGREE_WORDS = {"bachelor": ("b.tech", "btech", "b.e", "be ", "bsc", "b.sc", "bca", "bachelor", "b.com", "ba "),
                "master": ("m.tech", "mtech", "msc", "m.sc", "mca", "master", "mba", "m.e"),
                "phd": ("phd", "ph.d", "doctor")}


def _degree_level(text: str) -> str | None:
    t = f" {text.lower()} "
    for level in ("phd", "master", "bachelor"):
        if any(w in t for w in DEGREE_WORDS[level]):
            return level
    return None


def _status(ok: bool | None) -> str:
    return "unknown" if ok is None else "met" if ok else "not_met"


def _requirement_rows(jd: JDAnalysis, have: set[str], years: float | None) -> list[dict]:
    """Each requirement line from the JD, with whether the profile shows it."""
    rows = []
    for line in (jd.requirements + jd.nice_to_have)[:30]:
        skills = [canonical(s) for s in find_skills(line)]
        m = re.search(r"(\d+(?:\.\d+)?)\s*\+?\s*(?:-|to)?\s*(\d+)?\s*(?:years|yrs)", line, re.I)
        if m:
            need = float(m.group(1))
            ok = None if years is None else years >= need
            why = f"Needs {need:g}+ years; your profile says {years:g}." if years is not None else "Your total experience isn't in your profile."
        elif skills:
            missing = [s for s in skills if _skill_key(s) not in have]
            ok = not missing
            why = "You have " + ", ".join(skills) if ok else "Not in your profile: " + ", ".join(missing)
        else:
            ok, why = None, "Check this yourself: it isn't a skill or experience Saige can verify."
        rows.append({"text": line, "status": _status(ok), "why": why, "nice_to_have": line in jd.nice_to_have})
    return rows


def analyze(profile: Profile, jd_text: str, title: str = "", company: str = "") -> dict:
    title = (title or "").strip() or _guess_title(jd_text) or "This role"
    jd = analyze_jd(title, jd_text)
    p = profile.personal
    have = candidate_skills(profile)
    years = p.total_experience_years
    match = compute_match(profile, {"title": title, "company": company, "location": None, "remote": jd.remote, "skills": jd.skills}, jd)

    req = list(dict.fromkeys(canonical(s) for s in jd.required_skills))
    pref = [s for s in dict.fromkeys(canonical(s) for s in jd.preferred_skills) if s not in req]
    req_have = [s for s in req if _skill_key(s) in have]
    req_miss = [s for s in req if s not in req_have]
    pref_have = [s for s in pref if _skill_key(s) in have]
    pref_miss = [s for s in pref if s not in pref_have]
    cov = round(100 * len(req_have) / len(req)) if req else None

    # experience
    exp_need = jd.experience_min
    if exp_need is None:
        exp = {"status": "unknown", "text": "The JD doesn't state the years of experience needed."}
    elif years is None:
        exp = {"status": "unknown", "text": f"Needs {exp_need:g}+ years. Add your total experience to your profile to check."}
    elif years >= exp_need:
        over = jd.experience_max is not None and years > jd.experience_max + 3
        exp = {"status": "met", "text": f"Needs {exp_need:g}{f'–{jd.experience_max:g}' if jd.experience_max else '+'} years; you have {years:g}."
               + (" You may be considered overqualified." if over else "")}
    else:
        exp = {"status": "not_met", "text": f"Needs {exp_need:g}+ years; you have {years:g} ({exp_need - years:g} short)."}

    # education
    need_level = _degree_level(" ".join(jd.education)) if jd.education else None
    mine = [f"{e.degree}{f' in {e.field}' if e.field else ''}" for e in profile.knowledge.education]
    my_level = max((_degree_level(m) or "" for m in mine), key=lambda x: ("", "bachelor", "master", "phd").index(x) if x else 0, default="")
    if not jd.education:
        edu = {"status": "unknown", "text": "No degree requirement stated."}
    elif not mine:
        edu = {"status": "unknown", "text": f"Asks for: {'; '.join(jd.education[:2])}. Your education isn't in your profile."}
    else:
        order = ("", "bachelor", "master", "phd")
        ok = None if not need_level or not my_level else order.index(my_level) >= order.index(need_level)
        edu = {"status": _status(ok), "text": f"Asks for: {'; '.join(jd.education[:2])}. You have: {', '.join(mine[:2])}."}

    # eligibility checklist
    checks = [
        {"label": "Required skills", "status": "unknown" if cov is None else "met" if cov >= 70 else "not_met" if cov < 40 else "partial",
         "text": "No specific skills listed." if cov is None else f"You have {len(req_have)} of {len(req)} required skills ({cov}%)."},
        {"label": "Experience", **exp},
        {"label": "Education", **edu},
    ]
    if jd.notice_period_max_days is not None:
        n = p.notice_period_days
        checks.append({"label": "Notice period", "status": _status(None if n is None else n <= jd.notice_period_max_days),
                       "text": f"Wants {jd.notice_period_max_days} days or less; yours is {'not set' if n is None else f'{n} days'}."})
    if jd.no_visa_sponsorship:
        checks.append({"label": "Work authorisation", "status": "unknown", "text": "No visa sponsorship: you need the right to work there."})

    hard_fail = any(c["status"] == "not_met" for c in checks if c["label"] in ("Experience", "Education"))
    if hard_fail or (cov is not None and cov < 40):
        verdict = ("not_yet", "Not eligible yet")
    elif all(c["status"] in ("met", "unknown") for c in checks) and (cov is None or cov >= 70):
        verdict = ("eligible", "Eligible: apply")
    else:
        verdict = ("partial", "Partly eligible: worth applying if you can speak to the gaps")

    strengths = []
    if req_have:
        strengths.append(f"Required skills you already have: {', '.join(req_have[:8])}.")
    if pref_have:
        strengths.append(f"Bonus skills you have: {', '.join(pref_have[:6])}.")
    if exp["status"] == "met":
        strengths.append(exp["text"])
    if match.breakdown.role and match.breakdown.role >= 70:
        strengths.append(f"Your target roles line up with “{title}”.")
    if match.breakdown.domain == 100:
        strengths.append(f"Same domain: {', '.join(jd.domains[:3])}.")

    gaps = [f"{s}: required. If you have used it, add it to your Profile; otherwise it's the first thing to learn." for s in req_miss[:8]]
    gaps += [f"{s}: nice to have." for s in pref_miss[:5]]
    if exp["status"] == "not_met":
        gaps.append(exp["text"])

    return {
        "title": title, "company": company or None,
        "role": {"seniority": jd.seniority, "employment_type": jd.employment_type,
                 "work_mode": "Remote" if jd.remote else "Hybrid" if jd.hybrid else None,
                 "salary": _salary(jd), "domains": jd.domains},
        "score": match.overall, "classification": match.classification, "breakdown": match.breakdown.model_dump(),
        "verdict": {"key": verdict[0], "label": verdict[1]},
        "eligibility": checks,
        "skills": {"required": [{"name": s, "have": s in req_have} for s in req],
                   "preferred": [{"name": s, "have": s in pref_have} for s in pref],
                   "required_coverage": cov},
        "requirements": _requirement_rows(jd, have, years),
        "responsibilities": jd.responsibilities[:15],
        "strengths": strengths, "gaps": gaps, "issues": match.issues,
        "keywords_to_use": req_have + pref_have,
        "summary": _plain_summary(title, company, verdict[1], cov, req_miss, exp),
    }


def _salary(jd: JDAnalysis) -> str | None:
    if not (jd.salary_min or jd.salary_max):
        return None
    lo, hi = jd.salary_min, jd.salary_max
    return f"{jd.currency or ''} {lo:,.0f}{f' – {hi:,.0f}' if hi and hi != lo else ''}".strip()


_ROLE_WORDS = re.compile(r"\b(engineer|sdet|tester|testing|qa|qe|developer|analyst|architect|lead|manager|consultant|specialist|"
                         r"scientist|designer|administrator|associate|intern|executive|officer|devops|sre|programmer)\b", re.I)
_JUNK = re.compile(r"cookie|accept|privacy|sign in|log in|apply now|share|save job|subscribe|consent|javascript|skip to|menu|"
                   r"posted|applicants|easy apply|promoted", re.I)
_TITLE_PATTERNS = [
    re.compile(r"(?im)^\s*(?:job title|position|role|designation|opening|job role|title)\s*[:\-–]\s*(.{3,80}?)\s*$"),
    re.compile(r"(?i)\b(?:hiring|looking for|seeking|searching for)\s+(?:an?\s+|experienced\s+|talented\s+)*"
               r"((?:senior|junior|lead|staff|principal|sr\.?|jr\.?)?\s*[A-Za-z/&()+\- ]{2,60}?"
               r"(?:engineer|sdet|tester|developer|analyst|architect|lead|manager|consultant|specialist|scientist|designer)s?)\b"),
]


def _guess_title(text: str) -> str:
    """The job title in a JD, ignoring page furniture copied with it (cookie banners, buttons)."""
    head = (text or "")[:5000]
    for rx in _TITLE_PATTERNS:
        m = rx.search(head)
        if m and not _JUNK.search(m.group(1)):
            return re.sub(r"\s+", " ", m.group(1)).strip(" :-–,.")
    for line in head.splitlines()[:25]:
        line = line.strip(" :-*#•|\t")
        if 3 <= len(line) <= 70 and not line.endswith(".") and _ROLE_WORDS.search(line) and not _JUNK.search(line):
            return line
    return ""


def _plain_summary(title: str, company: str, verdict: str, cov: int | None, missing: list[str], exp: dict) -> str:
    at = f" at {company}" if company else ""
    parts = [f"{title}{at}: {verdict}."]
    if cov is not None:
        parts.append(f"You cover {cov}% of the required skills.")
    if missing:
        parts.append(f"Missing: {', '.join(missing[:5])}.")
    if exp["status"] != "unknown":
        parts.append(exp["text"])
    return " ".join(parts)


# ------------------------------------------------------------------ company name from the JD

_GENERIC = {"us", "the company", "our company", "company", "the team", "our team", "we", "you", "the role", "this role", "india",
            "remote", "hybrid", "job", "jobs", "careers", "linkedin", "naukri", "indeed", "glassdoor", "equal opportunity"}
_CO = r"([A-Z][A-Za-z0-9&.'\-]*(?:\s+(?:[A-Z][A-Za-z0-9&.'\-]*|&|of|and)){0,4})"
_PATTERNS = [
    re.compile(r"(?im)^\s*(?:company|company name|organi[sz]ation|employer|client)\s*[:\-–]\s*(.+?)\s*$"),
    re.compile(r"(?m)^\s*About\s+" + _CO + r"\s*:?\s*$"),
    re.compile(r"(?:Join|join)\s+(?:us\s+at\s+|the\s+team\s+at\s+)?" + _CO + r"(?=[\s,.!]|$)"),
    re.compile(r"(?:at|At)\s+" + _CO + r",?\s+(?:we|our|you)\b"),
    re.compile(r"(?m)^\s*" + _CO + r"\s+(?:is|are)\s+(?:a|an|the|one of|india'?s|the world'?s|hiring|looking)\b"),
    re.compile(r"(?:Why|why)\s+" + _CO + r"\s*\?"),
    re.compile(r"(?:work(?:ing)?\s+(?:at|with|for))\s+" + _CO + r"(?=[\s,.!]|$)"),
]
_DOMAIN = re.compile(r"(?:@|https?://(?:www\.|careers\.|jobs\.)?|www\.)([a-z0-9-]{2,40})\.(?:com|in|io|ai|co|org|net|tech)\b", re.I)
_FREEMAIL = {"gmail", "yahoo", "outlook", "hotmail", "linkedin", "naukri", "indeed", "greenhouse", "lever", "workday", "myworkdayjobs",
             "ashbyhq", "smartrecruiters", "google", "forms", "bit", "rediffmail", "icloud", "proton"}


def _clean_company(s: str) -> str | None:
    s = re.sub(r"\s+", " ", s or "").strip(" .,:;-–|\"'")
    s = re.sub(r"\s+(?:is|are|was|has|we|our|India|Pvt|Private|Limited|Ltd|Inc|LLC)\.?$", "", s, flags=re.I).strip()
    if not s or len(s) > 60 or s.lower() in _GENERIC or len(s) < 2:
        return None
    return s


def extract_company(text: str) -> str | None:
    """The hiring company named in a job description, or None if it isn't clear."""
    head = (text or "")[:6000]
    votes: dict[str, int] = {}
    for i, rx in enumerate(_PATTERNS):
        for m in rx.finditer(head):
            name = _clean_company(m.group(1))
            if name:
                votes[name] = votes.get(name, 0) + (3 if i == 0 else 2)
    for m in _DOMAIN.finditer(head):
        d = m.group(1).lower()
        if d not in _FREEMAIL:
            # prefer a written name that matches the domain ("razorpay.com" -> "Razorpay")
            match = next((n for n in votes if n.lower().replace(" ", "") in d or d in n.lower().replace(" ", "")), None)
            key = match or d.capitalize()
            votes[key] = votes.get(key, 0) + 2
    if not votes:
        return None
    # names repeated across the text are stronger evidence
    for n in list(votes):
        votes[n] += min(len(re.findall(re.escape(n), head)), 5)
    return max(votes, key=votes.get)


def extract_title(text: str) -> str | None:
    """The role named in a job description, for pre-filling forms."""
    return _guess_title(text) or None
