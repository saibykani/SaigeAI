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
  MailCheck,
  Pause,
  Play,
  Reply,
  Search,
  Send,
  Sparkles,
  Target,
  Trophy,
  Video,
  Wand2,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Notice } from "@/components/app-shell";
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
      {/* Hero */}
      <section className="relative overflow-hidden rounded-3xl border p-7 text-white shadow-[var(--shadow-lift)] md:p-9"
        style={{ background: "linear-gradient(135deg, color-mix(in srgb, var(--tone-green) 62%, #021a0f) 0%, color-mix(in srgb, var(--tone-green) 30%, #01100a) 55%, #010a06 100%)" }}>
        <div aria-hidden className="animate-float pointer-events-none absolute -right-24 -top-24 size-80 rounded-full bg-white/10 blur-3xl" />
        {/* Slowly turning 3D rings behind the banner */}
        <div aria-hidden className="hero-rings pointer-events-none absolute -right-10 top-1/2 size-[420px] -translate-y-1/2 opacity-40 [perspective:900px]">
          <span className="hero-ring absolute inset-0 rounded-full border border-white/30" />
          <span className="hero-ring hero-ring-2 absolute inset-10 rounded-full border border-white/25" />
          <span className="hero-ring hero-ring-3 absolute inset-24 rounded-full border border-white/20" />
          <span className="hero-moon absolute left-1/2 top-1/2 size-3 rounded-full bg-white shadow-[0_0_18px_rgba(255,255,255,0.9)]" />
        </div>
        <div aria-hidden className="pointer-events-none absolute inset-0 bg-[radial-gradient(rgba(255,255,255,0.08)_1px,transparent_1px)] [background-size:24px_24px] [mask-image:linear-gradient(to_left,black,transparent_70%)]" />
        <div className="relative flex flex-col gap-8 lg:flex-row lg:items-center lg:justify-between">
          <div className="max-w-2xl">
            <p className="text-sm font-medium text-white/70">{greeting()}{firstName ? `, ${firstName}` : ""}</p>
            <h1 className="mt-1.5 text-3xl font-semibold tracking-tight md:text-[40px] md:leading-tight">Dashboard</h1>
            <div className="mt-4 flex flex-wrap gap-x-6 gap-y-2 text-sm text-white/75">
              <span><b className="text-lg font-semibold text-white"><CountUp value={data.totals.jobs} /></b> jobs tracked</span>
              <span><b className="text-lg font-semibold text-white"><CountUp value={data.totals.applications} /></b> applications</span>
              <span><b className="text-lg font-semibold text-white"><CountUp value={data.totals.interviews} /></b> interviews</span>
              <span><b className="text-lg font-semibold text-white"><CountUp value={data.totals.resumes} /></b> resumes</span>
            </div>

            {/* Scheduler & Streak Status Badge */}
            <div className="mt-4 flex flex-wrap items-center gap-2.5">
              <Link
                href="/profiles?tab=schedule"
                className="inline-flex items-center gap-1.5 rounded-full border border-white/20 bg-white/10 px-3 py-1 text-xs text-white/90 backdrop-blur-sm transition-colors hover:bg-white/20"
              >
                <Clock className="size-3.5" />
                <span>
                  Next profile refresh <b>{refreshTime} {tzLabel}</b> · last ran {lastRan}
                </span>
              </Link>
              {sched && sched.naukri_streak > 0 && (
                <Link
                  href="/profiles?tab=naukri"
                  className="inline-flex items-center gap-1.5 rounded-full border border-white/20 bg-white/10 px-3 py-1 text-xs text-white/90 backdrop-blur-sm transition-colors hover:bg-white/20"
                >
                  <Flame className="size-3.5 text-[var(--tone-orange)]" />
                  <span>Naukri streak: <b>{sched.naukri_streak}d</b></span>
                </Link>
              )}
            </div>

            <div className="mt-6 flex flex-wrap gap-2">
              <Link href="/jobs" className={buttonVariants({ className: "bg-white text-black hover:bg-white/90" })}>Find jobs <ArrowRight /></Link>
              <Link href="/profiles" className={buttonVariants({ className: "border border-white/25 bg-white/10 text-white hover:bg-white/15" })}><Sparkles /> Optimize profiles</Link>
              <Button onClick={togglePause} disabled={toggling} className={cn("border border-white/25 bg-transparent text-white hover:bg-white/10", paused && "bg-white/20")}>
                {paused ? <Play /> : <Pause />} {paused ? "Resume automation" : "Pause all automation"}
              </Button>
            </div>
          </div>
          <div className="flex items-center gap-5 rounded-2xl border border-white/15 bg-white/[0.06] p-5 backdrop-blur-md">
            <ProgressRing value={data.profile.completeness} size={108} stroke={9} trackClass="stroke-white/15" barClass="stroke-white">
              <span className="text-[28px] font-semibold"><CountUp value={data.profile.completeness} suffix="%" /></span>
            </ProgressRing>
            <div>
              <p className="text-sm font-medium">Profile readiness</p>
              <p className="mt-1 max-w-[13rem] text-xs text-white/65">AI outputs use only what your verified profile contains.</p>
              <Link href="/profile" className="mt-3 inline-flex items-center gap-1 text-xs font-medium text-white underline-offset-4 hover:underline">Complete profile <ArrowRight className="size-3" /></Link>
            </div>
          </div>
        </div>
      </section>

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
