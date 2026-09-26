"""Recruiter contacts and outreach (spec sections 24-26).

Contacts come only from the user: manual entry, CSV import, senders of imported recruiter email,
or a job posting's contact. Saige never scrapes profiles or guesses email addresses.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

ContactRole = Literal["recruiter", "hiring_manager", "referral", "alumni", "other"]
ContactSource = Literal["manual", "csv", "gmail", "job"]
OutreachKind = Literal["referral", "cold", "hiring_manager", "employee_intro", "linkedin_note", "followup", "thank_you"]
OutreachStatus = Literal["draft", "approved", "sent", "replied", "bounced", "no_response", "unsubscribed", "cancelled"]


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ContactIn(_M):
    name: str = Field(..., min_length=1, max_length=120)
    company: str = Field(..., min_length=1, max_length=160)
    email: EmailStr | None = None
    linkedin_url: str | None = Field(default=None, max_length=300)
    title: str | None = Field(default=None, max_length=160)
    role: ContactRole = "recruiter"
    tags: list[str] = Field(default=[], max_length=20)
    notes: str | None = Field(default=None, max_length=2000)
    source: ContactSource = "manual"

    @field_validator("linkedin_url")
    @classmethod
    def _linkedin(cls, v: str | None) -> str | None:
        if v and not v.startswith(("https://", "http://")):
            v = f"https://{v}"
        return v or None


class ContactUpdate(_M):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    company: str | None = Field(default=None, min_length=1, max_length=160)
    email: EmailStr | None = None
    linkedin_url: str | None = Field(default=None, max_length=300)
    title: str | None = Field(default=None, max_length=160)
    role: ContactRole | None = None
    tags: list[str] | None = None
    notes: str | None = Field(default=None, max_length=2000)


class CsvImport(_M):
    csv: str = Field(..., min_length=1, max_length=500_000)


class DraftIn(_M):
    contact_id: str
    kind: OutreachKind = "referral"
    job_id: str | None = None
    parent_id: str | None = None  # the earlier message a follow-up refers to
    context: str | None = Field(default=None, max_length=600)  # e.g. "We worked together at Acme"


class OutreachEdit(_M):
    subject: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=1, max_length=5000)
