"use client";

import type { LucideIcon } from "lucide-react";
import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import Link from "next/link";
import { useId } from "react";

import { CountUp, ProgressRing } from "@/components/motion";
import { cn } from "@/utils/cn";

/** 7-point area sparkline in the theme's primary ink (single hue - it's a trend, not categories). */
export function Sparkline({ points, className }: { points: number[]; className?: string }) {
  const id = useId().replace(/:/g, "");
  const max = Math.max(1, ...points);
  const w = 120, h = 36;
  const step = w / Math.max(1, points.length - 1);
  const xy = points.map((v, i) => [i * step, h - 3 - (v / max) * (h - 8)] as const);
  const line = xy.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const area = `${line} L${w},${h} L0,${h} Z`;
  const [lx, ly] = xy[xy.length - 1];
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className={cn("h-9 w-full overflow-visible", className)} aria-hidden preserveAspectRatio="none">
      <defs>
        <linearGradient id={`sp-${id}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="var(--primary)" stopOpacity="0.28" />
          <stop offset="1" stopColor="var(--primary)" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#sp-${id})`} />
      <path d={line} fill="none" stroke="var(--primary)" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" vectorEffect="non-scaling-stroke" className="spark-draw" />
      <circle cx={lx} cy={ly} r="3" fill="var(--primary)" />
    </svg>
  );
}

function Delta({ today, yesterday }: { today: number; yesterday: number }) {
  const diff = today - yesterday;
  const Icon = diff > 0 ? ArrowUpRight : diff < 0 ? ArrowDownRight : Minus;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-0.5 rounded-full px-1.5 py-0.5 text-[11px] font-medium",
        diff > 0 ? "bg-success/15 text-success" : diff < 0 ? "bg-muted text-muted-foreground" : "bg-muted text-muted-foreground",
      )}
      title="Compared with yesterday"
    >
      <Icon className="size-3" />
      {diff === 0 ? "same as yesterday" : `${diff > 0 ? "+" : ""}${diff} vs yesterday`}
    </span>
  );
}

export function TrendKpi({ label, series, icon: Icon, href, delay = 0 }: { label: string; series: number[]; icon: LucideIcon; href?: string; delay?: number }) {
  const today = series[series.length - 1] ?? 0;
  const yesterday = series[series.length - 2] ?? 0;
  const body = (
    <div className="glass lift animate-rise group relative h-full overflow-hidden rounded-2xl border p-5 shadow-[var(--shadow-card)]" style={{ animationDelay: `${delay}ms` }}>
      <div aria-hidden className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-[var(--primary)] to-transparent opacity-40" />
      <div className="flex items-center justify-between gap-2">
        <span className="text-[13px] text-muted-foreground">{label}</span>
        <span className="grid size-8 place-items-center rounded-xl border bg-muted/60 text-foreground transition-transform duration-300 group-hover:scale-110 group-hover:-rotate-6">
          <Icon className="size-4" aria-hidden />
        </span>
      </div>
      <p className="mt-3 text-[34px] font-semibold leading-none tracking-tight"><CountUp value={today} /></p>
      <div className="mt-2"><Delta today={today} yesterday={yesterday} /></div>
      <Sparkline points={series} className="mt-3" />
      <p className="mt-1 text-[10px] uppercase tracking-wider text-muted-foreground/70">Last 7 days · {series.reduce((a, b) => a + b, 0)} total</p>
    </div>
  );
  return href ? <Link href={href} className="block h-full rounded-2xl">{body}</Link> : body;
}

export function RateKpi({ label, value, hint, icon: Icon, delay = 0 }: { label: string; value: number | null; hint?: string; icon: LucideIcon; delay?: number }) {
  return (
    <div className="glass lift animate-rise flex h-full items-center gap-4 rounded-2xl border p-4 shadow-[var(--shadow-card)]" style={{ animationDelay: `${delay}ms` }}>
      <ProgressRing value={value ?? 0} size={58} stroke={6} trackClass="stroke-muted" barClass="stroke-[var(--primary)]">
        <Icon className="size-4 text-muted-foreground" aria-hidden />
      </ProgressRing>
      <div className="min-w-0">
        <p className="text-2xl font-semibold leading-none tracking-tight">
          {value == null ? <span className="text-base text-muted-foreground">—</span> : <CountUp value={value} suffix="%" />}
        </p>
        <p className="mt-1 text-[13px] text-muted-foreground">{label}</p>
        {hint && <p className="text-[11px] text-muted-foreground/70">{hint}</p>}
      </div>
    </div>
  );
}

export function CountKpi({ label, value, hint, icon: Icon, href, delay = 0 }: { label: string; value: number; hint?: string; icon: LucideIcon; href?: string; delay?: number }) {
  const body = (
    <div className="glass lift animate-rise flex h-full items-center gap-4 rounded-2xl border p-4 shadow-[var(--shadow-card)]" style={{ animationDelay: `${delay}ms` }}>
      <span className="grid size-[58px] shrink-0 place-items-center rounded-2xl border bg-muted/60">
        <Icon className="size-5" aria-hidden />
      </span>
      <div className="min-w-0">
        <p className="text-2xl font-semibold leading-none tracking-tight"><CountUp value={value} /></p>
        <p className="mt-1 text-[13px] text-muted-foreground">{label}</p>
        {hint && <p className="text-[11px] text-muted-foreground/70">{hint}</p>}
      </div>
    </div>
  );
  return href ? <Link href={href} className="block h-full rounded-2xl">{body}</Link> : body;
}
