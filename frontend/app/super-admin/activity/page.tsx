"use client";

import { Download } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/form";
import { Err, Pager, fmt } from "@/components/super-admin";
import { useApi } from "@/hooks/use-api";
import { downloadFile } from "@/services/api";

type Row = { id: string; at: string | null; email: string; action: string; entity: string | null; entity_id: string | null };
type Page = { items: Row[]; total: number; page: number; page_size: number };

export default function ActivityAudit() {
  const [user, setUser] = useState("");
  const [action, setAction] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [page, setPage] = useState(1);
  const [size, setSize] = useState(50);
  const [error, setError] = useState<string | null>(null);
  const qs = `user=${encodeURIComponent(user)}&action=${encodeURIComponent(action)}&date_from=${from}&date_to=${to}`;
  const data = useApi<Page>(`/superadmin/audit?${qs}&page=${page}&page_size=${size}`);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold">Activity &amp; audit</h1>
        <Button variant="outline" onClick={() => downloadFile(`/superadmin/audit/export.csv?${qs}`, "saige-audit.csv").catch((e: unknown) => setError(e instanceof Error ? e.message : "Export failed"))}>
          <Download className="size-4" /> Export CSV
        </Button>
      </div>
      <Err message={error ?? data.error} />
      <Card>
        <CardContent className="pt-6">
          <div className="mb-4 flex flex-wrap gap-2">
            <Input placeholder="User email" value={user} onChange={(e) => { setUser(e.target.value); setPage(1); }} className="w-56" aria-label="User email" />
            <Input placeholder="Action (e.g. resume)" value={action} onChange={(e) => { setAction(e.target.value); setPage(1); }} className="w-56" aria-label="Action" />
            <Input type="date" value={from} onChange={(e) => { setFrom(e.target.value); setPage(1); }} className="w-40" aria-label="From date" />
            <Input type="date" value={to} onChange={(e) => { setTo(e.target.value); setPage(1); }} className="w-40" aria-label="To date" />
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-xs uppercase tracking-wide text-muted-foreground"><tr><th className="py-2">Time</th><th>User</th><th>Action</th><th>Entity</th></tr></thead>
              <tbody>{(data.data?.items ?? []).map((r) => (
                <tr key={r.id} className="border-t"><td className="py-2 pr-3 whitespace-nowrap text-muted-foreground">{fmt(r.at)}</td><td className="pr-3">{r.email}</td><td className="pr-3 font-mono text-xs">{r.action}</td><td>{r.entity ?? "—"}</td></tr>
              ))}</tbody>
            </table>
          </div>
          <Pager page={page} pageSize={size} total={data.data?.total ?? 0} onPage={setPage} onSize={(n) => { setSize(n); setPage(1); }} />
        </CardContent>
      </Card>
    </div>
  );
}
