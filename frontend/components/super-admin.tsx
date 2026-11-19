"use client";

import { Table2 } from "lucide-react";
import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export const fmt = (iso: string | null | undefined) => (iso ? new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "—");

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
