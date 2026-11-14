"use client";

import { Building2, ClipboardCopy, FileText, Inbox, MailCheck, MessageCircle, Reply, Send, Upload, UserPlus, Users } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Notice, PageHeader } from "@/components/app-shell";
import { CountKpi, RateKpi } from "@/components/kpi";
import { OutreachCard, ROLE_LABEL } from "@/components/outreach";
import { ContactsSection } from "@/components/recruiter-contacts";
import { EmailTemplatesManager } from "@/components/recruiter-templates";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input, Select, Textarea } from "@/components/ui/form";
import { useApi } from "@/hooks/use-api";
import { request } from "@/services/api";
import type { ContactRole, Outreach, OutreachKind, OutreachStats, OutreachTemplate, PagedContacts, RecruiterContact } from "@/types/api";
import { cn } from "@/utils/cn";
import { formatDate, formatDateTime } from "@/utils/format";

type Tab = "contacts" | "queue" | "sent" | "find" | "templates" | "emailtpl" | "add";
type Msg = { tone: "success" | "error" | "warning"; text: string } | null;

const TEMPLATE_TONE: Record<string, string> = {
  cold: "orange", hiring_manager: "purple", referral: "green", employee_intro: "teal",
  linkedin_note: "yellow", followup: "mint", thank_you: "red",
  wa_hr: "green", wa_referral: "green", wa_followup: "green", wa_thanks: "green",
};

function TemplateCard({ t, contacts, onUse, delay }: { t: OutreachTemplate; contacts: RecruiterContact[]; onUse: (c: RecruiterContact, kind: OutreachKind) => void; delay: number }) {
  const [copied, setCopied] = useState(false);
  const [contactId, setContactId] = useState("");
  const tone = `var(--tone-${TEMPLATE_TONE[t.kind] ?? "green"})`;
  return (
    <Card className="lift animate-rise flex flex-col" style={{ animationDelay: `${delay}ms`, borderColor: `color-mix(in srgb, ${tone} 30%, transparent)`, backgroundImage: `radial-gradient(120% 80% at 100% 0%, color-mix(in srgb, ${tone} 14%, transparent), transparent 60%)` }}>
      <CardHeader>
        <div className="flex items-center gap-2">
          <span className="grid size-8 place-items-center rounded-lg text-[#0b0b0c]" style={{ background: tone }}>{t.channel === "whatsapp" ? <MessageCircle className="size-4" /> : <FileText className="size-4" />}</span>
          <div className="min-w-0">
            <CardTitle className="text-base">{t.name}</CardTitle>
            <p className="text-xs text-muted-foreground">For: {t.audience}</p>
          </div>
        </div>
        <CardDescription>{t.description}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col gap-3">
        {t.channel === "email" && <p className="text-sm"><span className="text-muted-foreground">Subject: </span>{t.subject}</p>}
        <p className="flex-1 whitespace-pre-wrap rounded-xl border bg-muted/40 p-3 text-sm leading-relaxed">{t.body}</p>
        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm" variant="outline" onClick={async () => { await navigator.clipboard.writeText(t.kind === "linkedin_note" ? t.body : `Subject: ${t.subject}\n\n${t.body}`); setCopied(true); setTimeout(() => setCopied(false), 1500); }}>
            <ClipboardCopy /> {copied ? "Copied" : "Copy"}
          </Button>
          {t.wa_link && (
            <a href={t.wa_link} target="_blank" rel="noopener noreferrer" className="inline-flex h-8 items-center gap-1.5 rounded-full px-3.5 text-xs font-medium text-[#0b0b0c]" style={{ background: "#25D366" }}>
              <MessageCircle className="size-3.5" /> Open in WhatsApp
            </a>
          )}
          {t.channel !== "whatsapp" && t.kind !== "followup" && contacts.length > 0 && (
            <>
              <Select value={contactId} onChange={(e) => setContactId(e.target.value)} className="h-8 w-auto max-w-[12rem] text-xs" aria-label="Contact">
                <option value="">Use with a contact…</option>
                {contacts.filter((c) => !c.unsubscribed).map((c) => <option key={c.id} value={c.id}>{c.name} · {c.company}</option>)}
              </Select>
              <Button size="sm" disabled={!contactId} onClick={() => { const c = contacts.find((x) => x.id === contactId); if (c) onUse(c, t.kind as OutreachKind); }}>Draft</Button>
            </>
          )}
        </div>
        {t.kind === "linkedin_note" && <p className="text-[11px] text-muted-foreground">{t.body.length}/300 characters</p>}
      </CardContent>
    </Card>
  );
}

