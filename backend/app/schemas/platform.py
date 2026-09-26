"""LinkedIn / Naukri profile snapshots and profile-change control (spec sections 27-31, 50-51).

Neither platform offers an official API that lets third-party apps edit a member's profile, so
snapshots are entered by the user and every improvement is delivered as a copy-ready change the
user applies themselves. Nothing here logs in to, scrapes or automates either site.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Platform = Literal["linkedin", "naukri", "resume"]
ApprovalStatus = Literal["AUTO_APPROVED", "USER_APPROVAL_REQUIRED", "USER_APPROVED", "USER_REJECTED", "FAILED"]


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class PlatformExperience(_M):
    title: str = Field(default="", max_length=200)
    company: str = Field(default="", max_length=200)
    description: str | None = Field(default=None, max_length=4000)


class OpenToWork(_M):
    enabled: bool = False
    titles: list[str] = []
    locations: list[str] = []
    job_types: list[str] = []


class LinkedInProfile(_M):
    profile_url: str | None = Field(default=None, max_length=300)
    headline: str | None = Field(default=None, max_length=220)  # LinkedIn's limit
    about: str | None = Field(default=None, max_length=2600)  # LinkedIn's limit
    current_title: str | None = Field(default=None, max_length=200)
    skills: list[str] = []
    experience: list[PlatformExperience] = []
    education: list[str] = []
    certifications: list[str] = []
    featured_links: list[str] = []
    open_to_work: OpenToWork = OpenToWork()


class NaukriProfile(_M):
    profile_url: str | None = Field(default=None, max_length=300)
    headline: str | None = Field(default=None, max_length=250)  # Naukri resume headline limit
    summary: str | None = Field(default=None, max_length=1000)  # Naukri profile summary limit
    key_skills: list[str] = []
    current_designation: str | None = Field(default=None, max_length=200)
    current_company: str | None = Field(default=None, max_length=200)
    total_experience_years: float | None = Field(default=None, ge=0, le=60)
    employment: list[PlatformExperience] = []
    education: list[str] = []
    preferred_roles: list[str] = []
    preferred_locations: list[str] = []
    expected_salary: float | None = Field(default=None, ge=0)
    notice_period_days: int | None = Field(default=None, ge=0, le=365)
    resume_updated_on: str | None = Field(default=None, max_length=20)  # YYYY-MM-DD
    profile_updated_on: str | None = Field(default=None, max_length=20)


class ChangeEdit(_M):
    after: str | list[str] = Field(...)


class SkillTrend(BaseModel):
    skill: str
    pct: float
    jobs: int
    candidate_has: bool


class PlatformAnalysis(BaseModel):
    platform: Platform
    completeness: int
    keyword_alignment: int
    missing_fields: list[str]
    skills_to_add: list[str]
    skills_in_demand_you_lack: list[str]
    changes_created: int
