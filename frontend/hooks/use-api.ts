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

  return { data, setData, error, loading, reload };
}
