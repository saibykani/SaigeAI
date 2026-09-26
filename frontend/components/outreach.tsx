"use client";

import { Check, ClipboardCopy, ExternalLink, Mail, Pencil, Send, ShieldCheck, Sparkles, UserPlus, X } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Notice } from "@/components/app-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input, Textarea } from "@/components/ui/form";
import { useApi } from "@/hooks/use-api";
import { request } from "@/services/api";
import type { Outreach, OutreachKind, OutreachStatus, RecruiterContact } from "@/types/api";
import { formatDateTime } from "@/utils/format";

export const KIND_LABEL: Record<OutreachKind, string> = {
  referral: "Referral request",
  cold: "Cold email",
  hiring_manager: "Hiring manager",
  employee_intro: "Employee intro",
  linkedin_note: "LinkedIn note",
  followup: "Follow-up",
  thank_you: "Thank-you",
};

const STATUS_TONE: Record<OutreachStatus, "warning" | "default" | "success" | "muted" | "destructive"> = {
  draft: "warning",
  approved: "default",
  sent: "default",
  replied: "success",
  bounced: "destructive",
  no_response: "muted",
  unsubscribed: "muted",
  cancelled: "muted",
};

export const ROLE_LABEL: Record<RecruiterContact["role"], string> = {
  recruiter: "Recruiter",
  hiring_manager: "Hiring manager",
  referral: "Referral",
  alumni: "Alumni",
  other: "Other",
};

function errText(e: unknown): string {
  return e instanceof Error ? e.message : "Something went wrong";
}