type Target = { company: string; sources: string[]; job_url: string | null; email_search: string;
  known: { id: string; name: string; email: string | null; phone: string | null; title: string | null }[];
  searches: { label: string; url: string }[] };

/** Who to reach at each company you're pursuing: LinkedIn people searches you open, plus contacts already known. */
function FindPeople({ onAdded }: { onAdded: () => void }) {
  const { data } = useApi<Target[]>("/recruiters/find-people");
  const [adding, setAdding] = useState<string | null>(null);
  const [form, setForm] = useState({ name: "", title: "", linkedin_url: "", email: "", phone: "" });
  const [msg, setMsg] = useState<string | null>(null);
  async function add(company: string) {
    setMsg(null);
    try {
      await request("/recruiters", { method: "POST", body: { company, name: form.name, title: form.title || null,
        linkedin_url: form.linkedin_url || null, email: form.email || null, phone: form.phone || null,
        role: /qa|test|sdet|engineer|manager/i.test(form.title) && !/hr|talent|recruit/i.test(form.title) ? "hiring_manager" : "recruiter" } });
      setAdding(null);
      setForm({ name: "", title: "", linkedin_url: "", email: "", phone: "" });
      setMsg(`Added to Contacts at ${company}.`);
      onAdded();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Could not add");
    }
  }
  return (
    <div className="flex flex-col gap-4">
      <Notice>
        For every company you&apos;ve applied to or saved, open a LinkedIn search for its HR, talent acquisition, QA managers and test leads. Pick the right person on LinkedIn,
        then add them here (paste their profile link, and their email or phone if they share it). Saige doesn&apos;t scrape LinkedIn, so your account stays safe.
      </Notice>
      {msg && <Notice tone="success">{msg}</Notice>}
      {!data ? <div className="skeleton h-72 rounded-3xl" /> : data.length === 0 ? (
        <Card className="p-8 text-center text-sm text-muted-foreground">Save or apply to jobs first; their companies appear here.</Card>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {data.map((t, i) => (
            <Card key={t.company} className="lift animate-rise" style={{ animationDelay: `${Math.min(i, 12) * 30}ms` }}>
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-base"><Building2 className="size-4" style={{ color: "var(--tone-lime)" }} /> {t.company}</CardTitle>
                <CardDescription className="capitalize">{t.sources.join(" · ")}{t.known.length ? ` · ${t.known.length} contact(s) known` : ""}</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                <div className="flex flex-wrap gap-1.5">
                  {t.searches.map((q) => (
                    <a key={q.label} href={q.url} target="_blank" rel="noopener noreferrer" className="rounded-full border px-2.5 py-1 text-xs font-medium hover:bg-muted">in · {q.label}</a>
                  ))}
                  <a href={t.email_search} target="_blank" rel="noopener noreferrer" className="rounded-full border px-2.5 py-1 text-xs hover:bg-muted">Find careers email</a>
                </div>
                {t.known.length > 0 && (
                  <ul className="flex flex-col gap-1 text-xs">
                    {t.known.slice(0, 4).map((k) => <li key={k.id} className="truncate"><b>{k.name}</b>{k.title ? ` · ${k.title}` : ""}{k.email ? ` · ${k.email}` : ""}{k.phone ? ` · ${k.phone}` : ""}</li>)}
                  </ul>
                )}
                {adding === t.company ? (
                  <form className="grid gap-2 sm:grid-cols-2" onSubmit={(e) => { e.preventDefault(); void add(t.company); }}>
                    <Input required placeholder="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
                    <Input placeholder="Title, e.g. QA Manager" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
                    <Input placeholder="LinkedIn profile URL" value={form.linkedin_url} onChange={(e) => setForm({ ...form, linkedin_url: e.target.value })} />
                    <Input type="email" placeholder="Email (if shared)" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
                    <Input placeholder="Phone (if shared)" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
                    <div className="flex gap-2"><Button type="submit" size="sm">Add contact</Button><Button type="button" size="sm" variant="ghost" onClick={() => setAdding(null)}>Cancel</Button></div>
                  </form>
                ) : (
                  <Button size="sm" variant="outline" className="w-fit" onClick={() => setAdding(t.company)}><UserPlus /> Add a person</Button>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
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
  const contactsPage = useApi<PagedContacts>("/recruiters?paged=1&page_size=100");
  const contacts = { data: contactsPage.data?.items ?? null, reload: contactsPage.reload };
  const [rev, setRev] = useState(0);
  const outreach = useApi<Outreach[]>("/outreach");
  const stats = useApi<OutreachStats>("/outreach/stats");
  const tpls = useApi<OutreachTemplate[]>("/outreach/templates");
  const [tab, setTab] = useState<Tab>("contacts");
  useEffect(() => { if (new URLSearchParams(window.location.search).get("tab") === "find") setTab("find"); }, []);
  const [msg, setMsg] = useState<Msg>(null);
  const [form, setForm] = useState(EMPTY);
  const [showAdd, setShowAdd] = useState(false);
  const [csv, setCsv] = useState("");
  async function importCsv(text: string, file?: string) {
    await run(async () => {
      setMsg({ tone: "success", text: `Importing${file ? ` ${file}` : ""}… this can take a few seconds for large files.` });
      const r = await request<{ created: number; duplicates: number; errors: string[] }>("/recruiters/import-csv", { method: "POST", body: { csv: text } });
      setCsv("");
      setMsg({ tone: r.errors.length ? "warning" : "success", text: `Imported ${r.created}, skipped ${r.duplicates} duplicate(s)${r.errors.length ? `, ${r.errors.length} row(s) with errors: ${r.errors.slice(0, 3).join("; ")}` : ""}.` });
    });
  }
  const [q, setQ] = useState("");
  const [source, setSource] = useState<string>("all");
  const [draftFor, setDraftFor] = useState<{ contact: RecruiterContact; kind: OutreachKind; context: string } | null>(null);

  const reload = () => { setRev((n) => n + 1); void contacts.reload(); void outreach.reload(); void stats.reload(); };
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
  const s = stats.data;
  const TABS: { id: Tab; label: string; count?: number }[] = [
    { id: "contacts", label: "Contacts", count: s?.contacts },
    { id: "queue", label: "Queue", count: queue.length },
    { id: "sent", label: "Sent & replies", count: sent.length },
    { id: "find", label: "Find people" },
    { id: "emailtpl", label: "Bulk email templates" },
    { id: "templates", label: "Email & WhatsApp templates" },
    { id: "add", label: "Add & import" },
  ];

  const draftSlot = draftFor ? (
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
  ) : null;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Recruiters & referrals"
        description="Your own contacts, truth-checked messages, and follow-ups that stop the moment someone replies. You send every message yourself."
        actions={
          <>
            <Button onClick={() => { setTab("add"); setShowAdd(true); }}><UserPlus /> Add contact</Button>
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
          <CountKpi label="Contacts" value={s.contacts} hint={`${Object.entries(s.contacts_by_source).map(([k, v]) => `${v} ${k}`).join(" · ")}`} icon={Users} tone="purple" delay={80} />
          <CountKpi label="Follow-ups due" value={s.followups_due.length} hint="Day 3 · 7 · 14 after sending" icon={MailCheck} tone="orange" delay={120} />
        </div>
      )}

      <div className="flex flex-wrap gap-1 rounded-full border bg-card/60 p-1 self-start">
        {TABS.map((t) => (
          <button key={t.id} onClick={() => setTab(t.id)} className={cn("inline-flex items-center gap-2 rounded-full px-4 py-1.5 text-sm transition-colors", tab === t.id ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground")}>
            {t.label}
            {!!t.count && <span className={cn("rounded-full px-1.5 text-[11px]", tab === t.id ? "bg-black/15" : "bg-muted")}>{t.count}</span>}
          </button>
        ))}
      </div>

      {tab === "contacts" && (
        <ContactsSection
        rev={rev}
        onChanged={reload}
        onDraft={(c) => setDraftFor({ contact: c, kind: c.role === "referral" || c.role === "alumni" ? "referral" : "cold", context: "" })}
        onDelete={(c) => { if (confirm(`Delete ${c.name} and their message history?`)) void run(() => request(`/recruiters/${c.id}`, { method: "DELETE" })); }}
        slot={draftSlot}
      />
      )}


      {s && (s.queued_bulk ?? 0) > 0 && (
        <Card className="animate-rise p-4">
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <span className="font-medium">{s.queued_bulk} approved emails are Ready to send tomorrow.</span>
            <span className="text-muted-foreground">{s.remaining_today} left in today&apos;s cap.</span>
            <Button size="sm" disabled={s.remaining_today === 0 || !s.can_send_from_saige} onClick={() => { if (confirm(`Send up to ${s.remaining_today} queued emails now? They were approved when you queued them.`)) void run(async () => {
              const r = await request<{ sent: number; still_queued: number }>("/recruiters/bulk/send-queued", { method: "POST", query: { confirm: "true" } });
              setMsg({ tone: "success", text: `Sent ${r.sent}; ${r.still_queued} still queued.` });
            }); }}>Send queued now</Button>
          </div>
        </Card>
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

      {tab === "find" && <FindPeople onAdded={reload} />}

      {tab === "templates" && (
        <div className="flex flex-col gap-4">
          <Notice>
            Templates are filled from your verified profile. Bracketed parts like [First name] and [Company] are replaced automatically when you draft for a contact. Emails go out only after you approve them.
          </Notice>
          {!tpls.data ? <div className="skeleton h-72 rounded-3xl" /> : (
            ([["email", "Email templates"], ["linkedin", "LinkedIn"], ["whatsapp", "WhatsApp messages"]] as const).map(([ch, title]) => {
              const list = tpls.data!.filter((t) => t.channel === ch);
              if (!list.length) return null;
              return (
                <section key={ch} className="flex flex-col gap-3">
                  <h2 className="flex items-center gap-2 text-sm font-semibold">
                    {ch === "whatsapp" ? <MessageCircle className="size-4" style={{ color: "#25D366" }} /> : <FileText className="size-4 text-muted-foreground" />} {title}
                    {ch === "whatsapp" && <span className="font-normal text-muted-foreground">· opens WhatsApp with the message ready; you pick the chat and press send</span>}
                  </h2>
                  <div className="grid gap-4 lg:grid-cols-2">
                    {list.map((t, i) => (
                      <TemplateCard key={t.kind} t={t} contacts={contacts.data ?? []} delay={i * 40}
                        onUse={(c, kind) => run(async () => {
                          await request("/outreach/draft", { method: "POST", body: { contact_id: c.id, kind } });
                          setTab("queue");
                        }, `Draft for ${c.name} is ready in the queue.`)} />
                    ))}
                  </div>
                </section>
              );
            })
          )}
        </div>
      )}

      {tab === "emailtpl" && <EmailTemplatesManager />}

      {tab === "add" && (
        <div className="grid gap-4 lg:grid-cols-2">
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
                  <Button disabled={!csv.trim()} onClick={() => importCsv(csv)}>Import</Button>
                  <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium hover:bg-muted">
                    <Upload className="size-3.5" /> Choose a CSV file (imports right away)
                    <input type="file" accept=".csv,text/csv" className="hidden" onChange={async (e) => {
                      const f = e.target.files?.[0];
                      e.target.value = "";
                      if (f) await importCsv(await f.text(), f.name);
                    }} />
                  </label>
                </div>
              </CardContent>
            </Card>
        </div>
      )}
    </div>
  );
}
