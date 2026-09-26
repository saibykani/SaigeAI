"""JD-based resume tailoring, ATS validation and cover letters (spec section 10, Phase 3).

Pipeline: JD analysis -> requirement extraction -> verified knowledge base -> skill / experience /
keyword mapping -> resume generator -> ATS validation -> truth validation.

The generator only *selects and orders* verified facts. It never invents a skill, employer, title,
metric or project; skills the JD wants that the candidate lacks are reported as gaps. Optional
Claude polish of the summary / cover letter is accepted only if it passes the truth guard.
"""

import re

from pydantic import BaseModel, Field

from app.agents.llm import get_provider
from app.jobs.matching import candidate_skills
from app.schemas.job import JDAnalysis
from app.schemas.profile import Profile
from app.schemas.resume import ParsedEducation, ParsedExperience, ParsedLinks, ParsedProject, ParsedResume
from app.services.skills_vocab import canonical, find_skills, implied_umbrellas, normalize_key
from app.services.truth_guard import GeneratedClaims, validate_claims


def _k(s: str) -> str:
    return normalize_key(canonical(s))


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9+#]{3,}", text.lower())}


class TailorError(ValueError):
    pass


def _jd_keywords(jd: JDAnalysis) -> list[str]:
    return list(dict.fromkeys(jd.required_skills + jd.preferred_skills + jd.skills))


def _relevance(text: str, jd_keys: set[str], req_words: set[str]) -> float:
    skills = {_k(s) for s in find_skills(text)}
    return 2.0 * len(skills & jd_keys) + 0.15 * len(_words(text) & req_words)


def _verified_skill_list(profile: Profile) -> list[str]:
    skills = list(profile.skills.all())
    for e in profile.knowledge.experience:
        skills += e.technologies
    for p in profile.knowledge.projects:
        skills += p.technologies
    categories = [cat for cat, vals in profile.skills.model_dump().items() if vals]
    skills += sorted(implied_umbrellas(skills, categories))
    seen: dict[str, str] = {}
    for s in skills:
        seen.setdefault(_k(s), canonical(s))
    return list(seen.values())


def order_skills(profile: Profile, jd: JDAnalysis) -> tuple[list[str], list[str]]:
    """Verified skills with JD-required first, then preferred, then the rest. Returns (ordered, moved_to_top)."""
    verified = _verified_skill_list(profile)
    by_key = {_k(s): s for s in verified}
    top = [by_key[_k(s)] for s in jd.required_skills if _k(s) in by_key]
    top += [by_key[_k(s)] for s in jd.preferred_skills if _k(s) in by_key and by_key[_k(s)] not in top]
    rest = [s for s in verified if s not in top]
    return top + rest, top


def template_summary(profile: Profile, job_title: str, matched: list[str]) -> str | None:
    p, kb = profile.personal, profile.knowledge
    parts: list[str] = []
    if kb.professional_summary:
        parts.append(kb.professional_summary.strip().rstrip(".") + ".")
    elif p.current_designation:
        yrs = f" with {int(p.total_experience_years)}+ years of experience" if p.total_experience_years else ""
        parts.append(f"{p.current_designation}{yrs}.")
    if matched:
        parts.append(f"Hands-on experience with {', '.join(matched[:6])}, directly relevant to the {job_title} role.")
    if kb.domains:
        parts.append(f"Domain experience: {', '.join(kb.domains)}.")
    return " ".join(parts) or None


class _Summary(BaseModel):
    summary: str = Field(description="2-3 sentence professional summary using only the provided facts")


class _Letter(BaseModel):
    body: str = Field(description="Cover letter body paragraphs using only the provided facts")


def _facts_block(profile: Profile, matched: list[str]) -> str:
    kb, p = profile.knowledge, profile.personal
    lines = [f"Current designation: {p.current_designation or 'UNKNOWN'}",
             f"Total experience (years): {p.total_experience_years if p.total_experience_years is not None else 'UNKNOWN'}",
             f"Verified summary: {kb.professional_summary or 'UNKNOWN'}",
             f"Verified skills relevant to this job: {', '.join(matched) or 'none'}",
             f"Domains: {', '.join(kb.domains) or 'none'}"]
    for e in kb.experience[:4]:
        lines.append(f"Role: {e.title} at {e.company}. Achievements: {'; '.join(e.achievements) or 'none'}")
    return "\n".join(lines)