/** One message through its life: edit → approve → send yourself → mark sent → outcome. */
export function OutreachCard({ item, onChange, delay = 0 }: { item: Outreach; onChange: () => void; delay?: number }) {
  const [editing, setEditing] = useState(false);
  const [subject, setSubject] = useState(item.subject);
  const [body, setBody] = useState(item.body);
  const [err, setErr] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const verified = item.validation?.status === "PASSED";

  async function act(path: string, method: "POST" | "PUT" = "POST", payload?: unknown) {
    setErr(null);
    try {
      await request(`/outreach/${item.id}${path}`, { method, body: payload });
      setEditing(false);
      onChange();
    } catch (e) {
      setErr(errText(e));
    }
  }

  async function copy() {
    await navigator.clipboard.writeText(`${item.subject}\n\n${item.body}`);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <Card className="lift animate-rise overflow-hidden" style={{ animationDelay: `${delay}ms` }}>
      <CardHeader className="gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline">{KIND_LABEL[item.kind]}</Badge>
          <Badge variant={STATUS_TONE[item.status]} className="capitalize">{item.status.replace("_", " ")}</Badge>
          {verified && <Badge variant="success" title="Checked against your verified profile"><ShieldCheck className="size-3" /> Verified</Badge>}
          <span className="ml-auto text-xs text-muted-foreground">
            {item.contact_name} · {item.company}
            {item.sent_at ? ` · sent ${formatDateTime(item.sent_at)}` : ""}
          </span>
        </div>
        {!editing && <CardTitle className="text-base">{item.subject}</CardTitle>}
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {editing ? (
          <>
            <Field label="Subject"><Input value={subject} onChange={(e) => setSubject(e.target.value)} maxLength={200} /></Field>
            <Field label="Message"><Textarea rows={9} value={body} onChange={(e) => setBody(e.target.value)} maxLength={5000} /></Field>
          </>
        ) : (
          <p className="whitespace-pre-wrap rounded-xl border bg-muted/40 p-3 text-sm leading-relaxed">{item.body}</p>
        )}
        {!verified && item.validation && (
          <Notice tone="warning">Contains claims not in your verified profile: {item.validation.violations.map((v) => v.value).join(", ")}. Edit before approving.</Notice>
        )}
        {err && <Notice tone="error">{err}</Notice>}

        <div className="flex flex-wrap items-center gap-2">
          {editing ? (
            <>
              <Button size="sm" onClick={() => act("", "PUT", { subject, body })}><Check /> Save</Button>
              <Button size="sm" variant="ghost" onClick={() => { setEditing(false); setSubject(item.subject); setBody(item.body); }}>Cancel</Button>
            </>
          ) : (
            <>
              {item.status === "draft" && (
                <>
                  <Button size="sm" onClick={() => act("/approve")} disabled={!verified}><Check /> Approve</Button>
                  <Button size="sm" variant="ghost" onClick={() => setEditing(true)}><Pencil /> Edit</Button>
                </>
              )}
              {item.status === "approved" && (
                <>
                  {item.gmail_compose && (
                    <a href={item.gmail_compose} target="_blank" rel="noopener noreferrer" className="inline-flex h-8 items-center gap-1.5 rounded-full bg-primary px-3.5 text-xs font-medium text-primary-foreground">
                      <Mail className="size-3.5" /> Open in Gmail
                    </a>
                  )}
                  {item.mailto && <a href={item.mailto} className="inline-flex h-8 items-center gap-1.5 rounded-full border px-3.5 text-xs font-medium hover:bg-muted"><ExternalLink className="size-3.5" /> Mail app</a>}
                  {!item.mailto && item.linkedin_url && (
                    <a href={item.linkedin_url} target="_blank" rel="noopener noreferrer" className="inline-flex h-8 items-center gap-1.5 rounded-full border px-3.5 text-xs font-medium hover:bg-muted"><ExternalLink className="size-3.5" /> Open LinkedIn</a>
                  )}
                  <Button size="sm" variant="outline" onClick={() => act("/mark-sent")}><Send /> I sent it</Button>
                  <Button size="sm" variant="ghost" onClick={() => setEditing(true)}><Pencil /> Edit</Button>
                </>
              )}
              <Button size="sm" variant="ghost" onClick={copy}><ClipboardCopy /> {copied ? "Copied" : "Copy"}</Button>
              {(item.status === "draft" || item.status === "approved") && (
                <Button size="sm" variant="ghost" onClick={() => act("/outcome/cancelled")}><X /> Discard</Button>
              )}
              {item.status === "sent" && (
                <>
                  <Button size="sm" variant="outline" onClick={() => act("/outcome/replied")}>Got a reply</Button>
                  <Button size="sm" variant="ghost" onClick={() => act("/outcome/no_response")}>No response</Button>
                  <Button size="sm" variant="ghost" onClick={() => act("/outcome/bounced")}>Bounced</Button>
                  <Button size="sm" variant="ghost" onClick={() => act("/outcome/unsubscribed")}>Asked not to contact</Button>
                </>
              )}
            </>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

/** On a job page: people you know at the company, and a one-click referral draft. */
export function ReferralFinder({ jobId }: { jobId: string }) {
  const { data, reload } = useApi<{ company: string; contacts: RecruiterContact[] }>(`/recruiters/for-job/${jobId}`);
  const [draft, setDraft] = useState<Outreach | null>(null);
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ name: "", email: "", linkedin_url: "", role: "referral" });
  const [err, setErr] = useState<string | null>(null);

  async function make(contactId: string, kind: OutreachKind) {
    setErr(null);
    try {
      setDraft(await request<Outreach>("/outreach/draft", { method: "POST", body: { contact_id: contactId, job_id: jobId, kind } }));
    } catch (e) {
      setErr(errText(e));
    }
  }

  async function refreshDraft() {
    if (!draft) return;
    const list = await request<Outreach[]>(`/outreach?contact_id=${draft.contact_id}`);
    setDraft(list.find((x) => x.id === draft.id) ?? null);
  }

  async function add(e: React.FormEvent) {
    e.preventDefault();
    if (!data) return;
    setErr(null);
    try {
      await request("/recruiters", { method: "POST", body: { ...form, email: form.email || null, linkedin_url: form.linkedin_url || null, company: data.company, source: "job" } });
      setAdding(false);
      setForm({ name: "", email: "", linkedin_url: "", role: "referral" });
      await reload();
    } catch (e2) {
      setErr(errText(e2));
    }
  }

  return (
    <Card style={{ borderColor: "color-mix(in srgb, var(--tone-purple) 28%, transparent)", backgroundImage: "radial-gradient(120% 90% at 100% 0%, color-mix(in srgb, var(--tone-purple) 14%, transparent), transparent 60%)" }}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2"><Sparkles className="size-4" style={{ color: "var(--tone-purple)" }} /> Get a referral</CardTitle>
        <CardDescription>Referrals are the fastest way in. People you know at {data?.company ?? "this company"}:</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {data?.contacts.length === 0 && !adding && <p className="text-sm text-muted-foreground">No contacts here yet. Add someone you know. Saige never looks people up for you.</p>}
        {data?.contacts.map((ct) => (
          <div key={ct.id} className="flex flex-wrap items-center gap-2 rounded-xl border p-2.5 text-sm">
            <div className="min-w-0 flex-1">
              <p className="truncate font-medium">{ct.name}</p>
              <p className="truncate text-xs text-muted-foreground">{ROLE_LABEL[ct.role]}{ct.title ? ` · ${ct.title}` : ""}</p>
            </div>
            <Button size="sm" variant="outline" disabled={ct.unsubscribed} onClick={() => make(ct.id, ct.role === "recruiter" || ct.role === "hiring_manager" ? "cold" : "referral")}>
              Draft {ct.role === "recruiter" || ct.role === "hiring_manager" ? "email" : "ask"}
            </Button>
          </div>
        ))}
        {adding ? (
          <form onSubmit={add} className="grid gap-2">
            <Input required placeholder="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            <Input type="email" placeholder="Email (optional)" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
            <Input placeholder="LinkedIn URL (optional)" value={form.linkedin_url} onChange={(e) => setForm({ ...form, linkedin_url: e.target.value })} />
            <div className="flex gap-2"><Button size="sm" type="submit">Add</Button><Button size="sm" variant="ghost" type="button" onClick={() => setAdding(false)}>Cancel</Button></div>
          </form>
        ) : (
          <Button size="sm" variant="ghost" className="self-start" onClick={() => setAdding(true)}><UserPlus /> Add a contact here</Button>
        )}
        {err && <Notice tone="error">{err}</Notice>}
        {draft && (
          <div className="flex flex-col gap-2">
            <OutreachCard key={draft.updated_at} item={draft} onChange={refreshDraft} />
            <Link href="/recruiters" className="text-xs font-medium hover:underline">Manage all outreach →</Link>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
