"use client";

import { useEffect, useRef } from "react";

/**
 * Interactive 3D spiral galaxy on a 2D canvas, centred in the viewport.
 *  - Stars on four logarithmic arms, a flattened 3D core bulge, dark dust lanes along the arms,
 *    warm core stars fading to white in the arms, soft halos on the brightest stars.
 *  - Hover: stars near the pointer are nudged aside and brighten.
 *  - Click: nearby stars gently spread apart and drift back. No flash, ring or spin burst.
 *  - Drag: orbit the camera (tilt / yaw) in 3D; releases with inertia.
 *  - Horizontal and slightly tilted, spread across the whole screen, with a glowing bulge and dust lanes.
 *  - Our solar system sits out on one of the arms and travels with the galaxy: the Sun, its planets on
 *    their orbits, and a small blue planet (with its moon) revolving around it.
 *  - Comets fall slowly across the sky, and a shooting star crosses it every 2-3 seconds.
 *  - Slow, stately rotation. Reduced motion: still frame.
 * Performance: stars are pre-sorted into a few colour buckets, so each frame sets fillStyle only a
 * handful of times; glows are pre-rendered sprites (no canvas filters).
 */
type Star = { r: number; a: number; y: number; speed: number; size: number; bucket: number; halo: boolean };

// Colour buckets from the warm core to cool-white arms: [r, g, b, alpha].
const BUCKETS: [number, number, number, number][] = [
  [255, 224, 180, 0.95], // core giants
  [255, 236, 208, 0.85],
  [250, 244, 232, 0.75],
  [238, 240, 246, 0.7], // arm stars
  [228, 232, 242, 0.55],
  [214, 220, 236, 0.4], // faint outer stars
];

function makeGalaxy(count: number): Star[] {
  const stars: Star[] = [];
  const arms = 4;
  for (let i = 0; i < count; i++) {
    const inBulge = i % 7 === 0;
    const t = inBulge ? Math.pow(Math.random(), 1.8) * 0.28 : Math.pow(Math.random(), 0.65);
    const arm = i % arms;
    const spread = (1 - t) * 0.45 + 0.06;
    const a = inBulge ? Math.random() * Math.PI * 2 : (arm / arms) * Math.PI * 2 + t * 5.2 + (Math.random() - 0.5) * spread * 1.6;
    // Bulge is a flattened sphere; the disc thins toward the edge.
    const thickness = inBulge ? (0.28 - t) * 0.55 : (1 - t) * 0.06 + 0.008;
    const bucket = inBulge || t < 0.12 ? (Math.random() < 0.5 ? 0 : 1) : t < 0.3 ? 2 : t < 0.65 ? 3 : Math.random() < 0.5 ? 4 : 5;
    stars.push({
      r: t + (Math.random() - 0.5) * 0.03,
      a,
      y: (Math.random() - 0.5) * thickness,
      speed: 0.11 / (0.24 + t),
      size: Math.random() < 0.02 ? 1.8 + Math.random() * 1.2 : 0.35 + Math.random() * 1.05,
      bucket,
      halo: Math.random() < 0.012,
    });
  }
  // Group by bucket once so drawing sets each colour only once per frame.
  return stars.sort((p, q) => p.bucket - q.bucket);
}

function glowSprite(rgb: string, stops: [number, number][]): HTMLCanvasElement {
  const c = document.createElement("canvas");
  c.width = c.height = 64;
  const g = c.getContext("2d")!;
  const grad = g.createRadialGradient(32, 32, 0, 32, 32, 32);
  for (const [at, alpha] of stops) grad.addColorStop(at, `rgba(${rgb},${alpha})`);
  g.fillStyle = grad;
  g.fillRect(0, 0, 64, 64);
  return c;
}

const isInteractive = (el: EventTarget | null) =>
  el instanceof Element && !!el.closest("input,button,a,textarea,select,label,form");

