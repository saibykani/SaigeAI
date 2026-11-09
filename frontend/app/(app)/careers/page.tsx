"use client";

import { Building2, ChevronDown, ChevronUp, ExternalLink, Mail, MapPin, RefreshCw, Search, Sparkles, Star, Target } from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { Notice, PageHeader } from "@/components/app-shell";
import { CountKpi } from "@/components/kpi";
import { Loader3D } from "@/components/loader3d";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input, Select } from "@/components/ui/form";
import { useApi } from "@/hooks/use-api";
import { request } from "@/services/api";
import type { CareerChange, CareerFit, CareerJob, CareerJobDetail, CareerJobsPage, CareerPortals, CareerScan, CareerSettings } from "@/types/api";
import { cn } from "@/utils/cn";
import { formatDate, timeAgo } from "@/utils/format";

type View = "jobs" | "companies" | "settings";
type Msg = { tone: "success" | "error" | "warning" | "info"; text: React.ReactNode } | null;

const FIT_TONE: Record<CareerFit, string> = { strong: "green", good: "yellow", stretch: "orange", low: "red" };
const FIT_NAME: Record<CareerFit, string> = { strong: "Strong fit", good: "Good fit", stretch: "Stretch", low: "Not a fit" };
const SCOPE_NAME: Record<string, string> = { country: "In your country", remote: "Remote", abroad: "Abroad" };
const CHANGE_TONE: Record<CareerChange["kind"], string> = {
  add: "green", ok: "green", gap: "red", nice: "yellow", experience: "orange", title: "purple", info: "teal",
};
const EMPTY = { q: "", fits: "", countries: "", location: "", companies: "", tiers: "", scopes: "", posted_days: "", max_exp: "", remote: false, sort: "score" };

function Dot({ tone }: { tone: string }) {
  return <span aria-hidden className="inline-block size-2 shrink-0 rounded-full" style={{ background: `var(--tone-${tone})` }} />;
}

function Score({ value }: { value: number }) {
  const tone = value >= 80 ? "green" : value >= 65 ? "yellow" : value >= 50 ? "orange" : "red";
  return (
    <div className="flex size-14 shrink-0 flex-col items-center justify-center rounded-2xl border" style={{ borderColor: `color-mix(in oklab, var(--tone-${tone}) 45%, transparent)` }}>
      <span className="text-lg font-semibold leading-none" style={{ color: `var(--tone-${tone})` }}>{value}</span>
      <span className="mt-0.5 text-[10px] text-muted-foreground">match</span>
    </div>
  );
}

function ScanStatus({ scan }: { scan: CareerScan | null }) {
  if (!scan) return <p className="text-sm text-muted-foreground">No scan yet. Press Scan now to read every company career page for your roles.</p>;
  if (scan.status === "needs_profile") return <Notice tone="warning">{scan.error}</Notice>;
  const failed = (scan.companies ?? []).filter((c) => c.status === "error");
  return (
    <p className="text-sm text-muted-foreground">
      Last scan {scan.finished_at ? timeAgo(scan.finished_at) : "running"} for <span className="text-foreground">{scan.roles.join(", ")}</span>
      {scan.country ? ` · ${scan.country}` : ""} · {scan.found} open, {scan.new} new, {scan.closed} closed
      {failed.length > 0 && <span title={failed.map((f) => `${f.name}: ${f.error}`).join("\n")}> · {failed.length} portal(s) didn&apos;t answer</span>}
    </p>
  );
}

