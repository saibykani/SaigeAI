"use client";

import { Mic, MicOff, Pause, Play, RotateCcw, SkipForward, Sparkles, Trash2, Volume2 } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { Notice, PageHeader } from "@/components/app-shell";
import { InterviewerFace, PERSONAS, type Persona } from "@/components/interviewer-face";
import { ProgressRing } from "@/components/motion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Select, Textarea } from "@/components/ui/form";
import { useApi } from "@/hooks/use-api";
import { request } from "@/services/api";
import type { Application } from "@/types/api";
import { LANG_CODES, pickVoice } from "@/utils/voice";

interface Question { index: number; text: string; kind: string; skill: string | null; keywords: string[]; star: boolean }
interface AnswerResult { score: number; feedback: string[]; outline: string[]; word_count: number; filler_count: number; breakdown: Record<string, number> }
interface Session {
  id: string; role: string; company: string | null; interview_type: string; difficulty: string; language: string; persona: string;
  generated_by: string; have: string[]; missing: string[]; questions: Question[]; status: string;
}
interface Report {
  overall: number; answered: number; dimensions: Record<string, number>; skills: { skill: string; score: number }[];
  strengths: string[]; improvements: string[];
  questions: { index: number; question: string; kind: string; score: number; answered: boolean; feedback: string[]; outline: string[]; answer: string }[];
}
interface SessionRow { id: string; role: string; company: string | null; interview_type: string; status: string; questions: number; score: number | null; created_at: string }

const SECONDS = 120;

/* eslint-disable @typescript-eslint/no-explicit-any */
type Rec = { lang: string; continuous: boolean; interimResults: boolean; start(): void; stop(): void; onresult: ((e: any) => void) | null; onend: (() => void) | null; onerror: ((e: any) => void) | null };
function getRecognition(): (new () => Rec) | null {
  if (typeof window === "undefined") return null;
  const w = window as any;
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}
/* eslint-enable @typescript-eslint/no-explicit-any */

function toneFor(score: number) {
  return score >= 75 ? "var(--tone-green)" : score >= 50 ? "var(--tone-orange)" : "var(--tone-red)";
}

export default function MockInterviewPage() {
  const [session, setSession] = useState<Session | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (report && session) return <ReportView session={session} report={report} onDone={() => { setReport(null); setSession(null); }} />;
  if (session) return <Room session={session} onFinish={setReport} onError={setError} error={error} />;
  return <Setup onStart={(s) => { setError(null); setSession(s); }} onOpen={(s, r) => { setSession(s); setReport(r); }} />;
}

