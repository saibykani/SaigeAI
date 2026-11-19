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
EMAIL_TEMPLATES = "email_templates"  # the user's own recruiter email templates

APPLICATIONS = "applications"
APPLICATION_ANSWERS = "application_answers"
APPLICATION_EVENTS = "application_events"

EMAILS = "emails"
SENT_EMAILS = "sent_emails"
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
GOALS = "goals"
SAVED_OFFERS = "saved_offers"
CALENDAR_FEEDS = "calendar_feeds"
PORTFOLIOS = "portfolios"

INTEGRATIONS = "integrations"
API_TOKENS = "api_tokens"

JOB_FEED = "job_feed"
FEED_HIDDEN = "feed_hidden"  # jobs the user swiped away in the mobile feed: {_id: uid:item_id, user_id, item_id, title, company, at}
JOB_ALERTS = "job_alerts"
PORTAL_LINKS = "portal_links"
LINKEDIN_POSTS = "linkedin_posts"
CAREER_JOBS = "career_jobs"
CAREER_SCANS = "career_scans"
ML_MODELS = "ml_models"
ML_SAMPLES = "ml_samples"
ML_RUNS = "ml_runs"

MOCK_INTERVIEWS = "mock_interviews"
DEBRIEFS = "debriefs"
QUESTION_BANK = "question_bank"
LEARNING_PATHS = "learning_paths"
WHATSAPP_SESSIONS = "whatsapp_sessions"
PUSH_SUBSCRIPTIONS = "push_subscriptions"

# Recruiter side: jobs a recruiter posts and interest requests sent to opted-in candidates.
RECRUITER_JOBS = "recruiter_jobs"
TALENT_REQUESTS = "talent_requests"

SCHEDULER_JOBS = "scheduler_jobs"
SYSTEM_SETTINGS = "system_settings"
ADMIN_NOTES = "admin_notes"  # super-admin-only notes about a user (user_id = the subject; never exported to the user)
USER_TAGS = "user_tags"  # one doc per user: {_id: user_id, user_id, tags: [...]}; super-admin only
ANNOUNCEMENTS = "announcements"  # super-admin broadcasts shown to every user (not user-scoped)

# Collections holding per-user data keyed by `user_id` (used by data export / account deletion).
USER_SCOPED = [
    CANDIDATE_PROFILES, RESUMES, RESUME_VERSIONS, RESUME_FILES, COVER_LETTERS, JOBS, JOB_MATCHES,
    RECRUITER_CONTACTS, APPLICATIONS, APPLICATION_ANSWERS, APPLICATION_EVENTS, EMAILS, SENT_EMAILS,
    EMAIL_CLASSIFICATIONS, INTERVIEWS, INTERVIEW_EVENTS, LINKEDIN_PROFILES, NAUKRI_PROFILES,
    PROFILE_CHANGES, OUTREACH, FOLLOWUPS, AGENT_RUNS, AGENT_TASKS, NOTIFICATIONS, AUDIT_LOGS,
    SCHEDULER_JOBS, SYSTEM_SETTINGS, REFRESH_TOKENS, INTEGRATIONS, API_TOKENS,
    JOB_FEED, JOB_ALERTS, PORTAL_LINKS, LINKEDIN_POSTS, CAREER_JOBS, CAREER_SCANS, ML_MODELS, ML_SAMPLES, ML_RUNS, GOALS, SAVED_OFFERS,
    CALENDAR_FEEDS, PORTFOLIOS,
    MOCK_INTERVIEWS, LEARNING_PATHS, WHATSAPP_SESSIONS, PUSH_SUBSCRIPTIONS,
    RECRUITER_JOBS, TALENT_REQUESTS, DEBRIEFS, QUESTION_BANK, EMAIL_TEMPLATES, ADMIN_NOTES, USER_TAGS, FEED_HIDDEN,
]

# Exported to the user but excluded from the JSON export (binary / security material).
EXPORT_EXCLUDED = {RESUME_FILES, REFRESH_TOKENS, INTEGRATIONS, API_TOKENS, JOB_FEED, CAREER_JOBS, PUSH_SUBSCRIPTIONS, ADMIN_NOTES, USER_TAGS}
