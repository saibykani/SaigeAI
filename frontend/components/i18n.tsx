"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { STRINGS } from "@/components/i18n-strings";

/** App language. The shell and the most-used pages are translated; any string without a translation shows in English. */
export const LANGUAGES = [
  { id: "en", name: "English", native: "English" },
  { id: "hi", name: "Hindi", native: "हिन्दी" },
  { id: "te", name: "Telugu", native: "తెలుగు" },
  { id: "ta", name: "Tamil", native: "தமிழ்" },
  { id: "kn", name: "Kannada", native: "ಕನ್ನಡ" },
  { id: "ml", name: "Malayalam", native: "മലയാളം" },
] as const;
export type Lang = (typeof LANGUAGES)[number]["id"];
type Vars = Record<string, string | number>;

const INDEX: Record<Exclude<Lang, "en">, number> = { hi: 0, te: 1, ta: 2, kn: 3, ml: 4 };

/** Translates an English source string; {name} placeholders are filled from vars. Missing keys fall back to English. */
export function translate(lang: Lang, s: string, vars?: Vars): string {
  const out = lang === "en" ? s : STRINGS[s]?.[INDEX[lang]] || s;
  return vars ? out.replace(/\{(\w+)\}/g, (m, k: string) => (k in vars ? String(vars[k]) : m)) : out;
}

const KEY = "saige-lang";
type Ctx = { lang: Lang; setLang: (l: Lang) => void; t: (s: string, vars?: Vars) => string };
const LangContext = createContext<Ctx>({ lang: "en", setLang: () => {}, t: (s, vars) => translate("en", s, vars) });

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLangState] = useState<Lang>("en");
  useEffect(() => {
    try {
      const saved = localStorage.getItem(KEY) as Lang | null;
      if (saved && LANGUAGES.some((l) => l.id === saved)) setLangState(saved);
    } catch {
      /* storage unavailable: default English */
    }
  }, []);
  useEffect(() => { document.documentElement.lang = lang; }, [lang]);
  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    try { localStorage.setItem(KEY, l); } catch { /* ignore */ }
  }, []);
  const t = useCallback((s: string, vars?: Vars) => translate(lang, s, vars), [lang]);
  const value = useMemo(() => ({ lang, setLang, t }), [lang, setLang, t]);
  return <LangContext.Provider value={value}>{children}</LangContext.Provider>;
}

export const useT = () => useContext(LangContext);
