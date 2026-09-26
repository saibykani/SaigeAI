"use client";

import {
  BarChart3,
  Bell,
  Briefcase,
  FileText,
  LayoutDashboard,
  LogOut,
  Mail,
  Menu,
  Send,
  Settings,
  Sparkles,
  UserRound,
  Users,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/use-auth";
import { cn } from "@/utils/cn";

const NAV = [
  { href: "/", label: "Command Center", icon: LayoutDashboard },
  { href: "/profile", label: "Master Profile", icon: UserRound },
  { href: "/resumes", label: "Resumes", icon: FileText },
  { href: "/jobs", label: "Jobs", icon: Briefcase },
  { href: "/settings", label: "Automation & Privacy", icon: Settings },
];

const UPCOMING = [
  { label: "Applications", icon: Send, phase: 4 },
  { label: "Gmail", icon: Mail, phase: 5 },
  { label: "Recruiters", icon: Users, phase: 6 },
  { label: "Profile Sync", icon: Sparkles, phase: 7 },
  { label: "Analytics", icon: BarChart3, phase: 8 },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, loading, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!loading && !user) router.replace(`/login?next=${encodeURIComponent(pathname)}`);
  }, [loading, user, router, pathname]);

  useEffect(() => setOpen(false), [pathname]);

  if (loading || !user) {
    return <div className="grid min-h-screen place-items-center text-sm text-muted-foreground">Loading…</div>;
  }

  const nav = (
    <nav className="flex flex-1 flex-col gap-6 overflow-y-auto p-3">
      <ul className="flex flex-col gap-0.5">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <li key={href}>
              <Link
                href={href}
                className={cn(
                  "flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors",
                  active ? "bg-accent font-medium text-accent-foreground" : "text-muted-foreground hover:bg-muted hover:text-foreground",
                )}
              >
                <Icon className="size-4" />
                {label}
              </Link>
            </li>
          );
        })}
      </ul>
      <div>
        <p className="px-3 pb-1.5 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Coming next</p>
        <ul className="flex flex-col gap-0.5">
          {UPCOMING.map(({ label, icon: Icon, phase }) => (
            <li
              key={label}
              className="flex items-center gap-2.5 px-3 py-1.5 text-sm text-muted-foreground/70"
              title={`Arrives in Phase ${phase}`}
            >
              <Icon className="size-4" />
              {label}
              <span className="ml-auto text-[10px]">P{phase}</span>
            </li>
          ))}
        </ul>
      </div>
    </nav>
  );

  return (
    <div className="min-h-screen md:grid md:grid-cols-[240px_1fr]">
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r bg-card transition-transform md:sticky md:top-0 md:h-screen md:w-auto md:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex h-14 items-center justify-between border-b px-4">
          <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight">
            <span className="grid size-7 place-items-center rounded-md bg-primary text-xs font-bold text-primary-foreground">S</span>
            Saige AI
          </Link>
          <Button variant="ghost" size="icon" className="md:hidden" aria-label="Close menu" onClick={() => setOpen(false)}>
            <X />
          </Button>
        </div>
        {nav}
        <div className="border-t p-3">
          <p className="truncate px-1 text-sm font-medium">{user.name || user.email}</p>
          <p className="truncate px-1 text-xs text-muted-foreground">{user.email}</p>
          <Button
            variant="ghost"
            size="sm"
            className="mt-2 w-full justify-start"
            onClick={async () => {
              await logout();
              router.replace("/login");
            }}
          >
            <LogOut /> Sign out
          </Button>
        </div>
      </aside>
      {open && <div className="fixed inset-0 z-30 bg-black/40 md:hidden" onClick={() => setOpen(false)} />}

      <div className="flex min-w-0 flex-col">
        <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b bg-background/85 px-4 backdrop-blur md:px-8">
          <Button variant="ghost" size="icon" className="md:hidden" aria-label="Open menu" onClick={() => setOpen(true)}>
            <Menu />
          </Button>
          <p className="text-sm text-muted-foreground">AI Career Command Center</p>
          <Link href="/settings#notifications" className="ml-auto" aria-label="Notifications">
            <Bell className="size-4 text-muted-foreground hover:text-foreground" />
          </Link>
        </header>
        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 md:px-8 md:py-8">{children}</main>
      </div>
    </div>
  );
}

export function PageHeader({ title, description, actions }: { title: string; description?: string; actions?: React.ReactNode }) {
  return (
    <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
        {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function Notice({ tone = "info", children }: { tone?: "info" | "error" | "success" | "warning"; children: React.ReactNode }) {
  const styles = {
    info: "border-border bg-muted text-foreground",
    error: "border-destructive/40 bg-destructive/10 text-destructive",
    success: "border-success/40 bg-success/10 text-success",
    warning: "border-warning/40 bg-warning/10 text-warning",
  }[tone];
  return (
    <div role={tone === "error" ? "alert" : "status"} className={cn("rounded-md border px-3 py-2 text-sm", styles)}>
      {children}
    </div>
  );
}
