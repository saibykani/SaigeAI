"use client";

import { Check, RefreshCw, ShieldCheck, Sparkles, X } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { Notice, PageHeader } from "@/components/app-shell";
import { CountUp, ProgressRing } from "@/components/motion";
import { BrandMark, ChangeCard, PlatformScore, SnapshotEditors } from "@/components/profile-parts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useApi } from "@/hooks/use-api";
import { request } from "@/services/api";
import type { ProfileChange, SyncOverview } from "@/types/api";
import { cn } from "@/utils/cn";
import { formatDate } from "@/utils/format";

type Tab = "linkedin" | "naukri" | "resume" | "consistency" | "snapshots";

export default function ProfileSyncPage() {
  const overview = useApi<SyncOverview>("/profile-sync/overview");
  const changes = useApi<ProfileChange[]>("/profile-changes");
  const [tab, setTab] = useState<Tab>("linkedin");
  const [running, setRunning] = useState(false);
  const [msg, setMsg] = useState<{ tone: "success" | "error"; text: string } | null>(null);

  const reload = () => { void overview.reload(); void changes.reload(); };

  async function run() {
    setRunning(true);
    setMsg(null);
    try {
      const r = await request<{ jobs_analyzed: number; pending_changes: number }>("/profile-sync/run", { method: "POST" });
      setMsg({ tone: "success", text: `Analyzed ${r.jobs_analyzed} job description(s). ${r.pending_changes} suggestion(s) are waiting for review.` });
      reload();
    } catch (e) {
      setMsg({ tone: "error", text: e instanceof Error ? e.message : "Optimization failed" });
    } finally {
      setRunning(false);
    }
  }

  const byPlatform = useMemo(() => {
    const all = changes.data ?? [];
    const order = (c: ProfileChange) => (c.applied_at ? 3 : c.approval_status === "USER_REJECTED" ? 4 : c.approval_status === "USER_APPROVED" ? 2 : 1);
    const FIELD_ORDER = ["headline", "about", "summary", "skills", "key_skills", "current_title", "open_to_work.titles"];
    const rank = (c: ProfileChange) => { const i = FIELD_ORDER.indexOf(c.field); return i === -1 ? 99 : i; };
    const sorted = [...all].sort((a, b) => order(a) - order(b) || rank(a) - rank(b));
    return { linkedin: sorted.filter((c) => c.platform === "linkedin"), naukri: sorted.filter((c) => c.platform === "naukri"), resume: sorted.filter((c) => c.platform === "resume") };
  }, [changes.data]);

  const o = overview.data;
  const TABS: { id: Tab; label: string; count?: number }[] = [
    { id: "linkedin", label: "LinkedIn", count: o?.linkedin.pending_changes },
    { id: "naukri", label: "Naukri", count: o?.naukri.pending_changes },
    { id: "resume", label: "Master resume", count: o?.resume.pending_changes },
    { id: "consistency", label: "Consistency" },
    { id: "snapshots", label: "Your profiles" },
  ];

  return (
    <>
      <PageHeader
        title="Profile Sync"
        description="Keep LinkedIn, Naukri and your master resume aligned with what recruiters are searching for — using only skills and experience you've verified."
        actions={
          <Button variant="gradient" className="animate-gradient sheen" disabled={running} onClick={run}>
            <RefreshCw className={cn(running && "animate-spin")} /> {running ? "Optimizing…" : "Run optimization"}
          </Button>
        }
      />
      {msg && <div className="mb-6"><Notice tone={msg.tone}>{msg.text}</Notice></div>}
      {overview.error && <Notice tone="error">{overview.error}</Notice>}

      {!o ? (
        <div className="grid gap-4 md:grid-cols-3">{[0, 1, 2].map((i) => <div key={i} className="skeleton h-44 rounded-2xl" />)}</div>
      ) : (
        <>
          <div className="grid gap-4 md:grid-cols-3">
            <PlatformScore platform="linkedin" completeness={o.linkedin.completeness} alignment={o.linkedin.keyword_alignment} pending={o.linkedin.pending_changes} delay={0} />
            <PlatformScore platform="naukri" completeness={o.naukri.completeness} alignment={o.naukri.keyword_alignment} pending={o.naukri.pending_changes} delay={70} />
            <Card className="lift animate-rise relative overflow-hidden p-5" style={{ animationDelay: "140ms" }}>
              <div className="flex items-center gap-3">
                <span className="grid size-10 place-items-center rounded-xl bg-[var(--series-7)] text-white shadow-sm"><ShieldCheck className="size-5" /></span>
                <div>
                  <p className="font-semibold">Profile consistency</p>
                  <p className="text-xs text-muted-foreground">Master · LinkedIn · Naukri · Resume</p>
                </div>
              </div>
              <div className="mt-5 flex items-center gap-5">
                <ProgressRing value={o.consistency.score ?? 0} size={84} stroke={8} trackClass="stroke-muted" barClass="stroke-[var(--series-7)]">
                  <span className="text-lg font-semibold">{o.consistency.score == null ? "—" : <CountUp value={o.consistency.score} suffix="%" />}</span>
                </ProgressRing>
                <div className="text-sm text-muted-foreground">
                  {o.consistency.score == null ? "Add your profiles to compare." : `${o.consistency.discrepancies.length} discrepanc${o.consistency.discrepancies.length === 1 ? "y" : "ies"} found`}
                  <p className="mt-2 text-xs">{o.last_run ? `Last optimized ${formatDate(o.last_run)}` : "Not optimized yet"}</p>
                </div>
              </div>
            </Card>
          </div>

          {/* Skill demand across recent target JDs */}
          <Card className="animate-rise mt-6" style={{ animationDelay: "200ms" }}>
            <CardHeader>
              <div className="flex flex-wrap items-end justify-between gap-3">
                <div>
                  <CardTitle className="text-lg">What recruiters are asking for</CardTitle>
                  <CardDescription>Share of your {o.jobs_analyzed} recent relevant job descriptions that mention each skill.</CardDescription>
                </div>
                <div className="flex items-center gap-4 text-xs text-muted-foreground">
                  <span className="flex items-center gap-1.5"><span className="size-2.5 rounded-full bg-[var(--series-1)]" /> You have it</span>
                  <span className="flex items-center gap-1.5"><span className="size-2.5 rounded-full bg-muted-foreground/40" /> Gap — learn before claiming</span>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {o.trends.length === 0 ? (
                <div className="flex flex-col items-center gap-3 rounded-2xl border border-dashed py-10 text-center">
                  <Sparkles className="size-7 text-muted-foreground" />
                  <p className="text-sm text-muted-foreground">Add a few jobs first — trends come from real job descriptions.</p>
                  <Link href="/jobs" className="text-sm font-medium text-primary hover:underline">Go to Jobs</Link>
                </div>
              ) : (
                <ul className="grid gap-x-10 gap-y-2.5 md:grid-cols-2">
                  {o.trends.slice(0, 16).map((t, i) => (
                    <li key={t.skill} className="grid grid-cols-[130px_1fr_44px] items-center gap-3 text-sm" title={`${t.skill}: ${t.jobs} of ${o.jobs_analyzed} JDs (${t.pct}%) — ${t.candidate_has ? "in your verified profile" : "not in your verified profile"}`}>
                      <span className="truncate">{t.skill}</span>
                      <span className="h-2.5 overflow-hidden rounded-full bg-muted">
                        <span
                          className="animate-grow-x block h-full rounded-full"
                          style={{ width: `${t.pct}%`, background: t.candidate_has ? "var(--series-1)" : "color-mix(in srgb, var(--muted-foreground) 40%, transparent)", animationDelay: `${250 + i * 40}ms` }}
                        />
                      </span>
                      <span className="text-right text-xs tabular-nums text-muted-foreground">{Math.round(t.pct)}%</span>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>

          {/* Tabs */}
          <div role="tablist" className="mt-8 mb-5 flex gap-1 overflow-x-auto rounded-full border bg-card-solid/60 p-1">
            {TABS.map((t) => (
              <button
                key={t.id}
                role="tab"
                aria-selected={tab === t.id}
                onClick={() => setTab(t.id)}
                className={cn(
                  "flex shrink-0 cursor-pointer items-center gap-2 rounded-full px-4 py-2 text-sm transition-all",
                  tab === t.id ? "bg-primary font-medium text-primary-foreground shadow-sm" : "text-muted-foreground hover:bg-muted hover:text-foreground",
                )}
              >
                {t.label}
                {!!t.count && <span className={cn("rounded-full px-1.5 text-[11px]", tab === t.id ? "bg-white/25" : "bg-muted")}>{t.count}</span>}
              </button>
            ))}
          </div>

          {(tab === "linkedin" || tab === "naukri" || tab === "resume") && (
            <div className="flex flex-col gap-4">
              {byPlatform[tab].length === 0 ? (
                <Card className="flex flex-col items-center gap-3 py-12 text-center">
                  <BrandMark platform={tab} />
                  <p className="text-sm text-muted-foreground">No suggestions yet. Save your current profile under “Your profiles”, then run optimization.</p>
                </Card>
              ) : (
                byPlatform[tab].map((ch, i) => <ChangeCard key={ch.id + ch.updated_at} change={ch} onChange={reload} delay={i * 50} />)
              )}
            </div>
          )}

          {tab === "consistency" && (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Consistency check</CardTitle>
                <CardDescription>Your master profile is the source of truth; other places should match it.</CardDescription>
              </CardHeader>
              <CardContent>
                {o.consistency.checks.length === 0 ? (
                  <p className="text-sm text-muted-foreground">Nothing to compare yet — fill in your profiles and upload a resume.</p>
                ) : (
                  <ul className="divide-y">
                    {o.consistency.checks.map((ch) => (
                      <li key={ch.field} className="flex flex-wrap items-start gap-3 py-3 text-sm">
                        <span className={cn("mt-0.5 grid size-6 shrink-0 place-items-center rounded-full", ch.consistent ? "bg-success/15 text-success" : "bg-warning/15 text-warning")}>
                          {ch.consistent ? <Check className="size-3.5" /> : <X className="size-3.5" />}
                        </span>
                        <div className="min-w-0 flex-1">
                          <p className="font-medium">{ch.field}</p>
                          <p className="text-xs text-muted-foreground">Master: {String(ch.master)}</p>
                        </div>
                        <div className="flex flex-wrap gap-1.5">
                          {Object.entries(ch.values).map(([k, v]) => (
                            <Badge key={k} variant={ch.mismatched.includes(k) ? "warning" : "muted"} className="capitalize">
                              {k}: {String(v)}
                            </Badge>
                          ))}
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          )}

          {tab === "snapshots" && <SnapshotEditors onSaved={reload} />}
        </>
      )}
    </>
  );
}
