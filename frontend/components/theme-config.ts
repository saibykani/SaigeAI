// Theme constants live in a plain module so server components (the root layout) can use them.
export const THEMES = [
  { id: "graphite", name: "Graphite", note: "Pure black · silver", swatch: ["#000000", "#ffffff", "#a1a1aa", "#e4e4e7"] },
  { id: "obsidian", name: "Obsidian", note: "Warm black · gold", swatch: ["#070604", "#fde68a", "#f5b73b", "#d6a04a"] },
  { id: "aurora", name: "Aurora", note: "Polar night · emerald", swatch: ["#030b0a", "#34d399", "#22d3ee", "#a3e635"] },
  { id: "ember", name: "Ember", note: "Charcoal · orange", swatch: ["#0a0706", "#ff8a3d", "#ffb37a", "#e8651a"] },
  { id: "forest", name: "Forest", note: "Deep green · mint", swatch: ["#040806", "#4ade80", "#86efac", "#16a34a"] },
  { id: "daylight", name: "Daylight", note: "Clean white · ink", swatch: ["#f7f8fb", "#111113", "#52525b", "#a1a1aa"] },
  { id: "terminal", name: "Retro Terminal", note: "Amber on black · monospace · scanlines", swatch: ["#050400", "#ffb000", "#ffcf66", "#b37b00"] },
  { id: "paper", name: "Paper & Ink", note: "Cream paper · serif · editorial", swatch: ["#f6f0e4", "#1d1a16", "#8a3b12", "#c9b99a"] },
  { id: "neon", name: "Neon Grid", note: "Synthwave night · lime neon · grid", swatch: ["#07030f", "#c6ff3d", "#8b5cf6", "#2a1a4a"] },
  { id: "sunset", name: "Desert Sunset", note: "Warm sand · terracotta · soft", swatch: ["#fbeee2", "#c2410c", "#7c2d12", "#f4c8a8"] },
  { id: "crystal", name: "Crystal Glass", note: "Apple-style clear glass · light · floating panels", swatch: ["#e9edf2", "#ffffff", "#8e8e93", "#c7ccd4"] },
  { id: "glass", name: "Liquid Glass", note: "Frosted glass · violet aurora · floating", swatch: ["#0b0718", "#b794ff", "#6d28d9", "#1e1238"] },
] as const;

export type ThemeId = (typeof THEMES)[number]["id"];
export const DEFAULT_THEME: ThemeId = "graphite";
export const THEME_KEY = "saige-theme";

/** Inline script run before paint so the saved theme applies without a flash. */
export const themeBootScript = `(function(){try{var t=localStorage.getItem("${THEME_KEY}");var ok=${JSON.stringify(THEMES.map((t) => t.id))};document.documentElement.dataset.theme=ok.indexOf(t)>-1?t:"${DEFAULT_THEME}";}catch(e){document.documentElement.dataset.theme="${DEFAULT_THEME}";}})();`;

