"use client";

import { Download } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/form";
import { BarList, DataChart, Err, Pager, Panel, fmt, num, shortDay, useAdmin } from "@/components/super-admin";
import { useApi } from "@/hooks/use-api";
import { downloadFile } from "@/services/api";

type Row = { id: string; at: string | null; user_id: string | null; email: string; action: string; feature: string; entity: string | null; platform: string | null };
type Page = { items: Row[]; total: number; page: number; page_size: number };
type Named = { name: string; count: number }[];
type Summary = { total: number; by_action: Named; by_feature: Named; by_user: { id: string; name: string; count: number }[]; by_day: { date: string; count: number }[] };

export default function ActivityAudit() {
  const { qs, label } = useAdmin();
  const [user, setUser] = useState("");
  const [action, setAction] = useState("");
  const [feature, setFeature] = useState("");
  const [page, setPage] = useState(1);
  const [size, setSize] = useState(50);
  const [error, setError] = useState<string | null>(null);
  const filt = `${qs}&user=${encodeURIComponent(user)}&action=${encodeURIComponent(action)}&feature=${encodeURIComponent(feature)}`;
  const data = useApi<Page>(`/superadmin/audit?${filt}&page=${page}&page_size=${size}`);
  const sum = useApi<Summary>(`/superadmin/audit/summary?${filt}`);
  const reset = (fn: () => void) => { fn(); setPage(1); };

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div><h1 className="text-xl font-semibold">Activity &amp; audit</h1><p className="text-sm text-muted-foreground">{label}. Event names only; details are never shown.</p></div>
        <Button variant="outline" onClick={() => downloadFile(`/superadmin/audit/export.csv?${filt}`, "saige-audit.csv").catch((e: unknown) => setError(e instanceof Error ? e.message : "Export failed"))}><Download className="size-4" /> Export CSV</Button>
      </div>
      <Err message={error ?? data.error} />
      <div className="flex flex-wrap gap-2">
        <Input placeholder="User name or email" value={user} onChange={(e) => reset(() => setUser(e.target.value))} className="w-56" aria-label="User" />
        <Select value={feature} onChange={(e) => reset(() => setFeature(e.target.value))} className="w-44" aria-label="Feature"><option value="">All features</option>{(sum.data?.by_feature ?? []).map((f) => <option key={f.name} value={f.name}>{f.name}</option>)}</Select>
        <Input placeholder="Event type (e.g. resume)" value={action} onChange={(e) => reset(() => setAction(e.target.value))} className="w-56" aria-label="Event type" />
      </div>
      <DataChart title={`${num(sum.data?.total)} events`} description="Per day for the current filters." kind="bar" x="label" rows={(sum.data?.by_day ?? []).map((d) => ({ label: shortDay(d.date), events: d.count }))} series={[{ key: "events", name: "Events" }]} />
      <div className="grid gap-5 lg:grid-cols-3">
        <Panel title="By feature"><BarList rows={sum.data?.by_feature.slice(0, 10) ?? []} /></Panel>
        <Panel title="By event type"><BarList rows={sum.data?.by_action.slice(0, 10) ?? []} /></Panel>
        <Panel title="Most active users"><BarList rows={(sum.data?.by_user ?? []).map((u) => ({ name: u.name, count: u.count }))} /></Panel>
      </div>
      <Panel title="Event stream">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-muted-foreground"><tr><th className="py-2 font-medium">Time</th><th className="font-medium">User</th><th className="font-medium">Feature</th><th className="font-medium">Event</th><th className="font-medium">Entity</th><th className="font-medium">Platform</th></tr></thead>
            <tbody>{(data.data?.items ?? []).map((r) => (
              <tr key={r.id} className="border-t"><td className="whitespace-nowrap py-2 pr-3 text-muted-foreground">{fmt(r.at)}</td><td className="pr-3">{r.email}</td><td className="pr-3">{r.feature}</td><td className="pr-3 font-mono text-xs">{r.action}</td><td className="pr-3">{r.entity ?? "—"}</td><td>{r.platform ?? "—"}</td></tr>
            ))}</tbody>
          </table>
        </div>
        <Pager page={page} pageSize={size} total={data.data?.total ?? 0} onPage={setPage} onSize={(n) => { setSize(n); setPage(1); }} />
      </Panel>
    </div>
  );
}
