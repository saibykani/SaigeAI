"use client";

import { cn } from "@/utils/cn";

/** Saige AI mark: the user's logo (black ellipse + half-ellipse bowl on off-white), same art as app/icon.svg. */
export function SaigeMark({ size = 32, className }: { size?: number; animated?: boolean; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 768 768" className={cn("shrink-0 rounded-[22%]", className)} role="img" aria-label="Saige AI">
      <rect width="768" height="768" fill="#ecebe7" />
      <ellipse cx="262.5" cy="384" rx="122.5" ry="244" fill="#000" />
      <path d="M385 383H627A121 245 0 0 1 385 383Z" fill="#000" />
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
