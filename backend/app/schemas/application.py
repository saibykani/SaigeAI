from typing import Literal

from pydantic import BaseModel, Field

ApplicationStatus = Literal[
    "DISCOVERED", "SHORTLISTED", "READY_TO_APPLY", "APPROVAL_REQUIRED", "APPLYING", "APPLIED",
    "APPLICATION_FAILED", "RECRUITER_CONTACTED", "RECRUITER_REPLIED", "SCREENING", "ASSESSMENT",
    "INTERVIEW_SCHEDULED", "INTERVIEW_COMPLETED", "OFFER", "REJECTED", "WITHDRAWN", "CLOSED",
]
Confidence = Literal["HIGH", "MEDIUM", "LOW"]
AnswerStatus = Literal["ANSWERED", "REVIEW_REQUIRED", "USER_PROVIDED"]
InterviewStatus = Literal["upcoming", "completed", "rescheduled", "cancelled"]


class ApplicationCreate(BaseModel):
    job_id: str
    resume_id: str | None = None
    cover_letter_id: str | None = None


class StatusUpdate(BaseModel):
    status: ApplicationStatus
    note: str | None = Field(default=None, max_length=1000)


class QuestionsIn(BaseModel):
    questions: list[str] = Field(min_length=1, max_length=40)


class AnswerEdit(BaseModel):
    answer: str = Field(min_length=1, max_length=2000)


class InterviewIn(BaseModel):
    application_id: str | None = None
    company: str | None = Field(default=None, max_length=200)
    role: str | None = Field(default=None, max_length=200)
    round: str | None = Field(default=None, max_length=100)
    scheduled_at: str = Field(description="ISO 8601 datetime")
    timezone: str = Field(default="Asia/Kolkata", max_length=64)
    duration_minutes: int = Field(default=60, ge=5, le=600)
    meeting_url: str | None = Field(default=None, max_length=500)
    interviewer: str | None = Field(default=None, max_length=200)
    interview_type: str | None = Field(default=None, max_length=60)
    status: InterviewStatus = "upcoming"
    notes: str | None = Field(default=None, max_length=4000)


class InterviewUpdate(BaseModel):
    round: str | None = Field(default=None, max_length=100)
    scheduled_at: str | None = None
    timezone: str | None = Field(default=None, max_length=64)
    meeting_url: str | None = Field(default=None, max_length=500)
    interviewer: str | None = Field(default=None, max_length=200)
    interview_type: str | None = Field(default=None, max_length=60)
    status: InterviewStatus | None = None
    notes: str | None = Field(default=None, max_length=4000)
