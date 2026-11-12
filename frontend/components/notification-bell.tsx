"use client";

import { Bell } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { useT } from "@/components/i18n";
import { request } from "@/services/api";
import type { AppNotification } from "@/types/api";
import { cn } from "@/utils/cn";

function ago(iso: string): string {
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return "a few sec";
  if (s < 3600) return `${Math.floor(s / 60)} min`;
  if (s < 86400) return `${Math.floor(s / 3600)} h`;
  return `${Math.floor(s / 86400)} d`;
}

const FILTERS = [{ id: "all", label: "All" }, { id: "apps", label: "Applications" }, { id: "jobs", label: "Jobs for you" }, { id: "account", label: "Account" }] as const;
type Filter = (typeof FILTERS)[number]["id"];
const GROUP: [RegExp, Filter][] = [[/^(application|auto_apply|status_change|interview|followup|outreach|recruiter|reply|email|cold|gmail)/, "apps"],
  [/^(job|high_match|career|morning)/, "jobs"]];
const groupOf = (kind?: string): Filter => GROUP.find(([re]) => re.test(kind ?? ""))?.[1] ?? "account";
function meta(kind?: string): { icon: string; bg: string } {
  const k = kind ?? "";
  if (/high_match|job|career/.test(k)) return { icon: "⭐", bg: "color-mix(in srgb, #f5b400 16%, transparent)" };
  if (/interview/.test(k)) return { icon: "📅", bg: "color-mix(in srgb, #8e44d6 14%, transparent)" };
  if (/application|auto_apply|status/.test(k)) return { icon: "📨", bg: "color-mix(in srgb, var(--primary) 12%, transparent)" };
  if (/outreach|recruiter|reply|email|followup|cold|gmail/.test(k)) return { icon: "✉️", bg: "color-mix(in srgb, #0b8bb0 14%, transparent)" };
  if (/profile|naukri|linkedin|coach/.test(k)) return { icon: "🎉", bg: "color-mix(in srgb, #1e8e3e 14%, transparent)" };
  return { icon: "🔔", bg: "var(--muted)" };
}

/** Header bell: unread badge (polled every minute), dropdown with the latest notifications. */
export function NotificationBell() {
  const router = useRouter();
  const { t } = useT();
  const [open, setOpen] = useState(false);
  const [ring, setRing] = useState(0);
  const [unread, setUnread] = useState(0);
  const [items, setItems] = useState<AppNotification[] | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const shown = items?.filter((n) => filter === "all" || groupOf(n.kind) === filter);
  const ref = useRef<HTMLDivElement>(null);

  const refreshCount = useCallback(async () => {
    try {
      setUnread((await request<{ unread: number }>("/notifications/unread-count")).unread);
    } catch {
      /* signed out or offline: keep the last count */
    }
  }, []);

  useEffect(() => {
    void refreshCount();
    const t = setInterval(refreshCount, 60_000);
    return () => clearInterval(t);
  }, [refreshCount]);

  useEffect(() => {
    if (!open) return;
    void request<AppNotification[]>("/notifications").then((l) => setItems(l.slice(0, 40))).catch(() => setItems([]));
    const close = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("mousedown", close); document.removeEventListener("keydown", esc); };
  }, [open]);

  async function openItem(n: AppNotification) {
    if (!n.read) {
      await request(`/notifications/${n.id}/read`, { method: "POST" }).catch(() => undefined);
      setUnread((u) => Math.max(0, u - 1));
    }
    setOpen(false);
    if (n.link) router.push(n.link);
  }

  async function readAll() {
    await request("/notifications/read-all", { method: "POST" });
    setUnread(0);
    setItems((l) => l?.map((n) => ({ ...n, read: true })) ?? l);
  }

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => { setOpen((o) => !o); setRing((r) => r + 1); }}
        className="relative grid size-11 place-items-center rounded-xl border bg-card text-foreground transition-colors hover:bg-muted hover:text-foreground"
        aria-label={unread ? `Notifications, ${unread} unread` : "Notifications"}
        aria-expanded={open}
      >
        <Bell key={ring} className={cn("size-[18px]", ring > 0 && "bell-ring")} />
        {unread > 0 && (
          <span className="animate-pop absolute right-1.5 top-1.5 grid min-w-4 place-items-center rounded-full px-1 text-[10px] font-semibold leading-4 text-primary-foreground bg-primary">
            {unread > 99 ? "99+" : unread}
          </span>
        )}
      </button>
      {open && (
        <div className="drop-3d absolute right-0 top-12 z-50 flex max-h-[34rem] w-[min(28rem,calc(100vw-2rem))] flex-col overflow-hidden rounded-3xl border bg-card-solid shadow-[var(--shadow-lift)]">
          <div className="flex items-center justify-between px-5 pb-3 pt-4">
            <p className="text-lg font-medium">{t("Activity")}</p>
            <button onClick={readAll} disabled={!unread} className="text-sm text-primary hover:underline disabled:opacity-40">{t("Mark all read")}</button>
          </div>
          <div className="flex gap-2 overflow-x-auto border-y px-5 py-3">
            {FILTERS.map((f) => (
              <button key={f.id} onClick={() => setFilter(f.id)} aria-pressed={filter === f.id}
                className={cn("shrink-0 rounded-full border px-3.5 py-1.5 text-sm", filter === f.id ? "border-primary bg-primary text-primary-foreground" : "hover:bg-muted")}>
                {t(f.label)}
              </button>
            ))}
          </div>
          <ul className="flex-1 divide-y overflow-y-auto">
            {items === null && <li className="p-4"><div className="skeleton h-10 rounded-xl" /></li>}
            {shown?.length === 0 && <li className="p-8 text-center text-sm text-muted-foreground">{t("You're all caught up.")}</li>}
            {shown?.map((n) => {
              const m = meta(n.kind);
              return (
                <li key={n.id}>
                  <button onClick={() => openItem(n)} className={cn("flex w-full gap-3.5 px-5 py-4 text-left hover:bg-muted/60", !n.read && "bg-accent/30")}>
                    <span className="grid size-11 shrink-0 place-items-center rounded-xl text-lg" style={{ background: m.bg }} aria-hidden>{m.icon}</span>
                    <span className="min-w-0 flex-1">
                      <span className="block font-medium">{n.title}</span>
                      {n.body && <span className="line-clamp-2 block text-sm text-muted-foreground">{n.body}</span>}
                      {!!n.details?.length && (
                        <span className="mt-1.5 block text-xs text-muted-foreground">{n.details.slice(0, 2).map((d) => `${d.platform} · ${d.field}: ${d.after}`).join("  ·  ")}</span>
                      )}
                      <span className="mt-2 block text-xs text-muted-foreground">{ago(n.created_at)} ago</span>
                    </span>
                    {!n.read && <span className="mt-2 size-2 shrink-0 rounded-full bg-primary" aria-label="unread" />}
                  </button>
                </li>
              );
            })}
          </ul>
          <Link href="/alerts" onClick={() => setOpen(false)} className="border-t py-3 text-center text-sm text-primary hover:bg-muted/60">{t("Job alert emails and settings")}</Link>
        </div>
      )}
    </div>
  );
}
