"use client";

import { Bot, Building2, CalendarClock, CheckSquare, ExternalLink, Loader2, Mail, Send, Square } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Notice, PageHeader } from "@/components/app-shell";
import { CountUp } from "@/components/motion";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useApi } from "@/hooks/use-api";
import { request } from "@/services/api";
import type { Application, ApplicationStatus } from "@/types/api";
import { formatDate, humanStatus } from "@/utils/format";

/** Pipeline columns; each groups related statuses. Stage order drives an ordinal blue accent. */
const COLUMNS: { title: string; statuses: ApplicationStatus[]; ord: number }[] = [
  { title: "To apply", statuses: ["SHORTLISTED", "READY_TO_APPLY", "APPROVAL_REQUIRED", "APPLYING", "APPLICATION_FAILED"], ord: 1 },
  { title: "Applied", statuses: ["APPLIED", "RECRUITER_CONTACTED"], ord: 3 },
  { title: "In process", statuses: ["RECRUITER_REPLIED", "SCREENING", "ASSESSMENT"], ord: 5 },
  { title: "Interviewing", statuses: ["INTERVIEW_SCHEDULED", "INTERVIEW_COMPLETED"], ord: 7 },
  { title: "Offer", statuses: ["OFFER"], ord: 8 },
];
const CLOSED: ApplicationStatus[] = ["REJECTED", "WITHDRAWN", "CLOSED"];

function statusTone(s: ApplicationStatus): "success" | "warning" | "destructive" | "default" | "muted" {
  if (s === "OFFER") return "success";
  if (s === "APPROVAL_REQUIRED" || s === "APPLYING") return "warning";
  if (s === "APPLICATION_FAILED" || s === "REJECTED") return "destructive";
  if (CLOSED.includes(s)) return "muted";
  return "default";
}

function AppCard({ a, delay }: { a: Application; delay: number }) {
  return (
    <Link href={`/applications/${a.id}`} className="block animate-rise" style={{ animationDelay: `${delay}ms` }}>
      <div className="lift rounded-2xl border bg-card-solid p-4 shadow-[var(--shadow-card)]">
        <div className="flex items-start gap-3">
          <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-muted text-muted-foreground">
            <Building2 className="size-4" />
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold">{a.role}</p>
            <p className="truncate text-xs text-muted-foreground">{a.company}</p>
          </div>
          {a.match_score != null && <span className="rounded-lg bg-success/15 px-1.5 py-0.5 text-xs font-semibold text-success">{a.match_score}%</span>}
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-1.5">
          <Badge variant={statusTone(a.status)}>{humanStatus(a.status)}</Badge>
          <span className="ml-auto text-[11px] text-muted-foreground">
            {a.applied_at ? `Applied ${formatDate(a.applied_at)}` : `Updated ${formatDate(a.updated_at)}`}
          </span>
        </div>
      </div>
    </Link>
  );
}

const READY: ApplicationStatus[] = ["SHORTLISTED", "READY_TO_APPLY", "APPROVAL_REQUIRED", "APPLICATION_FAILED"];
type BulkResult = { id: string; company: string; role: string; status: "sent" | "open" | "error"; message: string; url?: string };

