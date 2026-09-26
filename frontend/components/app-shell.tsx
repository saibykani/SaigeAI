"use client";

import {
  Briefcase,
  createLucideIcon,
  FileText,
  LayoutDashboard,
  LifeBuoy,
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

import { Wordmark } from "@/components/brand";
import { useT } from "@/components/i18n";
import { Loader3D } from "@/components/loader3d";
import { NotificationBell } from "@/components/notification-bell";
import { UserMenu } from "@/components/user-menu";
import { ThemeSwitcher } from "@/components/theme";
import { AssistantBubble } from "@/components/assistant";
import { Effects } from "@/components/effects";
import { Button } from "@/components/ui/button";
import { useLiveSync } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { cn } from "@/utils/cn";

// lucide dropped brand icons, so the LinkedIn glyph is defined here.
const Linkedin = createLucideIcon("Linkedin", [
  ["path", { d: "M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z", key: "k1" }],
  ["rect", { width: "4", height: "12", x: "2", y: "9", key: "k2" }],
  ["circle", { cx: "4", cy: "4", r: "2", key: "k3" }],
]);

type Tone = "green" | "orange" | "yellow" | "purple" | "red" | "mint" | "teal" | "lime";
type NavItem = { href: string; label: string; icon: LucideIcon; tone: Tone; tabs?: { href: string; label: string }[] };

// Pages that show the same kind of data share one sidebar entry and switch with tabs at the top.
const NAV: NavItem[] = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard, tone: "green", tabs: [{ href: "/", label: "Overview" }, { href: "/analytics", label: "Analytics" }] },
  { href: "/jobs", label: "Jobs", icon: Briefcase, tone: "orange" },
  { href: "/applications", label: "Applications", icon: Send, tone: "yellow", tabs: [{ href: "/applications", label: "Applications" }, { href: "/interviews", label: "Interviews" }] },
  { href: "/resumes", label: "Resumes", icon: FileText, tone: "purple" },
  { href: "/recruiters", label: "Recruiters", icon: Users, tone: "lime" },
  { href: "/inbox", label: "Inbox", icon: Mail, tone: "teal" },
  { href: "/assistant", label: "Saige AI", icon: Sparkles, tone: "purple" },
  { href: "/profiles", label: "LinkedIn & Naukri", icon: Linkedin, tone: "mint", tabs: [{ href: "/profiles", label: "LinkedIn & Naukri" }, { href: "/profile-sync", label: "Resume sync" }] },
  { href: "/alerts", label: "Settings", icon: Settings, tone: "red", tabs: [
    { href: "/alerts", label: "Alerts & templates" }, { href: "/integrations", label: "Integrations" },
    { href: "/agent", label: "Agent" }, { href: "/settings", label: "Automation & privacy" }] },
  { href: "/help", label: "Help & Docs", icon: LifeBuoy, tone: "green" },
  { href: "/profile", label: "Profile", icon: UserRound, tone: "mint" },
];

