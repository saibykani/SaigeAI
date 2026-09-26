"use client";

import { Check, Palette } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { cn } from "@/utils/cn";
import { DEFAULT_THEME, THEME_KEY, THEMES, type ThemeId } from "@/components/theme-config";

export { THEMES };

export function useTheme(): [ThemeId, (t: ThemeId) => void] {
  const [theme, setThemeState] = useState<ThemeId>(DEFAULT_THEME);
  useEffect(() => {
    const current = document.documentElement.dataset.theme as ThemeId | undefined;
    if (current) setThemeState(current);
  }, []);
  const setTheme = (t: ThemeId) => {
    document.documentElement.dataset.theme = t;
    try {
      localStorage.setItem(THEME_KEY, t);
    } catch {
      /* storage unavailable (private mode): theme still applies for this visit */
    }
    setThemeState(t);
  };
  return [theme, setTheme];
}

export function ThemeSwitcher({ align = "right" }: { align?: "left" | "right" }) {
  const [theme, setTheme] = useTheme();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const close = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("mousedown", close); document.removeEventListener("keydown", esc); };
  }, []);

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        aria-label="Change theme"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="grid size-10 cursor-pointer place-items-center rounded-full text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
      >
        <Palette className="size-[18px]" />
      </button>
      {open && (
        <div className={cn("glass animate-pop absolute top-12 z-50 w-72 rounded-2xl border p-2 shadow-[var(--shadow-lift)]", align === "right" ? "right-0" : "left-0")}>
          <p className="px-3 pb-1 pt-2 text-[11px] font-medium uppercase tracking-[0.08em] text-muted-foreground">Theme</p>
          {THEMES.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => { setTheme(t.id); setOpen(false); }}
              className={cn("flex w-full cursor-pointer items-center gap-3 rounded-xl px-3 py-2.5 text-left transition-colors hover:bg-muted", theme === t.id && "bg-muted")}
            >
              <span className="relative grid size-9 shrink-0 place-items-center overflow-hidden rounded-xl ring-1 ring-border" style={{ background: t.swatch[0] }}>
                <span className="absolute inset-1.5 rounded-lg" style={{ background: `linear-gradient(135deg, ${t.swatch[1]}, ${t.swatch[2]}, ${t.swatch[3]})` }} />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block text-sm font-medium">{t.name}</span>
                <span className="block truncate text-xs text-muted-foreground">{t.note}</span>
              </span>
              {theme === t.id && <Check className="size-4 text-primary" />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
