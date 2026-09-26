"use client";

import { useEffect, useRef } from "react";

/**
 * Interactive 3D spiral galaxy on a 2D canvas, centred in the viewport.
 *  - ~8k stars on four arms, thicker near the core, with differential rotation.
 *  - Hover: stars near the pointer are pushed aside and brighten (gravitational "lens").
 *  - Click: a shockwave ring ripples outward and briefly spins the galaxy faster.
 *  - Drag: orbit the camera (tilt / yaw) in 3D; releases with inertia.
 *  - Monochrome white/silver arms with a warm core on pure black. Reduced motion: still frame.
 */
type Star = { r: number; a: number; y: number; speed: number; size: number; light: number; warm: number; alpha: number };

function makeGalaxy(count: number): Star[] {
  const stars: Star[] = [];
  const arms = 4;
  for (let i = 0; i < count; i++) {
    const arm = i % arms;
    const t = Math.pow(Math.random(), 0.6);
    const spread = (1 - t) * 0.5 + 0.07;
    const core = t < 0.16;
    stars.push({
      r: t + (Math.random() - 0.5) * 0.035,
      a: (arm / arms) * Math.PI * 2 + t * 5.4 + (Math.random() - 0.5) * spread * 1.7,
      y: (Math.random() - 0.5) * ((1 - t) * 0.085 + 0.012) * (core ? 2.6 : 1),
      speed: 0.11 / (0.24 + t),
      size: core ? Math.random() * 1.0 + 0.4 : Math.random() * 1.2 + 0.3,
      light: core ? 88 + Math.random() * 10 : 70 + Math.random() * 28,
      warm: core ? 1 : Math.random() < 0.08 ? 0.6 : 0, // a few warm giants in the arms
      alpha: core ? 0.95 : 0.4 + Math.random() * 0.55,
    });
  }
  return stars;
}

const isInteractive = (el: EventTarget | null) =>
  el instanceof Element && !!el.closest("input,button,a,textarea,select,label,form");

