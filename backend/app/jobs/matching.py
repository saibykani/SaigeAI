"""Candidate <-> job compatibility scoring (spec sections 15-16).

Deterministic and explainable: every sub-score comes from the verified profile and the JD
analysis. A dimension with insufficient information is `None` (UNKNOWN) and is excluded from the
weighted average instead of being guessed.
"""

import re
from difflib import SequenceMatcher

from app.schemas.job import JDAnalysis, MatchBreakdown, MatchResult, MatchWeights
from app.schemas.profile import Profile
from app.services.skills_vocab import canonical, category_of, normalize_key
from app.utils import utcnow

CITY_ALIASES = {
    "bengaluru": "bangalore", "gurugram": "gurgaon", "new delhi": "delhi", "delhi ncr": "delhi",
    "ncr": "delhi", "bombay": "mumbai", "madras": "chennai", "calcutta": "kolkata",
    "hyderabad telangana": "hyderabad",
}
# Tokens treated as equivalent when comparing job titles with target roles.
ROLE_SYNONYMS = {
    "sdet": "qa", "tester": "qa", "testing": "qa", "test": "qa", "quality": "qa", "qe": "qa",
    "assurance": "qa", "engineer": "engineer", "developer": "engineer", "dev": "engineer",
    "automation": "automation", "automated": "automation", "sr": "senior", "jr": "junior",
    "perf": "performance",
}
_ROLE_STOP = {"of", "and", "the", "a", "in", "for", "i", "ii", "iii", "iv", "senior", "junior",
              "lead", "staff", "principal", "remote", "hybrid", "-", "/"}


SKILLS_UNKNOWN_CAP = 60  # "Potential Match" at most


def classify(score: int) -> str:
    if score >= 85:
        return "Highly Relevant"
    if score >= 70:
        return "Relevant"
    if score >= 55:
        return "Potential Match"
    if score >= 40:
        return "Low Match"
    return "Not Relevant"


def _skill_key(s: str) -> str:
    return normalize_key(canonical(s))


# Umbrella skills implied by having a concrete tool in that category (Rest Assured -> API Testing).
# Used for matching only; the truth guard never grants skills this way.
UMBRELLA_SKILLS = {"api_testing": "API Testing", "ci_cd": "CI/CD",
                   "performance_testing": "Performance Testing", "manual_testing": "Manual Testing"}


def candidate_skills(profile: Profile) -> set[str]:
    skills = list(profile.skills.all())
    for exp in profile.knowledge.experience:
        skills += exp.technologies
    for proj in profile.knowledge.projects:
        skills += proj.technologies
    implied = {UMBRELLA_SKILLS[cat] for s in skills if (cat := category_of(s)) in UMBRELLA_SKILLS}
    for category, umbrella in UMBRELLA_SKILLS.items():
        if getattr(profile.skills, category):
            implied.add(umbrella)
    return {_skill_key(s) for s in skills} | {_skill_key(s) for s in implied}


def _role_tokens(title: str) -> set[str]:
    words = re.split(r"[^a-z0-9+#]+", title.lower())
    return {ROLE_SYNONYMS.get(w, w) for w in words if w and w not in _ROLE_STOP}


def role_similarity(job_title: str, targets: list[str]) -> float | None:
    if not targets:
        return None
    jt = _role_tokens(job_title)
    best = 0.0
    for t in targets:
        tt = _role_tokens(t)
        if not jt or not tt:
            continue
        jaccard = len(jt & tt) / len(jt | tt)
        contain = len(jt & tt) / len(tt)  # all target tokens present -> strong match
        seq = SequenceMatcher(None, job_title.lower(), t.lower()).ratio()
        best = max(best, 0.5 * contain + 0.3 * jaccard + 0.2 * seq)
    return round(min(best, 1.0) * 100, 1)


def _norm_loc(value: str) -> str:
    v = re.sub(r"[^a-z ]", " ", value.lower())
    v = re.sub(r"\s+", " ", v).strip()
    for alias, canon in CITY_ALIASES.items():
        v = re.sub(rf"\b{alias}\b", canon, v)
    return v


def _loc_match(job_loc: str, prefs: list[str]) -> bool:
    jl = _norm_loc(job_loc)
    for p in prefs:
        pl = _norm_loc(p)
        if pl and (pl in jl or jl in pl or bool(set(pl.split()) & set(jl.split()) - {"india", "remote"})):
            return True
    return False


