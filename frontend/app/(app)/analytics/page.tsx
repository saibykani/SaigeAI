"use client";

import { Reply, Send, Table2, Trophy, Video } from "lucide-react";
import { useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { Notice, PageHeader } from "@/components/app-shell";
import { CountKpi, RateKpi } from "@/components/kpi";
import { InsightsGrid } from "@/components/insights";
import { KIND_LABEL } from "@/components/outreach";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useApi } from "@/hooks/use-api";
import type { Breakdowns, GroupMetrics } from "@/types/api";

type RateKey = "response_rate" | "interview_rate" | "offer_rate";

const SERIES = [
  { key: "applied", label: "Applied", color: "var(--chart-1)" },
  { key: "responses", label: "Responses", color: "var(--chart-2)" },
  { key: "interviews", label: "Interviews", color: "var(--chart-3)" },
  { key: "offers", label: "Offers", color: "var(--chart-4)" },
] as const;

const TOOLTIP = {
  contentStyle: { background: "var(--card-solid)", border: "1px solid var(--border)", borderRadius: 12, fontSize: 12, boxShadow: "var(--shadow-card)" },
  labelStyle: { color: "var(--foreground)", fontWeight: 600 },
  itemStyle: { color: "var(--foreground)" },
};

const weekLabel = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { day: "numeric", month: "short" });

/** One measure per group as a horizontal bar, one hue. Labels and values stay in text ink. */
function RateBars({ rows, rateKey, color, empty }: { rows: GroupMetrics[]; rateKey: RateKey; color: string; empty: string }) {
  if (!rows.some((r) => r.sent > 0)) return <p className="py-6 text-center text-sm text-muted-foreground">{empty}</p>;
  return (
    <ul className="flex flex-col gap-3">
      {rows.map((r, i) => {
        const v = r[rateKey];
        return (
          <li
            key={r.label}
            className="grid grid-cols-[minmax(0,9rem)_1fr_3rem] items-center gap-3 text-sm"
            title={`${r.label}: ${r.sent} sent · ${r.responses} responses · ${r.interviews} interviews · ${r.offers} offers`}
          >
            <span className="truncate">{r.label}</span>
            <span className="relative h-2.5 overflow-hidden rounded-full bg-muted">
              {v != null && <span className="animate-grow-x absolute inset-y-0 left-0 rounded-full" style={{ width: `${Math.max(v, 2)}%`, background: color, animationDelay: `${i * 50}ms` }} />}
            </span>
            <span className="text-right tabular-nums">
              {v == null ? <span className="text-muted-foreground">—</span> : `${v}%`}
              <span className="block text-[10px] text-muted-foreground">n={r.sent}</span>
            </span>
          </li>
        );
      })}
    </ul>
  );
}

