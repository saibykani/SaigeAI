import type { CSSProperties, ReactNode } from "react";

import { cn } from "@/utils/cn";

/**
 * Processing indicator: a ring of small dots around a centre label. Indeterminate mode sweeps a glowing
 * arc around the ring (one CSS animation, staggered delays); determinate mode lights `value`% of the dots.
 * Pure SVG + CSS, no JS timers.
 */
export function DotRing({
  value, label, sub, size = 96, dots = 36, className,
}: {
  /** 0-100 for determinate progress; omit for an indeterminate sweep. */
  value?: number | null;
  /** Centre text, e.g. "Uploading…"; defaults to the % in determinate mode. */
  label?: ReactNode;
  sub?: ReactNode;
  size?: number;
  dots?: number;
  className?: string;
}) {
  const determinate = typeof value === "number" && Number.isFinite(value);
  const pct = determinate ? Math.max(0, Math.min(100, value as number)) : 0;
  const lit = Math.round((pct / 100) * dots);
  const dur = 1.4;
  const r = 44, dotR = Math.max(1.3, Math.min(2.6, 150 / dots / 1.6));
  const text = label ?? (determinate ? `${Math.round(pct)}%` : null);
  return (
    <div role={determinate ? "progressbar" : "status"} aria-live="polite"
      aria-valuenow={determinate ? Math.round(pct) : undefined} aria-valuemin={determinate ? 0 : undefined} aria-valuemax={determinate ? 100 : undefined}
      className={cn("dot-ring", !determinate && "dot-ring-sweep", className)} style={{ width: size, height: size }}>
      <svg viewBox="0 0 100 100" aria-hidden>
        {Array.from({ length: dots }, (_, i) => {
          const a = (i / dots) * Math.PI * 2 - Math.PI / 2;
          return (
            <circle key={i} cx={50 + Math.cos(a) * r} cy={50 + Math.sin(a) * r} r={dotR}
              className={cn("dot-ring-dot", determinate && i < lit && "on")}
              style={determinate ? undefined : ({ "--dr-delay": `${(-(dots - i) / dots) * dur}s`, "--dr-dur": `${dur}s` } as CSSProperties)} />
          );
        })}
      </svg>
      {(text || sub) && (
        <div className="dot-ring-label px-3">
          {text && <div className={cn("font-medium", size >= 80 ? "text-sm" : "text-[10px]")}>{text}</div>}
          {sub && <div className="text-[10px] text-muted-foreground">{sub}</div>}
        </div>
      )}
      {!text && <span className="sr-only">Working</span>}
    </div>
  );
}
