"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { LANG_CODES, rankVoices } from "@/utils/voice";

/* Minimal Web Speech typings (not in lib.dom for all targets). */
interface SRResult { 0: { transcript: string }; isFinal: boolean; length: number }
interface SREvent { resultIndex: number; results: ArrayLike<SRResult> }
interface SR {
  lang: string; continuous: boolean; interimResults: boolean;
  onresult: ((e: SREvent) => void) | null; onend: (() => void) | null; onerror: ((e: { error: string }) => void) | null;
  start(): void; stop(): void; abort(): void;
}
type SRCtor = new () => SR;

const WAKE = /\b(hey|hi|ok|okay)[,.\s]+(saige|sage|sagar|say j)\b[,.\s]*/i;
const WAKE_KEY = "saige-wake";

export type VoiceState = "idle" | "listening" | "thinking" | "speaking" | "wake";

function ctor(): SRCtor | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as { SpeechRecognition?: SRCtor; webkitSpeechRecognition?: SRCtor };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export function speak(text: string, lang: string, onEnd?: () => void) {
  if (typeof window === "undefined" || !("speechSynthesis" in window) || !text) return onEnd?.();
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  const code = LANG_CODES[lang] ?? "en-IN";
  const v = rankVoices(window.speechSynthesis.getVoices(), lang)[0];
  u.lang = v?.lang ?? code;
  if (v) u.voice = v as SpeechSynthesisVoice;
  u.onend = () => onEnd?.();
  u.onerror = () => onEnd?.();
  window.speechSynthesis.speak(u);
}

/** Push-to-talk (and optional "Hey Saige" wake word) voice loop. `ask` sends text to the assistant and resolves to the spoken reply. */
export function useVoiceAssistant(lang: string, ask: (q: string) => Promise<string | null>) {
  const [state, setState] = useState<VoiceState>("idle");
  const [transcript, setTranscript] = useState("");
  const [wake, setWakeState] = useState(false);
  const [error, setError] = useState("");
  const rec = useRef<SR | null>(null);
  const wakeRef = useRef(false);
  const askRef = useRef(ask);
  askRef.current = ask;
  const supported = ctor() !== null;
  const canSpeak = typeof window !== "undefined" && "speechSynthesis" in window;

  const stopRec = useCallback(() => { const r = rec.current; rec.current = null; if (r) { r.onend = null; try { r.abort(); } catch { /* ignore */ } } }, []);

  const handle = useCallback(async (q: string) => {
    setState("thinking");
    const reply = await askRef.current(q);
    if (!reply) { setState(wakeRef.current ? "wake" : "idle"); return; }
    setState("speaking");
    speak(reply, lang, () => setState(wakeRef.current ? "wake" : "idle"));
  }, [lang]);

  const listen = useCallback((mode: "ptt" | "wake") => {
    const C = ctor();
    if (!C) return;
    stopRec();
    window.speechSynthesis?.cancel();
    setError("");
    const r = new C();
    r.lang = LANG_CODES[lang] ?? "en-IN";
    r.interimResults = true;
    r.continuous = mode === "wake";
    let finalText = "";
    let captured = false;
    r.onresult = (e) => {
      let interim = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const res = e.results[i];
        if (res.isFinal) finalText += res[0].transcript + " "; else interim += res[0].transcript;
      }
      const heard = (finalText + interim).trim();
      if (mode === "wake") {
        const m = WAKE.exec(heard);
        if (!m) { if (finalText) finalText = ""; return; }
        const rest = heard.slice(m.index + m[0].length).trim();
        setTranscript(rest);
        setState("listening");
        if (finalText && rest && !captured) { captured = true; stopRec(); void handle(rest).then(() => { if (wakeRef.current && !document.hidden) listen("wake"); }); }
      } else {
        setTranscript(heard);
      }
    };
    r.onerror = (e) => {
      if (e.error === "not-allowed" || e.error === "service-not-allowed") { setError("Microphone permission was denied."); wakeRef.current = false; setWakeState(false); }
      else if (e.error === "no-speech" || e.error === "aborted") return;
      else setError("Voice recognition error: " + e.error);
    };
    r.onend = () => {
      if (rec.current !== r) return;
      rec.current = null;
      if (mode === "wake") { if (wakeRef.current && !document.hidden) listen("wake"); return; }
      const q = finalText.trim() || "";
      if (q) void handle(q); else setState(wakeRef.current ? "wake" : "idle");
    };
    rec.current = r;
    setTranscript("");
    setState(mode === "wake" ? "wake" : "listening");
    try { r.start(); } catch { setState("idle"); }
  }, [lang, handle, stopRec]);

  const toggle = useCallback(() => {
    if (state === "listening" && rec.current) { rec.current.stop(); return; }
    if (state === "speaking") { window.speechSynthesis?.cancel(); setState(wakeRef.current ? "wake" : "idle"); return; }
    listen("ptt");
  }, [state, listen]);

  const setWake = useCallback((on: boolean) => {
    wakeRef.current = on;
    setWakeState(on);
    try { localStorage.setItem(WAKE_KEY, "0"); } catch { /* ignore */ } // never persisted: always off by default
    if (on) listen("wake"); else { stopRec(); setState("idle"); }
  }, [listen, stopRec]);

  useEffect(() => {
    const onVis = () => { if (document.hidden) { stopRec(); window.speechSynthesis?.cancel(); setState("idle"); if (wakeRef.current) { wakeRef.current = false; setWakeState(false); } } };
    document.addEventListener("visibilitychange", onVis);
    return () => { document.removeEventListener("visibilitychange", onVis); stopRec(); window.speechSynthesis?.cancel(); };
  }, [stopRec]);

  return { state, transcript, wake, setWake, toggle, supported, canSpeak, error };
}
