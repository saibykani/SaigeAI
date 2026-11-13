"use client";

import {
  BellRing, Briefcase, Check, ChevronDown, FileCheck2, Globe, Lock, Mail, MessagesSquare, Mic, Send, ShieldCheck, Sparkles, Target, UserCheck,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { LANGUAGES, useT, type Lang } from "@/components/i18n";
import { CONTACT_EMAIL } from "@/components/legal";
import { Starfield } from "@/components/landing/starfield";
import { useAuth } from "@/hooks/use-auth";
import { cn } from "@/utils/cn";

import s from "./landing.module.css";

// Product facts, each checked against the code: careers/catalog.py (187 companies), portfolio/templates.py (41),
// components/i18n.tsx (6 languages), recruiters/service.py HARD_DAILY_CAP = 10, jobs matching (9 dimensions).
const STATS = [
  { v: "180+", l: "company career portals" },
  { v: "9", l: "dimension job matching" },
  { v: "41", l: "portfolio templates" },
  { v: "6", l: "languages" },
  { v: "10/day", l: "recruiter outreach cap" },
];

const CONNECTS = ["Gmail", "Google Calendar", "Greenhouse", "Lever", "Ashby", "Workday", "WhatsApp", "Telegram", "GitHub", "LeetCode"];

const CAPABILITIES: { i: LucideIcon; t: string; d: string; tags: string[] }[] = [
  { i: Target, t: "Job discovery & matching", d: "Jobs from public ATS boards and job APIs, scored on 9 dimensions against your verified profile.", tags: ["9 dimensions", "Daily scan"] },
  { i: FileCheck2, t: "ATS resumes from verified facts", d: "Tailored resumes and cover letters built only from your master profile. Every claim passes the truth guard.", tags: ["DOCX & PDF", "Truth guard"] },
  { i: Send, t: "Auto-apply with your approval", d: "Saige prepares applications every day. Nothing is sent until you approve it.", tags: ["You approve", "Email apply"] },
  { i: Mail, t: "Gmail tracking", d: "Read-only Gmail sync spots replies, interviews and rejections and updates your pipeline.", tags: ["Read-only", "Encrypted"] },
  { i: MessagesSquare, t: "Recruiter outreach", d: "Truth-checked messages to recruiters, capped at 10 a day and 3 per company a week.", tags: ["10/day cap", "Follow-ups"] },
  { i: Globe, t: "Portfolio websites", d: "Publish a personal website from your profile in one click, with 41 templates.", tags: ["41 templates", "Public link"] },
  { i: Mic, t: "Mock interviews", d: "Interview prep and mock interview practice for the roles you target.", tags: ["Practice", "Prep plans"] },
  { i: BellRing, t: "WhatsApp & Telegram alerts", d: "High-match jobs, replies and interview reminders where you already chat.", tags: ["WhatsApp", "Telegram"] },
];

const STEPS = [
  { t: "Upload your resume", d: "Saige reads it and builds your master profile. You confirm every fact." },
  { t: "Pick the jobs you want", d: "Choose roles, cities and remote preference. Saige scans portals daily." },
  { t: "Approve what goes out", d: "Review tailored resumes, applications and messages before they are sent." },
  { t: "Track and follow up", d: "Gmail sync, reminders and analytics keep every application moving." },
];

const SEEKERS = ["Jobs ranked by how well you actually fit", "Resumes and cover letters that never invent anything",
  "One dashboard for applications, interviews and replies", "Free to start"];
const RECRUITERS = ["Post jobs in minutes", "Find opted-in candidates with verified profiles",
  "Candidates choose to be discoverable", "Reach people who want to hear from you"];

const PROMISE: { i: LucideIcon; t: string; d: string }[] = [
  { i: ShieldCheck, t: "Truth guard", d: "Every skill, title, metric and employer is checked against your verified profile. Unknown stays unknown." },
  { i: Lock, t: "No scraping", d: "We never scrape LinkedIn, Naukri or Indeed or ask for their passwords. Only official APIs, OAuth and your own clicks." },
  { i: UserCheck, t: "You approve", d: "Applications, emails and recruiter messages wait for your OK unless you turn on a standing approval." },
  { i: Sparkles, t: "Private", d: "Gmail is read-only and tokens are encrypted. Export or delete all your data at any time." },
];

const FAQ = [
  { q: "Is Saige free?", a: "Yes. You can sign up and start using Saige for free." },
  { q: "Will Saige make up experience to get me shortlisted?", a: "No. Every generated claim is checked against the profile you verified. If something is unknown, Saige leaves it out." },
  { q: "Does Saige apply to jobs without asking me?", a: "Not by default. Applications wait for your approval. You can opt in to automatic modes, and caps and pauses still apply." },
  { q: "Do you log in to LinkedIn or Naukri for me?", a: "No. Those sites have no public profile-edit API, so Saige prepares copy-ready changes that you apply yourself." },
  { q: "Which languages are supported?", a: "English, Hindi, Telugu, Tamil, Kannada and Malayalam." },
  { q: "Can I delete my data?", a: "Yes. Export everything or delete your account permanently from Automation & privacy." },
];

const NAV = [["#what", "What we do"], ["#how", "How it works"], ["#promise", "Our promise"], ["#about", "About"], ["#faq", "FAQ"]];

/** Fades a block in once it scrolls into view (opacity/transform/filter only, so no layout shift). */
function Reveal({ children, delay = 0, className, as: Tag = "div" }: { children: React.ReactNode; delay?: number; className?: string; as?: "div" | "li" | "article" }) {
  const ref = useRef<HTMLElement | null>(null);
  const [shown, setShown] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) { setShown(true); io.disconnect(); } }, { rootMargin: "0px 0px -10% 0px" });
    io.observe(el);
    return () => io.disconnect();
  }, []);
  return (
    <Tag ref={ref as never} className={cn(s.reveal, shown && s.shown, className)} style={{ transitionDelay: `${delay}ms` }}>
      {children}
    </Tag>
  );
}

