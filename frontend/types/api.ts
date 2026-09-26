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
  limits: {
    daily_application_limit: number;
    daily_email_limit: number;
    daily_recruiter_contact_limit: number;
    min_match_score: number;
  };
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