function JobDetailPanel({ id }: { id: string }) {
  const { data, error, loading } = useApi<CareerJobDetail>(`/careers/jobs/${id}`);
  const [full, setFull] = useState(false);
  if (loading) return <div className="py-6"><Loader3D size={40} label="Checking your fit" /></div>;
  if (error || !data) return <Notice tone="error">{error ?? "Couldn't load this job."}</Notice>;
  const dims = Object.entries(data.breakdown).filter(([, v]) => v != null) as [string, number][];
  return (
    <div className="mt-4 grid gap-5 border-t pt-4 lg:grid-cols-[1.3fr_1fr]">
      <div className="space-y-3">
        <p className="text-sm font-medium">What to change in your resume</p>
        {data.resume && (
          <p className="text-xs text-muted-foreground">
            Checked against <span className="text-foreground">{data.resume.name}</span>: covers {data.resume.overlap} of {data.resume.of} skills this posting asks for.
          </p>
        )}
        <ul className="space-y-2.5">
          {data.resume_changes.map((ch, i) => (
            <li key={i} className="rounded-xl border bg-card-solid/40 p-3">
              <p className="flex items-center gap-2 text-sm font-medium"><Dot tone={CHANGE_TONE[ch.kind]} />{ch.title}</p>
              <p className="mt-1 text-[13px] text-muted-foreground">{ch.text}</p>
              {ch.items && ch.items.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1.5">{ch.items.map((s) => <Badge key={s} variant="outline">{s}</Badge>)}</div>
              )}
            </li>
          ))}
        </ul>
      </div>
      <div className="space-y-4">
        <div>
          <p className="text-sm font-medium">{data.fit_label}</p>
          <div className="mt-2 space-y-1.5">
            {dims.map(([k, v]) => (
              <div key={k} className="flex items-center gap-3 text-xs">
                <span className="w-28 capitalize text-muted-foreground">{k.replace(/_/g, " ")}</span>
                <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
                  <span className="block h-full rounded-full" style={{ width: `${v}%`, background: "var(--tone-green)" }} />
                </span>
                <span className="w-9 text-right tabular-nums">{Math.round(v)}%</span>
              </div>
            ))}
          </div>
        </div>
        {data.matched_skills.length > 0 && (
          <div>
            <p className="text-xs text-muted-foreground">You match</p>
            <div className="mt-1.5 flex flex-wrap gap-1.5">{data.matched_skills.map((s) => <Badge key={s} variant="success">{s}</Badge>)}</div>
          </div>
        )}
        {data.description && (
          <div>
            <button type="button" onClick={() => setFull((x) => !x)} className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
              {full ? <ChevronUp className="size-3.5" /> : <ChevronDown className="size-3.5" />} {full ? "Hide" : "Read"} the job description
            </button>
            {full && <p className="mt-2 max-h-80 overflow-auto whitespace-pre-line rounded-xl border p-3 text-[13px] text-muted-foreground">{data.description}</p>}
          </div>
        )}
      </div>
    </div>
  );
}

function JobRow({ job, onMsg }: { job: CareerJob; onMsg: (m: Msg) => void }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  async function save() {
    setBusy(true);
    try {
      const r = await request<{ job_id: string; duplicate: boolean }>(`/careers/jobs/${job.id}/save`, { method: "POST" });
      router.push(`/jobs/${r.job_id}`);
    } catch (e) {
      onMsg({ tone: "error", text: e instanceof Error ? e.message : "Couldn't save this job." });
      setBusy(false);
    }
  }

  return (
    <li className={cn("rounded-2xl border p-4", !job.active && "opacity-60")}>
      <div className="flex gap-4">
        <Score value={job.score} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-semibold leading-snug">{job.title}</h3>
            {!job.active && <Badge variant="muted">Closed</Badge>}
            {Date.now() - Date.parse(job.first_seen) < 86_400_000 * 2 && job.active && <Badge variant="success">New</Badge>}
          </div>
          <p className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[13px] text-muted-foreground">
            <span className="flex items-center gap-1"><Building2 className="size-3.5" />{job.company}</span>
            <span className="flex items-center gap-1"><MapPin className="size-3.5" />{job.location || (job.remote ? "Remote" : "Location not listed")}</span>
            <span>{SCOPE_NAME[job.scope] ?? job.scope}</span>
            {job.posted && <span>Posted {formatDate(job.posted)}</span>}
            {job.exp_min != null && <span>{job.exp_min}{job.exp_max != null ? `–${job.exp_max}` : "+"} yrs</span>}
          </p>
          <p className="mt-2 flex items-center gap-2 text-[13px]"><Dot tone={FIT_TONE[job.fit]} />{job.fit_label}</p>
          {(job.matched_skills.length > 0 || job.missing_skills.length > 0) && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {job.matched_skills.slice(0, 5).map((s) => <Badge key={s} variant="success">{s}</Badge>)}
              {job.missing_skills.slice(0, 4).map((s) => <Badge key={s} variant="outline" className="text-muted-foreground">needs {s}</Badge>)}
            </div>
          )}
          <div className="mt-3 flex flex-wrap gap-2">
            <a href={job.url || job.careers_url} target="_blank" rel="noopener noreferrer" className="inline-flex h-8 items-center gap-1.5 rounded-full bg-primary px-3.5 text-xs font-medium text-primary-foreground">
              Open career page <ExternalLink className="size-3.5" />
            </a>
            <Button size="sm" variant="outline" onClick={() => setOpen((x) => !x)} aria-expanded={open}>
              <Target /> {open ? "Hide fit" : "Fit & resume changes"}
            </Button>
            <Button size="sm" variant="outline" onClick={save} disabled={busy}>
              <Star /> {job.saved_job_id ? "Open in Jobs" : "Save & tailor resume"}
            </Button>
          </div>
        </div>
      </div>
      {open && <JobDetailPanel id={job.id} />}
    </li>
  );
}

