"use client";

import { Activity, Bot, Briefcase, FileText, Globe, Send, Table2, UserPlus, Users } from "lucide-react";
import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { Notice, PageHeader } from "@/components/app-shell";
import { CountKpi } from "@/components/kpi";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/form";
import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { request } from "@/services/api";
import type { AdminActivity, AdminOverview, AdminUser, UserRole } from "@/types/api";

const fmt = (iso: string | null) => (iso ? new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "—");
const day = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { month: "short", day: "numeric" });

function SignupsChart({ rows }: { rows: AdminOverview["signups"] }) {
  const [table, setTable] = useState(false);
  const data = rows.map((r) => ({ ...r, label: day(r.date) }));
  return (
    <Card className="animate-rise">
      <CardHeader className="flex-row items-start justify-between gap-3">
        <div>
          <CardTitle className="text-base">Sign-ups per day</CardTitle>
          <CardDescription>Last 30 days, all roles.</CardDescription>
        </div>
        <Button size="icon" variant="ghost" className="size-8" onClick={() => setTable(!table)} aria-label={table ? "Show chart" : "Show table"} title={table ? "Show chart" : "Show table"}>
          <Table2 className="size-4" />
        </Button>
      </CardHeader>
      <CardContent>
        {table ? (
          <div className="max-h-72 overflow-y-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-xs uppercase tracking-wide text-muted-foreground"><tr><th className="py-2">Day</th><th className="py-2 text-right">Sign-ups</th></tr></thead>
              <tbody>{[...data].reverse().map((r) => <tr key={r.date} className="border-t"><td className="py-2">{r.label}</td><td className="py-2 text-right tabular-nums">{r.count}</td></tr>)}</tbody>
            </table>
          </div>
        ) : (
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: -12 }}>
                <CartesianGrid vertical={false} stroke="var(--grid)" />
                <XAxis dataKey="label" tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
                <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} axisLine={false} tickLine={false} />
                <Tooltip cursor={{ fill: "var(--muted)" }} contentStyle={{ background: "var(--card-solid, var(--card))", border: "1px solid var(--border)", borderRadius: 12 }} />
                <Legend wrapperStyle={{ fontSize: 12, color: "var(--muted-foreground)" }} />
                <Bar dataKey="count" name="Sign-ups" fill="var(--chart-1)" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function UsageList({ title, description, rows, color }: { title: string; description: string; rows: { name: string; count: number }[]; color: string }) {
  const max = Math.max(1, ...rows.map((r) => r.count));
  return (
    <Card className="animate-rise">
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-2.5">
        {rows.length === 0 && <p className="text-sm text-muted-foreground">Nothing in the last 30 days.</p>}
        {rows.map((r) => (
          <div key={r.name} className="text-sm">
            <div className="mb-1 flex justify-between gap-3"><span className="truncate">{r.name.replace(/[_.]/g, " ")}</span><span className="tabular-nums text-muted-foreground">{r.count}</span></div>
            <div className="h-1.5 rounded-full bg-muted"><div className="h-full rounded-full" style={{ width: `${(r.count / max) * 100}%`, background: color }} /></div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function UsersTable({ superAdmin, selfId }: { superAdmin: boolean; selfId: string }) {
  const [q, setQ] = useState("");
  const [role, setRole] = useState("");
  const [error, setError] = useState<string | null>(null);
  const users = useApi<AdminUser[]>(`/admin/users?q=${encodeURIComponent(q)}&role=${role}`);

  async function patch(id: string, body: { role?: UserRole; is_active?: boolean }) {
    setError(null);
    try {
      await request(`/admin/users/${id}`, { method: "PATCH", body });
      await users.reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Update failed");
    }
  }

  return (
    <Card className="animate-rise">
      <CardHeader className="gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <CardTitle className="text-base">Users</CardTitle>
          <CardDescription>{superAdmin ? "You can change any role, including admin." : "Only the super admin can grant or revoke admin."}</CardDescription>
        </div>
        <div className="flex gap-2">
          <Input placeholder="Search name or email" value={q} onChange={(e) => setQ(e.target.value)} className="w-56" aria-label="Search users" />
          <Select value={role} onChange={(e) => setRole(e.target.value)} aria-label="Filter by role" className="w-36">
            <option value="">All roles</option><option value="jobseeker">Job seekers</option><option value="recruiter">Recruiters</option><option value="admin">Admins</option>
          </Select>
        </div>
      </CardHeader>
      <CardContent>
        {error && <div className="mb-3"><Notice tone="error">{error}</Notice></div>}
        <div className="overflow-x-auto">
          <table className="w-full min-w-[820px] text-sm">
            <thead className="text-left text-xs uppercase tracking-wide text-muted-foreground">
              <tr><th className="py-2">User</th><th className="py-2">Role</th><th className="py-2">Signed up</th><th className="py-2">Last active</th>
                <th className="py-2 text-right">Resumes</th><th className="py-2 text-right">Applications</th><th className="py-2 text-right">Account</th></tr>
            </thead>
            <tbody>
              {(users.data ?? []).map((u) => {
                const locked = u.is_super_admin || (!superAdmin && u.role === "admin");
                return (
                  <tr key={u.id} className="border-t">
                    <td className="py-2.5"><span className="block font-medium">{u.name || "—"}</span><span className="text-xs text-muted-foreground">{u.email}</span></td>
                    <td className="py-2.5">
                      {u.is_super_admin ? <Badge>Super admin</Badge> : (
                        <Select value={u.role} disabled={locked} aria-label={`Role for ${u.email}`} className="h-8 w-32 text-xs"
                          onChange={(e) => void patch(u.id, { role: e.target.value as UserRole })}>
                          <option value="jobseeker">Job seeker</option><option value="recruiter">Recruiter</option>
                          <option value="admin" disabled={!superAdmin}>Admin</option>
                        </Select>
                      )}
                    </td>
                    <td className="py-2.5 text-muted-foreground">{fmt(u.created_at)}</td>
                    <td className="py-2.5 text-muted-foreground">{fmt(u.last_active_at)}</td>
                    <td className="py-2.5 text-right tabular-nums">{u.resumes}</td>
                    <td className="py-2.5 text-right tabular-nums">{u.applications}</td>
                    <td className="py-2.5 text-right">
                      {locked || u.id === selfId ? <Badge variant={u.is_active ? "success" : "muted"}>{u.is_active ? "Active" : "Disabled"}</Badge> : (
                        <Button size="sm" variant={u.is_active ? "outline" : "default"} onClick={() => void patch(u.id, { is_active: !u.is_active })}>
                          {u.is_active ? "Disable" : "Enable"}
                        </Button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {users.data?.length === 0 && <p className="py-6 text-center text-sm text-muted-foreground">No users match.</p>}
        </div>
      </CardContent>
    </Card>
  );
}

export default function AdminPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const overview = useApi<AdminOverview>(isAdmin ? "/admin/overview" : null);
  const activity = useApi<AdminActivity[]>(isAdmin ? "/admin/activity?limit=40" : null);

  if (!isAdmin) {
    return (<><PageHeader title="Admin" /><Notice tone="warning">This page is only for Saige AI admins.</Notice></>);
  }
  const k = overview.data?.kpis;
  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Admin" description="Platform health at a glance: who signed up, who is active, and which features they use. Counts only; resume contents and tokens are never shown." />
      {overview.error && <Notice tone="error">{overview.error}</Notice>}
      {k && (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <CountKpi label="Total users" value={k.total_users} hint={`${k.jobseekers} job seekers · ${k.recruiters} recruiters · ${k.admins} admins`} icon={Users} tone="green" />
          <CountKpi label="New users (7 days)" value={k.new_7d} hint={`${k.new_today} today · ${k.new_30d} in 30 days`} icon={UserPlus} tone="orange" delay={40} />
          <CountKpi label="Active (24 hours)" value={k.active_24h} hint={`${k.active_7d} active in 7 days`} icon={Activity} tone="mint" delay={80} />
          <CountKpi label="Agent runs" value={k.agent_runs} hint={`${k.agent_runs_30d} in the last 30 days`} icon={Bot} tone="purple" delay={120} />
          <CountKpi label="Resumes uploaded" value={k.resumes} icon={FileText} tone="yellow" delay={160} />
          <CountKpi label="Applications" value={k.applications} icon={Send} tone="teal" delay={200} />
          <CountKpi label="Portfolios published" value={k.portfolios_published} icon={Globe} tone="lime" delay={240} />
          <CountKpi label="Recruiter jobs posted" value={k.recruiter_jobs} icon={Briefcase} tone="red" delay={280} />
        </div>
      )}
      {overview.data && <SignupsChart rows={overview.data.signups} />}
      {overview.data && (
        <div className="grid gap-6 lg:grid-cols-2">
          <UsageList title="Agent runs by type" description="Last 30 days." rows={overview.data.agent_usage} color="var(--chart-2)" />
          <UsageList title="Actions by type" description="Audit log, last 30 days." rows={overview.data.action_usage} color="var(--chart-3)" />
        </div>
      )}
      <UsersTable superAdmin={Boolean(user?.is_super_admin)} selfId={user?.id ?? ""} />
      <Card className="animate-rise">
        <CardHeader><CardTitle className="text-base">Recent activity</CardTitle><CardDescription>Who did what, across all users.</CardDescription></CardHeader>
        <CardContent>
          <ul className="divide-y text-sm">
            {(activity.data ?? []).map((a) => (
              <li key={a.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                <span><span className="font-medium">{a.email}</span> <span className="text-muted-foreground">{a.action.replace(/[_.]/g, " ")}</span></span>
                <span className="text-xs text-muted-foreground">{fmt(a.at)}</span>
              </li>
            ))}
          </ul>
          {activity.data?.length === 0 && <p className="text-sm text-muted-foreground">No activity yet.</p>}
        </CardContent>
      </Card>
    </div>
  );
}
