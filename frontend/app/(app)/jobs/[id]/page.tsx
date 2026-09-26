"use client";

import { Archive, ArrowLeft, Bookmark, ExternalLink, ListChecks, RefreshCw, Send, Trash2, X } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";

import { Notice, PageHeader } from "@/components/app-shell";
import { JobDocuments } from "@/components/job-documents";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useApi } from "@/hooks/use-api";
import { ApiError, request } from "@/services/api";
import type { JobDetail, JobStatus } from "@/types/api";
import { cn } from "@/utils/cn";
import { UNKNOWN, formatDate, formatSalary, scoreTone } from "@/utils/format";

const DIMENSIONS: [string, string][] = [
  ["skills", "Skills"],
  ["experience", "Experience"],
  ["role", "Role"],
  ["domain", "Domain"],
  ["location", "Location"],
  ["salary", "Salary"],
  ["notice_period", "Notice period"],
  ["education", "Education"],
  ["work_authorization", "Work authorization"],
];

function ScoreBar({ label, value, weight }: { label: string; value: number | null; weight?: number }) {
  return (
    <div className="grid grid-cols-[120px_1fr_48px] items-center gap-3 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <div className="h-2 overflow-hidden rounded-full bg-muted">
        {value != null && (
          <div className={cn("h-full rounded-full", value >= 85 ? "bg-success" : value >= 55 ? "bg-primary" : "bg-warning")} style={{ width: `${value}%` }} />
        )}
      </div>
      <span className="text-right tabular-nums" title={weight != null ? `weight ${(weight * 100).toFixed(0)}%` : "not scored"}>
        {value == null ? <span className="text-xs text-muted-foreground">{UNKNOWN}</span> : `${Math.round(value)}%`}
      </span>
    </div>
  );
}

function Chips({ items, variant }: { items: string[]; variant: "success" | "destructive" | "warning" | "muted" }) {
  if (!items.length) return <p className="text-sm text-muted-foreground">None</p>;
  return (
    <div className="flex flex-wrap gap-1">
      {items.map((s) => (
        <Badge key={s} variant={variant}>{s}</Badge>
      ))}
    </div>
  );
}

