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
    title = (title or "").strip() or _guess_title(jd_text)
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


def _guess_title(text: str) -> str:
    for line in (text or "").splitlines()[:6]:
        line = line.strip(" :-*#")
        if 3 <= len(line) <= 80 and not line.endswith("."):
            return line
    return "Target role"


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
