"use client";

import { Check, Download, Sparkles, Target, X } from "lucide-react";
import { useEffect, useState } from "react";

import { Notice } from "@/components/app-shell";
import { ProgressRing } from "@/components/motion";
import { SkillConfirm } from "@/components/skill-confirm";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input, Select, Textarea } from "@/components/ui/form";
import { useApi } from "@/hooks/use-api";
import { downloadFile, request } from "@/services/api";
import type { Profile, Resume } from "@/types/api";

type Section = { section: string; ok: boolean; issue: string; add: string[]; fix: string };
type Coach = { role: string; resume: string; score: number; projected: number; matched: string[]; can_add: string[]; confirm: string[]; sections: Section[]; jd_text: string };
type Built = { id: string; ats: { score: number }; name: string };

const today = () => new Date().toISOString().slice(0, 10);

/** ATS coach agent: weak spots for any role + what to add, then builds the 100%-fit resume from verified facts. */
export function AtsCoach({ resumes }: { resumes: Resume[] }) {
  const profile = useApi<Profile>("/profile");
  const [resumeId, setResumeId] = useState("");
  const [role, setRole] = useState("");
  const [jd, setJd] = useState("");
  const [out, setOut] = useState<Coach | null>(null);
  const [built, setBuilt] = useState<Built | null>(null);
  const [busy, setBusy] = useState<"coach" | "build" | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    const p = profile.data;
    if (p && !role) setRole(p.preferences.target_roles?.[0] || p.personal.current_designation || "");
  }, [profile.data, role]);
  const rid = resumeId || (resumes.find((r) => r.kind !== "ATS Resume") ?? resumes[0])?.id || "";

  async function run() {
    setBusy("coach");
    setErr(null);
    setBuilt(null);
    try {
      setOut(await request<Coach>("/resumes/ats-coach", { method: "POST", body: { resume_id: rid, role, jd_text: jd || null } }));
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Couldn't analyse this resume.");
    } finally {
      setBusy(null);
    }
  }

  async function build() {
    if (!out) return;
    setBusy("build");
    setErr(null);
    try {
      setBuilt(await request<Built>("/studio/resume", { method: "POST", body: { jd_text: out.jd_text, title: out.role, company: "", template: "modern" } }));
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Couldn't build the resume.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <Card className="mb-6">
      <CardHeader>
        <CardTitle className="flex items-center gap-2"><Target className="size-5 text-primary" /> ATS coach: fit any role</CardTitle>
        <CardDescription>Type any role (or paste a JD). The agent shows where your resume is weak and what to add, then builds a 100%-fit resume from your verified profile.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-4 md:grid-cols-[1.2fr_1.5fr_auto] md:items-end">
          <Field label="Resume">
            <Select value={rid} onChange={(e) => setResumeId(e.target.value)}>{resumes.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}</Select>
          </Field>
          <Field label="Target role"><Input value={role} onChange={(e) => setRole(e.target.value)} placeholder="e.g. SDET, Data Analyst, Java Developer" /></Field>
          <Button onClick={() => void run()} disabled={!rid || role.trim().length < 2 || busy !== null}><Sparkles /> {busy === "coach" ? "Analysing…" : "Find weak spots"}</Button>
        </div>
        <details>
          <summary className="cursor-pointer text-sm text-muted-foreground">Have a specific job description? Paste it (optional)</summary>
          <Textarea className="mt-2" rows={5} value={jd} onChange={(e) => setJd(e.target.value)} placeholder="Paste the JD for an exact match" />
        </details>
        {err && <Notice tone="error">{err}</Notice>}

        {out && (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-6 rounded-2xl border p-4">
              <div className="flex items-center gap-3">
                <ProgressRing value={out.score} size={72} stroke={7} trackClass="stroke-muted" barClass="stroke-[var(--primary)]"><span className="font-semibold">{out.score}</span></ProgressRing>
                <div className="text-sm"><p className="font-medium">Now</p><p className="text-muted-foreground">{out.resume}</p></div>
              </div>
              <span className="text-2xl text-muted-foreground">→</span>
              <div className="flex items-center gap-3">
                <ProgressRing value={out.projected} size={72} stroke={7} trackClass="stroke-muted" barClass="stroke-[var(--primary)]"><span className="font-semibold">{out.projected}</span></ProgressRing>
                <div className="text-sm"><p className="font-medium">After the verified fixes</p><p className="text-muted-foreground">for {out.role}</p></div>
              </div>
            </div>

            <ul className="divide-y rounded-2xl border">
              {out.sections.map((s) => (
                <li key={s.section} className="flex gap-3 p-4">
                  {s.ok ? <Check className="mt-0.5 size-5 shrink-0 text-[var(--tone-green)]" /> : <X className="mt-0.5 size-5 shrink-0 text-primary" />}
                  <div className="min-w-0 text-sm">
                    <p className="font-medium">{s.section} <span className="font-normal text-muted-foreground">· {s.issue}</span></p>
                    {s.add.length > 0 && <p className="mt-1 flex flex-wrap gap-1.5">{s.add.map((a) => <span key={a} className="rounded-full border px-2 py-0.5 text-xs">{a}</span>)}</p>}
                    {!s.ok && s.fix && <p className="mt-1 text-muted-foreground">{s.fix}</p>}
                  </div>
                </li>
              ))}
            </ul>

            {out.confirm.length > 0 && (
              <SkillConfirm required={out.confirm} onConfirmed={() => run()} />
            )}

            <div className="flex flex-wrap items-center gap-3">
              <Button size="lg" onClick={() => void build()} disabled={busy !== null}>
                <Sparkles /> {busy === "build" ? "Building…" : `Build my ${out.role} resume`}
              </Button>
              {built && (
                <>
                  <span className="text-sm">ATS score <b className="text-primary">{built.ats.score}</b> · saved in ATS Studio</span>
                  <Button variant="outline" size="sm" onClick={() => void downloadFile(`/studio/resumes/${built.id}/download?format=pdf&on=${today()}`, "resume.pdf")}><Download /> PDF</Button>
                  <Button variant="outline" size="sm" onClick={() => void downloadFile(`/studio/resumes/${built.id}/download?format=docx&on=${today()}`, "resume.docx")}><Download /> Word</Button>
                </>
              )}
            </div>
            <p className="text-xs text-muted-foreground">Only skills and facts already in your profile are added. Confirm a skill above only if you have really used it.</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
