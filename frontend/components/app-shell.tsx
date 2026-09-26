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
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/use-auth";
import { cn } from "@/utils/cn";

type NavItem = { href: string; label: string; icon: LucideIcon; slot: number };

const NAV: NavItem[] = [
  { href: "/", label: "Command Center", icon: LayoutDashboard, slot: 1 },
  { href: "/profile", label: "Master Profile", icon: UserRound, slot: 7 },
  { href: "/resumes", label: "Resumes", icon: FileText, slot: 3 },
  { href: "/jobs", label: "Jobs", icon: Briefcase, slot: 2 },
  { href: "/settings", label: "Automation & Privacy", icon: Settings, slot: 5 },
];

const UPCOMING = [
  { label: "Applications", icon: Send, phase: 4 },
  { label: "Gmail", icon: Mail, phase: 5 },
  { label: "Recruiters", icon: Users, phase: 6 },
  { label: "Profile Sync", icon: Sparkles, phase: 7 },
  { label: "Analytics", icon: BarChart3, phase: 8 },
];

export function Logo({ className, onDark = false }: { className?: string; onDark?: boolean }) {
  return (
    <span className={cn("flex items-center gap-2.5 text-[17px] font-semibold tracking-tight", className)}>
      <span className={cn("animate-gradient relative grid size-8 place-items-center overflow-hidden rounded-[10px] text-white shadow-sm", onDark ? "bg-white/20 ring-1 ring-white/40" : "bg-[image:var(--brand-gradient)]")}>
        <Sparkles className="size-4" aria-hidden />
      </span>
      <span>
        Saige <span className={onDark ? "text-white/80" : "text-gradient animate-gradient"}>AI</span>
      </span>
    </span>
  );
}

function initials(name: string) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase())
    .join("");
}

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
    return (
      <div className="grid min-h-screen place-items-center">
        <div className="animate-pop flex flex-col items-center gap-3">
          <Logo />
          <div className="skeleton h-1.5 w-40 rounded-full" />
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen md:grid md:grid-cols-[264px_1fr]">
      <aside
        className={cn(
          "glass fixed inset-y-0 left-0 z-40 flex w-[264px] flex-col border-r transition-transform duration-300 md:sticky md:top-0 md:h-screen md:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex h-16 items-center justify-between px-5">
          <Link href="/" aria-label="Saige AI home">
            <Logo />
          </Link>
          <Button variant="ghost" size="icon" className="md:hidden" aria-label="Close menu" onClick={() => setOpen(false)}>
            <X />
          </Button>
        </div>

        <nav className="flex flex-1 flex-col gap-7 overflow-y-auto px-3 py-2">
          <ul className="flex flex-col gap-1">
            {NAV.map(({ href, label, icon: Icon, slot }) => {
              const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
              const color = `var(--series-${slot})`;
              return (
                <li key={href}>
                  <Link
                    href={href}
                    className={cn(
                      "group relative flex items-center gap-3 rounded-full px-3 py-2 text-sm transition-all duration-200",
                      active ? "bg-accent font-medium text-accent-foreground" : "text-muted-foreground hover:bg-muted hover:text-foreground",
                    )}
                  >
                    <span
                      className={cn(
                        "grid size-7 place-items-center rounded-lg transition-all duration-300",
                        active ? "text-white shadow-sm" : "group-hover:scale-110",
                      )}
                      style={active ? { background: color } : { color }}
                    >
                      <Icon className="size-4" aria-hidden />
                    </span>
                    {label}
                  </Link>
                </li>
              );
            })}
          </ul>
          <div>
            <p className="px-4 pb-2 text-[11px] font-medium uppercase tracking-[0.08em] text-muted-foreground">Coming next</p>
            <ul className="flex flex-col gap-0.5">
              {UPCOMING.map(({ label, icon: Icon, phase }) => (
                <li key={label} className="flex items-center gap-3 px-4 py-1.5 text-sm text-muted-foreground/70" title={`Arrives in Phase ${phase}`}>
                  <Icon className="size-4" aria-hidden />
                  {label}
                  <span className="ml-auto rounded-full bg-muted px-1.5 py-0.5 text-[10px] font-medium">P{phase}</span>
                </li>
              ))}
            </ul>
          </div>
        </nav>

        <div className="m-3 rounded-2xl border bg-card-solid/60 p-3">
          <div className="flex items-center gap-3">
            <span className="animate-gradient grid size-9 shrink-0 place-items-center rounded-full bg-[image:var(--brand-gradient)] text-xs font-semibold text-white">
              {initials(user.name || user.email)}
            </span>
            <div className="min-w-0">
              <p className="truncate text-sm font-medium">{user.name || user.email}</p>
              <p className="truncate text-xs text-muted-foreground">{user.email}</p>
            </div>
          </div>
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
      {open && <div className="fixed inset-0 z-30 bg-black/40 backdrop-blur-sm md:hidden" onClick={() => setOpen(false)} />}

      <div className="flex min-w-0 flex-col">
        <header className="glass sticky top-0 z-20 flex h-16 items-center gap-3 border-b px-4 md:px-10">
          <Button variant="ghost" size="icon" className="md:hidden" aria-label="Open menu" onClick={() => setOpen(true)}>
            <Menu />
          </Button>
          <p className="text-sm text-muted-foreground">AI Career Command Center</p>
          <Link
            href="/settings#notifications"
            className="ml-auto grid size-10 place-items-center rounded-full text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            aria-label="Notifications"
          >
            <Bell className="size-[18px]" />
          </Link>
        </header>
        {/* key on pathname replays the entrance animation on every navigation */}
        <main key={pathname} className="animate-rise mx-auto w-full max-w-7xl flex-1 px-4 py-8 md:px-10 md:py-10">
          {children}
        </main>
      </div>
    </div>
  );
}

export function PageHeader({ title, description, actions }: { title: string; description?: string; actions?: React.ReactNode }) {
  return (
    <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight md:text-[34px]">{title}</h1>
        {description && <p className="mt-2 max-w-2xl text-[15px] text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function Notice({ tone = "info", children }: { tone?: "info" | "error" | "success" | "warning"; children: React.ReactNode }) {
  const styles = {
    info: "border-border bg-muted text-foreground",
    error: "border-destructive/30 bg-destructive/10 text-destructive",
    success: "border-success/30 bg-success/10 text-success",
    warning: "border-warning/30 bg-warning/10 text-warning",
  }[tone];
  return (
    <div role={tone === "error" ? "alert" : "status"} className={cn("animate-rise rounded-xl border px-4 py-2.5 text-sm", styles)}>
      {children}
    </div>
  );
}
