"use client";

import { useEffect, useState } from "react";

import type { Insights } from "@/components/insights";
import { useApi } from "@/hooks/use-api";

/** Header ticker: live numbers from your search flip in 3D every few seconds, beside a small spinning orbit. */
export function LiveTicker() {
  const { data } = useApi<Insights>("/analytics/insights");
  const [i, setI] = useState(0);
  const f = data?.feed;
  const apps = (data?.applications_by_status ?? []).reduce((n, r) => n + r.count, 0);
  const emails = (data?.inbox ?? []).reduce((n, r) => n + r.count, 0);
  const items = f ? [
    { n: f.total, label: `jobs for ${f.roles[0] ?? "your roles"}`, tone: "orange" },
    { n: f.strong, label: "strong matches (80%+)", tone: "green" },
    { n: f.country, label: `jobs in ${f.country_name ?? "your country"}`, tone: "teal" },
    { n: f.remote, label: "remote jobs", tone: "mint" },
    { n: apps, label: "applications in progress", tone: "yellow" },
    { n: emails, label: "job emails in your inbox", tone: "purple" },
    { n: f.walk_in, label: "walk-in drives", tone: "red" },
  ] : [];

  useEffect(() => {
    if (!items.length) return;
    const id = window.setInterval(() => setI((x) => (x + 1) % items.length), 3200);
    return () => window.clearInterval(id);
  }, [items.length]);

  const cur = items[i % Math.max(1, items.length)];
  return (
    <div className="hidden min-w-0 items-center gap-3 sm:flex" aria-live="polite">
      <span className="ticker-orbit relative size-7 shrink-0" aria-hidden>
        <span className="absolute inset-0 rounded-full border border-current opacity-30" style={{ transform: "rotateX(68deg)" }} />
        <span className="ticker-planet absolute left-1/2 top-1/2 size-2 rounded-full" style={{ background: `var(--tone-${cur?.tone ?? "green"})`, boxShadow: `0 0 10px var(--tone-${cur?.tone ?? "green"})` }} />
        <span className="absolute left-1/2 top-1/2 size-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-foreground/80" />
      </span>
      <span className="ticker-3d relative h-6 overflow-hidden text-sm [perspective:400px]">
        {cur && (
          <span key={i} className="ticker-flip flex items-center gap-1.5 whitespace-nowrap">
            <b className="tabular-nums" style={{ color: `var(--tone-${cur.tone})` }}>{cur.n}</b>
            <span className="text-muted-foreground">{cur.label}</span>
          </span>
        )}
      </span>
    </div>
  );
}
