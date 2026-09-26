"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Notice } from "@/components/app-shell";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input } from "@/components/ui/form";
import { useAuth } from "@/hooks/use-auth";

function safeNext(next: string | null): string {
  // Only allow same-site relative paths (prevents open redirects).
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/";
}

export function AuthForm({ mode }: { mode: "login" | "register" }) {
  const { login, register, user, loading } = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(
    params.get("error") === "google" ? "Google sign-in failed or was cancelled." : null,
  );
  const [busy, setBusy] = useState(false);
  const next = safeNext(params.get("next"));

  useEffect(() => {
    if (!loading && user) router.replace(next);
  }, [loading, user, router, next]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mode === "login") await login(email, password);
      else await register(name, email, password);
      router.replace(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  const isLogin = mode === "login";
  return (
    <main className="grid min-h-screen place-items-center px-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex items-center justify-center gap-2 text-lg font-semibold">
          <span className="grid size-8 place-items-center rounded-md bg-primary text-sm font-bold text-primary-foreground">S</span>
          Saige AI
        </div>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{isLogin ? "Sign in" : "Create your account"}</CardTitle>
            <CardDescription>{isLogin ? "Welcome back to your career command center." : "Your verified profile powers everything Saige does."}</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={onSubmit} className="flex flex-col gap-4">
              {error && <Notice tone="error">{error}</Notice>}
              {!isLogin && (
                <Field label="Full name" htmlFor="name">
                  <Input id="name" autoComplete="name" required value={name} onChange={(e) => setName(e.target.value)} />
                </Field>
              )}
              <Field label="Email" htmlFor="email">
                <Input id="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
              </Field>
              <Field label="Password" htmlFor="password" hint={isLogin ? undefined : "8–72 characters"}>
                <Input
                  id="password"
                  type="password"
                  autoComplete={isLogin ? "current-password" : "new-password"}
                  required
                  minLength={isLogin ? 1 : 8}
                  maxLength={72}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </Field>
              <Button type="submit" disabled={busy}>
                {busy ? "Please wait…" : isLogin ? "Sign in" : "Create account"}
              </Button>
            </form>
            <div className="my-4 flex items-center gap-3 text-xs text-muted-foreground">
              <span className="h-px flex-1 bg-border" /> or <span className="h-px flex-1 bg-border" />
            </div>
            {/* Full-page navigation: the backend redirects to Google and back via the proxy. */}
            <a href="/api/auth/google/authorize" className={buttonVariants({ variant: "outline", className: "w-full" })}>
              Continue with Google
            </a>
            <p className="mt-5 text-center text-sm text-muted-foreground">
              {isLogin ? "New to Saige AI? " : "Already have an account? "}
              <Link href={isLogin ? "/register" : "/login"} className="font-medium text-primary hover:underline">
                {isLogin ? "Create an account" : "Sign in"}
              </Link>
            </p>
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
