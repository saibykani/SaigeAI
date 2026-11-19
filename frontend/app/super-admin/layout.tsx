"use client";

import { Activity, ArrowLeft, BarChart3, Megaphone, ServerCog, ShieldAlert, Users, LayoutDashboard, type LucideIcon } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import { Loader3D } from "@/components/loader3d";
import { useAuth } from "@/hooks/use-auth";
import { cn } from "@/utils/cn";

const TABS: { href: string; label: string; icon: LucideIcon }[] = [
  { href: "/super-admin", label: "Overview", icon: LayoutDashboard },
  { href: "/super-admin/users", label: "Users", icon: Users },
  { href: "/super-admin/activity", label: "Activity & audit", icon: Activity },
  { href: "/super-admin/features", label: "Feature usage", icon: BarChart3 },
  { href: "/super-admin/health", label: "System health", icon: ServerCog },
  { href: "/super-admin/announcements", label: "Announcements", icon: Megaphone },
];

export default function SuperAdminLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  useEffect(() => {
    if (!loading && !user) router.replace(`/login?next=${encodeURIComponent(pathname)}`);
  }, [loading, user, router, pathname]);

  if (loading || !user) return <div className="grid min-h-screen place-items-center"><Loader3D size={72} /></div>;
  if (!user.is_super_admin) {
    return (
      <div className="grid min-h-screen place-items-center px-6 text-center">
        <div className="max-w-sm">
          <ShieldAlert className="mx-auto size-10 text-red-400" aria-hidden />
          <h1 className="mt-4 text-2xl font-semibold">403 · Super admin only</h1>
          <p className="mt-2 text-sm text-muted-foreground">This area is reserved for the Saige AI owner. If you got here by mistake, head back to your dashboard.</p>
          <Link href="/" className="mt-5 inline-flex h-10 items-center rounded-full bg-primary px-5 text-sm font-medium text-primary-foreground">Back to app</Link>
        </div>
      </div>
    );
  }
  return (
    <div className="min-h-screen bg-black text-foreground">
      <header className="sticky top-0 z-30 flex h-14 items-center justify-between gap-3 border-b border-red-500/30 bg-black/90 px-4 backdrop-blur md:px-6">
        <div className="flex items-center gap-3">
          <span className="inline-flex items-center gap-1.5 rounded-full border border-red-500/50 bg-red-500/10 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-red-400">
            <ShieldAlert className="size-3.5" aria-hidden /> Super Admin
          </span>
          <span className="hidden text-sm text-muted-foreground sm:inline">Control room</span>
        </div>
        <Link href="/" className="inline-flex h-9 items-center gap-2 rounded-full border px-4 text-sm font-medium hover:bg-muted"><ArrowLeft className="size-4" aria-hidden /> Back to app</Link>
      </header>
      <div className="mx-auto grid w-full max-w-[1500px] gap-6 px-4 py-6 md:grid-cols-[220px_1fr] md:px-6">
        <nav aria-label="Super admin" className="md:sticky md:top-20 md:self-start">
          <ul className="flex gap-2 overflow-x-auto md:flex-col md:gap-1">
            {TABS.map(({ href, label, icon: Icon }) => {
              const on = href === "/super-admin" ? pathname === href : pathname.startsWith(href);
              return (
                <li key={href} className="shrink-0">
                  <Link href={href} aria-current={on ? "page" : undefined}
                    className={cn("flex items-center gap-2.5 rounded-xl px-3.5 py-2.5 text-sm font-medium", on ? "bg-red-500/15 text-red-300" : "text-muted-foreground hover:bg-muted hover:text-foreground")}>
                    <Icon className="size-4" aria-hidden /> {label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
        <main className="min-w-0">{children}</main>
      </div>
    </div>
  );
}
