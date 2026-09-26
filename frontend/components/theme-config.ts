// Theme constants live in a plain module so server components (the root layout) can use them.
export const THEMES = [
  { id: "midnight", name: "Midnight", note: "Deep space · cyan & violet", swatch: ["#04060d", "#22d3ee", "#6d7cff", "#a855f7"] },
  { id: "nebula", name: "Nebula", note: "Cosmic violet · solar glow", swatch: ["#0a0612", "#fb923c", "#c084fc", "#38bdf8"] },
  { id: "aurora", name: "Aurora", note: "Polar night · emerald & teal", swatch: ["#030b0a", "#34d399", "#22d3ee", "#a3e635"] },
  { id: "daylight", name: "Daylight", note: "Clean & bright", swatch: ["#f7f8fb", "#1a73e8", "#7c3aed", "#0ea5e9"] },
] as const;

export type ThemeId = (typeof THEMES)[number]["id"];
export const DEFAULT_THEME: ThemeId = "midnight";
export const THEME_KEY = "saige-theme";

/** Inline script run before paint so the saved theme applies without a flash. */
export const themeBootScript = `(function(){try{var t=localStorage.getItem("${THEME_KEY}");var ok=${JSON.stringify(THEMES.map((t) => t.id))};document.documentElement.dataset.theme=ok.indexOf(t)>-1?t:"${DEFAULT_THEME}";}catch(e){document.documentElement.dataset.theme="${DEFAULT_THEME}";}})();`;

