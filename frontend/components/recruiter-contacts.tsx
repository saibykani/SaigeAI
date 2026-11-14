"use client";

import { Building2, ChevronLeft, ChevronRight, Mail, Users } from "lucide-react";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";

import { Notice } from "@/components/app-shell";
import { useT } from "@/components/i18n";
import { ROLE_LABEL } from "@/components/outreach";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/form";
import { request } from "@/services/api";
import type { BulkPreview, BulkResult, CompanyCount, CompanyType, EmailTemplate, PagedContacts, RecruiterContact } from "@/types/api";
import { cn } from "@/utils/cn";
import { formatDateTime } from "@/utils/format";

const TYPES: CompanyType[] = ["service", "product", "startup", "unknown"];
const TYPE_LABEL: Record<CompanyType, string> = { service: "Service-based", product: "Product-based", startup: "Startup", unknown: "Unknown" };
const TYPE_TONE: Record<CompanyType, string> = { service: "orange", product: "green", startup: "purple", unknown: "yellow" };
const SOURCES: [string, string][] = [["", "All sources"], ["csv", "CSV / LinkedIn export"], ["manual", "Added by you"], ["gmail", "From inbox"], ["job", "From job postings"], ["portal", "From LinkedIn / Naukri"]];

type Filters = { q: string; company: string; companyType: string; hasEmail: string; contacted: string; source: string; sort: string };
const NO_FILTERS: Filters = { q: "", company: "", companyType: "", hasEmail: "", contacted: "", source: "", sort: "recent" };