/** Approve many prepared applications at once (the auto-applier's queue). */
function ApprovalQueue({ apps, onDone }: { apps: Application[]; onDone: () => void }) {
  const ready = apps.filter((a) => READY.includes(a.status));
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [results, setResults] = useState<BulkResult[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  if (!ready.length && !results) return null;
  const all = ready.length > 0 && ready.every((a) => picked.has(a.id));

  async function approve() {
    setBusy(true);
    setErr(null);
    try {
      const r = await request<{ results: BulkResult[] }>("/applications/approve-bulk", { method: "POST", body: { ids: [...picked] } });
      setResults(r.results);
      setPicked(new Set());
      onDone();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Approval failed");
    } finally {
      setBusy(false);
    }
  }

  async function submitted(id: string) {
    await request(`/applications/${id}/mark-applied`, { method: "POST" });
    setResults((r) => r?.map((x) => (x.id === id ? { ...x, status: "sent", message: "Marked as applied" } : x)) ?? null);
    onDone();
  }

  return (
    <Card className="animate-rise mb-6" style={{ borderColor: "color-mix(in srgb, var(--tone-purple) 30%, transparent)" }}>
      <CardHeader className="gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <CardTitle className="flex items-center gap-2 text-lg">
            <span className="grid size-8 place-items-center rounded-lg text-[#0b0b0c]" style={{ background: "var(--tone-purple)" }}><Bot className="size-4" /></span>
            Ready to approve <span className="text-muted-foreground">· {ready.length}</span>
          </CardTitle>
          <CardDescription className="mt-1 max-w-3xl">
            Prepared by you or the auto-applier, with your best resume attached. Approving sends email applications from your Gmail (when the posting asks for CVs by email) and opens the employer&apos;s page for the rest.
          </CardDescription>
        </div>
        <div className="flex items-center gap-2">
          <button type="button" className="inline-flex items-center gap-1.5 whitespace-nowrap text-sm font-medium" onClick={() => setPicked(all ? new Set() : new Set(ready.map((a) => a.id)))}>
            {all ? <CheckSquare className="size-4" style={{ color: "var(--tone-purple)" }} /> : <Square className="size-4" />} Select all
          </button>
          <Button size="sm" disabled={!picked.size || busy} onClick={approve}>{busy ? <Loader2 className="animate-spin" /> : <Send />} Approve &amp; apply ({picked.size})</Button>
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
        {err && <Notice tone="error">{err}</Notice>}
        {results && (
          <ul className="mb-2 flex flex-col gap-1.5 rounded-2xl border p-3 text-sm">
            {results.map((r) => (
              <li key={r.id} className="flex flex-wrap items-center gap-2">
                <span className="size-2 rounded-full" style={{ background: `var(--tone-${r.status === "sent" ? "green" : r.status === "open" ? "yellow" : "red"})` }} />
                <b>{r.role}</b> · {r.company} <span className="text-muted-foreground">— {r.message}</span>
                {r.status === "open" && r.url && (
                  <span className="ml-auto flex gap-1.5">
                    <a href={r.url} target="_blank" rel="noopener noreferrer" className={buttonVariants({ size: "sm", variant: "outline" })}><ExternalLink /> Open</a>
                    <Button size="sm" variant="ghost" onClick={() => submitted(r.id)}>I&apos;ve submitted</Button>
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}
        <ul className="grid gap-2 md:grid-cols-2">
          {ready.map((a) => (
            <li key={a.id}>
              <label className="flex cursor-pointer items-center gap-3 rounded-2xl border p-3 hover:bg-muted/40">
                <input type="checkbox" className="size-4 accent-[var(--tone-purple)]" checked={picked.has(a.id)}
                  onChange={() => setPicked((p) => { const n = new Set(p); if (n.has(a.id)) n.delete(a.id); else n.add(a.id); return n; })} />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium">{a.role}</span>
                  <span className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
                    {a.company}
                    {a.auto && <span className="rounded-full border px-1.5">auto</span>}
                    {a.apply_email && <span className="inline-flex items-center gap-0.5" style={{ color: "var(--tone-teal)" }}><Mail className="size-3" /> email apply</span>}
                    {a.walk_in && <span className="inline-flex items-center gap-0.5" style={{ color: "var(--tone-yellow)" }}><CalendarClock className="size-3" /> walk-in {a.walk_in.date ?? ""}</span>}
                    {!a.resume_id && <span className="text-destructive">no resume yet</span>}
                  </span>
                </span>
                {a.match_score != null && <span className="rounded-lg bg-success/15 px-1.5 py-0.5 text-xs font-semibold text-success">{a.match_score}%</span>}
                <Link href={`/applications/${a.id}`} className="text-xs underline" onClick={(e) => e.stopPropagation()}>Review</Link>
              </label>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

export default function ApplicationsPage() {
  const { data, error, loading, reload } = useApi<Application[]>("/applications");
  const closed = (data ?? []).filter((a) => CLOSED.includes(a.status));

  return (
    <>
      <PageHeader
        title="Applications"
        description="Every application from preparation to offer. Approve prepared applications in bulk: email applications go from your Gmail, the rest open on the employer's site."
        actions={<Link href="/jobs" className={buttonVariants({ variant: "gradient", className: "animate-gradient" })}><Send /> Prepare from a job</Link>}
      />
      {error && <Notice tone="error">{error}</Notice>}
      {loading && !data && <div className="grid gap-4 md:grid-cols-5">{COLUMNS.map((c) => <div key={c.title} className="skeleton h-64 rounded-2xl" />)}</div>}
      {data && data.length === 0 && (
        <Card className="flex flex-col items-center gap-3 py-14 text-center">
          <Send className="size-8 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">No applications yet. In Jobs → Jobs for you, select jobs and click Auto-apply, or turn on the auto-applier.</p>
          <Link href="/jobs" className={buttonVariants({ size: "sm" })}>Go to Jobs</Link>
        </Card>
      )}
      {data && data.length > 0 && (
        <>
          <ApprovalQueue apps={data} onDone={() => void reload()} />
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
            {COLUMNS.map((col, ci) => {
              const items = data.filter((a) => col.statuses.includes(a.status));
              return (
                <section key={col.title} className="animate-rise flex flex-col gap-3 rounded-3xl border bg-muted/40 p-3" style={{ animationDelay: `${ci * 60}ms` }}>
                  <header className="flex items-center gap-2 px-1">
                    <span className="size-2.5 rounded-full" style={{ background: `var(--ord-${col.ord})` }} aria-hidden />
                    <h2 className="text-sm font-semibold">{col.title}</h2>
                    <span className="ml-auto rounded-full bg-card-solid px-2 text-xs font-medium text-muted-foreground"><CountUp value={items.length} /></span>
                  </header>
                  {items.length === 0 ? (
                    <p className="px-1 py-6 text-center text-xs text-muted-foreground">Nothing here</p>
                  ) : (
                    items.map((a, i) => <AppCard key={a.id} a={a} delay={ci * 60 + i * 40} />)
                  )}
                </section>
              );
            })}
          </div>
          {closed.length > 0 && (
            <div className="mt-8">
              <h2 className="mb-3 text-sm font-semibold text-muted-foreground">Closed ({closed.length})</h2>
              <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-4">
                {closed.map((a, i) => <AppCard key={a.id} a={a} delay={i * 30} />)}
              </div>
            </div>
          )}
        </>
      )}
    </>
  );
}