const matches = (href: string, pathname: string) => (href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`));

/** The sidebar entry a path belongs to (its own page or one of its tabs). */
function sectionFor(pathname: string): NavItem | undefined {
  const all = NAV.flatMap((n) => [n.href, ...(n.tabs ?? []).map((t) => t.href)].map((href) => ({ href, n })));
  return all.sort((a, b) => b.href.length - a.href.length).find(({ href }) => matches(href, pathname))?.n;
}

/** Tabs across the top of merged sections (e.g. Applications · Interviews). */
function SectionTabs({ pathname }: { pathname: string }) {
  const { t } = useT();
  const section = sectionFor(pathname);
  if (!section?.tabs) return null;
  const current = [...section.tabs].sort((a, b) => b.href.length - a.href.length).find((x) => matches(x.href, pathname));
  if (!current || pathname !== current.href) return null; // detail pages (e.g. /applications/123) keep their own header
  return (
    <nav aria-label={t(section.label)} className="mb-6 inline-flex rounded-full border bg-muted/50 p-1 text-sm">
      {section.tabs.map((tab) => (
        <Link key={tab.href} href={tab.href} aria-current={tab.href === current.href ? "page" : undefined}
          className={cn("rounded-full px-4 py-1.5 transition-colors", tab.href === current.href ? "font-medium text-[#0b0b0c] shadow-sm" : "text-muted-foreground hover:text-foreground")}
          style={tab.href === current.href ? { background: `var(--tone-${section.tone})` } : undefined}>
          {t(tab.label)}
        </Link>
      ))}
    </nav>
  );
}

// Features announced in the sidebar before they ship. Empty once every phase has landed.
const UPCOMING: { label: string; icon: LucideIcon; phase: number }[] = [];

export function Logo({ className, onDark = false }: { className?: string; onDark?: boolean }) {
  return (
    <span className={cn("flex items-center", className)}>
      <Wordmark className={cn("text-[19px]", onDark && "text-white")} />
    </span>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const { t } = useT();
  const router = useRouter();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  useLiveSync(Boolean(user));

  useEffect(() => {
    if (!loading && !user) router.replace(`/login?next=${encodeURIComponent(pathname)}`);
  }, [loading, user, router, pathname]);

  useEffect(() => setOpen(false), [pathname]);

  if (loading || !user) {
    return (
      <div className="grid min-h-screen place-items-center">
        <div className="animate-pop flex flex-col items-center gap-6">
          <Loader3D size={84} />
          <Logo />
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen md:grid md:grid-cols-[264px_1fr]">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[60] focus:rounded-full focus:bg-primary focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-primary-foreground">
        Skip to content
      </a>
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
            {NAV.map(({ href, label, icon: Icon, tone }) => {
              const active = sectionFor(pathname)?.href === href;
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
                        active ? "text-[#0b0b0c] shadow-sm" : "group-hover:scale-110",
                      )}
                      style={active ? { background: `var(--tone-${tone})`, boxShadow: `0 4px 14px -4px var(--tone-${tone})` } : { color: `var(--tone-${tone})` }}
                    >
                      <Icon className="size-4" aria-hidden />
                    </span>
                    {t(label)}
                  </Link>
                </li>
              );
            })}
          </ul>
          {UPCOMING.length > 0 && (
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
          )}
        </nav>

      </aside>
      {open && <div className="fixed inset-0 z-30 bg-black/40 backdrop-blur-sm md:hidden" onClick={() => setOpen(false)} />}

      <div className="relative flex min-w-0 flex-col">
        {/* One soft glow in the current section's colour (never mixed colours). */}
        <div aria-hidden className="pointer-events-none absolute inset-x-0 top-0 -z-0 h-[420px] transition-colors duration-700"
          style={{ background: `radial-gradient(60% 100% at 30% 0%, color-mix(in srgb, var(--tone-${sectionFor(pathname)?.tone ?? "green"}) 16%, transparent), transparent 70%)` }} />
        <header className="glass sticky top-0 z-20 flex h-16 items-center gap-3 border-b px-4 md:px-10">
          <Button variant="ghost" size="icon" className="md:hidden" aria-label="Open menu" onClick={() => setOpen(true)}>
            <Menu />
          </Button>
          <p className="hidden text-sm text-muted-foreground sm:block">{t("Saige AI · your AI job search partner")}</p>
          <div className="ml-auto" />
          <ThemeSwitcher />
          <NotificationBell />
          <UserMenu />
        </header>
        {/* key on pathname replays the entrance animation on every navigation */}
        <main id="main" tabIndex={-1} key={pathname} className="animate-rise relative outline-none mx-auto w-full max-w-7xl flex-1 px-4 py-8 md:px-10 md:py-10">
          <SectionTabs pathname={pathname} />
          {children}
        </main>
        {pathname !== "/assistant" && <AssistantBubble />}
        <Effects tone={sectionFor(pathname)?.tone ?? "green"} />
      </div>
    </div>
  );
}

export function PageHeader({ title, description, actions }: { title: string; description?: string; actions?: React.ReactNode }) {
  const pathname = usePathname();
  const tone = sectionFor(pathname)?.tone ?? "green";
  return (
    <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <span aria-hidden className="animate-grow-x mb-3 block h-1 w-10 rounded-full" style={{ background: `var(--tone-${tone})`, boxShadow: `0 0 16px var(--tone-${tone})` }} />
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
