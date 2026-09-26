"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Logo, Notice } from "@/components/app-shell";
import { LoginScene } from "@/components/login-scene";
import { Button, buttonVariants } from "@/components/ui/button";
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
    <main className="grid min-h-screen lg:grid-cols-[1.1fr_1fr]">
      {/* Brand panel: animated aurora + 3D scene */}
      <section className="relative hidden overflow-hidden bg-[#1b1463] p-12 text-white lg:flex lg:flex-col lg:justify-between">
        <div aria-hidden className="absolute inset-0">
          <div className="aurora absolute -left-1/4 -top-1/4 size-[70%] rounded-full bg-[#4285f4] opacity-60 blur-[90px]" />
          <div className="aurora absolute -right-1/4 top-1/4 size-[65%] rounded-full bg-[#9b72cb] opacity-60 blur-[90px]" style={{ animationDelay: "-7s" }} />
          <div className="aurora absolute -bottom-1/3 left-1/4 size-[60%] rounded-full bg-[#d96570] opacity-50 blur-[90px]" style={{ animationDelay: "-14s" }} />
          <div className="absolute inset-0 bg-[radial-gradient(rgba(255,255,255,0.12)_1px,transparent_1px)] [background-size:22px_22px] [mask-image:radial-gradient(ellipse_at_center,black_40%,transparent_75%)]" />
        </div>
        <Logo onDark className="relative text-white" />
        <div className="relative flex flex-1 items-center justify-center py-6">
          <LoginScene />
        </div>
        <div className="relative max-w-lg">
          <h2 className="text-[40px] font-semibold leading-[1.08] tracking-tight [perspective:600px]">
            {"Your job search, on autopilot. Honestly.".split(" ").map((w, i) => (
              <span key={i} className="word-in mr-[0.25em]" style={{ animationDelay: `${150 + i * 90}ms` }}>
                {w}
              </span>
            ))}
          </h2>
          <p className="animate-rise mt-4 text-lg text-white/80" style={{ animationDelay: "700ms" }}>
            Saige finds and scores jobs, tailors your resume and tracks every application — using only what&apos;s true about you.
          </p>
        </div>
      </section>

      {/* Form panel */}
      <section className="flex items-center justify-center px-5 py-12">
        <div className="animate-rise w-full max-w-sm">
          <Logo className="mb-10 lg:hidden" />
          <h1 className="text-3xl font-semibold tracking-tight">{isLogin ? "Welcome back" : "Create your account"}</h1>
          <p className="mt-2 text-[15px] text-muted-foreground">
            {isLogin ? "Sign in to your career command center." : "Your verified profile powers everything Saige does."}
          </p>

          {/* Full-page navigation: the backend redirects to Google and back via the proxy. */}
          <a href="/api/auth/google/authorize" className={buttonVariants({ variant: "outline", size: "lg", className: "mt-8 w-full" })}>
            <GoogleMark /> Continue with Google
          </a>
          <div className="my-6 flex items-center gap-3 text-xs text-muted-foreground">
            <span className="h-px flex-1 bg-border" /> or use email <span className="h-px flex-1 bg-border" />
          </div>

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
            <Button type="submit" size="lg" variant="gradient" disabled={busy} className="sheen mt-2 animate-gradient">
              {busy ? "Please wait…" : isLogin ? "Sign in" : "Create account"}
            </Button>
          </form>
          <p className="mt-6 text-center text-sm text-muted-foreground">
            {isLogin ? "New to Saige AI? " : "Already have an account? "}
            <Link href={isLogin ? "/register" : "/login"} className="font-medium text-primary hover:underline">
              {isLogin ? "Create an account" : "Sign in"}
            </Link>
          </p>
        </div>
      </section>
    </main>
  );
}

function GoogleMark() {
  return (
    <svg viewBox="0 0 48 48" className="size-5" aria-hidden>
      <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z" />
      <path fill="#FF3D00" d="m6.3 14.7 6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z" />
      <path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-8l-6.5 5C9.5 39.6 16.2 44 24 44z" />
      <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z" />
    </svg>
  );
}
