"""Job Analysis Agent: deterministic JD analysis plus optional, verified LLM enrichment."""

import re

from pydantic import BaseModel, Field

from app.agents.llm import get_provider
from app.jobs.jd_parser import analyze_jd
from app.schemas.job import JDAnalysis
from app.services.skills_vocab import canonical

SYSTEM = (
    "You extract structured requirements from job descriptions for a job-search assistant. "
    "Copy wording from the job description; do not add requirements, skills or numbers that the "
    "text does not state. Leave a field empty or null when the description does not say."
)


class LLMJobExtraction(BaseModel):
    required_skills: list[str] = Field(description="Technologies/skills stated as required")
    preferred_skills: list[str] = Field(description="Technologies/skills stated as nice-to-have")
    requirements: list[str] = Field(description="Requirement bullet points, verbatim where possible")
    nice_to_have: list[str] = Field(description="Nice-to-have bullet points, verbatim where possible")
    responsibilities: list[str] = Field(description="Responsibility bullet points")
    experience_min: float | None = Field(description="Minimum years of experience stated, else null")
    experience_max: float | None = Field(description="Maximum years of experience stated, else null")


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9+#]+", " ", s.lower()).strip()


def _in_text(value: str, text_norm: str) -> bool:
    v = _norm(value)
    return bool(v) and v in text_norm


def _grounded_line(line: str, text_norm: str, text_words: set[str]) -> bool:
    """A bullet is kept only if it is (nearly) a quote of the JD."""
    if _in_text(line, text_norm):
        return True
    words = set(_norm(line).split())
    return len(words) >= 3 and len(words & text_words) / len(words) >= 0.9


def verify_extraction(ext: LLMJobExtraction, description: str) -> dict:
    """Drop anything the model returned that is not grounded in the job description."""
    text_norm = _norm(description)
    words = set(text_norm.split())
    nums = {float(n) for n in re.findall(r"\d+(?:\.\d+)?", description)}
    return {
        "required_skills": [canonical(s) for s in ext.required_skills if _in_text(s, text_norm)],
        "preferred_skills": [canonical(s) for s in ext.preferred_skills if _in_text(s, text_norm)],
        "requirements": [x for x in ext.requirements if _grounded_line(x, text_norm, words)],
        "nice_to_have": [x for x in ext.nice_to_have if _grounded_line(x, text_norm, words)],
        "responsibilities": [x for x in ext.responsibilities if _grounded_line(x, text_norm, words)],
        "experience_min": ext.experience_min if ext.experience_min in nums else None,
        "experience_max": ext.experience_max if ext.experience_max in nums else None,
    }


def _merge_unique(a: list[str], b: list[str]) -> list[str]:
    seen = {x.lower() for x in a}
    return a + [x for x in b if x.lower() not in seen and not seen.add(x.lower())]


async def analyze_job(title: str, description: str) -> JDAnalysis:
    jd = analyze_jd(title, description)
    provider = get_provider()
    if provider is None:
        return jd
    ext = await provider.extract(
        system=SYSTEM,
        prompt=f"Job title: {title}\n\n<job_description>\n{description}\n</job_description>",
        schema=LLMJobExtraction,
    )
    if ext is None:
        return jd
    v = verify_extraction(ext, description)
    required = _merge_unique(jd.required_skills, v["required_skills"])
    preferred = [s for s in _merge_unique(jd.preferred_skills, v["preferred_skills"])
                 if s.lower() not in {r.lower() for r in required}]
    return jd.model_copy(update={
        "required_skills": required,
        "preferred_skills": preferred,
        "skills": _merge_unique(jd.skills, required + preferred),
        "requirements": jd.requirements or v["requirements"],
        "nice_to_have": jd.nice_to_have or v["nice_to_have"],
        "responsibilities": jd.responsibilities or v["responsibilities"],
        "experience_min": jd.experience_min if jd.experience_min is not None else v["experience_min"],
        "experience_max": jd.experience_max if jd.experience_max is not None else v["experience_max"],
        "extraction": f"deterministic+{provider.name}",
    })
