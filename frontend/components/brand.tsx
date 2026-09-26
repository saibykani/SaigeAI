"use client";

import { useId } from "react";

import { cn } from "@/utils/cn";

/**
 * Saige AI mark: a four-point star at the centre of a tilted orbit, with a satellite that
 * travels the orbit. Uses the active theme's brand gradient.
 */
export function SaigeMark({ size = 32, animated = true, className }: { size?: number; animated?: boolean; className?: string }) {
  const id = useId().replace(/:/g, "");
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" className={cn("shrink-0", className)} role="img" aria-label="Saige AI">
      <defs>
        <linearGradient id={`g-${id}`} x1="0" y1="0" x2="64" y2="64" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="var(--brand-1)" />
          <stop offset="0.5" stopColor="var(--brand-2)" />
          <stop offset="1" stopColor="var(--brand-3)" />
        </linearGradient>
        <radialGradient id={`c-${id}`} cx="0.5" cy="0.5" r="0.5">
          <stop offset="0" stopColor="#fff" stopOpacity="0.95" />
          <stop offset="1" stopColor="#fff" stopOpacity="0" />
        </radialGradient>
        <path id={`o-${id}`} d="M6 32a26 11 -28 1 0 52 0a26 11 -28 1 0 -52 0" />
      </defs>
      <circle cx="32" cy="32" r="30" fill={`url(#g-${id})`} opacity="0.16" />
      <ellipse cx="32" cy="32" rx="26" ry="11" transform="rotate(-28 32 32)" fill="none" stroke={`url(#g-${id})`} strokeWidth="2.4" opacity="0.9" />
      {/* four-point star */}
      <path
        d="M32 14c1.6 8.2 5.8 12.4 14 14-8.2 1.6-12.4 5.8-14 14-1.6-8.2-5.8-12.4-14-14 8.2-1.6 12.4-5.8 14-14z"
        fill={`url(#g-${id})`}
      />
      <circle cx="32" cy="28" r="5" fill={`url(#c-${id})`} />
      {/* satellite */}
      <circle r="3.2" fill="#fff">
        {animated && <animateMotion dur="6s" repeatCount="indefinite" rotate="auto"><mpath href={`#o-${id}`} /></animateMotion>}
      </circle>
    </svg>
  );
}

export function Wordmark({ className, size = "md" }: { className?: string; size?: "md" | "xl" }) {
  return (
    <span className={cn("font-semibold tracking-tight", size === "xl" ? "text-5xl md:text-7xl" : "text-[17px]", className)}>
      Saige <span className="text-gradient animate-gradient">AI</span>
    </span>
  );
}
