"use client";

import { ArrowLeft, CalendarPlus, Check, CircleAlert, ExternalLink, FileText, Mail, Send, ShieldAlert, Trash2 } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";

import { Notice, PageHeader } from "@/components/app-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input, Select, Textarea } from "@/components/ui/form";
import { useApi } from "@/hooks/use-api";
import { request } from "@/services/api";
import type { ApplicationAnswer, ApplicationDetail, ApplicationStatus } from "@/types/api";
import { cn } from "@/utils/cn";
import { formatDate, formatDateTime, humanStatus } from "@/utils/format";

const MOVE_TO: ApplicationStatus[] = ["RECRUITER_REPLIED", "SCREENING", "ASSESSMENT", "INTERVIEW_COMPLETED", "OFFER", "REJECTED", "CLOSED"];

function AnswerRow({ a, appId, onSaved }: { a: ApplicationAnswer; appId: string; onSaved: () => void }) {
  const [editing, setEditing] = useState(a.status === "REVIEW_REQUIRED" && !a.answer);
  const [value, setValue] = useState(a.answer ?? "");
  const tone = a.status === "REVIEW_REQUIRED" ? "warning" : a.status === "USER_PROVIDED" ? "default" : "success";
  return (
    <li className="rounded-2xl border bg-card-solid/60 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-sm font-medium">{a.question}</p>
        <Badge variant={tone}>{a.status === "REVIEW_REQUIRED" ? "Review required" : a.status === "USER_PROVIDED" ? "Your answer" : "Answered"}</Badge>
        <Badge variant="outline">{a.confidence}</Badge>
        {a.sensitive && <Badge variant="warning"><ShieldAlert className="size-3" /> Sensitive</Badge>}
      </div>
      {editing ? (
        <div className="mt-3 flex flex-col gap-2">
          <Textarea rows={2} value={value} onChange={(e) => setValue(e.target.value)} placeholder="Type your answer" />
          <div>
            <Button
              size="sm"
              disabled={!value.trim()}
              onClick={async () => {
                await request(`/applications/${appId}/answers/${a.id}`, { method: "PUT", body: { answer: value } });
                setEditing(false);
                onSaved();
              }}
            >
              <Check /> Save answer
            </Button>
          </div>
        </div>
      ) : (
        <div className="mt-2 flex items-start gap-2">
          <p className="flex-1 text-sm">{a.answer ?? "—"}</p>
          <Button size="sm" variant="ghost" onClick={() => setEditing(true)}>Edit</Button>
        </div>
      )}
      <p className="mt-2 text-xs text-muted-foreground">
        Source: {a.source}
        {a.note && ` · ${a.note}`}
        {a.sensitive && a.status === "REVIEW_REQUIRED" && " · Confirm before sharing"}
      </p>
      {a.sensitive && a.status === "REVIEW_REQUIRED" && a.answer && (
        <Button
          size="sm"
          variant="outline"
          className="mt-2"
          onClick={async () => {
            await request(`/applications/${appId}/answers/${a.id}`, { method: "PUT", body: { answer: a.answer } });
            onSaved();
          }}
        >
          <Check /> Approve this answer
        </Button>
      )}
    </li>
  );
}

