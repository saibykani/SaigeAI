"use client";

import type { RadarJob } from "@/types/api";

const SIZE = 420;
const C = SIZE / 2;
const MAX_R = 188;
const RINGS = [{ r: 47, label: "90+" }, { r: 94, label: "75+" }, { r: 141, label: "60+" }, { r: 188, label: "<60" }];

export function toneFor(score: number) {
  return score >= 80 ? "green" : score >= 65 ? "yellow" : score >= 50 ? "orange" : "red";
}

/** Jobs as dots: the higher the score, the closer to the centre. Angles are spread by rank so dots rarely overlap. */
export function RadarChart({ jobs, active, onSelect }: { jobs: RadarJob[]; active: string | null; onSelect: (id: string) => void }) {
  const dots = jobs.map((j, i) => {
    const r = Math.min(14 + ((100 - Math.min(100, Math.max(0, j.score))) / 100) * (MAX_R - 14) * 1.05, MAX_R - 6);
    const a = i * 2.399963 - Math.PI / 2; // golden angle
    return { j, x: C + r * Math.cos(a), y: C + r * Math.sin(a) };
  });
  return (
    <svg viewBox={`0 0 ${SIZE} ${SIZE}`} role="img" aria-label="Radar of your best-fit jobs, best matches in the centre" className="mx-auto w-full max-w-[460px]">
      {RINGS.map((g) => (
        <g key={g.r}>
          <circle cx={C} cy={C} r={g.r} fill="none" stroke="var(--border)" strokeWidth={1} strokeDasharray="3 5" />
          <text x={C + 4} y={C - g.r + 12} fontSize={10} fill="var(--muted-foreground)">{g.label}</text>
        </g>
      ))}
      <line x1={C} y1={C - MAX_R} x2={C} y2={C + MAX_R} stroke="var(--border)" strokeWidth={0.5} />
      <line x1={C - MAX_R} y1={C} x2={C + MAX_R} y2={C} stroke="var(--border)" strokeWidth={0.5} />
      <line x1={C} y1={C} x2={C} y2={C - MAX_R} stroke="var(--tone-green)" strokeWidth={1.5} strokeOpacity={0.35} strokeLinecap="round">
        <animateTransform attributeName="transform" type="rotate" from={`0 ${C} ${C}`} to={`360 ${C} ${C}`} dur="14s" repeatCount="indefinite" />
      </line>
      <circle cx={C} cy={C} r={4} fill="var(--tone-green)" />
      {dots.map(({ j, x, y }) => {
        const tone = toneFor(j.score);
        const on = active === j.id;
        return (
          <g key={j.id} onClick={() => onSelect(j.id)} className="cursor-pointer">
            <title>{`${j.title} · ${j.company} · ${j.score}%`}</title>
            <circle cx={x} cy={y} r={on ? 11 : 7} fill={`var(--tone-${tone})`} fillOpacity={on ? 0.35 : 0.2} />
            <circle cx={x} cy={y} r={on ? 6 : 4.5} fill={`var(--tone-${tone})`}>
              <animate attributeName="opacity" values="1;0.55;1" dur={`${3 + (j.score % 4)}s`} repeatCount="indefinite" />
            </circle>
          </g>
        );
      })}
    </svg>
  );
}
