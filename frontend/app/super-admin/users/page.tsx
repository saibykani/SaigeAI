"use client";

import { ArrowDown, ArrowUp, X } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/form";
import { ConfirmDialog, Err, Pager, fmt } from "@/components/super-admin";
import { useApi } from "@/hooks/use-api";
import { request } from "@/services/api";

type U = {
  id: string; email: string; name: string; role: string; is_super_admin: boolean; is_active: boolean; created_at: string | null;
  last_active_at: string | null; resumes: number; applications: number; emails_sent: number; plan: string;
};
type Page = { items: U[]; total: number; page: number; page_size: number };
type Detail = U & {
  sessions: number; counts: Record<string, number>; recent_audit: { at: string | null; action: string; entity: string | null }[];
  recent_runs: { at: string | null; agent: string | null; status: string | null }[];
};
type Pending = { kind: "disable" | "enable" | "signout" | "delete" | "role"; user: U; role?: string };

export default function UsersPage() {
  const [q, setQ] = useState("");
  const [role, setRole] = useState("");
  const [state, setState] = useState("");
  const [sort, setSort] = useState("created_at");
  const [order, setOrder] = useState("desc");
  const [page, setPage] = useState(1);
  const [size, setSize] = useState(25);
  const [open, setOpen] = useState<string | null>(null);
  const [pending, setPending] = useState<Pending | null>(null);
  const [error, setError] = useState<string | null>(null);
  const list = useApi<Page>(`/superadmin/users?q=${encodeURIComponent(q)}&role=${role}&state=${state}&sort=${sort}&order=${order}&page=${page}&page_size=${size}`);
  const detail = useApi<Detail>(open ? `/superadmin/users/${open}` : null);

  function sortBy(key: string) {
    if (sort === key) setOrder(order === "asc" ? "desc" : "asc");
    else { setSort(key); setOrder("desc"); }
    setPage(1);
  }
  const head = (key: string, label: string) => (
    <th className="py-2 pr-3"><button type="button" className="inline-flex items-center gap-1 uppercase" onClick={() => sortBy(key)}>{label}{sort === key && (order === "asc" ? <ArrowUp className="size-3" /> : <ArrowDown className="size-3" />)}</button></th>
  );

  async function run(p: Pending) {
    setPending(null);
    setError(null);
    try {
      const id = p.user.id;
      if (p.kind === "delete") { await request(`/superadmin/users/${id}/delete`, { method: "POST", body: { confirm_email: p.user.email } }); setOpen(null); }
      else if (p.kind === "signout") await request(`/superadmin/users/${id}/sign-out`, { method: "POST" });
      else if (p.kind === "role") await request(`/superadmin/users/${id}`, { method: "PATCH", body: { role: p.role } });
      else await request(`/superadmin/users/${id}`, { method: "PATCH", body: { is_active: p.kind === "enable" } });
      await list.reload();
      if (open && p.kind !== "delete") await detail.reload();
    } catch (e) { setError(e instanceof Error ? e.message : "Action failed"); }
  }

  const copy: Record<Pending["kind"], [string, string, string]> = {
    disable: ["Disable this account?", "They are signed out everywhere and cannot sign in until re-enabled.", "Disable"],
    enable: ["Enable this account?", "They can sign in again.", "Enable"],
    signout: ["Force sign-out?", "All of their sessions are revoked immediately.", "Sign out"],
    role: ["Change role?", "Their access changes immediately.", "Change role"],
    delete: ["Delete this user permanently?", "Everything they saved is removed and cannot be recovered. Type their email to confirm.", "Delete forever"],
  };
  const d = detail.data;

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold">Users</h1>
      <Err message={error ?? list.error} />
      <Card>
        <CardContent className="pt-6">
          <div className="mb-4 flex flex-wrap gap-2">
            <Input placeholder="Search name or email" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} className="w-60" aria-label="Search users" />
            <Select value={role} onChange={(e) => { setRole(e.target.value); setPage(1); }} className="w-36" aria-label="Role">
              <option value="">All roles</option><option value="jobseeker">Job seekers</option><option value="recruiter">Recruiters</option><option value="admin">Admins</option>
            </Select>
            <Select value={state} onChange={(e) => { setState(e.target.value); setPage(1); }} className="w-36" aria-label="Status">
              <option value="">All status</option><option value="active">Active</option><option value="disabled">Disabled</option>
            </Select>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-xs text-muted-foreground">
                <tr>{head("email", "User")}{head("role", "Role")}<th className="pr-3">Status</th><th className="pr-3 text-right">Resumes</th><th className="pr-3 text-right">Apps</th><th className="pr-3 text-right">Emails</th><th className="pr-3">Plan</th>{head("last_active_at", "Last active")}{head("created_at", "Signed up")}</tr>
              </thead>
              <tbody>{(list.data?.items ?? []).map((u) => (
                <tr key={u.id} className="cursor-pointer border-t hover:bg-muted/40" onClick={() => setOpen(u.id)}>
                  <td className="py-2 pr-3"><p className="font-medium">{u.email}</p><p className="text-xs text-muted-foreground">{u.name}</p></td>
                  <td className="pr-3">{u.role}{u.is_super_admin ? " (owner)" : ""}</td>
                  <td className="pr-3"><Badge variant={u.is_active ? "outline" : "destructive"}>{u.is_active ? "Active" : "Disabled"}</Badge></td>
                  <td className="pr-3 text-right tabular-nums">{u.resumes}</td><td className="pr-3 text-right tabular-nums">{u.applications}</td><td className="pr-3 text-right tabular-nums">{u.emails_sent}</td>
                  <td className="pr-3">{u.plan}</td><td className="pr-3 whitespace-nowrap text-muted-foreground">{fmt(u.last_active_at)}</td><td className="whitespace-nowrap text-muted-foreground">{fmt(u.created_at)}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
          <Pager page={page} pageSize={size} total={list.data?.total ?? 0} onPage={setPage} onSize={(n) => { setSize(n); setPage(1); }} />
        </CardContent>
      </Card>

      {open && (
        <div className="fixed inset-0 z-[70] flex justify-end bg-black/60" onClick={() => setOpen(null)}>
          <aside className="h-full w-full max-w-md overflow-y-auto border-l bg-card p-6" onClick={(e) => e.stopPropagation()} role="dialog" aria-label="User detail">
            <div className="flex items-start justify-between gap-3">
              <div><h2 className="text-lg font-semibold break-all">{d?.email ?? "Loading…"}</h2><p className="text-sm text-muted-foreground">{d?.name}</p></div>
              <Button size="icon" variant="ghost" onClick={() => setOpen(null)} aria-label="Close"><X className="size-4" /></Button>
            </div>
            {d && (
              <div className="mt-4 flex flex-col gap-5 text-sm">
                <dl className="grid grid-cols-2 gap-2">
                  <dt className="text-muted-foreground">Role</dt><dd>{d.role}</dd>
                  <dt className="text-muted-foreground">Status</dt><dd>{d.is_active ? "Active" : "Disabled"}</dd>
                  <dt className="text-muted-foreground">Plan</dt><dd>{d.plan}</dd>
                  <dt className="text-muted-foreground">Signed up</dt><dd>{fmt(d.created_at)}</dd>
                  <dt className="text-muted-foreground">Last active</dt><dd>{fmt(d.last_active_at)}</dd>
                  <dt className="text-muted-foreground">Live sessions</dt><dd>{d.sessions}</dd>
                  {Object.entries(d.counts).map(([k, v]) => <><dt key={`${k}-l`} className="text-muted-foreground">{k.replace("_", " ")}</dt><dd key={`${k}-v`}>{v}</dd></>)}
                </dl>
                {!d.is_super_admin && (
                  <div className="flex flex-wrap items-center gap-2">
                    <Select value={d.role} onChange={(e) => setPending({ kind: "role", user: d, role: e.target.value })} className="w-36" aria-label="Change role">
                      <option value="jobseeker">jobseeker</option><option value="recruiter">recruiter</option><option value="admin">admin</option>
                    </Select>
                    <Button variant="outline" size="sm" onClick={() => setPending({ kind: d.is_active ? "disable" : "enable", user: d })}>{d.is_active ? "Disable" : "Enable"}</Button>
                    <Button variant="outline" size="sm" onClick={() => setPending({ kind: "signout", user: d })}>Force sign-out</Button>
                    <Button variant="destructive" size="sm" onClick={() => setPending({ kind: "delete", user: d })}>Delete user</Button>
                  </div>
                )}
                <section><h3 className="mb-2 font-medium">Recent actions</h3><ul className="flex flex-col gap-1 text-xs">{d.recent_audit.map((a, i) => <li key={i} className="flex justify-between gap-2"><span className="font-mono">{a.action}</span><span className="text-muted-foreground">{fmt(a.at)}</span></li>)}</ul></section>
                <section><h3 className="mb-2 font-medium">Recent agent runs</h3><ul className="flex flex-col gap-1 text-xs">{d.recent_runs.map((r, i) => <li key={i} className="flex justify-between gap-2"><span>{r.agent} · {r.status}</span><span className="text-muted-foreground">{fmt(r.at)}</span></li>)}</ul></section>
              </div>
            )}
          </aside>
        </div>
      )}
      {pending && (
        <ConfirmDialog title={copy[pending.kind][0]} body={`${pending.user.email}: ${copy[pending.kind][1]}`} confirmLabel={copy[pending.kind][2]}
          typed={pending.kind === "delete" ? pending.user.email : undefined} onConfirm={() => void run(pending)} onCancel={() => setPending(null)} />
      )}
    </div>
  );
}
