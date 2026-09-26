// The Saige AI user manual: one section per screen. Screenshots live in /public/help and are
// regenerated with the manual capture script (see AGENTS.md).

export type ManualSection = {
  id: string;
  title: string;
  href: string;
  tone: string;
  image: string;
  purpose: string;
  steps: string[];
  tips?: string[];
};

export const QUICK_START = [
  "Sign in (email and password, or Google once your account is a test user).",
  "Resumes → upload your resume, then click “Import to profile”.",
  "Profile → fill anything marked UNKNOWN: notice period, expected CTC, target roles and locations.",
  "Integrations → connect Gmail with an App Password, and turn on WhatsApp alerts if you like.",
  "Jobs → Discover jobs for your role, select the good matches, click “Save & prepare applications”.",
  "LinkedIn & Naukri → paste your current profile text; Saige suggests truthful improvements daily.",
  "Recruiters → add contacts or sync them, pick a template, and click “Approve & send”.",
];

export const MANUAL: ManualSection[] = [
  {
    id: "dashboard", title: "Dashboard", href: "/", tone: "green", image: "/help/dashboard.jpg",
    purpose: "Your daily overview: what Saige found and did today, pipeline health, what needs you, and the next scheduled profile refresh.",
    steps: [
      "Read the Today cards: each shows today's count, the change since yesterday and a 7-day trend line. Click a card to open that section.",
      "Check “Action required” for approvals, follow-ups, interviews and profile suggestions waiting for you.",
      "Use “Pause all automation” at the top whenever you want Saige to stop everything instantly.",
    ],
    tips: ["The profile-readiness ring shows how complete your profile is. Higher means better matching and documents."],
  },
  {
    id: "profile", title: "Profile", href: "/profile", tone: "mint", image: "/help/profile.jpg",
    purpose: "Your verified career facts. Every resume, answer and message Saige writes uses only what's here, so nothing is ever invented.",
    steps: [
      "Import from your resume first (Resumes → Import to profile), then review each section.",
      "Fill fields marked UNKNOWN: notice period, current and expected CTC, target roles and preferred locations.",
      "Add skills, tools and achievements you can back up in an interview. Click Save.",
    ],
    tips: ["Missing skills that jobs ask for show as gaps. Add them only if you genuinely have them."],
  },
  {
    id: "linkedin-naukri", title: "LinkedIn & Naukri", href: "/profiles", tone: "teal", image: "/help/profiles.jpg",
    purpose: "Truthful, copy-ready improvements for your LinkedIn and Naukri profiles, plus a daily Naukri freshness edit that keeps you high in recruiter searches.",
    steps: [
      "Open the LinkedIn or Naukri tab and paste what's currently on your profile into the snapshot form, then save.",
      "Click “Run profile refresh”. Saige compares your profile with recent target job descriptions.",
      "For each suggestion: Copy, open the site with the “Open … edit page” button, paste, save there, then click “Mark as updated”.",
      "On the Naukri tab, “Run 2-min freshness” creates one small daily edit; apply it to keep your streak going.",
    ],
    tips: ["LinkedIn and Naukri don't allow apps to edit profiles, so you paste the text. It takes about a minute and keeps your account safe."],
  },
  {
    id: "schedule", title: "Daily schedule", href: "/profiles?tab=schedule", tone: "teal", image: "/help/schedule.jpg",
    purpose: "When Saige runs its daily jobs: profile refresh, Naukri freshness, job-board sync, Gmail sync, follow-up checks and the morning report.",
    steps: [
      "Choose which platforms to refresh, the run time, days of the week and your timezone, then Save schedule.",
      "Use “Refresh now” or “Freshness now” to run immediately.",
      "Each run ends with a notification (and a WhatsApp message, if on) listing every field it changed: old value → new value.",
    ],
  },
  {
    id: "resumes", title: "Resumes", href: "/resumes", tone: "purple", image: "/help/resumes.jpg",
    purpose: "Upload and version your resumes. Tailored resumes created for specific jobs also appear here.",
    steps: [
      "Choose a PDF, DOCX or TXT file, give it a name, and click Upload.",
      "Open a resume to see what was parsed, then click “Import to profile” to fill your Profile.",
      "Duplicate, archive or download any version. Originals are never modified.",
    ],
  },
  {
    id: "jobs", title: "Jobs & Discover", href: "/jobs", tone: "orange", image: "/help/jobs.jpg",
    purpose: "Find jobs for your role, add jobs from anywhere, and see every job scored against your profile.",
    steps: [
      "Discover: type a role (or leave it empty to use your target role) and a city, then Search.",
      "Results are scored 0–100. Good matches (70+) are pre-selected. Use “Select all” or pick individually.",
      "Click “Save & prepare applications” to add them to your jobs and create an application for each, with the best resume attached.",
      "For LinkedIn, Naukri or Indeed postings, use the Chrome extension or paste the description under “Add a job”.",
      "Follow a company's Greenhouse, Lever or Ashby board to fetch its new postings every day.",
    ],
    tips: ["Discover uses official job APIs. Add a free Adzuna key in the backend settings for India-wide results."],
  },
  {
    id: "job-detail", title: "Job details", href: "/jobs", tone: "orange", image: "/help/job-detail.jpg",
    purpose: "Why a job matches (9 dimensions), the skills you have and lack, AI documents, and people who can refer you.",
    steps: [
      "Review the match breakdown and missing skills.",
      "Click “Generate tailored resume” and “Generate cover letter”. Both use only verified facts.",
      "Under “Get a referral”, draft a referral request to anyone you know at the company.",
      "Click “Prepare application” when you're ready to apply.",
    ],
  },
  {
    id: "applications", title: "Applications", href: "/applications", tone: "yellow", image: "/help/applications.jpg",
    purpose: "Every application from preparation to offer, with follow-ups scheduled automatically.",
    steps: [
      "Open an application to see its resume, cover letter and prepared answers.",
      "Paste the employer's questions and click “Answer questions”. Uncertain or sensitive answers are flagged for review.",
      "Apply on the employer's site, then click “Mark applied”. Follow-ups are scheduled for day 3 and day 7.",
      "Status updates arrive automatically from Gmail (interview, rejection, offer). You can also move stages yourself.",
    ],
  },
  {
    id: "interviews", title: "Interviews", href: "/interviews", tone: "red", image: "/help/interviews.jpg",
    purpose: "Upcoming, completed and cancelled interviews, added by you or detected from email.",
    steps: [
      "Click Calendar to add an interview to Google Calendar, Outlook or Apple Calendar.",
      "Use Join to open the meeting link, and Done or Cancel to update the status.",
    ],
  },
  {
    id: "recruiters", title: "Recruiters & outreach", href: "/recruiters", tone: "lime", image: "/help/recruiters.jpg",
    purpose: "Your recruiter and referral contacts, truth-checked emails, and follow-ups that stop when someone replies.",
    steps: [
      "Click “Sync recruiters” to add people who emailed you and contacts listed in your saved job postings, or add contacts yourself or by CSV.",
      "Filter contacts by source: From inbox, From job postings, Added by you, CSV.",
      "Click Draft on a contact, choose the type and add how you know them.",
      "In the Queue, review the email and click “Approve & send”. Saige sends it from your Gmail and schedules follow-ups.",
      "Limits: 10 emails a day and 3 people per company a week, to protect your reputation.",
    ],
    tips: ["“Approve & send” appears once Gmail is connected with an App Password. Otherwise open the email in Gmail and send it yourself."],
  },
  {
    id: "templates", title: "Email templates", href: "/recruiters", tone: "lime", image: "/help/templates.jpg",
    purpose: "Ready-to-send templates, filled from your profile: cold email to HR, hiring manager, referral request, informational chat, LinkedIn note, follow-up and thank-you.",
    steps: [
      "Open Recruiters → Email templates.",
      "Copy a template, or choose a contact and click Draft to create a personalised email in your queue.",
    ],
  },
  {
    id: "analytics", title: "Analytics", href: "/analytics", tone: "purple", image: "/help/analytics.jpg",
    purpose: "What works: response, interview and offer rates by source, role, resume version and match score.",
    steps: [
      "Compare sources to see where your best responses come from.",
      "Use the table icon on any chart to see the exact numbers.",
    ],
  },
  {
    id: "inbox", title: "Inbox", href: "/inbox", tone: "teal", image: "/help/inbox.jpg",
    purpose: "Job-search emails from Gmail, classified automatically (confirmation, interview, assessment, rejection, offer).",
    steps: [
      "Connect Gmail in Integrations, then click Sync (it also runs daily).",
      "Each email links to the application it updated.",
    ],
  },
  {
    id: "integrations", title: "Integrations", href: "/integrations", tone: "orange", image: "/help/integrations.jpg",
    purpose: "Connect Gmail, WhatsApp alerts, company job boards, calendar and the browser extension.",
    steps: [
      "Gmail: create an App Password at myaccount.google.com/apppasswords (needs 2-Step Verification) and paste it in “Connect Gmail”.",
      "WhatsApp: follow the three steps in the WhatsApp card to get a CallMeBot key, then click “Connect & send test”.",
      "Drag “Save to Saige” to your bookmarks bar to capture any job page.",
    ],
  },
  {
    id: "notifications", title: "Notifications & WhatsApp", href: "/integrations#whatsapp", tone: "mint", image: "/help/notifications.jpg",
    purpose: "Everything Saige does is announced in the bell (top right) and, if enabled, on WhatsApp.",
    steps: [
      "Click the bell to see recent updates. Profile updates show each changed field with old → new values.",
      "Click an item to jump to it; “Mark all read” clears the badge.",
      "Pause or remove WhatsApp alerts from the WhatsApp card at any time.",
    ],
  },
  {
    id: "settings", title: "Automation & Privacy", href: "/settings", tone: "yellow", image: "/help/settings.jpg",
    purpose: "Control what Saige may do automatically, daily limits, match weights, the browser extension, and your data.",
    steps: [
      "Pick an automation mode and pause individual agents (job discovery, emails, profile updates, and more).",
      "Set daily limits for applications and outreach.",
      "Browser extension: download it, create a token, and paste the token in the extension's Settings.",
      "Export all your data as JSON, or delete your account.",
    ],
  },
];