async def llm_polish(kind: str, profile: Profile, job_title: str, company: str, matched: list[str],
                     fallback: str) -> tuple[str, str]:
    """Optionally ask Claude for better wording; keep it only if it passes the truth guard."""
    provider = get_provider()
    if provider is None:
        return fallback, "deterministic"
    schema = _Summary if kind == "summary" else _Letter
    ask = ("Write a 2-3 sentence resume summary" if kind == "summary"
           else "Write the body (3 short paragraphs, no greeting or sign-off) of a cover letter")
    out = await provider.extract(
        system=("You write job-application text for a candidate. Use ONLY the facts provided. Do not add skills, "
                "employers, titles, numbers, certifications or years that are not in the facts."),
        prompt=f"{ask} for the {job_title} role at {company}.\n\n<facts>\n{_facts_block(profile, matched)}\n</facts>",
        schema=schema,
    )
    text = (getattr(out, "summary", None) or getattr(out, "body", None)) if out else None
    if not text:
        return fallback, "deterministic"
    titles = [profile.personal.current_designation] if profile.personal.current_designation else []
    if validate_claims(GeneratedClaims(text=text, titles=titles), profile).passed:
        return text.strip(), f"deterministic+{provider.name}"
    return fallback, "deterministic"  # LLM wording failed validation; keep the safe version


def tailor_resume(profile: Profile, jd: JDAnalysis, job: dict, base: ParsedResume | None,
                  summary: str | None) -> tuple[ParsedResume, list[str]]:
    kb, p = profile.knowledge, profile.personal
    if not profile.skills.all() and not kb.experience:
        raise TailorError("Complete your master profile (skills and experience) or import a resume into it first.")
    jd_keys = {_k(s) for s in _jd_keywords(jd)}
    req_words = _words(" ".join(jd.requirements + jd.responsibilities))
    skills, moved = order_skills(profile, jd)
    changes: list[str] = []
    if moved:
        changes.append(f"Skills reordered: {', '.join(moved[:8])} moved to the top to match the JD")

    experience: list[ParsedExperience] = []
    reordered_roles = 0
    for e in kb.experience:
        resp = sorted(e.responsibilities, key=lambda b: -_relevance(b, jd_keys, req_words))
        ach = sorted(e.achievements, key=lambda b: -_relevance(b, jd_keys, req_words))
        if resp != e.responsibilities or ach != e.achievements:
            reordered_roles += 1
        experience.append(ParsedExperience(company=e.company, title=e.title, location=e.location,
                                           start_date=e.start_date, end_date=e.end_date, is_current=e.is_current,
                                           responsibilities=resp, achievements=ach, technologies=e.technologies))
    if not experience and base:
        experience = base.experience  # the user's own resume content, unchanged
    if reordered_roles:
        changes.append(f"Most relevant bullets moved first in {reordered_roles} role(s)")

    projects = sorted(kb.projects, key=lambda pr: -_relevance(" ".join([pr.name, *pr.highlights, *pr.technologies]),
                                                               jd_keys, req_words))
    parsed_projects = [ParsedProject(name=pr.name, highlights=pr.highlights, technologies=pr.technologies)
                       for pr in projects[:4]]
    if len(projects) > 1 and projects[0].name != kb.projects[0].name:
        changes.append(f"Projects reordered: '{projects[0].name}' now first")

    if summary:
        changes.insert(0, "Professional summary tailored to the role")
    links = ParsedLinks(linkedin=str(p.linkedin_url) if p.linkedin_url else None,
                        github=str(p.github_url) if p.github_url else None,
                        portfolio=str(p.portfolio_url) if p.portfolio_url else None)
    parsed = ParsedResume(
        name=p.name or (base.name if base else None), email=p.email or (base.email if base else None),
        phone=p.phone or (base.phone if base else None), location=p.current_location, links=links,
        summary=summary or kb.professional_summary, skills=skills,
        tools=[s for s in skills if _k(s) in jd_keys][:12], experience=experience, projects=parsed_projects,
        education=[ParsedEducation(degree=e.degree, institution=e.institution, field=e.field,
                                   start_year=e.start_year, end_year=e.end_year) for e in kb.education]
        or (base.education if base else []),
        certifications=[c.name for c in kb.certifications] or (base.certifications if base else []),
        achievements=[],
    )
    missing = [s for s in jd.required_skills if _k(s) not in candidate_skills(profile)]
    if missing:
        changes.append(f"Not added (not in your verified profile): {', '.join(missing[:8])}")
    return parsed, changes


