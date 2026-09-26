"use client";

import { Check, Download, FileText, Mail, Pencil, ShieldCheck, Sparkles, Wand2, X } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Notice } from "@/components/app-shell";
import { CountUp, ProgressRing } from "@/components/motion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/form";
import { useApi } from "@/hooks/use-api";
import { ApiError, downloadFile, request } from "@/services/api";
import type { AtsReport, CoverLetter, JobDocuments as Docs } from "@/types/api";
import { cn } from "@/utils/cn";
import { formatDate } from "@/utils/format";

function violationText(e: unknown): string {
  if (e instanceof ApiError && e.detail && typeof e.detail === "object" && "violations" in (e.detail as object)) {
    const v = (e.detail as { violations: { value: string; reason: string }[] }).violations;
    return `Blocked — not in your verified profile: ${v.map((x) => x.value).join(", ")}`;
  }
  return e instanceof Error ? e.message : "Something went wrong";
}

function AtsPanel({ ats }: { ats: AtsReport }) {
  const tone = ats.score >= 80 ? "stroke-[var(--series-3)]" : ats.score >= 60 ? "stroke-[var(--series-1)]" : "stroke-[var(--series-4)]";
  return (
    <div className="flex flex-col gap-4 rounded-2xl border bg-card-solid/60 p-4">
      <div className="flex items-center gap-4">
        <ProgressRing value={ats.score} size={88} stroke={8} trackClass="stroke-muted" barClass={tone}>
          <span className="text-xl font-semibold"><CountUp value={ats.score} /></span>
        </ProgressRing>
        <div className="grid flex-1 grid-cols-2 gap-3 text-sm">
          <p className="col-span-2 text-xs font-medium text-muted-foreground">ATS score</p>
          <div>
            <p className="text-xs text-muted-foreground">Required keywords</p>
            <p className="font-semibold">{ats.required_coverage}%</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Nice-to-have keywords</p>
            <p className="font-semibold">{ats.preferred_coverage}%</p>
          </div>
        </div>
      </div>
      <div className="flex flex-col gap-3 text-sm">
        {ats.missing_required.length > 0 && (
          <div>
            <p className="mb-1 text-xs text-muted-foreground">Required but not in your verified profile (not added)</p>
            <div className="flex flex-wrap gap-1">
              {ats.missing_required.map((s) => <Badge key={s} variant="destructive">{s}</Badge>)}
            </div>
          </div>
        )}
        <ul className="grid gap-1.5">
          {ats.checks.map((c) => (
            <li key={c.check} className="flex items-center gap-1.5 text-xs">
              <span className={cn("grid size-4 place-items-center rounded-full", c.passed ? "bg-success/15 text-success" : "bg-warning/15 text-warning")}>
                {c.passed ? <Check className="size-3" /> : <X className="size-3" />}
              </span>
              {c.check}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function LetterEditor({ letter, onSaved }: { letter: CoverLetter; onSaved: () => void }) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(letter.text);
  const [err, setErr] = useState<string | null>(null);
  return (
    <div className="rounded-2xl border bg-card-solid/60 p-4">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <Mail className="size-4 text-muted-foreground" />
        <span className="text-sm font-medium">Cover letter</span>
        {letter.validation?.status === "PASSED" && <Badge variant="success"><ShieldCheck className="size-3" /> Verified</Badge>}
        <span className="ml-auto text-xs text-muted-foreground">{formatDate(letter.updated_at)}</span>
      </div>
      {editing ? (
        <Textarea rows={12} value={text} onChange={(e) => setText(e.target.value)} />
      ) : (
        <p className="max-h-72 overflow-y-auto whitespace-pre-wrap text-sm leading-relaxed">{letter.text}</p>
      )}
      {err && <div className="mt-2"><Notice tone="error">{err}</Notice></div>}
      <div className="mt-3 flex flex-wrap gap-2">
        {editing ? (
          <>
            <Button
              size="sm"
              onClick={async () => {
                setErr(null);
                try {
                  await request(`/cover-letters/${letter.id}`, { method: "PUT", body: { text } });
                  setEditing(false);
                  onSaved();
                } catch (e) {
                  setErr(violationText(e));
                }
              }}
            >
              <Check /> Save
            </Button>
            <Button size="sm" variant="ghost" onClick={() => { setText(letter.text); setEditing(false); }}>Cancel</Button>
          </>
        ) : (
          <>
            <Button size="sm" variant="outline" onClick={() => downloadFile(`/cover-letters/${letter.id}/docx`, "cover-letter.docx")}>
              <Download /> Word
            </Button>
            <Button size="sm" variant="ghost" onClick={() => navigator.clipboard.writeText(letter.text)}>Copy</Button>
            <Button size="sm" variant="ghost" onClick={() => setEditing(true)}><Pencil /> Edit</Button>
          </>
        )}
      </div>
    </div>
  );
}

export function JobDocuments({ jobId }: { jobId: string }) {
  const { data, reload } = useApi<Docs>(`/jobs/${jobId}/documents`);
  const [busy, setBusy] = useState<"resume" | "letter" | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function generate(kind: "resume" | "letter") {
    setBusy(kind);
    setErr(null);
    try {
      await request(kind === "resume" ? `/jobs/${jobId}/tailor-resume` : `/jobs/${jobId}/cover-letter`, {
        method: "POST",
        body: kind === "resume" ? {} : undefined,
      });
      await reload();
    } catch (e) {
      setErr(violationText(e));
    } finally {
      setBusy(null);
    }
  }

  const latestResume = data?.resumes[0];
  const latestLetter = data?.cover_letters[0];

  return (
    <Card className="animate-rise overflow-hidden">
      <div className="animate-gradient h-1 w-full bg-[image:var(--brand-gradient)]" aria-hidden />
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg"><Sparkles className="size-4 text-primary" /> AI documents</CardTitle>
        <CardDescription>Tailored only from your verified profile — reordered and focused, never embellished.</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-wrap gap-2">
          <Button variant="gradient" className="animate-gradient sheen" disabled={busy !== null} onClick={() => generate("resume")}>
            <Wand2 /> {busy === "resume" ? "Tailoring…" : latestResume ? "Re-tailor resume" : "Generate tailored resume"}
          </Button>
          <Button variant="outline" disabled={busy !== null} onClick={() => generate("letter")}>
            <Mail /> {busy === "letter" ? "Writing…" : latestLetter ? "New cover letter" : "Generate cover letter"}
          </Button>
        </div>
        {err && <Notice tone="error">{err}</Notice>}
        {!data && <div className="skeleton h-24 rounded-2xl" />}
        {latestResume && (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <FileText className="size-4 text-muted-foreground" />
              <Link href={`/resumes/${latestResume.id}`} className="font-medium hover:underline">{latestResume.name}</Link>
              <Badge variant="muted">{latestResume.engine === "deterministic" ? "Rule-based" : "Claude-polished · verified"}</Badge>
              <span className="text-xs text-muted-foreground">{formatDate(latestResume.created_at)}</span>
              <Button size="sm" variant="outline" className="ml-auto" onClick={() => downloadFile(`/resumes/${latestResume.id}/export.docx`, "resume.docx")}>
                <Download /> Word
              </Button>
            </div>
            {latestResume.ats && <AtsPanel ats={latestResume.ats} />}
          </div>
        )}
        {latestLetter && <LetterEditor key={latestLetter.id + latestLetter.updated_at} letter={latestLetter} onSaved={reload} />}
        {data && data.resumes.length > 1 && (
          <p className="text-xs text-muted-foreground">{data.resumes.length} tailored versions and {data.cover_letters.length} cover letters for this job are saved.</p>
        )}
      </CardContent>
    </Card>
  );
}
