"use client";

import { Bar, BarChart, CartesianGrid, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export function FunnelChart({ data }: { data: { stage: string; count: number }[] }) {
  const empty = data.every((d) => d.count === 0);
  return (
    <div className="relative h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 4, right: 40, bottom: 4, left: 8 }}>
          <CartesianGrid horizontal={false} stroke="var(--border)" />
          <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} axisLine={false} tickLine={false} />
          <YAxis
            dataKey="stage"
            type="category"
            width={128}
            tick={{ fontSize: 12, fill: "var(--foreground)" }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            cursor={{ fill: "var(--muted)" }}
            contentStyle={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 12 }}
            labelStyle={{ color: "var(--foreground)" }}
          />
          <Bar dataKey="count" name="Count" fill="var(--primary)" radius={[0, 4, 4, 0]} maxBarSize={22}>
            <LabelList dataKey="count" position="right" style={{ fontSize: 11, fill: "var(--muted-foreground)" }} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      {empty && (
        <p className="pointer-events-none absolute inset-0 grid place-items-center text-sm text-muted-foreground">
          No pipeline data yet — add jobs to start your funnel
        </p>
      )}
    </div>
  );
}
