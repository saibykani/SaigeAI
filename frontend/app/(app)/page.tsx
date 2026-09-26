"use client";

import {
  AlertTriangle,
  ArrowRight,
  Briefcase,
  CalendarCheck,
  CheckCircle2,
  ClipboardCheck,
  MailOpen,
  Pause,
  Play,
  Search,
  Send,
  Target,
  ThumbsDown,
  Trophy,
  Users,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Notice } from "@/components/app-shell";
import { FunnelChart } from "@/components/funnel-chart";
import { CountUp, ProgressRing } from "@/components/motion";
import { StatTile, type Slot } from "@/components/stat-tile";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { request } from "@/services/api";
import type { AutomationSettings, Dashboard } from "@/types/api";
import { cn } from "@/utils/cn";

type TileKey = keyof Dashboard["today"];
const TILES: { key: TileKey; label: string; icon: typeof Search; slot: Slot | null; href?: string }[] = [
  { key: "jobs_found", label: "Jobs found", icon: Search, slot: 1, href: "/jobs" },
  { key: "relevant_jobs", label: "Relevant jobs", icon: Target, slot: 2, href: "/jobs" },
  { key: "applications_ready", label: "Applications ready", icon: ClipboardCheck, slot: 3 },
  { key: "applications_submitted", label: "Submitted", icon: Send, slot: 4 },
  { key: "recruiters_contacted", label: "Recruiters contacted", icon: Users, slot: 5 },
  { key: "replies", label: "Replies", icon: MailOpen, slot: 6 },
  { key: "interviews", label: "Interviews", icon: CalendarCheck, slot: 7 },
  { key: "offers", label: "Offers", icon: Trophy, slot: 8 },
  // Rejections are de-emphasised (neutral) rather than given a ninth hue.
  { key: "rejections", label: "Rejections", icon: ThumbsDown, slot: null },
];

function greeting() {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
}

function NeutralTile({ label, value, icon: Icon, delay }: { label: string; value: number; icon: typeof Search; delay: number }) {
  return (
    <div className="glass lift animate-rise relative h-full overflow-hidden rounded-2xl border p-4 shadow-[var(--shadow-card)]" style={{ animationDelay: `${delay}ms` }}>
      <span className="grid size-9 place-items-center rounded-xl bg-muted text-muted-foreground">
        <Icon className="size-[18px]" aria-hidden />
      </span>
      <p className="mt-4 text-[28px] font-semibold leading-none tracking-tight">
        <CountUp value={value} />
      </p>
      <p className="mt-1.5 text-[13px] text-muted-foreground">{label}</p>
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <div className="flex flex-col gap-6">
      <div className="skeleton h-52 rounded-3xl" />
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5 xl:grid-cols-9">
        {Array.from({ length: 9 }).map((_, i) => (
          <div key={i} className="skeleton h-32 rounded-2xl" />
        ))}
      </div>
      <div className="skeleton h-80 rounded-2xl" />
    </div>
  );
}

