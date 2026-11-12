"use client";

import { useEffect, useState } from "react";

export interface Persona {
  id: string;
  name: string;
  title: string;
  gender: "f" | "m";
  pitch: number;
  rate: number;
  skin: string;
  hair: string;
  shirt: string;
  hairStyle: "long" | "short" | "bun";
  glasses?: boolean;
  beard?: boolean;
}

export const PERSONAS: Persona[] = [
  { id: "priya", name: "Priya", title: "HR", gender: "f", pitch: 1.08, rate: 0.98, skin: "#c98e6a", hair: "#1d1410", shirt: "#0f9d8a", hairStyle: "long" },
  { id: "arjun", name: "Arjun", title: "Tech lead", gender: "m", pitch: 0.92, rate: 1.0, skin: "#b57b55", hair: "#151010", shirt: "#e8710a", hairStyle: "short", glasses: true, beard: true },
  { id: "meera", name: "Meera", title: "Manager", gender: "f", pitch: 0.98, rate: 0.95, skin: "#a86f4c", hair: "#2a1a12", shirt: "#8e44d6", hairStyle: "bun", glasses: true },
  { id: "kabir", name: "Kabir", title: "Senior engineer", gender: "m", pitch: 1.0, rate: 1.04, skin: "#d4a07c", hair: "#3a2a20", shirt: "#5f9e0f", hairStyle: "short" },
];

/** Animated SVG interviewer: blinks every few seconds, mouth moves while `speaking`, nods slightly while `listening`. */
export function InterviewerFace({ persona, speaking, listening, size = 220 }: { persona: Persona; speaking: boolean; listening: boolean; size?: number }) {
  const [blink, setBlink] = useState(false);
  const [mouth, setMouth] = useState(0);
  useEffect(() => {
    let t: ReturnType<typeof setTimeout>;
    const loop = () => {
      t = setTimeout(() => { setBlink(true); setTimeout(() => setBlink(false), 140); loop(); }, 2400 + Math.random() * 2600);
    };
    loop();
    return () => clearTimeout(t);
  }, []);
  useEffect(() => {
    if (!speaking) { setMouth(0); return; }
    const id = setInterval(() => setMouth(0.2 + Math.random() * 0.8), 110);
    return () => clearInterval(id);
  }, [speaking]);
  const p = persona;
  const eyeRy = blink ? 0.6 : 5;
  return (
    <svg viewBox="0 0 200 220" width={size} height={size * 1.1} role="img" aria-label={`${p.name}, ${p.title}`}
      className={listening ? "mi-nod" : speaking ? "mi-breathe" : ""}>
      {/* shoulders */}
      <path d="M30 220 C34 176 66 160 100 160 C134 160 166 176 170 220 Z" fill={p.shirt} />
      <path d="M86 160 L100 178 L114 160 Z" fill="#fff" opacity="0.85" />
      <rect x="90" y="140" width="20" height="24" rx="8" fill={p.skin} />
      {/* hair back */}
      {p.hairStyle === "long" && <path d="M48 90 C44 40 156 40 152 90 L158 160 C140 150 60 150 42 160 Z" fill={p.hair} />}
      {p.hairStyle === "bun" && <circle cx="100" cy="34" r="18" fill={p.hair} />}
      {/* face */}
      <ellipse cx="100" cy="96" rx="48" ry="56" fill={p.skin} />
      <ellipse cx="52" cy="100" rx="7" ry="11" fill={p.skin} />
      <ellipse cx="148" cy="100" rx="7" ry="11" fill={p.skin} />
      {/* hair front */}
      {p.hairStyle === "short" && <path d="M52 86 C50 44 150 40 148 86 C138 62 70 60 52 86 Z" fill={p.hair} />}
      {(p.hairStyle === "long" || p.hairStyle === "bun") && <path d="M52 92 C52 46 148 46 148 92 C128 64 96 58 52 92 Z" fill={p.hair} />}
      {p.beard && <path d="M58 112 C62 156 138 156 142 112 C134 140 66 140 58 112 Z" fill={p.hair} opacity="0.85" />}
      {/* brows */}
      <path d="M70 80 Q80 75 90 80" stroke={p.hair} strokeWidth="3" fill="none" strokeLinecap="round" />
      <path d="M110 80 Q120 75 130 80" stroke={p.hair} strokeWidth="3" fill="none" strokeLinecap="round" />
      {/* eyes */}
      <ellipse cx="80" cy="94" rx="5" ry={eyeRy} fill="#1a1a1a" style={{ transition: "ry 80ms" }} />
      <ellipse cx="120" cy="94" rx="5" ry={eyeRy} fill="#1a1a1a" style={{ transition: "ry 80ms" }} />
      {p.glasses && (
        <g stroke="#222" strokeWidth="2.2" fill="none">
          <rect x="66" y="84" width="28" height="20" rx="8" />
          <rect x="106" y="84" width="28" height="20" rx="8" />
          <path d="M94 93 L106 93" />
        </g>
      )}
      {/* nose */}
      <path d="M100 100 Q96 114 102 116" stroke="#00000033" strokeWidth="2.2" fill="none" strokeLinecap="round" />
      {/* mouth */}
      <ellipse cx="100" cy="130" rx={10 + mouth * 2} ry={1.8 + mouth * 7} fill="#5a1f1f" style={{ transition: "ry 90ms, rx 90ms" }} />
      {!speaking && <path d="M88 128 Q100 136 112 128" stroke="#5a1f1f" strokeWidth="2.5" fill="none" strokeLinecap="round" />}
    </svg>
  );
}