function GroupTable({ rows }: { rows: GroupMetrics[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="text-left text-xs uppercase tracking-wide text-muted-foreground">
          <tr><th className="py-2 pr-3">Group</th><th className="py-2 pr-3 text-right">Sent</th><th className="py-2 pr-3 text-right">Responses</th><th className="py-2 pr-3 text-right">Interviews</th><th className="py-2 text-right">Offers</th></tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.label} className="border-t">
              <td className="py-2 pr-3">{r.label}</td>
              <td className="py-2 pr-3 text-right tabular-nums">{r.sent}</td>
              <td className="py-2 pr-3 text-right tabular-nums">{r.responses}{r.response_rate != null && <span className="text-muted-foreground"> · {r.response_rate}%</span>}</td>
              <td className="py-2 pr-3 text-right tabular-nums">{r.interviews}{r.interview_rate != null && <span className="text-muted-foreground"> · {r.interview_rate}%</span>}</td>
              <td className="py-2 text-right tabular-nums">{r.offers}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Breakdown({ title, description, rows, color, empty }: { title: string; description: string; rows: GroupMetrics[]; color: string; empty: string }) {
  const [metric, setMetric] = useState<RateKey>("response_rate");
  const [table, setTable] = useState(false);
  return (
    <Card className="animate-rise">
      <CardHeader className="flex-row flex-wrap items-start justify-between gap-3">
        <div>
          <CardTitle className="text-base">{title}</CardTitle>
          <CardDescription>{description}</CardDescription>
        </div>
        <div className="flex items-center gap-1">
          {!table && (
            <select value={metric} onChange={(e) => setMetric(e.target.value as RateKey)} className="h-8 rounded-full border bg-transparent px-3 text-xs" aria-label="Metric">
              <option value="response_rate">Response rate</option>
              <option value="interview_rate">Interview rate</option>
              <option value="offer_rate">Offer rate</option>
            </select>
          )}
          <Button size="icon" variant="ghost" className="size-8" onClick={() => setTable(!table)} aria-label={table ? "Show chart" : "Show table"} title={table ? "Show chart" : "Show table"}>
            <Table2 className="size-4" />
          </Button>
        </div>
      </CardHeader>
      <CardContent>{table ? <GroupTable rows={rows} /> : <RateBars rows={rows} rateKey={metric} color={color} empty={empty} />}</CardContent>
    </Card>
  );
}

export default function AnalyticsPage() {
  const { data, error } = useApi<Breakdowns>("/analytics/breakdowns");
  const [weeklyTable, setWeeklyTable] = useState(false);

  if (error) return <><PageHeader title="Analytics" /><Notice tone="error">{error}</Notice><div className="mt-6"><InsightsGrid /></div></>;
  if (!data) return <div className="flex flex-col gap-6"><div className="skeleton h-28 rounded-2xl" /><div className="skeleton h-80 rounded-3xl" /></div>;

  const o = data.overall;
  const maxTtr = Math.max(1, ...data.time_to_response.map((t) => t.count));
  const weekly = data.weekly.map((w) => ({ ...w, label: weekLabel(w.week) }));

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Analytics" description="What's working in your search: your market, pipeline, and which sources, roles, resumes and messages get responses. Counts from your own records, never estimates." />
      <InsightsGrid />
      {o.sent === 0 && (
        <Notice>Response, interview and offer rates appear once applications are marked Applied (after you submit them, or when Saige sends an email application).</Notice>
      )}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <CountKpi label="Applications sent" value={o.sent} hint={`${o.applications} tracked in total`} icon={Send} tone="orange" />
        <RateKpi label="Response rate" value={o.response_rate} hint={`${o.responses} responses`} icon={Reply} tone="purple" delay={40} />
        <RateKpi label="Interview rate" value={o.interview_rate} hint={`${o.interviews} interviews`} icon={Video} tone="green" delay={80} />
        <RateKpi label="Offer rate" value={o.offer_rate} hint={`${o.offers} offers`} icon={Trophy} tone="yellow" delay={120} />
      </div>

      <Card className="animate-rise">
        <CardHeader className="flex-row items-start justify-between gap-3">
          <div>
            <CardTitle className="text-base">Weekly activity</CardTitle>
            <CardDescription>Last {weekly.length} weeks, by the week each event happened.</CardDescription>
          </div>
          <Button size="icon" variant="ghost" className="size-8" onClick={() => setWeeklyTable(!weeklyTable)} aria-label={weeklyTable ? "Show chart" : "Show table"}>
            <Table2 className="size-4" />
          </Button>
        </CardHeader>
        <CardContent>
          {weeklyTable ? (
            <table className="w-full text-sm">
              <thead className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                <tr><th className="py-2">Week of</th>{SERIES.map((s) => <th key={s.key} className="py-2 text-right">{s.label}</th>)}</tr>
              </thead>
              <tbody>
                {weekly.map((w) => (
                  <tr key={w.week} className="border-t"><td className="py-2">{w.label}</td>{SERIES.map((s) => <td key={s.key} className="py-2 text-right tabular-nums">{w[s.key]}</td>)}</tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={weekly} margin={{ top: 8, right: 16, bottom: 0, left: -12 }}>
                  <CartesianGrid vertical={false} stroke="var(--grid)" />
                  <XAxis dataKey="label" tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} axisLine={false} tickLine={false} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} axisLine={false} tickLine={false} />
                  <Tooltip {...TOOLTIP} cursor={{ stroke: "var(--muted-foreground)", strokeDasharray: "3 3" }} />
                  <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} formatter={(value: string) => <span style={{ color: "var(--foreground)" }}>{value}</span>} />
                  {SERIES.map((s) => (
                    <Line key={s.key} type="monotone" dataKey={s.key} name={s.label} stroke={s.color} strokeWidth={2}
                          dot={{ r: 4, strokeWidth: 2, stroke: "var(--card-solid)", fill: s.color }} activeDot={{ r: 6 }} animationDuration={900} />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Breakdown title="By source" description="Where the jobs you applied to came from. A sent referral request counts as Referral." rows={data.by_source} color="var(--chart-1)" empty="Apply to a few jobs to compare sources." />
        <Breakdown title="By role family" description="How each kind of role responds to you." rows={data.by_role_family} color="var(--chart-2)" empty="No applications sent yet." />
        <Breakdown title="By resume version" description="Which resume gets replies. Tailored resumes usually win." rows={data.by_resume} color="var(--chart-3)" empty="Attach resumes to applications to compare versions." />
        <Breakdown title="Match score vs outcome" description="Whether a higher Saige match score leads to more responses." rows={data.by_match} color="var(--chart-4)" empty="No scored applications sent yet." />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="animate-rise">
          <CardHeader>
            <CardTitle className="text-base">Time to first response</CardTitle>
            <CardDescription>Days from applying to the first human reply, screening, interview or rejection.</CardDescription>
          </CardHeader>
          <CardContent>
            {data.time_to_response.every((t) => t.count === 0) ? (
              <p className="py-6 text-center text-sm text-muted-foreground">No responses yet.</p>
            ) : (
              <div className="flex h-44 items-end gap-4">
                {data.time_to_response.map((t, i) => (
                  <div key={t.bucket} className="flex h-full flex-1 flex-col items-center justify-end gap-1.5" title={`${t.bucket}: ${t.count}`}>
                    <span className="text-xs tabular-nums">{t.count}</span>
                    <span className="animate-rise w-full max-w-14 rounded-t-md" style={{ height: `${Math.max(4, (t.count / maxTtr) * 100)}%`, background: "var(--chart-2)", animationDelay: `${i * 60}ms` }} />
                    <span className="text-[11px] text-muted-foreground">{t.bucket}</span>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="animate-rise">
          <CardHeader>
            <CardTitle className="text-base">Outreach reply rate</CardTitle>
            <CardDescription>Messages you sent from Recruiters, by type.</CardDescription>
          </CardHeader>
          <CardContent>
            <RateBars
              rows={data.outreach.map((k) => ({ label: KIND_LABEL[k.kind], applications: k.sent, sent: k.sent, responses: k.replied, interviews: 0, offers: 0, response_rate: k.reply_rate, interview_rate: null, offer_rate: null }))}
              rateKey="response_rate"
              color="var(--chart-3)"
              empty="No outreach sent yet."
            />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
