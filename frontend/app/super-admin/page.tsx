"use client";

import { Activity, AlertTriangle, FileText, Mail, Send, UserCheck, UserPlus, UserX, Users } from "lucide-react";

import { CountKpi } from "@/components/kpi";
import { DataChart, Err } from "@/components/super-admin";
import { useApi } from "@/hooks/use-api";

type Overview = { kpis: Record<string, number>; agent_runs_by_type: { name: string; count: number }[] };
type Growth = { series: { date: string; signups: number; active: number; applications: number }[] };

export default function SuperAdminOverview() {
  const o = useApi<Overview>("/superadmin/overview");
  const g = useApi<Growth>("/superadmin/growth");
  const k = o.data?.kpis;
  const rows = (g.data?.series ?? []).map((r) => ({ ...r, label: new Date(`${r.date}T00:00:00`).toLocaleDateString(undefined, { month: "short", day: "numeric" }) }));
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold">Overview</h1>
      <Err message={o.error} />
      {k && (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <CountKpi label="Total users" value={k.total_users} icon={Users} tone="green" hint={`${k.jobseekers} seekers · ${k.recruiters} recruiters`} />
          <CountKpi label="Active (24h)" value={k.active_24h} icon={Activity} tone="orange" hint={`${k.active_7d} in 7d · ${k.active_30d} in 30d`} />
          <CountKpi label="New signups (7d)" value={k.new_7d} icon={UserPlus} tone="purple" hint={`${k.new_today} today · ${k.new_30d} in 30d`} />
          <CountKpi label="Disabled accounts" value={k.disabled} icon={UserX} tone="red" hint={`${k.admins} admins`} />
          <CountKpi label="Resumes" value={k.resumes} icon={FileText} tone="teal" />
          <CountKpi label="Applications sent" value={k.applications_sent} icon={Send} tone="mint" hint={`${k.applications} tracked in total`} />
          <CountKpi label="Emails sent today" value={k.emails_sent_today} icon={Mail} tone="yellow" hint={`${k.emails_sent_7d} in 7d`} />
          <CountKpi label="Agent errors (24h)" value={k.errors_24h} icon={AlertTriangle} tone="lime" hint={`${k.agent_runs_30d} agent runs in 30d`} />
        </div>
      )}
      <DataChart title="Growth, last 90 days" description="Sign-ups, active users and applications per day." rows={rows} x="label"
        series={[{ key: "signups", name: "Sign-ups" }, { key: "active", name: "Active users" }, { key: "applications", name: "Applications" }]} />
      <DataChart title="AI / agent runs by type" description="Last 30 days." kind="bar" x="name" rows={o.data?.agent_runs_by_type ?? []} series={[{ key: "count", name: "Runs" }]} />
      <p className="flex items-center gap-2 text-xs text-muted-foreground"><UserCheck className="size-3.5" aria-hidden /> Counts only; resume contents, tokens and passwords are never shown here.</p>
    </div>
  );
}
