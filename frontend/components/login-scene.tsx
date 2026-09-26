"use client";

import { CalendarCheck, FileCheck2, Sparkles, Target } from "lucide-react";
import { useEffect, useRef } from "react";

/**
 * 3D brand scene for the sign-in page: glass cards floating at different depths inside a
 * perspective stage that tilts toward the pointer, with an orbiting ring and glow orbs.
 * Pure CSS 3D transforms (no WebGL). Motion is disabled under prefers-reduced-motion.
 */
export function LoginScene() {
  const stage = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = stage.current;
    if (!el || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let frame = 0;
    const target = { x: 0, y: 0 };
    const current = { x: 0, y: 0 };
    const onMove = (e: PointerEvent) => {
      target.x = (e.clientX / window.innerWidth - 0.5) * 2;
      target.y = (e.clientY / window.innerHeight - 0.5) * 2;
    };
    const tick = () => {
      current.x += (target.x - current.x) * 0.06;
      current.y += (target.y - current.y) * 0.06;
      el.style.transform = `rotateX(${12 - current.y * 10}deg) rotateY(${-14 + current.x * 14}deg)`;
      frame = requestAnimationFrame(tick);
    };
    window.addEventListener("pointermove", onMove);
    frame = requestAnimationFrame(tick);
    return () => {
      window.removeEventListener("pointermove", onMove);
      cancelAnimationFrame(frame);
    };
  }, []);

  return (
    <div className="scene relative h-[420px] w-full max-w-[520px]" aria-hidden>
      <div ref={stage} className="scene-stage absolute inset-0" style={{ transform: "rotateX(12deg) rotateY(-14deg)" }}>
        {/* orbit ring lying in 3D space */}
        <div className="absolute left-1/2 top-1/2 size-[380px]" style={{ transform: "translate(-50%,-50%) translateZ(-60px) rotateX(72deg)" }}>
          <div className="orbit absolute inset-0 rounded-full border border-white/25">
            <span className="absolute -top-1.5 left-1/2 size-3 -translate-x-1/2 rounded-full bg-white shadow-[0_0_18px_6px_rgba(255,255,255,0.6)]" />
            <span className="absolute -bottom-1 left-1/4 size-2 rounded-full bg-amber-200 shadow-[0_0_14px_4px_rgba(253,230,138,0.6)]" />
          </div>
        </div>

        {/* main card: job match */}
        <div className="float-a glass-card absolute left-[8%] top-[18%] w-[300px] p-5" style={{ transform: "translateZ(90px)" }}>
          <div className="flex items-center gap-3">
            <span className="grid size-10 place-items-center rounded-xl bg-white/25">
              <Target className="size-5" />
            </span>
            <div>
              <p className="text-sm font-semibold">Senior SDET · PayCo</p>
              <p className="text-xs text-white/75">Bengaluru · Hybrid</p>
            </div>
            <span className="ml-auto rounded-full bg-emerald-300/90 px-2.5 py-1 text-xs font-bold text-emerald-950">94%</span>
          </div>
          <div className="mt-4 space-y-2">
            {[["Skills", 96], ["Experience", 100], ["Location", 90]].map(([label, v], i) => (
              <div key={label} className="flex items-center gap-2 text-[11px]">
                <span className="w-16 text-white/75">{label}</span>
                <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/20">
                  <span className="bar block h-full rounded-full bg-white" style={{ width: `${v}%`, animationDelay: `${600 + i * 180}ms` }} />
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* resume card */}
        <div className="float-b glass-card absolute right-[2%] top-[4%] w-[210px] p-4" style={{ transform: "translateZ(30px)" }}>
          <div className="flex items-center gap-2 text-sm font-semibold">
            <FileCheck2 className="size-4" /> Resume tailored
          </div>
          <p className="mt-1 text-[11px] text-white/75">12 keywords aligned · 0 fabricated</p>
          <div className="mt-3 flex flex-wrap gap-1">
            {["Java", "Selenium", "Rest Assured", "JMeter"].map((t) => (
              <span key={t} className="rounded-full bg-white/20 px-2 py-0.5 text-[10px]">{t}</span>
            ))}
          </div>
        </div>

        {/* interview card */}
        <div className="float-c glass-card absolute bottom-[6%] right-[10%] w-[230px] p-4" style={{ transform: "translateZ(140px)" }}>
          <div className="flex items-center gap-3">
            <span className="grid size-9 place-items-center rounded-xl bg-amber-200/90 text-amber-900">
              <CalendarCheck className="size-4" />
            </span>
            <div>
              <p className="text-sm font-semibold">Interview scheduled</p>
              <p className="text-[11px] text-white/75">Tomorrow · 11:00 AM IST</p>
            </div>
          </div>
        </div>

        {/* sparkle chip */}
        <div className="float-b glass-card absolute bottom-[26%] left-[2%] flex items-center gap-2 px-3 py-2 text-xs font-medium" style={{ transform: "translateZ(180px)", animationDelay: "-3s" }}>
          <Sparkles className="size-3.5" /> 127 jobs scanned today
        </div>
      </div>
    </div>
  );
}
