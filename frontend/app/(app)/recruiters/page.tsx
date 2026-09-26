"use client";

import { Building2, ClipboardCopy, FileText, Inbox, MailCheck, Reply, Send, Upload, UserPlus, Users } from "lucide-react";
import { useMemo, useState } from "react";

import { Notice, PageHeader } from "@/components/app-shell";
import { CountKpi, RateKpi } from "@/components/kpi";
import { OutreachCard, ROLE_LABEL } from "@/components/outreach";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input, Select, Textarea } from "@/components/ui/form";
import { useApi } from "@/hooks/use-api";
import { request } from "@/services/api";
import type { ContactRole, Outreach, OutreachKind, OutreachStats, OutreachTemplate, RecruiterContact } from "@/types/api";
import { cn } from "@/utils/cn";
import { formatDate, formatDateTime } from "@/utils/format";

type Tab = "queue" | "sent" | "contacts" | "templates";
type Msg = { tone: "success" | "error" | "warning"; text: string } | null;

const TEMPLATE_TONE: Record<string, string> = {
  cold: "orange", hiring_manager: "purple", referral: "green", employee_intro: "teal",
  linkedin_note: "yellow", followup: "mint", thank_you: "red",
};

function TemplateCard({ t, contacts, onUse, delay }: { t: OutreachTemplate; contacts: RecruiterContact[]; onUse: (c: RecruiterContact, kind: OutreachKind) => void; delay: number }) {
  const [copied, setCopied] = useState(false);
  const [contactId, setContactId] = useState("");
  const tone = `var(--tone-${TEMPLATE_TONE[t.kind] ?? "green"})`;
  return (
    <Card className="lift animate-rise flex flex-col" style={{ animationDelay: `${delay}ms`, borderColor: `color-mix(in srgb, ${tone} 30%, transparent)`, backgroundImage: `radial-gradient(120% 80% at 100% 0%, color-mix(in srgb, ${tone} 14%, transparent), transparent 60%)` }}>
      <CardHeader>
        <div className="flex items-center gap-2">
          <span className="grid size-8 place-items-center rounded-lg text-[#0b0b0c]" style={{ background: tone }}><FileText className="size-4" /></span>
          <div className="min-w-0">
            <CardTitle className="text-base">{t.name}</CardTitle>
            <p className="text-xs text-muted-foreground">For: {t.audience}</p>
          </div>
        </div>
        <CardDescription>{t.description}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col gap-3">
        {t.kind !== "linkedin_note" && <p className="text-sm"><span className="text-muted-foreground">Subject: </span>{t.subject}</p>}
        <p className="flex-1 whitespace-pre-wrap rounded-xl border bg-muted/40 p-3 text-sm leading-relaxed">{t.body}</p>
        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm" variant="outline" onClick={async () => { await navigator.clipboard.writeText(t.kind === "linkedin_note" ? t.body : `Subject: ${t.subject}\n\n${t.body}`); setCopied(true); setTimeout(() => setCopied(false), 1500); }}>
            <ClipboardCopy /> {copied ? "Copied" : "Copy"}
          </Button>
          {t.kind !== "followup" && contacts.length > 0 && (
            <>
              <Select value={contactId} onChange={(e) => setContactId(e.target.value)} className="h-8 w-auto max-w-[12rem] text-xs" aria-label="Contact">
                <option value="">Use with a contact…</option>
                {contacts.filter((c) => !c.unsubscribed).map((c) => <option key={c.id} value={c.id}>{c.name} · {c.company}</option>)}
              </Select>
              <Button size="sm" disabled={!contactId} onClick={() => { const c = contacts.find((x) => x.id === contactId); if (c) onUse(c, t.kind); }}>Draft</Button>
            </>
          )}
        </div>
        {t.kind === "linkedin_note" && <p className="text-[11px] text-muted-foreground">{t.body.length}/300 characters</p>}
      </CardContent>
    </Card>
  );
}

const EMPTY = { name: "", company: "", email: "", linkedin_url: "", title: "", role: "recruiter" as ContactRole, notes: "" };

