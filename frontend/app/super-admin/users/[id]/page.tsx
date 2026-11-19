"use client";

import { ArrowLeft, Trash2, X } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input, Select, Textarea } from "@/components/ui/form";
import { Avatar, ConfirmDialog, Err, HealthBar, LifecycleBadge, Panel, fmt, num } from "@/components/super-admin";
import { useApi } from "@/hooks/use-api";
import { request } from "@/services/api";

type Detail = {
  id: string; email: string; name: string; role: string; is_super_admin: boolean; is_active: boolean; created_at: string | null; last_active_at: string | null;
  source: string; lifecycle: string; health: number; health_label: string; health_parts: { idle_days: number; events_30d: number; features_30d: number };
  profile: { designation: string | null; location: string | null; experience_years: number | null; target_role: string | null };
  kpis: Record<string, number>; resumes_by_kind: { kind: string; count: number }[]; tags: string[]; notes_count: number;
  sessions: { first_seen: string | null; last_seen: string | null; platform: string; os: string; active: boolean }[];
};
type Timeline = { items: { at: string | null; kind: string; label: string; entity: string | null; platform: string | null }[] };
type Apps = { items: { id: string; company: string; role: string; status: string; source: string | null; match_score: number | null; applied_at: string | null; created_at: string | null }[] };
type Emails = { items: { id: string; subject: string | null; status: string; kind: string | null; sent_at: string | null; replied_at: string | null }[] };
type Notes = { items: { id: string; text: string; created_at: string | null; author: string }[] };
type Pending = "disable" | "enable" | "signout" | "delete" | "role";
const TABS = ["Timeline", "Applications", "Emails", "Notes"] as const;

