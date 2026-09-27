"use client";

import { Check, ExternalLink, GraduationCap, MessageCircleQuestion, Mic, TriangleAlert } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { request } from "@/services/api";

type Prep = {
  technical: { skill: string; you_have_it: boolean; questions: string[] }[];
  behavioural: { question: string; your_story: string | null; tip: string }[];
  ask_them: string[];
  research: { label: string; url: string }[];
  prepare_first: string[];
  pitch: string;
};

/** Interview prep for this job: likely questions, your own stories to answer with, and what to ask. */
export function InterviewPrep({ jobId }: { jobId: string }) {
  const [data, setData] = useState<Prep | null>(null);
  const [busy, setBusy] = useState(false);
  const [tab, setTab] = useState<"tech" | "star" | "ask">("tech");
  async function load() {
    setBusy(true);
    try { setData(await request<Prep>(`/jobs/${jobId}/interview-prep`)); } finally { setBusy(false); }
  }
  return (
    <Card className="animate-rise" style={{ borderColor: "color-mix(in srgb, var(--tone-red) 28%, transparent)" }}>
      <CardHeader className="gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <CardTitle className="flex items-center gap-2 text-lg">
            <span className="grid size-8 place-items-center rounded-lg text-[#0b0b0c]" style={{ background: "var(--tone-red)" }}><GraduationCap className="size-4" /></span>
            Interview prep
          </CardTitle>
          <CardDescription>Likely questions from this job description, your own achievements to answer them with (STAR), and smart questions to ask.</CardDescription>
        </div>
        {!data && <Button size="sm" disabled={busy} onClick={load}>{busy ? "Preparing…" : "Prepare me"}</Button>}
      </CardHeader>
      {data && (
        <CardContent className="flex flex-col gap-4">
          <div className="rounded-2xl border p-3 text-sm">
            <p className="mb-1 flex items-center gap-1.5 font-medium"><Mic className="size-4" style={{ color: "var(--tone-red)" }} /> Your 30-second intro</p>
            <p className="text-muted-foreground">{data.pitch}</p>
          </div>
          {data.prepare_first.length > 0 && (
            <p className="flex items-start gap-2 text-sm" style={{ color: "var(--tone-orange)" }}>
              <TriangleAlert className="mt-0.5 size-4 shrink-0" /> Brush up first: {data.prepare_first.join(", ")} (asked in the JD, not in your profile yet).
            </p>
          )}
          <div className="inline-flex w-fit rounded-full border bg-muted/50 p-1 text-sm">
            {([["tech", "Technical"], ["star", "Behavioural (STAR)"], ["ask", "Ask them"]] as const).map(([id, label]) => (
              <button key={id} type="button" onClick={() => setTab(id)} className="rounded-full px-3.5 py-1"
                style={tab === id ? { background: "var(--tone-red)", color: "#0b0b0c", fontWeight: 600 } : undefined}>{label}</button>
            ))}
          </div>
          {tab === "tech" && (
            <ul className="grid gap-2 md:grid-cols-2">
              {data.technical.map((t) => (
                <li key={t.skill} className="rounded-2xl border p-3 text-sm">
                  <p className="mb-1 flex items-center gap-1.5 font-medium">
                    {t.you_have_it ? <Check className="size-4" style={{ color: "var(--tone-green)" }} /> : <TriangleAlert className="size-4" style={{ color: "var(--tone-orange)" }} />}
                    {t.skill}
                  </p>
                  <ul className="list-disc space-y-1 pl-5 text-muted-foreground">{t.questions.map((q) => <li key={q}>{q}</li>)}</ul>
                </li>
              ))}
            </ul>
          )}
          {tab === "star" && (
            <ul className="flex flex-col gap-2">
              {data.behavioural.map((b) => (
                <li key={b.question} className="rounded-2xl border p-3 text-sm">
                  <p className="flex items-center gap-1.5 font-medium"><MessageCircleQuestion className="size-4" style={{ color: "var(--tone-purple)" }} /> {b.question}</p>
                  {b.your_story && <p className="mt-1.5 rounded-xl bg-muted/60 p-2 text-muted-foreground">Your story: {b.your_story}</p>}
                  <p className="mt-1 text-xs text-muted-foreground">{b.tip}</p>
                </li>
              ))}
            </ul>
          )}
          {tab === "ask" && (
            <div className="grid gap-3 md:grid-cols-2">
              <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">{data.ask_them.map((q) => <li key={q}>{q}</li>)}</ul>
              <div className="flex flex-col gap-1.5 text-sm">
                <p className="font-medium">Research the company</p>
                {data.research.map((r) => <a key={r.label} href={r.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 underline">{r.label} <ExternalLink className="size-3" /></a>)}
              </div>
            </div>
          )}
        </CardContent>
      )}
    </Card>
  );
}
