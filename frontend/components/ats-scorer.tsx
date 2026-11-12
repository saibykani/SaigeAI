"use client";

import { Check, Gauge, X } from "lucide-react";
import { useState } from "react";

import { DotRing } from "@/components/dot-ring";
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
          <Button type="submit" className="w-fit" disabled={busy || !rid}>{busy ? <DotRing size={18} dots={12} /> : <Gauge />} Score my resume</Button>
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
                  {fixing ? <DotRing size={18} dots={12} /> : <Gauge />} {fixing ? "Optimising…" : "Optimise my resume for this job"}
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

type HealthItem = { before: string; after?: string; ask?: string; edit?: boolean };
type HealthSection = { area: string; ok: boolean; tip: string; items: HealthItem[]; fixable: boolean };
type Health = { score: number; label: string; resume: string; bullets: number; quantified: number; words: number; sections: HealthSection[]; plan?: Plan };
type Plan = { rows: { before: string; after: string; changed: boolean; needs_number: boolean; ask: string }[]; projected: number; numbers_needed: number; blockers: string[] };
type FixOut = Health & { before: number; changes: string[] };

export function ResumeHealth({ resumes }: { resumes: Resume[] }) {
  const [rid, setRid] = useState("");
  const id = rid || (resumes.find((r) => r.kind !== "ATS Resume") ?? resumes[0])?.id || "";
  const { data, loading, reload } = useApi<Health>(id ? `/resumes/${id}/health` : null);
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [opts, setOpts] = useState({ verbs: true, split: true, trim_skills: false });
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<FixOut | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const tone = !data ? "purple" : data.score >= 80 ? "green" : data.score >= 55 ? "yellow" : "red";
  const fixable = (area: string) => data?.sections.find((s) => s.area === area && !s.ok && s.fixable);
  const typed = Object.values(edits).filter((v) => v.trim()).length;

  async function applyAll() {
    setBusy(true);
    setErr(null);
    try {
      const r = await request<FixOut>(`/resumes/${id}/health/fix`, { method: "POST", body: { edits, verbs: true, split: true, trim_skills: !!fixable("Skills") } });
      setResult(r);
      setEdits({});
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Couldn't apply the fixes.");
    } finally {
      setBusy(false);
    }
  }

  async function fix(only?: "verbs" | "split" | "trim_skills" | "edits") {
    setBusy(true);
    setErr(null);
    const body = only ? { edits: only === "edits" ? edits : {}, verbs: only === "verbs", split: only === "split", trim_skills: only === "trim_skills" }
      : { edits, verbs: opts.verbs && !!fixable("Strong verbs"), split: opts.split && !!fixable("Bullet length"), trim_skills: opts.trim_skills && !!fixable("Skills") };
    try {
      const r = await request<FixOut>(`/resumes/${id}/health/fix`, { method: "POST", body });
      setResult(r);
      setEdits({});
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Couldn't apply the fixes.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card id="health" className="animate-rise mb-6 scroll-mt-24">
      <CardHeader className="gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <CardTitle className="flex items-center gap-2 text-lg">Resume health</CardTitle>
          <CardDescription>What to change, line by line. Saige rewrites wording only; numbers come from you.</CardDescription>
        </div>
        <Select className="w-64" value={id} onChange={(e) => { setRid(e.target.value); setResult(null); setEdits({}); }} aria-label="Resume">
          {resumes.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
        </Select>
      </CardHeader>
      <CardContent className="space-y-5">
        {loading && !data ? <div className="skeleton h-40 rounded-2xl" /> : data && (
          <>
            <div className="flex flex-wrap items-center gap-5">
              <span style={{ color: `var(--tone-${tone})` }}>
                <ProgressRing value={data.score} size={88} stroke={8} trackClass="stroke-muted" barClass="stroke-current">
                  <span className="text-2xl font-semibold text-foreground">{data.score}</span>
                </ProgressRing>
              </span>
              <div className="text-sm">
                <p className="font-medium">{data.label}</p>
                <p className="text-muted-foreground">{data.quantified}/{data.bullets} bullets with numbers · {data.words} words · {data.sections.filter((s) => !s.ok).length} to fix</p>
              </div>
            </div>
            {data.plan && data.plan.rows.length > 0 && (() => {
              const pl = data.plan;
              const left = Math.max(0, pl.numbers_needed - typed);
              return (
                <div className="rounded-2xl border">
                  <div className="flex flex-wrap items-center gap-3 border-b p-4 text-sm">
                    <b className="font-medium">Side by side: your resume → what changes</b>
                    <span className="rounded-full border px-2.5 py-0.5">Now {data.score}</span>
                    <span>→</span>
                    <span className="rounded-full border px-2.5 py-0.5">After wording fixes {pl.projected}</span>
                    <span>→</span>
                    <span className="rounded-full bg-primary px-2.5 py-0.5 text-primary-foreground">100</span>
                    <span className="text-muted-foreground">
                      {left > 0 ? `add a real number to ${left} more bullet(s)` : "numbers done"}{pl.blockers.length ? ` · also fix in Profile: ${pl.blockers.join(", ")}` : ""}
                    </span>
                  </div>
                  <div className="hidden grid-cols-2 gap-4 border-b px-4 py-2 text-xs uppercase tracking-wide text-muted-foreground md:grid"><span>Your resume now</span><span>Change to</span></div>
                  <ul className="divide-y">
                    {pl.rows.map((r) => (
                      <li key={r.before} className="grid gap-3 p-4 text-sm md:grid-cols-2 md:gap-4">
                        <p className={r.changed || edits[r.before] ? "text-muted-foreground line-through decoration-muted-foreground/40" : ""}>{r.before}</p>
                        <div className="space-y-2">
                          {!r.changed && !r.needs_number && !edits[r.before] ? <p className="flex items-center gap-1.5 text-[var(--tone-green)]"><Check className="size-4" /> Good, no change</p>
                            : <p>{edits[r.before]?.trim() || r.after}</p>}
                          {r.needs_number && (
                            <>
                              <p className="text-xs text-primary">{r.ask}</p>
                              <Input placeholder="Type the line with your real number (optional)" value={edits[r.before] ?? ""}
                                onChange={(e) => setEdits((x) => ({ ...x, [r.before]: e.target.value }))} />
                            </>
                          )}
                        </div>
                      </li>
                    ))}
                  </ul>
                  <div className="flex flex-wrap items-center gap-3 border-t p-4">
                    <Button onClick={() => void applyAll()} disabled={busy}>{busy ? <DotRing size={18} dots={12} /> : <Check />} Apply all changes → new version</Button>
                    <span className="text-xs text-muted-foreground">Wording fixes are automatic. Numbers come only from what you type; Saige never invents them.</span>
                  </div>
                </div>
              );
            })()}
            {result && (
              <Notice tone="success">
                Saved as a new version: score {result.before} → {result.score}. {result.changes.slice(0, 4).join(" · ")}{result.changes.length > 4 ? ` · +${result.changes.length - 4} more` : ""}
              </Notice>
            )}
            {err && <Notice tone="error">{err}</Notice>}
            <ul className="divide-y rounded-2xl border">
              {[...data.sections].sort((a, b) => Number(a.ok) - Number(b.ok)).map((s) => (
                <li key={s.area} className="p-4 text-sm">
                  <p className="flex items-start gap-2">
                    {s.ok ? <Check className="mt-0.5 size-4 shrink-0" style={{ color: "var(--tone-green)" }} /> : <X className="mt-0.5 size-4 shrink-0 text-primary" />}
                    <span><b className="font-medium">{s.area}</b> <span className="text-muted-foreground">· {s.tip}</span></span>
                  </p>
                  {!s.ok && (() => {
                    const kind = s.area === "Strong verbs" ? "verbs" : s.area === "Bullet length" ? "split" : s.area === "Skills" && s.fixable ? "trim_skills"
                      : s.area === "Quantified impact" ? "edits" : null;
                    const link = ["Contact details", "Summary", "Length"].includes(s.area) ? "/profile" : null;
                    if (kind && (s.fixable || kind === "edits")) return (
                      <Button size="sm" variant="outline" className="ml-6 mt-2" disabled={busy || (kind === "edits" && typed === 0)} onClick={() => void fix(kind)}>
                        <Check /> {kind === "edits" ? (typed ? `Save my ${typed} rewrite(s) as a new version` : "Type a rewrite below, then save") : "Apply this fix → new version"}
                      </Button>);
                    if (link) return <a href={link} className="ml-6 mt-2 inline-block text-xs text-primary underline">Fix in Profile, then rebuild</a>;
                    return null;
                  })()}
                  {!s.ok && s.items.length > 0 && (
                    <ul className="mt-3 space-y-2 pl-6">
                      {s.items.map((it) => (
                        <li key={it.before} className="rounded-xl bg-muted/50 p-3">
                          <p className={it.after ? "text-muted-foreground line-through decoration-muted-foreground/40" : ""}>{it.before}</p>
                          {it.after && <p className="mt-1">→ {it.after}</p>}
                          {it.ask && <p className="mt-1 text-xs text-primary">{it.ask}</p>}
                          {it.edit && (
                            <Input className="mt-2" placeholder="Rewrite with a real result, e.g. … covering 320 test cases, cutting runs from 3 days to 6 hours"
                              value={edits[it.before] ?? ""} onChange={(e) => setEdits((x) => ({ ...x, [it.before]: e.target.value }))} />
                          )}
                        </li>
                      ))}
                    </ul>
                  )}
                </li>
              ))}
            </ul>
            <div className="flex flex-wrap items-center gap-4 rounded-2xl border p-4 text-sm">
              {fixable("Strong verbs") && <label className="flex items-center gap-2"><input type="checkbox" className="size-4 accent-[var(--primary)]" checked={opts.verbs} onChange={(e) => setOpts({ ...opts, verbs: e.target.checked })} /> Use action verbs</label>}
              {fixable("Bullet length") && <label className="flex items-center gap-2"><input type="checkbox" className="size-4 accent-[var(--primary)]" checked={opts.split} onChange={(e) => setOpts({ ...opts, split: e.target.checked })} /> Split long bullets</label>}
              {fixable("Skills") && <label className="flex items-center gap-2"><input type="checkbox" className="size-4 accent-[var(--primary)]" checked={opts.trim_skills} onChange={(e) => setOpts({ ...opts, trim_skills: e.target.checked })} /> Keep only skills my experience shows</label>}
              <Button className="ml-auto" onClick={() => void fix()} disabled={busy || (typed === 0 && !fixable("Strong verbs") && !fixable("Bullet length") && !(opts.trim_skills && fixable("Skills")))}>
                {busy ? <DotRing size={18} dots={12} /> : <Check />} {busy ? "Saving…" : `Apply fixes${typed ? ` + ${typed} rewrite(s)` : ""}`}
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">Fixes are saved as a new version of this resume, so you can always go back. Skills or employers you type that aren&apos;t in your profile are blocked by the truth guard.</p>
          </>
        )}
      </CardContent>
    </Card>
  );
}
