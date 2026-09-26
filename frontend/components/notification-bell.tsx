"use client";

import { Bell, CheckCheck } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { request } from "@/services/api";
import type { AppNotification } from "@/types/api";
import { cn } from "@/utils/cn";

function ago(iso: string): string {
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  if (s < 86400) return `${Math.floor(s / 3600)}h`;
  return `${Math.floor(s / 86400)}d`;
}

/** Header bell: unread badge (polled every minute), dropdown with the latest notifications. */
export function NotificationBell() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [unread, setUnread] = useState(0);
  const [items, setItems] = useState<AppNotification[] | null>(null);
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
    void request<AppNotification[]>("/notifications").then((l) => setItems(l.slice(0, 20))).catch(() => setItems([]));
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
        onClick={() => setOpen((o) => !o)}
        className="relative grid size-10 place-items-center rounded-full text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        aria-label={unread ? `Notifications, ${unread} unread` : "Notifications"}
        aria-expanded={open}
      >
        <Bell className="size-[18px]" />
        {unread > 0 && (
          <span className="animate-pop absolute right-1.5 top-1.5 grid min-w-4 place-items-center rounded-full px-1 text-[10px] font-semibold leading-4 text-black" style={{ background: "var(--tone-orange)" }}>
            {unread > 99 ? "99+" : unread}
          </span>
        )}
      </button>
      {open && (
        <div className="animate-pop absolute right-0 top-12 z-50 bg-card-solid w-[min(24rem,calc(100vw-2rem))] overflow-hidden rounded-2xl border shadow-[var(--shadow-lift)]">
          <div className="flex items-center justify-between border-b px-4 py-3">
            <p className="text-sm font-semibold">Notifications</p>
            <button onClick={readAll} disabled={!unread} className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground disabled:opacity-40">
              <CheckCheck className="size-3.5" /> Mark all read
            </button>
          </div>
          <ul className="max-h-[26rem] overflow-y-auto">
            {items === null && <li className="p-4"><div className="skeleton h-10 rounded-xl" /></li>}
            {items?.length === 0 && <li className="p-6 text-center text-sm text-muted-foreground">You&apos;re all caught up.</li>}
            {items?.map((n) => (
              <li key={n.id}>
                <button onClick={() => openItem(n)} className={cn("flex w-full gap-3 px-4 py-3 text-left transition-colors hover:bg-muted/60", !n.read && "bg-accent/40")}>
                  <span className={cn("mt-1.5 size-2 shrink-0 rounded-full", n.read ? "bg-transparent" : "")} style={n.read ? undefined : { background: "var(--tone-orange)" }} aria-hidden />
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm font-medium">{n.title}</span>
                    {n.body && <span className="line-clamp-2 block text-xs text-muted-foreground">{n.body}</span>}
                  </span>
                  <span className="shrink-0 text-[11px] text-muted-foreground">{ago(n.created_at)}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
