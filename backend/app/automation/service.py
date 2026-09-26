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


class AutomationSettings(BaseModel):
    mode: AutomationMode = "conservative"
    paused_all: bool = False
    pauses: Pauses = Pauses()
    schedules: Schedules = Schedules()
    limits: Limits = Limits()
    profile_schedule: ProfileSchedule = ProfileSchedule()


class AutomationSettingsUpdate(BaseModel):
    mode: AutomationMode | None = None
    pauses: Pauses | None = None
    schedules: Schedules | None = None
    limits: Limits | None = None
    profile_schedule: ProfileSchedule | None = None


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


async def is_allowed(db: AsyncIOMotorDatabase, user_id: str, capability: Capability) -> bool:
    s = await get_settings_doc(db, user_id)
    return not s.paused_all and not getattr(s.pauses, capability)
