"use client";

import { useCallback, useEffect, useState } from "react";

import { request } from "@/services/api";

// Stale-while-revalidate: revisiting a page shows the last response instantly, then refreshes it.
// In-memory only, so it resets on reload or sign-out and never persists personal data to disk.
const cache = new Map<string, unknown>();

export function clearApiCache() {
  cache.clear();
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
      const fresh = await request<T>(path);
      cache.set(path, fresh);
      setDataState(fresh);
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
    const onRefresh = () => void reload();
    window.addEventListener("saige:refresh", onRefresh);
    return () => window.removeEventListener("saige:refresh", onRefresh);
  }, [reload]);

  return { data, setData, error, loading, reload };
}

/** While Saige is open (and the tab visible), sync Gmail + portal alerts every 3 minutes and refresh the job feed. */
export function useLiveSync(enabled: boolean) {
  useEffect(() => {
    if (!enabled) return;
    let stopped = false;
    const tick = async () => {
      if (stopped || document.visibilityState !== "visible") return;
      try {
        const r = await request<{ gmail: { fetched?: number } | null; feed: { jobs?: number } | null }>("/live/tick", { method: "POST" });
        if ((r.gmail?.fetched ?? 0) > 0 || r.feed?.jobs !== undefined) window.dispatchEvent(new Event("saige:refresh"));
      } catch {
        /* offline or signed out: try again next tick */
      }
    };
    const first = window.setTimeout(tick, 8000);
    const every = window.setInterval(tick, 180_000);
    return () => { stopped = true; window.clearTimeout(first); window.clearInterval(every); };
  }, [enabled]);
}
