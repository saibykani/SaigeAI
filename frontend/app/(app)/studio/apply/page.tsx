"use client";

import { Download, Mail, Send, Sparkles } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Notice, PageHeader } from "@/components/app-shell";
import { ProgressRing } from "@/components/motion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input, Textarea } from "@/components/ui/form";
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
  const [format, setFormat] = useState<"pdf" | "docx">("pdf");
  const [busy, setBusy] = useState<"draft" | "send" | null>(null);
  const [msg, setMsg] = useState<{ tone: "success" | "error" | "info"; text: string } | null>(null);

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

  async function send() {
    if (draft?.status !== "ready") return;
    setBusy("send");
    setMsg(null);
    try {
      const r = await request<{ to: string; from: string; file: string }>("/studio/apply/send", {
        method: "POST", body: { resume_id: draft.id, to, subject, body, format, on: localDate() },
      });
      setMsg({ tone: "success", text: `Sent from ${r.from} to ${r.to} with ${r.file} attached.` });
    } catch (e) {
      setMsg({ tone: "error", text: e instanceof Error ? e.message : "Couldn't send." });
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
          <Field label="Job description or LinkedIn post" className="lg:col-span-2">
            <Textarea rows={9} value={post} onChange={(e) => setPost(e.target.value)} placeholder="Paste the post, including the email address to apply to" />
          </Field>
          <div className="flex justify-end lg:col-span-2">
            <Button onClick={() => void makeDraft()} disabled={busy !== null || post.trim().length < 30}>
              <Sparkles /> {busy === "draft" ? "Building resume and email…" : "Draft resume & email"}
            </Button>
          </div>
        </CardContent>
      </Card>

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
              <Field label="To" hint={draft.emails_found.length > 1 ? `Also in the post: ${draft.emails_found.filter((e) => e !== to).join(", ")}` : undefined}>
                <Input type="email" value={to} onChange={(e) => setTo(e.target.value)} placeholder="No email in the post: type the address" />
              </Field>
              <Field label="Subject"><Input value={subject} onChange={(e) => setSubject(e.target.value)} /></Field>
              <Field label="Message"><Textarea rows={16} value={body} onChange={(e) => setBody(e.target.value)} /></Field>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-2 text-sm">
                  <span className="text-muted-foreground">Attach as</span>
                  {(["pdf", "docx"] as const).map((f) => (
                    <Button key={f} size="sm" variant={format === f ? "default" : "outline"} onClick={() => setFormat(f)} aria-pressed={format === f}>{f.toUpperCase()}</Button>
                  ))}
                </div>
                <Button onClick={() => void send()} disabled={busy !== null || !draft.gmail || !to.includes("@") || body.trim().length < 20}>
                  <Send /> {busy === "send" ? "Sending…" : "Send from my Gmail"}
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
                <Button variant="outline" size="sm" onClick={() => void downloadFile(`/studio/resumes/${draft.id}/download?format=${format}&on=${localDate()}`, `resume.${format}`)}>
                  <Download /> Download {format.toUpperCase()}
                </Button>
                <Link href="/studio"><Button variant="ghost" size="sm">Change template in Resume builder</Button></Link>
              </div>
              {draft.improve.length > 0 && <ul className="list-disc space-y-1 pl-5 text-xs text-muted-foreground">{draft.improve.slice(0, 3).map((t) => <li key={t}>{t}</li>)}</ul>}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
