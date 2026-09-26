"""Canonical MongoDB collection names (spec section 41)."""

USERS = "users"
REFRESH_TOKENS = "refresh_tokens"
CANDIDATE_PROFILES = "candidate_profiles"

RESUMES = "resumes"
RESUME_VERSIONS = "resume_versions"
RESUME_FILES = "resume_files"
COVER_LETTERS = "cover_letters"

JOB_SOURCES = "job_sources"
JOBS = "jobs"
JOB_MATCHES = "job_matches"

COMPANIES = "companies"
RECRUITERS = "recruiters"
RECRUITER_CONTACTS = "recruiter_contacts"

APPLICATIONS = "applications"
APPLICATION_ANSWERS = "application_answers"
APPLICATION_EVENTS = "application_events"

EMAILS = "emails"
EMAIL_CLASSIFICATIONS = "email_classifications"

INTERVIEWS = "interviews"
INTERVIEW_EVENTS = "interview_events"

LINKEDIN_PROFILES = "linkedin_profiles"
NAUKRI_PROFILES = "naukri_profiles"
PROFILE_CHANGES = "profile_changes"

OUTREACH = "outreach"
FOLLOWUPS = "followups"

AGENT_RUNS = "agent_runs"
AGENT_TASKS = "agent_tasks"

NOTIFICATIONS = "notifications"
AUDIT_LOGS = "audit_logs"

INTEGRATIONS = "integrations"

SCHEDULER_JOBS = "scheduler_jobs"
SYSTEM_SETTINGS = "system_settings"

# Collections holding per-user data keyed by `user_id` (used by data export / account deletion).
USER_SCOPED = [
    CANDIDATE_PROFILES, RESUMES, RESUME_VERSIONS, RESUME_FILES, COVER_LETTERS, JOBS, JOB_MATCHES,
    RECRUITER_CONTACTS, APPLICATIONS, APPLICATION_ANSWERS, APPLICATION_EVENTS, EMAILS,
    EMAIL_CLASSIFICATIONS, INTERVIEWS, INTERVIEW_EVENTS, LINKEDIN_PROFILES, NAUKRI_PROFILES,
    PROFILE_CHANGES, OUTREACH, FOLLOWUPS, AGENT_RUNS, AGENT_TASKS, NOTIFICATIONS, AUDIT_LOGS,
    SCHEDULER_JOBS, SYSTEM_SETTINGS, REFRESH_TOKENS, INTEGRATIONS,
]

# Exported to the user but excluded from the JSON export (binary / security material).
EXPORT_EXCLUDED = {RESUME_FILES, REFRESH_TOKENS, INTEGRATIONS}
