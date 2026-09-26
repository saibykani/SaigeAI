"use client";

import { Check } from "lucide-react";
import { useEffect, useRef, useState } from "react";

type Burst = { id: number; label: string; tone: string };

function describe(method: string, path: string): { label: string; tone: string } {
  const p = path.split("?")[0];
  if (method === "DELETE") return { label: "Removed", tone: "red" };
  if (/send|approve-bulk|mark-applied|\/approve$/.test(p)) return { label: /mark-applied/.test(p) ? "Marked as applied" : "Done · sent", tone: "green" };
  if (/save|feed\/save|discover\/save/.test(p)) return { label: "Saved", tone: "green" };
  if (/sync/.test(p)) return { label: "Synced", tone: "teal" };
  if (/draft|tailor|cover-letter|ats-optimize|optimi/.test(p)) return { label: "Created", tone: "purple" };
  if (/run|refresh/.test(p)) return { label: "Running", tone: "orange" };
  if (method === "POST") return { label: "Created", tone: "green" };
  return { label: "Saved", tone: "green" };
}

/** A short, happy confirmation after any save / create / send: a badge flips in with a burst of sparks. */
export function Celebrate() {
  const [bursts, setBursts] = useState<Burst[]>([]);
  const last = useRef(0);
  useEffect(() => {
    const on = (e: Event) => {
      const now = Date.now();
      if (now - last.current < 1200) return; // bulk actions: one celebration
      last.current = now;
      const { method, path } = (e as CustomEvent<{ method: string; path: string }>).detail;
      const b = { id: now, ...describe(method, path) };
      setBursts((x) => [...x, b]);
      window.setTimeout(() => setBursts((x) => x.filter((y) => y.id !== b.id)), 1800);
    };
    window.addEventListener("saige:done", on);
    return () => window.removeEventListener("saige:done", on);
  }, []);
  return (
    <div aria-live="polite" className="pointer-events-none fixed bottom-8 left-1/2 z-[70] -translate-x-1/2">
      {bursts.map((b) => (
        <div key={b.id} className="celebrate relative flex items-center gap-2.5 rounded-full border bg-card-solid py-2 pl-2 pr-4 text-sm font-medium shadow-[0_20px_50px_-15px_rgba(0,0,0,.55)]">
          <span className="celebrate-badge grid size-7 place-items-center rounded-full text-[#0b0b0c]" style={{ background: `var(--tone-${b.tone})` }}>
            <Check className="size-4" strokeWidth={3} />
          </span>
          {b.label}
          {Array.from({ length: 10 }, (_, i) => {
            const a = (i / 10) * Math.PI * 2;
            return (
              <span key={i} className="celebrate-spark absolute left-5 top-1/2 size-1.5 rounded-full"
                style={{ background: i % 2 ? `var(--tone-${b.tone})` : "#fff", ["--dx" as string]: `${Math.cos(a) * 46}px`, ["--dy" as string]: `${Math.sin(a) * 34}px` }} />
            );
          })}
        </div>
      ))}
    </div>
  );
}
