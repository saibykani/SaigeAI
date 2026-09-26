"use client";

import { Users, BookOpen, Briefcase, CalendarDays, FileText, LifeBuoy, Mail, Plug, Search, Send, Settings, ShieldCheck, Sparkles, UserRound, type LucideIcon } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { PageHeader } from "@/components/app-shell";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/form";

type Guide = { title: string; icon: LucideIcon; href: string; tone: string; steps: string[] };

const GUIDES: Guide[] = [
  { title: "Get started", icon: BookOpen, href: "/profile", tone: "green", steps: [
    "Upload your resume in Resumes, then click “Import to profile”.",
    "Open Master Profile and fill anything still marked UNKNOWN: notice period, expected CTC, target roles, locations.",
    "Every AI output uses only what your verified profile contains, so a complete profile means better results.",
  ] },
  { title: "Find & score jobs", icon: Briefcase, href: "/jobs", tone: "orange", steps: [
    "Paste a job description, or follow a company’s Greenhouse, Lever or Ashby board to fetch new postings.",
    "On LinkedIn, Naukri or Indeed, use the “Save to Saige” bookmark (Integrations) while viewing a posting.",
    "Each job gets a 9-dimension match score. Tune the weights in Jobs → Matching.",
  ] },
  { title: "Tailor resumes", icon: FileText, href: "/resumes", tone: "purple", steps: [
    "Open a job and click Tailor resume. Saige reorders and rewrites using only verified facts.",
    "Run the ATS check to see keyword coverage and formatting issues.",
    "Generate a cover letter and export either document as DOCX.",
  ] },
  { title: "Track applications", icon: Send, href: "/applications", tone: "yellow", steps: [
    "Create an application from a job. Saige drafts answers with a confidence level; sensitive fields always need your review.",
    "Approve it, apply on the company site yourself, then click Mark applied.",
    "Follow-ups are suggested on days 3 and 7; the application auto-closes after 14 days of silence.",
  ] },
  { title: "Interviews & calendar", icon: CalendarDays, href: "/interviews", tone: "teal", steps: [
    "Interviews are added by you or detected from Gmail.",
    "Click Calendar to add one to Google Calendar, Outlook or Apple Calendar (.ics).",
  ] },
  { title: "Gmail monitoring", icon: Mail, href: "/integrations", tone: "red", steps: [
    "Integrations → Gmail → Connect. Access is read-only; tokens are encrypted.",
    "Saige spots confirmations, assessments, interviews, rejections and offers, and updates applications (status only moves forward).",
    "Disconnect at any time. Access is revoked immediately.",
  ] },
  { title: "LinkedIn & Naukri profiles", icon: UserRound, href: "/profiles", tone: "mint", steps: [
    "Paste your current headline, About/summary and skills in the LinkedIn & Naukri hub.",
    "Saige schedules truthful daily optimizations from target JDs, plus a daily 2-minute micro-edit to keep your Naukri profile active.",
    "LinkedIn and Naukri have no public edit API, so Saige never logs in for you or stores those passwords. Suggestions are copy-ready.",
  ] },
  { title: "Recruiters & referrals", icon: Users, href: "/recruiters", tone: "orange", steps: [
    "Add people you know, import a CSV (LinkedIn’s connections export works), or pull recruiters who emailed you.",
    "On any job, “Get a referral” lists your contacts there and drafts a truth-checked request.",
    "Approve, send it yourself from Gmail or LinkedIn, then click “I sent it”. Max 10 a day and 3 per company a week; follow-ups stop when they reply.",
  ] },
  { title: "Automation & privacy", icon: Settings, href: "/settings", tone: "lime", steps: [
    "Pick a mode (conservative, balanced or aggressive), set daily limits, and pause any agent, or everything, with one switch.",
    "Export all your data as JSON or delete your account in Privacy.",
  ] },
];

