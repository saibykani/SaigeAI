"use client";

import { Check, Gauge, Loader2, X } from "lucide-react";
import { useState } from "react";

import { Notice } from "@/components/app-shell";
import { ProgressRing } from "@/components/motion";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input, Select, Textarea } from "@/components/ui/form";
import { useApi } from "@/hooks/use-api";
import { request } from "@/services/api";
import type { AtsScore, JobSummary, Resume } from "@/types/api";

/** ATS resume scorer: any resume against a saved job or a pasted job description. */
export function AtsScorer({ resumes }: { resumes: Resume[] }) {
  const jobs = useApi<{ items: JobSummary[] }>("/jobs?sort=recent&limit=50");
  const [resumeId, setResumeId] = useState("");
  const [jobId, setJobId] = useState("");
  const [title, setTitle] = useState("");
  const [jd, setJd] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [out, setOut] = useState<AtsScore | null>(null);
  const [fixing, setFixing] = useState(false);
  const [fixed, setFixed] = useState<{ resume_id: string; name: string; before: AtsScore; after: AtsScore; changes: string[]; gaps: string[]; note: string } | null>(null);

  async function optimise() {
    setFixing(true);
    setErr(null);
    try {
      const r = await request<NonNullable<typeof fixed>>("/resumes/ats-optimize", { method: "POST", body: { resume_id: rid, job_id: jobId || null, jd_text: jobId ? null : jd, title: title || null } });
      setFixed(r);
      setOut({ ...r.after, job: out?.job ?? "", resume: r.name, tips: r.gaps.map((g) => `Add “${g}” to your Profile only if you've used it, then optimise again.`) });
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : "Could not optimise");
    } finally {
      setFixing(false);
    }
  }
  const rid = resumeId || resumes[0]?.id || "";

  async function score(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    setFixed(null);
    try {
      setOut(await request<AtsScore>("/resumes/ats-score", { method: "POST", body: { resume_id: rid, job_id: jobId || null, jd_text: jobId ? null : jd, title: title || null } }));
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : "Scoring failed");
    } finally {
      setBusy(false);
    }
  }

  const tone = !out ? "purple" : out.score >= 80 ? "green" : out.score >= 60 ? "yellow" : "red";
  return (
    <Card id="ats" className="animate-rise mb-6 scroll-mt-24" style={{ borderColor: "color-mix(in srgb, var(--tone-purple) 30%, transparent)" }}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <span className="grid size-8 place-items-center rounded-lg text-[#0b0b0c]" style={{ background: "var(--tone-purple)" }}><Gauge className="size-4" /></span>
          ATS resume scorer
        </CardTitle>
        <CardDescription>See how an applicant tracking system reads your resume for a job: keyword coverage, format checks and exactly what to fix.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-6 lg:grid-cols-[1fr_1.1fr]">
        <form onSubmit={score} className="flex flex-col gap-3">
          <Field label="Resume">
            <Select value={rid} onChange={(e) => setResumeId(e.target.value)} required>
              {resumes.length === 0 && <option value="">Upload a resume first</option>}
              {resumes.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
            </Select>
          </Field>
          <Field label="Job">
            <Select value={jobId} onChange={(e) => setJobId(e.target.value)}>
              <option value="">Paste a job description</option>
              {(jobs.data?.items ?? []).map((j) => <option key={j.id} value={j.id}>{j.title} · {j.company}</option>)}
            </Select>
          </Field>
          {!jobId && (
            <>
              <Field label="Job title"><Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. SDET" /></Field>
              <Field label="Job description"><Textarea rows={7} minLength={30} required value={jd} onChange={(e) => setJd(e.target.value)} placeholder="Paste the full job description" /></Field>
            </>
          )}
          <Button type="submit" className="w-fit" disabled={busy || !rid}>{busy ? <Loader2 className="animate-spin" /> : <Gauge />} Score my resume</Button>
          {err && <Notice tone="error">{err}</Notice>}
        </form>
        <div className="rounded-2xl border bg-muted/30 p-4">
          {!out ? (
            <p className="py-16 text-center text-sm text-muted-foreground">Your score, missing keywords and fixes appear here.</p>
          ) : (
            <div className="flex flex-col gap-4">
              <div className="flex items-center gap-4">
                <span style={{ color: `var(--tone-${tone})` }}>
                  <ProgressRing value={out.score} size={84} stroke={8} trackClass="stroke-muted" barClass="stroke-current">
                    <span className="text-xl font-semibold text-foreground">{out.score}</span>
                  </ProgressRing>
                </span>
                <div className="text-sm">
                  <p className="font-semibold">{out.resume}</p>
                  <p className="text-muted-foreground">vs {out.job}</p>
                  <p className="mt-1 text-xs text-muted-foreground">Required keywords {out.required_coverage}% · Nice-to-have {out.preferred_coverage}% · {out.word_count} words</p>
                </div>
              </div>
              {out.matched_keywords.length > 0 && <p className="text-xs" style={{ color: "var(--tone-green)" }}>✓ {out.matched_keywords.join(" · ")}</p>}
              {out.missing_required.length > 0 && <p className="text-xs" style={{ color: "var(--tone-red)" }}>Missing: {out.missing_required.join(" · ")}</p>}
              <ul className="grid gap-1 text-xs sm:grid-cols-2">
                {out.checks.map((c) => (
                  <li key={c.check} className="flex items-center gap-1.5">
                    {c.passed ? <Check className="size-3.5" style={{ color: "var(--tone-green)" }} /> : <X className="size-3.5" style={{ color: "var(--tone-red)" }} />} {c.check}
                  </li>
                ))}
              </ul>
              {out.tips.length > 0 && (
                <div>
                  <p className="mb-1 text-sm font-medium">What to fix</p>
                  <ul className="list-disc space-y-0.5 pl-5 text-sm text-muted-foreground">{out.tips.map((t) => <li key={t}>{t}</li>)}</ul>
                </div>
              )}
              {!fixed && out.score < 100 && (
                <Button className="w-fit" disabled={fixing} onClick={optimise}>
                  {fixing ? <Loader2 className="animate-spin" /> : <Gauge />} {fixing ? "Optimising…" : "Optimise my resume for this job"}
                </Button>
              )}
              {fixed && (
                <div className="rounded-2xl border p-3 text-sm" style={{ borderColor: "color-mix(in srgb, var(--tone-green) 35%, transparent)" }}>
                  <p className="font-semibold">
                    ATS score <span style={{ color: "var(--tone-red)" }}>{fixed.before.score}</span> → <span style={{ color: "var(--tone-green)" }}>{fixed.after.score}</span>
                    <span className="ml-2 font-normal text-muted-foreground">saved as “{fixed.name}”</span>
                  </p>
                  <ul className="mt-2 list-disc space-y-0.5 pl-5 text-muted-foreground">{fixed.changes.map((c) => <li key={c}>{c}</li>)}</ul>
                  <p className="mt-2 text-xs text-muted-foreground">{fixed.note}</p>
                  <a href={`/resumes/${fixed.resume_id}`} className="mt-2 inline-block text-xs font-medium underline">Open the optimised resume</a>
                </div>
              )}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

type Health = { score: number; label: string; resume: string; bullets: number; quantified: number; words: number;
  sections: { area: string; ok: boolean; tip: string }[] };

/** Resume health report: how a recruiter and an ATS see this resume, without any job. */
export function ResumeHealth({ resumes }: { resumes: Resume[] }) {
  const [rid, setRid] = useState("");
  const id = rid || resumes[0]?.id || "";
  const { data, loading } = useApi<Health>(id ? `/resumes/${id}/health` : null);
  const tone = !data ? "purple" : data.score >= 80 ? "green" : data.score >= 55 ? "yellow" : "red";
  return (
    <Card id="health" className="animate-rise mb-6 scroll-mt-24" style={{ borderColor: `color-mix(in srgb, var(--tone-${tone}) 32%, transparent)` }}>
      <CardHeader className="gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <CardTitle className="flex items-center gap-2 text-lg">
            <span className="grid size-8 place-items-center rounded-lg text-[#0b0b0c]" style={{ background: `var(--tone-${tone})` }}><Check className="size-4" /></span>
            Resume health
          </CardTitle>
          <CardDescription>Impact, repetition, bullet length, contact details and structure. No job needed.</CardDescription>
        </div>
        <Select className="w-64" value={id} onChange={(e) => setRid(e.target.value)} aria-label="Resume">
          {resumes.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
        </Select>
      </CardHeader>
      <CardContent>
        {loading && !data ? <div className="skeleton h-40 rounded-2xl" /> : data && (
          <div className="grid gap-5 md:grid-cols-[auto_1fr]">
            <div className="flex flex-col items-center gap-2">
              <span style={{ color: `var(--tone-${tone})` }}>
                <ProgressRing value={data.score} size={96} stroke={9} trackClass="stroke-muted" barClass="stroke-current">
                  <span className="text-2xl font-semibold text-foreground">{data.score}</span>
                </ProgressRing>
              </span>
              <span className="text-sm font-medium" style={{ color: `var(--tone-${tone})` }}>{data.label}</span>
              <span className="text-xs text-muted-foreground">{data.quantified}/{data.bullets} bullets with numbers · {data.words} words</span>
            </div>
            <ul className="grid gap-2 sm:grid-cols-2">
              {data.sections.map((s) => (
                <li key={s.area} className="flex items-start gap-2 rounded-xl border p-2.5 text-sm" style={{ borderColor: `color-mix(in srgb, var(--tone-${s.ok ? "green" : "red"}) 30%, transparent)` }}>
                  {s.ok ? <Check className="mt-0.5 size-4 shrink-0" style={{ color: "var(--tone-green)" }} /> : <X className="mt-0.5 size-4 shrink-0" style={{ color: "var(--tone-red)" }} />}
                  <span><span className="block font-medium">{s.area}</span><span className="text-xs text-muted-foreground">{s.tip}</span></span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
