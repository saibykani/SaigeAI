"use client";

import { Copy, Mic, MicOff, Send, Sparkles, Trash2 } from "lucide-react";
import { useRef, useState } from "react";

import { Notice, PageHeader } from "@/components/app-shell";
import { useT } from "@/components/i18n";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Select, Textarea } from "@/components/ui/form";
import { useApi } from "@/hooks/use-api";
import { request } from "@/services/api";
import type { Interview } from "@/types/api";
import { formatDateTime } from "@/utils/format";

interface ThankYou { subject: string; body: string; to: string | null; status: "draft" | "sent" }
interface Debrief {
  id: string; company: string; role: string; round: string | null; date: string | null; questions: string[]; skills: string[];
  went_well: string[]; to_improve: string[]; next_steps: string[]; dates: string[]; interviewers: string[]; thank_you: ThankYou; created_at: string;
}
interface Bank { items: { id: string; text: string; companies: string[]; rounds: string[]; skills: string[]; count: number }[]; companies: string[]; skills: string[] }

/* eslint-disable @typescript-eslint/no-explicit-any */
type Rec = { lang: string; continuous: boolean; interimResults: boolean; start(): void; stop(): void; onresult: ((e: any) => void) | null; onend: (() => void) | null; onerror: ((e: any) => void) | null };
function getRecognition(): (new () => Rec) | null {
  if (typeof window === "undefined") return null;
  const w = window as any;
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}
/* eslint-enable @typescript-eslint/no-explicit-any */

function List({ title, items, tone }: { title: string; items: string[]; tone: string }) {
  const { t } = useT();
  return (
    <Card>
      <CardHeader><CardTitle className="text-base" style={{ color: `var(--tone-${tone})` }}>{t(title)}</CardTitle></CardHeader>
      <CardContent>
        {items.length === 0 ? <p className="text-sm text-muted-foreground">{t("Nothing detected")}</p> : (
          <ul className="flex list-disc flex-col gap-1.5 pl-5 text-sm">{items.map((x) => <li key={x}>{x}</li>)}</ul>
        )}
      </CardContent>
    </Card>
  );
}

