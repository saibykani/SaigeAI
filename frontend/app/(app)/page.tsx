"use client";

import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Briefcase,
  CalendarCheck,
  CheckCircle2,
  Clock,
  FileText,
  Flame,
  Gauge,
  MapPin,
  MailCheck,
  Pause,
  Play,
  Reply,
  Search,
  Send,
  Sparkles,
  Star,
  Target,
  Trophy,
  UserRound,
  Video,
  Wand2,
} from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { Notice } from "@/components/app-shell";
import { CoachCard, HistoryTable } from "@/components/coach-history";
import { GhostingList, GoalsCard } from "@/components/growth";
import { FunnelChart } from "@/components/funnel-chart";
import { InsightsGrid } from "@/components/insights";
import { CountKpi, RateKpi, TrendKpi } from "@/components/kpi";
import { CountUp, ProgressRing } from "@/components/motion";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { request } from "@/services/api";
import type { AutomationSettings, Dashboard, SchedulerStatus } from "@/types/api";
import { cn } from "@/utils/cn";
import { formatDateTime } from "@/utils/format";

function greeting() {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
}

// A different warm line each visit, tuned to the time of day and weekday. Never claims anything about the user.
const WISHES: Record<string, string[]> = {
  morning: ["Fresh day, fresh openings. Let's find the one that fits you.", "Coffee in hand? Your best matches are waiting below.",
    "Small steps every morning add up to the offer letter.", "Rise and shine, {n}. Today is a great day to hit Apply."],
  afternoon: ["Halfway through the day: one tailored application beats ten generic ones.", "Keep the momentum going, {n}. You're closer than you think.",
    "A quick follow-up this afternoon could be the reply you're waiting for.", "Recruiters are online now. A good time to reach out."],
  evening: ["Wind down with one smart move: check today's new matches.", "Great work today, {n}. Tomorrow's applications are already lined up.",
    "Evenings are perfect for polishing your resume. Saige has suggestions ready.", "Rest well. Saige keeps scanning while you sleep."],
  monday: ["New week, new goals. Set your weekly targets and let's go.", "Monday energy: the first application of the week counts the most."],
  friday: ["Happy Friday, {n}! Send one more application before the weekend.", "Friday wins: review your follow-ups and close the week strong."],
  weekend: ["Weekend mode: a calm time to upgrade your profile.", "Enjoy your weekend, {n}. A small profile tweak now pays off on Monday."],
};
function wish(name?: string) {
  const d = new Date(), h = d.getHours(), day = d.getDay();
  const pool = [...WISHES[h < 12 ? "morning" : h < 17 ? "afternoon" : "evening"],
    ...(day === 1 ? WISHES.monday : day === 5 ? WISHES.friday : day === 0 || day === 6 ? WISHES.weekend : [])];
  return pool[Math.floor(Math.random() * pool.length)].replace("{n}", name || "there");
}