function Pill({ children, className }: { children: React.ReactNode; className?: string }) {
  return <span className={cn(s.glass, "inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs text-white/80", className)}>{children}</span>;
}

function SectionHead({ eyebrow, title, id }: { eyebrow: string; title: string; id: string }) {
  return (
    <Reveal className="mx-auto mb-12 max-w-3xl text-center">
      <Pill>{eyebrow}</Pill>
      <h2 id={id} className={cn(s.serif, "mt-5 text-4xl leading-[1.05] md:text-6xl")}>{title}</h2>
    </Reveal>
  );
}

function LanguageSelect() {
  const { lang, setLang, t } = useT();
  return (
    <label className="relative inline-flex items-center">
      <span className="sr-only">{t("Language")}</span>
      <Globe className="pointer-events-none absolute left-3 size-4 text-white/70" aria-hidden />
      <select value={lang} onChange={(e) => setLang(e.target.value as Lang)}
        className={cn(s.glass, "appearance-none rounded-full bg-transparent py-2 pl-9 pr-4 text-sm text-white outline-none focus-visible:ring-2 focus-visible:ring-white/60")}>
        {LANGUAGES.map((l) => <option key={l.id} value={l.id} className="bg-black text-white">{l.native}</option>)}
      </select>
    </label>
  );
}

function GetStarted({ t, align = "right" }: { t: (k: string) => string; align?: "right" | "left" }) {
  return (
    <details className="group relative">
      <summary className="flex cursor-pointer list-none items-center gap-1.5 rounded-full bg-white px-4 py-2 text-sm font-medium text-black [&::-webkit-details-marker]:hidden">
        {t("Get started free")} <ChevronDown className="size-4 transition-transform group-open:rotate-180" aria-hidden />
      </summary>
      <div className={cn(s.glass, "absolute z-20 mt-2 w-56 rounded-2xl bg-black/80 p-2", align === "right" ? "right-0" : "left-0")}>
        <Link href="/register?role=jobseeker" className="flex items-center gap-2 rounded-xl px-3 py-2 text-sm hover:bg-white/10"><Briefcase className="size-4" aria-hidden /> {t("Job seeker")}</Link>
        <Link href="/register?role=recruiter" className="flex items-center gap-2 rounded-xl px-3 py-2 text-sm hover:bg-white/10"><UserCheck className="size-4" aria-hidden /> {t("Recruiter")}</Link>
      </div>
    </details>
  );
}

