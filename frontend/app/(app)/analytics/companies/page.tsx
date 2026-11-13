"use client";

import Link from "next/link";
import { Ghost, Reply, Send, Table2, ThumbsDown, ThumbsUp, Video } from "lucide-react";
import { useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { Notice, PageHeader } from "@/components/app-shell";
import { useT } from "@/components/i18n";
import { CountKpi, RateKpi } from "@/components/kpi";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useApi } from "@/hooks/use-api";
import type { CompanyInsights, InsightGroup } from "@/types/api";

const RANGES = [{ d: "30", l: "30 days" }, { d: "90", l: "90 days" }, { d: "365", l: "365 days" }, { d: "", l: "All time" }];
type SortKey = "label" | "applied" | "replied" | "interviews" | "reply_rate" | "interview_rate" | "median_response_days" | "ghosted" | "last_activity";
const COLS: { key: SortKey; label: string; right?: boolean }[] = [
  { key: "label", label: "Company" }, { key: "applied", label: "Applied", right: true }, { key: "replied", label: "Replied", right: true },
  { key: "interviews", label: "Interviews", right: true }, { key: "reply_rate", label: "Reply rate" }, { key: "interview_rate", label: "Interview rate" },
  { key: "median_response_days", label: "Median reply (days)", right: true }, { key: "ghosted", label: "Ghosted", right: true }, { key: "last_activity", label: "Last activity" },
];

function RateBar({ v, color }: { v: number | null; color: string }) {
  return (
    <div className="flex min-w-24 items-center gap-2">
      <span className="relative h-2 flex-1 overflow-hidden rounded-full bg-muted">
        {v != null && <span className="absolute inset-y-0 left-0 rounded-full" style={{ width: `${Math.max(v, 2)}%`, background: color }} />}
      </span>
      <span className="w-9 text-right text-xs tabular-nums">{v == null ? "—" : `${v}%`}</span>
    </div>
  );
}

