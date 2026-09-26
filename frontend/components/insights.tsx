"use client";

import { Building2, Globe2, Inbox, MapPin, Send, Target, Users, Zap } from "lucide-react";
import Link from "next/link";

import { CountUp } from "@/components/motion";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useApi } from "@/hooks/use-api";
import { humanStatus } from "@/utils/format";

type Row = { label: string; count: number };
export type Insights = {
  applications_by_status: Row[]; jobs_by_source: Row[]; match_distribution: Row[]; top_companies: Row[]; inbox: Row[];
  contacts_by_source: Row[];
  feed: { total: number; country: number; remote: number; walk_in: number; strong: number; avg_score: number | null;
    top_locations: Row[]; top_companies: Row[]; by_source: Row[]; country_name: string | null; roles: string[] };
};

/** A ranked list with one-hue bars (values stay in text ink). */
function Bars({ rows, tone, format = (s: string) => s, empty }: { rows: Row[]; tone: string; format?: (s: string) => string; empty: string }) {
  if (!rows.length) return <p className="py-4 text-center text-sm text-muted-foreground">{empty}</p>;
  const max = Math.max(...rows.map((r) => r.count), 1);
  return (
    <ul className="flex flex-col gap-2">
      {rows.slice(0, 7).map((r, i) => (
        <li key={r.label} className="grid grid-cols-[minmax(0,8.5rem)_1fr_2.5rem] items-center gap-3 text-sm" title={`${format(r.label)}: ${r.count}`}>
          <span className="truncate capitalize">{format(r.label)}</span>
          <span className="h-2.5 overflow-hidden rounded-full bg-muted">
            <span className="animate-grow-x block h-full rounded-full" style={{ width: `${Math.max(4, (r.count / max) * 100)}%`, background: `var(--tone-${tone})`, animationDelay: `${i * 50}ms` }} />
          </span>
          <span className="text-right tabular-nums">{r.count}</span>
        </li>
      ))}
    </ul>
  );
}

function Panel({ title, icon: Icon, tone, href, children }: { title: string; icon: typeof Zap; tone: string; href?: string; children: React.ReactNode }) {
  return (
    <Card className="lift animate-rise" style={{ borderColor: `color-mix(in srgb, var(--tone-${tone}) 26%, transparent)` }}>
      <CardHeader className="flex-row items-center justify-between pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <span className="grid size-7 place-items-center rounded-lg text-[#0b0b0c]" style={{ background: `var(--tone-${tone})` }}><Icon className="size-3.5" /></span>
          {title}
        </CardTitle>
        {href && <Link href={href} className="text-xs text-muted-foreground hover:text-foreground">Open →</Link>}
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

function Stat({ label, value, tone }: { label: string; value: number | string | null; tone: string }) {
  return (
    <div className="rounded-2xl border p-3" style={{ borderColor: `color-mix(in srgb, var(--tone-${tone}) 30%, transparent)` }}>
      <p className="text-2xl font-semibold tabular-nums" style={{ color: `var(--tone-${tone})` }}>
        {typeof value === "number" ? <CountUp value={value} /> : value ?? "—"}
      </p>
      <p className="text-xs text-muted-foreground">{label}</p>
    </div>
  );
}

/** Pipeline + market insights that are useful from day one (no sent applications needed). */
export function InsightsGrid({ compact = false }: { compact?: boolean }) {
  const { data } = useApi<Insights>("/analytics/insights");
  if (!data) return <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{[0, 1, 2].map((i) => <div key={i} className="skeleton h-56 rounded-3xl" />)}</div>;
  const f = data.feed;
  return (
    <div className="flex flex-col gap-4">
      <Panel title={`Market for ${f.roles.slice(0, 2).join(", ") || "your roles"}${f.country_name ? ` · ${f.country_name}` : ""}`} icon={Globe2} tone="orange" href="/jobs">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <Stat label="Open jobs found" value={f.total} tone="orange" />
          <Stat label={`In ${f.country_name ?? "your country"}`} value={f.country} tone="green" />
          <Stat label="Remote" value={f.remote} tone="teal" />
          <Stat label="Strong matches (80%+)" value={f.strong} tone="yellow" />
          <Stat label="Walk-in drives" value={f.walk_in} tone="red" />
          <Stat label="Average match" value={f.avg_score != null ? `${f.avg_score}%` : null} tone="purple" />
        </div>
      </Panel>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <Panel title="Where jobs are" icon={MapPin} tone="green" href="/jobs"><Bars rows={f.top_locations} tone="green" empty="Open Jobs to fetch jobs for your roles." /></Panel>
        <Panel title="Companies hiring for you" icon={Building2} tone="purple" href="/jobs"><Bars rows={f.top_companies} tone="purple" empty="No jobs fetched yet." /></Panel>
        <Panel title="Applications by stage" icon={Send} tone="yellow" href="/applications"><Bars rows={data.applications_by_status} tone="yellow" format={humanStatus} empty="No applications yet." /></Panel>
        {!compact && <Panel title="Saved jobs by match" icon={Target} tone="mint" href="/jobs"><Bars rows={data.match_distribution} tone="mint" format={(s) => `${s}%`} empty="No saved jobs yet." /></Panel>}
        {!compact && <Panel title="Saved jobs by source" icon={Zap} tone="orange" href="/jobs"><Bars rows={data.jobs_by_source} tone="orange" empty="No saved jobs yet." /></Panel>}
        {!compact && <Panel title="Companies you applied to" icon={Building2} tone="lime" href="/applications"><Bars rows={data.top_companies} tone="lime" empty="No applications yet." /></Panel>}
        <Panel title="Inbox by type" icon={Inbox} tone="teal" href="/inbox"><Bars rows={data.inbox} tone="teal" empty="Connect Gmail to classify your job email." /></Panel>
        {!compact && <Panel title="Recruiters by source" icon={Users} tone="red" href="/recruiters"><Bars rows={data.contacts_by_source} tone="red" empty="Sync recruiters to collect HR contacts." /></Panel>}
      </div>
    </div>
  );
}
