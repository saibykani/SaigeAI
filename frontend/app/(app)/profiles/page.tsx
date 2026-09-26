"use client";

import { Check, Clock, ExternalLink, Flame, History, RefreshCw, Sparkles, Zap } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";

import { Notice, PageHeader } from "@/components/app-shell";
import { Loader3D } from "@/components/loader3d";
import { BrandMark, ChangeCard, FIELD_LABEL, PlatformScore, SnapshotEditors } from "@/components/profile-parts";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useApi } from "@/hooks/use-api";
import { request } from "@/services/api";
import type {
  AutomationSettings,
  ProfileChange,
  ProfileSchedule,
  SchedulerJobRun,
  SchedulerStatus,
  SyncOverview,
} from "@/types/api";
import { cn } from "@/utils/cn";
import { formatDate, formatDateTime } from "@/utils/format";

type Tab = "linkedin" | "naukri" | "schedule";

const DAYS_OF_WEEK = [
  { day: 0, label: "Mon" },
  { day: 1, label: "Tue" },
  { day: 2, label: "Wed" },
  { day: 3, label: "Thu" },
  { day: 4, label: "Fri" },
  { day: 5, label: "Sat" },
  { day: 6, label: "Sun" },
];

const TIMEZONES = ["Asia/Kolkata", "Asia/Dubai", "Asia/Singapore", "Europe/London", "Europe/Berlin", "America/New_York", "America/Los_Angeles", "Australia/Sydney"];

/** Human-readable one-liner for a scheduler run result. */
function describeResult(r: Record<string, unknown>): string {
  if (!r || !Object.keys(r).length) return "";
  if (r.skipped) return String(r.skipped);
  if (r.error) return `Error: ${String(r.error)}`;
  if (r.summary) return String(r.summary);
  const parts: string[] = [];
  if (typeof r.changes_created === "number") parts.push(`${r.changes_created} suggestion(s)`);
  if (typeof r.jobs_analyzed === "number") parts.push(`${r.jobs_analyzed} JD(s) analysed`);
  if (typeof r.created === "number") parts.push(r.created ? `micro-edit ready (${FIELD_LABEL[String(r.field)] ?? r.field})` : String(r.note ?? "nothing new today"));
  if (typeof r.new === "number") parts.push(`${r.new} new job(s) from ${r.boards ?? 0} board(s)`);
  if (typeof r.due === "number") parts.push(`${r.due} follow-up(s) due`);
  if (typeof r.fetched === "number") parts.push(`${r.fetched} email(s) checked`);
  return parts.join(" · ");
}

export default function ProfilesPage() {
  // useSearchParams needs a Suspense boundary for static rendering.
  return (
    <Suspense fallback={<div className="grid min-h-[50vh] place-items-center"><Loader3D /></div>}>
      <ProfilesHub />
    </Suspense>
  );
}

