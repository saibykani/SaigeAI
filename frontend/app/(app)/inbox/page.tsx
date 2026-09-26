"use client";

import { ArrowRight, Inbox, Link2, Mail, RefreshCw, Video, Zap } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Notice, PageHeader } from "@/components/app-shell";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input, Textarea } from "@/components/ui/form";
import { useApi } from "@/hooks/use-api";
import { request } from "@/services/api";
import type { InboxEmail, Integrations } from "@/types/api";
import { cn } from "@/utils/cn";
import { formatDateTime } from "@/utils/format";

const CATEGORIES = ["All", "Application Confirmation", "Interview Invitation", "Interview Reschedule", "Assessment", "Coding Test",
  "Recruiter Outreach", "Recruiter Reply", "Rejection", "Offer", "Follow-up", "Other"];

function tone(cat: string): "success" | "warning" | "destructive" | "default" | "muted" {
  if (cat === "Offer") return "success";
  if (cat.startsWith("Interview") || cat === "Assessment" || cat === "Coding Test") return "warning";
  if (cat === "Rejection") return "destructive";
  if (cat === "Other") return "muted";
  return "default";
}

export default function InboxPage() {
  const integ = useApi<Integrations>("/integrations");
  const [filter, setFilter] = useState("All");
  const emails = useApi<InboxEmail[]>(filter === "All" ? "/emails" : `/emails?category=${encodeURIComponent(filter)}`);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ tone: "success" | "error" | "info"; text: string } | null>(null);
  const [paste, setPaste] = useState({ sender: "", subject: "", body: "" });

  useEffect(() => {
    const p = new URLSearchParams(window.location.search).get("gmail");
    if (p === "connected") setMsg({ tone: "success", text: "Gmail connected. Click Sync to scan the last 30 days of job-search mail." });
  }, []);

  async function run(fn: () => Promise<unknown>) {
    setBusy(true);
    setMsg(null);
    try {
      await fn();
      await Promise.all([emails.reload(), integ.reload()]);
    } catch (e) {
      setMsg({ tone: "error", text: e instanceof Error ? e.message : "Something went wrong" });
    } finally {
      setBusy(false);
    }
  }

  const g = integ.data?.gmail;

  return (
    <>
      <PageHeader
        title="Inbox"
        description="Saige reads your job-search email (read-only), classifies it and updates the matching application automatically — every change links back to the email."
        actions={g?.connected ? (
          <Button disabled={busy} onClick={() => run(async () => {
            const r = await request<{ fetched: number; status_updates: number }>("/emails/sync", { method: "POST" });
            setMsg({ tone: "success", text: `Synced ${r.fetched} new email(s) · ${r.status_updates} application update(s).` });
          })}>
            <RefreshCw className={cn(busy && "animate-spin")} /> Sync Gmail
          </Button>
        ) : undefined}
      />
      {msg && <div className="mb-4"><Notice tone={msg.tone}>{msg.text}</Notice></div>}

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="flex flex-col gap-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2"><Mail className="size-4" /> Gmail</CardTitle>
              <CardDescription>Read-only access through Google&apos;s official OAuth. Saige never sends or deletes mail.</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-3 text-sm">
              {g?.connected ? (
                <>
                  <p>Connected as <b>{g.email}</b></p>
                  <p className="text-xs text-muted-foreground">{g.last_sync_at ? `Last synced ${formatDateTime(g.last_sync_at)}` : "Not synced yet"}</p>
                  {g.error && <Notice tone="error">{g.error}</Notice>}
                  <Link href="/integrations" className="text-xs text-muted-foreground hover:text-foreground">Manage connection →</Link>
                </>
              ) : (
                <>
                  <p className="text-muted-foreground">Connect Gmail to detect confirmations, interviews, assessments, rejections and offers automatically.</p>
                  <Button disabled={busy || !g?.available} onClick={() => run(async () => {
                    const r = await request<{ url: string }>("/auth/connect/gmail", { method: "POST" });
                    window.location.href = r.url;
                  })}>
                    <Link2 /> Connect Gmail
                  </Button>
                  {!g?.available && <p className="text-xs text-muted-foreground">Google OAuth isn&apos;t configured on the server.</p>}
                </>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2"><Zap className="size-4" /> Paste an email</CardTitle>
              <CardDescription>Works without Gmail — the same classification and automatic updates apply.</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              <Field label="From"><Input value={paste.sender} onChange={(e) => setPaste({ ...paste, sender: e.target.value })} placeholder="Priya <priya@company.com>" /></Field>
              <Field label="Subject"><Input value={paste.subject} onChange={(e) => setPaste({ ...paste, subject: e.target.value })} /></Field>
              <Field label="Body"><Textarea rows={5} value={paste.body} onChange={(e) => setPaste({ ...paste, body: e.target.value })} /></Field>
              <Button variant="outline" disabled={busy || !paste.sender || !paste.subject || !paste.body} onClick={() => run(async () => {
                const e = await request<InboxEmail>("/emails/import", { method: "POST", body: paste });
                setPaste({ sender: "", subject: "", body: "" });
                setMsg({ tone: "success", text: `Classified as “${e.category}”${e.action ? ` · ${e.action.replace("status:", "status → ")}` : ""}.` });
              })}>
                Classify &amp; apply
              </Button>
            </CardContent>
          </Card>
        </div>

        <Card className="lg:col-span-2">
          <CardHeader>
            <div className="flex flex-wrap gap-1.5">
              {CATEGORIES.map((cat) => (
                <button key={cat} type="button" onClick={() => setFilter(cat)}
                  className={cn("cursor-pointer rounded-full border px-3 py-1 text-xs transition-colors", filter === cat ? "bg-primary text-primary-foreground" : "hover:bg-muted")}>
                  {cat}
                </button>
              ))}
            </div>
          </CardHeader>
          <CardContent>
            {!emails.data ? (
              <div className="skeleton h-64 rounded-2xl" />
            ) : emails.data.length === 0 ? (
              <div className="flex flex-col items-center gap-3 py-16 text-center">
                <Inbox className="size-8 text-muted-foreground" />
                <p className="text-sm text-muted-foreground">No job-search email yet.</p>
              </div>
            ) : (
              <ul className="flex flex-col gap-2">
                {emails.data.map((e, i) => (
                  <li key={e.id} className="animate-rise rounded-2xl border bg-card-solid/50 p-4" style={{ animationDelay: `${i * 25}ms` }}>
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant={tone(e.category)}>{e.category}</Badge>
                      <span className="truncate text-sm font-medium">{e.subject}</span>
                      <span className="ml-auto text-xs text-muted-foreground">{formatDateTime(e.received_at)}</span>
                    </div>
                    <p className="mt-1 truncate text-xs text-muted-foreground">{e.sender}</p>
                    <p className="mt-2 line-clamp-2 text-sm text-muted-foreground">{e.snippet}</p>
                    <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
                      {e.extracted.interview_at && <Badge variant="outline">Interview {formatDateTime(e.extracted.interview_at)}</Badge>}
                      {e.extracted.meeting_url && <a href={e.extracted.meeting_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-primary hover:underline"><Video className="size-3" /> Meeting link</a>}
                      {e.extracted.deadline && <Badge variant="warning">Due {formatDateTime(e.extracted.deadline)}</Badge>}
                      {e.action && <Badge variant="success">{e.action.replace("status:", "Status → ").replace("interview_rescheduled", "Interview rescheduled")}</Badge>}
                      {e.application_id && (
                        <Link href={`/applications/${e.application_id}`} className={buttonVariants({ variant: "ghost", size: "sm", className: "ml-auto" })}>Application <ArrowRight /></Link>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </>
  );
}
