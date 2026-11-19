"use client";

import { BarChart3, ExternalLink, Link2, MailCheck, Table2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { useT } from "@/components/i18n";
import { CountKpi, RateKpi } from "@/components/kpi";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useApi } from "@/hooks/use-api";
import { request } from "@/services/api";
import type { EmailTrackingStats, SentEmail, SentEmailPage, TrackingGroup } from "@/types/api";
import { cn } from "@/utils/cn";
import { formatDateTime } from "@/utils/format";

const KINDS = ["outreach", "bulk", "apply", "auto_apply", "thank_you"] as const;
const KIND_LABEL: Record<string, string> = { outreach: "Outreach", bulk: "Bulk", apply: "Application", auto_apply: "Auto-apply", thank_you: "Thank-you" };
const PAGE = 20;

function fmtHours(h: number | null) {
  if (h == null) return "-";
  return h < 48 ? `${h}h` : `${Math.round(h / 24)}d`;
}

function Chip({ s }: { s: SentEmail }) {
  const { t } = useT();
  const tone = s.status === "replied" ? "var(--tone-green)" : s.status === "bounced" ? "var(--tone-red)" : "var(--muted-foreground)";
  const label = s.status === "replied" ? `${t("Replied")}${s.reply_category ? ` · ${s.reply_category}` : ""}` : s.status === "bounced" ? t("Bounced") : t("Sent");
  return <span className="inline-flex rounded-full border px-2 py-0.5 text-xs" style={{ color: tone, borderColor: `color-mix(in srgb, ${tone} 40%, transparent)` }}>{label}</span>;
}