def compute_match(profile: Profile, job: dict, jd: JDAnalysis,
                  weights: MatchWeights | None = None) -> MatchResult:
    w = weights or MatchWeights()
    p, prefs = profile.personal, profile.preferences
    issues: list[str] = []
    b = MatchBreakdown()

    # --- skills
    have = candidate_skills(profile)
    req = list(dict.fromkeys(jd.required_skills))
    pref = list(dict.fromkeys(jd.preferred_skills))
    matched = [s for s in req + pref if _skill_key(s) in have]
    missing_req = [s for s in req if _skill_key(s) not in have]
    missing_pref = [s for s in pref if _skill_key(s) not in have]
    if req or pref:
        req_score = (len(req) - len(missing_req)) / len(req) if req else 1.0
        pref_score = (len(pref) - len(missing_pref)) / len(pref) if pref else req_score
        b.skills = round((0.8 * req_score + 0.2 * pref_score) * 100, 1) if req else round(pref_score * 100, 1)
    if not have:
        issues.append("Your profile has no skills yet - skills match is based on an empty list")

    # --- experience
    gap = None
    yrs = p.total_experience_years
    if jd.experience_min is not None:
        if yrs is None:
            issues.append("Total experience is UNKNOWN in your profile")
        elif yrs >= jd.experience_min:
            b.experience = 100.0
            if jd.experience_max is not None and yrs > jd.experience_max + 3:
                b.experience = 80.0
                gap = (f"{yrs:g} years vs {jd.experience_min:g}-{jd.experience_max:g} required "
                       "(may be overqualified)")
        else:
            short = jd.experience_min - yrs
            b.experience = round(max(0.0, 100 - short * 25), 1)
            gap = f"{short:g} year(s) short of the {jd.experience_min:g}+ years required"
            issues.append(f"Experience gap: {gap}")

    # --- role
    targets = prefs.target_roles or ([p.current_designation] if p.current_designation else [])
    b.role = role_similarity(job.get("title", ""), targets)
    if b.role is None:
        issues.append("No target roles or current designation set - role match is UNKNOWN")

    # --- domain
    if jd.domains:
        mine = {d.lower() for d in profile.knowledge.domains}
        mine |= {e.domain.lower() for e in profile.knowledge.experience if e.domain}
        if mine:
            b.domain = 100.0 if {d.lower() for d in jd.domains} & mine else 50.0

    # --- location
    job_loc = job.get("location") or ""
    remote = job.get("remote") if job.get("remote") is not None else jd.remote
    loc_prefs = prefs.preferred_locations + ([p.current_location] if p.current_location else [])
    if prefs.excluded_locations and job_loc and _loc_match(job_loc, prefs.excluded_locations):
        b.location = 0.0
        issues.append(f"Location '{job_loc}' is in your excluded locations")
    elif remote and prefs.remote_preference is not False:
        b.location = 100.0
    elif job_loc and loc_prefs:
        if _loc_match(job_loc, loc_prefs):
            b.location = 100.0
        elif prefs.relocation:
            b.location = 70.0
        else:
            b.location = 30.0
            issues.append(f"Location issue: '{job_loc}' is not in your preferred locations")
    elif remote is False and prefs.remote_preference and not prefs.hybrid_preference:
        b.location = 40.0
        issues.append("On-site role but you prefer remote")

    # --- salary
    job_max = job.get("salary_max") or jd.salary_max
    job_cur = (job.get("currency") or jd.currency or "").upper()
    want = prefs.min_salary or p.expected_ctc
    want_cur = (prefs.salary_currency or p.ctc_currency or "").upper()
    if job_max and want:
        if job_cur and want_cur and job_cur != want_cur:
            issues.append(f"Salary in {job_cur}, your expectation is in {want_cur} - not compared")
        elif job_max >= want:
            b.salary = 100.0
        else:
            b.salary = round(max(0.0, job_max / want) * 100, 1)
            issues.append(f"Salary issue: posted maximum {job_max:,.0f} is below your {want:,.0f}")

    # --- notice period
    if jd.notice_period_max_days is not None and p.notice_period_days is not None:
        if p.notice_period_days <= jd.notice_period_max_days:
            b.notice_period = 100.0
        else:
            b.notice_period = 40.0
            issues.append(f"Notice period issue: yours is {p.notice_period_days} days, "
                          f"role wants {jd.notice_period_max_days} or less")

    # --- education
    if jd.education:
        b.education = 100.0 if profile.knowledge.education else None
        if not profile.knowledge.education:
            issues.append("Role lists a degree requirement; education is UNKNOWN in your profile")

    # --- work authorization
    if jd.no_visa_sponsorship and prefs.visa_requirement and \
            prefs.visa_requirement.strip().lower() not in {"no", "none", "not required", "n/a"}:
        b.work_authorization = 20.0
        issues.append("Role does not sponsor visas and your profile says you need sponsorship")

    # --- weighted overall over known dimensions only
    scores = b.model_dump()
    wd = w.model_dump()
    used = {k: wd[k] for k, v in scores.items() if v is not None and wd[k] > 0}
    total_w = sum(used.values())
    overall = round(sum(scores[k] * wt for k, wt in used.items()) / total_w) if total_w else 0

    # Without a skills signal the score rests on role/location alone - never call that a strong match.
    if b.skills is None and overall > SKILLS_UNKNOWN_CAP:
        overall = SKILLS_UNKNOWN_CAP
        issues.append("No recognizable skills in this JD - score is based on role and location only; "
                      "read the description before applying")

    company = (job.get("company") or "").lower()
    if company and any(company == c.lower() for c in prefs.excluded_companies):
        issues.insert(0, f"{job.get('company')} is in your excluded companies")
        overall = min(overall, 20)

    return MatchResult(
        overall=overall, classification=classify(overall), breakdown=b,  # type: ignore[arg-type]
        matched_skills=matched, missing_required_skills=missing_req,
        missing_preferred_skills=missing_pref, experience_gap=gap, issues=issues,
        weights={k: round(v / total_w, 3) for k, v in used.items()} if total_w else {},
        computed_at=utcnow().isoformat(),
    )
