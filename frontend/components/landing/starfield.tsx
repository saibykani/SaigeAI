"use client";

import { useEffect, useRef } from "react";

/**
 * Lightweight cinematic background for the landing page: a slow starfield with a few drifting soft light
 * pools. One small canvas, capped device-pixel ratio, paused off-screen and in hidden tabs, and drawn once
 * (static) when the visitor prefers reduced motion.
 */
export function Starfield({ className }: { className?: string }) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let w = 0, h = 0, raf = 0, visible = true, last = 0;
    const count = window.innerWidth < 768 ? 140 : 320;
    const stars = Array.from({ length: count }, () => ({
      x: Math.random(), y: Math.random(), z: Math.random() * 0.8 + 0.2, p: Math.random() * Math.PI * 2,
    }));
    const pools = [
      { x: 0.2, y: 0.3, r: 0.55, a: 0.07, s: 0.00006 },
      { x: 0.8, y: 0.2, r: 0.45, a: 0.05, s: -0.00005 },
      { x: 0.55, y: 0.85, r: 0.6, a: 0.06, s: 0.00004 },
    ];

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
      w = canvas.clientWidth; h = canvas.clientHeight;
      canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    const draw = (t: number) => {
      ctx.fillStyle = "#000";
      ctx.fillRect(0, 0, w, h);
      for (const p of pools) {
        const cx = (p.x + Math.sin(t * p.s) * 0.08) * w, cy = (p.y + Math.cos(t * p.s) * 0.06) * h, r = p.r * Math.max(w, h);
        const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, r);
        g.addColorStop(0, `rgba(255,244,230,${p.a})`);
        g.addColorStop(1, "rgba(255,244,230,0)");
        ctx.fillStyle = g;
        ctx.fillRect(0, 0, w, h);
      }
      for (const s of stars) {
        const y = ((s.y + t * 0.000008 * s.z) % 1) * h;
        const tw = 0.55 + 0.45 * Math.sin(t * 0.0012 * s.z + s.p);
        ctx.globalAlpha = tw * s.z;
        ctx.fillStyle = "#fff";
        ctx.fillRect(s.x * w, y, s.z * 1.4, s.z * 1.4);
      }
      ctx.globalAlpha = 1;
    };

    const loop = (t: number) => {
      raf = 0;
      if (!visible || document.hidden) return;
      if (t - last > 33) { draw(t); last = t; } // ~30 fps is plenty for a slow drift
      raf = requestAnimationFrame(loop);
    };
    const start = () => { if (!reduce && !raf) raf = requestAnimationFrame(loop); };

    resize();
    draw(0);
    const ro = new ResizeObserver(() => { resize(); draw(last); });
    ro.observe(canvas);
    const io = new IntersectionObserver(([e]) => { visible = e.isIntersecting; if (visible) start(); });
    io.observe(canvas);
    const onVis = () => { if (!document.hidden) start(); };
    document.addEventListener("visibilitychange", onVis);
    start();
    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      io.disconnect();
      document.removeEventListener("visibilitychange", onVis);
    };
  }, []);

  return <canvas ref={ref} aria-hidden className={className} />;
}
