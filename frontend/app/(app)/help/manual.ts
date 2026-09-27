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
  "Create an account: step 1 is your email and password, step 2 your current role, experience, the roles you want, city, country and notice period (these start your profile).",
  "Resumes → upload your resume, then click “Import to profile”.",
  "Profile (last item in the sidebar) → fill anything marked UNKNOWN, and check your target roles and country.",
  "Settings → Integrations → connect Gmail with an App Password and set up job alerts on LinkedIn / Naukri / Indeed. Settings → Alerts & templates → turn on WhatsApp alerts.",
  "Jobs → Jobs for you lists every job for your roles in your country. Select all good matches and click “Auto-apply to selected”.",
  "Applications → “Ready to approve” → Select all → “Approve & apply”. Email applications go from your Gmail; others open the employer's page.",
  "Recruiters → Sync recruiters to collect HR emails, pick an email or WhatsApp template, and click “Approve & send”.",
];

export const MANUAL: ManualSection[] = [
  {
    id: "dashboard", title: "Dashboard", href: "/", tone: "green", image: "/help/dashboard.jpg",
    purpose: "Your daily overview: what Saige found and did today, pipeline health, your market (jobs found, where, which companies), what needs you, and the next scheduled profile refresh.",
    steps: [
      "Read the Today cards: each shows today's count, the change since yesterday and a 7-day trend line. Click a card to open that section.",
      "Check “Action required” for approvals, follow-ups, interviews and profile suggestions waiting for you.",
      "Use “Pause all automation” at the top whenever you want Saige to stop everything instantly.",
    ],
    tips: ["The profile-readiness ring shows how complete your profile is. Higher means better matching and documents."],
  },
  {
    id: "profile", title: "Profile (last item in the sidebar)", href: "/profile", tone: "mint", image: "/help/profile.jpg",
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
      "Faster with the Saige browser extension: on Naukri / LinkedIn, click the field (e.g. Headline), open the extension and press Fill next to that edit, click Save on the site, then Mark updated.",
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
    tips: ["Runs prepare edits; they don't change LinkedIn or Naukri by themselves (no app is allowed to). Run History shows “N edit(s) waiting for you” until you paste each one on the site and click “Mark as updated”."],
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
    id: "health", title: "Resume health", href: "/resumes#health", tone: "purple", image: "/help/health.jpg",
    purpose: "A health report for any resume, no job needed: quantified impact, repetition, bullet length, strong verbs, contact details, summary, skills and length.",
    steps: [
      "Resumes → “Resume health”, then pick a resume.",
      "Red items show exactly what to change; green items are fine.",
      "Fix the resume, upload the new version, and check the score again.",
    ],
  },
  {
    id: "ats", title: "ATS resume scorer", href: "/resumes#ats", tone: "purple", image: "/help/ats.jpg",
    purpose: "See how an applicant tracking system reads your resume for a job: keyword coverage, format checks and exactly what to fix.",
    steps: [
      "Resumes → scroll to “ATS resume scorer”.",
      "Pick a resume, then pick a saved job or paste any job description.",
      "Click “Score my resume”. Green ticks are keywords you have; red are required keywords missing.",
      "Follow “What to fix”, or click “Optimise my resume for this job”: Saige builds an optimised version (keywords first, relevant bullets first, tailored summary, full contact details), saves it as a new resume and shows the new score.",
      "Keywords you haven't used are listed as gaps. Add them to your Profile only if they're true, then optimise again to reach 100%.",
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
    tips: ["On company career sites (Greenhouse, Lever, Ashby, Workday…), open the application form and press “Fill this application” in the Saige browser extension: your details, prepared answers and resume go in, and you press Submit. Saige never submits for you."],
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
      "“Did you submit these?” lists applications you opened on employer sites: tick the ones you submitted and click “Mark as applied”.",
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
    id: "analytics", title: "Analytics (Dashboard tab)", href: "/analytics", tone: "purple", image: "/help/analytics.jpg",
    purpose: "Your market and pipeline from day one (jobs by location, company, source and match; applications by stage; inbox by type), plus response, interview and offer rates once applications are marked Applied.",
    steps: [
      "Compare sources to see where your best responses come from.",
      "Use the table icon on any chart to see the exact numbers.",
    ],
  },
  {
    id: "inbox", title: "Inbox", href: "/inbox", tone: "teal", image: "/help/inbox.jpg",
    purpose: "Your job-search email plus every LinkedIn, Naukri and Indeed notification: job alerts, recruiter invites, InMail/message alerts, profile views and application updates.",
    steps: [
      "Connect Gmail in Settings → Integrations. Saige searches all of Gmail (including the Social, Promotions and Updates tabs).",
      "While Saige is open it syncs every minute (each sync imports the next batch of older mail too); you can also click “Sync Gmail”.",
      "Use the tabs: Recruiters, Interviews & tests, Applications, Invites & messages, Job alerts, LinkedIn, Naukri, Other portals.",
      "Recruiters named in Naukri / LinkedIn invites are added to Recruiters automatically (with any phone number the email contains).",
      "Each email links to the application it updated. Portal notifications never change an application's status.",
    ],
    tips: ["The Gmail card shows how many emails the last sync found. If it's 0, check that IMAP is on in Gmail settings."],
  },
  {
    id: "assistant", title: "Saige AI assistant", href: "/assistant", tone: "purple", image: "/help/assistant.jpg",
    purpose: "Chat with your job-search assistant: “Ask Saige AI” in the top bar opens it full screen, and the little galaxy in the bottom-right corner opens it on any page.",
    steps: [
      "Ask things like “What are my best jobs today?”, “How are my applications doing?”, “Any upcoming interviews?” or “Show my latest recruiter emails”.",
      "Answers come from your own records (profile, jobs, applications, inbox, contacts) and include buttons to open the right page.",
      "With an Anthropic API key on the server it can also draft messages, headlines and interview answers. It never invents facts about you.",
    ],
  },
  {
    id: "extension", title: "Browser extension: fill forms & profile edits", href: "/settings#extension", tone: "teal", image: "/help/settings.jpg",
    purpose: "Score and save any job page, fill application forms on company career sites with your verified details and resume, and put prepared LinkedIn / Naukri edits into the right field.",
    steps: [
      "Settings → Automation & privacy → Browser extension: download (v1.1), unzip, open chrome://extensions, turn on Developer mode, Load unpacked.",
      "Create a token on the same card and paste it in the extension's Settings.",
      "On an application form: open the extension → “Fill this application”. Filled fields get a green outline and your resume is attached. Review, then press Submit on the site.",
      "On Naukri / LinkedIn: click the field to edit, open the extension, press Fill next to the edit, Save on the site, then Mark updated.",
    ],
    tips: ["The extension only acts on the tab you click it on, and never presses Submit or Save for you."],
  },
  {
    id: "interview-prep", title: "Interview prep", href: "/jobs", tone: "red", image: "/help/job-detail.jpg",
    purpose: "For any saved job: a 30-second intro, likely technical questions from the JD's skills, behavioural questions paired with your own achievements (STAR), questions to ask, and company research links.",
    steps: [
      "Open a job → Interview prep → Prepare me.",
      "Technical: green ticks are skills you have; orange ones are asked in the JD but missing from your profile, so brush up first.",
      "Behavioural: each question shows a real achievement from your profile to tell as a STAR story.",
    ],
  },
  {
    id: "linkedin-posts", title: "LinkedIn daily posts", href: "/linkedin", tone: "teal", image: "/help/linkedin-posts.jpg",
    purpose: "A LinkedIn post every day from your role and verified skills: a rotating series (tips, common mistakes, checklists, interview questions, tool spotlights, learning notes, career notes) with a designed image or PDF carousel, hashtags and your disclaimer, published automatically and tracked day by day.",
    steps: [
      "LinkedIn & Naukri → Daily posts. Tick “Post every day”, choose the time, days, series, format, tone, hashtags and a disclaimer (e.g. “Views are my own.”).",
      "Click “Connect LinkedIn” once (LinkedIn's official sign-in). From then on posts publish automatically at your time.",
      "Not connected yet? Each post is still prepared with its image; press “Post manually” to open LinkedIn with the text ready.",
      "Track your streak and every post (date, series, format, link). Add reactions / comments / impressions from LinkedIn to see what works.",
      "Replying to comments: open your post on LinkedIn, open the Saige extension → “Draft replies”, click a reply box and press Fill.",
    ],
    tips: ["Posts share general know-how about skills you really have and never claim results or numbers you haven't verified."],
  },
  {
    id: "find-people", title: "Find people (HR, QA managers)", href: "/recruiters?tab=find", tone: "lime", image: "/help/find-people.jpg",
    purpose: "For every company you've applied to or saved: one-click LinkedIn searches for HR, talent acquisition, technical recruiters, QA managers, test leads and engineering managers.",
    steps: [
      "Recruiters → Find people.",
      "Click a search (e.g. “in · QA Manager”). LinkedIn opens the people search for that company.",
      "Pick the right person, then click “Add a person” and paste their name, title and profile link (plus email or phone if they share it).",
      "Draft a referral or cold email to them from Contacts or Templates.",
    ],
    tips: ["Saige doesn't scrape LinkedIn: opening the search yourself keeps your LinkedIn account safe."],
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
    id: "alerts", title: "Settings → Alerts & templates", href: "/alerts", tone: "yellow", image: "/help/alerts.jpg",
    purpose: "WhatsApp alerts, which updates reach WhatsApp, and every template in one place: Email, WhatsApp, SMS and LinkedIn.",
    steps: [
      "Connect WhatsApp (CallMeBot key) and click “Connect & send test”. If it fails, the exact CallMeBot answer is shown. Use “Send test” any time.",
      "Under “What to send to WhatsApp”, tick the kinds of update you want: applications, recruiter emails, interviews, outreach, jobs, LinkedIn & Naukri.",
      "Pick a template channel. Copy, “Open in WhatsApp”, “Open in Messages” (SMS), or draft an email for a contact.",
    ],
  },
  {
    id: "agent", title: "Settings → Agent", href: "/agent", tone: "teal", image: "/help/agent.jpg",
    purpose: "How your agent works: outreach mode (Auto or Manual), your own message templates, auto-reply to recruiters, follow-ups, the auto-applier and blocked companies.",
    steps: [
      "Outreach mode: Auto mode sends replies, follow-ups and (optionally) emails to HR contacts in jobs you applied to, from your Gmail, within the limits. Manual mode waits for your approval on each message.",
      "Your message templates: write your own cold email, referral request, follow-up or thank-you with {{firstName}}, {{jobTitle}}, {{companyName}}, {{jobLink}}, {{myName}} and more.",
      "Auto-reply: when a recruiter emails, Saige drafts the answer to what they asked (CTC, notice, location, experience, resume, availability, job ID) from your verified profile, attaching your resume if asked. Approve it in Recruiters → Queue and it's sent from your Gmail.",
      "Follow-ups: choose the days after sending (e.g. 3, 7, 14). They stop when someone replies.",
      "Auto-applier: minimum match, how many a day, where, and email applications.",
      "Blocked companies: jobs, auto-apply and outreach skip these (e.g. your current employer).",
    ],
  },
  {
    id: "notifications", title: "Notifications & WhatsApp", href: "/alerts", tone: "mint", image: "/help/notifications.jpg",
    purpose: "Everything Saige does is announced in the bell (top right) and, if enabled, on WhatsApp.",
    steps: [
      "Click the bell to see recent updates. Profile updates show each changed field with old → new values.",
      "Click an item to jump to it; “Mark all read” clears the badge.",
      "Pause, remove or fine-tune WhatsApp alerts in Settings → Alerts & templates.",
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
  { q: "Where is the theme switcher?", a: "Click your avatar (top right) → Theme. Creative themes (Retro Terminal, Paper & Ink, Neon Grid, Desert Sunset, Liquid Glass) change fonts, shapes, backgrounds and colours across the whole app." },
  { q: "Can Saige change my Naukri / LinkedIn profile by itself?", a: "No app is allowed to log into Naukri or LinkedIn and edit your profile; accounts doing that get blocked. The closest safe way: the Saige extension fills each prepared edit into the field you click on the site, and you press Save." },
  { q: "Where did Interviews, Analytics and Integrations go?", a: "Similar pages are grouped with tabs: Interviews is in Applications, Analytics in Dashboard, Resume sync in LinkedIn & Naukri, and Settings holds Alerts & templates, Integrations, Agent, and Automation & privacy. Profile is the last item in the sidebar." },
  { q: "Can Saige fetch LinkedIn / Naukri jobs every second, and apply there?", a: "Not from their websites: both forbid automated access and auto-applying, and accounts that do it get banned. While Saige is open it syncs Gmail every minute, so LinkedIn / Naukri job alerts, invites and messages appear within a minute; job sites and career pages refresh every 5 minutes. For LinkedIn / Naukri postings, open the job and apply there (Easy Apply / Apply on Naukri), then mark it applied." },
  { q: "Can Saige get recruiters' phone numbers from LinkedIn?", a: "Saige never scrapes LinkedIn. It saves phone numbers and emails that recruiters share with you: in Naukri / LinkedIn invite emails, recruiter emails, and job postings. Import your LinkedIn connections CSV for your network." },
  { q: "Does Saige send emails for me?", a: "Only after you approve each one, and only if you've connected Gmail with an App Password. Limits of 10 a day and 3 per company a week apply." },
  { q: "How do WhatsApp alerts work?", a: "Saige mirrors every notification to your own WhatsApp number via CallMeBot, a free relay. Set it up in Integrations → WhatsApp notifications." },
  { q: "Can Saige invent skills to match a job?", a: "Never. Every claim is checked against your verified profile. Missing skills are shown as gaps to learn." },
  { q: "How long does my sign-in last?", a: "30 days, renewed as you use Saige." },
  { q: "Why is a match score capped at 60%?", a: "The job description listed no clear skills, so Saige can't be confident. Paste the full description for an accurate score." },
];
