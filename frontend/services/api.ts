import type { TokenResponse } from "@/types/api";

/**
 * API client. The access token lives only in memory; the refresh token is an HttpOnly cookie
 * the browser sends to /api/auth/*. Requests go to the same origin and Next.js proxies them.
 */

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public detail?: unknown,
  ) {
    super(message);
  }
}

let accessToken: string | null = null;
let refreshInFlight: Promise<boolean> | null = null;
let onSessionExpired: (() => void) | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function setSessionExpiredHandler(fn: (() => void) | null) {
  onSessionExpired = fn;
}

const BASE_HEADERS = { "X-Requested-With": "saige" };

export async function refreshSession(): Promise<boolean> {
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      try {
        const res = await fetch("/api/auth/refresh", {
          method: "POST",
          headers: BASE_HEADERS,
          credentials: "same-origin",
        });
        if (!res.ok) {
          accessToken = null;
          return false;
        }
        const body = (await res.json()) as TokenResponse;
        accessToken = body.access_token;
        return true;
      } catch {
        return false;
      } finally {
        setTimeout(() => (refreshInFlight = null), 0);
      }
    })();
  }
  return refreshInFlight;
}

function errorMessage(detail: unknown, status: number): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length) {
    return detail
      .map((d: { loc?: unknown[]; msg?: string }) => {
        const field = Array.isArray(d.loc) ? d.loc.slice(1).join(".") : "";
        return field ? `${field}: ${d.msg}` : d.msg;
      })
      .join("; ");
  }
  return `Request failed (${status})`;
}

export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  form?: FormData;
  query?: Record<string, string | number | boolean | undefined>;
  raw?: boolean;
}

export async function request<T = unknown>(path: string, opts: RequestOptions = {}, retried = false): Promise<T> {
  const qs = opts.query
    ? "?" +
      new URLSearchParams(
        Object.entries(opts.query)
          .filter(([, v]) => v !== undefined)
          .map(([k, v]) => [k, String(v)]),
      ).toString()
    : "";
  const headers: Record<string, string> = { ...BASE_HEADERS };
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  let body: BodyInit | undefined;
  if (opts.form) body = opts.form;
  else if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.body);
  }

  const res = await fetch(`/api${path}${qs}`, {
    method: opts.method ?? "GET",
    headers,
    body,
    credentials: "same-origin",
  });

  if (res.status === 401 && !retried && !path.startsWith("/auth/")) {
    if (await refreshSession()) return request<T>(path, opts, true);
    onSessionExpired?.();
  }
  if (!res.ok) {
    let detail: unknown;
    try {
      detail = (await res.json()).detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, errorMessage(detail, res.status), detail);
  }
  if (opts.raw) return res as unknown as T;
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/** Download an authenticated binary response as a file. */
export async function downloadFile(path: string, fallbackName: string) {
  const res = await request<Response>(path, { raw: true });
  const blob = await res.blob();
  const cd = res.headers.get("Content-Disposition") ?? "";
  const match = /filename\*=UTF-8''([^;]+)|filename=([^;]+)/i.exec(cd);
  const name = match ? decodeURIComponent((match[1] ?? match[2]).trim()) : fallbackName;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}
