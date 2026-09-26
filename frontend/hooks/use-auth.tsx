"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { refreshSession, request, setAccessToken, setSessionExpiredHandler } from "@/services/api";
import type { TokenResponse, User } from "@/types/api";

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (name: string, email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  reload: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const loadMe = useCallback(async () => {
    setUser(await request<User>("/auth/me"));
  }, []);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      if (await refreshSession()) await loadMe();
      else setUser(null);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, [loadMe]);

  useEffect(() => {
    setSessionExpiredHandler(() => {
      setAccessToken(null);
      setUser(null);
    });
    void reload();
    return () => setSessionExpiredHandler(null);
  }, [reload]);

  const login = useCallback(
    async (email: string, password: string) => {
      const t = await request<TokenResponse>("/auth/login", { method: "POST", body: { email, password } });
      setAccessToken(t.access_token);
      await loadMe();
    },
    [loadMe],
  );

  const register = useCallback(
    async (name: string, email: string, password: string) => {
      const t = await request<TokenResponse>("/auth/register", {
        method: "POST",
        body: { name, email, password },
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
      setUser(null);
    }
  }, []);

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
