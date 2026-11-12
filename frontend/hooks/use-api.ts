"use client";

import { useCallback, useEffect, useState } from "react";

import { request } from "@/services/api";

// Stale-while-revalidate: revisiting a page shows the last response instantly, then refreshes it.
// In-memory only, so it resets on reload or sign-out and never persists personal data to disk.
const cache = new Map<string, unknown>();
// Identical GETs issued at the same moment (several components, or a refresh burst) share one request.
const inflight = new Map<string, Promise<unknown>>();
// Last serialised response per path, so an unchanged refetch doesn't re-render the page.
const fingerprints = new Map<string, string>();

export function clearApiCache() {
  cache.clear();
  inflight.clear();
  fingerprints.clear();
}

function fetchShared<T>(path: string): Promise<T> {
  const pending = inflight.get(path) as Promise<T> | undefined;
  if (pending) return pending;
  const p = request<T>(path).finally(() => inflight.delete(path));
  inflight.set(path, p);
  return p;
}

function fingerprint(value: unknown): string | null {
  try { return JSON.stringify(value); } catch { return null; }
}

/** Fetch JSON on mount with loading / error state and a manual reload. */
export function useApi<T>(path: string | null) {
  const cached = path ? (cache.get(path) as T | undefined) : undefined;
  const [data, setDataState] = useState<T | null>(cached ?? null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(Boolean(path) && cached === undefined);

  const setData = useCallback((next: T | null | ((prev: T | null) => T | null)) => {
    setDataState((prev) => {
      const value = typeof next === "function" ? (next as (p: T | null) => T | null)(prev) : next;
      if (path) {
        fingerprints.delete(path);
        if (value === null) cache.delete(path);
        else cache.set(path, value);
      }
      return value;
    });
  }, [path]);

  const reload = useCallback(async () => {
    if (!path) return;
    if (!cache.has(path)) setLoading(true);
    setError(null);
    try {
      const fresh = await fetchShared<T>(path);
      const fp = fingerprint(fresh);
      const unchanged = fp !== null && fp === fingerprints.get(path) && cache.has(path);
      cache.set(path, fresh);
      if (fp !== null) fingerprints.set(path, fp);
      if (!unchanged) setDataState(fresh);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }, [path]);

  useEffect(() => {
    void reload();
  }, [reload]);

  // Live updates: the app shell fires "saige:refresh" when a background sync brought new data.
  useEffect(() => {
    // Skip while the tab is hidden; reload on return instead.
    const onRefresh = () => { if (document.visibilityState === "visible") void reload(); };
    window.addEventListener("saige:refresh", onRefresh);
    return () => window.removeEventListener("saige:refresh", onRefresh);
  }, [reload]);

  return { data, setData, error, loading, reload };
}

/** While Saige is open (and the tab visible), sync Gmail + portal alerts every minute and refresh the job feed every 5. */
export function useLiveSync(enabled: boolean) {
  useEffect(() => {
    if (!enabled) return;
    let stopped = false;
    const tick = async () => {
      if (stopped || document.visibilityState !== "visible") return;
      try {
        const r = await request<{ gmail: { fetched?: number } | null; feed: { jobs?: number } | null }>("/live/tick", { method: "POST" });
        if ((r.gmail?.fetched ?? 0) > 0 || (r.feed?.jobs ?? 0) > 0) window.dispatchEvent(new Event("saige:refresh"));
      } catch {
        /* offline or signed out: try again next tick */
      }
      try {
        const w = await request<{ new?: number }>("/careers/watch", { method: "POST" });
        if ((w.new ?? 0) > 0) window.dispatchEvent(new Event("saige:refresh"));
      } catch {
        /* watch off or paused */
      }
    };
    const first = window.setTimeout(tick, 8000);
    // Once a minute (was every 30 s): each tick may run an IMAP sync server-side.
    const every = window.setInterval(tick, 60_000);
    return () => { stopped = true; window.clearTimeout(first); window.clearInterval(every); };
  }, [enabled]);
}
