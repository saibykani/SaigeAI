"use client";

import {
  Activity, ArrowLeft, BarChart3, Megaphone, PanelLeftClose, PanelLeftOpen, RefreshCw, Search, ServerCog, ShieldAlert, Users, LayoutDashboard, type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { Loader3D } from "@/components/loader3d";
import { AdminCtx, Avatar, type AdminRange } from "@/components/super-admin";
import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { cn } from "@/utils/cn";

const GROUPS: { title: string; items: { href: string; label: string; icon: LucideIcon }[] }[] = [
  { title: "Insights", items: [
    { href: "/super-admin", label: "Overview", icon: LayoutDashboard },
    { href: "/super-admin/features", label: "Feature usage", icon: BarChart3 },
  ] },
  { title: "Customers", items: [{ href: "/super-admin/users", label: "Users", icon: Users }] },
  { title: "Operations", items: [
    { href: "/super-admin/activity", label: "Activity & audit", icon: Activity },
    { href: "/super-admin/health", label: "System health", icon: ServerCog },
  ] },
  { title: "Communication", items: [{ href: "/super-admin/announcements", label: "Announcements", icon: Megaphone }] },
];

const PRESETS = [{ v: "7", label: "Last 7 days" }, { v: "30", label: "Last 30 days" }, { v: "90", label: "Last 90 days" }, { v: "custom", label: "Custom range" }];
const KEY = "saige-admin-ui";

function GlobalSearch() {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const router = useRouter();
  const res = useApi<{ users: { id: string; email: string; name: string; role: string; is_active: boolean }[] }>(q.trim().length >= 2 ? `/superadmin/search?q=${encodeURIComponent(q.trim())}` : null);
  const hits = q.trim().length >= 2 ? res.data?.users ?? [] : [];
  return (
    <div className="relative w-full max-w-sm">
      <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
      <input value={q} onChange={(e) => { setQ(e.target.value); setOpen(true); }} onFocus={() => setOpen(true)} onBlur={() => setTimeout(() => setOpen(false), 150)}
        placeholder="Search users by name or email" aria-label="Search users" className="h-9 w-full rounded-lg border bg-transparent pl-9 pr-3 text-sm outline-none focus:border-foreground/40" />
      {open && q.trim().length >= 2 && (
        <ul className="absolute left-0 right-0 top-11 z-40 overflow-hidden rounded-xl border bg-card shadow-lg" role="listbox">
          {hits.length === 0 && <li className="px-3 py-2 text-sm text-muted-foreground">{res.loading ? "Searching…" : "No matching users"}</li>}
          {hits.map((u) => (
            <li key={u.id}>
              <button type="button" className="flex w-full items-center gap-3 px-3 py-2 text-left hover:bg-muted" onMouseDown={() => { setQ(""); router.push(`/super-admin/users/${u.id}`); }}>
                <Avatar name={u.name} email={u.email} size={28} />
                <span className="min-w-0"><span className="block truncate text-sm font-medium">{u.name || u.email}</span><span className="block truncate text-xs text-muted-foreground">{u.email} · {u.role}{u.is_active ? "" : " · disabled"}</span></span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function SuperAdminLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const [collapsed, setCollapsed] = useState(false);
  const [preset, setPreset] = useState("30");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");

  useEffect(() => {
    try {
      const s = JSON.parse(localStorage.getItem(KEY) || "{}") as { collapsed?: boolean; preset?: string; from?: string; to?: string };
      if (s.collapsed) setCollapsed(true);
      if (s.preset) setPreset(s.preset);
      if (s.from) setFrom(s.from);
      if (s.to) setTo(s.to);
    } catch { /* private mode */ }
  }, []);
  useEffect(() => {
    try { localStorage.setItem(KEY, JSON.stringify({ collapsed, preset, from, to })); } catch { /* private mode */ }
  }, [collapsed, preset, from, to]);
  useEffect(() => {
    if (!loading && !user) router.replace(`/login?next=${encodeURIComponent(pathname)}`);
  }, [loading, user, router, pathname]);

  const range = useMemo<AdminRange>(() => {
    if (preset === "custom" && from && to && from <= to) return { days: 0, from, to, qs: `date_from=${from}&date_to=${to}`, label: `${from} to ${to}` };
    const d = preset === "custom" ? 30 : Number(preset);
    return { days: d, from: "", to: "", qs: `days=${d}`, label: `Last ${d} days` };
  }, [preset, from, to]);

  if (loading || !user) return <div className="grid min-h-screen place-items-center"><Loader3D size={72} /></div>;
  if (!user.is_super_admin) {
    return (
      <div className="grid min-h-screen place-items-center px-6 text-center">
        <div className="max-w-sm">
          <ShieldAlert className="mx-auto size-10 text-muted-foreground" aria-hidden />
          <h1 className="mt-4 text-2xl font-semibold">403 · Restricted</h1>
          <p className="mt-2 text-sm text-muted-foreground">This area is reserved for the Saige AI owner. If you got here by mistake, head back to your dashboard.</p>
          <Link href="/" className="mt-5 inline-flex h-10 items-center rounded-full bg-primary px-5 text-sm font-medium text-primary-foreground">Back to app</Link>
        </div>
      </div>
    );
  }
  return (
    <AdminCtx.Provider value={range}>
      <div className="min-h-screen bg-background text-foreground">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b bg-background/90 px-3 backdrop-blur md:px-5">
          <button type="button" onClick={() => setCollapsed(!collapsed)} aria-label={collapsed ? "Expand navigation" : "Collapse navigation"} className="grid size-9 place-items-center rounded-lg text-muted-foreground hover:bg-muted">
            {collapsed ? <PanelLeftOpen className="size-4" /> : <PanelLeftClose className="size-4" />}
          </button>
          <span className="hidden text-sm font-semibold tracking-tight sm:inline">Saige AI · Admin</span>
          <div className="mx-auto flex w-full max-w-sm flex-1 justify-center"><GlobalSearch /></div>
          <div className="flex items-center gap-2">
            <select value={preset} onChange={(e) => setPreset(e.target.value)} aria-label="Date range" className="h-9 rounded-lg border bg-transparent px-2 text-sm">
              {PRESETS.map((p) => <option key={p.v} value={p.v}>{p.label}</option>)}
            </select>
            {preset === "custom" && (
              <>
                <input type="date" value={from} max={to || undefined} onChange={(e) => setFrom(e.target.value)} aria-label="From date" className="hidden h-9 rounded-lg border bg-transparent px-2 text-sm md:block" />
                <input type="date" value={to} min={from || undefined} onChange={(e) => setTo(e.target.value)} aria-label="To date" className="hidden h-9 rounded-lg border bg-transparent px-2 text-sm md:block" />
              </>
            )}
            <button type="button" onClick={() => window.dispatchEvent(new Event("saige:refresh"))} aria-label="Refresh" className="grid size-9 place-items-center rounded-lg border text-muted-foreground hover:bg-muted"><RefreshCw className="size-4" /></button>
            <Link href="/" className="hidden h-9 items-center gap-2 rounded-lg border px-3 text-sm font-medium hover:bg-muted sm:inline-flex"><ArrowLeft className="size-4" aria-hidden /> Back to app</Link>
          </div>
        </header>
        <div className="flex">
          <nav aria-label="Admin" className={cn("sticky top-14 hidden h-[calc(100vh-3.5rem)] shrink-0 overflow-y-auto border-r p-2 sm:block", collapsed ? "w-14" : "w-56")}>
            {GROUPS.map((g) => (
              <div key={g.title} className="mb-3">
                {!collapsed && <p className="px-3 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">{g.title}</p>}
                <ul className="flex flex-col gap-0.5">
                  {g.items.map(({ href, label, icon: Icon }) => {
                    const on = href === "/super-admin" ? pathname === href : pathname.startsWith(href);
                    return (
                      <li key={href}>
                        <Link href={href} title={label} aria-current={on ? "page" : undefined}
                          className={cn("flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm", collapsed && "justify-center px-0", on ? "bg-muted font-medium text-foreground" : "text-muted-foreground hover:bg-muted/60 hover:text-foreground")}>
                          <Icon className="size-4 shrink-0" aria-hidden />{!collapsed && label}
                        </Link>
                      </li>
                    );
                  })}
                </ul>
              </div>
            ))}
          </nav>
          <main className="min-w-0 flex-1 px-3 py-5 md:px-6">
            <nav aria-label="Admin sections" className="mb-4 flex gap-1 overflow-x-auto sm:hidden">
              {GROUPS.flatMap((g) => g.items).map(({ href, label }) => (
                <Link key={href} href={href} className={cn("shrink-0 rounded-lg px-3 py-1.5 text-sm", (href === "/super-admin" ? pathname === href : pathname.startsWith(href)) ? "bg-muted font-medium" : "text-muted-foreground")}>{label}</Link>
              ))}
              <Link href="/" className="shrink-0 rounded-lg px-3 py-1.5 text-sm text-muted-foreground">Back to app</Link>
            </nav>
            <div className="mx-auto w-full max-w-[1400px]">{children}</div>
          </main>
        </div>
      </div>
    </AdminCtx.Provider>
  );
}
