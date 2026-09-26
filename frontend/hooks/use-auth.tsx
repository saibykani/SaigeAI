"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { clearApiCache } from "@/hooks/use-api";
import { refreshSession, request, setAccessToken, setSessionExpiredHandler } from "@/services/api";
import type { TokenResponse, User } from "@/types/api";

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (name: string, email: string, password: string, details?: SignupDetails) => Promise<void>;
  logout: () => Promise<void>;
  reload: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

// The last signed-in user (name/email only) lets the app shell render instantly on the next visit
// while the session refresh runs in the background. Never holds tokens.
const USER_KEY = "saige-user";
const readCachedUser = (): User | null => {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? (JSON.parse(raw) as User) : null;
  } catch {
    return null;
  }
};
const writeCachedUser = (u: User | null) => {
  try {
    if (u) localStorage.setItem(USER_KEY, JSON.stringify(u));
    else localStorage.removeItem(USER_KEY);
  } catch {
    /* storage unavailable: just no instant start */
  }
};

/** Optional career details asked at sign-up; they start the profile so Jobs for you works right away. */
export type SignupDetails = {
  phone?: string; current_designation?: string; total_experience_years?: number; target_role?: string;
  current_location?: string; country?: string; notice_period_days?: number; linkedin_url?: string;
};

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const setAndCache = useCallback((u: User | null) => {
    setUser(u);
    writeCachedUser(u);
    if (!u) clearApiCache();
  }, []);

  const loadMe = useCallback(async () => {
    setAndCache(await request<User>("/auth/me"));
  }, [setAndCache]);

  const reload = useCallback(async () => {
    const cached = readCachedUser();
    if (cached) {
      setUser(cached); // show the app now; the refresh below confirms or signs out
      setLoading(false);
    } else {
      setLoading(true);
    }
    try {
      if (await refreshSession()) await loadMe();
      else setAndCache(null);
    } catch {
      setAndCache(null);
    } finally {
      setLoading(false);
    }
  }, [loadMe, setAndCache]);

  useEffect(() => {
    setSessionExpiredHandler(() => {
      setAccessToken(null);
      setAndCache(null);
    });
    void reload();
    return () => setSessionExpiredHandler(null);
  }, [reload, setAndCache]);

  const login = useCallback(
    async (email: string, password: string) => {
      const t = await request<TokenResponse>("/auth/login", { method: "POST", body: { email, password } });
      setAccessToken(t.access_token);
      await loadMe();
    },
    [loadMe],
  );

  const register = useCallback(
    async (name: string, email: string, password: string, details?: SignupDetails) => {
      const t = await request<TokenResponse>("/auth/register", {
        method: "POST",
        body: { name, email, password, ...(details ?? {}) },
      });
      setAccessToken(t.access_token);
      await loadMe();
    },
    [loadMe],
  );

  const logout = useCallback(async () => {
    try {
      await request("/auth/logout", { method: "POST" });
    } finally {
      setAccessToken(null);
      setAndCache(null);
    }
  }, [setAndCache]);

  const value = useMemo(
    () => ({ user, loading, login, register, logout, reload }),
    [user, loading, login, register, logout, reload],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
