export interface User {
  id: string;
  email: string;
  name: string;
  roles: string[];
  auth_providers: string[];
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface PersonalInfo {
  name: string | null;
  email: string | null;
  phone: string | null;
  current_location: string | null;
  country: string | null;
  current_company: string | null;
  current_designation: string | null;
  total_experience_years: number | null;
  current_ctc: number | null;
  expected_ctc: number | null;
  ctc_currency: string | null;
  notice_period_days: number | null;
  availability: string | null;
  linkedin_url: string | null;
  naukri_url: string | null;
  github_url: string | null;
  portfolio_url: string | null;
}

export const SKILL_CATEGORIES = [
  ["primary", "Primary Skills"],
  ["secondary", "Secondary Skills"],
  ["programming_languages", "Programming Languages"],
  ["automation", "Automation"],
  ["frameworks", "Frameworks"],
  ["api_testing", "API Testing"],
  ["performance_testing", "Performance Testing"],
  ["manual_testing", "Manual Testing"],
  ["testing_tools", "Testing Tools"],
  ["tools", "Tools"],
  ["ci_cd", "CI/CD"],
  ["cloud", "Cloud"],
  ["databases", "Databases"],
] as const;

export type SkillCategory = (typeof SKILL_CATEGORIES)[number][0];
export type Skills = Record<SkillCategory, string[]>;

export interface Preferences {
  target_roles: string[];
  target_industries: string[];
  target_companies: string[];
  excluded_companies: string[];
  preferred_locations: string[];
  excluded_locations: string[];
  remote_preference: boolean | null;
  hybrid_preference: boolean | null;
  relocation: boolean | null;
  min_salary: number | null;
  max_salary: number | null;
  salary_currency: string | null;
  employment_types: string[];
  visa_requirement: string | null;
  timezone: string;
}

export interface Experience {
  company: string;
  title: string;
  location: string | null;
  start_date: string | null;
  end_date: string | null;
  is_current: boolean;
  domain: string | null;
  responsibilities: string[];
  achievements: string[];
  technologies: string[];
}

export interface Project {
  name: string;
  description: string | null;
  role: string | null;
  technologies: string[];
  highlights: string[];
  url: string | null;
}

export interface Education {
  institution: string | null;
  degree: string;
  field: string | null;
  start_year: number | null;
  end_year: number | null;
  grade: string | null;
}

export interface Certification {
  name: string;
  issuer: string | null;
  issued: string | null;
  expires: string | null;
  credential_url: string | null;
}

export interface KnowledgeBase {
  professional_summary: string | null;
  domains: string[];
  experience: Experience[];
  projects: Project[];
  education: Education[];
  certifications: Certification[];
}

export interface Profile {
  personal: PersonalInfo;
  skills: Skills;
  preferences: Preferences;
  knowledge: KnowledgeBase;
  completeness: number;
  unknown_fields: string[];
  updated_at: string | null;
}

export interface ParsedExperience {
  company: string | null;
  title: string | null;
  location: string | null;
  start_date: string | null;
  end_date: string | null;
  is_current: boolean;
  responsibilities: string[];
  achievements: string[];
  technologies: string[];
}

export interface ParsedResume {
  name: string | null;
  email: string | null;
  phone: string | null;
  location: string | null;
  links: { linkedin: string | null; github: string | null; portfolio: string | null; other: string[] };
  summary: string | null;
  skills: string[];
  tools: string[];
  experience: ParsedExperience[];
  projects: { name: string; highlights: string[]; technologies: string[] }[];
  education: {
    degree: string | null;
    institution: string | null;
    field: string | null;
    start_year: number | null;
    end_year: number | null;
    raw: string;
  }[];
  certifications: string[];
  achievements: string[];
  sections_found: string[];
  warnings: string[];
}

export interface Resume {
  id: string;
  name: string;
  kind: string;
  status: "active" | "archived";
  filename: string | null;
  content_type: string | null;
  size: number | null;
  current_version_id: string | null;
  version_count: number;
  job_id?: string | null;
  base_resume_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ResumeVersion {
  id: string;
  resume_id: string;
  version: number;
  base_resume_id: string | null;
  job_id: string | null;
  source: string;
  changes: string[];
  parsed: ParsedResume;
  raw_text: string;
  created_at: string;
}

export interface ResumeDetail extends Resume {
  current_version: ResumeVersion | null;
}

export interface ResumeCompare {
  a_version_id: string;
  b_version_id: string;
  skills_added: string[];
  skills_removed: string[];
  summary_changed: boolean;
  experience_count: [number, number];
  projects_count: [number, number];
  certifications_added: string[];
  certifications_removed: string[];
}

export interface ImportResult {
  applied: string[];
  skipped: string[];
  completeness: number;
}

export interface Dashboard {
  today: Record<
    | "jobs_found"
    | "relevant_jobs"
    | "applications_ready"
    | "applications_submitted"
    | "recruiters_contacted"
    | "replies"
    | "interviews"
    | "rejections"
    | "offers",
    number
  >;
  totals: { jobs: number; applications: number; interviews: number; resumes: number };
  high_match_jobs: { id: string; title: string; company: string; score: number }[];
  action_required: {
    applications_need_approval: number;
    followups_due: number;
    upcoming_interviews: number;
    profile_changes_pending: number;
    unknown_profile_fields: number;
  };
  funnel: { stage: string; count: number }[];
  profile: { completeness: number; unknown_fields: string[] };
  automation: { mode: AutomationMode; paused_all: boolean };
  trend: Record<"jobs_found" | "relevant_jobs" | "applications_submitted" | "interviews" | "documents" | "profile_changes", number[]>;
  health: {
    active_applications: number;
    response_rate: number | null;
    interview_rate: number | null;
    offer_rate: number | null;
    avg_match: number | null;
    avg_ats: number | null;
    followups_due: number;
    tailored_resumes: number;
    cover_letters: number;
  };
  upcoming_interviews: { id: string; company: string | null; role: string | null; round: string | null; scheduled_at: string; meeting_url: string | null }[];
  activity: { id: string; label: string; action: string; at: string }[];
  skills_in_demand: { skill: string; pct: number; jobs: number; candidate_has: boolean }[];
}

export type AutomationMode = "conservative" | "balanced" | "autonomous";

export const CAPABILITIES = [
  ["job_discovery", "Job Discovery"],
  ["applications", "Applications"],
  ["emails", "Emails"],
  ["recruiter_outreach", "Recruiter Outreach"],
  ["profile_updates", "Profile Updates"],
  ["gmail_sync", "Gmail Sync"],
] as const;

export type Capability = (typeof CAPABILITIES)[number][0];

export interface ProfileSchedule {
  linkedin_enabled: boolean;
  naukri_enabled: boolean;
  refresh_time: string;
  days: number[];
  naukri_daily_freshness: boolean;
}

export interface SchedulerJobRun {
  id: string;
  job: string;
  label: string;
  run_date: string;
  trigger: "cron" | "manual";
  status: "running" | "succeeded" | "failed" | "skipped";
  result: Record<string, unknown>;
  applied?: number;
  waiting?: number;
  started_at: string | null;
  finished_at: string | null;
}

export interface SchedulerStatus {
  timezone: string;
  paused_all: boolean;
  profile_schedule: ProfileSchedule;
  jobs: {
    job: string;
    label: string;
    next_run: string | null;
    last_run: SchedulerJobRun | null;
  }[];
  naukri_streak: number;
}

export interface AutomationSettings {
  mode: AutomationMode;
  paused_all: boolean;
  pauses: Record<Capability, boolean>;
  schedules: {
    timezone: string;
    profile_optimization_window: string;
    job_discovery_time: string;
    followup_time: string;
    analytics_time: string;
    gmail_sync_minutes: number;
  };
  profile_schedule: ProfileSchedule;
  limits: {
    daily_application_limit: number;
    daily_email_limit: number;
    daily_recruiter_contact_limit: number;
    min_match_score: number;
  };
  auto_apply: AutoApplySettings;
  auto_reply: { enabled: boolean; talent_details: boolean; resume: boolean; next_step: boolean; job_details: boolean };
  followups: { enabled: boolean; days: number[] };
  blocked_companies: string[];
  outreach: { mode: "manual" | "auto"; send_replies: boolean; send_followups: boolean; cold_email_jobs: boolean; templates: Record<string, string> };
}

export interface AutoApplySettings {
  enabled: boolean;
  min_score: number;
  daily_max: number;
  scopes: JobScope[];
  include_walk_in: boolean;
  email_apply: boolean;
}

export interface ConnectedAccount {
  provider: string;
  connected: boolean;
  scopes: string[];
  status: string;
}

export interface AppNotification {
  id: string;
  kind: string;
  title: string;
  body: string;
  link: string | null;
  details?: { platform: string; field: string; before: string; after: string }[];
  read: boolean;
  created_at: string;
}

export const RESUME_KINDS = [
  "Master Resume",
  "SDET Resume",
  "QA Automation Resume",
  "Performance Testing Resume",
  "API Testing Resume",
  "Java Automation Resume",
  "Other",
];

export type JobStatus = "new" | "saved" | "shortlisted" | "archived" | "rejected";

export interface JobSummary {
  id: string;
  title: string;
  company: string;
  location: string | null;
  country: string | null;
  remote: boolean | null;
  source: string;
  sources: string[];
  salary_min: number | null;
  salary_max: number | null;
  currency: string | null;
  experience_required: string | null;
  status: JobStatus;
  score: number | null;
  classification: string | null;
  posted_date: string | null;
  created_at: string;
}

export interface MatchResult {
  overall: number;
  classification: string;
  breakdown: Record<string, number | null>;
  matched_skills: string[];
  missing_required_skills: string[];
  missing_preferred_skills: string[];
  experience_gap: string | null;
  issues: string[];
  weights: Record<string, number>;
  computed_at: string;
}

export interface JDAnalysis {
  skills: string[];
  required_skills: string[];
  preferred_skills: string[];
  requirements: string[];
  nice_to_have: string[];
  responsibilities: string[];
  experience_min: number | null;
  experience_max: number | null;
  seniority: string | null;
  employment_type: string | null;
  domains: string[];
  education: string[];
  notice_period_max_days: number | null;
  no_visa_sponsorship: boolean;
  extraction: string;
}

export interface JobDetail extends JobSummary {
  employment_type: string | null;
  description: string;
  requirements: string[];
  nice_to_have: string[];
  skills: string[];
  application_url: string | null;
  deadline: string | null;
  source_refs: { source: string; source_job_id: string | null; url: string | null; first_seen: string }[];
  analysis: JDAnalysis;
  match: MatchResult | null;
  updated_at: string;
  recommended_resume?: { id: string; name: string; kind: string; overlap: number; of: number } | null;
}

export interface JobSource {
  id: string;
  provider: "greenhouse" | "lever" | "ashby";
  board: string;
  company_name: string | null;
  last_synced_at: string | null;
  last_result: Record<string, number | string> | null;
}

export type MatchWeights = Record<
  "skills" | "experience" | "role" | "domain" | "location" | "salary" | "notice_period" | "education" | "work_authorization",
  number
>;

// ---------------- Phase 7: profile sync
export type SyncPlatform = "linkedin" | "naukri" | "resume";
export type ApprovalStatus = "AUTO_APPROVED" | "USER_APPROVAL_REQUIRED" | "USER_APPROVED" | "USER_REJECTED" | "FAILED";

export interface SkillTrend {
  skill: string;
  pct: number;
  jobs: number;
  candidate_has: boolean;
}

export interface ProfileChange {
  id: string;
  platform: SyncPlatform;
  field: string;
  before: string | string[] | number | null;
  after: string | string[] | number | null;
  reason: string;
  source_jobs: string[];
  ai_confidence: number;
  approval_status: ApprovalStatus;
  action: string;
  validation: { status: string; violations: { type: string; value: string; reason: string }[] };
  applied_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ConsistencyCheck {
  field: string;
  master: string | number;
  values: Record<string, string | number>;
  consistent: boolean;
  mismatched: string[];
}

export interface PlatformSummary {
  completeness: number;
  missing_fields: string[];
  keyword_alignment: number;
  skills_to_add: string[];
  pending_changes: number;
}

export interface SyncOverview {
  jobs_analyzed: number;
  trends: SkillTrend[];
  linkedin: PlatformSummary;
  naukri: PlatformSummary;
  resume: { pending_changes: number };
  consistency: { score: number | null; checks: ConsistencyCheck[]; discrepancies: ConsistencyCheck[] };
  last_run: string | null;
}

export interface LinkedInSnapshot {
  profile_url: string | null;
  headline: string | null;
  about: string | null;
  current_title: string | null;
  skills: string[];
  experience: { title: string; company: string; description: string | null }[];
  education: string[];
  certifications: string[];
  featured_links: string[];
  open_to_work: { enabled: boolean; titles: string[]; locations: string[]; job_types: string[] };
}

export interface NaukriSnapshot {
  profile_url: string | null;
  headline: string | null;
  summary: string | null;
  key_skills: string[];
  current_designation: string | null;
  current_company: string | null;
  total_experience_years: number | null;
  employment: { title: string; company: string; description: string | null }[];
  education: string[];
  preferred_roles: string[];
  preferred_locations: string[];
  expected_salary: number | null;
  notice_period_days: number | null;
  resume_updated_on: string | null;
  profile_updated_on: string | null;
}

// ---------------- Phase 3: resume AI
export interface AtsReport {
  score: number;
  required_coverage: number;
  preferred_coverage: number;
  matched_keywords: string[];
  missing_required: string[];
  missing_preferred: string[];
  checks: { check: string; passed: boolean }[];
  word_count: number;
}

export interface CoverLetter {
  id: string;
  job_id: string;
  resume_id: string | null;
  text: string;
  validation: { status: string; violations: { type: string; value: string; reason: string }[] } | null;
  engine: string | null;
  created_at: string;
  updated_at: string;
}

export interface JobDocuments {
  resumes: (Resume & { ats: AtsReport | null; engine: string | null })[];
  cover_letters: CoverLetter[];
}

// ---------------- Phase 4: applications & interviews
export type ApplicationStatus =
  | "DISCOVERED" | "SHORTLISTED" | "READY_TO_APPLY" | "APPROVAL_REQUIRED" | "APPLYING" | "APPLIED"
  | "APPLICATION_FAILED" | "RECRUITER_CONTACTED" | "RECRUITER_REPLIED" | "SCREENING" | "ASSESSMENT"
  | "INTERVIEW_SCHEDULED" | "INTERVIEW_COMPLETED" | "OFFER" | "REJECTED" | "WITHDRAWN" | "CLOSED";

export interface Application {
  id: string;
  job_id: string | null;
  company: string;
  role: string;
  source: string | null;
  application_url: string | null;
  match_score: number | null;
  resume_id: string | null;
  cover_letter_id: string | null;
  status: ApplicationStatus;
  applied_at: string | null;
  last_contact_at: string | null;
  next_followup_at: string | null;
  recruiter_id: string | null;
  interview_id: string | null;
  created_at: string;
  updated_at: string;
  auto?: boolean;
  apply_email?: string | null;
  applied_via?: string | null;
  walk_in?: WalkIn | null;
}

export interface ApplicationAnswer {
  id: string;
  question: string;
  answer: string | null;
  source: string | null;
  confidence: "HIGH" | "MEDIUM" | "LOW";
  status: "ANSWERED" | "REVIEW_REQUIRED" | "USER_PROVIDED";
  sensitive: boolean;
  note: string | null;
}

export interface Interview {
  id: string;
  application_id: string | null;
  company: string | null;
  role: string | null;
  round: string | null;
  scheduled_at: string;
  timezone: string | null;
  duration_minutes: number;
  meeting_url: string | null;
  interviewer: string | null;
  interview_type: string | null;
  status: "upcoming" | "completed" | "rescheduled" | "cancelled";
  notes: string | null;
  source: string;
  created_at: string;
}

export interface ApplicationDetail extends Application {
  events: { id: string; type: string; note: string | null; from: string | null; to: string | null; source: string; email_id: string | null; at: string }[];
  answers: ApplicationAnswer[];
  followups: { id: string; kind: string; sequence: number; status: string; due_at: string }[];
  interviews: Interview[];
}

// ---------------- Phase 5: email & integrations
export interface InboxEmail {
  id: string;
  gmail_id: string | null;
  sender: string;
  subject: string;
  snippet: string;
  received_at: string;
  category: string;
  confidence: number;
  extracted: {
    sender_name: string | null;
    sender_email: string;
    sender_domain: string;
    interview_at: string | null;
    timezone: string;
    meeting_url: string | null;
    deadline: string | null;
    interview_round: string | null;
  };
  application_id: string | null;
  action: string | null;
  source: string;
}

export interface Integrations {
  google: { connected: boolean; available: boolean };
  gmail: { connected: boolean; available: boolean; email: string | null; method: "oauth" | "app_password" | null; status: string; error: string | null; last_sync_at: string | null;
    last_result?: { search?: Record<"mail" | "portals", { matched?: number; fetched?: number; mailbox?: string; fallback?: boolean } | undefined> } | null };
  whatsapp: { connected: boolean; enabled: boolean; phone: string | null; error: string | null; muted?: string[] };
  linkedin: { snapshot: boolean; mode: string };
  naukri: { snapshot: boolean; mode: string };
  ats_boards: { count: number };
  claude: { enabled: boolean; model: string | null };
}

// ---------------- Recruiters & outreach
export type ContactRole = "recruiter" | "hiring_manager" | "referral" | "alumni" | "other";
export type OutreachKind = "referral" | "cold" | "hiring_manager" | "employee_intro" | "linkedin_note" | "followup" | "thank_you" | "reply";
export type OutreachStatus = "draft" | "approved" | "sent" | "replied" | "bounced" | "no_response" | "unsubscribed" | "cancelled";

export interface RecruiterContact {
  id: string;
  name: string;
  company: string;
  email: string | null;
  phone?: string | null;
  linkedin_url: string | null;
  title: string | null;
  role: ContactRole;
  tags: string[];
  notes: string | null;
  source: "manual" | "csv" | "gmail" | "job";
  unsubscribed: boolean;
  last_contacted_at: string | null;
  created_at: string;
}

export interface Outreach {
  attach_resume?: boolean;
  asks?: string[];
  id: string;
  contact_id: string;
  job_id: string | null;
  parent_id: string | null;
  kind: OutreachKind;
  status: OutreachStatus;
  subject: string;
  body: string;
  company: string | null;
  contact_name: string | null;
  channel_hint: "email" | "linkedin";
  validation: { status: string; violations: { type: string; value: string; reason: string }[] } | null;
  mailto: string | null;
  gmail_compose: string | null;
  linkedin_url: string | null;
  approved_at: string | null;
  sent_at: string | null;
  sent_via?: "gmail" | "manual" | null;
  replied_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface OutreachStats {
  can_send_from_saige: boolean;
  contacts_by_source: Record<string, number>;
  sent_today: number;
  daily_limit: number;
  remaining_today: number;
  by_status: Partial<Record<OutreachStatus, number>>;
  contacts: number;
  reply_rate: number | null;
  followups_due: { followup_id: string; outreach_id: string; contact_id: string; contact_name: string | null; company: string | null; subject: string; sequence: number; due_at: string }[];
}

// ---------------- Analytics
export interface GroupMetrics {
  label: string;
  applications: number;
  sent: number;
  responses: number;
  interviews: number;
  offers: number;
  response_rate: number | null;
  interview_rate: number | null;
  offer_rate: number | null;
}

export interface Breakdowns {
  overall: Omit<GroupMetrics, "label">;
  by_source: GroupMetrics[];
  by_role_family: GroupMetrics[];
  by_resume: GroupMetrics[];
  by_match: GroupMetrics[];
  weekly: { week: string; applied: number; responses: number; interviews: number; offers: number }[];
  time_to_response: { bucket: string; count: number }[];
  outreach: { kind: OutreachKind; sent: number; replied: number; reply_rate: number | null }[];
}

export interface OutreachTemplate {
  kind: OutreachKind | `wa_${string}` | `sms_${string}`;
  channel: "email" | "linkedin" | "whatsapp" | "sms";
  wa_link?: string;
  sms_link?: string;
  name: string;
  audience: string;
  description: string;
  subject: string;
  body: string;
}

export interface DiscoverResult {
  source: string;
  source_job_id: string | null;
  title: string;
  company: string;
  location: string | null;
  remote: boolean | null;
  url: string | null;
  posted: string | null;
  description: string;
  salary_min?: number | null;
  salary_max?: number | null;
  score: number;
  classification: string;
  matched_skills: string[];
  missing_skills: string[];
  saved_job_id: string | null;
  id?: string;
  source_label?: string;
  scope?: JobScope;
  walk_in?: WalkIn | null;
  hr_emails?: string[];
  apply_by_email?: boolean;
  exp_min?: number | null;
  exp_max?: number | null;
  employment_type?: string | null;
  snippet?: string;
}

export type JobScope = "country" | "remote" | "abroad";
export interface WalkIn { date: string | null; time: string | null; venue: string | null }

export type FeedItem = Omit<DiscoverResult, "description" | "id" | "scope" | "source_label"> & { id: string; scope: JobScope; source_label: string };

export interface JobFeed {
  roles: string[];
  country: string | null;
  built_at: string | null;
  errors: Record<string, string>;
  counts: { all: number; country: number; remote: number; abroad: number; walk_in: number; alerts: number; careers: number; with_email: number };
  items: FeedItem[];
}

export interface HiringPortal {
  key: string;
  name: string;
  method: "api" | "alerts";
  region: string;
  url: string;
  alert_help?: string;
  state: "connected" | "receiving" | "waiting" | "needs_gmail" | "setup";
  jobs: number;
  profile_url: string | null;
  alerts_on: boolean;
}

export interface AtsScore {
  score: number;
  required_coverage: number;
  preferred_coverage: number;
  matched_keywords: string[];
  missing_required: string[];
  missing_preferred: string[];
  checks: { check: string; passed: boolean }[];
  word_count: number;
  job: string;
  resume: string;
  tips: string[];
}

export interface DiscoverResponse {
  query: string;
  location: string | null;
  providers: string[];
  errors: Record<string, string>;
  results: DiscoverResult[];
}
