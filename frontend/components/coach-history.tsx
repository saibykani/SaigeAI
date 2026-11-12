"use client";

import { ArrowRight, RefreshCw } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { useApi } from "@/hooks/use-api";
import { request } from "@/services/api";
import { cn } from "@/utils/cn";

type Suggestion = { id: string; area: "resume" | "profile"; priority: number; title: string; why: string; link: string; items: string[] };
type HistoryRow = { id: string; at: string | null; group: string; kind: "agent" | "action"; status: string; title: string; detail: string; action: string };

/** Resume & profile coach agent: ranked, truthful suggestions (the user adds only what they really have). */
export function CoachCard() {
  const { data, reload } = useApi<Suggestion[]>("/suggestions");
  const [busy, setBusy] = useState(false);
  async function run() {
    setBusy(true);
    try { await request("/suggestions/run", { method: "POST" }); await reload(); } finally { setBusy(false); }
  }
  return (
    <section className="rounded-3xl border bg-card p-5">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <h2 className="text-xl">Resume &amp; profile coach</h2>
          <p className="text-sm text-muted-foreground">Ranked fixes from your own profile and the jobs you track.</p>
        </div>
        <Button variant="outline" size="sm" onClick={() => void run()} disabled={busy}><RefreshCw className={cn(busy && "animate-spin")} /> Run agent</Button>
      </div>
      {data?.length === 0 && <p className="py-6 text-center text-sm text-muted-foreground">Nothing to fix. Your profile is in great shape.</p>}
      <ul className="divide-y">
        {data?.slice(0, 6).map((s) => (
          <li key={s.id}>
            <Link href={s.link} className="flex items-start gap-3 py-3 hover:opacity-80">
              <span className="mt-0.5 grid size-6 shrink-0 place-items-center rounded-full bg-accent text-sm text-primary">+</span>
              <span className="min-w-0 flex-1">
                <span className="flex items-center gap-2">
                  <span>{s.title}</span>
                  <span className="rounded-full border px-2 text-[11px] capitalize text-muted-foreground">{s.area}</span>
                </span>
                <span className="block text-sm text-muted-foreground">{s.why}</span>
                {s.items.length > 0 && <span className="mt-1 block text-sm text-primary">{s.items.join(" · ")}</span>}
              </span>
              <ArrowRight className="mt-1 size-4 text-muted-foreground" />
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

const dayKey = (d: Date) => d.toDateString();

/** History: what Saige did today / yesterday / this week, as a table. */
export function HistoryTable() {
  const { data } = useApi<HistoryRow[]>("/activity/history?days=7");
  const [tab, setTab] = useState<"today" | "yesterday" | "week">("today");
  const rows = useMemo(() => {
    const today = new Date();
    const yest = new Date(Date.now() - 86_400_000);
    return (data ?? []).filter((r) => {
      if (!r.at || tab === "week") return true;
      return dayKey(new Date(r.at)) === dayKey(tab === "today" ? today : yest);
    });
  }, [data, tab]);
  return (
    <section className="rounded-3xl border bg-card p-5">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl">History</h2>
          <p className="text-sm text-muted-foreground">Every agent run and action Saige took for you.</p>
        </div>
        <div className="inline-flex rounded-full border p-1 text-sm">
          {(["today", "yesterday", "week"] as const).map((t) => (
            <button key={t} onClick={() => setTab(t)} aria-pressed={tab === t}
              className={cn("rounded-full px-3.5 py-1 capitalize", tab === t ? "bg-primary text-primary-foreground" : "text-muted-foreground")}>
              {t === "week" ? "7 days" : t}
            </button>
          ))}
        </div>
      </div>
      <div className="max-h-[420px] overflow-auto">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-card text-left text-xs text-muted-foreground">
            <tr><th className="py-2 pr-3 font-normal">Time</th><th className="py-2 pr-3 font-normal">What</th><th className="py-2 pr-3 font-normal">Details</th><th className="py-2 font-normal">Status</th></tr>
          </thead>
          <tbody className="divide-y">
            {data === null && <tr><td colSpan={4} className="py-6"><div className="skeleton h-8 rounded-xl" /></td></tr>}
            {data && rows.length === 0 && <tr><td colSpan={4} className="py-8 text-center text-muted-foreground">Nothing recorded {tab === "week" ? "this week" : tab}.</td></tr>}
            {rows.map((r) => (
              <tr key={r.id}>
                <td className="whitespace-nowrap py-2.5 pr-3 text-muted-foreground">
                  {r.at ? new Date(r.at).toLocaleString(undefined, tab === "week" ? { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" } : { hour: "2-digit", minute: "2-digit" }) : "—"}
                </td>
                <td className="py-2.5 pr-3">{r.title}<span className="ml-2 text-xs capitalize text-muted-foreground">{r.group}</span></td>
                <td className="max-w-[22rem] truncate py-2.5 pr-3 text-muted-foreground" title={r.detail}>{r.detail || "—"}</td>
                <td className="py-2.5">
                  <span className={cn("rounded-full px-2 py-0.5 text-xs", r.status === "failed" ? "bg-destructive/10 text-destructive" : "bg-accent text-primary")}>
                    {r.status === "succeeded" || r.status === "done" ? "Done" : r.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
