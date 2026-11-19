"use client";

import { BarList, DataChart, Err, Panel, Spark, num, shortDay, useAdmin } from "@/components/super-admin";
import { useApi } from "@/hooks/use-api";

type Feat = { name: string; events: number; users: number; adoption_pct: number | null; previous_events: number; series: number[] };
type Features = { dates: string[]; active_users: number; features: Feat[]; top_actions: { name: string; count: number }[]; agents: { name: string; runs: number; failed: number; users: number }[] };

export default function FeatureUsage() {
  const { qs, label } = useAdmin();
  const f = useApi<Features>(`/superadmin/features?${qs}`);
  const d = f.data;
  const top = (d?.features ?? []).slice(0, 4);
  const rows = (d?.dates ?? []).map((date, i) => Object.fromEntries([["label", shortDay(date)], ...top.map((t) => [t.name, t.series[i] ?? 0])]) as Record<string, string | number>);
  return (
    <div className="flex flex-col gap-5">
      <div><h1 className="text-xl font-semibold">Feature usage</h1><p className="text-sm text-muted-foreground">{label}. A feature is the first part of an audit event name; adoption is unique users divided by {num(d?.active_users)} active users.</p></div>
      <Err message={f.error} />
      <DataChart title="Top features over time" description="Events per day for the four busiest features." rows={rows} x="label" series={top.map((t) => ({ key: t.name, name: t.name }))} />
      <Panel title="Adoption by feature">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-muted-foreground"><tr><th className="py-2 font-medium">Feature</th><th className="text-right font-medium">Unique users</th><th className="w-48 pl-4 font-medium">Adoption</th><th className="text-right font-medium">Events</th><th className="text-right font-medium">Previous</th><th className="w-28 pl-4 font-medium">Trend</th></tr></thead>
            <tbody>{(d?.features ?? []).map((x) => (
              <tr key={x.name} className="border-t"><td className="py-2 capitalize">{x.name.replace(/_/g, " ")}</td><td className="text-right tabular-nums">{x.users}</td>
                <td className="pl-4"><div className="flex items-center gap-2"><div className="h-1.5 flex-1 rounded-full bg-muted"><div className="h-full rounded-full" style={{ width: `${x.adoption_pct ?? 0}%`, background: "var(--chart-2)" }} /></div><span className="w-10 text-right text-xs tabular-nums">{x.adoption_pct ?? 0}%</span></div></td>
                <td className="text-right tabular-nums">{num(x.events)}</td><td className="text-right tabular-nums text-muted-foreground">{num(x.previous_events)}</td><td className="pl-4"><Spark points={x.series} className="h-6 w-24" /></td></tr>
            ))}</tbody>
          </table>
        </div>
      </Panel>
      <div className="grid gap-5 lg:grid-cols-2">
        <Panel title="Top actions"><BarList rows={(d?.top_actions ?? []).slice(0, 15)} /></Panel>
        <Panel title="AI agents" description="Runs, failures and unique users per agent.">
          <BarList rows={(d?.agents ?? []).map((a) => ({ name: a.name, count: a.runs, note: `${a.failed} failed · ${a.users} users` }))} />
        </Panel>
      </div>
    </div>
  );
}