export const FAQ = [
  { q: "Google says “Access blocked: has not completed the Google verification process”.", a: "Your Google Cloud project is in Testing mode. Add your Gmail address under Google Cloud → Google Auth Platform → Audience → Test users. For Gmail, you can skip this entirely: connect with an App Password in Integrations." },
  { q: "Can Saige update my Naukri or LinkedIn profile by itself?", a: "No. Both sites forbid apps from logging in or editing profiles, and accounts that do get restricted. Saige prepares the exact text and opens the edit page; pasting takes about a minute." },
  { q: "Can Saige auto-apply to jobs on Naukri, LinkedIn or Indeed?", a: "Those sites don't allow third-party auto-apply. Saige prepares everything in bulk (resume, cover letter, answers) and you submit on the employer's page." },
  { q: "Does Saige send emails for me?", a: "Only after you approve each one, and only if you've connected Gmail with an App Password. Limits of 10 a day and 3 per company a week apply." },
  { q: "How do WhatsApp alerts work?", a: "Saige mirrors every notification to your own WhatsApp number via CallMeBot, a free relay. Set it up in Integrations → WhatsApp notifications." },
  { q: "Can Saige invent skills to match a job?", a: "Never. Every claim is checked against your verified profile. Missing skills are shown as gaps to learn." },
  { q: "How long does my sign-in last?", a: "30 days, renewed as you use Saige." },
  { q: "Why is a match score capped at 60%?", a: "The job description listed no clear skills, so Saige can't be confident. Paste the full description for an accurate score." },
];
