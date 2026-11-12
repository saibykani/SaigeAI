import { describe, expect, it } from "vitest";

import { pickVoice, rankVoices } from "./voice";

const voices = [
  { name: "Google हिन्दी", lang: "hi-IN" },
  { name: "Microsoft Swara Online (Natural) - Hindi", lang: "hi-IN" },
  { name: "Microsoft Madhur Online (Natural) - Hindi", lang: "hi-IN" },
  { name: "Microsoft Heera - English (India)", lang: "en-IN" },
  { name: "Microsoft Ravi Online - English (India)", lang: "en-IN" },
  { name: "Google US English", lang: "en-US" },
];

describe("voice ranking", () => {
  it("prefers natural, then online, then google", () => {
    expect(rankVoices(voices, "en").map((v) => v.name)[0]).toContain("Ravi Online");
    expect(rankVoices(voices, "hi")[0].name).toContain("Natural");
    expect(rankVoices(voices, "te")).toEqual([]);
  });
  it("gives personas different voices", () => {
    expect(pickVoice(voices, "hi", "f", 0)?.name).toContain("Swara");
    expect(pickVoice(voices, "hi", "m", 0)?.name).toContain("Madhur");
    expect(pickVoice(voices, "te", "f", 0)?.lang.startsWith("en")).toBe(true);
  });
});
