import { UNKNOWN, display, emptyToNull, formatBytes, linesToList, numberOrNull } from "./format";

describe("format utils", () => {
  it("shows UNKNOWN for missing values instead of guessing", () => {
    expect(display(null)).toBe(UNKNOWN);
    expect(display("")).toBe(UNKNOWN);
    expect(display([])).toBe(UNKNOWN);
    expect(display(["Java", "Selenium"])).toBe("Java, Selenium");
    expect(display(0)).toBe("0");
  });

  it("parses numeric input safely", () => {
    expect(numberOrNull("")).toBeNull();
    expect(numberOrNull("  ")).toBeNull();
    expect(numberOrNull("4.5")).toBe(4.5);
    expect(numberOrNull("abc")).toBeNull();
  });

  it("normalises form values", () => {
    expect(emptyToNull({ a: "", b: "x" })).toEqual({ a: null, b: "x" });
    expect(linesToList(" one \n\n two ")).toEqual(["one", "two"]);
    expect(formatBytes(2048)).toBe("2.0 KB");
  });
});

describe("job formatting", () => {
  it("formats INR in lakhs and other currencies in thousands", async () => {
    const { formatSalary, scoreTone } = await import("./format");
    expect(formatSalary(1800000, 2800000, "INR")).toBe("₹18L–28L");
    expect(formatSalary(120000, 150000, "USD")).toBe("USD 120k–150k");
    expect(formatSalary(null, null, null)).toBe("—");
    expect(scoreTone(90)).toBe("success");
    expect(scoreTone(null)).toBe("muted");
  });
});