def resume_text(r: ParsedResume) -> str:
    parts = [r.summary or "", " ".join(r.skills)]
    for e in r.experience:
        parts += [e.title or "", e.company or "", *e.responsibilities, *e.achievements]
    for pr in r.projects:
        parts += [pr.name, *pr.highlights, *pr.technologies]
    parts += r.certifications
    return "\n".join(parts)


def validate_resume(r: ParsedResume, profile: Profile) -> dict:
    claims = GeneratedClaims(
        text=r.summary or "", skills=r.skills,
        companies=[e.company for e in r.experience if e.company],
        titles=[e.title for e in r.experience if e.title],
        certifications=r.certifications, projects=[pr.name for pr in r.projects],
    )
    result = validate_claims(claims, profile)
    return {"status": result.status, "violations": [v.model_dump() for v in result.violations]}


def ats_report(r: ParsedResume, jd: JDAnalysis) -> dict:
    """Keyword coverage against the JD plus structural checks that commonly trip ATS parsers."""
    text = resume_text(r)
    present = {_k(s) for s in r.skills} | {_k(s) for s in find_skills(text)}
    req = list(dict.fromkeys(jd.required_skills))
    pref = list(dict.fromkeys(jd.preferred_skills))
    req_hit = [s for s in req if _k(s) in present]
    pref_hit = [s for s in pref if _k(s) in present]
    words = len(re.findall(r"\w+", text))
    checks = [
        {"check": "Email present", "passed": bool(r.email)},
        {"check": "Phone present", "passed": bool(r.phone)},
        {"check": "Professional summary", "passed": bool(r.summary)},
        {"check": "Skills section", "passed": len(r.skills) >= 5},
        {"check": "Dated work experience", "passed": bool(r.experience) and all(e.start_date for e in r.experience)},
        {"check": "Achievement bullets", "passed": any(e.achievements or e.responsibilities for e in r.experience)},
        {"check": "Education listed", "passed": bool(r.education)},
        {"check": "Length 250-1200 words", "passed": 250 <= words <= 1200},
        {"check": "Single-column, no tables or images", "passed": True},  # guaranteed by the DOCX exporter
    ]
    req_cov = len(req_hit) / len(req) if req else 1.0
    pref_cov = len(pref_hit) / len(pref) if pref else 1.0
    checks_ok = sum(c["passed"] for c in checks) / len(checks)
    score = round(100 * (0.55 * req_cov + 0.15 * pref_cov + 0.30 * checks_ok))
    return {
        "score": score,
        "required_coverage": round(100 * req_cov),
        "preferred_coverage": round(100 * pref_cov),
        "matched_keywords": req_hit + pref_hit,
        "missing_required": [s for s in req if s not in req_hit],
        "missing_preferred": [s for s in pref if s not in pref_hit],
        "checks": checks,
        "word_count": words,
    }


def template_cover_letter(profile: Profile, job: dict, jd: JDAnalysis, matched: list[str]) -> tuple[str, str]:
    """Returns (greeting+signoff wrapper parts are added by caller) body text built from verified facts."""
    p, kb = profile.personal, profile.knowledge
    title, company = job.get("title", "the role"), job.get("company", "your company")
    yrs = f" with {int(p.total_experience_years)}+ years of experience" if p.total_experience_years else ""
    intro = f"I am excited to apply for the {title} position at {company}."
    if p.current_designation:
        intro += f" I am currently a {p.current_designation}{yrs}"
        intro += f" at {p.current_company}." if p.current_company else "."
    body = ""
    if matched:
        body = f"My background lines up closely with what you are looking for, including {', '.join(matched[:5])}."
    wins = [a for e in kb.experience for a in e.achievements][:2]
    if wins:
        body += " Recent results I am proud of: " + " ".join(w.rstrip(".") + "." for w in wins)
    shared = [d for d in kb.domains if d.lower() in {x.lower() for x in jd.domains}]
    if shared:
        body += f" I also bring domain experience in {', '.join(shared)}."
    close = (f"I would welcome the chance to discuss how I can contribute to {company}. "
             "Thank you for your time and consideration.")
    return "\n\n".join(x for x in (intro, body.strip(), close) if x), f"Dear Hiring Team at {company},"


def cover_letter_text(greeting: str, body: str, name: str | None) -> str:
    return f"{greeting}\n\n{body}\n\nSincerely,\n{name or ''}".strip()
