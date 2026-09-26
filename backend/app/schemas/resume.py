from typing import Literal

from pydantic import BaseModel, Field

ResumeStatus = Literal["active", "archived"]


class ParsedExperience(BaseModel):
    company: str | None = None
    title: str | None = None
    location: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    is_current: bool = False
    responsibilities: list[str] = []
    achievements: list[str] = []
    technologies: list[str] = []


class ParsedEducation(BaseModel):
    degree: str | None = None
    institution: str | None = None
    field: str | None = None
    start_year: int | None = None
    end_year: int | None = None
    raw: str = ""


class ParsedProject(BaseModel):
    name: str
    highlights: list[str] = []
    technologies: list[str] = []


class ParsedLinks(BaseModel):
    linkedin: str | None = None
    github: str | None = None
    portfolio: str | None = None
    other: list[str] = []


class ParsedResume(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    links: ParsedLinks = ParsedLinks()
    summary: str | None = None
    skills: list[str] = []
    tools: list[str] = []
    experience: list[ParsedExperience] = []
    projects: list[ParsedProject] = []
    education: list[ParsedEducation] = []
    certifications: list[str] = []
    achievements: list[str] = []
    sections_found: list[str] = []
    warnings: list[str] = []


class ResumeOut(BaseModel):
    id: str
    name: str
    kind: str
    status: ResumeStatus
    filename: str | None
    content_type: str | None
    size: int | None
    current_version_id: str | None
    version_count: int
    created_at: str
    updated_at: str


class ResumeVersionOut(BaseModel):
    id: str
    resume_id: str
    version: int
    base_resume_id: str | None
    job_id: str | None
    source: str
    changes: list[str]
    parsed: ParsedResume
    raw_text: str
    created_at: str


class ResumeDetail(ResumeOut):
    current_version: ResumeVersionOut | None


class ResumeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    kind: str | None = Field(default=None, min_length=1, max_length=60)
    parsed: ParsedResume | None = None
    change_note: str | None = Field(default=None, max_length=300)


class ResumeCompare(BaseModel):
    a_version_id: str
    b_version_id: str
    skills_added: list[str]
    skills_removed: list[str]
    summary_changed: bool
    experience_count: tuple[int, int]
    projects_count: tuple[int, int]
    certifications_added: list[str]
    certifications_removed: list[str]


class ImportResult(BaseModel):
    applied: list[str]
    skipped: list[str]
    completeness: int
