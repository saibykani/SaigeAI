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
  "Profile (top-right avatar → Profile) → fill anything marked UNKNOWN, and set your target roles and country.",
  "Settings → Integrations → connect Gmail with an App Password, turn on WhatsApp alerts, and set up job alerts on LinkedIn / Naukri / Indeed.",
  "Jobs → Jobs for you lists every job for your roles in your country. Select all good matches and click “Auto-apply to selected”.",
  "Applications → “Ready to approve” → Select all → “Approve & apply”. Email applications go from your Gmail; others open the employer's page.",
  "Recruiters → Sync recruiters to collect HR emails, pick an email or WhatsApp template, and click “Approve & send”.",
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
    id: "profile", title: "Profile (avatar menu, top right)", href: "/profile", tone: "mint", image: "/help/profile.jpg",
    purpose: "Your verified career facts. Every resume, answer and message Saige writes uses only what's here, so nothing is ever invented.",
    steps: [
      "Import from your resume first (Resumes → Import to profile), then review each section.",
      "Fill fields marked UNKNOWN: notice period, current and expected CTC, target roles, country and preferred locations.",
      "Your target roles and country decide which jobs appear in Jobs → Jobs for you.",
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
    id: "ats", title: "ATS resume scorer", href: "/resumes#ats", tone: "purple", image: "/help/ats.jpg",
    purpose: "See how an applicant tracking system reads your resume for a job: keyword coverage, format checks and exactly what to fix.",
    steps: [
      "Resumes → scroll to “ATS resume scorer”.",
      "Pick a resume, then pick a saved job or paste any job description.",
      "Click “Score my resume”. Green ticks are keywords you have; red are required keywords missing.",
      "Follow “What to fix”. For a version aimed at one job, open the job and click “Generate tailored resume”.",
    ],
    tips: ["Only add a missing keyword if you've really used it. Saige never adds skills you don't have."],
  },
  {
    id: "jobs", title: "Jobs for you", href: "/jobs", tone: "orange", image: "/help/jobs.jpg",
    purpose: "Every job for your target roles in your country (plus remote), fetched automatically and scored 0–100 against your profile. Nothing to add by hand.",
    steps: [
      "Open Jobs. Saige fetches from job sites (Himalayas, Remotive, Jobicy, Arbeitnow), company career pages (Stripe, MongoDB, Zscaler, Groww, Meesho, CRED and more) and your LinkedIn / Naukri / Indeed job-alert emails.",
      "Use the tabs: For you, In India (your country), Remote, Walk-in drives, Job alerts, Career pages, Abroad.",
      "Filter by source, match %, posting date, experience, job type, or “Has HR email”, and sort by best match or newest.",
      "Tick jobs, or “Select all”, then click “Auto-apply to selected”: each job is saved and an application is prepared with your best resume.",
      "Walk-in drives show the date, time and venue. Postings that ask for CVs by email show the HR address and “apply by email”.",
      "Refresh fetches again now; the list also refreshes every morning.",
      "Other tabs: Saved jobs (everything you kept), Search any role (a role outside your targets), Add manually (paste a JD or follow another company's career page).",
    ],
    tips: ["LinkedIn, Naukri and Indeed don't allow automated search, so their jobs come from the job alerts they email you. Set those up in Settings → Integrations → Hiring portals."],
  },
  {
    id: "auto-apply", title: "Auto-applier", href: "/jobs", tone: "purple", image: "/help/auto-apply.jpg",
    purpose: "Every morning Saige picks jobs at or above your match score, attaches your best resume and prepares the applications, then messages you on WhatsApp.",
    steps: [
      "Jobs → Jobs for you → scroll to “Auto-applier”.",
      "Tick “Run every day”, choose the minimum match (e.g. 80%), how many a day (up to 25), and where (in my country, remote, abroad).",
      "Keep “Send email applications from Gmail after I approve” on, so postings that ask for CVs by email are applied to from your Gmail.",
      "Click “Run now” to try it straight away.",
      "Open Applications → “Ready to approve” → Select all → “Approve & apply”.",
    ],
    tips: ["Applications on company websites still need your final click there: those sites use logins and CAPTCHAs that no tool may bypass. Saige opens each page for you."],
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
    purpose: "Every application from preparation to offer, with bulk approval and follow-ups scheduled automatically. Interviews is the second tab.",
    steps: [
      "“Ready to approve” lists every prepared application. Select all and click “Approve & apply”.",
      "Email applications are sent from your Gmail with your resume attached and marked Applied. Others show Open: submit on the employer's page, then click “I've submitted”.",
      "Open an application to see its resume, cover letter and prepared answers.",
      "Paste the employer's questions and click “Answer questions”. Uncertain or sensitive answers are flagged for review.",
      "Apply on the employer's site, then click “Mark applied”. Follow-ups are scheduled for day 3 and day 7.",
      "Status updates arrive automatically from Gmail (interview, rejection, offer). You can also move stages yourself.",
    ],
  },
  {
    id: "interviews", title: "Interviews (Applications tab)", href: "/interviews", tone: "red", image: "/help/interviews.jpg",
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
      "Click “Sync recruiters” to collect HR emails: people who emailed you, and the HR addresses published in your saved jobs and in Jobs for you. You can also add contacts yourself, or import your LinkedIn connections CSV.",
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
      "Open Recruiters → Email & WhatsApp templates.",
      "Copy a template, or choose a contact and click Draft to create a personalised email in your queue.",
    ],
  },
  {
    id: "wa-templates", title: "WhatsApp templates", href: "/recruiters", tone: "green", image: "/help/wa-templates.jpg",
    purpose: "Short WhatsApp messages for HR, referrals, follow-ups and thank-yous, written from your verified profile.",
    steps: [
      "Recruiters → Email & WhatsApp templates → WhatsApp messages.",
      "Click “Open in WhatsApp”. WhatsApp opens with the message ready; pick the chat, replace [First name] and [Company], and press send.",
    ],
    tips: ["Message recruiters on WhatsApp only when they've shared their number or a posting lists it."],
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
    id: "integrations", title: "Settings → Integrations", href: "/integrations", tone: "orange", image: "/help/integrations.jpg",
    purpose: "Connect Gmail, WhatsApp alerts, hiring portals, calendar and the browser extension.",
    steps: [
      "Gmail: create an App Password at myaccount.google.com/apppasswords (needs 2-Step Verification) and paste it in “Connect Gmail”.",
      "WhatsApp: follow the three steps in the WhatsApp card to get a CallMeBot key, then click “Connect & send test”.",
      "Drag “Save to Saige” to your bookmarks bar to capture any job page.",
    ],
  },
  {
    id: "portals", title: "Hiring portals", href: "/integrations#portals", tone: "orange", image: "/help/portals.jpg",
    purpose: "Every hiring portal and how its jobs reach you: automatic job APIs and career pages, or job-alert emails from LinkedIn, Naukri, Indeed, Foundit, Glassdoor, Instahyre, Hirist, Cutshort, Wellfound, Shine, iimjobs, TimesJobs, Internshala and apna.",
    steps: [
      "Settings → Integrations → Hiring portals.",
      "Automatic portals need nothing from you.",
      "For each alert portal, click “Set up” and follow the one-line instruction to create a job alert for your role and city, using the email you connected in Gmail.",
      "Optionally save your profile link, tick “I've turned on job alerts”, and click Save.",
      "After the next Gmail sync, those jobs appear in Jobs → Job alerts and the portal shows “Receiving alerts”.",
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
    id: "settings", title: "Settings → Automation & privacy", href: "/settings", tone: "yellow", image: "/help/settings.jpg",
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
  { q: "Can Saige auto-apply to jobs on Naukri, LinkedIn or Indeed?", a: "Those sites don't allow third-party auto-apply. The auto-applier prepares applications in bulk every day. After you approve, email applications are sent from your Gmail, and the rest open on the employer's page for your final click." },
  { q: "Where do LinkedIn and Naukri jobs come from?", a: "From the job-alert emails those sites send you. Turn on alerts for your role and city (Settings → Integrations → Hiring portals), connect Gmail, and they appear under Jobs → Job alerts." },
  { q: "Why don't I see jobs in my country?", a: "Set your country (or current city) and target roles in Profile. Jobs for you uses them to fetch and sort jobs." },
  { q: "Where did Interviews, Analytics and Profile go?", a: "Similar pages are now grouped: Interviews is a tab in Applications, Analytics is a tab in Dashboard, Resume sync is a tab in LinkedIn & Naukri, and Integrations plus Automation & privacy are under Settings. Profile is in the avatar menu (top right)." },
  { q: "Does Saige send emails for me?", a: "Only after you approve each one, and only if you've connected Gmail with an App Password. Limits of 10 a day and 3 per company a week apply." },
  { q: "How do WhatsApp alerts work?", a: "Saige mirrors every notification to your own WhatsApp number via CallMeBot, a free relay. Set it up in Integrations → WhatsApp notifications." },
  { q: "Can Saige invent skills to match a job?", a: "Never. Every claim is checked against your verified profile. Missing skills are shown as gaps to learn." },
  { q: "How long does my sign-in last?", a: "30 days, renewed as you use Saige." },
  { q: "Why is a match score capped at 60%?", a: "The job description listed no clear skills, so Saige can't be confident. Paste the full description for an accurate score." },
];
