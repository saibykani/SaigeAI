"use client";

import { useEffect, useRef } from "react";

/**
 * Animated 3D spiral galaxy on a 2D canvas.
 * - ~7k stars on four logarithmic arms, thicker near the core, with differential rotation
 *   (inner stars orbit faster), projected through a tilted perspective camera.
 * - Pointer moves tilt/rotate the camera for parallax; twinkling field stars behind.
 * - Additive blending for glow. Honors prefers-reduced-motion (renders one still frame).
 */
type Star = { r: number; a: number; y: number; speed: number; size: number; hue: number; light: number; alpha: number };

function makeGalaxy(count: number): Star[] {
  const stars: Star[] = [];
  const arms = 4;
  for (let i = 0; i < count; i++) {
    const arm = i % arms;
    const t = Math.pow(Math.random(), 0.62); // denser toward the core
    const r = t * 1.0;
    const spread = (1 - t) * 0.55 + 0.08;
    const a = (arm / arms) * Math.PI * 2 + r * 5.2 + (Math.random() - 0.5) * spread * 1.6;
    const thickness = (1 - t) * 0.09 + 0.012;
    const core = t < 0.18;
    stars.push({
      r: r + (Math.random() - 0.5) * 0.04,
      a,
      y: (Math.random() - 0.5) * thickness * (core ? 2.4 : 1),
      speed: 0.12 / (0.25 + r), // Keplerian-ish: faster near the centre
      size: core ? Math.random() * 1.6 + 0.6 : Math.random() * 1.3 + 0.35,
      // core warm white/gold -> arms blue/violet with pink HII regions
      hue: core ? 38 + Math.random() * 18 : Math.random() < 0.12 ? 320 + Math.random() * 20 : 205 + Math.random() * 60,
      light: core ? 82 + Math.random() * 12 : 62 + Math.random() * 25,
      alpha: core ? 0.9 : 0.45 + Math.random() * 0.5,
    });
  }
  return stars;
}

export function Galaxy({ className }: { className?: string }) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d", { alpha: true });
    if (!ctx) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const small = window.innerWidth < 768;
    const stars = makeGalaxy(small ? 3500 : 7000);
    const field = Array.from({ length: small ? 180 : 360 }, () => ({
      x: Math.random(), y: Math.random(), s: Math.random() * 1.2 + 0.2, p: Math.random() * Math.PI * 2,
    }));

    let w = 0, h = 0, dpr = 1;
    const resize = () => {
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      w = canvas.clientWidth;
      h = canvas.clientHeight;
      canvas.width = Math.floor(w * dpr);
      canvas.height = Math.floor(h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    window.addEventListener("resize", resize);

    const pointer = { x: 0, y: 0 }, cam = { x: 0, y: 0 };
    const onMove = (e: PointerEvent) => {
      pointer.x = e.clientX / window.innerWidth - 0.5;
      pointer.y = e.clientY / window.innerHeight - 0.5;
    };
    window.addEventListener("pointermove", onMove);

    let frame = 0;
    let time = 0;
    let last = performance.now();

    const draw = (now: number) => {
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      time += dt;
      cam.x += (pointer.x - cam.x) * 0.04;
      cam.y += (pointer.y - cam.y) * 0.04;

      ctx.clearRect(0, 0, w, h);
      ctx.globalCompositeOperation = "source-over";

      // twinkling field stars
      for (const s of field) {
        const tw = 0.45 + 0.55 * Math.sin(time * 1.4 + s.p);
        ctx.fillStyle = `rgba(210,225,255,${0.25 + tw * 0.5})`;
        ctx.fillRect(s.x * w + cam.x * -12, s.y * h + cam.y * -12, s.s, s.s);
      }

      const cx = w * 0.5, cy = h * 0.5;
      const scale = Math.min(w, h) * 0.62;
      const tilt = 1.05 + cam.y * 0.35; // radians around X
      const spin = time * 0.05 + cam.x * 0.6;
      const cosT = Math.cos(tilt), sinT = Math.sin(tilt);
      const focal = 2.2;

      // core glow
      const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, scale * 0.42);
      g.addColorStop(0, "rgba(255,236,200,0.55)");
      g.addColorStop(0.25, "rgba(255,190,140,0.18)");
      g.addColorStop(0.6, "rgba(120,110,255,0.07)");
      g.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.ellipse(cx, cy, scale * 0.6, scale * 0.6 * Math.abs(cosT) + scale * 0.12, 0, 0, Math.PI * 2);
      ctx.fill();

      ctx.globalCompositeOperation = "lighter";
      for (const s of stars) {
        const ang = s.a + spin + time * s.speed * (reduce ? 0 : 1);
        const x = Math.cos(ang) * s.r;
        const z0 = Math.sin(ang) * s.r;
        // tilt around X axis
        const y = s.y * cosT - z0 * sinT;
        const z = s.y * sinT + z0 * cosT;
        const persp = focal / (focal + z);
        const px = cx + x * scale * persp;
        const py = cy + y * scale * persp;
        if (px < -4 || py < -4 || px > w + 4 || py > h + 4) continue;
        const size = s.size * persp;
        ctx.fillStyle = `hsla(${s.hue},90%,${s.light}%,${s.alpha * Math.min(1, persp)})`;
        ctx.fillRect(px, py, size, size);
      }
      ctx.globalCompositeOperation = "source-over";
      if (!reduce) frame = requestAnimationFrame(draw);
    };
    frame = requestAnimationFrame(draw);

    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("resize", resize);
      window.removeEventListener("pointermove", onMove);
    };
  }, []);

  return <canvas ref={ref} className={className} aria-hidden />;
}
