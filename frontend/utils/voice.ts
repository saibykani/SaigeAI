/** Voice helpers for the mock interview: pick the most natural speechSynthesis voice for a language. */

export const LANG_CODES: Record<string, string> = { en: "en-IN", hi: "hi-IN", te: "te-IN", ta: "ta-IN", kn: "kn-IN", ml: "ml-IN" };

export interface VoiceLike { name: string; lang: string; localService?: boolean }

/** Higher is better: natural/neural > online > google > other; exact locale beats same language. */
export function voiceRank(v: VoiceLike, lang: string): number {
  const want = (LANG_CODES[lang] ?? lang).toLowerCase();
  const vl = v.lang.toLowerCase().replace("_", "-");
  if (!vl.startsWith(want.slice(0, 2))) return -1;
  let s = vl === want ? 20 : 10;
  if (/natural|neural/i.test(v.name)) s += 300;
  else if (/online/i.test(v.name)) s += 200;
  else if (/google/i.test(v.name)) s += 100;
  return s;
}

/** Voices for a language, best first. Personas pick `ranked[i % n]` so each one sounds different when several exist. */
export function rankVoices<T extends VoiceLike>(voices: T[], lang: string): T[] {
  return voices.map((v) => ({ v, r: voiceRank(v, lang) })).filter((x) => x.r >= 0).sort((a, b) => b.r - a.r).map((x) => x.v);
}

/** Persona voice: prefer a voice whose name hints the persona's gender, among the top-ranked ones. */
export function pickVoice<T extends VoiceLike>(voices: T[], lang: string, gender: "f" | "m", slot: number): T | undefined {
  const ranked = rankVoices(voices, lang);
  if (!ranked.length) return lang === "en" ? undefined : pickVoice(voices, "en", gender, slot);
  const fem = /female|woman|heera|swara|neerja|kalpana|priya|shruti|pallavi|sapna|zira|aria|jenny|sonia|libby|samantha|veena|lekha|kavya|shobana/i;
  const mal = /male|man\b|ravi|prabhat|madhur|hemant|mohan|valluvar|gagan|guy|ryan|david|mark|rishi|aarav|kunal/i;
  const top = ranked[0] ? voiceRank(ranked[0], lang) : 0;
  const good = ranked.filter((v) => voiceRank(v, lang) >= top - 100);
  const byGender = good.filter((v) => (gender === "f" ? fem.test(v.name) && !/\bmale\b/i.test(v.name) : mal.test(v.name)));
  const pool = byGender.length ? byGender : good;
  return pool[slot % pool.length];
}
