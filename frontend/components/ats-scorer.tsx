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
  const rid = resumeId || resumes[0]?.id || "";

  async function score(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
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
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
