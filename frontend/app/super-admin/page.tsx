"use client";

import Link from "next/link";
import { useEffect } from "react";

import { BarList, DataChart, Err, KpiCard, Panel, Spark, heat, num, shortDay, useAdmin, fmt, type Kpi } from "@/components/super-admin";
import { useApi } from "@/hooks/use-api";

type Overview = { kpis: Record<string, Kpi>; series: { date: string; signups: number; active: number }[]; totals: { users: number; disabled: number; resumes: number; applications: number } };
type Funnel = { stages: { stage: string; users: number; pct_of_signups: number | null; pct_of_previous: number | null }[] };
type Cohorts = { weeks: { week: string; size: number; retention: (number | null)[] }[] };
type Features = { features: { name: string; events: number; users: number; adoption_pct: number | null; previous_events: number; series: number[] }[]; active_users: number };
type Named = { name: string; count: number; users?: number }[];
type Breakdowns = { companies: Named; roles: Named; geography: { cities: Named; unknown: number }; platforms: { name: string; logins: number; users: number }[]; os: Named };
type Live = { items: { at: string; user_id: string | null; email: string; kind: string; label: string; platform: string | null }[] };

function LiveFeed() {
  const live = useApi<Live>("/superadmin/live?limit=30");
  const { reload } = live;
  useEffect(() => {
    const t = setInterval(() => { if (document.visibilityState === "visible") void reload(); }, 30000);
    return () => clearInterval(t);
  }, [reload]);
  const items = live.data?.items ?? [];
  return (
    <Panel title="Live activity" description="Latest events across users. Refreshes every 30 seconds.">
      {items.length === 0 && <p className="text-sm text-muted-foreground">No recent activity.</p>}
      <ul className="max-h-96 divide-y overflow-y-auto text-sm">
        {items.map((e, i) => (
          <li key={`${e.at}-${i}`} className="flex items-baseline justify-between gap-3 py-2">
            <span className="min-w-0">
              {e.user_id ? <Link href={`/super-admin/users/${e.user_id}`} className="font-medium hover:underline">{e.email}</Link> : <span className="font-medium">{e.email}</span>}
              <span className="ml-2 font-mono text-xs text-muted-foreground">{e.label}{e.platform ? ` · ${e.platform}` : ""}</span>
            </span>
            <span className="shrink-0 text-xs text-muted-foreground">{fmt(e.at)}</span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

export default function SuperAdminOverview() {
  const { qs, label } = useAdmin();
  const o = useApi<Overview>(`/superadmin/overview?${qs}`);
  const f = useApi<Funnel>(`/superadmin/funnel?${qs}`);
  const w = Math.min(12, Math.max(4, Math.ceil(30 / 7) + 4));
  const co = useApi<Cohorts>(`/superadmin/cohorts?weeks=${w}`);
  const ft = useApi<Features>(`/superadmin/features?${qs}`);
  const b = useApi<Breakdowns>(`/superadmin/breakdowns?${qs}`);
  const k = o.data?.kpis;
  const rows = (o.data?.series ?? []).map((r) => ({ ...r, label: shortDay(r.date) }));
  return (
    <div className="flex flex-col gap-5">
      <div><h1 className="text-xl font-semibold">Overview</h1><p className="text-sm text-muted-foreground">{label}, compared with the previous period of equal length.</p></div>
      <Err message={o.error} />
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-4">
        <KpiCard label="Total users" kpi={k?.total_users} hint={o.data ? `${num(o.data.totals.disabled)} disabled` : undefined} />
        <KpiCard label="DAU" kpi={k?.dau} hint="active on the last day" />
        <KpiCard label="WAU" kpi={k?.wau} hint="active in the last 7 days" />
        <KpiCard label="MAU" kpi={k?.mau} hint="active in the last 30 days" />
        <KpiCard label="New signups" kpi={k?.signups} />
        <KpiCard label="Activation rate" kpi={k?.activation_rate} hint="signups with a resume within 7 days" />
        <KpiCard label="Applications sent" kpi={k?.applications_sent} />
        <KpiCard label="Emails sent" kpi={k?.emails_sent} />
        <KpiCard label="Reply rate" kpi={k?.reply_rate} hint="replied / emails sent" />
        <KpiCard label="AI agent runs" kpi={k?.agent_runs} />
        <KpiCard label="Error rate" kpi={k?.error_rate} invert hint="failed / agent runs" />
      </div>
      <DataChart title="Signups and active users" description="Per day over the selected range." rows={rows} x="label" series={[{ key: "signups", name: "Signups" }, { key: "active", name: "Active users" }]} />
      <div className="grid gap-5 lg:grid-cols-2">
        <Panel title="Conversion funnel" description="Signups in this range, by furthest stage reached.">
          <ul className="flex flex-col gap-3">
            {(f.data?.stages ?? []).map((s) => (
              <li key={s.stage} className="text-sm">
                <div className="flex justify-between"><span>{s.stage}</span><span className="tabular-nums text-muted-foreground">{num(s.users)} · {s.pct_of_signups ?? 0}%{s.pct_of_previous !== null ? ` (${s.pct_of_previous}% of previous)` : ""}</span></div>
                <div className="mt-1 h-2 rounded-full bg-muted"><div className="h-full rounded-full" style={{ width: `${s.pct_of_signups ?? 0}%`, background: "var(--chart-2)" }} /></div>
              </li>
            ))}
          </ul>
        </Panel>
        <Panel title="Retention cohorts" description="Weekly signup cohorts; % active in week 0 to 8 after signup.">
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="text-muted-foreground"><tr><th className="py-1 text-left font-medium">Cohort</th><th className="font-medium">Size</th>{Array.from({ length: 9 }, (_, i) => <th key={i} className="px-1 font-medium">W{i}</th>)}</tr></thead>
              <tbody>{(co.data?.weeks ?? []).map((r) => (
                <tr key={r.week}><td className="py-0.5 pr-2 whitespace-nowrap">{shortDay(r.week)}</td><td className="text-center tabular-nums">{r.size}</td>
                  {r.retention.map((v, i) => <td key={i} className="px-0.5"><div className="rounded px-1 py-1 text-center tabular-nums" style={heat(v)}>{v === null ? "" : Math.round(v)}</div></td>)}</tr>
              ))}</tbody>
            </table>
          </div>
        </Panel>
      </div>
      <Panel title="Feature adoption" description={`Share of the ${num(ft.data?.active_users)} active users who used each feature in this range.`}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-muted-foreground"><tr><th className="py-2 font-medium">Feature</th><th className="font-medium">Users</th><th className="w-48 font-medium">Adoption</th><th className="text-right font-medium">Events</th><th className="w-28 font-medium">Trend</th></tr></thead>
            <tbody>{(ft.data?.features ?? []).map((x) => (
              <tr key={x.name} className="border-t"><td className="py-2 capitalize">{x.name.replace(/_/g, " ")}</td><td className="tabular-nums">{x.users}</td>
                <td><div className="flex items-center gap-2"><div className="h-1.5 flex-1 rounded-full bg-muted"><div className="h-full rounded-full" style={{ width: `${x.adoption_pct ?? 0}%`, background: "var(--chart-2)" }} /></div><span className="w-10 text-right text-xs tabular-nums">{x.adoption_pct ?? 0}%</span></div></td>
                <td className="text-right tabular-nums">{num(x.events)}</td><td><Spark points={x.series} className="h-6 w-24" /></td></tr>
            ))}</tbody>
          </table>
          {ft.data?.features.length === 0 && <p className="text-sm text-muted-foreground">No feature events in this range.</p>}
        </div>
      </Panel>
      <div className="grid gap-5 lg:grid-cols-3">
        <Panel title="Top companies applied to"><BarList rows={(b.data?.companies ?? []).map((x) => ({ name: x.name, count: x.count, note: `${x.users} users` }))} /></Panel>
        <Panel title="Role mix"><BarList rows={(b.data?.roles ?? []).map((x) => ({ name: x.name, count: x.count }))} /></Panel>
        <Panel title="Geography" description={b.data ? `From profile location. ${b.data.geography.unknown} users have none.` : undefined}><BarList rows={b.data?.geography.cities ?? []} /></Panel>
      </div>
      <div className="grid gap-5 lg:grid-cols-2">
        <Panel title="Platform" description="Sign-ins by web vs app, recorded from the User-Agent since this tracking launched.">
          <BarList rows={(b.data?.platforms ?? []).map((p) => ({ name: p.name, count: p.logins, note: `${p.users} users` }))} empty="No sign-ins recorded in this range." />
          {(b.data?.os.length ?? 0) > 0 && <div className="mt-4"><p className="mb-2 text-xs font-medium text-muted-foreground">Operating system</p><BarList rows={b.data?.os ?? []} /></div>}
        </Panel>
        <LiveFeed />
      </div>
    </div>
  );
}
