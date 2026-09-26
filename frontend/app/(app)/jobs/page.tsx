"use client";

import { Link2, Plus, RefreshCw, Search, Trash2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Notice, PageHeader } from "@/components/app-shell";
import { JobDiscover } from "@/components/job-discover";
import { AutoApplyCard, JobsFeed } from "@/components/jobs-feed";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input, Select, Textarea } from "@/components/ui/form";
import { useApi } from "@/hooks/use-api";
import { request } from "@/services/api";
import type { JobDetail, JobSource, JobStatus, JobSummary } from "@/types/api";
import { cn } from "@/utils/cn";
import { formatDate, formatSalary, scoreTone, timeAgo } from "@/utils/format";

type Msg = { tone: "success" | "error" | "info"; text: React.ReactNode } | null;

const CLASSIFICATIONS = ["Highly Relevant", "Relevant", "Potential Match", "Low Match", "Not Relevant"];
const STATUSES: (JobStatus | "")[] = ["", "new", "saved", "shortlisted", "archived", "rejected"];

function ImportCard({ onImported }: { onImported: () => void }) {
  const [mode, setMode] = useState<"paste" | "url">("paste");
  const [form, setForm] = useState({ title: "", company: "", location: "", application_url: "", description: "" });
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<Msg>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setMsg(null);
    try {
      const r =
        mode === "paste"
          ? await request<{ job: JobDetail; duplicate: boolean }>("/jobs/import", {
              method: "POST",
              body: {
                ...form,
                location: form.location || null,
                application_url: form.application_url || null,
                source: "manual",
              },
            })
          : await request<{ job: JobDetail; duplicate: boolean }>("/jobs/import-url", { method: "POST", body: { url } });
      setMsg({
        tone: "success",
        text: (
          <>
            {r.duplicate ? "Already tracked — merged into " : "Imported "}
            <Link href={`/jobs/${r.job.id}`} className="font-medium underline">
              {r.job.title} at {r.job.company}
            </Link>
            {r.job.score != null && ` · ${r.job.score}% match`}
          </>
        ),
      });
      setForm({ title: "", company: "", location: "", application_url: "", description: "" });
      setUrl("");
      onImported();
    } catch (err) {
      setMsg({ tone: "error", text: err instanceof Error ? err.message : "Import failed" });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Add a job</CardTitle>
        <CardDescription>
          Paste any job description (LinkedIn, Naukri, Indeed, company sites), or import a Greenhouse, Lever or Ashby link automatically.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div role="tablist" className="mb-4 inline-flex rounded-md border p-0.5 text-sm">
          {(["paste", "url"] as const).map((m) => (
            <button
              key={m}
              role="tab"
              aria-selected={mode === m}
              onClick={() => setMode(m)}
              className={cn("cursor-pointer rounded px-3 py-1", mode === m ? "bg-accent font-medium text-accent-foreground" : "text-muted-foreground")}
            >
              {m === "paste" ? "Paste JD" : "From URL"}
            </button>
          ))}
        </div>
        <form onSubmit={submit} className="flex flex-col gap-3">
          {mode === "paste" ? (
            <>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <Field label="Job title *"><Input required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></Field>
                <Field label="Company *"><Input required value={form.company} onChange={(e) => setForm({ ...form, company: e.target.value })} /></Field>
                <Field label="Location"><Input value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} /></Field>
                <Field label="Posting URL"><Input type="url" placeholder="https://" value={form.application_url} onChange={(e) => setForm({ ...form, application_url: e.target.value })} /></Field>
              </div>
              <Field label="Job description *" hint="At least 30 characters. Include requirements and nice-to-haves for the best match.">
                <Textarea required minLength={30} rows={7} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
              </Field>
            </>
          ) : (
            <Field label="Posting URL" hint="Supported: boards.greenhouse.io, jobs.lever.co, jobs.ashbyhq.com. Other sites don't permit automated import — paste the JD instead.">
              <Input type="url" required placeholder="https://jobs.lever.co/company/..." value={url} onChange={(e) => setUrl(e.target.value)} />
            </Field>
          )}
          <div>
            <Button type="submit" disabled={busy}>
              {mode === "paste" ? <Plus /> : <Link2 />} {busy ? "Analyzing…" : "Import & score"}
            </Button>
          </div>
          {msg && <Notice tone={msg.tone}>{msg.text}</Notice>}
        </form>
      </CardContent>
    </Card>
  );
}