function ProfilesHub() {
  const searchParams = useSearchParams();
  const initialTab = (searchParams.get("tab") as Tab) || "linkedin";
  const [tab, setTab] = useState<Tab>(initialTab === "schedule" || initialTab === "naukri" ? initialTab : "linkedin");

  const overview = useApi<SyncOverview>("/profile-sync/overview");
  const changes = useApi<ProfileChange[]>("/profile-changes");
  const scheduler = useApi<SchedulerStatus>("/scheduler/status");
  const history = useApi<SchedulerJobRun[]>("/scheduler/history?limit=25");
  const settings = useApi<AutomationSettings>("/automation/status");

  const [runningJob, setRunningJob] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const [savingSchedule, setSavingSchedule] = useState(false);

  // Local editable schedule state
  const [timezone, setTimezone] = useState("Asia/Kolkata");
  const [scheduleState, setScheduleState] = useState<ProfileSchedule>({
    linkedin_enabled: true,
    naukri_enabled: true,
    refresh_time: "08:00",
    days: [0, 1, 2, 3, 4, 5, 6],
    naukri_daily_freshness: true,
  });

  useEffect(() => {
    if (settings.data?.profile_schedule) setScheduleState(settings.data.profile_schedule);
    if (settings.data?.schedules?.timezone) setTimezone(settings.data.schedules.timezone);
  }, [settings.data]);

  const reloadAll = () => {
    void overview.reload();
    void changes.reload();
    void scheduler.reload();
    void history.reload();
  };

  async function runJob(job: "profile_refresh" | "naukri_freshness" | "job_discovery") {
    setRunningJob(job);
    setMsg(null);
    try {
      const res = await request<{ job: string; status: string; result: Record<string, unknown> }>(`/scheduler/run-now/${job}`, {
        method: "POST",
      });
      const created = (res.result?.changes_created as number) || (res.result?.created as number) || 0;
      if (res.status === "skipped") {
        setMsg({ tone: "error", text: `Job skipped: ${String(res.result?.skipped || "automation paused")}` });
      } else {
        setMsg({
          tone: "success",
          text: created > 0 ? `Completed ${job.replaceAll("_", " ")}: ${created} new suggestion(s) ready.` : `Run completed. No new changes were needed today.`,
        });
      }
      reloadAll();
    } catch (e) {
      setMsg({ tone: "error", text: e instanceof Error ? e.message : "Run failed" });
    } finally {
      setRunningJob(null);
    }
  }

  async function saveSchedule() {
    setSavingSchedule(true);
    setMsg(null);
    try {
      await request<AutomationSettings>("/automation/settings", {
        method: "PUT",
        body: { profile_schedule: scheduleState, ...(settings.data ? { schedules: { ...settings.data.schedules, timezone } } : {}) },
      });
      setMsg({ tone: "success", text: "Profile refresh schedule saved." });
      void settings.reload();
      void scheduler.reload();
    } catch (e) {
      setMsg({ tone: "error", text: e instanceof Error ? e.message : "Failed to save schedule" });
    } finally {
      setSavingSchedule(false);
    }
  }

  const byPlatform = useMemo(() => {
    const all = changes.data ?? [];
    const order = (c: ProfileChange) => (c.applied_at ? 3 : c.approval_status === "USER_REJECTED" ? 4 : c.approval_status === "USER_APPROVED" ? 2 : 1);
    const sorted = [...all].sort((a, b) => order(a) - order(b));
    return {
      linkedin: sorted.filter((c) => c.platform === "linkedin"),
      naukri: sorted.filter((c) => c.platform === "naukri"),
    };
  }, [changes.data]);

  const o = overview.data;
  const s = scheduler.data;
  const streak = s?.naukri_streak ?? 0;

  const liPending = byPlatform.linkedin.filter((c) => !c.applied_at && c.approval_status !== "USER_REJECTED");
  const liApplied = byPlatform.linkedin.filter((c) => !!c.applied_at);
  const nkPending = byPlatform.naukri.filter((c) => !c.applied_at && c.approval_status !== "USER_REJECTED");
  const nkApplied = byPlatform.naukri.filter((c) => !!c.applied_at);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="LinkedIn & Naukri"
        description="Truthful, copy-ready optimizations and daily freshness for your LinkedIn and Naukri profiles. No web scraping, no automated logins."
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant="gradient"
              className="animate-gradient sheen"
              disabled={Boolean(runningJob)}
              onClick={() => runJob("profile_refresh")}
            >
              <RefreshCw className={cn(runningJob === "profile_refresh" && "animate-spin")} />
              {runningJob === "profile_refresh" ? "Refreshing…" : "Run profile refresh"}
            </Button>
            <Button variant="outline" onClick={() => setTab("schedule")}>
              <Clock className="size-4" /> Schedule
            </Button>
          </div>
        }
      />

      {msg && <Notice tone={msg.tone}>{msg.text}</Notice>}

      {/* Tabs */}
      <div className="flex border-b">
        <button
          onClick={() => setTab("linkedin")}
          className={cn(
            "relative flex items-center gap-2.5 px-5 py-3 text-sm font-medium transition-colors",
            tab === "linkedin" ? "text-foreground" : "text-muted-foreground hover:text-foreground",
          )}
        >
          <span className="grid size-5 place-items-center rounded bg-[#0a66c2] text-[10px] font-bold text-white">in</span>
          LinkedIn
          {liPending.length > 0 && (
            <Badge variant="warning" className="px-1.5 py-0 text-[11px]">
              {liPending.length}
            </Badge>
          )}
          {tab === "linkedin" && <span className="absolute inset-x-0 bottom-0 h-0.5 bg-primary" />}
        </button>

        <button
          onClick={() => setTab("naukri")}
          className={cn(
            "relative flex items-center gap-2.5 px-5 py-3 text-sm font-medium transition-colors",
            tab === "naukri" ? "text-foreground" : "text-muted-foreground hover:text-foreground",
          )}
        >
          <span className="grid size-5 place-items-center rounded bg-[#275df5] text-[10px] font-bold text-white">N</span>
          Naukri
          {streak > 0 && (
            <span className="flex items-center gap-1 rounded-full bg-[var(--tone-orange)]/15 px-2 py-0.5 text-[11px] font-semibold text-[var(--tone-orange)]">
              <Flame className="size-3" /> {streak}d
            </span>
          )}
          {nkPending.length > 0 && (
            <Badge variant="warning" className="px-1.5 py-0 text-[11px]">
              {nkPending.length}
            </Badge>
          )}
          {tab === "naukri" && <span className="absolute inset-x-0 bottom-0 h-0.5 bg-primary" />}
        </button>

        <button
          onClick={() => setTab("schedule")}
          className={cn(
            "relative flex items-center gap-2 px-5 py-3 text-sm font-medium transition-colors",
            tab === "schedule" ? "text-foreground" : "text-muted-foreground hover:text-foreground",
          )}
        >
          <Clock className="size-4" />
          Daily Schedule & History
          {tab === "schedule" && <span className="absolute inset-x-0 bottom-0 h-0.5 bg-primary" />}
        </button>
      </div>

      {/* LINKEDIN TAB */}
      {tab === "linkedin" && (
        <div className="flex flex-col gap-6">
          {/* Quick Actions & Deep Link Bar */}
          <div className="glass flex flex-wrap items-center justify-between gap-4 rounded-2xl border p-4 shadow-[var(--shadow-card)]">
            <div className="flex items-center gap-3">
              <BrandMark platform="linkedin" size={38} />
              <div>
                <p className="font-semibold">LinkedIn Profile Optimizer</p>
                <p className="text-xs text-muted-foreground">
                  Apply approved suggestions on LinkedIn to attract recruiters searching for your verified skills.
                </p>
              </div>
            </div>
            <a
              href="https://www.linkedin.com/in/me/edit/intro/"
              target="_blank"
              rel="noopener noreferrer"
              className={buttonVariants({ variant: "outline", size: "sm" })}
            >
              <ExternalLink className="size-3.5" /> Open LinkedIn edit page
            </a>
          </div>

          {/* Scores Row */}
          {o && (
            <div className="grid gap-4 md:grid-cols-2">
              <PlatformScore
                platform="linkedin"
                completeness={o.linkedin.completeness}
                alignment={o.linkedin.keyword_alignment}
                pending={o.linkedin.pending_changes}
                delay={0}
              />
              <Card className="lift animate-rise flex flex-col justify-between p-5" style={{ animationDelay: "60ms" }}>
                <div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Next automated refresh</span>
                    <Badge variant="outline">Every day at {s?.profile_schedule?.refresh_time || "08:00"} {s?.timezone === "Asia/Kolkata" ? "IST" : ""}</Badge>
                  </div>
                  <p className="mt-3 text-sm text-muted-foreground">
                    Saige analyzes target job postings and verifies every claim against your master profile. Nothing is ever fabricated.
                  </p>
                </div>
                <div className="mt-4 flex items-center justify-between border-t pt-4 text-xs text-muted-foreground">
                  <span>Pending suggestions: <b className="text-foreground">{liPending.length}</b></span>
                  <span>Applied changes: <b className="text-foreground">{liApplied.length}</b></span>
                </div>
              </Card>
            </div>
          )}

          {/* Suggestions Section */}
          <div className="flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold tracking-tight">Pending suggestions ({liPending.length})</h3>
                <p className="text-xs text-muted-foreground">Copy approved text to LinkedIn, then mark as updated.</p>
              </div>
            </div>

            {liPending.length === 0 ? (
              <Card className="flex flex-col items-center gap-3 py-10 text-center text-muted-foreground">
                <Sparkles className="size-8 text-primary" />
                <p className="font-medium text-foreground">Your LinkedIn suggestions are up to date</p>
                <p className="max-w-md text-sm">
                  Run a profile refresh to compare recent target job descriptions against your verified profile and find new truthful optimizations.
                </p>
                <Button size="sm" variant="outline" onClick={() => runJob("profile_refresh")}>
                  <RefreshCw className="size-3.5" /> Check now
                </Button>
              </Card>
            ) : (
              <div className="grid gap-4">
                {liPending.map((c, i) => (
                  <ChangeCard key={c.id} change={c} onChange={reloadAll} delay={i * 40} />
                ))}
              </div>
            )}
          </div>

          {/* Snapshot Editor */}
          <div className="mt-4">
            <h3 className="mb-2 text-lg font-semibold tracking-tight">LinkedIn Snapshot</h3>
            <p className="mb-4 text-xs text-muted-foreground">
              Keep Saige updated with your current LinkedIn text so it generates precise, non-redundant diffs.
            </p>
            <SnapshotEditors only="linkedin" onSaved={reloadAll} />
          </div>

          {/* Applied History */}
          {liApplied.length > 0 && (
            <div className="mt-4 flex flex-col gap-3">
              <h3 className="text-lg font-semibold tracking-tight">Applied changes ({liApplied.length})</h3>
              <div className="grid gap-3">
                {liApplied.map((c) => (
                  <Card key={c.id} className="p-4 text-sm">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <Check className="size-4 text-[var(--tone-green)]" />
                        <span className="font-medium">{FIELD_LABEL[c.field] ?? c.field}</span>
                        <span className="text-xs text-muted-foreground">Updated {formatDate(c.applied_at || c.updated_at)}</span>
                      </div>
                      <Badge variant="success">Applied</Badge>
                    </div>
                    <p className="mt-2 text-xs text-muted-foreground">{c.reason}</p>
                  </Card>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* NAUKRI TAB */}
      {tab === "naukri" && (
        <div className="flex flex-col gap-6">
          {/* Quick Actions & Deep Link Bar */}
          <div className="glass flex flex-wrap items-center justify-between gap-4 rounded-2xl border p-4 shadow-[var(--shadow-card)]">
            <div className="flex items-center gap-3">
              <BrandMark platform="naukri" size={38} />
              <div>
                <p className="font-semibold">Naukri Profile Optimizer & Daily Freshness</p>
                <p className="text-xs text-muted-foreground">
                  Naukri gives higher search ranking to candidates with daily profile activity.
                </p>
              </div>
            </div>
            <a
              href="https://www.naukri.com/mnjuser/profile"
              target="_blank"
              rel="noopener noreferrer"
              className={buttonVariants({ variant: "outline", size: "sm" })}
            >
              <ExternalLink className="size-3.5" /> Open Naukri edit page
            </a>
          </div>

          {/* Freshness Streak Card */}
          <Card
            className="lift animate-rise relative overflow-hidden p-6"
            style={{
              borderColor: "color-mix(in srgb, var(--tone-orange) 35%, transparent)",
              backgroundImage:
                "radial-gradient(120% 90% at 100% 0%, color-mix(in srgb, var(--tone-orange) 18%, transparent), transparent 60%)",
            }}
          >
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-center gap-4">
                <span className="grid size-14 place-items-center rounded-2xl bg-[var(--tone-orange)] text-[#0b0b0c] shadow-lg">
                  <Flame className="size-8" />
                </span>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-xl font-bold tracking-tight">Daily Freshness Streak</h3>
                    <Badge variant={streak > 0 ? "warning" : "outline"} className="text-xs">
                      {streak} {streak === 1 ? "day" : "days"} in a row
                    </Badge>
                  </div>
                  <p className="mt-1 max-w-xl text-xs text-muted-foreground">
                    Naukri prioritises freshly updated resumes in recruiter searches. Every morning, Saige rotates ONE truthful micro-edit (headline wording, key skills order, or summary line) crafted only from verified facts.
                  </p>
                </div>
              </div>
              <Button
                variant="gradient"
                className="shrink-0"
                disabled={Boolean(runningJob)}
                onClick={() => runJob("naukri_freshness")}
              >
                <Zap className="size-4" />
                {runningJob === "naukri_freshness" ? "Preparing edit…" : "Run 2-min freshness"}
              </Button>
            </div>
          </Card>

          {/* Scores Row */}
          {o && (
            <div className="grid gap-4 md:grid-cols-2">
              <PlatformScore
                platform="naukri"
                completeness={o.naukri.completeness}
                alignment={o.naukri.keyword_alignment}
                pending={o.naukri.pending_changes}
                delay={0}
              />
              <Card className="lift animate-rise flex flex-col justify-between p-5" style={{ animationDelay: "60ms" }}>
                <div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Freshness schedule</span>
                    <Badge variant="outline">
                      {s?.profile_schedule?.naukri_daily_freshness ? "Active daily" : "Disabled in settings"}
                    </Badge>
                  </div>
                  <p className="mt-3 text-sm text-muted-foreground">
                    Applying just 1 suggestion per day on Naukri keeps your profile timestamped as “Recently Active”.
                  </p>
                </div>
                <div className="mt-4 flex items-center justify-between border-t pt-4 text-xs text-muted-foreground">
                  <span>Pending suggestions: <b className="text-foreground">{nkPending.length}</b></span>
                  <span>Applied changes: <b className="text-foreground">{nkApplied.length}</b></span>
                </div>
              </Card>
            </div>
          )}

          {/* Suggestions Section */}
          <div className="flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold tracking-tight">Pending suggestions ({nkPending.length})</h3>
                <p className="text-xs text-muted-foreground">Copy approved text to Naukri, then mark as updated.</p>
              </div>
            </div>

            {nkPending.length === 0 ? (
              <Card className="flex flex-col items-center gap-3 py-10 text-center text-muted-foreground">
                <Sparkles className="size-8 text-primary" />
                <p className="font-medium text-foreground">Your Naukri profile is up to date</p>
                <p className="max-w-md text-sm">
                  Click “Run 2-min freshness” to generate today’s micro-edit or run a full profile refresh.
                </p>
                <div className="flex gap-2">
                  <Button size="sm" variant="outline" onClick={() => runJob("naukri_freshness")}>
                    <Zap className="size-3.5" /> Freshness micro-edit
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => runJob("profile_refresh")}>
                    <RefreshCw className="size-3.5" /> Full refresh
                  </Button>
                </div>
              </Card>
            ) : (
              <div className="grid gap-4">
                {nkPending.map((c, i) => (
                  <ChangeCard key={c.id} change={c} onChange={reloadAll} delay={i * 40} />
                ))}
              </div>
            )}
          </div>

          {/* Snapshot Editor */}
          <div className="mt-4">
            <h3 className="mb-2 text-lg font-semibold tracking-tight">Naukri Snapshot</h3>
            <p className="mb-4 text-xs text-muted-foreground">
              Paste what is currently on your Naukri profile so Saige knows what to optimize.
            </p>
            <SnapshotEditors only="naukri" onSaved={reloadAll} />
          </div>

          {/* Applied History */}
          {nkApplied.length > 0 && (
            <div className="mt-4 flex flex-col gap-3">
              <h3 className="text-lg font-semibold tracking-tight">Applied changes ({nkApplied.length})</h3>
              <div className="grid gap-3">
                {nkApplied.map((c) => (
                  <Card key={c.id} className="p-4 text-sm">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <Check className="size-4 text-[var(--tone-green)]" />
                        <span className="font-medium">{FIELD_LABEL[c.field] ?? c.field}</span>
                        <span className="text-xs text-muted-foreground">Updated {formatDate(c.applied_at || c.updated_at)}</span>
                      </div>
                      <Badge variant="success">Applied</Badge>
                    </div>
                    <p className="mt-2 text-xs text-muted-foreground">{c.reason}</p>
                  </Card>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* SCHEDULE & HISTORY TAB */}
      {tab === "schedule" && (
        <div className="flex flex-col gap-6">
          <Card className="p-6">
            <CardHeader className="p-0 pb-4">
              <CardTitle className="text-lg">Daily Profile Refresh Schedule</CardTitle>
              <CardDescription>
                Configure when Saige evaluates target JDs, computes truth-checked optimizations, and prepares daily freshness edits.
              </CardDescription>
            </CardHeader>
            <CardContent className="grid gap-6 p-0 pt-2">
              {/* Toggles */}
              <div className="grid gap-4 sm:grid-cols-3">
                <label className="flex cursor-pointer items-start gap-3 rounded-xl border p-4 hover:bg-muted/40">
                  <input
                    type="checkbox"
                    checked={scheduleState.linkedin_enabled}
                    onChange={(e) => setScheduleState({ ...scheduleState, linkedin_enabled: e.target.checked })}
                    className="mt-1 size-4 rounded accent-primary"
                  />
                  <div>
                    <p className="text-sm font-medium">LinkedIn refresh</p>
                    <p className="text-xs text-muted-foreground">Daily optimization suggestions</p>
                  </div>
                </label>

                <label className="flex cursor-pointer items-start gap-3 rounded-xl border p-4 hover:bg-muted/40">
                  <input
                    type="checkbox"
                    checked={scheduleState.naukri_enabled}
                    onChange={(e) => setScheduleState({ ...scheduleState, naukri_enabled: e.target.checked })}
                    className="mt-1 size-4 rounded accent-primary"
                  />
                  <div>
                    <p className="text-sm font-medium">Naukri refresh</p>
                    <p className="text-xs text-muted-foreground">Headline & skills optimization</p>
                  </div>
                </label>

                <label className="flex cursor-pointer items-start gap-3 rounded-xl border p-4 hover:bg-muted/40">
                  <input
                    type="checkbox"
                    checked={scheduleState.naukri_daily_freshness}
                    onChange={(e) => setScheduleState({ ...scheduleState, naukri_daily_freshness: e.target.checked })}
                    className="mt-1 size-4 rounded accent-primary"
                  />
                  <div>
                    <p className="text-sm font-medium">Naukri daily freshness</p>
                    <p className="text-xs text-muted-foreground">One truthful micro-edit/day</p>
                  </div>
                </label>
              </div>

              {/* Time & Days */}
              <div className="grid gap-6 sm:grid-cols-2">
                <div>
                  <label className="mb-2 block text-sm font-medium">Run time</label>
                  <input
                    type="time"
                    value={scheduleState.refresh_time}
                    onChange={(e) => setScheduleState({ ...scheduleState, refresh_time: e.target.value })}
                    className="glass h-10 w-full max-w-xs rounded-xl border px-3 text-sm"
                  />
                  <label className="mb-2 mt-4 block text-sm font-medium">Timezone</label>
                  <select
                    value={timezone}
                    onChange={(e) => setTimezone(e.target.value)}
                    className="glass h-10 w-full max-w-xs rounded-xl border px-3 text-sm"
                  >
                    {[...new Set([timezone, ...TIMEZONES])].map((tz) => <option key={tz} value={tz}>{tz}</option>)}
                  </select>
                </div>

                <div>
                  <label className="mb-2 block text-sm font-medium">Active days</label>
                  <div className="flex flex-wrap gap-1.5">
                    {DAYS_OF_WEEK.map(({ day, label }) => {
                      const active = scheduleState.days.includes(day);
                      return (
                        <button
                          key={day}
                          type="button"
                          onClick={() => {
                            const next = active ? scheduleState.days.filter((d) => d !== day) : [...scheduleState.days, day];
                            setScheduleState({ ...scheduleState, days: next });
                          }}
                          className={cn(
                            "rounded-lg px-3 py-1.5 text-xs font-medium transition-colors",
                            active ? "bg-primary text-primary-foreground" : "border text-muted-foreground hover:bg-muted",
                          )}
                        >
                          {label}
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>

              <div className="flex flex-wrap items-center justify-between gap-4 border-t pt-4">
                <Button onClick={saveSchedule} disabled={savingSchedule}>
                  {savingSchedule ? "Saving…" : "Save schedule"}
                </Button>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground">Manual triggers:</span>
                  <Button size="sm" variant="outline" disabled={Boolean(runningJob)} onClick={() => runJob("profile_refresh")}>
                    Refresh now
                  </Button>
                  <Button size="sm" variant="outline" disabled={Boolean(runningJob)} onClick={() => runJob("naukri_freshness")}>
                    Freshness now
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Daily jobs */}
          {s && (
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {s.jobs.map((j) => (
                <Card key={j.job} className="lift p-4">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-sm font-medium">{j.label}</p>
                    {j.last_run && <Badge variant={j.last_run.status === "succeeded" ? "success" : j.last_run.status === "failed" ? "destructive" : "muted"}>{j.last_run.status}</Badge>}
                  </div>
                  <p className="mt-2 text-xs text-muted-foreground">Next: {j.next_run ? formatDateTime(j.next_run) : "not scheduled"}</p>
                  <p className="text-xs text-muted-foreground">Last: {j.last_run?.started_at ? formatDateTime(j.last_run.started_at) : "never"}</p>
                </Card>
              ))}
            </div>
          )}

          {/* Run History Timeline */}
          <Card className="p-6">
            <CardHeader className="p-0 pb-4">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2 text-lg">
                    <History className="size-4" /> Run History
                  </CardTitle>
                  <CardDescription>Recent scheduler runs and results.</CardDescription>
                </div>
                <Button size="sm" variant="ghost" onClick={() => void history.reload()}>
                  <RefreshCw className="size-3.5" />
                </Button>
              </div>
            </CardHeader>
            <CardContent className="p-0 pt-2">
              {!history.data || history.data.length === 0 ? (
                <div className="py-8 text-center text-sm text-muted-foreground">
                  No scheduler runs recorded yet. Click “Refresh now” or wait for the morning cron.
                </div>
              ) : (
                <div className="divide-y text-sm">
                  {history.data.map((h) => {
                    const statusTone = h.status === "succeeded" ? "success" : h.status === "skipped" ? "muted" : "destructive";
                    return (
                      <div key={h.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-foreground">{h.label}</span>
                            <Badge variant={statusTone as "success" | "muted" | "destructive"}>{h.status}</Badge>
                            <Badge variant="outline" className="text-[10px] uppercase">
                              {h.trigger}
                            </Badge>
                          </div>
                          <p className="mt-1 text-xs text-muted-foreground">
                            {formatDateTime(h.started_at || h.run_date)}
                            {describeResult(h.result) && <span> · {describeResult(h.result)}</span>}
                          </p>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