function Setup({ onStart, onOpen }: { onStart: (s: Session) => void; onOpen: (s: Session, r: Report) => void }) {
  const apps = useApi<Application[]>("/applications");
  const history = useApi<SessionRow[]>("/mock-interview/sessions");
  const [source, setSource] = useState<"role" | "jd" | "app">("role");
  const [form, setForm] = useState({ role: "", jd_text: "", application_id: "", interview_type: "mixed", difficulty: "medium", num_questions: 8, language: "en", persona: "priya" });
  // Opened from the resume builder ("Practise this interview"): the JD and role arrive via sessionStorage.
  useEffect(() => {
    try {
      const raw = sessionStorage.getItem("saige-mock-jd");
      if (!raw) return;
      sessionStorage.removeItem("saige-mock-jd");
      const p = JSON.parse(raw) as { jd: string; title?: string };
      setSource("jd");
      setForm((f) => ({ ...f, jd_text: p.jd, role: p.title || f.role, interview_type: "technical" }));
    } catch { /* private mode */ }
  }, []);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const set = (k: keyof typeof form, v: string | number) => setForm((f) => ({ ...f, [k]: v }));

  async function start() {
    setBusy(true); setError(null);
    try {
      const body: Record<string, unknown> = { interview_type: form.interview_type, difficulty: form.difficulty, num_questions: form.num_questions, language: form.language, persona: form.persona };
      if (source === "app") body.application_id = form.application_id;
      else { body.role = form.role; if (source === "jd") body.jd_text = form.jd_text; }
      onStart(await request<Session>("/mock-interview/sessions", { method: "POST", body }));
    } catch (e) { setError(e instanceof Error ? e.message : "Could not start"); } finally { setBusy(false); }
  }
  async function open(id: string) {
    const s = await request<Session & { report: Report | null }>(`/mock-interview/sessions/${id}`);
    if (s.report) onOpen(s, s.report); else onStart(s);
  }
  async function remove(id: string) { await request(`/mock-interview/sessions/${id}`, { method: "DELETE" }); await history.reload(); }

  const persona = PERSONAS.find((p) => p.id === form.persona) ?? PERSONAS[0];
  return (
    <>
      <PageHeader title="Mock interview" description="Practise with an AI interviewer. Questions come from the job description and your verified profile; answers are scored with feedback built only from your own facts." />
      {error && <Notice tone="error">{error}</Notice>}
      <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <Card className="animate-rise">
          <CardHeader><CardTitle>Set up your interview</CardTitle></CardHeader>
          <CardContent className="space-y-5">
            <div className="flex flex-wrap gap-2">
              {([["role", "Just a role"], ["jd", "Paste a JD"], ["app", "Saved application"]] as const).map(([k, l]) => (
                <Button key={k} size="sm" variant={source === k ? "default" : "outline"} onClick={() => setSource(k)}>{l}</Button>
              ))}
            </div>
            {source !== "app" && <label className="block space-y-1.5 text-sm"><span className="font-medium">Role</span>
              <Input value={form.role} onChange={(e) => set("role", e.target.value)} placeholder="e.g. SDET, Data Analyst" /></label>}
            {source === "jd" && <label className="block space-y-1.5 text-sm"><span className="font-medium">Job description</span>
              <Textarea rows={7} value={form.jd_text} onChange={(e) => set("jd_text", e.target.value)} placeholder="Paste the full JD" /></label>}
            {source === "app" && <label className="block space-y-1.5 text-sm"><span className="font-medium">Application</span>
              <Select value={form.application_id} onChange={(e) => set("application_id", e.target.value)}>
                <option value="">Choose…</option>
                {(apps.data ?? []).map((a) => <option key={a.id} value={a.id}>{a.role} · {a.company}</option>)}
              </Select></label>}
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="space-y-1.5 text-sm"><span className="font-medium">Interview type</span>
                <Select value={form.interview_type} onChange={(e) => set("interview_type", e.target.value)}>
                  <option value="mixed">Mixed</option><option value="hr">HR</option><option value="technical">Technical</option><option value="behavioural">Behavioural</option>
                </Select></label>
              <label className="space-y-1.5 text-sm"><span className="font-medium">Difficulty</span>
                <Select value={form.difficulty} onChange={(e) => set("difficulty", e.target.value)}>
                  <option value="easy">Easy</option><option value="medium">Medium</option><option value="hard">Hard</option>
                </Select></label>
              <label className="space-y-1.5 text-sm"><span className="font-medium">Questions: {form.num_questions}</span>
                <input type="range" min={5} max={15} value={form.num_questions} onChange={(e) => set("num_questions", Number(e.target.value))} className="w-full accent-[var(--tone-orange)]" /></label>
            </div>
            <Button size="lg" onClick={start} disabled={busy || (source === "app" ? !form.application_id : !form.role.trim() && !form.jd_text.trim())}>
              <Sparkles /> {busy ? "Preparing questions…" : "Start interview"}
            </Button>
          </CardContent>
        </Card>
        <Card className="animate-rise">
          <CardHeader><CardTitle>Your interviewer</CardTitle></CardHeader>
          <CardContent>
            <div className="grid place-items-center rounded-3xl bg-muted/40 py-4"><InterviewerFace persona={persona} speaking={false} listening={false} size={170} /></div>
            <div className="mt-4 grid grid-cols-2 gap-2">
              {PERSONAS.map((p) => (
                <button key={p.id} type="button" onClick={() => set("persona", p.id)}
                  className={`rounded-2xl border p-3 text-left text-sm transition-colors ${form.persona === p.id ? "border-[var(--tone-orange)] bg-muted" : "border-border hover:bg-muted/60"}`}>
                  <span className="font-medium">{p.name}</span><span className="block text-xs text-muted-foreground">{p.title}</span>
                </button>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
      {!!history.data?.length && (
        <Card className="mt-6">
          <CardHeader><CardTitle>Past sessions</CardTitle></CardHeader>
          <CardContent className="divide-y divide-border">
            {history.data.map((h) => (
              <div key={h.id} className="flex items-center gap-3 py-2.5 text-sm">
                <button type="button" className="flex-1 text-left hover:underline" onClick={() => open(h.id)}>
                  {h.role}{h.company ? ` · ${h.company}` : ""} <span className="text-muted-foreground">· {h.interview_type} · {h.questions} Q · {new Date(h.created_at).toLocaleDateString()}</span>
                </button>
                {h.score != null ? <Badge style={{ color: toneFor(h.score) }}>{h.score}/100</Badge> : <Badge>{h.status.replace("_", " ")}</Badge>}
                <Button size="icon" variant="ghost" aria-label="Delete" onClick={() => remove(h.id)}><Trash2 /></Button>
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </>
  );
}

function Room({ session, onFinish, onError, error }: { session: Session; onFinish: (r: Report) => void; onError: (e: string | null) => void; error: string | null }) {
  const persona: Persona = PERSONAS.find((p) => p.id === session.persona) ?? PERSONAS[0];
  const slot = PERSONAS.filter((p) => p.gender === persona.gender).indexOf(persona);
  const [i, setI] = useState(0);
  const [text, setText] = useState("");
  const [interim, setInterim] = useState("");
  const [speaking, setSpeaking] = useState(false);
  const [listening, setListening] = useState(false);
  const [left, setLeft] = useState(SECONDS);
  const [paused, setPaused] = useState(false);
  const [last, setLast] = useState<AnswerResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);
  const recRef = useRef<Rec | null>(null);
  const started = useRef(Date.now());
  const [Recognition] = useState(() => getRecognition());
  const canSpeak = typeof window !== "undefined" && "speechSynthesis" in window;
  const q = session.questions[i];

  useEffect(() => {
    if (!canSpeak) return;
    const load = () => setVoices(window.speechSynthesis.getVoices());
    load();
    window.speechSynthesis.addEventListener("voiceschanged", load);
    return () => { window.speechSynthesis.removeEventListener("voiceschanged", load); window.speechSynthesis.cancel(); };
  }, [canSpeak]);

  const speak = useCallback((line: string) => {
    if (!canSpeak) return;
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(line);
    const v = pickVoice(voices, session.language, persona.gender, Math.max(0, slot));
    if (v) { u.voice = v; u.lang = v.lang; } else u.lang = LANG_CODES[session.language];
    u.pitch = persona.pitch; u.rate = persona.rate;
    u.onstart = () => setSpeaking(true);
    u.onend = u.onerror = () => setSpeaking(false);
    window.speechSynthesis.speak(u);
  }, [canSpeak, voices, session.language, persona, slot]);

  useEffect(() => {
    if (!q) return;
    setText(""); setInterim(""); setLeft(SECONDS); started.current = Date.now();
    const id = setTimeout(() => speak(q.text), 350);
    return () => clearTimeout(id);
    // speak once per question; voices loading late should not repeat it
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [i, voices.length > 0]);

  useEffect(() => {
    if (paused || speaking) return;
    const id = setInterval(() => setLeft((s) => Math.max(0, s - 1)), 1000);
    return () => clearInterval(id);
  }, [paused, speaking, i]);

  function stopMic() { recRef.current?.stop(); recRef.current = null; setListening(false); setInterim(""); }
  function startMic() {
    if (!Recognition) return;
    window.speechSynthesis?.cancel();
    const r = new Recognition();
    r.lang = LANG_CODES[session.language]; r.continuous = true; r.interimResults = true;
    r.onresult = (e) => {
      let fin = "", tmp = "";
      for (let k = e.resultIndex; k < e.results.length; k++) {
        const res = e.results[k];
        if (res.isFinal) fin += res[0].transcript; else tmp += res[0].transcript;
      }
      if (fin) setText((t) => `${t}${t && !t.endsWith(" ") ? " " : ""}${fin.trim()}`);
      setInterim(tmp);
    };
    r.onerror = (e) => { if (e?.error === "not-allowed") onError("Microphone permission was denied. You can type your answer instead."); };
    r.onend = () => { setListening(false); setInterim(""); };
    r.start(); recRef.current = r; setListening(true);
  }

  async function submit(skipped: boolean) {
    stopMic(); window.speechSynthesis?.cancel(); setBusy(true); onError(null);
    try {
      const res = await request<AnswerResult>(`/mock-interview/sessions/${session.id}/answer`, {
        method: "POST", body: { index: q.index, text: skipped ? "" : text, skipped, duration_s: Math.round((Date.now() - started.current) / 1000) },
      });
      setLast(skipped ? null : res);
      if (i + 1 < session.questions.length) setI(i + 1);
      else onFinish(await request<Report>(`/mock-interview/sessions/${session.id}/finish`, { method: "POST" }));
    } catch (e) { onError(e instanceof Error ? e.message : "Could not save the answer"); } finally { setBusy(false); }
  }

  const mm = `${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")}`;
  return (
    <>
      <style>{`
        @keyframes mi-nod { 0%,100% { transform: translateY(0) } 50% { transform: translateY(2px) rotate(0.6deg) } }
        @keyframes mi-breathe { 0%,100% { transform: scale(1) } 50% { transform: scale(1.01) } }
        @keyframes mi-pulse { 0% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--tone-red) 45%, transparent) } 100% { box-shadow: 0 0 0 14px transparent } }
        .mi-nod { animation: mi-nod 1.8s ease-in-out infinite; transform-origin: 50% 80% }
        .mi-breathe { animation: mi-breathe 2.4s ease-in-out infinite; transform-origin: 50% 80% }
        .mi-rec { animation: mi-pulse 1.4s ease-out infinite }
        @media (prefers-reduced-motion: reduce) { .mi-nod, .mi-breathe, .mi-rec { animation: none } }
      `}</style>
      <PageHeader title="Mock interview" description={`${session.role}${session.company ? ` · ${session.company}` : ""} · ${session.interview_type} · ${session.difficulty}`} />
      {error && <Notice tone="error">{error}</Notice>}
      {!Recognition && <Notice tone="warning">Speech recognition isn&apos;t supported in this browser (for example Firefox). Type your answers instead, or use Chrome or Edge to answer by voice.</Notice>}
      {!canSpeak && <Notice tone="info">This browser can&apos;t read questions aloud; they are shown as captions.</Notice>}
      <div className="grid gap-6 lg:grid-cols-[1fr_1.3fr]">
        <Card className="animate-rise">
          <CardContent className="flex flex-col items-center gap-4 pt-6">
            <div className="relative grid place-items-center rounded-[2rem] bg-muted/40 px-8 py-4">
              <InterviewerFace persona={persona} speaking={speaking} listening={listening} />
              {speaking && <span className="absolute right-4 top-4 inline-flex items-center gap-1 rounded-full bg-background/80 px-2 py-1 text-xs"><Volume2 className="size-3" /> speaking</span>}
            </div>
            <p className="text-sm font-medium">{persona.name} <span className="text-muted-foreground">· {persona.title}</span></p>
            <div className="w-full">
              <div className="mb-1 flex justify-between text-xs text-muted-foreground"><span>Question {i + 1} of {session.questions.length}</span><span>{mm}</span></div>
              <div className="h-1.5 overflow-hidden rounded-full bg-muted"><div className="h-full rounded-full bg-[var(--tone-orange)] transition-all duration-500" style={{ width: `${((i + 1) / session.questions.length) * 100}%` }} /></div>
            </div>
            {last && (
              <div className="w-full rounded-2xl border border-border p-3 text-sm animate-rise">
                <p className="font-medium">Last answer: <span style={{ color: toneFor(last.score) }}>{last.score}/100</span></p>
                <p className="mt-1 text-muted-foreground">{last.feedback[0]}</p>
              </div>
            )}
          </CardContent>
        </Card>
        <Card className="animate-rise">
          <CardContent className="space-y-4 pt-6">
            <div key={i} className="animate-rise rounded-2xl bg-muted/50 p-4" aria-live="polite">
              <div className="mb-2 flex flex-wrap gap-1.5"><Badge>{q.kind}</Badge>{q.skill && <Badge>{q.skill}</Badge>}{q.star && <Badge>STAR</Badge>}</div>
              <p className="text-lg leading-relaxed">{q.text}</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" size="sm" onClick={() => speak(q.text)} disabled={!canSpeak}><RotateCcw /> Repeat</Button>
              <Button variant="outline" size="sm" onClick={() => setPaused((p) => !p)}>{paused ? <Play /> : <Pause />} {paused ? "Resume timer" : "Pause timer"}</Button>
              {Recognition && (listening
                ? <Button size="sm" variant="destructive" className="mi-rec" onClick={stopMic}><MicOff /> Stop</Button>
                : <Button size="sm" onClick={startMic}><Mic /> Answer by voice</Button>)}
            </div>
            <Textarea rows={8} value={text + (interim ? ` ${interim}` : "")} onChange={(e) => { setInterim(""); setText(e.target.value); }}
              placeholder={Recognition ? "Speak or type your answer. You can edit the transcript." : "Type your answer"} />
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span>{text.trim() ? text.trim().split(/\s+/).length : 0} words · aim for 60 to 250</span>
              {left === 0 && <span style={{ color: "var(--tone-red)" }}>Time is up: wrap up your answer</span>}
            </div>
            <div className="flex gap-2">
              <Button onClick={() => submit(false)} disabled={busy || !text.trim()}>{i + 1 < session.questions.length ? "Next question" : "Finish & see report"}</Button>
              <Button variant="ghost" onClick={() => submit(true)} disabled={busy}><SkipForward /> Skip</Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </>
  );
}

function ReportView({ session, report, onDone }: { session: Session; report: Report; onDone: () => void }) {
  return (
    <>
      <PageHeader title="Interview report" description={`${session.role}${session.company ? ` · ${session.company}` : ""} · ${report.answered} of ${report.questions.length} answered`}
        actions={<Button onClick={onDone}>New interview</Button>} />
      <div className="grid gap-6 lg:grid-cols-[auto_1fr_1fr]">
        <Card className="animate-rise">
          <CardContent className="grid place-items-center pt-6">
            <ProgressRing value={report.overall} size={150} stroke={12} trackClass="stroke-muted" barClass="stroke-[var(--tone-green)]">
              <div className="text-center"><div className="text-4xl font-semibold">{report.overall}</div><div className="text-xs text-muted-foreground">out of 100</div></div>
            </ProgressRing>
            <div className="mt-5 w-full space-y-2 text-sm">
              {Object.entries(report.dimensions).map(([k, v]) => (
                <div key={k}><div className="flex justify-between capitalize"><span>{k}</span><span>{v}</span></div>
                  <div className="h-1.5 rounded-full bg-muted"><div className="h-full rounded-full" style={{ width: `${v}%`, background: toneFor(v) }} /></div></div>
              ))}
            </div>
          </CardContent>
        </Card>
        <Card className="animate-rise">
          <CardHeader><CardTitle>Per skill</CardTitle></CardHeader>
          <CardContent className="space-y-2 text-sm">
            {report.skills.map((s) => (
              <div key={s.skill}><div className="flex justify-between"><span>{s.skill}</span><span>{s.score}</span></div>
                <div className="h-1.5 rounded-full bg-muted"><div className="h-full rounded-full" style={{ width: `${s.score}%`, background: toneFor(s.score) }} /></div></div>
            ))}
          </CardContent>
        </Card>
        <Card className="animate-rise">
          <CardHeader><CardTitle>Strengths & improvements</CardTitle></CardHeader>
          <CardContent className="space-y-3 text-sm">
            <ul className="space-y-1">{report.strengths.map((s) => <li key={s} style={{ color: "var(--tone-green)" }}>✓ <span className="text-foreground">{s}</span></li>)}</ul>
            <ul className="space-y-1">{report.improvements.map((s) => <li key={s} style={{ color: "var(--tone-orange)" }}>→ <span className="text-foreground">{s}</span></li>)}</ul>
          </CardContent>
        </Card>
      </div>
      <div className="mt-6 space-y-4">
        {report.questions.map((q) => (
          <Card key={q.index} className="animate-rise">
            <CardContent className="space-y-3 pt-6 text-sm">
              <div className="flex items-start justify-between gap-3">
                <p className="font-medium">{q.index + 1}. {q.question}</p>
                <span className="shrink-0 text-lg font-semibold" style={{ color: toneFor(q.score) }}>{q.answered ? q.score : "—"}</span>
              </div>
              {q.answer && <p className="rounded-2xl bg-muted/50 p-3 text-muted-foreground">{q.answer}</p>}
              <div className="grid gap-3 md:grid-cols-2">
                <div><p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">Feedback</p><ul className="list-disc space-y-1 pl-4">{q.feedback.map((f) => <li key={f}>{f}</li>)}</ul></div>
                <div><p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">Model outline (from your profile)</p><ul className="list-disc space-y-1 pl-4">{q.outline.map((f) => <li key={f}>{f}</li>)}</ul></div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </>
  );
}
