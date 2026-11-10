"use client";

import { CheckCircle2, Download, FileText, Sparkles, XCircle } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";

import { Notice, PageHeader } from "@/components/app-shell";
import { Loader3D } from "@/components/loader3d";
import { ProgressRing } from "@/components/motion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input, Textarea } from "@/components/ui/form";
import { useApi } from "@/hooks/use-api";
import { downloadFile, request } from "@/services/api";
import type { StudioGenerated, StudioResumeRow, StudioTemplates } from "@/types/api";
import { cn } from "@/utils/cn";
import { timeAgo } from "@/utils/format";

const PREFILL_KEY = "saige:studio-prefill";
type Msg = { tone: "success" | "error" | "warning" | "info"; text: string } | null;

function localDate() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function scoreTone(s: number) {
  return s >= 90 ? "stroke-[var(--tone-green)]" : s >= 70 ? "stroke-[var(--tone-yellow)]" : "stroke-[var(--tone-orange)]";
}

function Builder() {
  const params = useSearchParams();
  const tpl = useApi<StudioTemplates>("/studio/templates");
  const history = useApi<StudioResumeRow[]>("/studio/resumes");
  const [company, setCompany] = useState("");
  const [title, setTitle] = useState("");
  const [jd, setJd] = useState("");
  const [careerJob, setCareerJob] = useState<string | null>(null);
  const [template, setTemplate] = useState("modern");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<Msg>(null);
  const [result, setResult] = useState<StudioGenerated | null>(null);
  const [preview, setPreview] = useState<string>("");
  const started = useRef(false);

  async function generate(over?: { career_job_id?: string; jd_text?: string; title?: string; company?: string }) {
    setBusy(true);
    setMsg(null);
    try {
      const body = { jd_text: over?.jd_text ?? (careerJob ? null : jd), title: over?.title ?? title, company: over?.company ?? company,
        career_job_id: over?.career_job_id ?? careerJob, template };
      const r = await request<StudioGenerated>("/studio/resume", { method: "POST", body });
      setResult(r);
      setPreview(r.html);
      setTitle(r.title);
      setCompany(r.company);
      await history.reload();
    } catch (e) {
      setMsg({ tone: "error", text: e instanceof Error ? e.message : "Couldn't generate the resume." });
    } finally {
      setBusy(false);
    }
  }

  // Arrive from Career portals (?career_job=…) or from the JD analyzer (prefill in session storage).
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    const cj = params.get("career_job");
    if (cj) {
      setCareerJob(cj);
      setTitle(params.get("title") ?? "");
      setCompany(params.get("company") ?? "");
      void generate({ career_job_id: cj, title: params.get("title") ?? "", company: params.get("company") ?? "" });
      return;
    }
    try {
      const raw = sessionStorage.getItem(PREFILL_KEY);
      if (raw) {
        sessionStorage.removeItem(PREFILL_KEY);
        const p = JSON.parse(raw) as { jd: string; title: string; company: string };
        setJd(p.jd);
        setTitle(p.title);
        setCompany(p.company);
      }
    } catch {
      /* storage blocked: start empty */
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function switchTemplate(id: string) {
    setTemplate(id);
    if (!result) return;
    try {
      const r = await request<{ html: string }>(`/studio/resumes/${result.id}?template=${id}`);
      setPreview(r.html);
    } catch {
      /* keep the current preview */
    }
  }

  async function open(id: string) {
    try {
      const r = await request<StudioGenerated & { resume: unknown }>(`/studio/resumes/${id}`);
      setResult({ ...r, changes: [], improve: [], verdict: { key: "", label: "" }, engine: "" });
      setPreview(r.html);
      setTemplate(r.template || "modern");
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (e) {
      setMsg({ tone: "error", text: e instanceof Error ? e.message : "Couldn't open it." });
    }
  }

  async function download(fmt: string) {
    if (!result) return;
    try {
      await downloadFile(`/studio/resumes/${result.id}/download?format=${fmt}&template=${template}&on=${localDate()}`, `resume.${fmt}`);
    } catch (e) {
      setMsg({ tone: "error", text: e instanceof Error ? e.message : "Download failed." });
    }
  }

  const ats = result?.ats;
  return (
    <div className="space-y-6">
      <PageHeader title="ATS resume builder"
        description="Paste a job description and the company. Saige builds a resume aimed at that job from your verified profile only, scores it the way an applicant tracking system does, and lets you download it in several templates and formats." />
      {msg && <Notice tone={msg.tone}>{msg.text}</Notice>}

      <Card>
        <CardContent className="grid gap-4 pt-5 lg:grid-cols-2">
          <Field label="Company"><Input value={company} onChange={(e) => setCompany(e.target.value)} placeholder="e.g. Razorpay" /></Field>
          <Field label="Job title"><Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. QA Automation Engineer" /></Field>
          {careerJob ? (
            <div className="lg:col-span-2"><Notice tone="info">Using the job description from Career portals. <button type="button" className="underline" onClick={() => setCareerJob(null)}>Paste a different one</button></Notice></div>
          ) : (
            <Field label="Job description" className="lg:col-span-2">
              <Textarea rows={10} value={jd} onChange={(e) => setJd(e.target.value)} placeholder="Paste the full job description here" />
            </Field>
          )}
          <div className="lg:col-span-2">
            <p className="mb-2 text-xs font-medium text-muted-foreground">Template</p>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
              {(tpl.data?.templates ?? []).map((t) => (
                <button key={t.id} type="button" aria-pressed={template === t.id} onClick={() => void switchTemplate(t.id)}
                        className={cn("rounded-2xl border p-3 text-left", template === t.id ? "border-foreground bg-foreground text-background" : "")}>
                  <p className="text-sm font-medium">{t.name}</p>
                  <p className={cn("mt-1 text-xs", template === t.id ? "opacity-80" : "text-muted-foreground")}>{t.description}</p>
                </button>
              ))}
            </div>
          </div>
          <div className="flex justify-end lg:col-span-2">
            <Button onClick={() => void generate()} disabled={busy || (!careerJob && jd.trim().length < 30)}>
              <Sparkles /> {busy ? "Building…" : result ? "Generate again" : "Generate ATS resume"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {busy && !result && <div className="py-10"><Loader3D label="Building your resume" /></div>}

      {result && ats && (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
          <div className="space-y-6">
            <Card>
              <CardContent className="flex items-center gap-5 pt-5">
                <ProgressRing value={ats.score} trackClass="stroke-muted" barClass={scoreTone(ats.score)}>
                  <span className="text-2xl font-semibold">{ats.score}</span>
                </ProgressRing>
                <div className="min-w-0">
                  <p className="font-semibold">ATS score for {result.title}{result.company ? ` at ${result.company}` : ""}</p>
                  <p className="mt-1 text-sm text-muted-foreground">Required keywords {ats.required_coverage}% · nice-to-have {ats.preferred_coverage}% · {ats.word_count} words</p>
                  {ats.score >= 100 ? <p className="mt-1 text-sm text-[var(--tone-green)]">Every keyword and check is covered.</p>
                    : <p className="mt-1 text-sm text-muted-foreground">Only verified facts are used, so the score shows your real match. See below for how to raise it honestly.</p>}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle>Download</CardTitle><CardDescription>Saved as Your_Name_{(result.company || "Company").replace(/\W+/g, "_")}_{localDate()}</CardDescription></CardHeader>
              <CardContent className="flex flex-wrap gap-2">
                {(tpl.data?.formats ?? []).map((f) => (
                  <Button key={f.id} variant={f.id === "pdf" ? "default" : "outline"} size="sm" onClick={() => void download(f.id)}><Download /> {f.name}</Button>
                ))}
              </CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle>Keywords</CardTitle></CardHeader>
              <CardContent className="space-y-3">
                <div className="flex flex-wrap gap-1.5">{ats.matched_keywords.map((k) => <Badge key={k} variant="success">{k}</Badge>)}</div>
                {ats.missing_required.length > 0 && (
                  <div>
                    <p className="text-xs font-medium text-muted-foreground">Required but not in your profile (not added)</p>
                    <div className="mt-1.5 flex flex-wrap gap-1.5">{ats.missing_required.map((k) => <Badge key={k} variant="outline">{k}</Badge>)}</div>
                  </div>
                )}
                <ul className="space-y-1 text-sm">
                  {ats.checks.map((c) => (
                    <li key={c.check} className="flex items-center gap-2">
                      {c.passed ? <CheckCircle2 className="size-4 text-[var(--tone-green)]" /> : <XCircle className="size-4 text-[var(--tone-red)]" />}{c.check}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
            {result.improve.length > 0 && (
              <Card>
                <CardHeader><CardTitle>Raise the score</CardTitle></CardHeader>
                <CardContent><ul className="list-disc space-y-1.5 pl-5 text-sm">{result.improve.map((t) => <li key={t}>{t}</li>)}</ul></CardContent>
              </Card>
            )}
            {result.changes.length > 0 && (
              <Card>
                <CardHeader><CardTitle>What Saige changed for this job</CardTitle></CardHeader>
                <CardContent><ul className="list-disc space-y-1.5 pl-5 text-sm">{result.changes.map((t) => <li key={t}>{t}</li>)}</ul></CardContent>
              </Card>
            )}
          </div>
          <Card className="overflow-hidden">
            <CardHeader><CardTitle>Preview</CardTitle><CardDescription>{tpl.data?.templates.find((t) => t.id === template)?.name} template</CardDescription></CardHeader>
            <CardContent>
              <iframe title="Resume preview" srcDoc={preview} sandbox="" className="h-[900px] w-full rounded-xl border bg-white" />
            </CardContent>
          </Card>
        </div>
      )}

      <Card>
        <CardHeader><CardTitle>Your ATS resumes</CardTitle></CardHeader>
        <CardContent>
          {(history.data ?? []).length === 0 ? <p className="text-sm text-muted-foreground">None yet.</p> : (
            <ul className="divide-y">
              {history.data!.map((r) => (
                <li key={r.id} className="flex items-center justify-between gap-3 py-3">
                  <button type="button" onClick={() => void open(r.id)} className="flex min-w-0 items-center gap-2 text-left text-sm">
                    <FileText className="size-4 shrink-0 text-muted-foreground" /><span className="truncate font-medium">{r.name}</span>
                  </button>
                  <span className="shrink-0 text-xs text-muted-foreground">ATS {r.ats_score ?? "–"} · {timeAgo(r.created_at)}</span>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default function StudioPage() {
  return <Suspense fallback={<div className="py-16"><Loader3D label="Loading" /></div>}><Builder /></Suspense>;
}