export default function DebriefPage() {
  const { t } = useT();
  const interviews = useApi<Record<Interview["status"], Interview[]>>("/interviews");
  const history = useApi<Debrief[]>("/debriefs");
  const [filters, setFilters] = useState({ company: "", skill: "" });
  const qs = new URLSearchParams(Object.entries(filters).filter(([, v]) => v)).toString();
  const bank = useApi<Bank>(`/question-bank${qs ? `?${qs}` : ""}`);
  const [pick, setPick] = useState("");
  const [manual, setManual] = useState({ company: "", role: "" });
  const [text, setText] = useState("");
  const [listening, setListening] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [result, setResult] = useState<Debrief | null>(null);
  const [draft, setDraft] = useState<ThankYou | null>(null);
  const [to, setTo] = useState("");
  const rec = useRef<Rec | null>(null);
  const base = useRef("");

  const all = [...(interviews.data?.completed ?? []), ...(interviews.data?.upcoming ?? []), ...(interviews.data?.rescheduled ?? [])]
    .filter((i) => new Date(i.scheduled_at).getTime() < Date.now() || i.status === "completed")
    .sort((a, b) => b.scheduled_at.localeCompare(a.scheduled_at));
  const hasSpeech = getRecognition() !== null;

  function toggleMic() {
    if (listening) { rec.current?.stop(); return; }
    const R = getRecognition();
    if (!R) return;
    const r = new R();
    r.lang = "en-IN"; r.continuous = true; r.interimResults = true;
    base.current = text ? `${text.trim()} ` : "";
    r.onresult = (e) => {
      let s = "";
      for (let i = 0; i < e.results.length; i++) s += e.results[i][0].transcript;
      setText(base.current + s);
    };
    r.onend = () => setListening(false);
    r.onerror = (e) => { setListening(false); if (e?.error === "not-allowed") setError(t("Microphone permission was denied.")); };
    rec.current = r;
    r.start();
    setListening(true);
  }

  function show(d: Debrief) { setResult(d); setDraft(d.thank_you); setTo(d.thank_you.to ?? ""); }

  async function save() {
    setBusy(true); setError(null); setOk(null);
    try {
      const body: Record<string, string> = { text };
      if (pick) body.interview_id = pick; else { body.company = manual.company; body.role = manual.role; }
      const d = await request<Debrief>("/debriefs", { method: "POST", body });
      show(d); setText(""); await Promise.all([history.reload(), bank.reload()]);
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); } finally { setBusy(false); }
  }

  async function saveDraft() {
    if (!result || !draft) return;
    const d = await request<Debrief>(`/debriefs/${result.id}/thank-you`, { method: "PATCH", body: { subject: draft.subject, body: draft.body, to } });
    setResult(d);
  }

  async function send() {
    if (!result || !draft) return;
    if (!window.confirm(t("Send this thank-you email from your Gmail to {to}?", { to }))) return;
    setError(null);
    try {
      const d = await request<Debrief>(`/debriefs/${result.id}/thank-you/send`, { method: "POST", body: { to, approved: true, subject: draft.subject, body: draft.body } });
      show(d); setOk(t("Thank-you sent.")); await history.reload();
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  }

  async function remove(id: string) {
    await request(`/debriefs/${id}`, { method: "DELETE" });
    if (result?.id === id) { setResult(null); setDraft(null); }
    await Promise.all([history.reload(), bank.reload()]);
  }

  const sent = draft?.status === "sent";
  return (
    <>
      <PageHeader title="Interview debrief" description="Right after an interview, say or type what happened. Saige turns it into notes, grows your question bank and drafts a thank-you email." />
      {error && <Notice tone="error">{error}</Notice>}
      {ok && <Notice tone="success">{ok}</Notice>}
      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <CardHeader><CardTitle className="flex items-center gap-2 text-lg"><Mic className="size-5 text-primary" /> {t("New debrief")}</CardTitle></CardHeader>
          <CardContent className="flex flex-col gap-3">
            <Select value={pick} onChange={(e) => setPick(e.target.value)}>
              <option value="">{t("Another interview (enter below)")}</option>
              {all.map((i) => <option key={i.id} value={i.id}>{i.role} · {i.company} · {formatDateTime(i.scheduled_at)}</option>)}
            </Select>
            {!pick && (
              <div className="grid grid-cols-2 gap-2">
                <Input placeholder={t("Company")} value={manual.company} onChange={(e) => setManual({ ...manual, company: e.target.value })} />
                <Input placeholder={t("Role")} value={manual.role} onChange={(e) => setManual({ ...manual, role: e.target.value })} />
              </div>
            )}
            <Textarea rows={9} value={text} onChange={(e) => setText(e.target.value)}
              placeholder={t("They asked me about... It went well when... I struggled with... Next step is...")} />
            <div className="flex flex-wrap gap-2">
              {hasSpeech
                ? <Button variant="outline" onClick={toggleMic}>{listening ? <MicOff /> : <Mic />} {listening ? t("Stop") : t("Speak")}</Button>
                : <p className="text-xs text-muted-foreground">{t("Voice input isn't supported in this browser. Type your question instead.")}</p>}
              <Button onClick={save} disabled={busy || text.trim().length < 10 || (!pick && !(manual.company && manual.role))}><Sparkles /> {t("Create notes")}</Button>
            </div>
          </CardContent>
        </Card>

        <div className="flex flex-col gap-6 lg:col-span-2">
          {!result ? (
            <Card><CardContent className="py-12 text-center text-sm text-muted-foreground">{t("Your structured notes appear here.")}</CardContent></Card>
          ) : (
            <>
              <p className="text-lg font-semibold">{result.role} · {result.company}{result.round ? ` · ${result.round}` : ""}</p>
              <div className="grid gap-4 md:grid-cols-2">
                <List title="Questions they asked" items={result.questions} tone="orange" />
                <List title="What went well" items={result.went_well} tone="green" />
                <List title="To improve" items={result.to_improve} tone="red" />
                <List title="Next steps" items={[...result.next_steps, ...result.dates.map((d) => `${t("Date mentioned")}: ${d}`)]} tone="purple" />
              </div>
              {(result.skills.length > 0 || result.interviewers.length > 0) && (
                <div className="flex flex-wrap gap-2">
                  {result.skills.map((s) => <Badge key={s}>{s}</Badge>)}
                  {result.interviewers.map((s) => <Badge key={s} variant="warning">{s}</Badge>)}
                </div>
              )}
              {draft && (
                <Card>
                  <CardHeader><CardTitle className="text-base">{t("Thank-you email draft")} {sent && <Badge variant="success">{t("Sent")}</Badge>}</CardTitle></CardHeader>
                  <CardContent className="flex flex-col gap-3">
                    <Input placeholder={t("Recipient email")} value={to} onChange={(e) => setTo(e.target.value)} disabled={sent} />
                    <Input value={draft.subject} onChange={(e) => setDraft({ ...draft, subject: e.target.value })} disabled={sent} />
                    <Textarea rows={9} value={draft.body} onChange={(e) => setDraft({ ...draft, body: e.target.value })} disabled={sent} />
                    <p className="text-xs text-muted-foreground">{t("Built only from your notes, the company, the role and your name. Review before sending; nothing is sent without your approval.")}</p>
                    <div className="flex flex-wrap gap-2">
                      <Button variant="outline" onClick={() => navigator.clipboard.writeText(`${draft.subject}\n\n${draft.body}`).then(() => setOk(t("Copied.")))}><Copy /> {t("Copy")}</Button>
                      {!sent && <Button variant="outline" onClick={saveDraft}>{t("Save draft")}</Button>}
                      {!sent && <Button onClick={send} disabled={!to.includes("@")}><Send /> {t("Send from my Gmail")}</Button>}
                    </div>
                  </CardContent>
                </Card>
              )}
            </>
          )}
        </div>
      </div>

      <div className="mt-8 grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader><CardTitle className="text-lg">{t("Question bank")}</CardTitle></CardHeader>
          <CardContent className="flex flex-col gap-3">
            <div className="flex flex-wrap gap-2">
              <Select value={filters.company} onChange={(e) => setFilters({ ...filters, company: e.target.value })}>
                <option value="">{t("All companies")}</option>
                {(bank.data?.companies ?? []).map((x) => <option key={x}>{x}</option>)}
              </Select>
              <Select value={filters.skill} onChange={(e) => setFilters({ ...filters, skill: e.target.value })}>
                <option value="">{t("All skills")}</option>
                {(bank.data?.skills ?? []).map((x) => <option key={x}>{x}</option>)}
              </Select>
            </div>
            {(bank.data?.items ?? []).length === 0 && <p className="py-6 text-center text-sm text-muted-foreground">{t("No questions yet.")}</p>}
            {(bank.data?.items ?? []).map((q) => (
              <div key={q.id} className="rounded-2xl border bg-card-solid/60 p-3 text-sm">
                <p className="font-medium">{q.text}</p>
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {q.companies.map((x) => <Badge key={x}>{x}</Badge>)}
                  {q.rounds.map((x) => <Badge key={x} variant="warning">{x}</Badge>)}
                  {q.skills.map((x) => <Badge key={x} variant="success">{x}</Badge>)}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-lg">{t("Past debriefs")}</CardTitle></CardHeader>
          <CardContent className="flex flex-col gap-2">
            {(history.data ?? []).length === 0 && <p className="text-sm text-muted-foreground">{t("None")}</p>}
            {(history.data ?? []).map((d) => (
              <div key={d.id} className="flex items-center gap-2 text-sm">
                <button className="min-w-0 flex-1 text-left hover:underline" onClick={() => show(d)}>
                  <span className="font-medium">{d.role} · {d.company}</span>
                  <span className="block text-xs text-muted-foreground">{d.date} · {d.questions.length} {t("questions")}</span>
                </button>
                <Button size="sm" variant="ghost" onClick={() => remove(d.id)} aria-label={t("Delete")}><Trash2 /></Button>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </>
  );
}