export function Galaxy({ className }: { className?: string }) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const small = window.innerWidth < 768;
    const stars = makeGalaxy(small ? 5000 : 12000);
    const offX = new Float32Array(stars.length);
    const offY = new Float32Array(stars.length);
    const field = Array.from({ length: small ? 200 : 420 }, () => ({
      x: Math.random(), y: Math.random(), s: Math.random() * 1.3 + 0.2, p: Math.random() * Math.PI * 2, d: Math.random() * 0.6 + 0.2,
    }));

    // Soft glow sprite for nebula dust (pre-rendered once, drawn many times)
    const sprite = document.createElement("canvas");
    sprite.width = sprite.height = 64;
    const sg = sprite.getContext("2d")!;
    const grad = sg.createRadialGradient(32, 32, 0, 32, 32, 32);
    grad.addColorStop(0, "rgba(255,255,255,0.55)");
    grad.addColorStop(0.35, "rgba(255,255,255,0.18)");
    grad.addColorStop(1, "rgba(255,255,255,0)");
    sg.fillStyle = grad;
    sg.fillRect(0, 0, 64, 64);
    const dust = Array.from({ length: small ? 140 : 320 }, (_, i) => {
      const t = Math.pow(Math.random(), 0.8) * 0.95 + 0.05;
      return { r: t, a: ((i % 4) / 4) * Math.PI * 2 + t * 5.4 + (Math.random() - 0.5) * 0.5,
               y: (Math.random() - 0.5) * 0.05, size: 0.06 + Math.random() * 0.12, alpha: 0.05 + Math.random() * 0.09,
               warm: Math.random() < 0.35 };
    });
    // Foreground stars drifting toward the viewer (real depth)
    const drift = Array.from({ length: small ? 90 : 200 }, () => ({ x: (Math.random() - 0.5) * 2, y: (Math.random() - 0.5) * 2, z: Math.random() }));
    const meteors: { x: number; y: number; vx: number; vy: number; life: number }[] = [];

    let w = 0, h = 0;
    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      w = canvas.clientWidth;
      h = canvas.clientHeight;
      canvas.width = Math.floor(w * dpr);
      canvas.height = Math.floor(h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();

    // interaction state
    const mouse = { x: -9999, y: -9999, inside: false };
    const look = { x: 0, y: 0 };
    const orbit = { yaw: 0, tilt: 1.08, vYaw: 0, vTilt: 0, dragging: false, lx: 0, ly: 0 };
    let spinBoost = 0;
    let zoomPulse = 0;
    const waves: { x: number; y: number; t: number }[] = [];

    const rect = () => canvas.getBoundingClientRect();
    const onMove = (e: PointerEvent) => {
      const r = rect();
      mouse.x = e.clientX - r.left;
      mouse.y = e.clientY - r.top;
      mouse.inside = true;
      look.x = e.clientX / window.innerWidth - 0.5;
      look.y = e.clientY / window.innerHeight - 0.5;
      if (orbit.dragging) {
        const dx = e.clientX - orbit.lx, dy = e.clientY - orbit.ly;
        orbit.vYaw = dx * 0.004;
        orbit.vTilt = dy * 0.003;
        orbit.lx = e.clientX;
        orbit.ly = e.clientY;
      }
    };
    const onDown = (e: PointerEvent) => {
      if (isInteractive(e.target)) return;
      orbit.dragging = true;
      orbit.lx = e.clientX;
      orbit.ly = e.clientY;
      document.body.style.cursor = "grabbing";
    };
    const onUp = () => {
      orbit.dragging = false;
      document.body.style.cursor = "";
    };
    const onClick = (e: MouseEvent) => {
      if (isInteractive(e.target)) return;
      const r = rect();
      waves.push({ x: e.clientX - r.left, y: e.clientY - r.top, t: 0 });
      spinBoost = Math.min(spinBoost + 1.4, 3);
      zoomPulse = 1;
    };
    const onLeave = () => { mouse.inside = false; mouse.x = mouse.y = -9999; };

    window.addEventListener("resize", resize);
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerdown", onDown);
    window.addEventListener("pointerup", onUp);
    window.addEventListener("click", onClick);
    document.addEventListener("pointerleave", onLeave);

    let frame = 0, time = 0, spin = 0, last = performance.now();

    const draw = (now: number) => {
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      time += dt;

      // camera: drag inertia + gentle pointer parallax
      if (!orbit.dragging) { orbit.vYaw *= 0.95; orbit.vTilt *= 0.9; }
      orbit.yaw += orbit.vYaw;
      orbit.tilt = Math.max(0.25, Math.min(1.45, orbit.tilt + orbit.vTilt));
      if (orbit.dragging) { orbit.vYaw *= 0.6; orbit.vTilt *= 0.6; }
      spinBoost *= 0.985;
      zoomPulse *= 0.93;
      spin += dt * (0.05 + spinBoost * 0.35);

      ctx.fillStyle = "#000";
      ctx.fillRect(0, 0, w, h);

      // parallax field stars (depth d) with twinkle
      for (const s of field) {
        const tw = 0.4 + 0.6 * Math.sin(time * 1.3 + s.p);
        ctx.fillStyle = `rgba(235,235,245,${(0.2 + tw * 0.55) * s.d})`;
        ctx.fillRect(s.x * w - look.x * 30 * s.d, s.y * h - look.y * 30 * s.d, s.s, s.s);
      }

      const cx = w / 2 - look.x * 14, cy = h / 2 - look.y * 14;
      const scale = Math.hypot(w, h) * (small ? 0.5 : 0.46) * (1 + zoomPulse * 0.06);
      const tilt = orbit.tilt + look.y * 0.18;
      const yaw = orbit.yaw + spin + look.x * 0.25;
      const cosT = Math.cos(tilt), sinT = Math.sin(tilt);
      const focal = 2.3;

      // warm core glow
      const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, scale * 0.45);
      g.addColorStop(0, "rgba(255,244,222,0.6)");
      g.addColorStop(0.2, "rgba(255,214,160,0.2)");
      g.addColorStop(0.55, "rgba(200,200,215,0.05)");
      g.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.ellipse(cx, cy, scale * 0.62, scale * 0.62 * Math.abs(cosT) + scale * 0.14, 0, 0, Math.PI * 2);
      ctx.fill();

      // nebula dust clouds riding the arms
      ctx.globalCompositeOperation = "lighter";
      for (const d of dust) {
        const ang = d.a + yaw + time * (0.11 / (0.24 + d.r)) * (reduce ? 0 : 1);
        const x = Math.cos(ang) * d.r, z0 = Math.sin(ang) * d.r;
        const y = d.y * cosT - z0 * sinT, z = d.y * sinT + z0 * cosT;
        const persp = focal / (focal + z);
        const size = d.size * scale * persp;
        ctx.globalAlpha = d.alpha * Math.min(1, persp);
        if (d.warm) ctx.filter = "sepia(1) saturate(1.6)";
        ctx.drawImage(sprite, cx + x * scale * persp - size / 2, cy + y * scale * persp - size / 2, size, size);
        ctx.filter = "none";
      }
      ctx.globalAlpha = 1;
      ctx.globalCompositeOperation = "source-over";

      // shockwaves
      for (const wv of waves) wv.t += dt;
      while (waves.length && waves[0].t > 2.2) waves.shift();

      ctx.globalCompositeOperation = "lighter";
      const R = 120; // hover influence radius (px)
      for (let i = 0; i < stars.length; i++) {
        const s = stars[i];
        const ang = s.a + yaw + time * s.speed * (reduce ? 0 : 1);
        const x = Math.cos(ang) * s.r;
        const z0 = Math.sin(ang) * s.r;
        const y = s.y * cosT - z0 * sinT;
        const z = s.y * sinT + z0 * cosT;
        const persp = focal / (focal + z);
        let px = cx + x * scale * persp;
        let py = cy + y * scale * persp;

        // hover lens: push away from the pointer
        let boost = 0;
        if (mouse.inside) {
          const dx = px - mouse.x, dy = py - mouse.y;
          const d2 = dx * dx + dy * dy;
          if (d2 < R * R && d2 > 0.01) {
            const d = Math.sqrt(d2);
            const f = (1 - d / R) ** 2;
            offX[i] += (dx / d) * f * 2.6;
            offY[i] += (dy / d) * f * 2.6;
            boost = f;
          }
        }
        // shockwave rings
        for (const wv of waves) {
          const radius = wv.t * 520;
          const dx = px - wv.x, dy = py - wv.y;
          const d = Math.sqrt(dx * dx + dy * dy) || 1;
          const band = Math.abs(d - radius);
          if (band < 40) {
            const f = (1 - band / 40) * (1 - wv.t / 2.2);
            offX[i] += (dx / d) * f * 3.2;
            offY[i] += (dy / d) * f * 3.2;
            boost = Math.max(boost, f);
          }
        }
        offX[i] *= 0.9;
        offY[i] *= 0.9;
        px += offX[i];
        py += offY[i];
        if (px < -4 || py < -4 || px > w + 4 || py > h + 4) continue;

        const size = s.size * persp * (1 + boost * 1.4);
        const light = Math.min(100, s.light + boost * 20);
        const a = Math.min(1, s.alpha * Math.min(1, persp) + boost * 0.5);
        ctx.fillStyle = s.warm ? `hsla(38,${60 * s.warm}%,${light}%,${a})` : `hsla(230,12%,${light}%,${a})`;
        ctx.fillRect(px, py, size, size);
      }
      ctx.globalCompositeOperation = "source-over";

      // foreground stars flying toward the viewer
      if (!reduce) {
        for (const p of drift) {
          p.z -= dt * 0.06;
          if (p.z <= 0.02) { p.z = 1; p.x = (Math.random() - 0.5) * 2; p.y = (Math.random() - 0.5) * 2; }
          const k = 0.35 / p.z;
          const sx = w / 2 + p.x * w * k * 0.5 - look.x * 60 / p.z;
          const sy = h / 2 + p.y * h * k * 0.5 - look.y * 60 / p.z;
          if (sx < 0 || sy < 0 || sx > w || sy > h) continue;
          const sz = Math.min(3.2, 0.6 / p.z);
          ctx.fillStyle = `rgba(255,255,255,${Math.min(0.9, (1 - p.z) * 1.1)})`;
          ctx.fillRect(sx, sy, sz, sz);
        }
        // occasional shooting star
        if (Math.random() < dt * 0.25) {
          meteors.push({ x: Math.random() * w, y: Math.random() * h * 0.5, vx: -(300 + Math.random() * 300), vy: 140 + Math.random() * 120, life: 1 });
        }
        for (const m of meteors) {
          m.x += m.vx * dt; m.y += m.vy * dt; m.life -= dt * 0.9;
          const tail = ctx.createLinearGradient(m.x, m.y, m.x - m.vx * 0.12, m.y - m.vy * 0.12);
          tail.addColorStop(0, `rgba(255,255,255,${Math.max(0, m.life)})`);
          tail.addColorStop(1, "rgba(255,255,255,0)");
          ctx.strokeStyle = tail;
          ctx.lineWidth = 1.4;
          ctx.beginPath();
          ctx.moveTo(m.x, m.y);
          ctx.lineTo(m.x - m.vx * 0.12, m.y - m.vy * 0.12);
          ctx.stroke();
        }
        while (meteors.length && meteors[0].life <= 0) meteors.shift();
      }

      // shockwave outlines
      for (const wv of waves) {
        const radius = wv.t * 520;
        ctx.strokeStyle = `rgba(255,255,255,${0.35 * (1 - wv.t / 2.2)})`;
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        ctx.arc(wv.x, wv.y, radius, 0, Math.PI * 2);
        ctx.stroke();
      }

      if (!reduce) frame = requestAnimationFrame(draw);
    };
    frame = requestAnimationFrame(draw);

    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("resize", resize);
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerdown", onDown);
      window.removeEventListener("pointerup", onUp);
      window.removeEventListener("click", onClick);
      document.removeEventListener("pointerleave", onLeave);
      document.body.style.cursor = "";
    };
  }, []);

  return <canvas ref={ref} className={className} aria-hidden />;
}
