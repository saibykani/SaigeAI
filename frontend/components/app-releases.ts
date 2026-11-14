// Android app release notes shown on /download (newest first). Add an entry every time a new APK is published,
// and bump `version:` in mobile/pubspec.yaml to match.

export type Release = { version: string; date: string; size: string; notes: string[] };

export const RELEASES: Release[] = [
  {
    version: "2.0",
    date: "2026-11-14T21:00:00+05:30",
    size: "19.2 MB",
    notes: [
      "Interview debrief: speak or type how it went; Saige saves the questions they asked to your question bank, plus what went well and what to improve",
      "Thank-you email drafted from your debrief, sent from your Gmail only after you confirm",
      "Debrief button on past interviews and in the side menu",
    ],
  },
  {
    version: "1.9",
    date: "2026-11-14T19:30:00+05:30",
    size: "19.1 MB",
    notes: [
      "Interview day mode: tap Prepare on any interview for a live countdown and a Join button that pulses when it's time",
      "Your brief from the job description: what they want, your matching projects, skills to brush up and 8 likely questions",
      "5-minute spoken warm-up: Saige asks 3 questions aloud, listens and shows what you said",
      "Interview checklist you can tick (saved for each interview); works for interviews found only in Gmail too",
    ],
  },
  {
    version: "1.8",
    date: "2026-11-14T18:00:00+05:30",
    size: "19 MB",
    notes: [
      "Today feed on Home: interviews today/tomorrow with Join, approvals, jobs closing soon, follow-ups, best matches and a coach tip as swipeable action cards",
      "Swipe right to act (approvals always ask first), swipe left to dismiss for today; “All caught up” when you're done",
      "Livelier sign-in: floating 3D logo with a pulsing glow, shimmering wordmark and a light travelling around the glass panel; extra text removed",
      "Simpler app: Saved jobs is now a filter in Jobs, Company insights and Salary are one Insights screen, fewer menu items",
    ],
  },
  {
    version: "1.7",
    date: "2026-11-14T16:30:00+05:30",
    size: "18.9 MB",
    notes: [
      "Cinematic opening: hyperspace stars, the logo flies in from deep space with a 3D turn and a light sweep, then the name appears",
      "Sign-in on the full-screen Milky Way galaxy (drag to turn it, tap to scatter stars) with a frosted glass panel",
      "Full sign-in details: Google, email, role choice (job hunting / hiring), approval promise, terms and help contact",
    ],
  },
  {
    version: "1.6",
    date: "2026-11-14T15:02:00+05:30",
    size: "19 MB",
    notes: [
      "New sign-in designed like Google and Apple apps: clean, instant, Continue with Google, no waiting",
      "Welcome animation after you sign in: your logo and name, then the app opens through a circle",
      "More elegant home: today's date, greeting, a one-line summary, profile ring and quick actions",
      "Assistant checks your Gmail when you ask “any interviews today?” and answers like a person",
      "More natural, human-sounding voices for the assistant and mock interviews",
    ],
  },
  {
    version: "1.5",
    date: "2026-11-14T14:35:00+05:30",
    size: "18.9 MB",
    notes: [
      "Side menu (three lines, top left) with every module grouped: Home, Job search, Resume & ATS, Network, Growth, Account",
      "Simpler bottom bar: Home, Jobs, Pipeline, Saige",
    ],
  },
  {
    version: "1.4",
    date: "2026-11-13T15:14:00+05:30",
    size: "18.8 MB",
    notes: ["Continue with Google on the sign-in screen (works once the Android sign-in key is added in Google Cloud)"],
  },
  {
    version: "1.3",
    date: "2026-11-13T14:50:00+05:30",
    size: "18.4 MB",
    notes: [
      "Light, Google/Apple-style design with 7 themes (Light, Dark, Blue, Green, Purple, Coral, Graphite) and Follow system",
      "Recruiters, outreach with approval, referrals and LinkedIn posts",
      "Portfolio, LinkedIn/Naukri profile optimiser, integrations and settings",
      "Admin screens for admins; Hiring home for recruiters; “Let recruiters find me” for job seekers",
    ],
  },
  {
    version: "1.2",
    date: "2026-11-13T13:30:00+05:30",
    size: "18 MB",
    notes: [
      "ATS coach, resume health with side-by-side fixes, and cover letters",
      "Find jobs, career portals and saved jobs",
      "Gmail inbox, goals, follow-ups, salary, learning path and company insights",
      "Mock interview with an animated interviewer, spoken questions and a scored report",
    ],
  },
  {
    version: "1.1",
    date: "2026-11-13T13:14:00+05:30",
    size: "17.5 MB",
    notes: ["Milky Way galaxy sign-in"],
  },
  {
    version: "1.0",
    date: "2026-11-13T11:59:00+05:30",
    size: "18 MB",
    notes: ["First Android app: home, swipe job deck, pipeline, interviews, voice assistant, resume upload"],
  },
];

export const LATEST = RELEASES[0];

export function releaseDate(iso: string): string {
  return new Date(iso).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Kolkata" }) + " IST";
}
