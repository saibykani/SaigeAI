"use client";

import { CheckCircle2, CircleHelp, MinusCircle, ScanText, Sparkles, XCircle } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Notice, PageHeader } from "@/components/app-shell";
import { ProgressRing } from "@/components/motion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input, Textarea } from "@/components/ui/form";
import { request } from "@/services/api";
import type { EligibilityStatus, JDAnalysisReport } from "@/types/api";

const PREFILL_KEY = "saige:studio-prefill";
const VERDICT_TONE = { eligible: "green", partial: "yellow", not_yet: "red" } as const;

function StatusIcon({ s }: { s: EligibilityStatus }) {
  if (s === "met") return <CheckCircle2 className="size-4 shrink-0 text-[var(--tone-green)]" aria-label="Met" />;
  if (s === "not_met") return <XCircle className="size-4 shrink-0 text-[var(--tone-red)]" aria-label="Not met" />;
  if (s === "partial") return <MinusCircle className="size-4 shrink-0 text-[var(--tone-yellow)]" aria-label="Partly met" />;
  return <CircleHelp className="size-4 shrink-0 text-muted-foreground" aria-label="Unknown" />;
}

export default function AnalyzePage() {
  const router = useRouter();
  const [company, setCompany] = useState("");
  const [title, setTitle] = useState("");
  const [jd, setJd] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [a, setA] = useState<JDAnalysisReport | null>(null);

  async function run() {
    setBusy(true);
    setErr(null);
    try {
      setA(await request<JDAnalysisReport>("/studio/analyze", { method: "POST", body: { jd_text: jd, title, company } }));
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Couldn't analyse this job description.");
    } finally {
      setBusy(false);
    }
  }

  function buildResume() {
    try {
      sessionStorage.setItem(PREFILL_KEY, JSON.stringify({ jd, title: a?.title ?? title, company }));
    } catch {
      /* storage blocked: the builder starts empty */
    }
    router.push("/studio");
  }

  const tone = a ? VERDICT_TONE[a.verdict.key] : "green";
  return (
    <div className="space-y-6">
      <PageHeader title="JD analyzer"
        description="Paste any job description. Saige reads it and explains what the job needs, what you have and don't have in your verified profile, whether you're eligible, and where you fit most." />
      {err && <Notice tone="error">{err}</Notice>}
      <Card>
        <CardContent className="grid gap-4 pt-5 lg:grid-cols-2">
          <Field label="Company"><Input value={company} onChange={(e) => setCompany(e.target.value)} placeholder="Optional" /></Field>
          <Field label="Job title"><Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Optional: read from the JD if empty" /></Field>
          <Field label="Job description" className="lg:col-span-2">
            <Textarea rows={10} value={jd} onChange={(e) => setJd(e.target.value)} placeholder="Paste the full job description here" />
          </Field>
          <div className="flex justify-end lg:col-span-2">
            <Button onClick={() => void run()} disabled={busy || jd.trim().length < 30}><ScanText /> {busy ? "Analysing…" : "Analyse"}</Button>
          </div>
        </CardContent>
      </Card>

      {a && (
        <>
          <Card>
            <CardContent className="flex flex-wrap items-center gap-6 pt-5">
              <ProgressRing value={a.score} trackClass="stroke-muted" barClass={`stroke-[var(--tone-${tone})]`}>
                <span className="text-2xl font-semibold">{a.score}</span>
              </ProgressRing>
              <div className="min-w-0 flex-1">
                <p className="text-lg font-semibold" style={{ color: `var(--tone-${tone})` }}>{a.verdict.label}</p>
                <p className="mt-1 text-sm">{a.summary}</p>
                <div className="mt-2 flex flex-wrap gap-1.5 text-xs">
                  {[a.role.seniority, a.role.employment_type, a.role.work_mode, a.role.salary, ...a.role.domains].filter(Boolean).map((x) => <Badge key={x!} variant="outline">{x}</Badge>)}
                </div>
              </div>
              <Button onClick={buildResume}><Sparkles /> Build an ATS resume for this job</Button>
            </CardContent>
          </Card>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader><CardTitle>Eligibility</CardTitle></CardHeader>
              <CardContent>
                <ul className="space-y-3">
                  {a.eligibility.map((c) => (
                    <li key={c.label} className="flex gap-3 text-sm"><StatusIcon s={c.status} /><div><p className="font-medium">{c.label}</p><p className="text-muted-foreground">{c.text}</p></div></li>
                  ))}
                </ul>
              </CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle>Skills: what you have and don&apos;t</CardTitle></CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <p className="text-xs font-medium text-muted-foreground">Required{a.skills.required_coverage != null ? ` · you have ${a.skills.required_coverage}%` : ""}</p>
                  <div className="mt-1.5 flex flex-wrap gap-1.5">
                    {a.skills.required.map((s) => <Badge key={s.name} variant={s.have ? "success" : "outline"}>{s.have ? "✓ " : "✗ "}{s.name}</Badge>)}
                    {!a.skills.required.length && <span className="text-sm text-muted-foreground">No specific skills listed.</span>}
                  </div>
                </div>
                {a.skills.preferred.length > 0 && (
                  <div>
                    <p className="text-xs font-medium text-muted-foreground">Nice to have</p>
                    <div className="mt-1.5 flex flex-wrap gap-1.5">{a.skills.preferred.map((s) => <Badge key={s.name} variant={s.have ? "success" : "outline"}>{s.have ? "✓ " : "✗ "}{s.name}</Badge>)}</div>
                  </div>
                )}
              </CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle>Where you fit most</CardTitle></CardHeader>
              <CardContent>{a.strengths.length ? <ul className="list-disc space-y-1.5 pl-5 text-sm">{a.strengths.map((s) => <li key={s}>{s}</li>)}</ul>
                : <p className="text-sm text-muted-foreground">Nothing in your verified profile lines up yet.</p>}</CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle>Gaps and what to do</CardTitle></CardHeader>
              <CardContent>{a.gaps.length ? <ul className="list-disc space-y-1.5 pl-5 text-sm">{a.gaps.map((s) => <li key={s}>{s}</li>)}</ul>
                : <p className="text-sm text-muted-foreground">No gaps found against your profile.</p>}</CardContent>
            </Card>
          </div>

          {a.requirements.length > 0 && (
            <Card>
              <CardHeader><CardTitle>Every requirement, checked</CardTitle></CardHeader>
              <CardContent>
                <ul className="divide-y">
                  {a.requirements.map((r) => (
                    <li key={r.text} className="flex gap-3 py-2.5 text-sm">
                      <StatusIcon s={r.status} />
                      <div><p>{r.text}{r.nice_to_have && <span className="ml-2 text-xs text-muted-foreground">nice to have</span>}</p><p className="text-xs text-muted-foreground">{r.why}</p></div>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}
          {a.responsibilities.length > 0 && (
            <Card>
              <CardHeader><CardTitle>What you&apos;d do in this job</CardTitle></CardHeader>
              <CardContent><ul className="list-disc space-y-1.5 pl-5 text-sm">{a.responsibilities.map((s) => <li key={s}>{s}</li>)}</ul></CardContent>
            </Card>
          )}
          {a.keywords_to_use.length > 0 && (
            <Card>
              <CardHeader><CardTitle>Keywords to use in your resume and interview</CardTitle></CardHeader>
              <CardContent className="flex flex-wrap gap-1.5">{a.keywords_to_use.map((k) => <Badge key={k} variant="success">{k}</Badge>)}</CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