export function Landing({ fontClass }: { fontClass: string }) {
  const { t } = useT();
  const { user } = useAuth();
  const headline = t("Your truthful AI career agent").split(" ");
  const year = new Date().getFullYear();

  return (
    <div className={cn(s.root, fontClass, "min-h-screen")}>
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-full focus:bg-white focus:px-4 focus:py-2 focus:text-black">{t("Skip to content")}</a>

      {/* Nav */}
      <header className="fixed inset-x-0 top-0 z-40 px-4 pt-4">
        <nav aria-label={t("Main")} className={cn(s.glass, "mx-auto flex max-w-6xl items-center gap-3 rounded-full bg-black/40 py-2 pl-5 pr-2")}>
          <Link href="/home" className="text-lg font-semibold tracking-tight">Saige AI</Link>
          <ul className="ml-6 hidden items-center gap-1 lg:flex">
            {NAV.map(([h, l]) => <li key={h}><a href={h} className="rounded-full px-3 py-1.5 text-sm text-white/75 hover:text-white">{t(l)}</a></li>)}
          </ul>
          <div className="ml-auto flex items-center gap-2">
            <div className="hidden sm:block"><LanguageSelect /></div>
            {user ? (
              <Link href="/" className="rounded-full bg-white px-4 py-2 text-sm font-medium text-black">{t("Open dashboard")}</Link>
            ) : (
              <>
                <Link href="/login" className="hidden rounded-full px-3 py-2 text-sm text-white/85 hover:text-white sm:inline">{t("Sign in")}</Link>
                <GetStarted t={t} />
              </>
            )}
          </div>
        </nav>
      </header>

      <main id="main">
        {/* Hero */}
        <section aria-labelledby="hero-title" className="relative isolate flex min-h-[100svh] items-center overflow-hidden px-4 pb-16 pt-32">
          <Starfield className="absolute inset-0 -z-10 size-full" />
          <div aria-hidden className="absolute inset-x-0 bottom-0 -z-10 h-40 bg-gradient-to-b from-transparent to-black" />
          <div className="mx-auto w-full max-w-6xl text-center">
            <div className={s.fade}>
              <Pill><span className="rounded-full bg-white px-2 py-0.5 text-[11px] font-semibold text-black">{t("New")}</span> {t("Portfolio websites from your verified profile")}</Pill>
            </div>
            <h1 id="hero-title" className={cn(s.serif, "mx-auto mt-7 max-w-4xl text-[44px] leading-[1.02] sm:text-6xl md:text-8xl")}>
              {headline.map((w, i) => (
                <span key={`${w}-${i}`} className={s.word} style={{ animationDelay: `${120 + i * 90}ms` }}>{w}{i < headline.length - 1 ? " " : ""}</span>
              ))}
            </h1>
            <p className={cn(s.fade, "mx-auto mt-6 max-w-2xl text-base text-white/75 md:text-lg")} style={{ animationDelay: "600ms" }}>
              {t("Saige finds the right jobs, writes ATS-ready resumes from facts you have verified, tracks every application and reaches recruiters, and asks before it acts on your behalf.")}
            </p>
            <div className={cn(s.fade, "mt-9 flex flex-wrap items-center justify-center gap-3")} style={{ animationDelay: "750ms" }}>
              <Link href="/register" className="rounded-full bg-white px-6 py-3 text-sm font-medium text-black">{t("Get started free")}</Link>
              <Link href="/login" className={cn(s.glass, "rounded-full px-6 py-3 text-sm")}>{t("Sign in")}</Link>
            </div>
            <div className={cn(s.fade, "mt-4 flex flex-wrap justify-center gap-2 text-sm text-white/70")} style={{ animationDelay: "850ms" }}>
              <Link href="/register?role=jobseeker" className="underline-offset-4 hover:text-white hover:underline">{t("I'm a job seeker")}</Link>
              <span aria-hidden>·</span>
              <Link href="/register?role=recruiter" className="underline-offset-4 hover:text-white hover:underline">{t("I'm a recruiter")}</Link>
            </div>

            <ul className="mx-auto mt-14 grid max-w-5xl grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
              {STATS.map((x, i) => (
                <li key={x.l} className={cn(s.glass, s.fade, "rounded-3xl px-4 py-5 text-left", i === 4 && "col-span-2 sm:col-span-1")} style={{ animationDelay: `${950 + i * 90}ms` }}>
                  <p className={cn(s.serif, "text-4xl")}>{x.v}</p>
                  <p className="mt-1 text-sm text-white/70">{t(x.l)}</p>
                </li>
              ))}
            </ul>
          </div>
        </section>

        {/* Connects with */}
        <section aria-label={t("Connects with")} className={cn(s.lazy, "border-y border-white/10 px-4 py-10")}>
          <p className="mb-6 text-center text-xs uppercase tracking-[0.2em] text-white/50">{t("Connects with the tools you already use")}</p>
          <ul className="mx-auto flex max-w-5xl flex-wrap items-center justify-center gap-x-10 gap-y-4">
            {CONNECTS.map((c) => <li key={c} className="text-lg font-medium text-white/55">{c}</li>)}
          </ul>
        </section>

        {/* What we do */}
        <section id="what" aria-labelledby="what-title" className={cn(s.lazy, "scroll-mt-24 px-4 py-24")}>
          <SectionHead id="what-title" eyebrow={t("What we do")} title={t("Everything your job search needs, in one agent")} />
          <ul className="mx-auto grid max-w-6xl gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {CAPABILITIES.map((c, i) => (
              <Reveal as="li" key={c.t} delay={(i % 4) * 80} className={cn(s.glass, "flex flex-col rounded-3xl p-6")}>
                <span className={cn(s.glass, "grid size-11 place-items-center rounded-2xl")}><c.i className="size-5" aria-hidden /></span>
                <h3 className="mt-5 text-lg font-medium">{t(c.t)}</h3>
                <p className="mt-2 flex-1 text-sm leading-relaxed text-white/70">{t(c.d)}</p>
                <div className="mt-5 flex flex-wrap gap-2">{c.tags.map((g) => <Pill key={g}>{t(g)}</Pill>)}</div>
              </Reveal>
            ))}
          </ul>
        </section>

        {/* How it works */}
        <section id="how" aria-labelledby="how-title" className={cn(s.lazy, "scroll-mt-24 px-4 py-24")}>
          <SectionHead id="how-title" eyebrow={t("How it works")} title={t("From resume to offer in four steps")} />
          <ol className="mx-auto grid max-w-6xl gap-4 md:grid-cols-2 lg:grid-cols-4">
            {STEPS.map((x, i) => (
              <Reveal as="li" key={x.t} delay={i * 90} className={cn(s.glass, "rounded-3xl p-6")}>
                <p className={cn(s.serif, "text-5xl text-white/60")}>0{i + 1}</p>
                <h3 className="mt-4 text-lg font-medium">{t(x.t)}</h3>
                <p className="mt-2 text-sm leading-relaxed text-white/70">{t(x.d)}</p>
              </Reveal>
            ))}
          </ol>
        </section>

        {/* Seekers vs recruiters */}
        <section aria-labelledby="sides-title" className={cn(s.lazy, "px-4 py-24")}>
          <SectionHead id="sides-title" eyebrow={t("Who it's for")} title={t("Built for both sides of hiring")} />
          <div className="mx-auto grid max-w-5xl gap-4 md:grid-cols-2">
            {[{ h: "For job seekers", items: SEEKERS, cta: "Join as a job seeker", href: "/register?role=jobseeker", I: Briefcase },
              { h: "For recruiters", items: RECRUITERS, cta: "Join as a recruiter", href: "/register?role=recruiter", I: UserCheck }].map((col, i) => (
              <Reveal key={col.h} delay={i * 100} className={cn(s.glass, "flex flex-col rounded-3xl p-7")}>
                <col.I className="size-6" aria-hidden />
                <h3 className={cn(s.serif, "mt-4 text-3xl")}>{t(col.h)}</h3>
                <ul className="mt-5 flex-1 space-y-3">
                  {col.items.map((x) => <li key={x} className="flex gap-3 text-sm text-white/80"><Check className="mt-0.5 size-4 shrink-0" aria-hidden />{t(x)}</li>)}
                </ul>
                <Link href={col.href} className="mt-7 self-start rounded-full bg-white px-5 py-2.5 text-sm font-medium text-black">{t(col.cta)}</Link>
              </Reveal>
            ))}
          </div>
        </section>

        {/* Promise */}
        <section id="promise" aria-labelledby="promise-title" className={cn(s.lazy, "scroll-mt-24 px-4 py-24")}>
          <SectionHead id="promise-title" eyebrow={t("Our promise")} title={t("Truthful by design")} />
          <ul className="mx-auto grid max-w-6xl gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {PROMISE.map((p, i) => (
              <Reveal as="li" key={p.t} delay={i * 80} className={cn(s.glass, "rounded-3xl p-6")}>
                <p.i className="size-6" aria-hidden />
                <h3 className="mt-4 text-lg font-medium">{t(p.t)}</h3>
                <p className="mt-2 text-sm leading-relaxed text-white/70">{t(p.d)}</p>
              </Reveal>
            ))}
          </ul>
        </section>

        {/* About */}
        <section id="about" aria-labelledby="about-title" className={cn(s.lazy, "scroll-mt-24 px-4 py-24")}>
          <Reveal className={cn(s.glass, "mx-auto max-w-4xl rounded-[2rem] p-8 md:p-12")}>
            <Pill>{t("About us")}</Pill>
            <h2 id="about-title" className={cn(s.serif, "mt-5 text-4xl md:text-5xl")}>{t("Why we built Saige")}</h2>
            <p className="mt-5 text-base leading-relaxed text-white/75 md:text-lg">
              {t("Job hunting rewards whoever sends the most applications, and that pushes people to exaggerate. We think an AI agent should do the busywork for you while keeping every word true. Saige is that agent: one candidate at a time, honest by default.")}
            </p>
            <p className="mt-6 text-sm text-white/70">{t("Contact us")}: <a href={`mailto:${CONTACT_EMAIL}`} className="text-white underline underline-offset-4">{CONTACT_EMAIL}</a></p>
          </Reveal>
        </section>

        {/* FAQ */}
        <section id="faq" aria-labelledby="faq-title" className={cn(s.lazy, "scroll-mt-24 px-4 py-24")}>
          <SectionHead id="faq-title" eyebrow={t("FAQ")} title={t("Questions, answered")} />
          <div className="mx-auto max-w-3xl space-y-3">
            {FAQ.map((f) => (
              <details key={f.q} className={cn(s.glass, "group rounded-2xl px-5 py-4")}>
                <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-base font-medium [&::-webkit-details-marker]:hidden">
                  {t(f.q)} <ChevronDown className="size-4 shrink-0 transition-transform group-open:rotate-180" aria-hidden />
                </summary>
                <p className="mt-3 text-sm leading-relaxed text-white/70">{t(f.a)}</p>
              </details>
            ))}
          </div>
        </section>

        {/* Final CTA */}
        <section aria-labelledby="cta-title" className={cn(s.lazy, "px-4 py-24")}>
          <Reveal className={cn(s.glass, "mx-auto max-w-5xl rounded-[2rem] px-6 py-14 text-center")}>
            <h2 id="cta-title" className={cn(s.serif, "mx-auto max-w-3xl text-4xl md:text-6xl")}>{t("Let Saige run your job search, honestly.")}</h2>
            <p className="mt-4 text-white/70">{t("Setup takes about 3 minutes.")}</p>
            <div className="mt-8 flex flex-wrap justify-center gap-3">
              <Link href="/register" className="rounded-full bg-white px-6 py-3 text-sm font-medium text-black">{t("Get started free")}</Link>
              <Link href="/download" className="rounded-full border border-white/25 px-6 py-3 text-sm font-medium text-white">{t("Get the app")}</Link>
              <Link href="/login" className={cn(s.glass, "rounded-full px-6 py-3 text-sm")}>{t("Sign in")}</Link>
            </div>
          </Reveal>
        </section>
      </main>

      <footer className="border-t border-white/10 px-4 py-10">
        <div className="mx-auto flex max-w-6xl flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-lg font-semibold">Saige AI</p>
            <p className="mt-1 text-sm text-white/60">© {year} Saige AI. {t("All rights reserved.")}</p>
          </div>
          <div className="flex flex-wrap items-center gap-5 text-sm text-white/70">
            <Link href="/download" className="hover:text-white">{t("Get the app")}</Link>
            <Link href="/privacy" className="hover:text-white">{t("Privacy")}</Link>
            <Link href="/terms" className="hover:text-white">{t("Terms")}</Link>
            <a href={`mailto:${CONTACT_EMAIL}`} className="hover:text-white">{t("Contact")}</a>
            <div className="sm:hidden"><LanguageSelect /></div>
          </div>
        </div>
      </footer>
    </div>
  );
}