function CapMeter({ stats }: { stats: OutreachStats }) {
  const pct = stats.daily_limit ? Math.min(100, (stats.sent_today / stats.daily_limit) * 100) : 100;
  const full = stats.remaining_today === 0;
  return (
    <Card className="animate-rise p-5" style={{ borderColor: `color-mix(in srgb, var(--tone-${full ? "red" : "green"}) 30%, transparent)` }}>
      <div className="flex items-baseline justify-between">
        <p className="text-sm font-medium">Today&apos;s outreach</p>
        <p className="text-2xl font-semibold tracking-tight">{stats.sent_today}<span className="text-base text-muted-foreground">/{stats.daily_limit}</span></p>
      </div>
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-muted">
        <div className="animate-grow-x h-full rounded-full" style={{ width: `${pct}%`, background: `var(--tone-${full ? "red" : "green"})` }} />
      </div>
      <p className="mt-2 text-xs text-muted-foreground">
        {full ? "Daily cap reached. Quality beats volume; more tomorrow." : `${stats.remaining_today} left today · max 3 people per company a week`}
      </p>
    </Card>
  );
}

export default function RecruitersPage() {
  const contacts = useApi<RecruiterContact[]>("/recruiters");
  const outreach = useApi<Outreach[]>("/outreach");
  const stats = useApi<OutreachStats>("/outreach/stats");
  const tpls = useApi<OutreachTemplate[]>("/outreach/templates");
  const [tab, setTab] = useState<Tab>("queue");
  const [msg, setMsg] = useState<Msg>(null);
  const [form, setForm] = useState(EMPTY);
  const [showAdd, setShowAdd] = useState(false);
  const [csv, setCsv] = useState("");
  const [q, setQ] = useState("");
  const [source, setSource] = useState<string>("all");
  const [draftFor, setDraftFor] = useState<{ contact: RecruiterContact; kind: OutreachKind; context: string } | null>(null);

  const reload = () => { void contacts.reload(); void outreach.reload(); void stats.reload(); };
  const run = async (fn: () => Promise<unknown>, ok?: string) => {
    setMsg(null);
    try {
      await fn();
      if (ok) setMsg({ tone: "success", text: ok });
      reload();
    } catch (e) {
      setMsg({ tone: "error", text: e instanceof Error ? e.message : "Something went wrong" });
    }
  };

  const queue = useMemo(() => (outreach.data ?? []).filter((o) => o.status === "draft" || o.status === "approved"), [outreach.data]);
  const sent = useMemo(() => (outreach.data ?? []).filter((o) => !["draft", "approved", "cancelled"].includes(o.status)), [outreach.data]);
  const shown = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return (contacts.data ?? []).filter((c) => (source === "all" || c.source === source)
      && (!needle || `${c.name} ${c.company} ${c.title ?? ""} ${c.email ?? ""}`.toLowerCase().includes(needle)));
  }, [contacts.data, q, source]);

  const s = stats.data;
  const TABS: { id: Tab; label: string; count?: number }[] = [
    { id: "queue", label: "Queue", count: queue.length },
    { id: "sent", label: "Sent & replies", count: sent.length },
    { id: "contacts", label: "Contacts", count: contacts.data?.length },
    { id: "templates", label: "Email templates" },
  ];

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Recruiters & referrals"
        description="Your own contacts, truth-checked messages, and follow-ups that stop the moment someone replies. You send every message yourself."
        actions={
          <>
            <Button onClick={() => { setTab("contacts"); setShowAdd(true); }}><UserPlus /> Add contact</Button>
            <Button variant="outline" onClick={() => run(async () => {
              const r = await request<{ created: number; from_inbox: number; from_jobs: number; duplicates: number }>("/recruiters/sync", { method: "POST" });
              setMsg({ tone: "success", text: `Synced: ${r.from_inbox} new from your inbox, ${r.from_jobs} from job postings (${r.duplicates} already saved).` });
            })}><Inbox /> Sync recruiters</Button>
          </>
        }
      />
      {msg && <Notice tone={msg.tone}>{msg.text}</Notice>}

      {s && (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <CapMeter stats={s} />
          <RateKpi label="Reply rate" value={s.reply_rate} hint="Replies ÷ delivered messages" icon={Reply} tone="green" delay={40} />
          <CountKpi label="Contacts" value={s.contacts} hint={`${(contacts.data ?? []).filter((c) => c.role === "referral" || c.role === "alumni").length} referral · alumni`} icon={Users} tone="purple" delay={80} />
          <CountKpi label="Follow-ups due" value={s.followups_due.length} hint="Day 3 · 7 · 14 after sending" icon={MailCheck} tone="orange" delay={120} />
        </div>
      )}

      {s && !s.can_send_from_saige && (
        <Notice>Want Saige to send approved emails for you? <a className="font-medium underline" href="/integrations#gmail-connect">Connect Gmail with an App Password</a>. Until then, open each message in Gmail and send it yourself.</Notice>
      )}

      {s && s.followups_due.length > 0 && (
        <Card className="animate-rise">
          <CardHeader><CardTitle className="text-base">Follow-ups due</CardTitle></CardHeader>
          <CardContent className="flex flex-col gap-2">
            {s.followups_due.map((f) => (
              <div key={f.followup_id} className="flex flex-wrap items-center gap-3 rounded-xl border p-3 text-sm">
                <div className="min-w-0 flex-1">
                  <p className="font-medium">{f.contact_name} · {f.company}</p>
                  <p className="truncate text-xs text-muted-foreground">Follow-up #{f.sequence} on “{f.subject}” · due {formatDate(f.due_at)}</p>
                </div>
                <Button size="sm" onClick={() => run(async () => {
                  await request("/outreach/draft", { method: "POST", body: { contact_id: f.contact_id, kind: "followup", parent_id: f.outreach_id } });
                  await request(`/outreach/followups/${f.followup_id}/done`, { method: "POST" });
                  setTab("queue");
                }, "Follow-up drafted. Review it in the queue.")}>Draft follow-up</Button>
                <Button size="sm" variant="ghost" onClick={() => run(() => request(`/outreach/followups/${f.followup_id}/done`, { method: "POST" }))}>Skip</Button>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      <div className="flex flex-wrap gap-1 rounded-full border bg-card/60 p-1 self-start">
        {TABS.map((t) => (
          <button key={t.id} onClick={() => setTab(t.id)} className={cn("inline-flex items-center gap-2 rounded-full px-4 py-1.5 text-sm transition-colors", tab === t.id ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground")}>
            {t.label}
            {!!t.count && <span className={cn("rounded-full px-1.5 text-[11px]", tab === t.id ? "bg-black/15" : "bg-muted")}>{t.count}</span>}
          </button>
        ))}
      </div>

      {tab === "queue" && (
        <div className="flex flex-col gap-4">
          {queue.length === 0 ? (
            <Card className="flex flex-col items-center gap-3 py-12 text-center">
              <Send className="size-7 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">No messages waiting. Draft one from a contact, or use “Get a referral” on any job.</p>
            </Card>
          ) : queue.map((o, i) => <OutreachCard key={o.id + o.updated_at} item={o} onChange={reload} delay={i * 40} canSend={!!s?.can_send_from_saige} />)}
        </div>
      )}

      {tab === "sent" && (
        <div className="flex flex-col gap-4">
          {sent.length === 0 ? (
            <Card className="py-12 text-center text-sm text-muted-foreground">Nothing sent yet.</Card>
          ) : sent.map((o, i) => <OutreachCard key={o.id + o.updated_at} item={o} onChange={reload} delay={i * 40} />)}
        </div>
      )}

      {tab === "templates" && (
        <div className="flex flex-col gap-4">
          <Notice>
            Templates are filled from your verified profile. Bracketed parts like [First name] and [Company] are replaced automatically when you draft for a contact. Nothing is ever sent for you.
          </Notice>
          {!tpls.data ? <div className="skeleton h-72 rounded-3xl" /> : (
            <div className="grid gap-4 lg:grid-cols-2">
              {tpls.data.map((t, i) => (
                <TemplateCard key={t.kind} t={t} contacts={contacts.data ?? []} delay={i * 40}
                  onUse={(c, kind) => run(async () => {
                    await request("/outreach/draft", { method: "POST", body: { contact_id: c.id, kind } });
                    setTab("queue");
                  }, `Draft for ${c.name} is ready in the queue.`)} />
              ))}
            </div>
          )}
        </div>
      )}

      {tab === "contacts" && (
        <div className="grid gap-6 xl:grid-cols-3">
          <div className="flex flex-col gap-4 xl:col-span-2">
            <div className="flex flex-wrap gap-1.5">
              {[["all", "All", "green"], ["gmail", "From inbox", "red"], ["job", "From job postings", "orange"], ["manual", "Added by you", "purple"], ["csv", "CSV / LinkedIn export", "teal"]].map(([id, label, tone]) => {
                const n = id === "all" ? (contacts.data?.length ?? 0) : (contacts.data ?? []).filter((c) => c.source === id).length;
                return (
                  <button key={id} onClick={() => setSource(id)} className={cn("inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-colors", source === id ? "text-[#0b0b0c]" : "text-muted-foreground hover:text-foreground")} style={source === id ? { background: `var(--tone-${tone})`, borderColor: "transparent" } : undefined}>
                    {label} <span className="opacity-70">{n}</span>
                  </button>
                );
              })}
            </div>
            <Input placeholder="Search name, company, title, email…" value={q} onChange={(e) => setQ(e.target.value)} className="h-11 rounded-full" />
            {draftFor && (
              <Card className="animate-rise">
                <CardHeader><CardTitle className="text-base">Draft for {draftFor.contact.name}</CardTitle></CardHeader>
                <CardContent className="grid gap-3">
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Field label="Type">
                      <Select value={draftFor.kind} onChange={(e) => setDraftFor({ ...draftFor, kind: e.target.value as OutreachKind })}>
                        <option value="cold">Cold email to HR / recruiter</option>
                        <option value="hiring_manager">Email to hiring manager</option>
                        <option value="referral">Referral request (employee)</option>
                        <option value="employee_intro">Informational chat (employee)</option>
                        <option value="linkedin_note">LinkedIn connection note</option>
                        <option value="thank_you">Thank-you</option>
                      </Select>
                    </Field>
                    <Field label="How you know them (optional)"><Input value={draftFor.context} maxLength={600} placeholder="e.g. We worked together at Acme" onChange={(e) => setDraftFor({ ...draftFor, context: e.target.value })} /></Field>
                  </div>
                  <div className="flex gap-2">
                    <Button onClick={() => run(async () => {
                      await request("/outreach/draft", { method: "POST", body: { contact_id: draftFor.contact.id, kind: draftFor.kind, context: draftFor.context || null } });
                      setDraftFor(null);
                      setTab("queue");
                    }, "Draft ready in the queue.")}>Create draft</Button>
                    <Button variant="ghost" onClick={() => setDraftFor(null)}>Cancel</Button>
                  </div>
                </CardContent>
              </Card>
            )}
            {shown.length === 0 ? (
              <Card className="flex flex-col items-center gap-3 py-12 text-center">
                <Users className="size-7 text-muted-foreground" />
                <p className="text-sm text-muted-foreground">No contacts yet. Add people you know, import a CSV, or pull recruiters from your inbox.</p>
              </Card>
            ) : (
              <div className="overflow-hidden rounded-2xl border">
                <table className="w-full text-sm">
                  <thead className="bg-muted/60 text-left text-xs uppercase tracking-wide text-muted-foreground">
                    <tr><th className="px-4 py-2.5">Name</th><th className="px-4 py-2.5">Company</th><th className="hidden px-4 py-2.5 md:table-cell">Role</th><th className="hidden px-4 py-2.5 lg:table-cell">Last contacted</th><th className="px-4 py-2.5" /></tr>
                  </thead>
                  <tbody>
                    {shown.map((c) => (
                      <tr key={c.id} className="border-t transition-colors hover:bg-muted/40">
                        <td className="px-4 py-3">
                          <p className="font-medium">{c.name}</p>
                          <p className="text-xs text-muted-foreground">{c.title || c.email || c.linkedin_url || "—"}</p>
                        </td>
                        <td className="px-4 py-3"><span className="inline-flex items-center gap-1.5"><Building2 className="size-3.5 text-muted-foreground" />{c.company}</span></td>
                        <td className="hidden px-4 py-3 md:table-cell">
                          <Badge variant="outline">{ROLE_LABEL[c.role]}</Badge>
                          {c.unsubscribed && <Badge variant="muted" className="ml-1">Do not contact</Badge>}
                        </td>
                        <td className="hidden px-4 py-3 text-muted-foreground lg:table-cell">{c.last_contacted_at ? formatDateTime(c.last_contacted_at) : "Never"}</td>
                        <td className="px-4 py-3 text-right">
                          <Button size="sm" variant="outline" disabled={c.unsubscribed} onClick={() => setDraftFor({ contact: c, kind: c.role === "referral" || c.role === "alumni" ? "referral" : "cold", context: "" })}>Draft</Button>
                          <Button size="sm" variant="ghost" onClick={() => { if (confirm(`Delete ${c.name} and their message history?`)) void run(() => request(`/recruiters/${c.id}`, { method: "DELETE" })); }}>Delete</Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <div className="flex flex-col gap-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base"><UserPlus className="size-4" /> Add contact</CardTitle>
                <CardDescription>Only people you know or who contacted you. Saige never looks up or guesses email addresses.</CardDescription>
              </CardHeader>
              {(showAdd || !contacts.data?.length) && (
                <CardContent>
                  <form className="grid gap-3" onSubmit={(e) => { e.preventDefault(); void run(async () => {
                    await request("/recruiters", { method: "POST", body: { ...form, email: form.email || null, linkedin_url: form.linkedin_url || null, title: form.title || null, notes: form.notes || null } });
                    setForm(EMPTY);
                  }, "Contact added."); }}>
                    <Field label="Name *"><Input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
                    <Field label="Company *"><Input required value={form.company} onChange={(e) => setForm({ ...form, company: e.target.value })} /></Field>
                    <Field label="Email"><Input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></Field>
                    <Field label="LinkedIn URL"><Input value={form.linkedin_url} onChange={(e) => setForm({ ...form, linkedin_url: e.target.value })} /></Field>
                    <div className="grid grid-cols-2 gap-3">
                      <Field label="Title"><Input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></Field>
                      <Field label="Relationship">
                        <Select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as ContactRole })}>
                          {Object.entries(ROLE_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                        </Select>
                      </Field>
                    </div>
                    <div><Button type="submit">Save contact</Button></div>
                  </form>
                </CardContent>
              )}
              {!(showAdd || !contacts.data?.length) && <CardContent><Button variant="outline" onClick={() => setShowAdd(true)}>Open form</Button></CardContent>}
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base"><Upload className="size-4" /> Import CSV</CardTitle>
                <CardDescription>Columns: name, company, and optionally email, linkedin, title, role. LinkedIn&apos;s “Export connections” file works.</CardDescription>
              </CardHeader>
              <CardContent className="grid gap-3">
                <Textarea rows={5} value={csv} onChange={(e) => setCsv(e.target.value)} placeholder={"name,company,email\nPriya Nair,PayCo,priya@payco.com"} />
                <div className="flex flex-wrap items-center gap-2">
                  <Button disabled={!csv.trim()} onClick={() => run(async () => {
                    const r = await request<{ created: number; duplicates: number; errors: string[] }>("/recruiters/import-csv", { method: "POST", body: { csv } });
                    setCsv("");
                    setMsg({ tone: r.errors.length ? "warning" : "success", text: `Imported ${r.created}, skipped ${r.duplicates} duplicate(s)${r.errors.length ? `, ${r.errors.length} row(s) with errors: ${r.errors.slice(0, 3).join("; ")}` : ""}.` });
                  })}>Import</Button>
                  <label className="cursor-pointer text-xs font-medium hover:underline">
                    or choose a file
                    <input type="file" accept=".csv,text/csv" className="hidden" onChange={async (e) => { const f = e.target.files?.[0]; if (f) setCsv(await f.text()); }} />
                  </label>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}