const FAQ = [
  { q: "Google says “Access blocked: has not completed the Google verification process”.", a: "The Google project is in Testing mode. In Google Cloud Console → Google Auth Platform → Audience → Test users, add your Google address, then try again. Public sign-in needs Google’s app verification." },
  { q: "Does Saige apply to jobs or message recruiters automatically?", a: "No. Saige prepares everything: tailored resume, answers and drafts. You approve and submit. Outreach is capped at 10 messages a day." },
  { q: "Can Saige invent skills to match a job?", a: "Never. Every claim is checked against your verified profile by the truth guard. Missing skills are shown as gaps to learn, not added to your resume." },
  { q: "How long does my sign-in last?", a: "30 days, renewed as you use Saige. Signing out ends the session on this device." },
  { q: "Is Claude AI required?", a: "No. Everything works without it. When an Anthropic key is configured, Claude polishes wording, and its output is still verified against your profile." },
  { q: "Why is my match score capped at 60%?", a: "The job description listed no clear skills, so Saige can’t be confident. Paste the full description for an accurate score." },
];

export default function HelpPage() {
  const [q, setQ] = useState("");
  const needle = q.trim().toLowerCase();
  const guides = useMemo(() => GUIDES.filter((g) => !needle || `${g.title} ${g.steps.join(" ")}`.toLowerCase().includes(needle)), [needle]);
  const faq = useMemo(() => FAQ.filter((f) => !needle || `${f.q} ${f.a}`.toLowerCase().includes(needle)), [needle]);

  return (
    <>
      <PageHeader title="Help & Docs" description="How every part of Saige works, and why it never does anything behind your back." />
      <div className="relative mb-8 max-w-xl">
        <Search className="pointer-events-none absolute left-4 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search guides and FAQ…" className="h-12 rounded-full pl-11" />
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {guides.map((g, i) => (
          <Card
            key={g.title}
            className="lift animate-rise group flex flex-col p-5"
            style={{ animationDelay: `${i * 40}ms`, borderColor: `color-mix(in srgb, var(--tone-${g.tone}) 28%, transparent)`, backgroundImage: `radial-gradient(120% 90% at 100% 0%, color-mix(in srgb, var(--tone-${g.tone}) 16%, transparent), transparent 60%)` }}
          >
            <span className="grid size-10 place-items-center rounded-xl text-[#0b0b0c] transition-transform duration-300 group-hover:scale-110 group-hover:-rotate-6" style={{ background: `var(--tone-${g.tone})` }}>
              <g.icon className="size-5" />
            </span>
            <h2 className="mt-4 font-semibold">{g.title}</h2>
            <ol className="mt-2 flex flex-1 list-decimal flex-col gap-1.5 pl-4 text-sm text-muted-foreground">
              {g.steps.map((s) => <li key={s}>{s}</li>)}
            </ol>
            <Link href={g.href} className="mt-4 text-sm font-medium hover:underline">Open →</Link>
          </Card>
        ))}
      </div>

      <h2 className="mb-4 mt-12 flex items-center gap-2 text-xl font-semibold tracking-tight"><LifeBuoy className="size-5" /> Frequently asked</h2>
      <div className="flex flex-col gap-2">
        {faq.map((f) => (
          <details key={f.q} className="glass group rounded-2xl border p-4 open:shadow-[var(--shadow-card)]">
            <summary className="cursor-pointer list-none font-medium marker:hidden">{f.q}</summary>
            <p className="mt-2 text-sm text-muted-foreground">{f.a}</p>
          </details>
        ))}
        {!faq.length && !guides.length && <p className="text-sm text-muted-foreground">Nothing matches “{q}”.</p>}
      </div>

      <Card className="mt-10 flex flex-wrap items-center gap-4 p-5">
        <ShieldCheck className="size-6" />
        <p className="flex-1 text-sm text-muted-foreground">Saige’s promise: no fabricated experience, no scraping, no stored LinkedIn or Naukri passwords, and nothing sent without your approval.</p>
        <Link href="/integrations" className="inline-flex items-center gap-1.5 text-sm font-medium hover:underline"><Plug className="size-4" /> Integrations</Link>
        <Link href="/profile-sync" className="inline-flex items-center gap-1.5 text-sm font-medium hover:underline"><Sparkles className="size-4" /> Profile Sync</Link>
      </Card>
    </>
  );
}