function SourcesCard({ onSynced }: { onSynced: () => void }) {
  const { data, reload } = useApi<JobSource[]>("/jobs/sources");
  const [form, setForm] = useState({ provider: "greenhouse", board: "", company_name: "" });
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<Msg>(null);

  async function add(e: React.FormEvent) {
    e.preventDefault();
    setMsg(null);
    try {
      await request("/jobs/sources", { method: "POST", body: { ...form, company_name: form.company_name || null } });
      setForm({ ...form, board: "", company_name: "" });
      await reload();
    } catch (err) {
      setMsg({ tone: "error", text: err instanceof Error ? err.message : "Could not add board" });
    }
  }

  async function sync(s: JobSource) {
    setBusy(s.id);
    setMsg(null);
    try {
      const r = await request<Record<string, number>>(`/jobs/sources/${s.id}/sync`, { method: "POST" });
      setMsg({
        tone: "success",
        text: `${s.board}: ${r.fetched} postings, ${r.new} new, ${r.duplicates} already tracked, ${r.skipped_irrelevant} skipped as unrelated to your target roles.`,
      });
      await reload();
      onSynced();
    } catch (err) {
      setMsg({ tone: "error", text: err instanceof Error ? err.message : "Sync failed" });
    } finally {
      setBusy(null);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Career pages you follow</CardTitle>
        <CardDescription>
          Saige already checks 17 companies' career pages for you. Add more companies that publish jobs on Greenhouse, Lever or Ashby. The board id is in their careers URL, e.g.
          boards.greenhouse.io/<b>stripe</b>.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <form onSubmit={add} className="grid gap-2 sm:grid-cols-[1fr_1.2fr_1.2fr_auto] sm:items-end">
          <Field label="Provider">
            <Select value={form.provider} onChange={(e) => setForm({ ...form, provider: e.target.value })}>
              <option value="greenhouse">Greenhouse</option>
              <option value="lever">Lever</option>
              <option value="ashby">Ashby</option>
            </Select>
          </Field>
          <Field label="Board id *"><Input required pattern="[A-Za-z0-9_.\-]{1,80}" value={form.board} onChange={(e) => setForm({ ...form, board: e.target.value })} /></Field>
          <Field label="Company name"><Input value={form.company_name} onChange={(e) => setForm({ ...form, company_name: e.target.value })} /></Field>
          <Button type="submit" variant="outline"><Plus /> Add</Button>
        </form>
        {msg && <Notice tone={msg.tone}>{msg.text}</Notice>}
        {(data ?? []).length > 0 && (
          <ul className="divide-y rounded-md border">
            {data!.map((s) => (
              <li key={s.id} className="flex items-center gap-3 px-3 py-2 text-sm">
                <Badge variant="muted" className="capitalize">{s.provider}</Badge>
                <span className="font-medium">{s.company_name || s.board}</span>
                <span className="hidden text-xs text-muted-foreground sm:inline">
                  {s.last_synced_at ? `synced ${formatDate(s.last_synced_at)}` : "never synced"}
                </span>
                <div className="ml-auto flex gap-1">
                  <Button size="sm" variant="outline" disabled={busy === s.id} onClick={() => sync(s)}>
                    <RefreshCw className={cn(busy === s.id && "animate-spin")} /> Sync
                  </Button>
                  <Button
                    size="icon"
                    variant="ghost"
                    aria-label={`Remove ${s.board}`}
                    onClick={async () => {
                      await request(`/jobs/sources/${s.id}`, { method: "DELETE" });
                      await reload();
                    }}
                  >
                    <Trash2 />
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

type View = "feed" | "saved" | "search" | "add";

export default function JobsPage() {
  const [view, setView] = useState<View>("feed");
  const [filters, setFilters] = useState({ q: "", classification: "", status: "", sort: "score" });
  const [applied, setApplied] = useState(filters);
  const qs = new URLSearchParams(Object.entries(applied).filter(([, v]) => v) as [string, string][]).toString();
  const { data, error, loading, reload } = useApi<{ total: number; items: JobSummary[] }>(`/jobs?${qs}`);
  const [rematching, setRematching] = useState(false);
  const views: { id: View; label: string }[] = [
    { id: "feed", label: "Jobs for you" },
    { id: "saved", label: `Saved jobs${data ? ` · ${data.total}` : ""}` },
    { id: "search", label: "Search any role" },
    { id: "add", label: "Add manually" },
  ];

  return (
    <>
      <PageHeader
        title="Jobs"
        description="Jobs for your target roles in your country, fetched automatically and scored against your verified profile. Select the ones you like, or let the auto-applier prepare them."
        actions={view === "saved" ? (
          <Button
            variant="outline"
            disabled={rematching}
            onClick={async () => {
              setRematching(true);
              try {
                await request("/jobs/rematch-all", { method: "POST" });
                await reload();
              } finally {
                setRematching(false);
              }
            }}
          >
            <RefreshCw className={cn(rematching && "animate-spin")} /> Re-score all
          </Button>
        ) : undefined}
      />
      <div role="tablist" className="mb-6 inline-flex flex-wrap rounded-full border bg-muted/50 p-1 text-sm">
        {views.map((v) => (
          <button key={v.id} role="tab" aria-selected={view === v.id} onClick={() => setView(v.id)}
            className={cn("rounded-full px-4 py-1.5 transition-colors", view === v.id ? "font-medium text-[#0b0b0c] shadow-sm" : "text-muted-foreground hover:text-foreground")}
            style={view === v.id ? { background: "var(--tone-orange)" } : undefined}>
            {v.label}
          </button>
        ))}
      </div>

      {view === "feed" && (
        <>
          <JobsFeed onSaved={reload} />
          <AutoApplyCard />
        </>
      )}
      {view === "search" && <JobDiscover onSaved={reload} />}
      {view === "add" && (
        <div className="mb-6 grid gap-6 xl:grid-cols-2">
          <ImportCard onImported={reload} />
          <SourcesCard onSynced={reload} />
        </div>
      )}

      {view === "saved" && (
      <>
      <form
        className="mb-3 flex flex-wrap items-end gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          setApplied(filters);
        }}
      >
        <div className="relative min-w-52 flex-1">
          <Search className="pointer-events-none absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
          <Input className="pl-8" placeholder="Search title, company, location" value={filters.q} onChange={(e) => setFilters({ ...filters, q: e.target.value })} />
        </div>
        <Select aria-label="Classification" className="w-44" value={filters.classification} onChange={(e) => setFilters({ ...filters, classification: e.target.value })}>
          <option value="">All matches</option>
          {CLASSIFICATIONS.map((c) => <option key={c}>{c}</option>)}
        </Select>
        <Select aria-label="Status" className="w-36" value={filters.status} onChange={(e) => setFilters({ ...filters, status: e.target.value })}>
          {STATUSES.map((s) => <option key={s} value={s}>{s ? s[0].toUpperCase() + s.slice(1) : "Active"}</option>)}
        </Select>
        <Select aria-label="Sort" className="w-36" value={filters.sort} onChange={(e) => setFilters({ ...filters, sort: e.target.value })}>
          <option value="score">Best match</option>
          <option value="recent">Most recent</option>
        </Select>
        <Button type="submit" variant="secondary">Apply</Button>
      </form>

      {error && <Notice tone="error">{error}</Notice>}
      {loading && !data && <p className="text-sm text-muted-foreground">Loading…</p>}
      {data && data.items.length === 0 && (
        <Card className="p-8 text-center text-sm text-muted-foreground">No saved jobs yet. Pick jobs in <b>Jobs for you</b> and click Save, or let the auto-applier prepare them.</Card>
      )}
      {data && data.items.length > 0 && (
        <>
          <p className="mb-2 text-xs text-muted-foreground">{data.total} job(s)</p>
          <ul className="flex flex-col gap-2">
            {data.items.map((j) => (
              <li key={j.id}>
                <Link href={`/jobs/${j.id}`}>
                  <Card className="flex items-center gap-4 p-4 transition-colors hover:bg-muted/60">
                    <div className={cn("grid size-12 shrink-0 place-items-center rounded-lg text-sm font-semibold tabular-nums",
                      j.score == null ? "bg-muted text-muted-foreground" : j.score >= 85 ? "bg-success/15 text-success" : j.score >= 70 ? "bg-accent text-accent-foreground" : "bg-muted text-foreground")}>
                      {j.score ?? "—"}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="truncate font-medium">{j.title}</p>
                        {j.classification && <Badge variant={scoreTone(j.score)}>{j.classification}</Badge>}
                        {j.status !== "new" && <Badge variant="outline" className="capitalize">{j.status}</Badge>}
                      </div>
                      <p className="truncate text-sm text-muted-foreground">
                        {j.company}
                        {j.location && ` · ${j.location}`}
                        {j.remote && " · Remote"}
                        {(j.salary_min || j.salary_max) && ` · ${formatSalary(j.salary_min, j.salary_max, j.currency)}`}
                      </p>
                    </div>
                    <div className="hidden text-right text-xs text-muted-foreground sm:block">
                      <p className="capitalize">{j.sources.join(", ")}</p>
                      <p>{j.posted_date ? `Posted ${timeAgo(j.posted_date)}` : `Saved ${formatDate(j.created_at)}`}</p>
                    </div>
                  </Card>
                </Link>
              </li>
            ))}
          </ul>
        </>
      )}
      </>
      )}
    </>
  );
}
