"use client";

import { AlertTriangle, CheckCircle2, Pause, Play } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Notice, PageHeader } from "@/components/app-shell";
import { FunnelChart } from "@/components/funnel-chart";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useApi } from "@/hooks/use-api";
import { request } from "@/services/api";
import type { AutomationSettings, Dashboard } from "@/types/api";
import { cn } from "@/utils/cn";

const TODAY: { key: keyof Dashboard["today"]; label: string }[] = [
  { key: "jobs_found", label: "Jobs Found" },
  { key: "relevant_jobs", label: "Relevant Jobs" },
  { key: "applications_ready", label: "Applications Ready" },
  { key: "applications_submitted", label: "Applications Submitted" },
  { key: "recruiters_contacted", label: "Recruiters Contacted" },
  { key: "replies", label: "Replies" },
  { key: "interviews", label: "Interviews" },
  { key: "rejections", label: "Rejections" },
  { key: "offers", label: "Offers" },
];

export default function CommandCenter() {
  const { data, error, loading, reload } = useApi<Dashboard>("/analytics/dashboard");
  const [toggling, setToggling] = useState(false);

  async function togglePause() {
    if (!data) return;
    setToggling(true);
    try {
      await request<AutomationSettings>(data.automation.paused_all ? "/automation/resume-all" : "/automation/pause-all", {
        method: "POST",
      });
      await reload();
    } finally {
      setToggling(false);
    }
  }

  if (error) return <Notice tone="error">{error}</Notice>;
  if (loading && !data) return <p className="text-sm text-muted-foreground">Loading dashboard…</p>;
  if (!data) return null;

  const paused = data.automation.paused_all;
  const actions = [
    { n: data.action_required.applications_need_approval, label: "applications need approval", href: null },
    { n: data.action_required.followups_due, label: "recruiters need follow-up", href: null },
    { n: data.action_required.upcoming_interviews, label: "upcoming interviews", href: null },
    { n: data.action_required.profile_changes_pending, label: "profile changes pending", href: null },
    { n: data.action_required.unknown_profile_fields, label: "profile fields are UNKNOWN", href: "/profile" },
  ];
  const pending = actions.filter((a) => a.n > 0);

  return (
    <>
      <PageHeader
        title="Command Center"
        description="Everything Saige is doing for your job search today."
        actions={
          <Button variant={paused ? "default" : "destructive"} onClick={togglePause} disabled={toggling}>
            {paused ? <Play /> : <Pause />}
            {paused ? "Resume automation" : "PAUSE ALL AUTOMATION"}
          </Button>
        }
      />

      {paused && (
        <div className="mb-6">
          <Notice tone="warning">All automation is paused. No agent will discover, apply, email or update anything until you resume.</Notice>
        </div>
      )}

      <section aria-labelledby="today" className="mb-6">
        <h2 id="today" className="mb-3 text-xs font-medium uppercase tracking-wider text-muted-foreground">
          Today
        </h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5 xl:grid-cols-9">
          {TODAY.map(({ key, label }) => (
            <Card key={key} className="p-4">
              <p className="text-2xl font-semibold tabular-nums">{data.today[key]}</p>
              <p className="mt-1 text-xs leading-tight text-muted-foreground">{label}</p>
            </Card>
          ))}
        </div>
      </section>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Application Funnel</CardTitle>
            <CardDescription>Counts of records at each stage. Descriptive only.</CardDescription>
          </CardHeader>
          <CardContent>
            <FunnelChart data={data.funnel} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Action Required</CardTitle>
          </CardHeader>
          <CardContent>
            {pending.length === 0 ? (
              <p className="flex items-center gap-2 text-sm text-muted-foreground">
                <CheckCircle2 className="size-4 text-success" /> Nothing needs your attention.
              </p>
            ) : (
              <ul className="flex flex-col gap-2">
                {pending.map((a) => (
                  <li key={a.label} className="flex items-center gap-2 text-sm">
                    <AlertTriangle className="size-4 shrink-0 text-warning" />
                    {a.href ? (
                      <Link href={a.href} className="hover:underline">
                        <span className="font-semibold tabular-nums">{a.n}</span> {a.label}
                      </Link>
                    ) : (
                      <span>
                        <span className="font-semibold tabular-nums">{a.n}</span> {a.label}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>High Match Jobs</CardTitle>
          </CardHeader>
          <CardContent>
            {data.high_match_jobs.length === 0 ? (
              <p className="text-sm text-muted-foreground">No jobs scored yet. Job import and matching arrive in Phase 2.</p>
            ) : (
              <ul className="divide-y">
                {data.high_match_jobs.map((j) => (
                  <li key={j.id} className="flex items-center justify-between py-2 text-sm">
                    <span>
                      {j.title} — <span className="text-muted-foreground">{j.company}</span>
                    </span>
                    <Badge variant="success">{j.score}%</Badge>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Profile Readiness</CardTitle>
            <CardDescription>Every AI output is limited to what your verified profile contains.</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <div className="flex items-baseline justify-between">
              <span className="text-2xl font-semibold tabular-nums">{data.profile.completeness}%</span>
              <span className="text-xs text-muted-foreground">{data.totals.resumes} active resume(s)</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-muted" role="progressbar" aria-valuenow={data.profile.completeness} aria-valuemin={0} aria-valuemax={100}>
              <div
                className={cn("h-full rounded-full", data.profile.completeness >= 80 ? "bg-success" : "bg-primary")}
                style={{ width: `${data.profile.completeness}%` }}
              />
            </div>
            {data.profile.unknown_fields.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {data.profile.unknown_fields.slice(0, 8).map((f) => (
                  <Badge key={f} variant="muted">
                    {f}
                  </Badge>
                ))}
              </div>
            )}
            <div className="flex gap-2">
              <Link href="/profile" className={buttonVariants({ size: "sm", variant: "outline" })}>
                Complete profile
              </Link>
              <Link href="/resumes" className={buttonVariants({ size: "sm", variant: "ghost" })}>
                Upload resume
              </Link>
            </div>
            <p className="text-xs text-muted-foreground">
              Automation mode: <span className="font-medium capitalize text-foreground">{data.automation.mode}</span>
            </p>
          </CardContent>
        </Card>
      </div>
    </>
  );
}
