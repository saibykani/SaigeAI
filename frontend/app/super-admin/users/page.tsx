"use client";

import { ArrowDown, ArrowUp, Download } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/form";
import { Avatar, ConfirmDialog, Err, HealthBar, LIFECYCLE_LABEL, LifecycleBadge, Pager, fmt } from "@/components/super-admin";
import { useApi } from "@/hooks/use-api";
import { downloadFile, request } from "@/services/api";

type U = {
  id: string; email: string; name: string; role: string; is_super_admin: boolean; is_active: boolean; created_at: string | null; last_active_at: string | null;
  lifecycle: string; health: number; source: string; location: string; tags: string[]; resumes: number; applications: number; emails_sent: number; replies: number;
};
type Page = { items: U[]; total: number; page: number; page_size: number; lifecycle_counts: Record<string, number> };
type Filters = { q: string; role: string; state: string; lifecycle: string; tag: string; health: string };
type View = { name: string; filters: Filters };
const EMPTY: Filters = { q: "", role: "", state: "", lifecycle: "", tag: "", health: "" };
const VIEWS_KEY = "saige-admin-user-views";

export default function UsersPage() {
  const router = useRouter();
  const [f, setF] = useState<Filters>(EMPTY);
  const [sort, setSort] = useState("created_at");
  const [order, setOrder] = useState("desc");
  const [page, setPage] = useState(1);
  const [size, setSize] = useState(25);
  const [sel, setSel] = useState<Set<string>>(new Set());
  const [views, setViews] = useState<View[]>([]);
  const [confirm, setConfirm] = useState<"disable" | "enable" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => { try { setViews(JSON.parse(localStorage.getItem(VIEWS_KEY) || "[]") as View[]); } catch { /* private mode */ } }, []);
  const saveViews = (v: View[]) => { setViews(v); try { localStorage.setItem(VIEWS_KEY, JSON.stringify(v)); } catch { /* private mode */ } };

  const filterQs = Object.entries(f).map(([k, v]) => `${k}=${encodeURIComponent(v)}`).join("&") + `&sort=${sort}&order=${order}`;
  const list = useApi<Page>(`/superadmin/users?${filterQs}&page=${page}&page_size=${size}`);
  const tags = useApi<{ tags: { name: string; count: number }[] }>("/superadmin/tags");
  const set = (k: keyof Filters, v: string) => { setF({ ...f, [k]: v }); setPage(1); setSel(new Set()); };

  function sortBy(key: string) {
    if (sort === key) setOrder(order === "asc" ? "desc" : "asc"); else { setSort(key); setOrder("desc"); }
    setPage(1);
  }
  const head = (key: string, label: string, right = false) => (
    <th className={`py-2 pr-3 font-medium ${right ? "text-right" : ""}`}><button type="button" className="inline-flex items-center gap-1" onClick={() => sortBy(key)}>{label}{sort === key && (order === "asc" ? <ArrowUp className="size-3" /> : <ArrowDown className="size-3" />)}</button></th>
  );
  const items = list.data?.items ?? [];
  const ids = [...sel];

  async function bulk(body: Record<string, unknown>) {
    setError(null); setMsg(null); setConfirm(null);
    try {
      const r = await request<{ updated: number; skipped: number }>("/superadmin/users-bulk", { method: "POST", body: { ids, ...body } });
      setMsg(`${r.updated} updated${r.skipped ? `, ${r.skipped} skipped (owner accounts)` : ""}.`);
      setSel(new Set());
      await list.reload();
    } catch (e) { setError(e instanceof Error ? e.message : "Action failed"); }
  }

  return (
    <div className="flex flex-col gap-5">
      <div><h1 className="text-xl font-semibold">Users</h1><p className="text-sm text-muted-foreground">Customer list with lifecycle stage and health score. Open a user for the full 360 view.</p></div>
      <Err message={error ?? list.error} />
      {msg && <p className="rounded-xl border px-4 py-2 text-sm">{msg}</p>}
      <div className="flex flex-wrap gap-2">
        {["", "new", "activated", "engaged", "at_risk", "churned"].map((s) => (
          <button key={s} type="button" onClick={() => set("lifecycle", s)} className={`rounded-full border px-3 py-1 text-xs font-medium ${f.lifecycle === s ? "bg-muted text-foreground" : "text-muted-foreground hover:bg-muted/50"}`}>
            {s ? LIFECYCLE_LABEL[s] : "All"}{s && list.data?.lifecycle_counts[s] !== undefined ? ` · ${list.data.lifecycle_counts[s]}` : ""}
          </button>
        ))}
      </div>
      <Card>
        <CardContent className="pt-5">
          <div className="mb-4 flex flex-wrap items-center gap-2">
            <Input placeholder="Search name or email" value={f.q} onChange={(e) => set("q", e.target.value)} className="w-56" aria-label="Search users" />
            <Select value={f.role} onChange={(e) => set("role", e.target.value)} className="w-36" aria-label="Role"><option value="">All roles</option><option value="jobseeker">Job seekers</option><option value="recruiter">Recruiters</option><option value="admin">Admins</option></Select>
            <Select value={f.state} onChange={(e) => set("state", e.target.value)} className="w-32" aria-label="Status"><option value="">All status</option><option value="active">Active</option><option value="disabled">Disabled</option></Select>
            <Select value={f.health} onChange={(e) => set("health", e.target.value)} className="w-32" aria-label="Health"><option value="">Any health</option><option value="healthy">Healthy</option><option value="fair">Fair</option><option value="low">Low</option></Select>
            <Select value={f.tag} onChange={(e) => set("tag", e.target.value)} className="w-32" aria-label="Tag"><option value="">Any tag</option>{(tags.data?.tags ?? []).map((t) => <option key={t.name} value={t.name}>{t.name} ({t.count})</option>)}</Select>
            <Select value="" onChange={(e) => { const v = views.find((x) => x.name === e.target.value); if (v) { setF(v.filters); setPage(1); } }} className="w-36" aria-label="Saved views"><option value="">Saved views</option>{views.map((v) => <option key={v.name} value={v.name}>{v.name}</option>)}</Select>
            <Button size="sm" variant="outline" onClick={() => { const name = window.prompt("Name this view"); if (name?.trim()) saveViews([...views.filter((v) => v.name !== name.trim()), { name: name.trim(), filters: f }]); }}>Save view</Button>
            {views.length > 0 && <Button size="sm" variant="ghost" onClick={() => saveViews([])}>Clear views</Button>}
            <Button size="sm" variant="outline" className="ml-auto" onClick={() => downloadFile(`/superadmin/users-export.csv?${filterQs}`, "saige-users.csv").catch((e: unknown) => setError(e instanceof Error ? e.message : "Export failed"))}><Download className="size-4" /> Export CSV</Button>
          </div>
          {sel.size > 0 && (
            <div className="mb-3 flex flex-wrap items-center gap-2 rounded-xl border bg-muted/40 px-3 py-2 text-sm">
              <span>{sel.size} selected</span>
              <Button size="sm" variant="outline" onClick={() => setConfirm("disable")}>Disable</Button>
              <Button size="sm" variant="outline" onClick={() => setConfirm("enable")}>Enable</Button>
              <Select value="" onChange={(e) => e.target.value && void bulk({ action: "role", role: e.target.value })} className="w-40" aria-label="Change role"><option value="">Change role…</option><option value="jobseeker">jobseeker</option><option value="recruiter">recruiter</option><option value="admin">admin</option></Select>
              <Button size="sm" variant="ghost" onClick={() => setSel(new Set())}>Clear</Button>
            </div>
          )}
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-xs text-muted-foreground">
                <tr>
                  <th className="w-8 py-2"><input type="checkbox" aria-label="Select all on page" checked={items.length > 0 && items.every((u) => sel.has(u.id))} onChange={(e) => setSel(e.target.checked ? new Set(items.map((u) => u.id)) : new Set())} /></th>
                  {head("email", "User")}{head("role", "Role")}<th className="pr-3 font-medium">Status</th><th className="pr-3 font-medium">Lifecycle</th>{head("health", "Health")}<th className="pr-3 font-medium">Source</th><th className="pr-3 font-medium">Location</th>
                  {head("resumes", "Resumes", true)}{head("applications", "Apps", true)}{head("emails_sent", "Emails", true)}{head("replies", "Replies", true)}{head("last_active_at", "Last active")}{head("created_at", "Signed up")}
                </tr>
              </thead>
              <tbody>{items.map((u) => (
                <tr key={u.id} className="cursor-pointer border-t hover:bg-muted/40" onClick={() => router.push(`/super-admin/users/${u.id}`)}>
                  <td className="py-2" onClick={(e) => e.stopPropagation()}><input type="checkbox" aria-label={`Select ${u.email}`} checked={sel.has(u.id)} onChange={(e) => { const n = new Set(sel); if (e.target.checked) n.add(u.id); else n.delete(u.id); setSel(n); }} /></td>
                  <td className="py-2 pr-3"><div className="flex items-center gap-2.5"><Avatar name={u.name} email={u.email} /><div className="min-w-0"><Link href={`/super-admin/users/${u.id}`} className="block truncate font-medium hover:underline" onClick={(e) => e.stopPropagation()}>{u.name || u.email}</Link><p className="truncate text-xs text-muted-foreground">{u.email}</p>
                    {u.tags.length > 0 && <p className="mt-0.5 flex flex-wrap gap-1">{u.tags.map((t) => <span key={t} className="rounded bg-muted px-1.5 text-[10px]">{t}</span>)}</p>}</div></div></td>
                  <td className="pr-3">{u.role}{u.is_super_admin ? " (owner)" : ""}</td>
                  <td className="pr-3">{u.is_active ? "Active" : <span className="text-muted-foreground">Disabled</span>}</td>
                  <td className="pr-3"><LifecycleBadge stage={u.lifecycle} /></td><td className="pr-3"><HealthBar score={u.health} /></td>
                  <td className="pr-3 text-muted-foreground">{u.source}</td><td className="pr-3 whitespace-nowrap text-muted-foreground">{u.location || "—"}</td>
                  <td className="pr-3 text-right tabular-nums">{u.resumes}</td><td className="pr-3 text-right tabular-nums">{u.applications}</td><td className="pr-3 text-right tabular-nums">{u.emails_sent}</td><td className="pr-3 text-right tabular-nums">{u.replies}</td>
                  <td className="pr-3 whitespace-nowrap text-muted-foreground">{fmt(u.last_active_at)}</td><td className="whitespace-nowrap text-muted-foreground">{fmt(u.created_at)}</td>
                </tr>
              ))}</tbody>
            </table>
            {!list.loading && items.length === 0 && <p className="py-6 text-center text-sm text-muted-foreground">No users match these filters.</p>}
          </div>
          <Pager page={page} pageSize={size} total={list.data?.total ?? 0} onPage={setPage} onSize={(n) => { setSize(n); setPage(1); }} />
        </CardContent>
      </Card>
      {confirm && <ConfirmDialog title={`${confirm === "disable" ? "Disable" : "Enable"} ${sel.size} accounts?`} body={confirm === "disable" ? "They are signed out everywhere and cannot sign in until re-enabled." : "They can sign in again."} confirmLabel={confirm === "disable" ? "Disable" : "Enable"} onConfirm={() => void bulk({ action: confirm })} onCancel={() => setConfirm(null)} />}
    </div>
  );
}
