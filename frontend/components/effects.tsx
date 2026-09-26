"use client";

import { useEffect } from "react";

/**
 * App-wide micro-interactions:
 *  - a click ring with a few sparks in the current section's colour,
 *  - 3D tilt: cards with the `lift` class lean toward the pointer while hovered.
 * Both respect reduced motion (CSS disables them) and never block clicks.
 */
export function Effects({ tone = "green" }: { tone?: string }) {
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const onClick = (e: MouseEvent) => {
      const color = `var(--tone-${tone})`;
      const ring = document.createElement("span");
      ring.className = "click-ring";
      ring.style.left = `${e.clientX}px`;
      ring.style.top = `${e.clientY}px`;
      ring.style.setProperty("--click-tone", color);
      document.body.appendChild(ring);
      setTimeout(() => ring.remove(), 600);
      for (let i = 0; i < 6; i++) {
        const a = (i / 6) * Math.PI * 2 + Math.random() * 0.5;
        const d = 16 + Math.random() * 14;
        const s = document.createElement("span");
        s.className = "click-spark";
        s.style.left = `${e.clientX}px`;
        s.style.top = `${e.clientY}px`;
        s.style.setProperty("--dx", `${Math.cos(a) * d}px`);
        s.style.setProperty("--dy", `${Math.sin(a) * d}px`);
        s.style.setProperty("--click-tone", color);
        document.body.appendChild(s);
        setTimeout(() => s.remove(), 650);
      }
    };
    const onMove = (e: PointerEvent) => {
      const el = (e.target as Element | null)?.closest?.(".lift") as HTMLElement | null;
      if (!el) return;
      const r = el.getBoundingClientRect();
      const x = (e.clientX - r.left) / r.width - 0.5, y = (e.clientY - r.top) / r.height - 0.5;
      el.style.setProperty("--ry", `${(x * 6).toFixed(2)}deg`);
      el.style.setProperty("--rx", `${(-y * 6).toFixed(2)}deg`);
    };
    window.addEventListener("click", onClick);
    window.addEventListener("pointermove", onMove, { passive: true });
    return () => { window.removeEventListener("click", onClick); window.removeEventListener("pointermove", onMove); };
  }, [tone]);
  return null;
}
