"use client";

import { useEffect, useState } from "react";

import { cn } from "@/utils/cn";

const DEFAULT = ["Reading your resume…", "Finding your roles and dates…", "Extracting skills and tools…", "Matching against the job…",
  "Checking every claim against your profile…", "Polishing the wording…", "Almost there…"];

/**
 * Resume-scanning animation: a paper page drifts up and down while a laser line sweeps it and lines light up as they
 * are "read", with guidance words that change every ~1.6 s. Use while parsing, scoring or generating.
 */
export function ScanLoader({ messages = DEFAULT, title, className, compact = false }: { messages?: string[]; title?: string; className?: string; compact?: boolean }) {
  const [i, setI] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setI((n) => (n + 1) % messages.length), 1600);
    return () => clearInterval(t);
  }, [messages.length]);
  const lines = [72, 48, 90, 84, 60, 0, 40, 92, 78, 86, 54, 0, 36, 88, 70, 80, 62, 0, 44, 90, 66];
  return (
    <div role="status" aria-live="polite" className={cn("flex flex-col items-center gap-5 py-8", className)}>
      <div className={cn("scan-stage relative", compact ? "h-40 w-32" : "h-56 w-44")}>
        <div className="scan-paper absolute inset-0 overflow-hidden rounded-xl border bg-white shadow-[0_18px_40px_-18px_rgba(0,0,0,.35)]">
          <div className="scan-doc px-4 pt-4">
            <div className="mb-3 flex items-center gap-2">
              <span className="size-6 rounded-full bg-[var(--primary)] opacity-80" />
              <span className="h-2 w-16 rounded-full bg-neutral-800/80" />
            </div>
            {[...lines, ...lines].map((w, k) => (
              <span key={k} className={cn("scan-line mb-1.5 block h-1.5 rounded-full", w ? "bg-neutral-300" : "h-3 bg-transparent")}
                style={{ width: `${w || 10}%`, animationDelay: `${(k % lines.length) * 0.11}s` }} />
            ))}
          </div>
        </div>
        <div className="scan-laser pointer-events-none absolute inset-x-[-10%] h-10" />
        <span className="scan-corner left-[-6px] top-[-6px] border-l-2 border-t-2" />
        <span className="scan-corner right-[-6px] top-[-6px] border-r-2 border-t-2" />
        <span className="scan-corner bottom-[-6px] left-[-6px] border-b-2 border-l-2" />
        <span className="scan-corner bottom-[-6px] right-[-6px] border-b-2 border-r-2" />
      </div>
      {title && <p className="text-lg">{title}</p>}
      <p key={i} className="scan-word text-sm text-muted-foreground">{messages[i]}</p>
    </div>
  );
}
