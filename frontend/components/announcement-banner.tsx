"use client";

import { Megaphone, X } from "lucide-react";
import { useEffect, useState } from "react";

import { request } from "@/services/api";
import type { Announcement } from "@/types/api";

const KEY = "saige-dismissed-announcements";

function dismissed(): string[] {
  try { return JSON.parse(localStorage.getItem(KEY) || "[]") as string[]; } catch { return []; }
}

/** Super-admin broadcast, shown to every signed-in user until they dismiss it (remembered in localStorage). */
export function AnnouncementBanner() {
  const [items, setItems] = useState<Announcement[]>([]);
  useEffect(() => {
    const gone = dismissed();
    void request<Announcement[]>("/announcements").then((rows) => setItems(rows.filter((r) => !gone.includes(r.id)))).catch(() => undefined);
  }, []);
  function close(id: string) {
    setItems((cur) => cur.filter((a) => a.id !== id));
    try { localStorage.setItem(KEY, JSON.stringify([...dismissed(), id].slice(-50))); } catch { /* private mode */ }
  }
  if (!items.length) return null;
  return (
    <div className="mb-4 flex flex-col gap-2" role="region" aria-label="Announcements">
      {items.map((a) => (
        <div key={a.id} className="flex items-start gap-3 rounded-2xl border bg-card px-4 py-3 text-sm"
          style={{ borderColor: a.level === "warning" ? "var(--tone-orange, #f59e0b)" : a.level === "success" ? "var(--tone-green, #22c55e)" : undefined }}>
          <Megaphone className="mt-0.5 size-4 shrink-0" aria-hidden />
          <div className="min-w-0 flex-1"><p className="font-medium">{a.title}</p><p className="text-muted-foreground">{a.message}</p></div>
          <button type="button" onClick={() => close(a.id)} aria-label="Dismiss announcement" className="rounded-full p-1 hover:bg-muted"><X className="size-4" /></button>
        </div>
      ))}
    </div>
  );
}
