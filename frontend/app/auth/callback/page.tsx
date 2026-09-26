"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/hooks/use-auth";

/** Landing page after Google OAuth: the refresh cookie is set, so the AuthProvider's
 *  bootstrap refresh signs the user in; we then forward to the dashboard. */
export default function OAuthCallback() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    router.replace(user ? "/" : "/login?error=google");
  }, [loading, user, router]);

  return <div className="grid min-h-screen place-items-center text-sm text-muted-foreground">Signing you in…</div>;
}