export function Galaxy({ className }: { className?: string }) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    const ctx = canvas?.getContext("2d", { alpha: false });
    if (!canvas || !ctx) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const small = window.innerWidth < 768;
    const stars = makeGalaxy(small ? 4500 : 9000);
    const offX = new Float32Array(stars.length);
    const offY = new Float32Array(stars.length);
    const velX = new Float32Array(stars.length);
    const velY = new Float32Array(stars.length);
    const field = Array.from({ length: small ? 180 : 380 }, () => ({
      x: Math.random(), y: Math.random(), s: Math.random() * 1.2 + 0.2, p: Math.random() * Math.PI * 2, d: Math.random() * 0.6 + 0.2,
    }));

    const whiteGlow = glowSprite("255,255,255", [[0, 0.5], [0.35, 0.16], [1, 0]]);
    const warmGlow = glowSprite("255,200,140", [[0, 0.45], [0.4, 0.14], [1, 0]]);
    const darkDust = glowSprite("0,0,0", [[0, 0.55], [0.5, 0.25], [1, 0]]);
    const starHalo = glowSprite("255,250,240", [[0, 0.9], [0.15, 0.35], [0.5, 0.06], [1, 0]]);

    // Luminous nebula clouds on the arms, and dark dust lanes just inside them.
    const clouds = Array.from({ length: small ? 110 : 240 }, (_, i) => {
      const t = Math.pow(Math.random(), 0.8) * 0.9 + 0.08;
      return { r: t, a: ((i % 4) / 4) * Math.PI * 2 + t * 5.2 + (Math.random() - 0.5) * 0.45, y: (Math.random() - 0.5) * 0.04,
               size: 0.07 + Math.random() * 0.13, alpha: 0.05 + Math.random() * 0.08, warm: t < 0.45 && Math.random() < 0.6 };
    });
    const lanes = Array.from({ length: small ? 70 : 150 }, (_, i) => {
      const t = Math.random() * 0.7 + 0.14;
      return { r: t, a: ((i % 4) / 4) * Math.PI * 2 + t * 5.2 - 0.22, y: 0, size: 0.05 + Math.random() * 0.07, alpha: 0.35 + Math.random() * 0.3 };
    });
    // A faint band of the far Milky Way behind everything.
    const band = Array.from({ length: small ? 250 : 600 }, () => {
      const u = Math.random();
      return { u, v: (Math.random() + Math.random() + Math.random() - 1.5) * 0.08, s: Math.random() * 0.9 + 0.2, a: Math.random() * 0.35 + 0.05 };
    });
    const meteors: { x: number; y: number; vx: number; vy: number; life: number }[] = [];

    let w = 0, h = 0;
    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
      w = canvas.clientWidth;
      h = canvas.clientHeight;
      canvas.width = Math.floor(w * dpr);
      canvas.height = Math.floor(h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();

    const mouse = { x: -9999, y: -9999, inside: false };
    const look = { x: 0, y: 0 };
    const orbit = { yaw: 0.6, tilt: 0.38, vYaw: 0, vTilt: 0, dragging: false, lx: 0, ly: 0, moved: 0 };
    // A distant solar system: a warm star with planets on tilted orbits (radius, size, speed, colour).
    const planets = [
      { r: 9, s: 0.9, v: 4.1, c: "190,180,170", earth: false }, { r: 14, s: 1.4, v: 1.6, c: "236,204,150", earth: false },
      { r: 20, s: 1.6, v: 1.0, c: "86,156,214", earth: true }, { r: 27, s: 1.2, v: 0.53, c: "214,110,70", earth: false },
      { r: 40, s: 3.2, v: 0.084, c: "222,186,140", earth: false }, { r: 52, s: 2.7, v: 0.034, c: "230,210,160", earth: false },
    ].map((p) => ({ ...p, a: Math.random() * Math.PI * 2 }));
    const sunArm = 1.2; // starts in the open lower-middle of the screen, then travels with the galaxy
    const comets: { x: number; y: number; vx: number; vy: number; life: number; size: number }[] = [];
    const ripples: { x: number; y: number; t: number }[] = [];
    const spreads: { x: number; y: number }[] = [];

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
        orbit.moved += Math.abs(dx) + Math.abs(dy);
        orbit.vYaw = dx * 0.0035;
        orbit.vTilt = dy * 0.0025;
        orbit.lx = e.clientX;
        orbit.ly = e.clientY;
      }
    };
    const onDown = (e: PointerEvent) => {
      if (isInteractive(e.target)) return;
      orbit.dragging = true;
      orbit.moved = 0;
      orbit.lx = e.clientX;
      orbit.ly = e.clientY;
      document.body.style.cursor = "grabbing";
    };
    const onUp = () => {
      orbit.dragging = false;
      document.body.style.cursor = "";
    };
    const onClick = (e: MouseEvent) => {
      if (isInteractive(e.target) || orbit.moved > 6) return; // a drag isn't a click
      const r = rect();
      spreads.push({ x: e.clientX - r.left, y: e.clientY - r.top });
      ripples.push({ x: e.clientX - r.left, y: e.clientY - r.top, t: 0 });
    };
    const onLeave = () => { mouse.inside = false; mouse.x = mouse.y = -9999; };

    window.addEventListener("resize", resize);
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerdown", onDown);
    window.addEventListener("pointerup", onUp);
    window.addEventListener("click", onClick);
    document.addEventListener("pointerleave", onLeave);

    let frame = 0, time = 0, last = performance.now();
    let nextMeteor = performance.now() + 800;
    const ROT = 0.4; // rotation speed factor

    const project = (r: number, a: number, y0: number, yaw: number, cosT: number, sinT: number, focal: number) => {
      const ang = a + yaw;
      const x = Math.cos(ang) * r, z0 = Math.sin(ang) * r;
      const y = y0 * cosT - z0 * sinT, z = y0 * sinT + z0 * cosT;
      const persp = focal / (focal + z);
      return { x, y, persp };
    };

    const draw = (now: number) => {
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      time += reduce ? 0 : dt;

      if (!orbit.dragging) { orbit.vYaw *= 0.94; orbit.vTilt *= 0.9; }
      orbit.yaw += orbit.vYaw;
      orbit.tilt = Math.max(0.04, Math.min(1.42, orbit.tilt + orbit.vTilt));
      if (orbit.dragging) { orbit.vYaw *= 0.6; orbit.vTilt *= 0.6; }

      ctx.fillStyle = "#000";
      ctx.fillRect(0, 0, w, h);

      // Far Milky Way band (diagonal), then twinkling field stars with parallax.
      ctx.fillStyle = "rgb(225,228,240)";
      for (const b of band) {
        const bx = b.u * w * 1.3 - w * 0.15 - look.x * 8;
        const by = h * 0.62 - b.u * h * 0.25 + b.v * h - look.y * 8;
        ctx.globalAlpha = b.a * 0.6;
        ctx.fillRect(bx, by, b.s, b.s);
      }
      for (const s of field) {
        ctx.globalAlpha = (0.2 + (0.4 + 0.6 * Math.sin(time * 1.1 + s.p)) * 0.5) * s.d;
        ctx.fillRect(s.x * w - look.x * 26 * s.d, s.y * h - look.y * 26 * s.d, s.s, s.s);
      }
      ctx.globalAlpha = 1;

      const cx = w / 2 - look.x * 12, cy = h / 2 - look.y * 12;
      const scale = Math.max(w, h) * (small ? 0.66 : 0.6); // spread across the whole screen
      const tilt = orbit.tilt + look.y * 0.12 + Math.sin(time * 0.05) * 0.04;
      const yaw = orbit.yaw + time * 0.02 + look.x * 0.2;
      const cosT = Math.cos(tilt), sinT = Math.sin(tilt);
      const focal = 2; // stronger perspective: the near side of the disc is visibly closer
      // Roll the whole galaxy so its long axis runs top-to-bottom (slightly diagonal).
      const roll = -0.14 + look.x * 0.03; // horizontal, slightly tilted
      const cr = Math.cos(roll), sr = Math.sin(roll);
      const toLocal = (x: number, y: number) => ({ x: (x - cx) * cr + (y - cy) * sr, y: -(x - cx) * sr + (y - cy) * cr });
      const reach = Math.hypot(w, h) / 2 + 8;
      ctx.save();
      ctx.translate(cx, cy);
      ctx.rotate(roll);

      // Disc glow and the 3D core bulge (an ellipsoid: wider than it is tall, squashed by tilt).
      // Circular gradients squashed vertically give smooth elliptical falloff (no hard edges).
      const glow = (radius: number, squash: number, stops: [number, string][]) => {
        const g = ctx.createRadialGradient(0, 0, 0, 0, 0, radius);
        for (const [at, c] of stops) g.addColorStop(at, c);
        ctx.save();
        ctx.scale(1, squash);
        ctx.fillStyle = g;
        ctx.fillRect(-radius, -radius, radius * 2, radius * 2);
        ctx.restore();
      };
      glow(scale * 0.95, Math.max(0.2, Math.abs(sinT) * 1.4), [[0, "rgba(255,236,210,0.13)"], [0.45, "rgba(210,212,228,0.03)"], [1, "rgba(0,0,0,0)"]]);
      glow(scale * 0.26, 0.42 + 0.5 * Math.abs(cosT), [[0, "rgba(255,248,232,0.95)"], [0.1, "rgba(255,228,184,0.55)"], [0.4, "rgba(255,196,140,0.13)"], [1, "rgba(0,0,0,0)"]]);

      // Luminous clouds (additive), then dark dust lanes (normal blending) for depth.
      ctx.globalCompositeOperation = "lighter";
      for (const d of clouds) {
        const p = project(d.r, d.a + time * (0.11 / (0.24 + d.r)) * ROT, d.y, yaw, cosT, sinT, focal);
        const size = d.size * scale * p.persp;
        ctx.globalAlpha = d.alpha * Math.min(1, p.persp);
        ctx.drawImage(d.warm ? warmGlow : whiteGlow, p.x * scale * p.persp - size / 2, p.y * scale * p.persp - size / 2, size, size);
      }
      ctx.globalCompositeOperation = "source-over";
      for (const d of lanes) {
        const p = project(d.r, d.a + time * (0.11 / (0.24 + d.r)) * ROT, d.y, yaw, cosT, sinT, focal);
        const size = d.size * scale * p.persp;
        ctx.globalAlpha = d.alpha * 0.8; // dust lane through the midplane of the edge-on disc
        ctx.drawImage(darkDust, p.x * scale * p.persp - size / 2, p.y * scale * p.persp - size * 0.3, size, size * 0.6);
      }
      ctx.globalAlpha = 1;

      // Click spreads: a single soft outward nudge per click, then stars spring back.
      const R = 110, S = 240;
      const clicks = spreads.splice(0, spreads.length).map((c) => toLocal(c.x, c.y));
      const m = mouse.inside ? toLocal(mouse.x, mouse.y) : null;
      ctx.globalCompositeOperation = "lighter";
      let bucket = -1;
      const halos: [number, number, number][] = [];
      for (let i = 0; i < stars.length; i++) {
        const s = stars[i];
        if (s.bucket !== bucket) {
          bucket = s.bucket;
          const [r, g, b, a] = BUCKETS[bucket];
          ctx.fillStyle = `rgb(${r},${g},${b})`;
          ctx.globalAlpha = a;
        }
        const ang = s.a + yaw + time * s.speed * ROT;
        const x = Math.cos(ang) * s.r, z0 = Math.sin(ang) * s.r;
        const y = s.y * cosT - z0 * sinT, z = s.y * sinT + z0 * cosT;
        const persp = focal / (focal + z);
        const bx = x * scale * persp, by = y * scale * persp;

        for (const c of clicks) {
          const dx = bx - c.x, dy = by - c.y;
          const d2 = dx * dx + dy * dy;
          if (d2 < S * S && d2 > 0.01) {
            const d = Math.sqrt(d2);
            const f = (1 - d / S) ** 2 * 11;
            velX[i] += (dx / d) * f;
            velY[i] += (dy / d) * f;
          }
        }
        if (m) {
          const dx = bx + offX[i] - m.x, dy = by + offY[i] - m.y;
          const d2 = dx * dx + dy * dy;
          if (d2 < R * R && d2 > 0.01) {
            const d = Math.sqrt(d2);
            const f = (1 - d / R) ** 2 * 0.5;
            velX[i] += (dx / d) * f;
            velY[i] += (dy / d) * f;
          }
        }
        // Damped spring back to the star's place in the galaxy.
        velX[i] = (velX[i] - offX[i] * 0.012) * 0.9;
        velY[i] = (velY[i] - offY[i] * 0.012) * 0.9;
        offX[i] += velX[i];
        offY[i] += velY[i];
        const px = bx + offX[i], py = by + offY[i];
        if (px < -reach || py < -reach || px > reach || py > reach) continue;
        const size = Math.min(2.2, s.size * persp * persp); // near stars larger, far ones finer: depth
        ctx.fillRect(px, py, size, size);
        if (s.halo) halos.push([px, py, size]);
      }
      ctx.globalAlpha = 0.8;
      for (const [hx, hy, hs] of halos) {
        const d = hs * 9;
        ctx.drawImage(starHalo, hx - d / 2 + hs / 2, hy - d / 2 + hs / 2, d, d);
      }
      ctx.globalAlpha = 1;
      ctx.globalCompositeOperation = "source-over";

      // Our solar system, out on an arm (r = 0.62), moving with the galaxy.
      {
        const r0 = 0.55;
        const sp = project(r0, sunArm + time * (0.11 / (0.24 + r0)) * ROT, 0, yaw, cosT, sinT, focal);
        const sx = sp.x * scale * sp.persp, sy = sp.y * scale * sp.persp;
        const k = Math.max(0.8, Math.min(1.6, sp.persp)) * (small ? 1 : 1.5);
        const inc = Math.max(0.28, Math.abs(sinT));
        ctx.globalCompositeOperation = "lighter";
        ctx.globalAlpha = 0.95;
        ctx.drawImage(warmGlow, sx - 30 * k, sy - 30 * k, 60 * k, 60 * k);
        ctx.globalCompositeOperation = "source-over";
        ctx.strokeStyle = "rgba(255,255,255,0.09)";
        ctx.lineWidth = 0.8;
        for (const pl of planets) {
          ctx.beginPath();
          ctx.ellipse(sx, sy, pl.r * k, pl.r * k * inc, 0, 0, Math.PI * 2);
          ctx.stroke();
        }
        const pos = (pl: (typeof planets)[number]) => {
          const ang = pl.a + time * pl.v * 0.9;
          return { ang, x: sx + Math.cos(ang) * pl.r * k, y: sy + Math.sin(ang) * pl.r * k * inc };
        };
        const drawPlanet = (pl: (typeof planets)[number]) => {
          const { ang, x, y } = pos(pl);
          const depth = 0.8 + 0.2 * Math.sin(ang);
          ctx.globalAlpha = 1;
          ctx.fillStyle = `rgb(${pl.c})`;
          ctx.beginPath();
          ctx.arc(x, y, pl.s * k * depth, 0, Math.PI * 2);
          ctx.fill();
          if (pl.earth) {
            ctx.strokeStyle = "rgba(140,200,255,0.55)"; // thin atmosphere
            ctx.lineWidth = 0.6;
            ctx.stroke();
            const ma = time * 5.5;
            ctx.fillStyle = "rgb(210,210,205)";
            ctx.beginPath();
            ctx.arc(x + Math.cos(ma) * 3.4 * k, y + Math.sin(ma) * 3.4 * k * inc, 0.55 * k, 0, Math.PI * 2);
            ctx.fill();

          }
          if (pl.r === 52) { // Saturn's ring
            ctx.strokeStyle = "rgba(230,210,160,0.6)";
            ctx.lineWidth = 0.7;
            ctx.beginPath();
            ctx.ellipse(x, y, pl.s * k * 2, pl.s * k * 0.7, -0.3, 0, Math.PI * 2);
            ctx.stroke();
          }
        };
        const behind = planets.filter((pl) => Math.sin(pos(pl).ang) < 0);
        const front = planets.filter((pl) => Math.sin(pos(pl).ang) >= 0);
        behind.forEach(drawPlanet);
        ctx.globalAlpha = 1;
        ctx.fillStyle = "rgb(255,232,180)";
        ctx.beginPath();
        ctx.arc(sx, sy, 3.2 * k, 0, Math.PI * 2);
        ctx.fill();
        front.forEach(drawPlanet);
        ctx.globalAlpha = 1;
      }
      ctx.restore();

      // Rare shooting star.
      if (!reduce) {
        if (now >= nextMeteor) { // a shooting star every 2-3 seconds, continuously
          nextMeteor = now + 2000 + Math.random() * 1000;
          meteors.push({ x: Math.random() * w, y: Math.random() * h * 0.45, vx: -(260 + Math.random() * 240), vy: 120 + Math.random() * 100, life: 1 });
        }
        for (const m of meteors) {
          m.x += m.vx * dt; m.y += m.vy * dt; m.life -= dt * 0.9;
          const tail = ctx.createLinearGradient(m.x, m.y, m.x - m.vx * 0.12, m.y - m.vy * 0.12);
          tail.addColorStop(0, `rgba(255,255,255,${Math.max(0, m.life) * 0.8})`);
          tail.addColorStop(1, "rgba(255,255,255,0)");
          ctx.strokeStyle = tail;
          ctx.lineWidth = 1.2;
          ctx.beginPath();
          ctx.moveTo(m.x, m.y);
          ctx.lineTo(m.x - m.vx * 0.12, m.y - m.vy * 0.12);
          ctx.stroke();
        }
        while (meteors.length && meteors[0].life <= 0) meteors.shift();

        // Slow comets falling across the sky: a glowing head with a long fading tail.
        if (Math.random() < dt * 0.09) {
          const fromLeft = Math.random() < 0.5;
          comets.push({ x: fromLeft ? Math.random() * w * 0.5 : w * 0.5 + Math.random() * w * 0.5, y: -20,
                        vx: (fromLeft ? 1 : -1) * (40 + Math.random() * 50), vy: 70 + Math.random() * 60, life: 1, size: 1.4 + Math.random() * 1.2 });
        }
        for (const c of comets) {
          c.x += c.vx * dt; c.y += c.vy * dt; c.life -= dt * 0.12;
          const tx = c.x - c.vx * 1.1, ty = c.y - c.vy * 1.1;
          const tail = ctx.createLinearGradient(c.x, c.y, tx, ty);
          tail.addColorStop(0, `rgba(255,244,225,${Math.max(0, c.life) * 0.55})`);
          tail.addColorStop(1, "rgba(255,244,225,0)");
          ctx.strokeStyle = tail;
          ctx.lineWidth = c.size * 1.6;
          ctx.lineCap = "round";
          ctx.beginPath();
          ctx.moveTo(c.x, c.y);
          ctx.lineTo(tx, ty);
          ctx.stroke();
          ctx.globalCompositeOperation = "lighter";
          ctx.globalAlpha = Math.max(0, c.life);
          ctx.drawImage(starHalo, c.x - c.size * 6, c.y - c.size * 6, c.size * 12, c.size * 12);
          ctx.globalAlpha = 1;
          ctx.globalCompositeOperation = "source-over";
        }
        for (let i = comets.length - 1; i >= 0; i--) if (comets[i].life <= 0 || comets[i].y > h + 60) comets.splice(i, 1);

        // Soft click ripple (no flash): one thin ring that fades out.
        for (const r of ripples) {
          r.t += dt;
          ctx.strokeStyle = `rgba(255,240,220,${Math.max(0, 0.35 - r.t * 0.5)})`;
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.arc(r.x, r.y, 10 + r.t * 120, 0, Math.PI * 2);
          ctx.stroke();
        }
        while (ripples.length && ripples[0].t > 0.8) ripples.shift();
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
