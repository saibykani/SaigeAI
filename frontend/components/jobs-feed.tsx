"use client";

import { Bot, CalendarClock, CheckSquare, ExternalLink, Loader2, Mail, MapPin, RefreshCw, Search, Square, Zap } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { Notice } from "@/components/app-shell";
import { Loader3D } from "@/components/loader3d";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/form";
import { useApi } from "@/hooks/use-api";
import { request } from "@/services/api";
import type { AutoApplySettings, AutomationSettings, FeedItem, JobFeed, JobScope } from "@/types/api";
import { cn } from "@/utils/cn";
import { formatDate, timeAgo } from "@/utils/format";

type Tab = "foryou" | "country" | "remote" | "walk_in" | "alerts" | "careers" | "abroad";
type Msg = { tone: "success" | "error" | "warning" | "info"; text: React.ReactNode } | null;

const PAGE = 60;
const EXP_RANGES: Record<string, [number, number]> = { "0-2": [0, 2], "3-5": [3, 5], "6-10": [6, 10], "10+": [10, 60] };

function scoreTone(s: number) {
  return s >= 85 ? "green" : s >= 70 ? "yellow" : s >= 55 ? "orange" : "red";
}

function daysAgo(date: string | null) {
  if (!date) return null;
  const t = Date.parse(date);
  return Number.isNaN(t) ? null : (Date.now() - t) / 86_400_000;
}

function inTab(i: FeedItem, tab: Tab) {
  switch (tab) {
    case "foryou": return i.scope !== "abroad";
    case "country": return i.scope === "country";
    case "remote": return i.scope === "remote";
    case "walk_in": return !!i.walk_in;
    case "alerts": return i.source_label.endsWith("alert");
    case "careers": return i.source_label === "Career page";
    case "abroad": return i.scope === "abroad";
  }
}

