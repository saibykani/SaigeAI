"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Err, fmt } from "@/components/super-admin";
import { useApi } from "@/hooks/use-api";

type Health = {
  database: { ok: boolean; latency_ms: number; query_ms: number }; collections: Record<string, number | null>;
  scheduler: { job: string; status: string; last_run: string | null; failed_7d: number; runs_7d: number }[];
  email_queue: { sent_today: number; senders_today: number; cap_per_user: number; users_at_cap: number; queued: number };
  agent_runs_24h: { total: number; failed: number }; feature_flags: Record<string, boolean>;
  failures: { at: string | null; agent: string; error: string }[];
};

export default function SystemHealth() {
  const h = useApi<Health>("/superadmin/health");
  const d = h.data;
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-xl font-semibold">System health</h1>
      <Err message={h.error} />
      {d && (
        <>
          <Card>
            <CardHeader><CardTitle className="text-base">Database</CardTitle></CardHeader>
            <CardContent className="flex items-center gap-3 text-sm">
              <Badge variant={d.database.ok ? "default" : "destructive"}>{d.database.ok ? "Connected" : "Down"}</Badge>
              <span className="tabular-nums text-muted-foreground">{d.database.latency_ms} ms ping · {d.database.query_ms} ms for two indexed queries</span>
              <span className="tabular-nums text-muted-foreground">Agent runs 24h: {d.agent_runs_24h.total} ({d.agent_runs_24h.failed} failed)</span>
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle className="text-base">Email queue today</CardTitle><CardDescription>Outreach is capped at {d.email_queue.cap_per_user} per user per day.</CardDescription></CardHeader>
            <CardContent className="grid grid-cols-2 gap-3 text-sm md:grid-cols-4">
              <div><p className="text-xs text-muted-foreground">Sent today</p><p className="text-lg font-semibold tabular-nums">{d.email_queue.sent_today}</p></div>
              <div><p className="text-xs text-muted-foreground">Users who sent</p><p className="text-lg font-semibold tabular-nums">{d.email_queue.senders_today}</p></div>
              <div><p className="text-xs text-muted-foreground">Users at daily cap</p><p className="text-lg font-semibold tabular-nums">{d.email_queue.users_at_cap}</p></div>
              <div><p className="text-xs text-muted-foreground">Queued to send</p><p className="text-lg font-semibold tabular-nums">{d.email_queue.queued}</p></div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle className="text-base">Integrations configured</CardTitle><CardDescription>Yes or no only; values are never shown.</CardDescription></CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              {Object.entries(d.feature_flags).map(([k, v]) => <Badge key={k} variant="outline">{k}: {v ? "yes" : "no"}</Badge>)}
            </CardContent>
          </Card>
          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader><CardTitle className="text-base">Collections</CardTitle></CardHeader>
              <CardContent><table className="w-full text-sm"><tbody>{Object.entries(d.collections).map(([k, v]) => <tr key={k} className="border-t"><td className="py-2">{k}</td><td className="py-2 text-right tabular-nums">{v ?? "?"}</td></tr>)}</tbody></table></CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle className="text-base">Scheduler, last runs</CardTitle></CardHeader>
              <CardContent>
                {d.scheduler.length === 0 && <p className="text-sm text-muted-foreground">No scheduler runs yet.</p>}
                <table className="w-full text-sm"><tbody>{d.scheduler.map((j) => <tr key={j.job} className="border-t"><td className="py-2">{j.job}</td><td className="py-2">{j.status} <span className="text-xs text-muted-foreground">({j.failed_7d} failed / {j.runs_7d} runs, 7d)</span></td><td className="py-2 text-right text-muted-foreground">{fmt(j.last_run)}</td></tr>)}</tbody></table>
              </CardContent>
            </Card>
          </div>
          <Card>
            <CardHeader><CardTitle className="text-base">Recent agent failures</CardTitle><CardDescription>Last 7 days.</CardDescription></CardHeader>
            <CardContent>
              {d.failures.length === 0 && <p className="text-sm text-muted-foreground">No failures.</p>}
              <ul className="flex flex-col gap-2 text-sm">{d.failures.map((f, i) => <li key={i} className="rounded-xl border p-3"><span className="font-medium">{f.agent}</span> <span className="text-muted-foreground">· {fmt(f.at)}</span><p className="mt-1 break-words text-muted-foreground">{f.error || "No message"}</p></li>)}</ul>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