export default function User360() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const d = useApi<Detail>(`/superadmin/users/${id}`);
  const [tab, setTab] = useState<(typeof TABS)[number]>("Timeline");
  const [kind, setKind] = useState("all");
  const tl = useApi<Timeline>(tab === "Timeline" ? `/superadmin/users/${id}/timeline?kind=${kind}&limit=150` : null);
  const apps = useApi<Apps>(tab === "Applications" ? `/superadmin/users/${id}/applications` : null);
  const mails = useApi<Emails>(tab === "Emails" ? `/superadmin/users/${id}/emails` : null);
  const notes = useApi<Notes>(tab === "Notes" ? `/superadmin/users/${id}/notes` : null);
  const [note, setNote] = useState("");
  const [tag, setTag] = useState("");
  const [pending, setPending] = useState<{ kind: Pending; role?: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const u = d.data;

  async function act(fn: () => Promise<unknown>, after?: () => Promise<unknown>) {
    setError(null);
    try { await fn(); await d.reload(); if (after) await after(); } catch (e) { setError(e instanceof Error ? e.message : "Action failed"); }
  }
  async function run(p: { kind: Pending; role?: string }) {
    setPending(null);
    if (!u) return;
    if (p.kind === "delete") {
      try { await request(`/superadmin/users/${id}/delete`, { method: "POST", body: { confirm_email: u.email } }); router.replace("/super-admin/users"); } catch (e) { setError(e instanceof Error ? e.message : "Delete failed"); }
      return;
    }
    await act(() => p.kind === "signout" ? request(`/superadmin/users/${id}/sign-out`, { method: "POST" })
      : request(`/superadmin/users/${id}`, { method: "PATCH", body: p.kind === "role" ? { role: p.role } : { is_active: p.kind === "enable" } }));
  }
  const saveTags = (tags: string[]) => act(() => request(`/superadmin/users/${id}/tags`, { method: "PUT", body: { tags } }));
  const copy: Record<Pending, [string, string, string]> = {
    disable: ["Disable this account?", "They are signed out everywhere and cannot sign in until re-enabled.", "Disable"],
    enable: ["Enable this account?", "They can sign in again.", "Enable"],
    signout: ["Force sign-out?", "All of their sessions are revoked immediately.", "Sign out"],
    role: ["Change role?", "Their access changes immediately.", "Change role"],
    delete: ["Delete this user permanently?", "Everything they saved is removed and cannot be recovered. Type their email to confirm.", "Delete forever"],
  };

  return (
    <div className="flex flex-col gap-5">
      <Link href="/super-admin/users" className="inline-flex w-fit items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"><ArrowLeft className="size-4" /> All users</Link>
      <Err message={error ?? d.error} />
      {u && (
        <>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="flex items-center gap-4">
              <Avatar name={u.name} email={u.email} size={56} />
              <div>
                <h1 className="text-xl font-semibold">{u.name || u.email}</h1>
                <p className="text-sm text-muted-foreground">{u.email} · {u.role}{u.is_super_admin ? " (owner)" : ""} · {u.is_active ? "Active" : "Disabled"}</p>
                <div className="mt-2 flex flex-wrap items-center gap-3"><LifecycleBadge stage={u.lifecycle} /><HealthBar score={u.health} /><span className="text-xs text-muted-foreground">signed up {fmt(u.created_at)} via {u.source}</span></div>
              </div>
            </div>
            {!u.is_super_admin && (
              <div className="flex flex-wrap items-center gap-2">
                <Select value={u.role} onChange={(e) => setPending({ kind: "role", role: e.target.value })} className="w-36" aria-label="Change role"><option value="jobseeker">jobseeker</option><option value="recruiter">recruiter</option><option value="admin">admin</option></Select>
                <Button variant="outline" size="sm" onClick={() => setPending({ kind: u.is_active ? "disable" : "enable" })}>{u.is_active ? "Disable" : "Enable"}</Button>
                <Button variant="outline" size="sm" onClick={() => setPending({ kind: "signout" })}>Force sign-out</Button>
                <Button variant="destructive" size="sm" onClick={() => setPending({ kind: "delete" })}>Delete user</Button>
              </div>
            )}
          </div>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-8">
            {Object.entries(u.kpis).map(([k, v]) => <div key={k} className="rounded-xl border bg-card p-3"><p className="text-xs capitalize text-muted-foreground">{k.replace(/_/g, " ")}</p><p className="text-lg font-semibold tabular-nums">{num(v)}</p></div>)}
          </div>
          <div className="grid gap-5 lg:grid-cols-3">
            <Panel title="Profile summary" description="From the user's profile fields; resume contents are never shown.">
              <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm">
                <dt className="text-muted-foreground">Current title</dt><dd>{u.profile.designation || "—"}</dd>
                <dt className="text-muted-foreground">Target role</dt><dd>{u.profile.target_role || "—"}</dd>
                <dt className="text-muted-foreground">Location</dt><dd>{u.profile.location || "—"}</dd>
                <dt className="text-muted-foreground">Experience</dt><dd>{u.profile.experience_years ?? "—"}{u.profile.experience_years !== null ? " yrs" : ""}</dd>
                <dt className="text-muted-foreground">Last active</dt><dd>{fmt(u.last_active_at)}</dd>
                <dt className="text-muted-foreground">Health inputs</dt><dd>{u.health_parts.idle_days}d idle · {u.health_parts.events_30d} events · {u.health_parts.features_30d} features (30d)</dd>
              </dl>
              <p className="mb-1 mt-4 text-xs font-medium text-muted-foreground">Resumes by kind</p>
              <div className="flex flex-wrap gap-1.5">{u.resumes_by_kind.length === 0 && <span className="text-sm text-muted-foreground">None</span>}{u.resumes_by_kind.map((r) => <span key={r.kind} className="rounded-full border px-2.5 py-0.5 text-xs">{r.kind} · {r.count}</span>)}</div>
            </Panel>
            <Panel title="Sessions" description="Recent sign-ins; platform comes from the User-Agent.">
              {u.sessions.length === 0 && <p className="text-sm text-muted-foreground">No sessions.</p>}
              <ul className="flex flex-col gap-2 text-sm">{u.sessions.map((s, i) => <li key={i} className="flex justify-between gap-2"><span>{s.platform} · {s.os}{s.active ? <span className="ml-2 text-xs text-muted-foreground">active</span> : ""}</span><span className="text-xs text-muted-foreground">{fmt(s.last_seen)}</span></li>)}</ul>
            </Panel>
            <Panel title="Tags" description="Visible to super admins only.">
              <div className="mb-3 flex flex-wrap gap-1.5">
                {u.tags.length === 0 && <span className="text-sm text-muted-foreground">No tags.</span>}
                {u.tags.map((t) => <span key={t} className="inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs">{t}<button type="button" aria-label={`Remove ${t}`} onClick={() => void saveTags(u.tags.filter((x) => x !== t))}><X className="size-3" /></button></span>)}
              </div>
              <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); if (tag.trim()) { void saveTags([...u.tags, tag]); setTag(""); } }}>
                <Input value={tag} onChange={(e) => setTag(e.target.value)} placeholder="Add tag (VIP, tester, feedback)" maxLength={24} aria-label="New tag" />
                <Button type="submit" size="sm" variant="outline">Add</Button>
              </form>
            </Panel>
          </div>
          <div className="flex gap-1 border-b">{TABS.map((t) => <button key={t} type="button" onClick={() => setTab(t)} className={`-mb-px border-b-2 px-3 py-2 text-sm ${tab === t ? "border-foreground font-medium" : "border-transparent text-muted-foreground"}`}>{t}{t === "Notes" ? ` (${u.notes_count})` : ""}</button>)}</div>
          {tab === "Timeline" && (
            <Panel title="Activity timeline" description="Audit events, agent runs and sign-ins (last 90 days)." right={
              <Select value={kind} onChange={(e) => setKind(e.target.value)} className="w-36" aria-label="Event kind"><option value="all">All events</option><option value="audit">Actions</option><option value="run">Agent runs</option><option value="login">Sign-ins</option></Select>}>
              {(tl.data?.items.length ?? 0) === 0 && <p className="text-sm text-muted-foreground">No events.</p>}
              <ul className="max-h-[32rem] divide-y overflow-y-auto text-sm">{(tl.data?.items ?? []).map((e, i) => <li key={i} className="flex justify-between gap-3 py-2"><span><span className="mr-2 rounded bg-muted px-1.5 py-0.5 text-[10px] uppercase">{e.kind}</span><span className="font-mono text-xs">{e.label}</span>{e.entity ? <span className="ml-2 text-xs text-muted-foreground">{e.entity}</span> : null}{e.platform ? <span className="ml-2 text-xs text-muted-foreground">{e.platform}</span> : null}</span><span className="shrink-0 text-xs text-muted-foreground">{fmt(e.at)}</span></li>)}</ul>
            </Panel>
          )}
          {tab === "Applications" && (
            <Panel title="Applications">
              {(apps.data?.items.length ?? 0) === 0 && <p className="text-sm text-muted-foreground">No applications.</p>}
              <div className="overflow-x-auto"><table className="w-full text-sm"><tbody>{(apps.data?.items ?? []).map((a) => <tr key={a.id} className="border-t"><td className="py-2 font-medium">{a.company}</td><td>{a.role}</td><td className="text-xs">{a.status}</td><td className="text-xs text-muted-foreground">{a.source ?? ""}</td><td className="text-right text-xs text-muted-foreground">{fmt(a.applied_at ?? a.created_at)}</td></tr>)}</tbody></table></div>
            </Panel>
          )}
          {tab === "Emails" && (
            <Panel title="Emails sent and replies">
              {(mails.data?.items.length ?? 0) === 0 && <p className="text-sm text-muted-foreground">No sent emails.</p>}
              <div className="overflow-x-auto"><table className="w-full text-sm"><tbody>{(mails.data?.items ?? []).map((m) => <tr key={m.id} className="border-t"><td className="py-2">{m.subject || "(no subject)"}</td><td className="text-xs">{m.status}</td><td className="text-xs text-muted-foreground">sent {fmt(m.sent_at)}</td><td className="text-right text-xs text-muted-foreground">{m.replied_at ? `replied ${fmt(m.replied_at)}` : ""}</td></tr>)}</tbody></table></div>
            </Panel>
          )}
          {tab === "Notes" && (
            <Panel title="Admin notes" description="Private to super admins. Never exported to the user; deleted with the account.">
              <form className="mb-4 flex flex-col gap-2" onSubmit={(e) => { e.preventDefault(); if (note.trim()) void act(() => request(`/superadmin/users/${id}/notes`, { method: "POST", body: { text: note } }), notes.reload).then(() => setNote("")); }}>
                <Textarea value={note} onChange={(e) => setNote(e.target.value)} maxLength={2000} placeholder="Add a note" aria-label="New note" />
                <Button type="submit" size="sm" className="self-end" disabled={!note.trim()}>Add note</Button>
              </form>
              <ul className="flex flex-col gap-2">{(notes.data?.items ?? []).map((n) => (
                <li key={n.id} className="flex items-start justify-between gap-3 rounded-xl border p-3 text-sm"><div><p className="whitespace-pre-wrap">{n.text}</p><p className="mt-1 text-xs text-muted-foreground">{n.author} · {fmt(n.created_at)}</p></div>
                  <Button size="icon" variant="ghost" aria-label="Delete note" onClick={() => void act(() => request(`/superadmin/users/${id}/notes/${n.id}`, { method: "DELETE" }), notes.reload)}><Trash2 className="size-4" /></Button></li>
              ))}</ul>
            </Panel>
          )}
        </>
      )}
      {pending && u && <ConfirmDialog title={copy[pending.kind][0]} body={`${u.email}: ${copy[pending.kind][1]}`} confirmLabel={copy[pending.kind][2]} typed={pending.kind === "delete" ? u.email : undefined} onConfirm={() => void run(pending)} onCancel={() => setPending(null)} />}
    </div>
  );
}
