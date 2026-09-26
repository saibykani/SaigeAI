"use client";

import { Check, Globe, LifeBuoy, LogOut, MessageCircle, MessageSquareHeart, Puzzle } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { LANGUAGES, useT } from "@/components/i18n";
import { CONTACT_EMAIL } from "@/components/legal";
import { useAuth } from "@/hooks/use-auth";
import { cn } from "@/utils/cn";

export function initials(name: string) {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]?.toUpperCase()).join("") || "?";
}

/** Top-right avatar with the account menu: profile, alerts, language and help. */
export function UserMenu() {
  const { user, logout } = useAuth();
  const { lang, setLang, t } = useT();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [langOpen, setLangOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) { setLangOpen(false); return; }
    const close = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("mousedown", close); document.removeEventListener("keydown", esc); };
  }, [open]);

  if (!user) return null;
  const label = user.name || user.email;
  const items = [
    { href: "/alerts", label: "WhatsApp alerts", icon: MessageCircle, tone: "mint" },
    { href: "/settings#extension", label: "Browser extension", icon: Puzzle, tone: "teal" },
    { href: "/help", label: "Help & Docs", icon: LifeBuoy, tone: "orange" },
  ];
  const current = LANGUAGES.find((l) => l.id === lang)!;
  const avatar = (size: string) => (
    <span className={cn("grid shrink-0 place-items-center rounded-full font-semibold text-black", size)} style={{ background: "var(--tone-green)" }}>
      {initials(label)}
    </span>
  );

  return (
    <div className="relative" ref={ref}>
      <button onClick={() => setOpen((o) => !o)} aria-label="Account menu" aria-expanded={open}
        className="grid size-10 place-items-center rounded-full ring-2 ring-transparent transition hover:ring-[color-mix(in_srgb,var(--tone-green)_55%,transparent)]">
        {avatar("size-9 text-xs")}
      </button>
      {open && (
        <div className="animate-pop absolute right-0 top-12 z-50 w-72 overflow-hidden rounded-2xl border bg-card-solid shadow-[var(--shadow-lift)]">
          <Link href="/profile" onClick={() => setOpen(false)} className="flex items-center gap-3 border-b p-4 transition-colors hover:bg-muted/50">
            {avatar("size-11 text-sm")}
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold">{user.name || t("Your account")}</p>
              <p className="truncate text-xs text-muted-foreground">{user.email}</p>
            </div>
          </Link>
          <ul className="p-1.5">
            {items.map((it) => (
              <li key={it.href}>
                <Link href={it.href} onClick={() => setOpen(false)} className="flex items-center gap-3 rounded-xl px-3 py-2 text-sm transition-colors hover:bg-muted">
                  <it.icon className="size-4" style={{ color: `var(--tone-${it.tone})` }} /> {t(it.label)}
                </Link>
              </li>
            ))}
            <li>
              <button onClick={() => setLangOpen((o) => !o)} aria-expanded={langOpen} className="flex w-full items-center gap-3 rounded-xl px-3 py-2 text-sm transition-colors hover:bg-muted">
                <Globe className="size-4" style={{ color: "var(--tone-purple)" }} /> {t("Language")}
                <span className="ml-auto text-xs text-muted-foreground">{current.native}</span>
              </button>
              {langOpen && (
                <ul className="mb-1 ml-9 flex flex-col">
                  {LANGUAGES.map((l) => (
                    <li key={l.id}>
                      <button onClick={() => setLang(l.id)} className="flex w-full items-center justify-between rounded-lg px-3 py-1.5 text-sm hover:bg-muted">
                        <span>{l.native} <span className="text-xs text-muted-foreground">{l.id !== "en" ? l.name : ""}</span></span>
                        {lang === l.id && <Check className="size-4" style={{ color: "var(--tone-green)" }} />}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </li>
            <li>
              <a href={`mailto:${CONTACT_EMAIL}?subject=${encodeURIComponent("Saige AI feedback")}`} className="flex items-center gap-3 rounded-xl px-3 py-2 text-sm transition-colors hover:bg-muted">
                <MessageSquareHeart className="size-4" style={{ color: "var(--tone-yellow)" }} /> {t("Send feedback")}
              </a>
            </li>
            <li className="mt-1 border-t pt-1">
              <button onClick={async () => { setOpen(false); await logout(); router.replace("/login"); }}
                className="flex w-full items-center gap-3 rounded-xl px-3 py-2 text-sm transition-colors hover:bg-muted">
                <LogOut className="size-4" style={{ color: "var(--tone-red)" }} /> {t("Sign out")}
              </button>
            </li>
          </ul>
        </div>
      )}
    </div>
  );
}