export default function CommandCenter() {
  const { user } = useAuth();
  const { data, error, loading, reload } = useApi<Dashboard>("/analytics/dashboard");
  const [toggling, setToggling] = useState(false);

  async function togglePause() {
    if (!data) return;
    setToggling(true);
    try {
      await request<AutomationSettings>(data.automation.paused_all ? "/automation/resume-all" : "/automation/pause-all", { method: "POST" });
      await reload();
    } finally {
      setToggling(false);
    }
  }

  if (error) return <Notice tone="error">{error}</Notice>;
  if (loading && !data) return <DashboardSkeleton />;
  if (!data) return null;

  const paused = data.automation.paused_all;
  const firstName = (user?.name || "").split(" ")[0];
  const actions = [
    { n: data.action_required.applications_need_approval, label: "applications need approval", href: "/applications" },
    { n: data.action_required.followups_due, label: "follow-ups due", href: null },
    { n: data.action_required.upcoming_interviews, label: "upcoming interviews", href: null },
    { n: data.action_required.profile_changes_pending, label: "profile changes pending", href: null },
    { n: data.action_required.unknown_profile_fields, label: "profile fields are UNKNOWN", href: "/profile" },
  ];
  const pending = actions.filter((a) => a.n > 0);

  return (
    <div className="flex flex-col gap-8">
      {/* ------------------------------------------------ hero */}
      <section className="animate-gradient relative overflow-hidden rounded-3xl bg-[image:var(--hero-gradient)] p-7 text-white shadow-[var(--shadow-lift)] md:p-10">
        <div aria-hidden className="animate-float pointer-events-none absolute -right-16 -top-20 size-72 rounded-full bg-white/15 blur-3xl" />
        <div aria-hidden className="animate-float pointer-events-none absolute -bottom-24 left-1/3 size-72 rounded-full bg-fuchsia-300/20 blur-3xl" style={{ animationDelay: "-4s" }} />
        <div className="relative flex flex-col gap-8 lg:flex-row lg:items-center lg:justify-between">
          <div className="max-w-xl">
            <p className="text-sm font-medium text-white/80">
              {greeting()}
              {firstName ? `, ${firstName}` : ""}
            </p>
            <h1 className="mt-2 text-3xl font-semibold leading-tight tracking-tight md:text-[42px]">Your career command center</h1>
            <p className="mt-3 text-[15px] text-white/85">
              <span className="font-semibold text-white"><CountUp value={data.totals.jobs} /></span> jobs tracked ·{" "}
              <span className="font-semibold text-white"><CountUp value={data.high_match_jobs.length} /></span> high matches ·{" "}
              <span className="font-semibold text-white"><CountUp value={data.totals.resumes} /></span> active resumes
            </p>
            <div className="mt-6 flex flex-wrap gap-2">
              <Link href="/jobs" className={buttonVariants({ className: "bg-white text-[#1a1a1a] hover:bg-white/90" })}>
                Find jobs <ArrowRight />
              </Link>
              <Button
                onClick={togglePause}
                disabled={toggling}
                className={cn("border border-white/40 bg-white/10 text-white backdrop-blur hover:bg-white/20", paused && "bg-white/25")}
              >
                {paused ? <Play /> : <Pause />}
                {paused ? "Resume automation" : "Pause all automation"}
              </Button>
            </div>
          </div>
          {/* The single hero figure of this view: profile readiness */}
          <div className="flex items-center gap-5 rounded-2xl bg-white/10 p-5 backdrop-blur-md">
            <ProgressRing value={data.profile.completeness} size={112} stroke={10}>
              <span className="text-[30px] font-semibold tracking-tight">
                <CountUp value={data.profile.completeness} suffix="%" />
              </span>
            </ProgressRing>
            <div>
              <p className="text-sm font-medium">Profile readiness</p>
              <p className="mt-1 max-w-[12rem] text-xs text-white/80">Every AI output is limited to what your verified profile contains.</p>
              <Link href="/profile" className="mt-3 inline-flex items-center gap-1 text-xs font-medium underline-offset-4 hover:underline">
                Complete profile <ArrowRight className="size-3" />
              </Link>
            </div>
          </div>
        </div>
      </section>

      {paused && <Notice tone="warning">All automation is paused. No agent will discover, apply, email or update anything until you resume.</Notice>}

      {/* ------------------------------------------------ today's KPIs */}
      <section aria-labelledby="today">
        <div className="mb-4 flex items-baseline justify-between">
          <h2 id="today" className="text-xl font-semibold tracking-tight">Today</h2>
          <span className="text-xs text-muted-foreground">
            Automation mode <span className="font-medium capitalize text-foreground">{data.automation.mode}</span>
          </span>
        </div>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5 xl:grid-cols-9">
          {TILES.map((t, i) =>
            t.slot ? (
              <StatTile key={t.key} label={t.label} value={data.today[t.key]} icon={t.icon} slot={t.slot} href={t.href} delay={i * 50} />
            ) : (
              <NeutralTile key={t.key} label={t.label} value={data.today[t.key]} icon={t.icon} delay={i * 50} />
            ),
          )}
        </div>
      </section>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="animate-rise lg:col-span-2" style={{ animationDelay: "150ms" }}>
          <CardHeader>
            <CardTitle className="text-lg">Application funnel</CardTitle>
            <CardDescription>How many records reached each stage. Descriptive only.</CardDescription>
          </CardHeader>
          <CardContent>
            <FunnelChart data={data.funnel} />
          </CardContent>
        </Card>

        <Card className="animate-rise" style={{ animationDelay: "220ms" }}>
          <CardHeader>
            <CardTitle className="text-lg">Action required</CardTitle>
          </CardHeader>
          <CardContent>
            {pending.length === 0 ? (
              <div className="flex flex-col items-center gap-2 py-8 text-center">
                <span className="animate-pop grid size-12 place-items-center rounded-full bg-success/15 text-success">
                  <CheckCircle2 className="size-6" />
                </span>
                <p className="text-sm text-muted-foreground">You&apos;re all caught up.</p>
              </div>
            ) : (
              <ul className="flex flex-col gap-1">
                {pending.map((a, i) => {
                  const inner = (
                    <span className="flex items-center gap-3">
                      <span className="grid size-8 shrink-0 place-items-center rounded-full bg-warning/15 text-warning">
                        <AlertTriangle className="size-4" />
                      </span>
                      <span className="text-sm">
                        <span className="font-semibold">{a.n}</span> {a.label}
                      </span>
                    </span>
                  );
                  return (
                    <li key={a.label} className="animate-rise" style={{ animationDelay: `${300 + i * 60}ms` }}>
                      {a.href ? (
                        <Link href={a.href} className="block rounded-xl p-2 transition-colors hover:bg-muted">{inner}</Link>
                      ) : (
                        <div className="p-2">{inner}</div>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card className="animate-rise lg:col-span-3" style={{ animationDelay: "280ms" }}>
          <CardHeader className="flex-row items-center justify-between">
            <div>
              <CardTitle className="text-lg">High-match jobs</CardTitle>
              <CardDescription>85% match or better.</CardDescription>
            </div>
            <Link href="/jobs" className={buttonVariants({ variant: "ghost", size: "sm" })}>
              All jobs <ArrowRight />
            </Link>
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
                {data.high_match_jobs.map((j, i) => (
                  <li key={j.id} className="animate-rise" style={{ animationDelay: `${350 + i * 60}ms` }}>
                    <Link href={`/jobs/${j.id}`} className="lift flex items-center gap-4 rounded-2xl border bg-card-solid/60 p-4">
                      <span className="grid size-12 shrink-0 place-items-center rounded-2xl bg-success/15 text-sm font-semibold text-success">{j.score}%</span>
                      <span className="min-w-0">
                        <span className="block truncate font-medium">{j.title}</span>
                        <span className="block truncate text-sm text-muted-foreground">{j.company}</span>
                      </span>
                      <Badge variant="success" className="ml-auto hidden sm:inline-flex">Highly relevant</Badge>
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
