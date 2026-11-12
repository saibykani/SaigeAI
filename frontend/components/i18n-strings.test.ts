import { describe, expect, it } from "vitest";

import { translate } from "@/components/i18n";
import { STRINGS } from "@/components/i18n-strings";

const placeholders = (s: string) => (s.match(/\{\w+\}/g) ?? []).sort().join(",");

describe("i18n strings", () => {
  it("has a non-empty translation for all five Indian languages", () => {
    for (const [key, tr] of Object.entries(STRINGS)) {
      expect(tr, key).toHaveLength(5);
      tr.forEach((x) => expect(x.trim(), key).not.toBe(""));
    }
  });

  it("keeps every {placeholder} in every translation", () => {
    for (const [key, tr] of Object.entries(STRINGS)) tr.forEach((x) => expect(placeholders(x), key).toBe(placeholders(key)));
  });

  it("falls back to English and fills placeholders", () => {
    expect(translate("ta", "No such key {n}", { n: 3 })).toBe("No such key 3");
    expect(translate("hi", "Dashboard")).toBe("डैशबोर्ड");
    expect(translate("ml", "{n} parts to finish", { n: 2 })).toBe("2 ഭാഗങ്ങൾ ബാക്കി");
    expect(translate("en", "Finish setting up · {n}% done", { n: 40 })).toBe("Finish setting up · 40% done");
  });
});
