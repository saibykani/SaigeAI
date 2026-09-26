"use client";

import { LifeBuoy, LogOut, Settings, UserRound } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { useAuth } from "@/hooks/use-auth";

export function initials(name: string) {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]?.toUpperCase()).join("") || "?";
}

/** Top-right avatar with the account menu. */
export function UserMenu() {
  const { user, logout } = useAuth();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("mousedown", close); document.removeEventListener("keydown", esc); };
  }, [open]);

  if (!user) return null;
  const label = user.name || user.email;
  const items = [
    { href: "/profile", label: "Master profile", icon: UserRound, tone: "green" },
    { href: "/settings", label: "Automation & privacy", icon: Settings, tone: "purple" },
    { href: "/help", label: "Help & docs", icon: LifeBuoy, tone: "orange" },
  ];

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        aria-label="Account menu"
        aria-expanded={open}
        className="grid size-10 place-items-center rounded-full ring-2 ring-transparent transition hover:ring-[color-mix(in_srgb,var(--tone-green)_55%,transparent)]"
      >
        <span className="grid size-9 place-items-center rounded-full text-xs font-semibold text-black" style={{ background: "linear-gradient(135deg, var(--tone-green), var(--tone-mint))" }}>
          {initials(label)}
        </span>
      </button>
      {open && (
        <div className="animate-pop absolute right-0 top-12 z-50 w-64 overflow-hidden rounded-2xl border bg-card-solid shadow-[var(--shadow-lift)]">
          <div className="flex items-center gap-3 border-b p-4">
            <span className="grid size-10 shrink-0 place-items-center rounded-full text-sm font-semibold text-black" style={{ background: "linear-gradient(135deg, var(--tone-green), var(--tone-mint))" }}>
              {initials(label)}
            </span>
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold">{user.name || "Your account"}</p>
              <p className="truncate text-xs text-muted-foreground">{user.email}</p>
            </div>
          </div>
          <ul className="p-1.5">
            {items.map((it) => (
              <li key={it.href}>
                <Link href={it.href} onClick={() => setOpen(false)} className="flex items-center gap-3 rounded-xl px-3 py-2 text-sm transition-colors hover:bg-muted">
                  <it.icon className="size-4" style={{ color: `var(--tone-${it.tone})` }} /> {it.label}
                </Link>
              </li>
            ))}
            <li className="mt-1 border-t pt-1">
              <button
                onClick={async () => { setOpen(false); await logout(); router.replace("/login"); }}
                className="flex w-full items-center gap-3 rounded-xl px-3 py-2 text-sm transition-colors hover:bg-muted"
              >
                <LogOut className="size-4" style={{ color: "var(--tone-red)" }} /> Sign out
              </button>
            </li>
          </ul>
        </div>
      )}
    </div>
  );
}
