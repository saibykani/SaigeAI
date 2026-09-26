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

type Group = { id: string; label: string; tone: string; match: (e: InboxEmail) => boolean };
const PORTAL_CATS = ["Job Alert", "Portal Invite", "Portal Message", "Profile View", "Application Update", "Portal Notification"];
const portalOf = (e: InboxEmail) => (e.extracted as { portal?: string }).portal ?? null;
const GROUPS: Group[] = [
  { id: "all", label: "All", tone: "green", match: () => true },
  { id: "recruiters", label: "Recruiters", tone: "lime", match: (e) => ["Recruiter Outreach", "Recruiter Reply", "Follow-up"].includes(e.category) },
  { id: "interviews", label: "Interviews & tests", tone: "red", match: (e) => e.category.startsWith("Interview") || ["Assessment", "Coding Test"].includes(e.category) },
  { id: "applications", label: "Applications", tone: "yellow", match: (e) => ["Application Confirmation", "Rejection", "Offer", "Application Update"].includes(e.category) },
  { id: "invites", label: "Invites & messages", tone: "purple", match: (e) => ["Portal Invite", "Portal Message", "Profile View"].includes(e.category) },
  { id: "alerts", label: "Job alerts", tone: "orange", match: (e) => e.category === "Job Alert" },
  { id: "linkedin", label: "LinkedIn", tone: "teal", match: (e) => portalOf(e) === "linkedin" },
  { id: "naukri", label: "Naukri", tone: "orange", match: (e) => portalOf(e) === "naukri" },
  { id: "portals", label: "Other portals", tone: "mint", match: (e) => !!portalOf(e) && !["linkedin", "naukri"].includes(portalOf(e)!) },
  { id: "other", label: "Other", tone: "muted", match: (e) => e.category === "Other" },
];

function tone(cat: string): "success" | "warning" | "destructive" | "default" | "muted" {
  if (cat === "Offer") return "success";
  if (cat.startsWith("Interview") || cat === "Assessment" || cat === "Coding Test" || cat === "Portal Invite") return "warning";
  if (cat === "Rejection") return "destructive";
  if (cat === "Other" || cat === "Portal Notification") return "muted";
  return "default";
}

export default function InboxPage() {
  const integ = useApi<Integrations>("/integrations");
  const [filter, setFilter] = useState("all");
  const emails = useApi<InboxEmail[]>("/emails?limit=300");
  const group = GROUPS.find((x) => x.id === filter) ?? GROUPS[0];
  const shown = (emails.data ?? []).filter(group.match);
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
        description="Job-search email plus every LinkedIn, Naukri and Indeed notification, alert and invite from your Gmail (read-only). Synced every few minutes while Saige is open."
        actions={g?.connected ? (
          <Button disabled={busy} onClick={() => run(async () => {
            const r = await request<{ fetched: number; status_updates: number; alert_jobs?: number }>("/emails/sync", { method: "POST" });
            setMsg({ tone: "success", text: `Synced ${r.fetched} new email(s) · ${r.status_updates} application update(s)${r.alert_jobs ? ` · ${r.alert_jobs} job(s) from portal alerts` : ""}.` });
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
              <CardDescription>Read-only. Saige never deletes or moves mail; it only sends emails you approve.</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-3 text-sm">
              {g?.connected ? (
                <>
                  <p>Connected as <b>{g.email}</b></p>
                  <p className="text-xs text-muted-foreground">{g.last_sync_at ? `Last synced ${formatDateTime(g.last_sync_at)}` : "Not synced yet"}</p>
                  {g.last_result?.search && (
                    <p className="text-xs text-muted-foreground">
                      Last sync found {g.last_result.search.mail?.matched ?? g.last_result.search.mail?.fetched ?? 0} job-search and {g.last_result.search.portals?.matched ?? g.last_result.search.portals?.fetched ?? 0} portal email(s)
                      {g.last_result.search.mail?.mailbox ? ` in ${g.last_result.search.mail.mailbox}` : ""}.
                    </p>
                  )}
                  {g.error && <Notice tone="error">{g.error}</Notice>}
                  <Link href="/integrations" className="text-xs text-muted-foreground hover:text-foreground">Manage connection →</Link>
                </>
              ) : (
                <>
                  <p className="text-muted-foreground">Connect Gmail to detect confirmations, interviews, assessments, rejections and offers automatically.</p>
                  <Link href="/integrations#gmail-connect" className={buttonVariants()}>
                    <Link2 /> Connect Gmail
                  </Link>
                  <p className="text-xs text-muted-foreground">Connect with a Google App Password (works right away) or with Google sign-in.</p>
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
              {GROUPS.map((gr) => {
                const n = (emails.data ?? []).filter(gr.match).length;
                const on = filter === gr.id;
                return (
                  <button key={gr.id} type="button" onClick={() => setFilter(gr.id)}
                    className={cn("cursor-pointer rounded-full border px-3 py-1 text-xs transition-colors", on ? "border-transparent font-medium text-[#0b0b0c]" : "hover:bg-muted")}
                    style={on ? { background: gr.tone === "muted" ? "var(--muted-foreground)" : `var(--tone-${gr.tone})` } : undefined}>
                    {gr.label} <span className="tabular-nums opacity-70">{n}</span>
                  </button>
                );
              })}
            </div>
          </CardHeader>
          <CardContent>
            {!emails.data ? (
              <div className="skeleton h-64 rounded-2xl" />
            ) : shown.length === 0 ? (
              <div className="flex flex-col items-center gap-3 py-16 text-center">
                <Inbox className="size-8 text-muted-foreground" />
                <p className="text-sm text-muted-foreground">
                  {["linkedin", "naukri", "alerts", "invites", "portals"].includes(filter)
                    ? "Nothing from job portals yet. Turn on job alerts on LinkedIn / Naukri / Indeed with this Gmail address; they appear here after the next sync."
                    : "No email here yet."}
                </p>
              </div>
            ) : (
              <ul className="flex flex-col gap-2">
                {shown.map((e, i) => (
                  <li key={e.id} className="animate-rise rounded-2xl border bg-card-solid/50 p-4" style={{ animationDelay: `${Math.min(i, 20) * 25}ms` }}>
                    <div className="flex flex-wrap items-center gap-2">
                      {portalOf(e) && <span className="rounded-full px-2 py-0.5 text-[11px] font-semibold capitalize text-[#0b0b0c]" style={{ background: `var(--tone-${portalOf(e) === "linkedin" ? "teal" : portalOf(e) === "naukri" ? "orange" : "mint"})` }}>{portalOf(e)}</span>}
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
