"""Master candidate profile + verified professional knowledge base (spec sections 6-7).

Missing information is stored as `None` / empty and surfaced to the user as UNKNOWN - it is
never guessed.
"""

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl

Str = str  # alias for readability in list fields
ShortText = Field(default=None, max_length=300)


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class PersonalInfo(_Model):
    name: str | None = ShortText
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    current_location: str | None = ShortText
    country: str | None = ShortText
    current_company: str | None = ShortText
    current_designation: str | None = ShortText
    total_experience_years: float | None = Field(default=None, ge=0, le=60)
    current_ctc: float | None = Field(default=None, ge=0)
    expected_ctc: float | None = Field(default=None, ge=0)
    ctc_currency: str | None = Field(default=None, max_length=8)
    notice_period_days: int | None = Field(default=None, ge=0, le=365)
    availability: str | None = ShortText
    linkedin_url: HttpUrl | None = None
    naukri_url: HttpUrl | None = None
    github_url: HttpUrl | None = None
    portfolio_url: HttpUrl | None = None


class Skills(_Model):
    primary: list[Str] = []
    secondary: list[Str] = []
    tools: list[Str] = []
    frameworks: list[Str] = []
    programming_languages: list[Str] = []
    testing_tools: list[Str] = []
    cloud: list[Str] = []
    databases: list[Str] = []
    ci_cd: list[Str] = []
    performance_testing: list[Str] = []
    api_testing: list[Str] = []
    automation: list[Str] = []
    manual_testing: list[Str] = []

    def all(self) -> list[str]:
        seen: dict[str, str] = {}
        for values in self.model_dump().values():
            for v in values:
                seen.setdefault(v.lower(), v)
        return list(seen.values())


class Preferences(_Model):
    target_roles: list[Str] = []
    target_industries: list[Str] = []
    target_companies: list[Str] = []
    excluded_companies: list[Str] = []
    preferred_locations: list[Str] = []
    excluded_locations: list[Str] = []
    remote_preference: bool | None = None
    hybrid_preference: bool | None = None
    relocation: bool | None = None
    min_salary: float | None = Field(default=None, ge=0)
    max_salary: float | None = Field(default=None, ge=0)
    salary_currency: str | None = Field(default=None, max_length=8)
    employment_types: list[Str] = []
    visa_requirement: str | None = ShortText
    timezone: str = "Asia/Kolkata"


class Experience(_Model):
    company: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=200)
    location: str | None = ShortText
    start_date: str | None = Field(default=None, max_length=20)
    end_date: str | None = Field(default=None, max_length=20)
    is_current: bool = False
    domain: str | None = ShortText
    responsibilities: list[Str] = []
    achievements: list[Str] = []
    technologies: list[Str] = []


class Project(_Model):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    role: str | None = ShortText
    technologies: list[Str] = []
    highlights: list[Str] = []
    url: HttpUrl | None = None


class Education(_Model):
    institution: str | None = ShortText
    degree: str = Field(min_length=1, max_length=200)
    field: str | None = ShortText
    start_year: int | None = Field(default=None, ge=1950, le=2100)
    end_year: int | None = Field(default=None, ge=1950, le=2100)
    grade: str | None = Field(default=None, max_length=40)


class Certification(_Model):
    name: str = Field(min_length=1, max_length=200)
    issuer: str | None = ShortText
    issued: str | None = Field(default=None, max_length=20)
    expires: str | None = Field(default=None, max_length=20)
    credential_url: HttpUrl | None = None


class KnowledgeBase(_Model):
    professional_summary: str | None = Field(default=None, max_length=4000)
    domains: list[Str] = []
    experience: list[Experience] = []
    projects: list[Project] = []
    education: list[Education] = []
    certifications: list[Certification] = []


class ProfileUpdate(_Model):
    """Partial update - only supplied sections are replaced."""

    personal: PersonalInfo | None = None
    skills: Skills | None = None
    preferences: Preferences | None = None
    knowledge: KnowledgeBase | None = None


class Profile(_Model):
    personal: PersonalInfo = PersonalInfo()
    skills: Skills = Skills()
    preferences: Preferences = Preferences()
    knowledge: KnowledgeBase = KnowledgeBase()


class ProfileOut(Profile):
    model_config = ConfigDict(extra="ignore")

    completeness: int
    unknown_fields: list[str]
    updated_at: str | None = None
