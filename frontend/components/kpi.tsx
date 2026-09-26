"use client";

import type { LucideIcon } from "lucide-react";
import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import Link from "next/link";
import { useId } from "react";

import { CountUp, ProgressRing } from "@/components/motion";
import { cn } from "@/utils/cn";

export type Tone = "green" | "orange" | "yellow" | "purple" | "red" | "mint" | "teal" | "lime";
const toneVar = (tone?: Tone) => (tone ? `var(--tone-${tone})` : "var(--primary)");

/** Solid single-accent surface: a soft wash of the card's one colour, never a mix of hues. */
function toneStyle(tone?: Tone, delay = 0): React.CSSProperties {
  const c = toneVar(tone);
  return {
    animationDelay: `${delay}ms`,
    ["--kpi" as string]: c,
    backgroundImage: tone ? `radial-gradient(120% 90% at 100% 0%, color-mix(in srgb, ${c} 20%, transparent), transparent 60%)` : undefined,
    borderColor: tone ? `color-mix(in srgb, ${c} 28%, transparent)` : undefined,
  };
}

function ToneIcon({ icon: Icon, tone, size = "sm" }: { icon: LucideIcon; tone?: Tone; size?: "sm" | "lg" }) {
  const c = toneVar(tone);
  return (
    <span
      className={cn("grid shrink-0 place-items-center transition-transform duration-300 group-hover:scale-110 group-hover:-rotate-6", size === "sm" ? "size-8 rounded-xl" : "size-[58px] rounded-2xl")}
      style={{ background: tone ? c : "var(--muted)", color: tone ? "#0b0b0c" : "var(--foreground)", boxShadow: tone ? `0 6px 18px -6px ${c}` : undefined }}
    >
      <Icon className={size === "sm" ? "size-4" : "size-5"} aria-hidden />
    </span>
  );
}

/** 7-point area sparkline in one hue (a trend, not categories). */
export function Sparkline({ points, className, tone }: { points: number[]; className?: string; tone?: Tone }) {
  const color = toneVar(tone);
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
          <stop offset="0" stopColor={color} stopOpacity="0.32" />
          <stop offset="1" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#sp-${id})`} />
      <path d={line} fill="none" stroke={color} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" vectorEffect="non-scaling-stroke" className="spark-draw" />
      <circle cx={lx} cy={ly} r="3" fill={color} />
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

export function TrendKpi({ label, series, icon, href, delay = 0, tone }: { label: string; series: number[]; icon: LucideIcon; href?: string; delay?: number; tone?: Tone }) {
  const today = series[series.length - 1] ?? 0;
  const yesterday = series[series.length - 2] ?? 0;
  const body = (
    <div className="glass lift animate-rise group relative h-full overflow-hidden rounded-2xl border p-5 shadow-[var(--shadow-card)]" style={toneStyle(tone, delay)}>
      <div aria-hidden className="pointer-events-none absolute inset-x-0 top-0 h-px opacity-70" style={{ background: `linear-gradient(90deg, transparent, ${toneVar(tone)}, transparent)` }} />
      <div className="flex items-center justify-between gap-2">
        <span className="text-[13px] text-muted-foreground">{label}</span>
        <ToneIcon icon={icon} tone={tone} />
      </div>
      <p className="mt-3 text-[34px] font-semibold leading-none tracking-tight"><CountUp value={today} /></p>
      <div className="mt-2"><Delta today={today} yesterday={yesterday} /></div>
      <Sparkline points={series} tone={tone} className="mt-3" />
      <p className="mt-1 text-[10px] uppercase tracking-wider text-muted-foreground/70">Last 7 days · {series.reduce((a, b) => a + b, 0)} total</p>
    </div>
  );
  return href ? <Link href={href} className="block h-full rounded-2xl">{body}</Link> : body;
}

export function RateKpi({ label, value, hint, icon: Icon, delay = 0, tone }: { label: string; value: number | null; hint?: string; icon: LucideIcon; delay?: number; tone?: Tone }) {
  return (
    <div className="glass lift animate-rise group flex h-full items-center gap-4 rounded-2xl border p-4 shadow-[var(--shadow-card)]" style={toneStyle(tone, delay)}>
      <ProgressRing value={value ?? 0} size={58} stroke={6} trackClass="stroke-muted" barClass="stroke-[var(--kpi)]">
        <Icon className="size-4" style={{ color: toneVar(tone) }} aria-hidden />
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

export function CountKpi({ label, value, hint, icon, href, delay = 0, tone }: { label: string; value: number; hint?: string; icon: LucideIcon; href?: string; delay?: number; tone?: Tone }) {
  const body = (
    <div className="glass lift animate-rise group flex h-full items-center gap-4 rounded-2xl border p-4 shadow-[var(--shadow-card)]" style={toneStyle(tone, delay)}>
      <ToneIcon icon={icon} tone={tone} size="lg" />
      <div className="min-w-0">
        <p className="text-2xl font-semibold leading-none tracking-tight"><CountUp value={value} /></p>
        <p className="mt-1 text-[13px] text-muted-foreground">{label}</p>
        {hint && <p className="text-[11px] text-muted-foreground/70">{hint}</p>}
      </div>
    </div>
  );
  return href ? <Link href={href} className="block h-full rounded-2xl">{body}</Link> : body;
}