function timeAgo(iso: string): string {
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

function Skeleton() {
  return (
    <div className="flex flex-col gap-6">
      <div className="skeleton h-48 rounded-3xl" />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-3 xl:grid-cols-6">{Array.from({ length: 6 }).map((_, i) => <div key={i} className="skeleton h-44 rounded-2xl" />)}</div>
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">{Array.from({ length: 8 }).map((_, i) => <div key={i} className="skeleton h-24 rounded-2xl" />)}</div>
    </div>
  );
}

export default function DashboardPage() {
  const { user } = useAuth();
  const { data, error, loading, reload } = useApi<Dashboard>("/analytics/dashboard");
  const scheduler = useApi<SchedulerStatus>("/scheduler/status");
  const [toggling, setToggling] = useState(false);

  const hello = useMemo(() => wish((user?.name || "").split(" ")[0]), [user?.name]);
  if (error) return <Notice tone="error">{error}</Notice>;
  if (loading && !data) return <Skeleton />;
  if (!data) return null;

  const paused = data.automation.paused_all;
  const firstName = (user?.name || "").split(" ")[0];
  const t = data.trend;
  const hl = data.health;
  const actions = [
    { n: data.action_required.applications_need_approval, label: "applications need your approval", href: "/applications" },
    { n: hl.followups_due, label: "follow-ups are due", href: "/applications" },
    { n: data.action_required.upcoming_interviews, label: "upcoming interviews", href: "/interviews" },
    { n: data.action_required.profile_changes_pending, label: "profile suggestions to review", href: "/profiles" },
    { n: data.action_required.unknown_profile_fields, label: "profile fields are still UNKNOWN", href: "/profile" },
  ].filter((a) => a.n > 0);

  const sched = scheduler.data;
  const refreshJob = sched?.jobs.find((j) => j.job === "profile_refresh");
  const lastRan = refreshJob?.last_run?.status === "succeeded" ? "✓" : refreshJob?.last_run?.status ? refreshJob.last_run.status : "pending";
  const refreshTime = sched?.profile_schedule?.refresh_time ?? "08:00";
  const tzLabel = sched?.timezone === "Asia/Kolkata" ? "IST" : (sched?.timezone ?? "");

  async function togglePause() {
    setToggling(true);
    try {
      await request<AutomationSettings>(paused ? "/automation/resume-all" : "/automation/pause-all", { method: "POST" });
      await reload();
      void scheduler.reload();
    } finally {
      setToggling(false);
    }
  }

  return (
    <div className="flex flex-col gap-8">
      {/* Greeting */}
      <section className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-4xl font-light tracking-[-0.03em] md:text-[52px] md:leading-[1.05]">{greeting()}{firstName ? `, ${firstName}` : ""}</h1>
          <p className="mt-2 text-lg text-foreground/80">{hello}</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Next profile refresh {refreshTime} {tzLabel} · last ran {lastRan}{sched && sched.naukri_streak > 0 ? ` · Naukri streak ${sched.naukri_streak}d` : ""}
          </p>
          <div className="mt-4 flex flex-wrap gap-2.5">
            {[["Jobs for you", "/jobs"], ["Career portals", "/careers"], ["Apply by email", "/studio/apply"], ["Recruiters", "/recruiters"], ["Optimize profiles", "/profiles"]].map(([l, h], i) => (
              <Link key={h} href={h} className="inline-flex items-center gap-1.5 rounded-full border bg-card px-4 py-2 text-sm hover:bg-muted">
                {i === 0 && <MapPin className="size-4 text-primary" />}{l}
              </Link>
            ))}
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={togglePause} disabled={toggling}>{paused ? <Play /> : <Pause />} {paused ? "Resume" : "Pause"}</Button>
          <Link href="/jobs" className={buttonVariants({ size: "lg" })}><Search /> Find jobs</Link>
        </div>
      </section>

      {data.profile.completeness < 60 && (
        <section className="flex flex-col gap-3 rounded-3xl border border-primary/40 bg-accent/40 p-5 sm:flex-row sm:items-center">
          <div className="flex-1">
            <p className="text-lg">Finish setting up · {data.profile.completeness}% done</p>
            <p className="text-sm text-muted-foreground">Upload your resume and pick the jobs you want. It takes about 3 minutes.</p>
          </div>
          <Link href="/welcome" className={buttonVariants({ size: "lg" })}>Continue setup</Link>
        </section>
      )}

      {/* Next step */}
      {(() => {
        const top = data.high_match_jobs[0];
        const a = data.action_required;
        const step = a.applications_need_approval ? { t: `Approve ${a.applications_need_approval} application${a.applications_need_approval > 1 ? "s" : ""}`, d: "Prepared and waiting for your OK.", h: "/applications", b: "Review" }
          : top ? { t: "Apply to your best match", d: `${top.title} at ${top.company} matches ${top.score}%. It takes one tap.`, h: `/jobs/${top.id}`, b: "View and apply" }
          : { t: "Find your next job", d: "Saige scans portals and career pages daily.", h: "/jobs", b: "Find jobs" };
        return (
          <section className="flex flex-col gap-4 rounded-3xl border bg-card p-5 sm:flex-row sm:items-center">
            <span className="grid size-14 shrink-0 place-items-center rounded-full bg-primary text-primary-foreground"><ArrowRight /></span>
            <div className="min-w-0 flex-1">
              <p className="text-sm text-primary">Your next step</p>
              <p className="text-xl">{step.t}</p>
              <p className="text-sm text-muted-foreground">{step.d}</p>
            </div>
            <Link href={step.h} className={buttonVariants({ size: "lg" })}>{step.b}</Link>
          </section>
        );
      })()}

      {/* Headline numbers */}
      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Link href="/jobs" className="rounded-3xl bg-primary p-5 text-primary-foreground">
          <p className="flex items-center gap-2 text-sm"><Briefcase className="size-5" /> Jobs tracked</p>
          <p className="mt-4 text-5xl font-light"><CountUp value={data.totals.jobs} /></p>
          <p className="mt-2 text-sm opacity-90">{data.totals.strong_matches ?? data.high_match_jobs.length} strong matches (85%+)</p>
        </Link>
        {[
          { l: "Applications sent", v: data.totals.applications_sent ?? data.totals.applications, s: `${data.totals.applications} tracked in total`, h: "/applications", I: FileText },
          { l: "Interviews", v: data.totals.interviews, s: "Scheduled or completed", h: "/interviews", I: Star },
          { l: "Profile strength", v: data.profile.completeness, s: `${data.profile.unknown_fields.length} parts to finish`, h: "/profile", I: UserRound, pct: true },
        ].map(({ l, v, s, h, I, pct }) => (
          <Link key={l} href={h} className="rounded-3xl border bg-card p-5">
            <p className="flex items-center gap-2 text-sm text-muted-foreground"><I className="size-5 text-primary" /> {l}</p>
            <p className="mt-4 text-5xl font-light text-primary"><CountUp value={v} suffix={pct ? "%" : ""} /></p>
            <p className="mt-2 text-sm text-muted-foreground">{s}</p>
          </Link>
        ))}
      </section>

      <div className="grid gap-6 xl:grid-cols-2">
        <GoalsCard compact />
        <GhostingList limit={4} />
      </div>

      <div className="grid gap-6 xl:grid-cols-[1fr_1.4fr]">
        <CoachCard />
        <HistoryTable />
      </div>

      {paused && <Notice tone="warning">All automation is paused. No agent will discover, apply, email or update anything until you resume.</Notice>}

      {/* Today, with 7-day trends */}
      <section aria-labelledby="today">
        <div className="mb-4 flex items-baseline justify-between">
          <h2 id="today" className="text-xl font-semibold tracking-tight">Today</h2>
          <span className="text-xs text-muted-foreground">Automation mode <b className="font-medium capitalize text-foreground">{data.automation.mode}</b></span>
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
          <TrendKpi label="Jobs found" series={t.jobs_found} icon={Search} href="/jobs" delay={0} tone="green" />
          <TrendKpi label="Relevant jobs" series={t.relevant_jobs} icon={Target} href="/jobs" delay={50} tone="orange" />
          <TrendKpi label="Applied" series={t.applications_submitted} icon={Send} href="/applications" delay={100} tone="purple" />
          <TrendKpi label="Interviews" series={t.interviews} icon={CalendarCheck} href="/interviews" delay={150} tone="yellow" />
          <TrendKpi label="AI documents" series={t.documents} icon={Wand2} delay={200} tone="mint" />
          <TrendKpi label="Profile suggestions" series={t.profile_changes} icon={Sparkles} href="/profiles" delay={250} tone="red" />
        </div>
      </section>

      {/* Pipeline health */}
      <section aria-labelledby="health">
        <h2 id="health" className="mb-4 text-xl font-semibold tracking-tight">Pipeline health</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <CountKpi label="Active applications" value={hl.active_applications} icon={Briefcase} href="/applications" delay={0} tone="purple" />
          <RateKpi label="Response rate" value={hl.response_rate} hint="Replies ÷ applications sent" icon={Reply} delay={40} tone="teal" />
          <RateKpi label="Interview rate" value={hl.interview_rate} hint="Interviews ÷ applications sent" icon={Video} delay={80} tone="yellow" />
          <RateKpi label="Offer rate" value={hl.offer_rate} hint="Offers ÷ applications sent" icon={Trophy} delay={120} tone="green" />
          <RateKpi label="Average job match" value={hl.avg_match} hint="Across all tracked jobs" icon={Gauge} delay={160} tone="orange" />
          <RateKpi label="Average ATS score" value={hl.avg_ats} hint="Tailored resumes" icon={FileText} delay={200} tone="lime" />
          <CountKpi label="Follow-ups due" value={hl.followups_due} icon={MailCheck} href="/applications" delay={240} tone="red" />
          <CountKpi label="Tailored resumes · cover letters" value={hl.tailored_resumes + hl.cover_letters} hint={`${hl.tailored_resumes} resumes · ${hl.cover_letters} letters`} icon={Wand2} delay={280} tone="mint" />
        </div>
      </section>

      <section aria-labelledby="market">
        <h2 id="market" className="mb-4 text-xl font-semibold tracking-tight">Your market &amp; pipeline</h2>
        <InsightsGrid compact />
      </section>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="animate-rise lg:col-span-2" style={{ animationDelay: "120ms" }}>
          <CardHeader>
            <CardTitle className="text-lg">Application funnel</CardTitle>
            <CardDescription>How many records reached each stage.</CardDescription>
          </CardHeader>
          <CardContent><FunnelChart data={data.funnel} /></CardContent>
        </Card>

        <Card className="animate-rise" style={{ animationDelay: "180ms" }}>
          <CardHeader><CardTitle className="text-lg">Action required</CardTitle></CardHeader>
          <CardContent>
            {actions.length === 0 ? (
              <div className="flex flex-col items-center gap-2 py-8 text-center">
                <span className="animate-pop grid size-12 place-items-center rounded-full bg-success/15 text-success"><CheckCircle2 className="size-6" /></span>
                <p className="text-sm text-muted-foreground">You&apos;re all caught up.</p>
              </div>
            ) : (
              <ul className="flex flex-col gap-1">
                {actions.map((a, i) => (
                  <li key={a.label} className="animate-rise" style={{ animationDelay: `${240 + i * 50}ms` }}>
                    <Link href={a.href} className="flex items-center gap-3 rounded-xl p-2 transition-colors hover:bg-muted">
                      <span className="grid size-8 shrink-0 place-items-center rounded-full bg-warning/15 text-warning"><AlertTriangle className="size-4" /></span>
                      <span className="text-sm"><b className="font-semibold">{a.n}</b> {a.label}</span>
                      <ArrowRight className="ml-auto size-4 text-muted-foreground" />
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card className="animate-rise" style={{ animationDelay: "220ms" }}>
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle className="text-lg">Upcoming interviews</CardTitle>
            <Link href="/interviews" className="text-xs text-muted-foreground hover:text-foreground">All</Link>
          </CardHeader>
          <CardContent>
            {data.upcoming_interviews.length === 0 ? (
              <p className="py-6 text-center text-sm text-muted-foreground">No interviews scheduled.</p>
            ) : (
              <ul className="flex flex-col gap-3">
                {data.upcoming_interviews.map((i) => (
                  <li key={i.id} className="flex items-center gap-3">
                    <span className="grid size-11 shrink-0 place-items-center rounded-xl border bg-muted/60 text-center leading-none">
                      <span><span className="block text-[10px] uppercase text-muted-foreground">{new Date(i.scheduled_at).toLocaleString(undefined, { month: "short" })}</span><b className="text-base">{new Date(i.scheduled_at).getDate()}</b></span>
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">{i.role} · {i.company}</p>
                      <p className="text-xs text-muted-foreground">{i.round || "Interview"} · {formatDateTime(i.scheduled_at)}</p>
                    </div>
                    {i.meeting_url && <a href={i.meeting_url} target="_blank" rel="noopener noreferrer" className="text-xs font-medium text-primary hover:underline">Join</a>}
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card className="animate-rise" style={{ animationDelay: "260ms" }}>
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle className="text-lg">Skills in demand</CardTitle>
            <Link href="/profile-sync" className="text-xs text-muted-foreground hover:text-foreground">Details</Link>
          </CardHeader>
          <CardContent>
            {data.skills_in_demand.length === 0 ? (
              <p className="py-6 text-center text-sm text-muted-foreground">Add jobs to see which skills recruiters want.</p>
            ) : (
              <ul className="flex flex-col gap-2.5">
                {data.skills_in_demand.map((s, i) => (
                  <li key={s.skill} className="grid grid-cols-[110px_1fr_40px] items-center gap-2 text-sm" title={`${s.jobs} job descriptions · ${s.candidate_has ? "you have it" : "gap"}`}>
                    <span className="truncate">{s.skill}</span>
                    <span className="h-2 overflow-hidden rounded-full bg-muted">
                      <span className="animate-grow-x block h-full rounded-full" style={{ width: `${s.pct}%`, background: s.candidate_has ? "var(--primary)" : "color-mix(in srgb, var(--muted-foreground) 45%, transparent)", animationDelay: `${300 + i * 40}ms` }} />
                    </span>
                    <span className="text-right text-xs text-muted-foreground">{Math.round(s.pct)}%</span>
                  </li>
                ))}
              </ul>
            )}
            <p className="mt-3 text-[11px] text-muted-foreground">Solid = in your verified profile · faded = a gap to learn first</p>
          </CardContent>
        </Card>

        <Card className="animate-rise" style={{ animationDelay: "300ms" }}>
          <CardHeader><CardTitle className="flex items-center gap-2 text-lg"><Activity className="size-4" /> Recent activity</CardTitle></CardHeader>
          <CardContent>
            {data.activity.length === 0 ? (
              <p className="py-6 text-center text-sm text-muted-foreground">Nothing yet.</p>
            ) : (
              <ol className="relative ml-1.5 border-l pl-5">
                {data.activity.map((a) => (
                  <li key={a.id} className="relative pb-3.5 last:pb-0">
                    <span className="absolute -left-[25px] top-1.5 size-2 rounded-full bg-primary" aria-hidden />
                    <p className="text-sm">{a.label}</p>
                    <p className="text-xs text-muted-foreground">{timeAgo(a.at)}</p>
                  </li>
                ))}
              </ol>
            )}
          </CardContent>
        </Card>

        <Card className="animate-rise lg:col-span-3" style={{ animationDelay: "340ms" }}>
          <CardHeader className="flex-row items-center justify-between">
            <div>
              <CardTitle className="text-lg">High-match jobs</CardTitle>
              <CardDescription>85% match or better.</CardDescription>
            </div>
            <Link href="/jobs" className={buttonVariants({ variant: "ghost", size: "sm" })}>All jobs <ArrowRight /></Link>
          </CardHeader>
          <CardContent>
            {data.high_match_jobs.length === 0 ? (
              <div className="flex flex-col items-center gap-3 rounded-2xl border border-dashed py-10 text-center">
                <Briefcase className="size-7 text-muted-foreground" />
                <p className="text-sm text-muted-foreground">No high-match jobs yet.</p>
                <Link href="/jobs" className={buttonVariants({ size: "sm" })}>Add jobs</Link>
              </div>
            ) : (
              <ul className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {data.high_match_jobs.map((j) => (
                  <li key={j.id}>
                    <Link href={`/jobs/${j.id}`} className="lift flex items-center gap-4 rounded-2xl border bg-card-solid/60 p-4">
                      <span className="grid size-12 shrink-0 place-items-center rounded-2xl bg-primary text-sm font-semibold text-primary-foreground">{j.score}%</span>
                      <span className="min-w-0">
                        <span className="block truncate font-medium">{j.title}</span>
                        <span className="block truncate text-sm text-muted-foreground">{j.company}</span>
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
