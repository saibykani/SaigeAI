"use client";

import { Briefcase, Search, Plug, LayoutDashboard, LifeBuoy, Mail, Menu, ScanText, Send, Settings, UserRound, Users, X, createLucideIcon, type LucideIcon } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Wordmark } from "@/components/brand";
import { useT } from "@/components/i18n";
import { Loader3D } from "@/components/loader3d";
import { NotificationBell } from "@/components/notification-bell";
import { UserMenu } from "@/components/user-menu";
import { AssistantBubble, Orb } from "@/components/assistant";
import { Celebrate } from "@/components/celebrate";
import { Button } from "@/components/ui/button";
import { useLiveSync } from "@/hooks/use-api";
import { request } from "@/services/api";
import { useAuth } from "@/hooks/use-auth";
import { cn } from "@/utils/cn";

// lucide dropped brand icons, so the LinkedIn glyph is defined here.
const Linkedin = createLucideIcon("Linkedin", [
  ["path", { d: "M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z", key: "k1" }],
  ["rect", { width: "4", height: "12", x: "2", y: "9", key: "k2" }],
  ["circle", { cx: "4", cy: "4", r: "2", key: "k3" }],
]);

type Tone = "green" | "orange" | "yellow" | "purple" | "red" | "mint" | "teal" | "lime";
type NavItem = { href: string; label: string; icon: LucideIcon; tone: Tone; group: string; tabs?: { href: string; label: string }[] };

// Pages that show the same kind of data share one sidebar entry and switch with tabs at the top.
const NAV: NavItem[] = [
  { group: "Home", href: "/", label: "Dashboard", icon: LayoutDashboard, tone: "green", tabs: [
    { href: "/", label: "Overview" }, { href: "/goals", label: "Weekly goals" }, { href: "/analytics", label: "Analytics" }, { href: "/activity", label: "Activity log" }] },
  { group: "Job search", href: "/jobs", label: "Find jobs", icon: Briefcase, tone: "orange", tabs: [
    { href: "/jobs", label: "Jobs for you" }, { href: "/careers", label: "Career portals" }, { href: "/salary", label: "Salary insights" }] },
  { group: "Job search", href: "/applications", label: "Track applications", icon: Send, tone: "yellow", tabs: [
    { href: "/applications", label: "Applications" }, { href: "/followups", label: "Follow-ups" }, { href: "/interviews", label: "Interviews" }] },
  { group: "Resume & ATS", href: "/resumes", label: "Resume & ATS", icon: ScanText, tone: "purple", tabs: [
    { href: "/resumes", label: "My resumes & ATS coach" }, { href: "/studio", label: "Resume builder" }, { href: "/studio/analyze", label: "JD analyzer" },
    { href: "/studio/apply", label: "Apply by email" }] },
  { group: "Network", href: "/recruiters", label: "Recruiters", icon: Users, tone: "lime" },
  { group: "Network", href: "/inbox", label: "Inbox", icon: Mail, tone: "teal" },
  { group: "Network", href: "/profiles", label: "LinkedIn & Naukri", icon: Linkedin, tone: "mint", tabs: [
    { href: "/profiles", label: "Profile suggestions" }, { href: "/linkedin", label: "Daily posts" }, { href: "/profile-sync", label: "Resume sync" }] },
  { group: "Account", href: "/profile", label: "Profile", icon: UserRound, tone: "mint" },
  { group: "Account", href: "/integrations", label: "Integrations", icon: Plug, tone: "orange" },
  { group: "Account", href: "/alerts", label: "Settings", icon: Settings, tone: "red", tabs: [
    { href: "/alerts", label: "Alerts & templates" }, { href: "/agent", label: "Agent" }, { href: "/settings", label: "Automation & privacy" }] },
  { group: "Account", href: "/help", label: "Help & Guide", icon: LifeBuoy, tone: "green" },
];
const GROUPS = ["Home", "Job search", "Resume & ATS", "Network", "Account"];

