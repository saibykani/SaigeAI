"use client";

import { useEffect, useRef, useState } from "react";

function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
}

/** Animated number that counts up from 0 (or its previous value) to `value`. */
export function CountUp({ value, duration = 900, suffix = "" }: { value: number; duration?: number; suffix?: string }) {
  const [shown, setShown] = useState(prefersReducedMotion() ? value : 0);
  const from = useRef(0);

  useEffect(() => {
    if (prefersReducedMotion()) {
      setShown(value);
      return;
    }
    const start = performance.now();
    const origin = from.current;
    let frame = 0;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      setShown(Math.round(origin + (value - origin) * eased));
      if (t < 1) frame = requestAnimationFrame(tick);
      else from.current = value;
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [value, duration]);

  return (
    <>
      {shown.toLocaleString()}
      {suffix}
    </>
  );
}

/** Circular progress ring that animates to `value` (0-100). */
export function ProgressRing({
  value,
  size = 96,
  stroke = 9,
  trackClass = "stroke-white/25",
  barClass = "stroke-white",
  children,
}: {
  value: number;
  size?: number;
  stroke?: number;
  trackClass?: string;
  barClass?: string;
  children?: React.ReactNode;
}) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const [pct, setPct] = useState(prefersReducedMotion() ? value : 0);
  useEffect(() => {
    const id = requestAnimationFrame(() => setPct(value));
    return () => cancelAnimationFrame(id);
  }, [value]);
  return (
    <div className="relative" style={{ width: size, height: size }} role="img" aria-label={`${value}%`}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth={stroke} className={trackClass} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          strokeWidth={stroke}
          strokeLinecap="round"
          className={barClass}
          strokeDasharray={c}
          strokeDashoffset={c - (c * Math.max(0, Math.min(100, pct))) / 100}
          style={{ transition: "stroke-dashoffset 1.1s cubic-bezier(0.2, 0.8, 0.2, 1)" }}
        />
      </svg>
      <div className="absolute inset-0 grid place-items-center">{children}</div>
    </div>
  );
}

/** Staggered entrance for a list of children: each child rises in sequence. */
export function Stagger({ children, step = 45, className }: { children: React.ReactNode[]; step?: number; className?: string }) {
  return (
    <div className={className}>
      {children.map((child, i) => (
        <div key={i} className="animate-rise" style={{ animationDelay: `${i * step}ms` }}>
          {child}
        </div>
      ))}
    </div>
  );
}
