"use client";

import { ArrowDownRight, ArrowUpRight, Table2 } from "lucide-react";
import { createContext, useContext, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export const fmt = (iso: string | null | undefined) => (iso ? new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "â€”");

const tick = { fontSize: 11, fill: "var(--muted-foreground)" };
const tip = { background: "var(--card-solid, var(--card))", border: "1px solid var(--border)", borderRadius: 12 };

export type Series = { key: string; name: string };

/** Line or bar chart (series use --chart-1..4) with a legend and a table-view toggle. */
export function DataChart({ title, description, rows, x, series, kind = "line" }: {
  title: string; description?: string; rows: Record<string, string | number>[]; x: string; series: Series[]; kind?: "line" | "bar";
}) {
  const [table, setTable] = useState(false);
  const common = { data: rows, margin: { top: 8, right: 16, bottom: 0, left: -12 } };
  const axes = (
    <>
      <CartesianGrid vertical={false} stroke="var(--grid)" />
      <XAxis dataKey={x} tick={tick} axisLine={false} tickLine={false} interval="preserveStartEnd" />
      <YAxis allowDecimals={false} tick={tick} axisLine={false} tickLine={false} />
      <Tooltip contentStyle={tip} />
      <Legend wrapperStyle={{ fontSize: 12, color: "var(--muted-foreground)" }} />
    </>
  );
  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between gap-3">
        <div><CardTitle className="text-base">{title}</CardTitle>{description && <CardDescription>{description}</CardDescription>}</div>
        <Button size="icon" variant="ghost" className="size-8" onClick={() => setTable(!table)} aria-label={table ? "Show chart" : "Show table"}><Table2 className="size-4" /></Button>
      </CardHeader>
      <CardContent>
        {table ? (
          <div className="max-h-72 overflow-y-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                <tr><th className="py-2">{x}</th>{series.map((s) => <th key={s.key} className="py-2 text-right">{s.name}</th>)}</tr>
              </thead>
              <tbody>{[...rows].reverse().map((r) => (
                <tr key={String(r[x])} className="border-t"><td className="py-2">{r[x]}</td>{series.map((s) => <td key={s.key} className="py-2 text-right tabular-nums">{r[s.key]}</td>)}</tr>
              ))}</tbody>
            </table>
          </div>
        ) : (
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              {kind === "bar" ? (
                <BarChart {...common}>{axes}{series.map((s, i) => <Bar key={s.key} dataKey={s.key} name={s.name} fill={`var(--chart-${(i % 4) + 1})`} radius={[6, 6, 0, 0]} />)}</BarChart>
              ) : (
                <LineChart {...common}>{axes}{series.map((s, i) => <Line key={s.key} type="monotone" dataKey={s.key} name={s.name} stroke={`var(--chart-${(i % 4) + 1})`} strokeWidth={2} dot={false} />)}</LineChart>
              )}
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export function Pager({ page, pageSize, total, onPage, onSize }: { page: number; pageSize: number; total: number; onPage: (p: number) => void; onSize?: (n: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 pt-3 text-sm text-muted-foreground">
      <span>{total} total</span>
      <div className="flex items-center gap-2">
        {onSize && (
          <select value={pageSize} onChange={(e) => onSize(Number(e.target.value))} aria-label="Rows per page" className="h-8 rounded-full border bg-transparent px-2">
            {[25, 50, 100].map((n) => <option key={n} value={n}>{n} / page</option>)}
          </select>
        )}
        <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => onPage(page - 1)}>Prev</Button>
        <span className="tabular-nums">{page} / {pages}</span>
        <Button size="sm" variant="outline" disabled={page >= pages} onClick={() => onPage(page + 1)}>Next</Button>
      </div>
    </div>
  );
}

/** Modal confirmation; `typed` requires the exact text to be entered before the action is enabled. */
export function ConfirmDialog({ title, body, confirmLabel, typed, onConfirm, onCancel }: {
  title: string; body: string; confirmLabel: string; typed?: string; onConfirm: () => void; onCancel: () => void;
}) {
  const [text, setText] = useState("");
  const ok = !typed || text.trim().toLowerCase() === typed.toLowerCase();
  return (
    <div className="fixed inset-0 z-[80] grid place-items-center bg-black/70 p-4" role="dialog" aria-modal="true" aria-label={title}>
      <div className="w-full max-w-md rounded-3xl border bg-card p-6">
        <h2 className="text-lg font-semibold">{title}</h2>
        <p className="mt-2 text-sm text-muted-foreground">{body}</p>
        {typed && <input autoFocus value={text} onChange={(e) => setText(e.target.value)} placeholder={typed} aria-label="Type to confirm" className="mt-4 h-10 w-full rounded-full border bg-transparent px-4 text-sm" />}
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="outline" onClick={onCancel}>Cancel</Button>
          <Button variant="destructive" disabled={!ok} onClick={onConfirm}>{confirmLabel}</Button>
        </div>
      </div>
    </div>
  );
}

export function Err({ message }: { message: string | null }) {
  return message ? <p role="alert" className="mb-3 rounded-2xl border border-red-500/40 bg-red-500/10 px-4 py-2 text-sm text-red-400">{message}</p> : null;
}

// ---------------------------------------------------------------- shared console kit

export type AdminRange = { days: number; from: string; to: string; qs: string; label: string };
export const AdminCtx = createContext<AdminRange>({ days: 30, from: "", to: "", qs: "days=30", label: "Last 30 days" });
/** The date range chosen in the top bar; every widget appends `qs` to its API path. */
export const useAdmin = () => useContext(AdminCtx);

export const num = (n: number | null | undefined) => (n === null || n === undefined ? "—" : n.toLocaleString());
export const shortDay = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { month: "short", day: "numeric" });

export type Kpi = { value: number | null; previous: number | null; change_pct: number | null; series: number[]; unit: string };

/** Tiny inline trend line in the console's single accent. */
export function Spark({ points, className = "h-9 w-full" }: { points: number[]; className?: string }) {
  if (points.length < 2) return <div className={className} aria-hidden />;
  const max = Math.max(...points, 1), min = Math.min(...points, 0);
  const span = max - min || 1;
  const xy = points.map((p, i) => `${(i / (points.length - 1)) * 100},${34 - ((p - min) / span) * 30}`);
  return (
    <svg viewBox="0 0 100 36" preserveAspectRatio="none" className={className} aria-hidden>
      <polyline points={`0,36 ${xy.join(" ")} 100,36`} fill="var(--accent-fill, color-mix(in srgb, var(--chart-2) 14%, transparent))" stroke="none" />
      <polyline points={xy.join(" ")} fill="none" stroke="var(--chart-2)" strokeWidth="1.6" vectorEffect="non-scaling-stroke" strokeLinejoin="round" />
    </svg>
  );
}

export function Delta({ pct, invert }: { pct: number | null; invert?: boolean }) {
  if (pct === null) return <span className="text-xs text-muted-foreground">no prior data</span>;
  const up = pct >= 0, good = invert ? !up : up;
  return (
    <span className="inline-flex items-center gap-0.5 text-xs font-medium tabular-nums" style={{ color: pct === 0 ? "var(--muted-foreground)" : good ? "var(--tone-green)" : "var(--tone-orange)" }}>
      {up ? <ArrowUpRight className="size-3" aria-hidden /> : <ArrowDownRight className="size-3" aria-hidden />}{Math.abs(pct)}%
    </span>
  );
}

/** KPI card: value, change vs the previous period of equal length, sparkline over the selected range. */
export function KpiCard({ label, kpi, invert, hint }: { label: string; kpi: Kpi | undefined; invert?: boolean; hint?: string }) {
  return (
    <div className="flex flex-col gap-1 rounded-2xl border bg-card p-4">
      <p className="text-xs font-medium text-muted-foreground">{label}</p>
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-2xl font-semibold tabular-nums">{kpi?.value === null || !kpi ? "—" : `${num(kpi.value)}${kpi.unit}`}</span>
        {kpi && <Delta pct={kpi.change_pct} invert={invert} />}
      </div>
      <Spark points={kpi?.series ?? []} />
      <p className="text-[11px] text-muted-foreground">{hint ?? (kpi ? `previous period: ${kpi.previous === null ? "—" : `${num(kpi.previous)}${kpi.unit}`}` : "")}</p>
    </div>
  );
}

export function Panel({ title, description, right, children, className }: { title: string; description?: string; right?: React.ReactNode; children: React.ReactNode; className?: string }) {
  return (
    <Card className={className}>
      <CardHeader className="flex-row items-start justify-between gap-3 pb-3">
        <div><CardTitle className="text-sm font-semibold">{title}</CardTitle>{description && <CardDescription className="text-xs">{description}</CardDescription>}</div>
        {right}
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

/** Horizontal bars for a ranked list (companies, roles, cities, features). */
export function BarList({ rows, empty = "No data in this range." }: { rows: { name: string; count: number; note?: string }[]; empty?: string }) {
  const max = Math.max(...rows.map((r) => r.count), 1);
  if (!rows.length) return <p className="text-sm text-muted-foreground">{empty}</p>;
  return (
    <ul className="flex flex-col gap-2">
      {rows.map((r) => (
        <li key={r.name} className="text-sm">
          <div className="flex justify-between gap-2"><span className="truncate">{r.name}</span><span className="tabular-nums text-muted-foreground">{num(r.count)}{r.note ? ` · ${r.note}` : ""}</span></div>
          <div className="mt-1 h-1.5 rounded-full bg-muted"><div className="h-full rounded-full" style={{ width: `${(r.count / max) * 100}%`, background: "var(--chart-2)" }} /></div>
        </li>
      ))}
    </ul>
  );
}

export const heat = (pct: number | null) => (pct === null ? undefined : { background: `color-mix(in srgb, var(--chart-2) ${Math.round(Math.min(pct, 100) * 0.85)}%, transparent)` });

export function Avatar({ name, email, size = 32 }: { name?: string; email: string; size?: number }) {
  const src = (name || email).trim();
  const parts = src.split(/[\s@._-]+/).filter(Boolean);
  const initials = ((parts[0]?.[0] ?? "?") + (parts.length > 1 ? parts[1][0] : "")).toUpperCase();
  return <span className="grid shrink-0 place-items-center rounded-full bg-muted text-xs font-semibold" style={{ width: size, height: size }} aria-hidden>{initials}</span>;
}

export const LIFECYCLE_LABEL: Record<string, string> = { new: "New", activated: "Activated", engaged: "Engaged", at_risk: "At risk", churned: "Churned" };
const LIFECYCLE_TONE: Record<string, string> = { new: "var(--tone-teal)", activated: "var(--tone-purple)", engaged: "var(--tone-green)", at_risk: "var(--tone-yellow)", churned: "var(--muted-foreground)" };

export function LifecycleBadge({ stage }: { stage: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium">
      <span className="size-1.5 rounded-full" style={{ background: LIFECYCLE_TONE[stage] ?? "var(--muted-foreground)" }} />{LIFECYCLE_LABEL[stage] ?? stage}
    </span>
  );
}

export function HealthBar({ score }: { score: number }) {
  const tone = score >= 70 ? "var(--tone-green)" : score >= 40 ? "var(--tone-yellow)" : "var(--tone-orange)";
  return (
    <span className="inline-flex items-center gap-2 text-xs tabular-nums" title={`Health score ${score}/100`}>
      <span className="h-1.5 w-12 rounded-full bg-muted"><span className="block h-full rounded-full" style={{ width: `${score}%`, background: tone }} /></span>{score}
    </span>
  );
}
