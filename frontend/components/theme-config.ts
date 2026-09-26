// Theme constants live in a plain module so server components (the root layout) can use them.
export const THEMES = [
  { id: "graphite", name: "Graphite", note: "Pure black · silver", swatch: ["#000000", "#ffffff", "#a1a1aa", "#e4e4e7"] },
  { id: "obsidian", name: "Obsidian", note: "Warm black · gold", swatch: ["#070604", "#fde68a", "#f5b73b", "#d6a04a"] },
  { id: "aurora", name: "Aurora", note: "Polar night · emerald", swatch: ["#030b0a", "#34d399", "#22d3ee", "#a3e635"] },
  { id: "daylight", name: "Daylight", note: "Clean white · ink", swatch: ["#f7f8fb", "#111113", "#52525b", "#a1a1aa"] },
] as const;

export type ThemeId = (typeof THEMES)[number]["id"];
export const DEFAULT_THEME: ThemeId = "graphite";
export const THEME_KEY = "saige-theme";

/** Inline script run before paint so the saved theme applies without a flash. */
export const themeBootScript = `(function(){try{var t=localStorage.getItem("${THEME_KEY}");var ok=${JSON.stringify(THEMES.map((t) => t.id))};document.documentElement.dataset.theme=ok.indexOf(t)>-1?t:"${DEFAULT_THEME}";}catch(e){document.documentElement.dataset.theme="${DEFAULT_THEME}";}})();`;