function TemplateChart({ rows }: { rows: TrackingGroup[] }) {
  const { t } = useT();
  const [table, setTable] = useState(false);
  const data = rows.slice(0, 8).map((r) => ({ name: r.key, sent: r.sent, replies: r.replies, interviews: r.interviews }));
  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between gap-2">
        <div>
          <CardTitle className="text-lg">{t("Templates that get answers")}</CardTitle>
          <CardDescription>{t("Replies need at least 5 sends before they can be compared.")}</CardDescription>
        </div>
        {rows.length > 0 && (
          <Button variant="outline" size="sm" onClick={() => setTable(!table)}>{table ? <BarChart3 /> : <Table2 />}{table ? t("Chart view") : t("Table view")}</Button>
        )}
      </CardHeader>
      <CardContent>
        {rows.length === 0 ? <p className="py-6 text-center text-sm text-muted-foreground">{t("No emails tracked yet. Send an email from Saige, then sync Gmail.")}</p> : table ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="text-left text-muted-foreground">
                <th className="py-1.5 font-medium">{t("Template")}</th><th className="py-1.5 text-right font-medium">{t("Sent")}</th>
                <th className="py-1.5 text-right font-medium">{t("Replies")}</th><th className="py-1.5 text-right font-medium">{t("Rate")}</th>
                <th className="py-1.5 text-right font-medium">{t("Interviews")}</th>
              </tr></thead>
              <tbody>{rows.map((r) => (
                <tr key={r.key} className="border-t">
                  <td className="py-1.5">{r.key}</td><td className="py-1.5 text-right tabular-nums">{r.sent}</td>
                  <td className="py-1.5 text-right tabular-nums">{r.replies}</td>
                  <td className="py-1.5 text-right tabular-nums">{r.rate == null ? "-" : `${r.rate}%`}{!r.enough_data && <span className="ml-1 text-xs text-muted-foreground">({t("too few sends")})</span>}</td>
                  <td className="py-1.5 text-right tabular-nums">{r.interviews}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        ) : (
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
                <CartesianGrid vertical={false} stroke="var(--grid)" />
                <XAxis dataKey="name" tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} axisLine={false} tickLine={false} interval={0} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} axisLine={false} tickLine={false} />
                <Tooltip cursor={{ fill: "var(--muted)" }} contentStyle={{ background: "var(--card-solid)", border: "1px solid var(--border)", borderRadius: 12, fontSize: 12 }}
                  labelStyle={{ color: "var(--foreground)", fontWeight: 600 }} />
                <Legend wrapperStyle={{ fontSize: 12, color: "var(--muted-foreground)" }} />
                <Bar dataKey="sent" name={t("Sent")} fill="var(--chart-2)" radius={[6, 6, 0, 0]} maxBarSize={28} />
                <Bar dataKey="replies" name={t("Replies")} fill="var(--chart-3)" radius={[6, 6, 0, 0]} maxBarSize={28} />
                <Bar dataKey="interviews" name={t("Interviews")} fill="var(--chart-1)" radius={[6, 6, 0, 0]} maxBarSize={28} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function Breakdown({ title, rows, label }: { title: string; rows: TrackingGroup[]; label?: (k: string) => string }) {
  const { t } = useT();
  return (
    <Card>
      <CardHeader><CardTitle className="text-base">{title}</CardTitle></CardHeader>
      <CardContent>
        {rows.length === 0 ? <p className="text-sm text-muted-foreground">-</p> : (
          <table className="w-full text-sm">
            <thead><tr className="text-left text-muted-foreground"><th className="py-1 font-medium" /><th className="py-1 text-right font-medium">{t("Sent")}</th><th className="py-1 text-right font-medium">{t("Replies")}</th><th className="py-1 text-right font-medium">{t("Rate")}</th></tr></thead>
            <tbody>{rows.map((r) => (
              <tr key={r.key} className="border-t">
                <td className="py-1">{label ? label(String(r.key)) : r.key}</td><td className="py-1 text-right tabular-nums">{r.sent}</td>
                <td className="py-1 text-right tabular-nums">{r.replies}</td>
                <td className={cn("py-1 text-right tabular-nums", !r.enough_data && "text-muted-foreground")}>{r.rate == null ? "-" : `${r.rate}%`}{!r.enough_data && "*"}</td>
              </tr>
            ))}</tbody>
          </table>
        )}
      </CardContent>
    </Card>
  );
}

function SentRow({ s }: { s: SentEmail }) {
  const { t } = useT();
  const [open, setOpen] = useState(false);
  return (
    <li className="border-t py-2.5 first:border-t-0">
      <button type="button" className="flex w-full flex-wrap items-center gap-x-3 gap-y-1 text-left" onClick={() => setOpen(!open)} aria-expanded={open}>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium">{s.subject || "-"}</span>
          <span className="block truncate text-xs text-muted-foreground">{s.to_email}{s.company ? ` · ${s.company}` : ""} · {t(KIND_LABEL[s.kind] ?? s.kind)}{s.template_name ? ` · ${s.template_name}` : ""}</span>
        </span>
        <span className="text-xs text-muted-foreground">{formatDateTime(s.sent_at)}</span>
        <Chip s={s} />
      </button>
      {open && (
        <div className="mt-2 rounded-2xl bg-muted/50 p-3 text-sm">
          {s.reply_snippet ? <p className="whitespace-pre-line">{s.reply_snippet}</p> : <p className="text-muted-foreground">{t("No reply yet.")}</p>}
          {s.replied_at && <p className="mt-1 text-xs text-muted-foreground">{formatDateTime(s.replied_at)}</p>}
          {s.gmail_url && (
            <a href={s.gmail_url} target="_blank" rel="noreferrer" className="mt-2 inline-flex items-center gap-1 text-xs underline"><ExternalLink className="size-3" />{t("Open in Gmail")}</a>
          )}
        </div>
      )}
    </li>
  );
}

const sel = "h-9 rounded-xl border bg-background px-3 text-sm";

export function EmailTrackingView() {
  const { t } = useT();
  const stats = useApi<EmailTrackingStats>("/email-tracking/stats");
  const [kind, setKind] = useState("");
  const [status, setStatus] = useState("");
  const [company, setCompany] = useState("");
  const [template, setTemplate] = useState("");
  const [page, setPage] = useState(1);
  const qs = new URLSearchParams({ page: String(page), page_size: String(PAGE) });
  if (kind) qs.set("kind", kind);
  if (status) qs.set("status", status);
  if (company.trim()) qs.set("company", company.trim());
  if (template) qs.set("template", template);
  const list = useApi<SentEmailPage>(`/email-tracking/sent?${qs.toString()}`);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const s = stats.data;
  const pages = Math.max(1, Math.ceil((list.data?.total ?? 0) / PAGE));

  async function backfill() {
    setBusy(true);
    try {
      const r = await request<{ recorded: number; linked: number }>("/email-tracking/backfill", { method: "POST" });
      setMsg(t("Linked {n} past replies.", { n: r.linked }));
      stats.reload();
      list.reload();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : t("Request failed"));
    } finally {
      setBusy(false);
    }
  }
  const reset = (fn: (v: string) => void) => (e: React.ChangeEvent<HTMLSelectElement | HTMLInputElement>) => { fn(e.target.value); setPage(1); };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-muted-foreground">{t("Replies are matched from your own Gmail sync. Nothing is added to your emails: no tracking pixels or rewritten links.")}</p>
        <Button variant="outline" size="sm" disabled={busy} onClick={backfill}><Link2 />{t("Link past replies")}</Button>
      </div>
      {msg && <p className="text-sm text-muted-foreground" role="status">{msg}</p>}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <CountKpi label={t("Sent")} value={s?.sent ?? 0} icon={MailCheck} tone="orange" />
        <CountKpi label={t("Replied")} value={s?.replied ?? 0} icon={MailCheck} tone="green" />
        <RateKpi label={t("Reply rate")} value={s?.reply_rate ?? null} icon={MailCheck} tone="purple" />
        <Card className="flex flex-col justify-center gap-1 p-4"><span className="text-xs text-muted-foreground">{t("Median reply time")}</span><span className="text-3xl tabular-nums">{fmtHours(s?.median_reply_hours ?? null)}</span></Card>
        <CountKpi label={t("Bounced")} value={s?.bounced ?? 0} icon={MailCheck} tone="red" />
      </div>
      <TemplateChart rows={s?.by_template ?? []} />
      <div className="grid gap-4 lg:grid-cols-3">
        <Breakdown title={t("By type")} rows={s?.by_kind ?? []} label={(k) => t(KIND_LABEL[k] ?? k)} />
        <Breakdown title={t("By day sent")} rows={s?.by_weekday ?? []} />
        <Breakdown title={t("By company domain")} rows={s?.by_domain ?? []} />
      </div>
      <p className="text-xs text-muted-foreground">* {t("Fewer than 5 sends: too early to say what works.")}</p>
      <Card>
        <CardHeader className="gap-3">
          <CardTitle className="text-lg">{t("Sent emails")}</CardTitle>
          <div className="flex flex-wrap gap-2">
            <select className={sel} aria-label={t("Type")} value={kind} onChange={reset(setKind)}>
              <option value="">{t("All types")}</option>{KINDS.map((k) => <option key={k} value={k}>{t(KIND_LABEL[k])}</option>)}
            </select>
            <select className={sel} aria-label={t("Status")} value={status} onChange={reset(setStatus)}>
              <option value="">{t("All statuses")}</option>
              <option value="sent">{t("Sent")}</option><option value="replied">{t("Replied")}</option><option value="bounced">{t("Bounced")}</option>
            </select>
            <select className={sel} aria-label={t("Template")} value={template} onChange={reset(setTemplate)}>
              <option value="">{t("All templates")}</option>{(s?.by_template ?? []).map((r) => <option key={r.key} value={String(r.key)}>{r.key}</option>)}
            </select>
            <input className={cn(sel, "w-44")} placeholder={t("Company")} aria-label={t("Company")} value={company} onChange={reset(setCompany)} />
          </div>
        </CardHeader>
        <CardContent>
          {(list.data?.items.length ?? 0) === 0 ? <p className="py-6 text-center text-sm text-muted-foreground">{t("No emails tracked yet. Send an email from Saige, then sync Gmail.")}</p> : (
            <ul>{list.data!.items.map((e) => <SentRow key={e.id} s={e} />)}</ul>
          )}
          {pages > 1 && (
            <div className="mt-3 flex items-center justify-between text-sm">
              <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>{t("Previous")}</Button>
              <span className="text-muted-foreground">{page} / {pages}</span>
              <Button variant="outline" size="sm" disabled={page >= pages} onClick={() => setPage(page + 1)}>{t("Next")}</Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

/** Small dashboard card: totals and a link to the full view. */
export function EmailTrackingCard() {
  const { t } = useT();
  const { data } = useApi<EmailTrackingStats>("/email-tracking/stats");
  if (!data || data.sent === 0) return null;
  const top = data.by_template.find((r) => r.enough_data && r.replies > 0);
  return (
    <Card className="animate-rise">
      <CardHeader className="flex-row items-center justify-between">
        <CardTitle className="text-lg">{t("Email replies")}</CardTitle>
        <Link href="/recruiters?tab=tracking" className="text-xs underline">{t("View details")}</Link>
      </CardHeader>
      <CardContent className="flex flex-col gap-1 text-sm">
        <p><span className="text-2xl tabular-nums">{data.replied}</span> / {data.sent} {t("replied")}{data.reply_rate != null && ` · ${data.reply_rate}%`}</p>
        <p className="text-muted-foreground">{t("Median reply time")}: {fmtHours(data.median_reply_hours)} · {t("Bounced")}: {data.bounced}</p>
        {top && <p className="text-muted-foreground">{t("Best template so far")}: {top.key} ({top.rate}%, {top.sent} {t("sent")})</p>}
      </CardContent>
    </Card>
  );
}