/** Jobs for you: every job for your target roles, fetched automatically for your country, with filters and select-all. */
export function JobsFeed({ onSaved }: { onSaved: () => void }) {
  const [data, setData] = useState<JobFeed | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [msg, setMsg] = useState<Msg>(null);
  const [tab, setTab] = useState<Tab>("foryou");
  const [f, setF] = useState({ q: "", source: "", min: 0, posted: 0, exp: "", type: "", email: false, sort: "match" });
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [limit, setLimit] = useState(PAGE);
  const [saving, setSaving] = useState(false);

  async function load(refresh = false) {
    if (refresh) setRefreshing(true);
    setMsg(null);
    try {
      const r = await request<JobFeed>(`/jobs/feed${refresh ? "?refresh=true" : ""}`);
      setData(r);
      const down = Object.keys(r.errors).filter((k) => k !== "profile");
      if (r.errors.profile) setMsg({ tone: "warning", text: <>{r.errors.profile} <Link href="/profile" className="underline">Open profile</Link></> });
      else if (down.length) setMsg({ tone: "info", text: `Some sources didn't answer this time (${down.join(", ")}). The rest are shown.` });
    } catch (e) {
      setMsg({ tone: "error", text: e instanceof Error ? e.message : "Could not load jobs" });
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }
  useEffect(() => { void load(); }, []);
  useEffect(() => {  // the live sync (every 3 minutes) signals when the feed was refreshed
    const on = () => void load();
    window.addEventListener("saige:refresh", on);
    return () => window.removeEventListener("saige:refresh", on);
  }, []);

  const sources = useMemo(() => [...new Set((data?.items ?? []).map((i) => i.source_label))].sort(), [data]);
  const shown = useMemo(() => {
    const q = f.q.trim().toLowerCase();
    const out = (data?.items ?? []).filter((i) => {
      if (!inTab(i, tab)) return false;
      if (q && !`${i.title} ${i.company} ${i.location ?? ""} ${i.matched_skills.join(" ")}`.toLowerCase().includes(q)) return false;
      if (f.source && i.source_label !== f.source) return false;
      if (i.score < f.min) return false;
      if (f.posted) { const d = daysAgo(i.posted); if (d == null || d > f.posted) return false; }
      if (f.exp && (i.exp_min != null || i.exp_max != null)) {
        const [lo, hi] = EXP_RANGES[f.exp];
        if ((i.exp_min ?? 0) > hi || (i.exp_max ?? i.exp_min ?? 60) < lo) return false;
      }
      if (f.type && !(i.employment_type ?? "").toLowerCase().replace(/[\s_-]/g, "").includes(f.type)) return false;
      if (f.email && !i.hr_emails?.length) return false;
      return true;
    });
    if (f.sort === "new") out.sort((a, b) => (Date.parse(b.posted ?? "") || 0) - (Date.parse(a.posted ?? "") || 0));
    return out;
  }, [data, tab, f]);

  useEffect(() => setLimit(PAGE), [tab, f]);

  const selectable = shown.filter((i) => !i.saved_job_id);
  const allPicked = selectable.length > 0 && selectable.every((i) => picked.has(i.id));
  const toggle = (id: string) => setPicked((p) => { const n = new Set(p); if (n.has(id)) n.delete(id); else n.add(id); return n; });

  async function save(prepare: boolean) {
    const ids = [...picked];
    if (!ids.length) return;
    setSaving(true);
    setMsg(null);
    try {
      let saved = 0, prepared = 0;
      for (let i = 0; i < ids.length; i += 100) {
        const r = await request<{ saved: number; applications_prepared: number }>("/jobs/feed/save", { method: "POST", body: { ids: ids.slice(i, i + 100), prepare_applications: prepare } });
        saved += r.saved;
        prepared += r.applications_prepared;
      }
      setMsg({ tone: "success", text: prepare
        ? <>Saved {saved} job(s) and prepared {prepared} application(s) with your best resume. <Link href="/applications" className="font-medium underline">Review &amp; approve them</Link>.</>
        : `Saved ${saved} job(s) to your list.` });
      setPicked(new Set());
      onSaved();
      await load();
    } catch (e) {
      setMsg({ tone: "error", text: e instanceof Error ? e.message : "Save failed" });
    } finally {
      setSaving(false);
    }
  }

  const c = data?.counts;
  const countryName = data?.country ?? "your country";
  const tabs: { id: Tab; label: string; n?: number }[] = [
    { id: "foryou", label: "For you", n: c ? c.country + c.remote : undefined },
    { id: "country", label: `In ${countryName}`, n: c?.country },
    { id: "remote", label: "Remote", n: c?.remote },
    { id: "walk_in", label: "Walk-in drives", n: c?.walk_in },
    { id: "alerts", label: "Job alerts", n: c?.alerts },
    { id: "careers", label: "Career pages", n: c?.careers },
    { id: "abroad", label: "Abroad", n: c?.abroad },
  ];

  return (
    <Card className="animate-rise mb-6" style={{ borderColor: "color-mix(in srgb, var(--tone-orange) 30%, transparent)" }}>
      <CardHeader className="gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <CardTitle className="flex items-center gap-2 text-lg">
            <span className="grid size-8 place-items-center rounded-lg text-[#0b0b0c]" style={{ background: "var(--tone-orange)" }}><Zap className="size-4" /></span>
            Jobs for you
          </CardTitle>
          <CardDescription className="mt-1">
            {data?.roles.length ? <>Every job for <b>{data.roles.join(", ")}</b>{data.country && <> in <b>{data.country}</b></>} and remote, fetched automatically from job sites, company career pages and your LinkedIn / Naukri / Indeed job alerts. </> : "Fetched automatically for your target roles and country. "}
            {data?.built_at && <span>Updated {formatDate(data.built_at)}.</span>}
          </CardDescription>
        </div>
        <Button variant="outline" size="sm" disabled={refreshing || loading} onClick={() => load(true)}>
          <RefreshCw className={cn(refreshing && "animate-spin")} /> {refreshing ? "Fetching…" : "Refresh"}
        </Button>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {msg && <Notice tone={msg.tone}>{msg.text}</Notice>}
        {loading && (
          <div className="flex flex-col items-center gap-3 py-12 text-sm text-muted-foreground">
            <Loader3D size={56} /> Fetching jobs for your roles from every source…
          </div>
        )}
        {data && (
          <>
            <div role="tablist" className="-mx-1 flex gap-1.5 overflow-x-auto px-1 pb-1">
              {tabs.map((t) => (
                <button key={t.id} role="tab" aria-selected={tab === t.id} onClick={() => setTab(t.id)}
                  className={cn("shrink-0 rounded-full border px-3.5 py-1.5 text-sm transition-colors", tab === t.id ? "border-transparent font-medium text-[#0b0b0c]" : "text-muted-foreground hover:text-foreground")}
                  style={tab === t.id ? { background: "var(--tone-orange)" } : undefined}>
                  {t.label}{t.n != null && <span className="ml-1.5 tabular-nums opacity-70">{t.n}</span>}
                </button>
              ))}
            </div>

            <div className="flex flex-wrap gap-2 [&>select]:w-auto [&>select]:min-w-[9.5rem] [&>select]:flex-1 sm:[&>select]:flex-none">
              <div className="relative min-w-[16rem] flex-[2]">
                <Search className="pointer-events-none absolute left-3 top-3 size-4 text-muted-foreground" />
                <Input className="pl-9" placeholder="Filter by title, company, skill" value={f.q} onChange={(e) => setF({ ...f, q: e.target.value })} />
              </div>
              <Select aria-label="Source" value={f.source} onChange={(e) => setF({ ...f, source: e.target.value })}>
                <option value="">All sources</option>
                {sources.map((s) => <option key={s}>{s}</option>)}
              </Select>
              <Select aria-label="Minimum match" value={f.min} onChange={(e) => setF({ ...f, min: Number(e.target.value) })}>
                {[0, 55, 70, 85].map((v) => <option key={v} value={v}>{v ? `${v}%+ match` : "Any match"}</option>)}
              </Select>
              <Select aria-label="Posted" value={f.posted} onChange={(e) => setF({ ...f, posted: Number(e.target.value) })}>
                <option value={0}>Any date</option><option value={1}>Last 24 hours</option><option value={3}>Last 3 days</option>
                <option value={7}>Last 7 days</option><option value={30}>Last 30 days</option>
              </Select>
              <Select aria-label="Experience" value={f.exp} onChange={(e) => setF({ ...f, exp: e.target.value })}>
                <option value="">Any experience</option>
                {Object.keys(EXP_RANGES).map((k) => <option key={k} value={k}>{k} years</option>)}
              </Select>
              <Select aria-label="Job type" value={f.type} onChange={(e) => setF({ ...f, type: e.target.value })}>
                <option value="">Any type</option><option value="fulltime">Full-time</option><option value="contract">Contract</option>
                <option value="parttime">Part-time</option><option value="intern">Internship</option>
              </Select>
              <Select aria-label="Sort" value={f.sort} onChange={(e) => setF({ ...f, sort: e.target.value })}>
                <option value="match">Best match</option><option value="new">Newest</option>
              </Select>
            </div>

            <div className="flex flex-wrap items-center gap-3 text-sm">
              <button type="button" onClick={() => setPicked(allPicked ? new Set() : new Set(selectable.map((i) => i.id)))} className="inline-flex items-center gap-1.5 font-medium">
                {allPicked ? <CheckSquare className="size-4" style={{ color: "var(--tone-orange)" }} /> : <Square className="size-4" />} Select all
              </button>
              <label className="inline-flex items-center gap-1.5 text-muted-foreground">
                <input type="checkbox" className="size-4 accent-[var(--tone-orange)]" checked={f.email} onChange={(e) => setF({ ...f, email: e.target.checked })} /> Has HR email
              </label>
              <span className="text-muted-foreground">{shown.length} job(s) · {picked.size} selected</span>
              <div className="ml-auto flex gap-2">
                <Button size="sm" variant="outline" disabled={!picked.size || saving} onClick={() => save(false)}>Save selected</Button>
                <Button size="sm" disabled={!picked.size || saving} onClick={() => save(true)}>
                  {saving ? <Loader2 className="animate-spin" /> : <Bot />} {saving ? "Working…" : `Auto-apply to ${picked.size || ""} selected`}
                </Button>
              </div>
            </div>

            <ul className="flex flex-col gap-2">
              {shown.length === 0 && (
                <li className="rounded-2xl border border-dashed py-10 text-center text-sm text-muted-foreground">
                  {tab === "walk_in" ? "No walk-in drives for your roles right now. They appear here when a posting or a Naukri alert announces one."
                    : tab === "alerts" ? <>No job alerts yet. Turn on LinkedIn / Naukri / Indeed job alerts and connect Gmail. <Link href="/integrations#portals" className="underline">How to set up</Link></>
                    : "No jobs match these filters."}
                </li>
              )}
              {shown.slice(0, limit).map((i) => <FeedRow key={i.id} i={i} picked={picked.has(i.id)} onToggle={() => toggle(i.id)} />)}
            </ul>
            {shown.length > limit && <Button variant="outline" className="self-center" onClick={() => setLimit(limit + PAGE)}>Show more ({shown.length - limit} left)</Button>}
          </>
        )}
      </CardContent>
    </Card>
  );
}

const SCOPE_LABEL: Record<JobScope, string> = { country: "", remote: "Remote", abroad: "Abroad" };

function FeedRow({ i, picked, onToggle }: { i: FeedItem; picked: boolean; onToggle: () => void }) {
  const exp = i.exp_min != null ? `${i.exp_min}${i.exp_max != null && i.exp_max !== i.exp_min ? `–${i.exp_max}` : "+"} yrs` : null;
  return (
    <li>
      <label className={cn("flex cursor-pointer items-start gap-3 rounded-2xl border p-3 transition-colors hover:bg-muted/40", picked && "bg-muted/50")}>
        <input type="checkbox" className="mt-1.5 size-4 accent-[var(--tone-orange)]" checked={picked} disabled={!!i.saved_job_id} onChange={onToggle} />
        <span className="grid size-11 shrink-0 place-items-center rounded-xl text-sm font-semibold text-[#0b0b0c]" style={{ background: `var(--tone-${scoreTone(i.score)})` }} title="Match with your profile">{i.score}</span>
        <span className="min-w-0 flex-1">
          <span className="block truncate font-medium">{i.title}</span>
          <span className="flex flex-wrap items-center gap-x-2 text-sm text-muted-foreground">
            <span className="truncate">{i.company || "Company not listed"}</span>
            {i.location && <span className="inline-flex items-center gap-0.5 truncate"><MapPin className="size-3" />{i.location}</span>}
            {SCOPE_LABEL[i.scope] && <span>· {SCOPE_LABEL[i.scope]}</span>}
            {exp && <span>· {exp}</span>}
            {i.posted && <span title={i.posted} style={{ color: (daysAgo(i.posted) ?? 99) <= 3 ? "var(--tone-green)" : undefined }}>· Posted {timeAgo(i.posted)}</span>}
          </span>
          <span className="mt-1.5 flex flex-wrap gap-1.5 text-[11px]">
            <span className="rounded-full border px-2 py-0.5">{i.source_label}</span>
            {i.employment_type && <span className="rounded-full border px-2 py-0.5">{i.employment_type}</span>}
            {i.walk_in && (
              <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-medium text-[#0b0b0c]" style={{ background: "var(--tone-yellow)" }}>
                <CalendarClock className="size-3" /> Walk-in{i.walk_in.date ? ` · ${i.walk_in.date}` : ""}{i.walk_in.time ? ` · ${i.walk_in.time}` : ""}
              </span>
            )}
            {i.hr_emails?.[0] && <span className="inline-flex items-center gap-1 rounded-full border px-2 py-0.5" style={{ color: "var(--tone-teal)" }}><Mail className="size-3" /> {i.hr_emails[0]}{i.apply_by_email ? " · apply by email" : ""}</span>}
          </span>
          {i.walk_in?.venue && <span className="mt-1 block truncate text-xs text-muted-foreground">Venue: {i.walk_in.venue}</span>}
          {i.matched_skills.length > 0 && <span className="mt-1 block truncate text-xs" style={{ color: "var(--tone-green)" }}>✓ {i.matched_skills.join(" · ")}</span>}
        </span>
        <span className="flex shrink-0 flex-col items-end gap-1 text-xs">
          {i.saved_job_id && <Link href={`/jobs/${i.saved_job_id}`} className="font-medium underline">Saved</Link>}
          {i.url && <a href={i.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-muted-foreground hover:text-foreground" onClick={(e) => e.stopPropagation()}>View <ExternalLink className="size-3" /></a>}
        </span>
      </label>
    </li>
  );
}

/** Auto-applier settings: prepares applications for strong matches every day; you approve them in one click. */
export function AutoApplyCard() {
  const { data, reload } = useApi<AutomationSettings>("/automation/status");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<Msg>(null);
  const a = data?.auto_apply;

  async function update(patch: Partial<AutoApplySettings>) {
    if (!a) return;
    await request("/automation/settings", { method: "PUT", body: { auto_apply: { ...a, ...patch } } });
    await reload();
  }

  async function run() {
    setBusy(true);
    setMsg(null);
    try {
      const r = await request<{ prepared?: number; skipped?: string }>("/jobs/auto-apply/run", { method: "POST" });
      setMsg(r.prepared
        ? { tone: "success", text: <>Prepared {r.prepared} application(s). <Link href="/applications" className="font-medium underline">Approve them</Link>.</> }
        : { tone: "info", text: r.skipped ? `Nothing prepared: ${r.skipped}.` : "No new jobs at or above your match threshold right now." });
    } catch (e) {
      setMsg({ tone: "error", text: e instanceof Error ? e.message : "Auto-apply failed" });
    } finally {
      setBusy(false);
    }
  }

  const toggleScope = (s: JobScope) => a && update({ scopes: a.scopes.includes(s) ? a.scopes.filter((x) => x !== s) : [...a.scopes, s] });

  return (
    <Card className="animate-rise mb-6" style={{ borderColor: "color-mix(in srgb, var(--tone-purple) 30%, transparent)" }}>
      <CardHeader className="gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <CardTitle className="flex items-center gap-2 text-lg">
            <span className="grid size-8 place-items-center rounded-lg text-[#0b0b0c]" style={{ background: "var(--tone-purple)" }}><Bot className="size-4" /></span>
            Auto-applier
            {a && <span className="rounded-full px-2 py-0.5 text-[11px] font-semibold text-[#0b0b0c]" style={{ background: a.enabled ? "var(--tone-green)" : "var(--muted-foreground)" }}>{a.enabled ? "On · daily" : "Off"}</span>}
          </CardTitle>
          <CardDescription className="mt-1 max-w-3xl">
            Every morning Saige picks jobs at or above your match score, attaches your best resume and prepares each application. You approve them all in one click in Applications:
            postings that ask for CVs by email are sent from your Gmail; others open the employer&apos;s page to submit. You get a WhatsApp message at each step.
          </CardDescription>
        </div>
        <Button size="sm" disabled={busy || !a} onClick={run}>{busy ? <Loader2 className="animate-spin" /> : <Zap />} Run now</Button>
      </CardHeader>
      {a && (
        <CardContent className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center gap-x-6 gap-y-3 text-sm">
            <label className="inline-flex items-center gap-2 font-medium">
              <input type="checkbox" className="size-4 accent-[var(--tone-purple)]" checked={a.enabled} onChange={(e) => update({ enabled: e.target.checked })} /> Run every day
            </label>
            <label className="inline-flex items-center gap-2">Match at least
              <Select className="h-8 w-24" value={a.min_score} onChange={(e) => update({ min_score: Number(e.target.value) })}>
                {[60, 65, 70, 75, 80, 85, 90].map((v) => <option key={v} value={v}>{v}%</option>)}
              </Select>
            </label>
            <label className="inline-flex items-center gap-2">Up to
              <Select className="h-8 w-20" value={a.daily_max} onChange={(e) => update({ daily_max: Number(e.target.value) })}>
                {[3, 5, 10, 15, 20, 25].map((v) => <option key={v} value={v}>{v}</option>)}
              </Select> a day
            </label>
            <span className="inline-flex items-center gap-3">
              {(["country", "remote", "abroad"] as JobScope[]).map((s) => (
                <label key={s} className="inline-flex items-center gap-1.5">
                  <input type="checkbox" className="size-4 accent-[var(--tone-purple)]" checked={a.scopes.includes(s)} onChange={() => toggleScope(s)} />
                  {s === "country" ? "In my country" : s === "remote" ? "Remote" : "Abroad"}
                </label>
              ))}
            </span>
            <label className="inline-flex items-center gap-1.5">
              <input type="checkbox" className="size-4 accent-[var(--tone-purple)]" checked={a.email_apply} onChange={(e) => update({ email_apply: e.target.checked })} /> Send email applications from Gmail after I approve
            </label>
          </div>
          {msg && <Notice tone={msg.tone}>{msg.text}</Notice>}
        </CardContent>
      )}
    </Card>
  );
}