/** Searchable company picker (distinct companies with contact counts, fetched as you type). */
function CompanyPicker({ value, onChange }: { value: string; onChange: (c: string) => void }) {
  const { t } = useT();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [rows, setRows] = useState<CompanyCount[]>([]);
  useEffect(() => {
    if (!open) return;
    const h = setTimeout(() => {
      request<CompanyCount[]>("/recruiters/companies", { query: { q: q || undefined, limit: 30 } }).then(setRows).catch(() => setRows([]));
    }, 200);
    return () => clearTimeout(h);
  }, [q, open]);
  return (
    <div className="relative">
      <Input
        value={open ? q : value}
        placeholder={t("All companies")}
        aria-label={t("Company")}
        className="h-9 w-48 rounded-full text-xs"
        onFocus={() => { setOpen(true); setQ(""); }}
        onChange={(e) => setQ(e.target.value)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
      />
      {open && (
        <ul className="absolute z-20 mt-1 max-h-64 w-72 overflow-auto rounded-2xl border bg-card-solid p-1 text-xs shadow-lg">
          <li><button type="button" className="w-full rounded-xl px-3 py-1.5 text-left hover:bg-muted" onMouseDown={() => { onChange(""); setOpen(false); }}>{t("All companies")}</button></li>
          {rows.map((r) => (
            <li key={r.company}>
              <button type="button" className="flex w-full items-center justify-between gap-2 rounded-xl px-3 py-1.5 text-left hover:bg-muted" onMouseDown={() => { onChange(r.company); setOpen(false); }}>
                <span className="truncate">{r.company}</span><span className="text-muted-foreground">{r.contacts}</span>
              </button>
            </li>
          ))}
          {rows.length === 0 && <li className="px-3 py-2 text-muted-foreground">{t("No matches")}</li>}
        </ul>
      )}
    </div>
  );
}

function BulkPanel({ selection, onClose, onDone }: { selection: { ids: string[] | null; filter: Record<string, unknown>; count: number }; onClose: () => void; onDone: (r: BulkResult) => void }) {
  const { t } = useT();
  const [templates, setTemplates] = useState<EmailTemplate[]>([]);
  const [templateId, setTemplateId] = useState("builtin:application");
  const [preview, setPreview] = useState<BulkPreview | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const body = useCallback(() => (selection.ids ? { template_id: templateId, contact_ids: selection.ids } : { template_id: templateId, filter: selection.filter }), [selection, templateId]);
  useEffect(() => { request<EmailTemplate[]>("/recruiters/email-templates").then(setTemplates).catch(() => undefined); }, []);
  useEffect(() => {
    setPreview(null);
    setErr(null);
    request<BulkPreview>("/recruiters/bulk/preview", { method: "POST", body: body() }).then(setPreview).catch((e) => setErr(e instanceof Error ? e.message : "Could not preview"));
  }, [body]);
  async function send() {
    if (!preview) return;
    const ok = window.confirm(t("Send {n} email(s) now from your Gmail and save {m} for tomorrow? You approve every email in this preview.", { n: preview.send_now, m: preview.queued }));
    if (!ok) return;
    setBusy(true);
    setErr(null);
    try {
      onDone(await request<BulkResult>("/recruiters/bulk/send", { method: "POST", body: { ...body(), confirm: true } }));
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not send");
    } finally {
      setBusy(false);
    }
  }
  const q = preview?.quota;
  return (
    <Card className="animate-rise">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base"><Mail className="size-4" /> {t("Email {n} contact(s)", { n: selection.count })}</CardTitle>
        <CardDescription>{t("Each email is filled only from your verified profile. Nothing is sent until you confirm.")}</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <Select value={templateId} onChange={(e) => setTemplateId(e.target.value)} className="h-9 w-auto max-w-xs text-xs" aria-label={t("Email template")}>
            {templates.map((x) => <option key={x.id} value={x.id}>{x.name}{x.builtin ? "" : " *"}</option>)}
          </Select>
          {preview?.attach_resume && <Badge variant="outline">{t("Resume attached")}</Badge>}
        </div>
        {err && <Notice tone="error">{err}</Notice>}
        {!preview && !err && <div className="skeleton h-24 rounded-2xl" />}
        {preview && q && (
          <>
            <div className="rounded-2xl border bg-muted/40 p-3 text-sm">
              <p>{t("Today: {sent}/{limit} sent · {left} left. Max {co} per company a week.", { sent: q.sent_today, limit: q.daily_limit, left: q.remaining_today, co: q.per_company_weekly_cap })}</p>
              <p className="mt-1 font-medium">{t("{n} will be sent now · {m} saved as Ready to send tomorrow · {s} skipped", { n: preview.send_now, m: preview.queued, s: preview.skipped_count })}</p>
              {preview.selected >= preview.max_per_action && <p className="mt-1 text-xs text-muted-foreground">{t("Up to {n} contacts are handled per action.", { n: preview.max_per_action })}</p>}
            </div>
            {preview.paused && <Notice tone="warning">{t("Recruiter outreach is paused in Automation settings.")}</Notice>}
            {!q.can_send_from_saige && <Notice>{t("Connect Gmail with an App Password in Integrations so Saige can send for you.")}</Notice>}
            <div className="flex flex-col gap-2">
              {preview.previews.map((p) => (
                <div key={p.contact_id} className="rounded-xl border p-3 text-sm">
                  <button type="button" className="flex w-full items-center justify-between gap-2 text-left" onClick={() => setOpen(open === p.contact_id ? null : p.contact_id)}>
                    <span className="min-w-0 truncate"><b>{p.name}</b> · {p.company} · <span className="text-muted-foreground">{p.to}</span></span>
                    <Badge variant="outline">{p.send_now ? t("Now") : t("Tomorrow")}</Badge>
                  </button>
                  {open === p.contact_id && (
                    <div className="mt-2 text-xs"><p className="font-medium">{p.subject}</p><p className="mt-1 whitespace-pre-wrap text-muted-foreground">{p.body}</p></div>
                  )}
                </div>
              ))}
              {preview.eligible > preview.previews.length && <p className="text-xs text-muted-foreground">{t("Showing {n} of {m} emails.", { n: preview.previews.length, m: preview.eligible })}</p>}
            </div>
            {preview.skipped.length > 0 && (
              <details className="text-xs text-muted-foreground">
                <summary className="cursor-pointer">{t("{n} skipped", { n: preview.skipped_count })}</summary>
                <ul className="mt-1 list-disc pl-5">{preview.skipped.slice(0, 10).map((s) => <li key={s.contact_id}>{s.name} · {s.company}: {s.reason}</li>)}</ul>
              </details>
            )}
          </>
        )}
        <div className="flex gap-2">
          <Button disabled={busy || !preview || preview.eligible === 0 || preview.paused} onClick={send}>{busy ? t("Sending…") : t("Approve and send")}</Button>
          <Button variant="ghost" onClick={onClose}>{t("Cancel")}</Button>
        </div>
      </CardContent>
    </Card>
  );
}

export function ContactsSection({ rev, onChanged, onDraft, onDelete, slot }: {
  rev: number; onChanged: () => void; onDraft: (c: RecruiterContact) => void; onDelete: (c: RecruiterContact) => void; slot?: ReactNode;
}) {
  const { t } = useT();
  const [f, setF] = useState<Filters>(NO_FILTERS);
  const [qInput, setQInput] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [data, setData] = useState<PagedContacts | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [allMatching, setAllMatching] = useState(false);
  const [bulk, setBulk] = useState(false);
  const [result, setResult] = useState<BulkResult | null>(null);
  const seq = useRef(0);

  useEffect(() => { const h = setTimeout(() => { setF((x) => (x.q === qInput ? x : { ...x, q: qInput })); setPage(1); }, 300); return () => clearTimeout(h); }, [qInput]);

  const filterBody = {
    q: f.q || null, company: f.company || null, company_type: f.companyType || null,
    has_email: f.hasEmail ? f.hasEmail === "yes" : null, contacted: f.contacted ? f.contacted === "yes" : null, source: f.source || null,
  };

  useEffect(() => {
    const n = ++seq.current;
    request<PagedContacts>("/recruiters", {
      query: { paged: 1, page, page_size: pageSize, sort: f.sort, q: f.q || undefined, company: f.company || undefined, company_type: f.companyType || undefined,
        has_email: f.hasEmail ? f.hasEmail === "yes" : undefined, contacted: f.contacted ? f.contacted === "yes" : undefined, source: f.source || undefined },
    }).then((d) => { if (n === seq.current) { setData(d); setError(null); } }).catch((e) => { if (n === seq.current) setError(e instanceof Error ? e.message : "Could not load contacts"); });
  }, [f, page, pageSize, rev]);

  const setFilter = (patch: Partial<Filters>) => { setF((x) => ({ ...x, ...patch })); setPage(1); setPicked(new Set()); setAllMatching(false); };
  const items = data?.items ?? [];
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;
  const pageAllPicked = items.length > 0 && items.every((c) => picked.has(c.id));
  const count = allMatching ? Math.min(data?.total ?? 0, 200) : picked.size;
  const toggle = (id: string) => { setAllMatching(false); setPicked((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n; }); };
  const togglePage = () => { setAllMatching(false); setPicked((s) => { const n = new Set(s); items.forEach((c) => (pageAllPicked ? n.delete(c.id) : n.add(c.id))); return n; }); };
  const setType = async (c: RecruiterContact, v: string) => {
    try { await request(`/recruiters/${c.id}`, { method: "PATCH", body: { company_type: v === "auto" ? null : v } }); onChanged(); } catch { /* shown on reload */ }
  };

  return (
    <section className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="flex items-center gap-2 text-lg font-semibold"><Users className="size-5" style={{ color: "var(--tone-purple)" }} /> {t("Contacts")}</h2>
        {data && <span className="text-sm text-muted-foreground">{t("{n} contacts", { n: data.total })}</span>}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Input placeholder={t("Search name, company, email…")} value={qInput} onChange={(e) => setQInput(e.target.value)} className="h-9 w-64 rounded-full text-xs" />
        <CompanyPicker value={f.company} onChange={(company) => setFilter({ company })} />
        <Select value={f.companyType} onChange={(e) => setFilter({ companyType: e.target.value })} className="h-9 w-auto rounded-full text-xs" aria-label={t("Company type")}>
          <option value="">{t("All types")}</option>
          {TYPES.map((x) => <option key={x} value={x}>{t(TYPE_LABEL[x])}</option>)}
        </Select>
        <Select value={f.hasEmail} onChange={(e) => setFilter({ hasEmail: e.target.value })} className="h-9 w-auto rounded-full text-xs" aria-label={t("Email")}>
          <option value="">{t("Any email")}</option><option value="yes">{t("With email")}</option><option value="no">{t("No email")}</option>
        </Select>
        <Select value={f.contacted} onChange={(e) => setFilter({ contacted: e.target.value })} className="h-9 w-auto rounded-full text-xs" aria-label={t("Contacted")}>
          <option value="">{t("Any status")}</option><option value="yes">{t("Contacted")}</option><option value="no">{t("Not contacted yet")}</option>
        </Select>
        <Select value={f.source} onChange={(e) => setFilter({ source: e.target.value })} className="h-9 w-auto rounded-full text-xs" aria-label={t("Source")}>
          {SOURCES.map(([id, label]) => <option key={id} value={id}>{t(label)}</option>)}
        </Select>
        <Select value={f.sort} onChange={(e) => setFilter({ sort: e.target.value })} className="h-9 w-auto rounded-full text-xs" aria-label={t("Sort")}>
          <option value="recent">{t("Recently added")}</option><option value="name">{t("Name")}</option><option value="company">{t("Company")}</option>
        </Select>
        {(f.q || f.company || f.companyType || f.hasEmail || f.contacted || f.source) && (
          <Button size="sm" variant="ghost" onClick={() => { setQInput(""); setF(NO_FILTERS); setPage(1); }}>{t("Clear filters")}</Button>
        )}
      </div>

      {count > 0 && !bulk && (
        <div className="flex flex-wrap items-center gap-3 rounded-2xl border bg-card/60 px-4 py-2.5 text-sm">
          <span className="font-medium">{t("{n} selected", { n: count })}</span>
          {!allMatching && data && data.total > items.length && pageAllPicked && (
            <Button size="sm" variant="outline" onClick={() => setAllMatching(true)}>{t("Select all {n} matching", { n: Math.min(data.total, 200) })}</Button>
          )}
          <Button size="sm" onClick={() => { setResult(null); setBulk(true); }}><Mail /> {t("Email selected")}</Button>
          <Button size="sm" variant="ghost" onClick={() => { setPicked(new Set()); setAllMatching(false); }}>{t("Clear")}</Button>
        </div>
      )}
      {result && (
        <Notice tone={result.failed ? "warning" : "success"}>
          {t("{n} sent · {m} saved for tomorrow · {f} failed · {s} skipped", { n: result.sent, m: result.queued, f: result.failed, s: result.skipped_count })}
        </Notice>
      )}
      {bulk && count > 0 && (
        <BulkPanel
          selection={{ ids: allMatching ? null : [...picked], filter: filterBody, count }}
          onClose={() => setBulk(false)}
          onDone={(r) => { setBulk(false); setResult(r); setPicked(new Set()); setAllMatching(false); onChanged(); }}
        />
      )}
      {slot}
      {error && <Notice tone="error">{error}</Notice>}

      {!data ? <div className="skeleton h-72 rounded-3xl" /> : items.length === 0 ? (
        <Card className="flex flex-col items-center gap-3 py-12 text-center">
          <Users className="size-7 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">{t("No contacts match. Change the filters, add people you know, or import a CSV.")}</p>
        </Card>
      ) : (
        <div className="overflow-x-auto rounded-2xl border">
          <table className="w-full text-sm">
            <thead className="bg-muted/60 text-left text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="w-10 px-4 py-2.5"><input type="checkbox" checked={pageAllPicked} onChange={togglePage} aria-label={t("Select page")} /></th>
                <th className="px-4 py-2.5">{t("Name")}</th><th className="px-4 py-2.5">{t("Company")}</th>
                <th className="hidden px-4 py-2.5 md:table-cell">{t("Company type")}</th>
                <th className="hidden px-4 py-2.5 lg:table-cell">{t("Last contacted")}</th><th className="px-4 py-2.5" />
              </tr>
            </thead>
            <tbody>
              {items.map((c) => {
                const type = c.company_type ?? "unknown";
                return (
                  <tr key={c.id} className="border-t transition-colors hover:bg-muted/40">
                    <td className="px-4 py-3"><input type="checkbox" checked={allMatching || picked.has(c.id)} onChange={() => toggle(c.id)} aria-label={c.name} /></td>
                    <td className="px-4 py-3">
                      <p className="font-medium">{c.name}</p>
                      <p className="text-xs text-muted-foreground">{c.title || c.email || c.linkedin_url || "—"}</p>
                      <span className="mt-1 flex flex-wrap gap-1.5 text-[11px]">
                        {c.email && <a href={`mailto:${c.email}`} className="rounded-full border px-2 py-0.5 hover:bg-muted">✉ {c.email}</a>}
                        {c.phone && <a href={`tel:${c.phone}`} className="rounded-full border px-2 py-0.5 hover:bg-muted">☎ {c.phone}</a>}
                        {c.linkedin_url && <a href={c.linkedin_url} target="_blank" rel="noopener noreferrer" className="rounded-full border px-2 py-0.5 hover:bg-muted">LinkedIn</a>}
                      </span>
                    </td>
                    <td className="px-4 py-3"><span className="inline-flex items-center gap-1.5"><Building2 className="size-3.5 text-muted-foreground" />{c.company}</span></td>
                    <td className="hidden px-4 py-3 md:table-cell">
                      <Select value={c.company_type_custom ? type : "auto"} onChange={(e) => void setType(c, e.target.value)} aria-label={t("Company type")}
                        className="h-8 w-auto rounded-full text-xs" style={{ color: `var(--tone-${TYPE_TONE[type]})` }}>
                        <option value="auto">{t(TYPE_LABEL[type])}{c.company_type_custom ? "" : ` (${t("auto")})`}</option>
                        {TYPES.map((x) => <option key={x} value={x}>{t(TYPE_LABEL[x])}</option>)}
                      </Select>
                      <div className="mt-1 flex gap-1"><Badge variant="outline">{ROLE_LABEL[c.role]}</Badge>{c.unsubscribed && <Badge variant="muted">{t("Do not contact")}</Badge>}</div>
                    </td>
                    <td className="hidden px-4 py-3 text-muted-foreground lg:table-cell">{c.last_contacted_at ? formatDateTime(c.last_contacted_at) : t("Never")}</td>
                    <td className="px-4 py-3 text-right">
                      <Button size="sm" variant="outline" disabled={c.unsubscribed} onClick={() => onDraft(c)}>{t("Draft")}</Button>
                      <Button size="sm" variant="ghost" onClick={() => onDelete(c)}>{t("Delete")}</Button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {data && data.total > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            {t("Per page")}
            <Select value={pageSize} onChange={(e) => { setPageSize(Number(e.target.value)); setPage(1); }} className="h-8 w-auto rounded-full text-xs">
              {[25, 50, 100].map((n) => <option key={n} value={n}>{n}</option>)}
            </Select>
          </label>
          <div className={cn("flex items-center gap-2")}>
            <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage(page - 1)} aria-label={t("Previous")}><ChevronLeft /></Button>
            <span className="text-xs text-muted-foreground">{t("Page {n} of {m}", { n: page, m: pages })}</span>
            <Button size="sm" variant="outline" disabled={page >= pages} onClick={() => setPage(page + 1)} aria-label={t("Next")}><ChevronRight /></Button>
          </div>
        </div>
      )}
    </section>
  );
}
