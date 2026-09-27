"""Automation mode + emergency controls (spec sections 55-56).

Every agent/worker added in later phases MUST call `is_allowed()` before acting.
"""

from typing import Literal

from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field, field_validator

from app.database import collections as c
from app.services.audit import log_action
from app.utils import new_id, utcnow

AutomationMode = Literal["conservative", "balanced", "autonomous"]
Capability = Literal["job_discovery", "applications", "emails", "recruiter_outreach",
                     "profile_updates", "gmail_sync"]
CAPABILITIES: tuple[str, ...] = ("job_discovery", "applications", "emails", "recruiter_outreach",
                                 "profile_updates", "gmail_sync")


class Pauses(BaseModel):
    job_discovery: bool = False
    applications: bool = False
    emails: bool = False
    recruiter_outreach: bool = False
    profile_updates: bool = False
    gmail_sync: bool = False


class Schedules(BaseModel):
    timezone: str = "Asia/Kolkata"
    profile_optimization_window: str = "07:00-10:00"
    job_discovery_time: str = "07:00"
    followup_time: str = "09:00"
    analytics_time: str = "23:30"
    gmail_sync_minutes: int = 30


class ProfileSchedule(BaseModel):
    """Daily LinkedIn/Naukri refresh. Saige prepares truthful, copy-ready edits; the user applies them."""
    linkedin_enabled: bool = True
    naukri_enabled: bool = True
    refresh_time: str = Field(default="08:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    days: list[int] = Field(default=[0, 1, 2, 3, 4, 5, 6])  # Monday = 0
    naukri_daily_freshness: bool = True

    @field_validator("days")
    @classmethod
    def _valid_days(cls, v: list[int]) -> list[int]:
        return sorted({d for d in v if 0 <= d <= 6})


class Limits(BaseModel):
    daily_application_limit: int = 20
    daily_email_limit: int = 20
    daily_recruiter_contact_limit: int = 10
    min_match_score: int = 70


class AutoApply(BaseModel):
    """Auto-applier: prepares applications for strong matches every day; the user approves them in one click."""
    enabled: bool = False
    min_score: int = Field(default=80, ge=50, le=100)
    daily_max: int = Field(default=10, ge=1, le=25)
    scopes: list[Literal["country", "remote", "abroad"]] = ["country", "remote"]
    include_walk_in: bool = True
    email_apply: bool = True  # when a posting asks for CVs by email, send the approved application from Gmail


class AutoReply(BaseModel):
    """Draft replies to recruiter emails from the verified profile (the user approves each before it's sent)."""
    enabled: bool = True
    talent_details: bool = True   # CTC, notice period, location, relocation, experience
    resume: bool = True           # attach the resume when asked for a CV
    next_step: bool = True        # confirm the application step / availability for a call
    job_details: bool = True      # ask for the job ID / posting link when missing


class FollowUps(BaseModel):
    enabled: bool = True
    days: list[int] = Field(default=[3, 7, 14], max_length=5)

    @field_validator("days")
    @classmethod
    def _valid(cls, v: list[int]) -> list[int]:
        return sorted({d for d in v if 1 <= d <= 60})[:5] or [3, 7, 14]


class LinkedInPosts(BaseModel):
    """Daily LinkedIn posting agent."""
    enabled: bool = False
    auto_publish: bool = True          # publish automatically when LinkedIn is connected
    time: str = Field(default="10:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    days: list[int] = Field(default=[0, 1, 2, 3, 4])   # Monday = 0
    series: list[str] = ["tip", "mistake", "checklist", "interview", "tool", "learned", "career"]
    topics: list[str] = Field(default=[], max_length=30)  # empty: rotate through your verified skills
    format: Literal["auto", "text", "image", "carousel"] = "auto"
    tone: str = Field(default="friendly and professional", max_length=60)
    hashtags: int = Field(default=5, ge=0, le=10)
    emojis: bool = True
    disclaimer: str = Field(default="", max_length=200)


class OutreachAuto(BaseModel):
    """Outreach mode. manual: every message waits for approval. auto: the user gives standing approval,
    so truth-checked messages within the caps are sent from Gmail automatically."""
    mode: Literal["manual", "auto"] = "manual"
    send_replies: bool = True       # auto-replies to recruiter emails
    send_followups: bool = True     # follow-ups when there's no reply
    cold_email_jobs: bool = False   # email HR contacts published in postings you applied to
    templates: dict[str, str] = {}  # kind -> body with {{firstName}} {{jobTitle}} {{companyName}} {{jobLink}}


class AutomationSettings(BaseModel):
    mode: AutomationMode = "conservative"
    paused_all: bool = False
    pauses: Pauses = Pauses()
    schedules: Schedules = Schedules()
    limits: Limits = Limits()
    profile_schedule: ProfileSchedule = ProfileSchedule()
    auto_apply: AutoApply = AutoApply()
    auto_reply: AutoReply = AutoReply()
    followups: FollowUps = FollowUps()
    blocked_companies: list[str] = Field(default=[], max_length=200)
    linkedin_posts: LinkedInPosts = LinkedInPosts()
    outreach: OutreachAuto = OutreachAuto()


class AutomationSettingsUpdate(BaseModel):
    mode: AutomationMode | None = None
    pauses: Pauses | None = None
    schedules: Schedules | None = None
    limits: Limits | None = None
    profile_schedule: ProfileSchedule | None = None
    auto_apply: AutoApply | None = None
    auto_reply: AutoReply | None = None
    followups: FollowUps | None = None
    blocked_companies: list[str] | None = Field(default=None, max_length=200)
    linkedin_posts: LinkedInPosts | None = None
    outreach: OutreachAuto | None = None


async def get_settings_doc(db: AsyncIOMotorDatabase, user_id: str) -> AutomationSettings:
    doc = await db[c.SYSTEM_SETTINGS].find_one({"user_id": user_id})
    if not doc:
        return AutomationSettings()
    return AutomationSettings.model_validate(doc.get("automation", {}))


async def save(db: AsyncIOMotorDatabase, user_id: str, settings: AutomationSettings,
               action: str, details: dict | None = None) -> AutomationSettings:
    await db[c.SYSTEM_SETTINGS].update_one(
        {"user_id": user_id},
        {"$set": {"automation": settings.model_dump(), "updated_at": utcnow()},
         "$setOnInsert": {"_id": new_id(), "user_id": user_id}},
        upsert=True,
    )
    await log_action(db, user_id=user_id, action=action, entity="automation_settings",
                     details=details or settings.model_dump())
    return settings


def is_blocked(s: AutomationSettings, company: str | None) -> bool:
    """True when the user blocked this company (current employer, companies to avoid)."""
    from app.jobs.dedupe import company_key

    key = company_key(company or "")
    return bool(key) and any(company_key(b) == key for b in s.blocked_companies if b.strip())


async def is_allowed(db: AsyncIOMotorDatabase, user_id: str, capability: Capability) -> bool:
    s = await get_settings_doc(db, user_id)
    return not s.paused_all and not getattr(s.pauses, capability)
