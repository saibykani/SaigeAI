import type { LucideIcon } from "lucide-react";
import Link from "next/link";

import { CountUp } from "@/components/motion";
import { cn } from "@/utils/cn";

/** Categorical slot (1-8) from the validated palette. Colour marks identity on the icon chip
 *  and accent bar only; label and value always stay in text ink. */
export type Slot = 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8;

export function StatTile({
  label,
  value,
  icon: Icon,
  slot,
  hint,
  href,
  delay = 0,
}: {
  label: string;
  value: number;
  icon: LucideIcon;
  slot: Slot;
  hint?: string;
  href?: string;
  delay?: number;
}) {
  const color = `var(--series-${slot})`;
  const body = (
    <div
      className="glass lift animate-rise group relative h-full overflow-hidden rounded-2xl border p-4 shadow-[var(--shadow-card)]"
      style={{ animationDelay: `${delay}ms` }}
    >
      {/* soft colour glow in the corner */}
      <div
        aria-hidden
        className="pointer-events-none absolute -right-8 -top-8 size-24 rounded-full opacity-[0.14] blur-2xl transition-opacity duration-300 group-hover:opacity-30"
        style={{ background: color }}
      />
      <div className="flex items-center justify-between">
        <span
          className="grid size-9 place-items-center rounded-xl text-white shadow-sm transition-transform duration-300 group-hover:scale-110 group-hover:-rotate-6"
          style={{ background: `linear-gradient(135deg, ${color}, color-mix(in srgb, ${color} 70%, #000))` }}
        >
          <Icon className="size-[18px]" aria-hidden />
        </span>
      </div>
      <p className="mt-4 text-[28px] font-semibold leading-none tracking-tight">
        <CountUp value={value} />
      </p>
      <p className="mt-1.5 text-[13px] text-muted-foreground">{label}</p>
      {hint && <p className="mt-0.5 text-[11px] text-muted-foreground/80">{hint}</p>}
      <div aria-hidden className="absolute inset-x-0 bottom-0 h-[3px] animate-grow-x" style={{ background: color, animationDelay: `${delay + 200}ms` }} />
    </div>
  );
  return href ? (
    <Link href={href} className={cn("block h-full rounded-2xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring")}>
      {body}
    </Link>
  ) : (
    body
  );
}
