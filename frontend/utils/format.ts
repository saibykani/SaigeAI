export const UNKNOWN = "UNKNOWN";

export function display(value: unknown): string {
  if (value === null || value === undefined || value === "") return UNKNOWN;
  if (Array.isArray(value)) return value.length ? value.join(", ") : UNKNOWN;
  return String(value);
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

export function formatBytes(n: number | null | undefined): string {
  if (!n) return "—";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

/** Empty strings from form inputs become null so the backend stores UNKNOWN, not "". */
export function emptyToNull<T extends Record<string, unknown>>(obj: T): T {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(obj)) out[k] = v === "" ? null : v;
  return out as T;
}

export function numberOrNull(v: string): number | null {
  if (v.trim() === "") return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

export function linesToList(text: string): string[] {
  return text
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);
}

export function formatSalary(min: number | null, max: number | null, currency: string | null): string {
  if (!min && !max) return "—";
  const cur = currency ?? "";
  const fmt = (n: number) =>
    cur === "INR" ? `${(n / 100000).toFixed(n % 100000 ? 1 : 0)}L` : n >= 1000 ? `${Math.round(n / 1000)}k` : String(n);
  const range = min && max ? `${fmt(min)}–${fmt(max)}` : fmt((min ?? max)!);
  return cur === "INR" ? `₹${range}` : `${cur} ${range}`.trim();
}

export function scoreTone(score: number | null | undefined): "success" | "default" | "warning" | "muted" {
  if (score == null) return "muted";
  if (score >= 85) return "success";
  if (score >= 70) return "default";
  if (score >= 55) return "warning";
  return "muted";
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString(undefined, { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
}

export function humanStatus(s: string): string {
  return s.toLowerCase().replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}

/** "today", "yesterday", "3 days ago", "2 weeks ago" for a posting date (ISO date or datetime). */
export function timeAgo(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return null;
  const days = Math.floor((Date.now() - t) / 86_400_000);
  if (days <= 0) return "today";
  if (days === 1) return "yesterday";
  if (days < 7) return `${days} days ago`;
  if (days < 30) return `${Math.floor(days / 7)} week${days < 14 ? "" : "s"} ago`;
  if (days < 365) return `${Math.floor(days / 30)} month${days < 60 ? "" : "s"} ago`;
  return formatDate(iso);
}