export default function JobDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { data: job, error, reload, setData } = useApi<JobDetail>(`/jobs/${id}`);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  if (error) return <Notice tone="error">{error}</Notice>;
  if (!job) return <p className="text-sm text-muted-foreground">Loading…</p>;
  const m = job.match;
  const a = job.analysis;

  async function act(fn: () => Promise<unknown>) {
    setBusy(true);
    setMsg(null);
    try {
      await fn();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Action failed");
    } finally {
      setBusy(false);
    }
  }

  const setStatus = (status: JobStatus) =>
    act(async () => {
      await request(`/jobs/${id}/status`, { method: "POST", body: { status } });
      setData({ ...job, status });
    });

  return (
    <>
      <Link href="/jobs" className="mb-3 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-4" /> All jobs
      </Link>
      <PageHeader
        title={job.title}
        description={[job.company, job.location, job.remote ? "Remote" : null, job.employment_type].filter(Boolean).join(" · ")}
        actions={
          <>
            {job.application_url && (
              <a href={job.application_url} target="_blank" rel="noopener noreferrer" className={buttonVariants({ variant: "outline", size: "sm" })}>
                <ExternalLink /> Open posting
              </a>
            )}
            <Button
              size="sm"
              variant="gradient"
              className="animate-gradient"
              disabled={busy}
              onClick={() => act(async () => {
                try {
                  const a = await request<{ id: string }>("/applications", { method: "POST", body: { job_id: id } });
                  router.push(`/applications/${a.id}`);
                } catch (e) {
                  const existing = e instanceof ApiError && e.status === 409 && e.detail && typeof e.detail === "object" ? (e.detail as { id?: string }).id : undefined;
                  if (existing) router.push(`/applications/${existing}`);
                  else throw e;
                }
              })}
            >
              <Send /> Prepare application
            </Button>
            <Button size="sm" variant={job.status === "saved" ? "default" : "outline"} disabled={busy} onClick={() => setStatus("saved")}>
              <Bookmark /> Save
            </Button>
            <Button size="sm" variant={job.status === "shortlisted" ? "default" : "outline"} disabled={busy} onClick={() => setStatus("shortlisted")}>
              <ListChecks /> Shortlist
            </Button>
            <Button size="sm" variant="outline" disabled={busy} onClick={() => setStatus("archived")}>
              <Archive /> Archive
            </Button>
            <Button size="sm" variant="outline" disabled={busy} onClick={() => setStatus("rejected")}>
              <X /> Not for me
            </Button>
            <Button size="sm" variant="ghost" disabled={busy} aria-label="Re-score" onClick={() => act(async () => { await request(`/jobs/${id}/match`, { method: "POST" }); await reload(); })}>
              <RefreshCw />
            </Button>
            <Button
              size="sm"
              variant="ghost"
              aria-label="Delete job"
              disabled={busy}
              onClick={() => {
                if (confirm("Delete this job?")) void act(async () => { await request(`/jobs/${id}`, { method: "DELETE" }); router.replace("/jobs"); });
              }}
            >
              <Trash2 />
            </Button>
          </>
        }
      />
      {msg && <div className="mb-4"><Notice tone="error">{msg}</Notice></div>}

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="flex flex-col gap-6 lg:col-span-2">
          <Card>
            <CardHeader className="flex-row items-center gap-4">
              <div className={cn("grid size-16 place-items-center rounded-xl text-xl font-semibold tabular-nums",
                m && m.overall >= 85 ? "bg-success/15 text-success" : "bg-accent text-accent-foreground")}>
                {m ? `${m.overall}%` : "—"}
              </div>
              <div>
                <CardTitle className="text-base">Overall match</CardTitle>
                {m && <Badge variant={scoreTone(m.overall)} className="mt-1">{m.classification}</Badge>}
                <CardDescription className="mt-1">Dimensions marked UNKNOWN lack information and are left out of the score.</CardDescription>
              </div>
            </CardHeader>
            {m && (
              <CardContent className="flex flex-col gap-2.5">
                {DIMENSIONS.map(([k, label]) => (
                  <ScoreBar key={k} label={label} value={m.breakdown[k] ?? null} weight={m.weights[k]} />
                ))}
              </CardContent>
            )}
          </Card>

          {m && (
            <Card>
              <CardHeader><CardTitle>Skills</CardTitle></CardHeader>
              <CardContent className="flex flex-col gap-4">
                <div><p className="mb-1.5 text-xs font-medium text-muted-foreground">You have</p><Chips items={m.matched_skills} variant="success" /></div>
                <div><p className="mb-1.5 text-xs font-medium text-muted-foreground">Missing — required</p><Chips items={m.missing_required_skills} variant="destructive" /></div>
                <div><p className="mb-1.5 text-xs font-medium text-muted-foreground">Missing — nice to have</p><Chips items={m.missing_preferred_skills} variant="warning" /></div>
                <p className="text-xs text-muted-foreground">
                  Only add a missing skill to your profile if you genuinely have it — Saige never claims skills on your behalf.
                </p>
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader><CardTitle>Job description</CardTitle></CardHeader>
            <CardContent>
              <div className="max-h-[32rem] overflow-y-auto whitespace-pre-wrap text-sm leading-relaxed">{job.description}</div>
            </CardContent>
          </Card>
        </div>

        <div className="flex flex-col gap-6">
          <JobDocuments jobId={id} />
          {m && m.issues.length > 0 && (
            <Card>
              <CardHeader><CardTitle>Things to note</CardTitle></CardHeader>
              <CardContent>
                <ul className="flex list-disc flex-col gap-1.5 pl-4 text-sm">
                  {m.issues.map((i) => <li key={i}>{i}</li>)}
                </ul>
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader><CardTitle>Details</CardTitle></CardHeader>
            <CardContent>
              <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
                <dt className="text-muted-foreground">Salary</dt><dd>{formatSalary(job.salary_min, job.salary_max, job.currency)}</dd>
                <dt className="text-muted-foreground">Experience</dt><dd>{job.experience_required ?? UNKNOWN}</dd>
                <dt className="text-muted-foreground">Seniority</dt><dd>{a.seniority ?? UNKNOWN}</dd>
                <dt className="text-muted-foreground">Domains</dt><dd>{a.domains.join(", ") || UNKNOWN}</dd>
                <dt className="text-muted-foreground">Country</dt><dd>{job.country ?? UNKNOWN}</dd>
                <dt className="text-muted-foreground">Posted</dt><dd>{job.posted_date ?? UNKNOWN}</dd>
                <dt className="text-muted-foreground">Status</dt><dd className="capitalize">{job.status}</dd>
                <dt className="text-muted-foreground">Analysis</dt><dd>{a.extraction}</dd>
              </dl>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>Recommended resume</CardTitle></CardHeader>
            <CardContent className="text-sm">
              {job.recommended_resume ? (
                <p>
                  <Link href={`/resumes/${job.recommended_resume.id}`} className="font-medium text-primary hover:underline">{job.recommended_resume.name}</Link>{" "}
                  <span className="text-muted-foreground">— covers {job.recommended_resume.overlap} of {job.recommended_resume.of} skills in this JD</span>
                </p>
              ) : (
                <p className="text-muted-foreground">Upload a resume to get a recommendation.</p>
              )}
              
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>Sources</CardTitle></CardHeader>
            <CardContent>
              <ul className="flex flex-col gap-1.5 text-sm">
                {job.source_refs.map((s, i) => (
                  <li key={i} className="flex items-center gap-2">
                    <Badge variant="muted" className="capitalize">{s.source}</Badge>
                    {s.url ? <a href={s.url} target="_blank" rel="noopener noreferrer" className="truncate text-primary hover:underline">{new URL(s.url).hostname}</a> : <span className="text-muted-foreground">pasted</span>}
                    <span className="ml-auto text-xs text-muted-foreground">{formatDate(s.first_seen)}</span>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        </div>
      </div>
    </>
  );
}
