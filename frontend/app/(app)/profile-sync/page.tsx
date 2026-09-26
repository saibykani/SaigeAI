"use client";

import { Check, ClipboardCopy, ExternalLink, FileText, Pencil, RefreshCw, ShieldCheck, Sparkles, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { Notice, PageHeader } from "@/components/app-shell";
import { CountUp, ProgressRing } from "@/components/motion";
import { TagInput } from "@/components/tag-input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input, Textarea } from "@/components/ui/form";
import { useApi } from "@/hooks/use-api";
import { request } from "@/services/api";
import type { LinkedInSnapshot, NaukriSnapshot, ProfileChange, SyncOverview, SyncPlatform } from "@/types/api";
import { cn } from "@/utils/cn";
import { UNKNOWN, formatDate, numberOrNull } from "@/utils/format";

const BRAND = {
  linkedin: { name: "LinkedIn", color: "#0a66c2", mark: "in", edit: "https://www.linkedin.com/in/me/" },
  naukri: { name: "Naukri", color: "#275df5", mark: "N", edit: "https://www.naukri.com/mnjuser/profile" },
  resume: { name: "Master resume", color: "var(--series-3)", mark: "CV", edit: "/resumes" },
} as const;

const FIELD_LABEL: Record<string, string> = {
  headline: "Headline",
  about: "About",
  summary: "Profile summary",
  skills: "Skills",
  key_skills: "Key skills",
  "open_to_work.titles": "Open-to-Work job titles",
  current_title: "Current title",
  preferred_locations: "Preferred locations",
  preferred_roles: "Preferred roles",
  notice_period_days: "Notice period (days)",
  expected_salary: "Expected salary",
  total_experience_years: "Total experience",
  resume_updated_on: "Resume refresh",
};

type Tab = "linkedin" | "naukri" | "resume" | "consistency" | "snapshots";

function BrandMark({ platform, size = 40 }: { platform: SyncPlatform; size?: number }) {
  const b = BRAND[platform];
  return (
    <span
      className="grid shrink-0 place-items-center rounded-xl text-sm font-bold text-white shadow-sm"
      style={{ background: b.color, width: size, height: size }}
      aria-hidden
    >
      {platform === "resume" ? <FileText className="size-4" /> : b.mark}
    </span>
  );
}

function asText(v: ProfileChange["after"]): string {
  if (v === null || v === undefined) return "";
  return Array.isArray(v) ? v.join(", ") : String(v);
}

function ChangeCard({ change, onChange, delay }: { change: ProfileChange; onChange: () => void; delay: number }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(asText(change.after));
  const [msg, setMsg] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const [copied, setCopied] = useState(false);
  const b = BRAND[change.platform];
  const isList = Array.isArray(change.after);
  const added = isList && Array.isArray(change.before) ? (change.after as string[]).filter((x) => !(change.before as string[]).includes(x)) : isList ? (change.after as string[]) : [];

  async function act(path: string, method: "POST" | "PUT" = "POST", body?: unknown) {
    setMsg(null);
    try {
      await request(`/profile-changes/${change.id}${path}`, { method, body });
      onChange();
    } catch (e) {
      setMsg({ tone: "error", text: e instanceof Error ? e.message : "Action failed" });
    }
  }

  async function copy() {
    await navigator.clipboard.writeText(asText(change.after));
    setCopied(true);
    setTimeout(() => setCopied(false), 1600);
  }

  const status = change.applied_at ? "Updated" : change.approval_status === "USER_APPROVED" ? "Approved" : change.approval_status === "USER_REJECTED" ? "Rejected" : "Needs review";
  const statusTone = change.applied_at ? "success" : change.approval_status === "USER_REJECTED" ? "muted" : change.approval_status === "USER_APPROVED" ? "default" : "warning";

  return (
    <Card className="lift animate-rise overflow-hidden" style={{ animationDelay: `${delay}ms` }}>
      <div className="h-1 w-full" style={{ background: b.color }} aria-hidden />
      <CardHeader className="flex-row items-start gap-3">
        <BrandMark platform={change.platform} size={36} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <CardTitle>{FIELD_LABEL[change.field] ?? change.field}</CardTitle>
            <Badge variant={statusTone as "success" | "muted" | "default" | "warning"}>{status}</Badge>
            <Badge variant="outline" title="How confident Saige is that this change helps">
              {Math.round(change.ai_confidence * 100)}% confidence
            </Badge>
            {change.validation.status === "PASSED" && (
              <Badge variant="success" title="Checked against your verified profile — nothing fabricated">
                <ShieldCheck className="size-3" /> Verified
              </Badge>
            )}
          </div>
          <CardDescription className="mt-1">{change.reason}</CardDescription>
          {change.source_jobs.length > 0 && (
            <p className="mt-1 text-xs text-muted-foreground">Based on {change.source_jobs.length} recent job description(s)</p>
          )}
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {!isList && (
          <div className="grid gap-3 md:grid-cols-2">
            <div className="rounded-xl border bg-muted/50 p-3">
              <p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Before</p>
              <p className="whitespace-pre-wrap text-sm text-muted-foreground">{asText(change.before) || UNKNOWN}</p>
            </div>
            <div className="rounded-xl border border-primary/30 bg-accent/60 p-3">
              <p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-accent-foreground">After</p>
              {editing ? (
                <Textarea rows={4} value={draft} onChange={(e) => setDraft(e.target.value)} />
              ) : (
                <p className="whitespace-pre-wrap text-sm">{asText(change.after)}</p>
              )}
            </div>
          </div>
        )}
        {isList && (
          <div className="rounded-xl border bg-muted/40 p-3">
            <p className="mb-2 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
              {added.length} to add · {(change.after as string[]).length} total
            </p>
            {editing ? (
              <TagInput value={draft ? draft.split(",").map((s) => s.trim()).filter(Boolean) : []} onChange={(v) => setDraft(v.join(", "))} />
            ) : (
              <div className="flex flex-wrap gap-1.5">
                {(change.after as string[]).map((s) => (
                  <span
                    key={s}
                    className={cn(
                      "rounded-full px-2.5 py-0.5 text-xs font-medium",
                      added.includes(s) ? "bg-success/15 text-success ring-1 ring-success/30" : "bg-card-solid text-muted-foreground ring-1 ring-border",
                    )}
                  >
                    {added.includes(s) && "+ "}
                    {s}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}
        {msg && <Notice tone={msg.tone}>{msg.text}</Notice>}
        <div className="flex flex-wrap items-center gap-2">
          {editing ? (
            <>
              <Button
                size="sm"
                onClick={async () => {
                  await act("", "PUT", { after: isList ? draft.split(",").map((s) => s.trim()).filter(Boolean) : draft });
                  setEditing(false);
                }}
              >
                <Check /> Save edit
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>Cancel</Button>
            </>
          ) : (
            <>
              <Button size="sm" variant="gradient" className="animate-gradient" onClick={copy}>
                <ClipboardCopy /> {copied ? "Copied!" : `Copy for ${b.name}`}
              </Button>
              {change.platform !== "resume" && (
                <a href={b.edit} target="_blank" rel="noopener noreferrer" className="inline-flex h-8 items-center gap-1.5 rounded-full border px-3.5 text-xs font-medium hover:bg-muted">
                  <ExternalLink className="size-3.5" /> Open {b.name}
                </a>
              )}
              {!change.applied_at && change.approval_status !== "USER_REJECTED" && (
                <>
                  <Button size="sm" variant="outline" onClick={() => act("/applied")}>
                    <Check /> {change.platform === "resume" ? "Apply to resume" : "Mark as updated"}
                  </Button>
                  {change.approval_status === "USER_APPROVAL_REQUIRED" && (
                    <Button size="sm" variant="ghost" onClick={() => act("/approve")}>Approve</Button>
                  )}
                  <Button size="sm" variant="ghost" onClick={() => { setDraft(asText(change.after)); setEditing(true); }}>
                    <Pencil /> Edit
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => act("/reject")}>
                    <X /> Reject
                  </Button>
                </>
              )}
              {change.applied_at && <span className="text-xs text-muted-foreground">Updated {formatDate(change.applied_at)}</span>}
            </>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function PlatformScore({ platform, completeness, alignment, pending, delay }: { platform: "linkedin" | "naukri"; completeness: number; alignment: number; pending: number; delay: number }) {
  const b = BRAND[platform];
  return (
    <Card className="lift animate-rise relative overflow-hidden p-5" style={{ animationDelay: `${delay}ms` }}>
      <div aria-hidden className="pointer-events-none absolute -right-10 -top-10 size-32 rounded-full opacity-15 blur-2xl" style={{ background: b.color }} />
      <div className="flex items-center gap-3">
        <BrandMark platform={platform} />
        <div>
          <p className="font-semibold">{b.name}</p>
          <p className="text-xs text-muted-foreground">{pending} suggestion(s) waiting</p>
        </div>
      </div>
      <div className="mt-5 flex items-center gap-5">
        <ProgressRing value={completeness} size={84} stroke={8} trackClass="stroke-muted" barClass="stroke-[var(--series-1)]">
          <span className="text-lg font-semibold"><CountUp value={completeness} suffix="%" /></span>
        </ProgressRing>
        <div className="flex-1 text-sm">
          <p className="text-muted-foreground">Profile completeness</p>
          <p className="mt-3 text-muted-foreground">Keyword alignment</p>
          <div className="mt-1 flex items-center gap-2">
            <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
              <div className="animate-grow-x h-full rounded-full" style={{ width: `${alignment}%`, background: b.color }} />
            </div>
            <span className="w-10 text-right font-medium">{alignment}%</span>
          </div>
        </div>
      </div>
    </Card>
  );
}

function SnapshotEditors({ onSaved }: { onSaved: () => void }) {
  const li = useApi<LinkedInSnapshot>("/profile/linkedin");
  const nk = useApi<NaukriSnapshot>("/profile/naukri");
  const [l, setL] = useState<LinkedInSnapshot | null>(null);
  const [n, setN] = useState<NaukriSnapshot | null>(null);
  const [msg, setMsg] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  useEffect(() => { if (li.data) setL(li.data); }, [li.data]);
  useEffect(() => { if (nk.data) setN(nk.data); }, [nk.data]);
  if (!l || !n) return <div className="skeleton h-96 rounded-2xl" />;
  const orNull = (v: string) => (v.trim() ? v : null);

  async function save(platform: "linkedin" | "naukri") {
    setMsg(null);
    try {
      await request(`/profile/${platform}`, { method: "PUT", body: platform === "linkedin" ? l : n });
      setMsg({ tone: "success", text: `${BRAND[platform].name} snapshot saved. Run optimization to refresh suggestions.` });
      onSaved();
    } catch (e) {
      setMsg({ tone: "error", text: e instanceof Error ? e.message : "Save failed" });
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <Notice>
        Paste what is currently on your LinkedIn and Naukri profiles. Saige compares it with your verified master profile and recent job descriptions — it never logs in to either site.
      </Notice>
      {msg && <Notice tone={msg.tone}>{msg.text}</Notice>}
      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader className="flex-row items-center gap-3"><BrandMark platform="linkedin" size={32} /><CardTitle>Your LinkedIn today</CardTitle></CardHeader>
          <CardContent className="grid gap-3">
            <Field label="Profile URL"><Input value={l.profile_url ?? ""} onChange={(e) => setL({ ...l, profile_url: orNull(e.target.value) })} placeholder="https://www.linkedin.com/in/…" /></Field>
            <Field label={`Headline (${(l.headline ?? "").length}/220)`}><Input maxLength={220} value={l.headline ?? ""} onChange={(e) => setL({ ...l, headline: orNull(e.target.value) })} /></Field>
            <Field label={`About (${(l.about ?? "").length}/2600)`}><Textarea rows={5} maxLength={2600} value={l.about ?? ""} onChange={(e) => setL({ ...l, about: orNull(e.target.value) })} /></Field>
            <Field label="Current title"><Input value={l.current_title ?? ""} onChange={(e) => setL({ ...l, current_title: orNull(e.target.value) })} /></Field>
            <Field label="Skills"><TagInput value={l.skills} onChange={(skills) => setL({ ...l, skills })} /></Field>
            <Field label="Education"><TagInput value={l.education} onChange={(education) => setL({ ...l, education })} placeholder="e.g. B.Tech, JNTU" /></Field>
            <Field label="Certifications"><TagInput value={l.certifications} onChange={(certifications) => setL({ ...l, certifications })} /></Field>
            <Field label="Open-to-Work job titles"><TagInput value={l.open_to_work.titles} onChange={(titles) => setL({ ...l, open_to_work: { ...l.open_to_work, titles } })} /></Field>
            <div><Button onClick={() => save("linkedin")}>Save LinkedIn snapshot</Button></div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex-row items-center gap-3"><BrandMark platform="naukri" size={32} /><CardTitle>Your Naukri today</CardTitle></CardHeader>
          <CardContent className="grid gap-3">
            <Field label="Profile URL"><Input value={n.profile_url ?? ""} onChange={(e) => setN({ ...n, profile_url: orNull(e.target.value) })} placeholder="https://www.naukri.com/mnjuser/profile" /></Field>
            <Field label={`Resume headline (${(n.headline ?? "").length}/250)`}><Input maxLength={250} value={n.headline ?? ""} onChange={(e) => setN({ ...n, headline: orNull(e.target.value) })} /></Field>
            <Field label={`Profile summary (${(n.summary ?? "").length}/1000)`}><Textarea rows={5} maxLength={1000} value={n.summary ?? ""} onChange={(e) => setN({ ...n, summary: orNull(e.target.value) })} /></Field>
            <Field label="Key skills"><TagInput value={n.key_skills} onChange={(key_skills) => setN({ ...n, key_skills })} /></Field>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Current designation"><Input value={n.current_designation ?? ""} onChange={(e) => setN({ ...n, current_designation: orNull(e.target.value) })} /></Field>
              <Field label="Current company"><Input value={n.current_company ?? ""} onChange={(e) => setN({ ...n, current_company: orNull(e.target.value) })} /></Field>
              <Field label="Total experience (years)"><Input type="number" min={0} step="any" value={n.total_experience_years ?? ""} onChange={(e) => setN({ ...n, total_experience_years: numberOrNull(e.target.value) })} /></Field>
              <Field label="Notice period (days)"><Input type="number" min={0} value={n.notice_period_days ?? ""} onChange={(e) => setN({ ...n, notice_period_days: numberOrNull(e.target.value) })} /></Field>
              <Field label="Expected salary"><Input type="number" min={0} value={n.expected_salary ?? ""} onChange={(e) => setN({ ...n, expected_salary: numberOrNull(e.target.value) })} /></Field>
              <Field label="Resume last updated"><Input type="date" value={n.resume_updated_on ?? ""} onChange={(e) => setN({ ...n, resume_updated_on: orNull(e.target.value) })} /></Field>
            </div>
            <Field label="Preferred roles"><TagInput value={n.preferred_roles} onChange={(preferred_roles) => setN({ ...n, preferred_roles })} /></Field>
            <Field label="Preferred locations"><TagInput value={n.preferred_locations} onChange={(preferred_locations) => setN({ ...n, preferred_locations })} /></Field>
            <div><Button onClick={() => save("naukri")}>Save Naukri snapshot</Button></div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

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
