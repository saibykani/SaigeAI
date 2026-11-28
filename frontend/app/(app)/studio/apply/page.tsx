"use client";

import { Download, Mail, Pencil, RotateCcw, Send, Sparkles, Upload } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { ScanLoader } from "@/components/scan-loader";
import { Notice, PageHeader } from "@/components/app-shell";
import { ProgressRing } from "@/components/motion";
import { ResumeEditor } from "@/components/resume-editor";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input, Textarea } from "@/components/ui/form";
import { SkillConfirm } from "@/components/skill-confirm";
import { useUndoSend } from "@/components/undo-send";
import { downloadFile, request } from "@/services/api";
import type { ApplyDraft } from "@/types/api";

const localDate = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

export default function ApplyByEmailPage() {
  const [post, setPost] = useState("");
  const [company, setCompany] = useState("");
  const [title, setTitle] = useState("");
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [draft, setDraft] = useState<ApplyDraft | null>(null);
  const [to, setTo] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [format, setFormat] = useState<"pdf" | "docx" | "text">("pdf");
  const fileRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState<"draft" | "send" | null>(null);
  const undoSend = useUndoSend();
  const [msg, setMsg] = useState<{ tone: "success" | "error" | "info"; text: string } | null>(null);
  const [templates, setTemplates] = useState<{ id: string; name: string }[]>([]);
  const [tplId, setTplId] = useState("");
  const [editing, setEditing] = useState(false);
  useEffect(() => { request<{ id: string; name: string }[]>("/recruiters/email-templates").then(setTemplates).catch(() => undefined); }, []);

  async function applyTemplate(id: string) {
    setTplId(id);
    if (!id) return;
    try {
      const r = await request<{ subject: string; body: string }>("/recruiters/email-templates/render", {
        method: "POST", body: { template_id: id, company: draft?.company || company, role: (draft && "title" in draft ? draft.title : "") || title },
      });
      setSubject(r.subject);
      setBody(r.body);
    } catch (e) {
      setMsg({ tone: "error", text: e instanceof Error ? e.message : "Couldn't use that template." });
    }
  }

  function clearAll() {
    setPost(""); setCompany(""); setTitle(""); setAnswers({}); setDraft(null);
    setTo(""); setSubject(""); setBody(""); setTplId(""); setEditing(false); setMsg(null);
  }

  const toList = to.split(/[,;\s]+/).map((e) => e.trim()).filter(Boolean);
  const toValid = toList.length > 0 && toList.length <= 10 && toList.every((e) => /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(e));

  async function readFile(f: File) {
    setMsg(null);
    try {
      const fd = new FormData();
      fd.append("file", f);
      const r = await request<{ text: string; emails_found: string[] }>("/studio/apply/extract", { method: "POST", form: fd });
      setPost(r.text);
      setMsg({ tone: "success", text: `Read ${f.name}${r.emails_found.length ? `: found ${r.emails_found.join(", ")}` : ""}. Now click Draft.` });
    } catch (e) {
      setMsg({ tone: "error", text: e instanceof Error ? e.message : "Couldn't read that file." });
    } finally {
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  async function makeDraft() {
    setBusy("draft");
    setMsg(null);
    try {
      const r = await request<ApplyDraft>("/studio/apply/draft", { method: "POST", body: { jd_text: post, title, company, answers } });
      setDraft(r);
      if (r.company && !company) setCompany(r.company);
      if (r.status === "ready") {
        setTo(r.to ?? "");
        setSubject(r.subject ?? "");
        setBody(r.body ?? "");
      }
    } catch (e) {
      setMsg({ tone: "error", text: e instanceof Error ? e.message : "Couldn't read this post." });
    } finally {
      setBusy(null);
    }
  }

  function send() {
    if (draft?.status !== "ready") return;
    setBusy("send");
    setMsg(null);
    undoSend(toList.length > 1 ? `to ${toList.length} addresses` : `to ${to}`, doSend, { onUndo: () => setBusy(null) });
  }

  async function doSend() {
    if (draft?.status !== "ready") return;
    try {
      const r = await request<{ to: string; from: string; file: string; failed: { to: string; error: string }[] }>("/studio/apply/send", {
        method: "POST", body: { resume_id: draft.id, to: toList.join(", "), subject, body, format, on: localDate() },
      });
      const fail = r.failed.length ? ` Not sent to ${r.failed.map((f) => f.to).join(", ")}: ${r.failed[0].error}` : "";
      setMsg({ tone: r.failed.length ? "info" : "success", text: `Sent from ${r.from} to ${r.to} (${r.file}).${fail}` });
    } catch (e) {
      const text = e instanceof Error ? e.message : "Couldn't send.";
      setMsg({ tone: "error", text: /unexpectedly closed|Gmail API|refusing/i.test(text) ? `${text} Fix: Settings → Integrations → “Send through the Gmail API”.` : text });
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Apply by email"
        description="Paste a job description or a LinkedIn hiring post. Saige builds a resume for it from your verified profile, drafts the application email and sends it from your Gmail when you click Send." />
      {msg && <Notice tone={msg.tone}>{msg.text}</Notice>}
      <Card>
        <CardContent className="grid gap-4 pt-5 lg:grid-cols-2">
          <Field label="Company"><Input value={company} onChange={(e) => setCompany(e.target.value)} placeholder="Optional: read from the post if empty" /></Field>
          <Field label="Job title"><Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Optional: read from the post if empty" /></Field>
          <Field label="Job description or LinkedIn post" className="lg:col-span-2"
                 hint="Paste the text, or upload the post as a PDF, Word or text file.">
            <Textarea rows={9} value={post} onChange={(e) => setPost(e.target.value)} placeholder="Paste the post, including the email address to apply to" />
          </Field>
          <input ref={fileRef} type="file" accept=".pdf,.docx,.txt" className="hidden"
                 onChange={(e) => { const f = e.target.files?.[0]; if (f) void readFile(f); }} />
          <div className="flex flex-wrap justify-end gap-2 lg:col-span-2">
            <Button variant="outline" onClick={() => fileRef.current?.click()} disabled={busy !== null}><Upload /> Upload PDF / Word / text</Button>
            <Button onClick={() => void makeDraft()} disabled={busy !== null || post.trim().length < 30}>
              <Sparkles /> {busy === "draft" ? "Building resume and email…" : "Draft resume & email"}
            </Button>
            <Button variant="ghost" onClick={clearAll} disabled={busy !== null}><RotateCcw /> Clear</Button>
          </div>
        </CardContent>
      </Card>

      {busy === "draft" && <ScanLoader title="Preparing your application" messages={["Reading the post…", "Finding the email to apply to…", "Building a resume for this role…", "Writing your email…", "Checking every claim…"]} />}

      {draft?.status === "needs_details" && (
        <Card>
          <CardHeader>
            <CardTitle>A few details first</CardTitle>
            <CardDescription>The post asks for these and they aren&apos;t in your profile. Saige saves them to your Profile so it asks only once.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-2">
            {draft.questions.map((q) => (
              <Field key={q.key} label={q.label}>
                <Input type={q.type === "number" ? "number" : "text"} inputMode={q.type === "number" ? "decimal" : undefined}
                  value={answers[q.key] ?? ""} onChange={(e) => setAnswers((a) => ({ ...a, [q.key]: e.target.value }))} />
              </Field>
            ))}
            <div className="flex justify-end sm:col-span-2">
              <Button onClick={() => void makeDraft()} disabled={busy !== null}><Sparkles /> {busy === "draft" ? "Working…" : "Save & continue"}</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {draft?.status === "ready" && (
        <div className="grid gap-6 xl:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2"><Mail className="size-5" /> Email</CardTitle>
              <CardDescription>
                {draft.gmail ? `Sends from ${draft.gmail}. Review and edit before sending.`
                  : <>Gmail isn&apos;t connected. <Link href="/integrations" className="underline">Connect it with an App Password</Link> to send from Saige.</>}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Field label="To" hint="Several addresses? Separate them with commas. Each one gets its own email (up to 10).">
                <Input value={to} onChange={(e) => setTo(e.target.value)} placeholder="hr@company.com, careers@company.com" />
              </Field>
              {draft.emails_found.filter((e) => !toList.includes(e)).length > 0 && (
                <div className="flex flex-wrap items-center gap-2 text-sm">
                  <span className="text-muted-foreground">Also in the post:</span>
                  {draft.emails_found.filter((e) => !toList.includes(e)).map((e) => (
                    <Button key={e} size="sm" variant="outline" onClick={() => setTo([...toList, e].join(", "))}>+ {e}</Button>
                  ))}
                  <Button size="sm" variant="ghost" onClick={() => setTo([...new Set([...toList, ...draft.emails_found])].join(", "))}>Add all</Button>
                </div>
              )}
              <Field label="Email template" hint="Fills the subject and message from your verified profile. Edit anything after.">
                <select value={tplId} onChange={(e) => void applyTemplate(e.target.value)} className="h-10 w-full rounded-xl border bg-transparent px-3 text-sm">
                  <option value="">Saige's draft for this post</option>
                  {templates.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
                </select>
              </Field>
              <Field label="Subject"><Input value={subject} onChange={(e) => setSubject(e.target.value)} /></Field>
              <Field label="Message"><Textarea rows={16} value={body} onChange={(e) => setBody(e.target.value)} /></Field>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-2 text-sm">
                  <span className="text-muted-foreground">Attach as</span>
                  {(["pdf", "docx", "text"] as const).map((f) => (
                    <Button key={f} size="sm" variant={format === f ? "default" : "outline"} onClick={() => setFormat(f)} aria-pressed={format === f}
                            title={f === "text" ? "No attachment: your resume is pasted as text below the message" : undefined}>
                      {f === "text" ? "Text in email" : f === "docx" ? "Word" : "PDF"}
                    </Button>
                  ))}
                </div>
                <Button onClick={send} disabled={busy !== null || !draft.gmail || !toValid || body.trim().length < 20}>
                  <Send /> {busy === "send" ? "Sending…" : toList.length > 1 ? `Send to ${toList.length}` : "Send"}
                </Button>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div className="flex items-center gap-4">
                <ProgressRing value={draft.ats.score} trackClass="stroke-muted" barClass="stroke-[var(--tone-teal)]">
                  <span className="text-lg font-semibold">{draft.ats.score}</span>
                </ProgressRing>
                <div className="min-w-0">
                  <CardTitle>{draft.title}{draft.company ? ` · ${draft.company}` : ""}</CardTitle>
                  <CardDescription>ATS match with this post · <Badge variant="outline">{draft.verdict.label}</Badge></CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <iframe title="Resume preview" srcDoc={draft.html} className="h-[560px] w-full rounded-2xl border bg-white" sandbox="" />
              <div className="flex flex-wrap gap-2">
                <Button variant="outline" size="sm" onClick={() => void downloadFile(`/studio/resumes/${draft.id}/download?format=${format === "text" ? "txt" : format}&on=${localDate()}`, `resume.${format === "text" ? "txt" : format}`)}>
                  <Download /> Download {format === "text" ? "TXT" : format === "docx" ? "Word" : "PDF"}
                </Button>
                <Button variant="outline" size="sm" onClick={() => setEditing((v) => !v)}><Pencil /> Edit resume</Button>
                <Link href="/studio"><Button variant="ghost" size="sm">Change template in Resume builder</Button></Link>
              </div>
              {editing && draft?.id && (
                <ResumeEditor resumeId={draft.id} onClose={() => setEditing(false)}
                  onSaved={() => setMsg({ tone: "success", text: "Resume saved. Downloads and the email attachment now use your edited version." })} />
              )}
              <SkillConfirm required={draft.ats.missing_required} preferred={draft.ats.missing_preferred} onConfirmed={() => makeDraft()} />
              {draft.improve.length > 0 && <ul className="list-disc space-y-1 pl-5 text-xs text-muted-foreground">{draft.improve.slice(0, 3).map((t) => <li key={t}>{t}</li>)}</ul>}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
