"""Truthfulness guard (spec sections 7, 44, 58).

Every AI-generated artefact (tailored resume, cover letter, application answer, profile
suggestion) must pass `validate_claims` against the verified candidate knowledge base before it
can be saved or sent. Anything that cannot be traced back to the knowledge base produces
VALIDATION FAILED and the action is blocked.
"""

import re
from typing import Literal

from pydantic import BaseModel

from app.schemas.profile import Profile
from app.services.skills_vocab import canonical, find_skills, normalize_key

ViolationType = Literal[
    "skill", "company", "title", "certification", "project", "education", "experience",
    "salary", "metric",
]

_COMPANY_SUFFIXES = {
    "inc", "ltd", "llc", "pvt", "private", "limited", "corp", "corporation", "co", "plc", "gmbh",
}


class GeneratedClaims(BaseModel):
    """Structured claims an AI generator must declare alongside its free text."""

    text: str = ""
    skills: list[str] = []
    companies: list[str] = []
    titles: list[str] = []
    certifications: list[str] = []
    projects: list[str] = []
    education: list[str] = []
    experience_years: float | None = None
    salary: float | None = None


class Violation(BaseModel):
    type: ViolationType
    value: str
    reason: str


class ValidationResult(BaseModel):
    status: Literal["PASSED", "VALIDATION FAILED"]
    violations: list[Violation]

    @property
    def passed(self) -> bool:
        return self.status == "PASSED"


def _company_key(name: str) -> str:
    words = re.sub(r"[^a-z0-9 ]", " ", name.lower()).split()
    return " ".join(w for w in words if w not in _COMPANY_SUFFIXES)


def _plain_key(value: str) -> str:
    return re.sub(r"[^a-z0-9+#]", "", value.lower())


class FactIndex:
    def __init__(self, profile: Profile) -> None:
        kb = profile.knowledge
        p = profile.personal

        skills = list(profile.skills.all())
        for exp in kb.experience:
            skills += exp.technologies
        for proj in kb.projects:
            skills += proj.technologies
        self.skills = {normalize_key(canonical(s)) for s in skills}

        self.companies = {_company_key(e.company) for e in kb.experience}
        if p.current_company:
            self.companies.add(_company_key(p.current_company))

        self.titles = {_plain_key(e.title) for e in kb.experience}
        if p.current_designation:
            self.titles.add(_plain_key(p.current_designation))

        self.certifications = {_plain_key(cert.name) for cert in kb.certifications}
        self.projects = {_plain_key(proj.name) for proj in kb.projects}
        self.education = {_plain_key(e.degree) for e in kb.education} | {
            _plain_key(e.institution) for e in kb.education if e.institution
        }
        self.experience_years = p.total_experience_years
        self.salaries = {v for v in (p.current_ctc, p.expected_ctc) if v is not None}

        corpus_parts: list[str] = [kb.professional_summary or ""]
        for exp in kb.experience:
            corpus_parts += exp.responsibilities + exp.achievements
        for proj in kb.projects:
            corpus_parts += [proj.description or ""] + proj.highlights
        self.corpus = _squash(" ".join(corpus_parts))


def _squash(text: str) -> str:
    return re.sub(r"\s+", "", text.lower())


_METRIC_RE = re.compile(
    r"(?:[$₹€£]\s?\d[\d,]*(?:\.\d+)?\s?[kmb]?)|(?:\d[\d,]*(?:\.\d+)?\s?(?:%|x\b|\+(?!\s*years?)))",
    re.IGNORECASE,
)
_YEARS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)\b", re.IGNORECASE)


def validate_claims(claims: GeneratedClaims, profile: Profile) -> ValidationResult:
    facts = FactIndex(profile)
    violations: list[Violation] = []

    def add(t: ViolationType, value: str, reason: str) -> None:
        if not any(v.type == t and v.value.lower() == value.lower() for v in violations):
            violations.append(Violation(type=t, value=value, reason=reason))

    # Declared structured claims
    for s in claims.skills:
        if normalize_key(canonical(s)) not in facts.skills:
            add("skill", s, "Skill is not in the candidate knowledge base")
    for s in find_skills(claims.text):
        if normalize_key(s) not in facts.skills:
            add("skill", s, "Text mentions a skill the candidate has not verified")
    for comp in claims.companies:
        if _company_key(comp) not in facts.companies:
            add("company", comp, "Company does not appear in verified employment history")
    for title in claims.titles:
        if _plain_key(title) not in facts.titles:
            add("title", title, "Job title does not appear in verified employment history")
    for cert in claims.certifications:
        if _plain_key(cert) not in facts.certifications:
            add("certification", cert, "Certification is not in the knowledge base")
    for proj in claims.projects:
        if _plain_key(proj) not in facts.projects:
            add("project", proj, "Project is not in the knowledge base")
    for edu in claims.education:
        if _plain_key(edu) not in facts.education:
            add("education", edu, "Qualification is not in the knowledge base")

    # Experience duration (declared or stated in text)
    stated_years = [claims.experience_years] if claims.experience_years is not None else []
    stated_years += [float(m) for m in _YEARS_RE.findall(claims.text)]
    for yrs in stated_years:
        if facts.experience_years is None:
            add("experience", f"{yrs:g} years", "Total experience is UNKNOWN in the profile")
        elif yrs > facts.experience_years + 0.5:
            add("experience", f"{yrs:g} years",
                f"Exceeds verified total experience of {facts.experience_years:g} years")

    if claims.salary is not None and claims.salary not in facts.salaries:
        add("salary", f"{claims.salary:g}", "Salary does not match current or expected CTC")

    # Quantified achievements must be traceable verbatim to the knowledge base.
    for m in _METRIC_RE.findall(claims.text):
        if _squash(m) not in facts.corpus:
            add("metric", m.strip(), "Metric not found in any verified achievement")

    return ValidationResult(status="VALIDATION FAILED" if violations else "PASSED",
                            violations=violations)
