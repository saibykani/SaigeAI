"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { DataChart, Err } from "@/components/super-admin";
import { useApi } from "@/hooks/use-api";

type Row = { name: string; count: number };
type Features = { days: number; features: Row[]; top_features: Row[]; actions: Row[]; agents: Row[] };

export default function FeatureUsage() {
  const f = useApi<Features>("/superadmin/features?days=30");
  const lists: [string, Row[]][] = [["Top actions", f.data?.actions ?? []], ["Agent runs", f.data?.agents ?? []]];
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold">Feature usage</h1>
      <Err message={f.error} />
      <div className="flex flex-wrap gap-2">
        {(f.data?.top_features ?? []).map((t, i) => <Badge key={t.name} variant="outline">#{i + 1} {t.name} · {t.count}</Badge>)}
      </div>
      <DataChart title="Actions by feature" description="Audit actions in the last 30 days, grouped by feature." kind="bar" x="name" rows={f.data?.features ?? []} series={[{ key: "count", name: "Actions" }]} />
      <div className="grid gap-6 lg:grid-cols-2">
        {lists.map(([title, rows]) => (
          <Card key={title}>
            <CardHeader><CardTitle className="text-base">{title}</CardTitle><CardDescription>Last 30 days.</CardDescription></CardHeader>
            <CardContent>
              <table className="w-full text-sm"><tbody>{rows.map((r) => <tr key={r.name} className="border-t"><td className="py-2">{r.name}</td><td className="py-2 text-right tabular-nums">{r.count}</td></tr>)}</tbody></table>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