export default function ApplicationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { data: a, error, reload } = useApi<ApplicationDetail>(`/applications/${id}`);
  const [questions, setQuestions] = useState("");
  const [msg, setMsg] = useState<{ tone: "success" | "error" | "warning"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [iv, setIv] = useState({ round: "", scheduled_at: "", meeting_url: "", interview_type: "Video" });

  if (error) return <Notice tone="error">{error}</Notice>;
  if (!a) return <div className="skeleton h-96 rounded-3xl" />;

  async function run(fn: () => Promise<unknown>, ok?: string) {
    setBusy(true);
    setMsg(null);
    try {
      await fn();
      if (ok) setMsg({ tone: "success", text: ok });
      await reload();
    } catch (e) {
      setMsg({ tone: "error", text: e instanceof Error ? e.message : "Action failed" });
    } finally {
      setBusy(false);
    }
  }

  const pendingReview = a.answers.filter((x) => x.status === "REVIEW_REQUIRED").length;
  const canApply = ["READY_TO_APPLY", "APPROVAL_REQUIRED", "SHORTLISTED", "APPLICATION_FAILED"].includes(a.status);

  return (
    <>
      <Link href="/applications" className="mb-3 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-4" /> All applications
      </Link>
      <PageHeader
        title={a.role}
        description={`${a.company}${a.match_score != null ? ` · ${a.match_score}% match` : ""} · ${humanStatus(a.status)}`}
        actions={
          <Button
            variant="ghost"
            size="sm"
            onClick={() => { if (confirm("Delete this application and its history?")) void run(async () => { await request(`/applications/${id}`, { method: "DELETE" }); router.replace("/applications"); }); }}
          >
            <Trash2 /> Delete
          </Button>
        }
      />
      {msg && <div className="mb-4"><Notice tone={msg.tone}>{msg.text}</Notice></div>}

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="flex flex-col gap-6 lg:col-span-2">
          {/* Submit */}
          <Card className="overflow-hidden">
            <div className="animate-gradient h-1 bg-[image:var(--brand-gradient)]" aria-hidden />
            <CardHeader>
              <CardTitle className="text-lg">Submit</CardTitle>
              <CardDescription>Saige opens the employer&apos;s page with everything prepared. You submit there — no site offers a permitted automatic-apply API.</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              {pendingReview > 0 && (
                <Notice tone="warning"><CircleAlert className="mr-1 inline size-4" /> {pendingReview} answer(s) need your review before applying.</Notice>
              )}
              <div className="flex flex-wrap gap-2">
                {canApply && (
                  <Button
                    variant="gradient"
                    className="animate-gradient sheen"
                    disabled={busy || pendingReview > 0}
                    onClick={() => run(async () => {
                      const r = await request<{ handoff_url: string; message: string }>(`/applications/${id}/approve`, { method: "POST" });
                      window.open(r.handoff_url, "_blank", "noopener,noreferrer");
                      setMsg({ tone: "warning", text: r.message });
                    })}
                  >
                    <Send /> Approve &amp; apply
                  </Button>
                )}
                {a.status === "APPLYING" && (
                  <Button disabled={busy} onClick={() => run(() => request(`/applications/${id}/mark-applied`, { method: "POST" }), "Marked as applied. Follow-ups scheduled.")}>
                    <Check /> I&apos;ve submitted
                  </Button>
                )}
                {a.application_url && (
                  <a href={a.application_url} target="_blank" rel="noopener noreferrer" className="inline-flex h-10 items-center gap-2 rounded-full border px-5 text-sm font-medium hover:bg-muted">
                    <ExternalLink className="size-4" /> Posting
                  </a>
                )}
                {canApply && (
                  <Button variant="ghost" disabled={busy} onClick={() => run(() => request(`/applications/${id}/reject`, { method: "POST" }), "Application withdrawn.")}>
                    Withdraw
                  </Button>
                )}
              </div>
              <div className="flex flex-wrap gap-3 text-sm">
                {a.resume_id && <Link href={`/resumes/${a.resume_id}`} className="inline-flex items-center gap-1.5 text-primary hover:underline"><FileText className="size-4" /> Resume for this application</Link>}
                {a.job_id && <Link href={`/jobs/${a.job_id}`} className="inline-flex items-center gap-1.5 text-primary hover:underline"><Mail className="size-4" /> Job &amp; cover letter</Link>}
              </div>
            </CardContent>
          </Card>

          {/* Questions */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Application questions</CardTitle>
              <CardDescription>Paste the employer&apos;s questions (one per line). Answers come only from your verified profile; anything uncertain is flagged for you.</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <Textarea rows={3} value={questions} onChange={(e) => setQuestions(e.target.value)} placeholder={"How many years of Selenium experience?\nWhat is your notice period?"} />
              <div>
                <Button
                  variant="outline"
                  disabled={busy || !questions.trim()}
                  onClick={() => run(async () => {
                    await request(`/applications/${id}/prepare`, { method: "POST", body: { questions: questions.split("\n").map((q) => q.trim()).filter(Boolean) } });
                    setQuestions("");
                  })}
                >
                  Answer questions
                </Button>
              </div>
              {a.answers.length > 0 && (
                <ul className="flex flex-col gap-3">
                  {a.answers.map((x) => <AnswerRow key={x.id + x.status} a={x} appId={id} onSaved={reload} />)}
                </ul>
              )}
            </CardContent>
          </Card>

          {/* Timeline */}
          <Card>
            <CardHeader><CardTitle className="text-lg">Timeline</CardTitle></CardHeader>
            <CardContent>
              <ol className="relative ml-2 border-l pl-6">
                {a.events.map((e, i) => (
                  <li key={e.id} className="animate-rise relative pb-5 last:pb-0" style={{ animationDelay: `${i * 40}ms` }}>
                    <span className="absolute -left-[31px] top-0.5 grid size-4 place-items-center rounded-full border-2 border-card-solid bg-primary" aria-hidden />
                    <p className="text-sm font-medium">{e.to ? humanStatus(e.to) : humanStatus(e.type)}</p>
                    <p className="text-xs text-muted-foreground">
                      {formatDateTime(e.at)} · {e.source === "gmail" ? "Detected from Gmail" : e.source === "system" ? "Automatic" : "You"}
                      {e.note && ` · ${e.note}`}
                    </p>
                  </li>
                ))}
              </ol>
            </CardContent>
          </Card>
        </div>

        <div className="flex flex-col gap-6">
          <Card>
            <CardHeader><CardTitle>Move to stage</CardTitle></CardHeader>
            <CardContent>
              <Select
                aria-label="Move to stage"
                value=""
                onChange={(e) => e.target.value && run(() => request(`/applications/${id}/status`, { method: "POST", body: { status: e.target.value } }), "Status updated.")}
              >
                <option value="">Choose a stage…</option>
                {MOVE_TO.map((s) => <option key={s} value={s}>{humanStatus(s)}</option>)}
              </Select>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>Follow-ups</CardTitle></CardHeader>
            <CardContent>
              {a.followups.length === 0 ? (
                <p className="text-sm text-muted-foreground">Scheduled automatically once you apply (day 3, day 7, close on day 14).</p>
              ) : (
                <ul className="flex flex-col gap-2 text-sm">
                  {a.followups.map((f) => (
                    <li key={f.id} className="flex items-center gap-2">
                      <span className={cn("size-2 rounded-full", f.status === "scheduled" ? "bg-primary" : "bg-muted-foreground/40")} />
                      {f.kind === "close" ? "Archive if no reply" : `Follow-up ${f.sequence}`}
                      <span className="ml-auto text-xs text-muted-foreground">{formatDate(f.due_at)} · {f.status}</span>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>Interviews</CardTitle></CardHeader>
            <CardContent className="flex flex-col gap-3">
              {a.interviews.map((i) => (
                <div key={i.id} className="rounded-xl border p-3 text-sm">
                  <p className="font-medium">{i.round || "Interview"} <Badge variant="muted" className="ml-1 capitalize">{i.status}</Badge></p>
                  <p className="text-xs text-muted-foreground">{formatDateTime(i.scheduled_at)}{i.interview_type && ` · ${i.interview_type}`}</p>
                  {i.meeting_url && <a href={i.meeting_url} target="_blank" rel="noopener noreferrer" className="text-xs text-primary hover:underline">Join link</a>}
                </div>
              ))}
              <Field label="Round"><Input value={iv.round} onChange={(e) => setIv({ ...iv, round: e.target.value })} placeholder="e.g. Technical 1" /></Field>
              <Field label="When"><Input type="datetime-local" value={iv.scheduled_at} onChange={(e) => setIv({ ...iv, scheduled_at: e.target.value })} /></Field>
              <Field label="Meeting link"><Input value={iv.meeting_url} onChange={(e) => setIv({ ...iv, meeting_url: e.target.value })} placeholder="https://" /></Field>
              <Button
                variant="outline"
                disabled={busy || !iv.scheduled_at}
                onClick={() => run(async () => {
                  await request("/interviews", { method: "POST", body: { application_id: id, round: iv.round || null, scheduled_at: new Date(iv.scheduled_at).toISOString(), meeting_url: iv.meeting_url || null, interview_type: iv.interview_type } });
                  setIv({ round: "", scheduled_at: "", meeting_url: "", interview_type: "Video" });
                }, "Interview added.")}
              >
                <CalendarPlus /> Add interview
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </>
  );
}
