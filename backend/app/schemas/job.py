"""Job schemas: import payloads, normalized job (spec section 13), JD analysis, match result."""

from typing import Literal

from pydantic import BaseModel, Field, HttpUrl

JobStatus = Literal["new", "saved", "shortlisted", "archived", "rejected"]
Classification = Literal["Highly Relevant", "Relevant", "Potential Match", "Low Match", "Not Relevant"]
AtsProvider = Literal["greenhouse", "lever", "ashby"]


class JobIn(BaseModel):
    """A job supplied by the user (pasted JD) or produced by a permitted ATS integration."""

    title: str = Field(min_length=2, max_length=200)
    company: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=30, max_length=60000)
    location: str | None = Field(default=None, max_length=200)
    remote: bool | None = None
    employment_type: str | None = Field(default=None, max_length=40)
    salary_min: float | None = Field(default=None, ge=0)
    salary_max: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, max_length=8)
    application_url: HttpUrl | None = None
    source: str = Field(default="manual", max_length=40)
    source_job_id: str | None = Field(default=None, max_length=200)
    posted_date: str | None = Field(default=None, max_length=40)
    deadline: str | None = Field(default=None, max_length=40)


class ImportUrlIn(BaseModel):
    url: HttpUrl


class JobSourceIn(BaseModel):
    provider: AtsProvider
    # Public board identifier, e.g. greenhouse "stripe", lever "netflix", ashby "notion".
    board: str = Field(pattern=r"^[A-Za-z0-9_.-]{1,80}$")
    company_name: str | None = Field(default=None, max_length=200)


class JobStatusIn(BaseModel):
    status: JobStatus


class JDAnalysis(BaseModel):
    skills: list[str] = []
    required_skills: list[str] = []
    preferred_skills: list[str] = []
    requirements: list[str] = []
    nice_to_have: list[str] = []
    responsibilities: list[str] = []
    experience_min: float | None = None
    experience_max: float | None = None
    experience_text: str | None = None
    seniority: str | None = None
    remote: bool | None = None
    hybrid: bool | None = None
    employment_type: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    currency: str | None = None
    education: list[str] = []
    domains: list[str] = []
    notice_period_max_days: int | None = None
    no_visa_sponsorship: bool = False
    extraction: str = "deterministic"


class MatchBreakdown(BaseModel):
    skills: float | None = None
    experience: float | None = None
    role: float | None = None
    domain: float | None = None
    location: float | None = None
    salary: float | None = None
    notice_period: float | None = None
    education: float | None = None
    work_authorization: float | None = None


class MatchResult(BaseModel):
    overall: int
    classification: Classification
    breakdown: MatchBreakdown
    matched_skills: list[str]
    missing_required_skills: list[str]
    missing_preferred_skills: list[str]
    experience_gap: str | None
    issues: list[str]
    weights: dict[str, float]
    computed_at: str


class MatchWeights(BaseModel):
    skills: float = Field(default=35, ge=0, le=100)
    experience: float = Field(default=20, ge=0, le=100)
    role: float = Field(default=15, ge=0, le=100)
    domain: float = Field(default=5, ge=0, le=100)
    location: float = Field(default=10, ge=0, le=100)
    salary: float = Field(default=10, ge=0, le=100)
    notice_period: float = Field(default=5, ge=0, le=100)
    education: float = Field(default=5, ge=0, le=100)
    work_authorization: float = Field(default=5, ge=0, le=100)
