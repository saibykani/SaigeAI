"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

/** App language. Navigation, menus and header are translated; page content is in English for now. */
export const LANGUAGES = [
  { id: "en", name: "English", native: "English" },
  { id: "hi", name: "Hindi", native: "हिन्दी" },
  { id: "te", name: "Telugu", native: "తెలుగు" },
] as const;
export type Lang = (typeof LANGUAGES)[number]["id"];

const STRINGS: Record<string, Partial<Record<Lang, string>>> = {
  Dashboard: { hi: "डैशबोर्ड", te: "డాష్‌బోర్డ్" },
  "Master Profile": { hi: "प्रोफ़ाइल", te: "ప్రొఫైల్" },
  Profile: { hi: "प्रोफ़ाइल", te: "ప్రొఫైల్" },
  "LinkedIn & Naukri": { hi: "LinkedIn और Naukri", te: "LinkedIn & Naukri" },
  Resumes: { hi: "रिज़्यूमे", te: "రెజ్యూమేలు" },
  Jobs: { hi: "नौकरियाँ", te: "ఉద్యోగాలు" },
  Applications: { hi: "आवेदन", te: "దరఖాస్తులు" },
  Interviews: { hi: "इंटरव्यू", te: "ఇంటర్వ్యూలు" },
  Recruiters: { hi: "रिक्रूटर", te: "రిక్రూటర్లు" },
  Analytics: { hi: "विश्लेषण", te: "విశ్లేషణ" },
  Inbox: { hi: "इनबॉक्स", te: "ఇన్‌బాక్స్" },
  "Profile Sync": { hi: "प्रोफ़ाइल सिंक", te: "ప్రొఫైల్ సింక్" },
  Integrations: { hi: "इंटीग्रेशन", te: "ఇంటిగ్రేషన్లు" },
  "Automation & Privacy": { hi: "ऑटोमेशन और गोपनीयता", te: "ఆటోమేషన్ & గోప్యత" },
  "Help & Docs": { hi: "सहायता और गाइड", te: "సహాయం & గైడ్" },
  "Saige AI · your AI job search partner": { hi: "Saige AI · आपका AI जॉब सर्च साथी", te: "Saige AI · మీ AI ఉద్యోగ శోధన భాగస్వామి" },
  Notifications: { hi: "सूचनाएँ", te: "నోటిఫికేషన్లు" },
  "Mark all read": { hi: "सब पढ़ा हुआ", te: "అన్నీ చదివినట్లు" },
  "You're all caught up.": { hi: "सब कुछ देख लिया।", te: "అన్నీ చూశారు." },
  "WhatsApp alerts": { hi: "WhatsApp अलर्ट", te: "WhatsApp అలర్ట్‌లు" },
  "Browser extension": { hi: "ब्राउज़र एक्सटेंशन", te: "బ్రౌజర్ ఎక్స్‌టెన్షన్" },
  Language: { hi: "भाषा", te: "భాష" },
  "Send feedback": { hi: "सुझाव भेजें", te: "అభిప్రాయం పంపండి" },
  "Sign out": { hi: "साइन आउट", te: "సైన్ అవుట్" },
  "Your account": { hi: "आपका खाता", te: "మీ ఖాతా" },
  Settings: { hi: "सेटिंग्स", te: "సెట్టింగ్‌లు" },
  Overview: { hi: "सारांश", te: "అవలోకనం" },
  "Resume sync": { hi: "रिज़्यूमे सिंक", te: "రెజ్యూమే సింక్" },
  "Automation & privacy": { hi: "ऑटोमेशन और गोपनीयता", te: "ఆటోమేషన్ & గోప్యత" },
  "Hiring portals": { hi: "हायरिंग पोर्टल", te: "హైరింగ్ పోర్టల్‌లు" },
};

const KEY = "saige-lang";
type Ctx = { lang: Lang; setLang: (l: Lang) => void; t: (s: string) => string };
const LangContext = createContext<Ctx>({ lang: "en", setLang: () => {}, t: (s) => s });

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
  const t = useCallback((s: string) => (lang === "en" ? s : STRINGS[s]?.[lang] ?? s), [lang]);
  const value = useMemo(() => ({ lang, setLang, t }), [lang, setLang, t]);
  return <LangContext.Provider value={value}>{children}</LangContext.Provider>;
}

export const useT = () => useContext(LangContext);
