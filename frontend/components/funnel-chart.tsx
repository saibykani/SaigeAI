"use client";

import { Bar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

/** Horizontal funnel. Stages are ordered, so bars use one ordinal ramp of the theme ink (faint -> strong
 *  by stage), not categorical hues. Values/labels stay in text ink; hover shows a tooltip. */
export function FunnelChart({ data }: { data: { stage: string; count: number }[] }) {
  const empty = data.every((d) => d.count === 0);
  return (
    <div className="relative h-80 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 4, right: 44, bottom: 4, left: 8 }} barCategoryGap={6}>
          <CartesianGrid horizontal={false} stroke="var(--grid)" />
          <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} axisLine={false} tickLine={false} />
          <YAxis dataKey="stage" type="category" width={132} tick={{ fontSize: 12.5, fill: "var(--foreground)" }} axisLine={false} tickLine={false} />
          <Tooltip
            cursor={{ fill: "var(--muted)", radius: 8 }}
            contentStyle={{
              background: "var(--card-solid)",
              border: "1px solid var(--border)",
              borderRadius: 12,
              fontSize: 12,
              boxShadow: "var(--shadow-card)",
            }}
            labelStyle={{ color: "var(--foreground)", fontWeight: 600 }}
            itemStyle={{ color: "var(--foreground)" }}
          />
          <Bar dataKey="count" name="Count" radius={[0, 6, 6, 0]} maxBarSize={24} animationDuration={900} animationEasing="ease-out">
            {data.map((d, i) => (
              // Monochrome ordinal ramp: later stages in stronger ink
              <Cell key={d.stage} fill={`color-mix(in srgb, var(--primary) ${Math.round(38 + (62 * i) / Math.max(1, data.length - 1))}%, transparent)`} />
            ))}
            <LabelList dataKey="count" position="right" style={{ fontSize: 12, fill: "var(--muted-foreground)", fontWeight: 500 }} />
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