export default function CompanyInsightsPage() {
  const { t } = useT();
  const [days, setDays] = useState("90");
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: "applied", dir: -1 });
  const [table, setTable] = useState(false);
  const { data, error, loading } = useApi<CompanyInsights>(`/analytics/companies${days ? `?days=${days}` : ""}`);

  const rows = useMemo(() => {
    const list = (data?.companies ?? []).filter((g) => g.label.toLowerCase().includes(q.trim().toLowerCase()));
    return [...list].sort((a, b) => {
      const x = a[sort.key] ?? -1, y = b[sort.key] ?? -1;
      return (typeof x === "string" && typeof y === "string" ? x.localeCompare(y) : Number(x) - Number(y)) * sort.dir;
    });
  }, [data, q, sort]);

  const o = data?.overall;
  const chart = (data?.sources ?? []).map((s: InsightGroup) => ({ name: s.label, "Reply rate": s.reply_rate ?? 0, "Interview rate": s.interview_rate ?? 0, applied: s.applied }));

  return (
    <div>
      <PageHeader title={t("Company insights")} description={t("Your own reply and interview rates per company and per source.")}
        actions={<div className="flex gap-1">{RANGES.map((r) => <Button key={r.d} size="sm" variant={days === r.d ? "default" : "outline"} onClick={() => setDays(r.d)}>{t(r.l)}</Button>)}</div>} />
      {error && <Notice tone="error">{error}</Notice>}
      {loading && !data && <p className="text-sm text-muted-foreground">{t("Loading…")}</p>}
      {data && o && (
        <>
          <div className="mb-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            <CountKpi label={t("Applied")} value={o.applied} icon={Send} tone="orange" />
            <RateKpi label={t("Reply rate")} value={o.reply_rate} icon={Reply} tone="green" />
            <RateKpi label={t("Interview rate")} value={o.interview_rate} icon={Video} tone="purple" />
            <CountKpi label={t("Ghosted")} value={o.ghosted} icon={Ghost} tone="red" />
            <CountKpi label={t("Offers")} value={o.offers} icon={ThumbsUp} tone="lime" />
          </div>

          {!data.enough_data ? (
            <div className="mb-6">
              <Notice>
                {t("Not enough data yet. Insights appear after a few sent applications.")}{" "}
                <Link href="/jobs" className="underline">{t("Find jobs")}</Link>
              </Notice>
            </div>
          ) : (
            <>
              <div className="mb-6 grid gap-3 md:grid-cols-2">
                <Card><CardContent className="flex items-center gap-3 p-4"><ThumbsUp className="size-5" style={{ color: "var(--tone-green)" }} aria-hidden />
                  <p className="text-sm">{data.best_source ? <>{t("Best source")}: <b>{data.best_source.label}</b> · {data.best_source.reply_rate}% {t("reply rate")} (n={data.best_source.applied})</> : t("No clear best source yet (needs 3+ applications in 2 sources).")}</p></CardContent></Card>
                <Card><CardContent className="flex items-center gap-3 p-4"><ThumbsDown className="size-5" style={{ color: "var(--tone-red)" }} aria-hidden />
                  <p className="text-sm">{data.worst_source ? <>{t("Weakest source")}: <b>{data.worst_source.label}</b> · {data.worst_source.reply_rate}% {t("reply rate")} (n={data.worst_source.applied})</> : t("No clear weakest source yet.")}</p></CardContent></Card>
              </div>

              <Card className="mb-6">
                <CardHeader className="flex-row items-center justify-between">
                  <CardTitle>{t("By source")}</CardTitle>
                  <Button size="sm" variant="outline" onClick={() => setTable((v) => !v)}><Table2 className="size-4" />{table ? t("Chart view") : t("Table view")}</Button>
                </CardHeader>
                <CardContent>
                  {table ? (
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead className="text-left text-xs uppercase tracking-wide text-muted-foreground"><tr><th className="py-2">{t("Source")}</th><th className="text-right">{t("Applied")}</th><th className="text-right">{t("Reply rate")}</th><th className="text-right">{t("Interview rate")}</th></tr></thead>
                        <tbody>{chart.map((r) => <tr key={r.name} className="border-t"><td className="py-2">{r.name}</td><td className="text-right tabular-nums">{r.applied}</td><td className="text-right tabular-nums">{r["Reply rate"]}%</td><td className="text-right tabular-nums">{r["Interview rate"]}%</td></tr>)}</tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="h-72">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={chart} margin={{ top: 8, right: 16, bottom: 0, left: -12 }}>
                          <CartesianGrid vertical={false} stroke="var(--grid)" />
                          <XAxis dataKey="name" tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} axisLine={false} tickLine={false} />
                          <YAxis unit="%" domain={[0, 100]} tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} axisLine={false} tickLine={false} />
                          <Tooltip cursor={{ fill: "var(--muted)" }} contentStyle={{ background: "var(--card-solid, var(--card))", border: "1px solid var(--border)", borderRadius: 12 }} />
                          <Legend wrapperStyle={{ fontSize: 12, color: "var(--muted-foreground)" }} />
                          <Bar dataKey="Reply rate" fill="var(--chart-1)" radius={[6, 6, 0, 0]} />
                          <Bar dataKey="Interview rate" fill="var(--chart-2)" radius={[6, 6, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  )}
                </CardContent>
              </Card>
            </>
          )}

          <Card>
            <CardHeader className="flex-row items-center justify-between gap-3">
              <CardTitle>{t("By company")}</CardTitle>
              <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("Search companies")} aria-label={t("Search companies")}
                className="h-9 w-56 rounded-xl border bg-transparent px-3 text-sm outline-none" />
            </CardHeader>
            <CardContent className="overflow-x-auto">
              {rows.length === 0 ? <p className="py-6 text-center text-sm text-muted-foreground">{t("No companies to show.")}</p> : (
                <table className="w-full text-sm">
                  <thead className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                    <tr>
                      {COLS.map((c) => (
                        <th key={c.key} className={`py-2 pr-3 ${c.right ? "text-right" : ""}`} aria-sort={sort.key === c.key ? (sort.dir === 1 ? "ascending" : "descending") : "none"}>
                          <button type="button" onClick={() => setSort((s) => ({ key: c.key, dir: s.key === c.key ? (s.dir === 1 ? -1 : 1) : -1 }))}>
                            {t(c.label)}{sort.key === c.key ? (sort.dir === 1 ? " ▲" : " ▼") : ""}
                          </button>
                        </th>
                      ))}
                      <th className="py-2">{t("Tip")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((g) => (
                      <tr key={g.label} className="border-t align-top">
                        <td className="py-2 pr-3 font-medium">{g.label}</td>
                        <td className="py-2 pr-3 text-right tabular-nums">{g.applied}</td>
                        <td className="py-2 pr-3 text-right tabular-nums">{g.replied}</td>
                        <td className="py-2 pr-3 text-right tabular-nums">{g.interviews}</td>
                        <td className="py-2 pr-3"><RateBar v={g.reply_rate} color="var(--chart-1)" /></td>
                        <td className="py-2 pr-3"><RateBar v={g.interview_rate} color="var(--chart-2)" /></td>
                        <td className="py-2 pr-3 text-right tabular-nums">{g.median_response_days ?? "—"}</td>
                        <td className="py-2 pr-3 text-right">{g.ghosted > 0 ? <span className="rounded-full border px-2 py-0.5 text-xs" style={{ color: "var(--tone-red)" }}>{g.ghosted}</span> : "—"}</td>
                        <td className="whitespace-nowrap py-2 pr-3 text-muted-foreground">{g.last_activity ? new Date(g.last_activity).toLocaleDateString() : "—"}</td>
                        <td className="min-w-56 py-2 text-xs text-muted-foreground">{g.tip}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