const matches = (href: string, pathname: string) => (href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`));

/** The sidebar entry a path belongs to (its own page or one of its tabs). */
function sectionFor(pathname: string): NavItem | undefined {
  const all = NAV.flatMap((n) => [n.href, ...(n.tabs ?? []).map((t) => t.href)].map((href) => ({ href, n })));
  return all.sort((a, b) => b.href.length - a.href.length).find(({ href }) => matches(href, pathname))?.n;
}

/** Sub-pages of a section as a side menu inside the page (a strip of links on small screens). */
function SubNav({ pathname, children }: { pathname: string; children: React.ReactNode }) {
  const { t } = useT();
  const section = sectionFor(pathname);
  const current = section?.tabs && [...section.tabs].sort((a, b) => b.href.length - a.href.length).find((x) => matches(x.href, pathname));
  if (!section?.tabs || !current || pathname !== current.href) return <>{children}</>; // detail pages keep their own header
  return (
    <div className="lg:grid lg:grid-cols-[210px_minmax(0,1fr)] lg:gap-8">
      <nav aria-label={t(section.label)} className="mb-6 lg:mb-0">
        <div className="lg:sticky lg:top-24">
          <p className="mb-2 hidden px-3 text-xs font-medium uppercase tracking-[0.08em] text-muted-foreground lg:block">{t(section.label)}</p>
          <ul className="flex gap-2 overflow-x-auto lg:flex-col lg:gap-1">
            {section.tabs.map((tab) => {
              const on = tab.href === current.href;
              return (
                <li key={tab.href} className="shrink-0">
                  <Link href={tab.href} aria-current={on ? "page" : undefined}
                    className={cn("block rounded-xl px-3.5 py-2 text-sm",
                      on ? "bg-accent font-medium text-primary shadow-[inset_3px_0_0_var(--primary)]" : "text-muted-foreground ring-1 ring-border hover:bg-muted hover:text-foreground lg:ring-0")}>
                    {t(tab.label)}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      </nav>
      <div className="min-w-0">{children}</div>
    </div>
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

  // First run: a new user sets up the profile (resume upload) before using the rest of Saige.
  useEffect(() => {
    if (!user || pathname === "/welcome" || pathname.startsWith("/help")) return;
    let skipped = false;
    try { skipped = localStorage.getItem("saige-welcome-done") === "1"; } catch { /* private mode */ }
    if (skipped) return;
    void request<{ needs_setup: boolean }>("/profile/setup-status").then((s) => { if (s.needs_setup) router.replace("/welcome"); }).catch(() => undefined);
  }, [user, pathname, router]);

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
          "fixed inset-y-0 left-0 z-40 flex w-[264px] flex-col border-r bg-card transition-transform duration-300 md:sticky md:top-0 md:h-screen md:translate-x-0",
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

        <nav className="flex flex-1 flex-col gap-1 overflow-y-auto px-3 py-3">
          {GROUPS.map((g) => (
            <div key={g}>
              <p className="px-4 pb-1 pt-3 text-[11px] font-medium uppercase tracking-[0.08em] text-muted-foreground/70">{t(g)}</p>
              
              <ul className="flex flex-col gap-1">
                {NAV.filter((n) => n.group === g).map(({ href, label, icon: Icon }) => {
                  const active = sectionFor(pathname)?.href === href;
                  return (
                    <li key={href}>
                      <Link
                        href={href}
                        className={cn(
                          "group relative flex items-center gap-3.5 rounded-xl px-4 py-2.5 text-[15px] transition-colors",
                          active ? "bg-primary font-medium text-primary-foreground" : "text-foreground/80 hover:bg-muted hover:text-foreground",
                        )}
                      >
                        <Icon className="size-5 shrink-0" aria-hidden />
                        {t(label)}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
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
        <Link href="/profile" className="m-3 flex items-center gap-3 rounded-2xl border p-3 hover:bg-muted">
          <span className="grid size-10 shrink-0 place-items-center rounded-full bg-primary text-sm font-medium text-primary-foreground">
            {(user.name || user.email || "?").charAt(0).toUpperCase()}
          </span>
          <span className="min-w-0">
            <span className="block truncate text-sm">{user.name || "My profile"}</span>
            <span className="block truncate text-xs text-muted-foreground">{user.email}</span>
          </span>
        </Link>
      </aside>
      {open && <div className="fixed inset-0 z-30 bg-black/40 backdrop-blur-sm md:hidden" onClick={() => setOpen(false)} />}

      <div className="relative flex min-w-0 flex-col">
        <header className="sticky top-0 z-20 flex h-[72px] items-center gap-3 bg-background/95 px-4 backdrop-blur md:px-10">
          <Button variant="ghost" size="icon" className="md:hidden" aria-label="Open menu" onClick={() => setOpen(true)}>
            <Menu />
          </Button>
          <span className="hidden text-xl lg:inline">{t(sectionFor(pathname)?.label ?? "Saige AI")}</span>
          <form className="ml-auto hidden w-full max-w-md md:block" onSubmit={(e) => { e.preventDefault(); const q = new FormData(e.currentTarget).get("q"); router.push(`/jobs${q ? `?q=${encodeURIComponent(String(q))}` : ""}`); }}>
            <label className="flex h-11 items-center gap-2.5 rounded-xl border bg-card px-4 text-sm">
              <Search className="size-5 text-muted-foreground" aria-hidden />
              <input name="q" placeholder={t("Search jobs, e.g. QA engineer in Hyderabad")} className="w-full bg-transparent outline-none placeholder:text-muted-foreground" />
            </label>
          </form>
          <div className="ml-auto md:hidden" />
          <Link href="/assistant" className="saige-cta group flex items-center gap-2 rounded-full border py-1 pl-1 pr-3.5 text-sm font-medium transition-colors hover:bg-muted"
            style={{ borderColor: "color-mix(in srgb, #ffc98a 40%, transparent)" }}>
            <Orb size={28} />
            <span className="hidden sm:inline">{t("Ask Saige AI")}</span>
          </Link>
          <NotificationBell />
          <UserMenu />
        </header>
        {/* key on pathname replays the entrance animation on every navigation */}
        <main id="main" tabIndex={-1} key={pathname} className="animate-rise relative outline-none mx-auto w-full max-w-7xl flex-1 px-4 py-8 md:px-10 md:py-10">
          <SubNav pathname={pathname}>{children}</SubNav>
        </main>
        {pathname !== "/assistant" && <AssistantBubble />}
        <Celebrate />
      </div>
    </div>
  );
}

export function PageHeader({ title, description, actions }: { title: string; description?: string; actions?: React.ReactNode }) {
  return (
    <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="text-3xl font-light tracking-[-0.03em] md:text-[44px] md:leading-tight">{title}</h1>
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