function JobsView({ onMsg }: { onMsg: (m: Msg) => void }) {
  const [f, setF] = useState(EMPTY);
  const [page, setPage] = useState(1);
  const qs = useMemo(() => {
    const p = new URLSearchParams({ sort: f.sort, page: String(page), page_size: "25" });
    for (const k of ["q", "fits", "countries", "location", "companies", "tiers", "scopes", "posted_days", "max_exp"] as const) if (f[k]) p.set(k, f[k]);
    if (f.remote) p.set("remote", "true");
    return p.toString();
  }, [f, page]);
  const { data, error, loading, reload } = useApi<CareerJobsPage>(`/careers/jobs?${qs}`);
  const portals = useApi<CareerPortals>("/careers/portals");
  const [scanning, setScanning] = useState(false);
  const [mailing, setMailing] = useState(false);

  const set = (k: keyof typeof EMPTY, v: string | boolean) => { setPage(1); setF((x) => ({ ...x, [k]: v })); };

  async function scan() {
    setScanning(true);
    onMsg({ tone: "info", text: "Reading company career pages… this takes up to a minute." });
    try {
      const r = await request<CareerScan>("/careers/scan", { method: "POST", body: {} });
      onMsg(r.status === "needs_profile" ? { tone: "warning", text: r.error } :
        { tone: "success", text: `Scanned ${r.companies?.length ?? 0} career portals: ${r.found} open roles, ${r.new} new, ${r.strong_new} new strong fits.` });
      await Promise.all([reload(), portals.reload()]);
    } catch (e) {
      onMsg({ tone: "error", text: e instanceof Error ? e.message : "Scan failed." });
    } finally {
      setScanning(false);
    }
  }

  async function mail() {
    setMailing(true);
    try {
      const r = await request<{ sent: number; to?: string; error?: string; reason?: string; skipped?: string }>("/careers/digest", { method: "POST", body: { test: true } });
      onMsg(r.sent ? { tone: "success", text: `Emailed ${r.sent} job(s) to ${r.to}.` } : { tone: r.error ? "warning" : "info", text: r.error ?? r.skipped ?? r.reason ?? "Nothing to send." });
    } catch (e) {
      onMsg({ tone: "error", text: e instanceof Error ? e.message : "Couldn't send the email." });
    } finally {
      setMailing(false);
    }
  }

  const fits = data?.facets.fits ?? [];
  const strong = fits.find((x) => x.value === "strong")?.count ?? 0;
  const totalOpen = fits.reduce((a, x) => a + x.count, 0);
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;
  const tiers = portals.data?.tiers ?? {};

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <ScanStatus scan={data?.scan ?? null} />
        <div className="flex gap-2">
          <Button variant="outline" onClick={mail} disabled={mailing}><Mail /> {mailing ? "Sending…" : "Email me these"}</Button>
          <Button onClick={scan} disabled={scanning}><RefreshCw className={cn(scanning && "animate-spin")} /> {scanning ? "Scanning…" : "Scan now"}</Button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <CountKpi label="Open roles for you" value={totalOpen} icon={Search} tone="orange" />
        <CountKpi label="Strong fits" value={strong} hint="80%+ match" icon={Sparkles} tone="green" delay={60} />
        <CountKpi label="New in last scan" value={data?.scan?.new ?? 0} icon={Star} tone="yellow" delay={120} />
        <CountKpi label="Companies hiring" value={data?.facets.companies.length ?? 0} icon={Building2} tone="purple" delay={180} />
      </div>

      <Card>
        <CardContent className="grid gap-3 pt-5 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="Search" className="sm:col-span-2">
            <Input placeholder="Title, company, skill or city" value={f.q} onChange={(e) => set("q", e.target.value)} />
          </Field>
          <Field label="Fit">
            <Select value={f.fits} onChange={(e) => set("fits", e.target.value)}>
              <option value="">Any fit</option>
              <option value="strong,good">Strong + good</option>
              {(["strong", "good", "stretch", "low"] as CareerFit[]).map((x) => <option key={x} value={x}>{FIT_NAME[x]}</option>)}
            </Select>
          </Field>
          <Field label="Sort">
            <Select value={f.sort} onChange={(e) => set("sort", e.target.value)}>
              <option value="score">Best match</option><option value="recent">Recently posted</option>
              <option value="new">Newly found</option><option value="company">Company A–Z</option>
            </Select>
          </Field>
          <Field label="Country">
            <Select value={f.countries} onChange={(e) => set("countries", e.target.value)}>
              <option value="">All countries</option>
              {(data?.facets.countries ?? []).map((x) => <option key={x.value} value={x.value}>{x.label} ({x.count})</option>)}
            </Select>
          </Field>
          <Field label="City or location">
            <Input placeholder="e.g. Hyderabad" value={f.location} onChange={(e) => set("location", e.target.value)} />
          </Field>
          <Field label="Where">
            <Select value={f.scopes} onChange={(e) => set("scopes", e.target.value)}>
              <option value="">Anywhere</option><option value="country,remote">My country + remote</option>
              <option value="country">In my country</option><option value="remote">Remote</option><option value="abroad">Abroad</option>
            </Select>
          </Field>
          <Field label="Company">
            <Select value={f.companies} onChange={(e) => set("companies", e.target.value)}>
              <option value="">All companies</option>
              {(data?.facets.companies ?? []).map((x) => <option key={x.value} value={x.value}>{x.label} ({x.count})</option>)}
            </Select>
          </Field>
          <Field label="Company group">
            <Select value={f.tiers} onChange={(e) => set("tiers", e.target.value)}>
              <option value="">All groups</option>
              {Object.entries(tiers).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </Select>
          </Field>
          <Field label="Posted within">
            <Select value={f.posted_days} onChange={(e) => set("posted_days", e.target.value)}>
              <option value="">Any time</option><option value="1">24 hours</option><option value="7">7 days</option>
              <option value="14">14 days</option><option value="30">30 days</option>
            </Select>
          </Field>
          <Field label="My experience (years)">
            <Input type="number" min={0} max={50} placeholder="Hide roles needing more" value={f.max_exp} onChange={(e) => set("max_exp", e.target.value)} />
          </Field>
          <div className="flex items-end justify-between gap-3">
            <label className="flex h-10 items-center gap-2 text-sm">
              <input type="checkbox" checked={f.remote} onChange={(e) => set("remote", e.target.checked)} className="size-4 accent-[var(--tone-green)]" /> Remote only
            </label>
            <Button variant="ghost" size="sm" onClick={() => { setPage(1); setF(EMPTY); }}>Clear</Button>
          </div>
        </CardContent>
      </Card>

      {error && <Notice tone="error">{error}</Notice>}
      {loading && !data ? (
        <div className="py-16"><Loader3D label="Loading career jobs" /></div>
      ) : data && data.items.length === 0 ? (
        <Card><CardContent className="py-12 text-center text-sm text-muted-foreground">
          {data.scan ? "No jobs match these filters. Clear a filter or scan again." : "Press Scan now to read company career pages for your roles."}
        </CardContent></Card>
      ) : (
        <>
          <p className="text-sm text-muted-foreground">{data?.total ?? 0} job(s)</p>
          <ul className="space-y-3">{data?.items.map((j) => <JobRow key={j.id} job={j} onMsg={onMsg} />)}</ul>
          {pages > 1 && (
            <div className="flex items-center justify-center gap-3">
              <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Previous</Button>
              <span className="text-sm text-muted-foreground">Page {page} of {pages}</span>
              <Button variant="outline" size="sm" disabled={page >= pages} onClick={() => setPage((p) => p + 1)}>Next</Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function CompaniesView() {
  const { data, error, loading } = useApi<CareerPortals>("/careers/portals");
  if (loading && !data) return <div className="py-16"><Loader3D label="Loading companies" /></div>;
  if (error || !data) return <Notice tone="error">{error ?? "Couldn't load companies."}</Notice>;
  const portalOnly = data.companies.filter((c) => !c.api);
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Google, Meta, Apple, Microsoft, Netflix</CardTitle>
          <CardDescription>
            These companies don&apos;t publish a public jobs API, and Saige never scrapes them. Each link opens their own careers search already
            filtered to your role{data.location ? ` and ${data.location}` : ""}.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {portalOnly.map((c) => (
            <div key={c.id} className="rounded-2xl border p-4">
              <p className="font-medium">{c.name}</p>
              <div className="mt-2 flex flex-col gap-1.5">
                {(c.role_links.length ? c.role_links : [{ role: "Careers", url: c.careers_url }]).map((l) => (
                  <a key={l.role} href={l.url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1.5 text-sm text-primary">
                    {l.role} <ExternalLink className="size-3.5" />
                  </a>
                ))}
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
      {Object.entries(data.tiers).map(([tier, label]) => {
        const list = data.companies.filter((c) => c.api && c.tiers.includes(tier));
        if (!list.length) return null;
        return (
          <Card key={tier}>
            <CardHeader><CardTitle>{label}</CardTitle></CardHeader>
            <CardContent className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {list.map((c) => (
                <a key={c.id} href={c.careers_url} target="_blank" rel="noopener noreferrer"
                   className={cn("flex items-center justify-between rounded-xl border px-3 py-2.5 text-sm", !c.selected && "opacity-50")}>
                  <span className="flex items-center gap-2">{c.name} <ExternalLink className="size-3 text-muted-foreground" /></span>
                  <span className="text-xs text-muted-foreground">{c.selected ? `${c.open_jobs} open` : "not scanned"}</span>
                </a>
              ))}
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}

function SettingsView({ onMsg }: { onMsg: (m: Msg) => void }) {
  const { data, error, setData } = useApi<CareerPortals>("/careers/portals");
  const [draft, setDraft] = useState<CareerSettings | null>(null);
  const [busy, setBusy] = useState(false);
  const s = draft ?? data?.settings ?? null;
  if (error) return <Notice tone="error">{error}</Notice>;
  if (!s || !data) return <div className="py-16"><Loader3D label="Loading settings" /></div>;
  const upd = (patch: Partial<CareerSettings>) => setDraft({ ...s, ...patch });
  const list = (v: string) => v.split(",").map((x) => x.trim()).filter(Boolean);

  async function save() {
    if (!s) return;
    setBusy(true);
    try {
      const saved = await request<CareerSettings>("/careers/settings", { method: "PUT", body: s });
      setData((d) => (d ? { ...d, settings: saved } : d));
      setDraft(null);
      onMsg({ tone: "success", text: "Career jobs settings saved." });
    } catch (e) {
      onMsg({ tone: "error", text: e instanceof Error ? e.message : "Couldn't save." });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Daily scan and email</CardTitle>
        <CardDescription>Every day Saige reads the career pages below, scores each opening against your verified profile, and emails you the new matches.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="flex flex-wrap gap-6">
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="size-4 accent-[var(--tone-green)]" checked={s.enabled} onChange={(e) => upd({ enabled: e.target.checked })} /> Scan every day</label>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="size-4 accent-[var(--tone-green)]" checked={s.email_digest} onChange={(e) => upd({ email_digest: e.target.checked })} /> Email me new matches</label>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Field label="Time (your timezone)"><Input type="time" value={s.time} onChange={(e) => upd({ time: e.target.value })} /></Field>
          <Field label="Email only matches from" hint="Match score, 0–100"><Input type="number" min={0} max={100} value={s.min_score} onChange={(e) => upd({ min_score: Number(e.target.value) })} /></Field>
          <Field label="Send to" hint="Empty: your account email"><Input type="email" value={s.digest_to} onChange={(e) => upd({ digest_to: e.target.value })} /></Field>
          <Field label="Roles" hint={`Empty: your profile's target roles (${data.roles.join(", ") || "none set"})`} className="sm:col-span-2">
            <Input value={s.roles.join(", ")} onChange={(e) => upd({ roles: list(e.target.value).slice(0, 5) })} placeholder="SDET, QA Automation Engineer" />
          </Field>
          <Field label="Email locations" hint="Empty: your country + remote">
            <Input value={s.locations.join(", ")} onChange={(e) => upd({ locations: list(e.target.value) })} placeholder="Hyderabad, Bengaluru" />
          </Field>
        </div>
        <div>
          <p className="text-xs font-medium text-muted-foreground">Company groups to scan (none selected: all of them)</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {Object.entries(data.tiers).map(([k, v]) => {
              const on = s.tiers.includes(k);
              return (
                <button key={k} type="button" aria-pressed={on} onClick={() => upd({ tiers: on ? s.tiers.filter((x) => x !== k) : [...s.tiers, k] })}
                        className={cn("rounded-full border px-3.5 py-1.5 text-sm", on ? "border-foreground bg-foreground text-background" : "text-muted-foreground")}>
                  {v}
                </button>
              );
            })}
          </div>
        </div>
        <div className="flex justify-end"><Button onClick={save} disabled={busy || !draft}>{busy ? "Saving…" : "Save settings"}</Button></div>
      </CardContent>
    </Card>
  );
}

export default function CareersPage() {
  const [view, setView] = useState<View>("jobs");
  const [msg, setMsg] = useState<Msg>(null);
  return (
    <div>
      <PageHeader
        title="Career portals"
        description="Openings for your roles, read straight from company career pages: FAANG, big tech, AI labs, fintech, SaaS and Indian product companies. Each job shows how well you fit and what to change in your resume."
      />
      <div className="mb-6 inline-flex rounded-full border bg-muted/50 p-1 text-sm" role="tablist">
        {([["jobs", "Jobs"], ["companies", "Companies"], ["settings", "Daily email"]] as [View, string][]).map(([k, label]) => (
          <button key={k} type="button" role="tab" aria-selected={view === k} onClick={() => setView(k)}
                  className={cn("rounded-full px-4 py-1.5", view === k ? "bg-background font-medium shadow-sm" : "text-muted-foreground")}>
            {label}
          </button>
        ))}
      </div>
      {msg && <div className="mb-4"><Notice tone={msg.tone}>{msg.text}</Notice></div>}
      {view === "jobs" && <JobsView onMsg={setMsg} />}
      {view === "companies" && <CompaniesView />}
      {view === "settings" && <SettingsView onMsg={setMsg} />}
    </div>
  );
}
