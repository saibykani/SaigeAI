"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Notice } from "@/components/app-shell";
import { SaigeMark, Wordmark } from "@/components/brand";
import { Galaxy } from "@/components/galaxy";
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
    <main className="relative min-h-screen overflow-hidden bg-[#02030a] text-white">
      {/* Deep-space backdrop: nebula wash + animated 3D galaxy */}
      <div aria-hidden className="pointer-events-none absolute inset-0">
        <div className="aurora absolute -left-1/4 top-0 size-[60vw] rounded-full bg-[#1d4ed8] opacity-25 blur-[120px]" />
        <div className="aurora absolute -right-1/4 bottom-0 size-[55vw] rounded-full bg-[#7c3aed] opacity-25 blur-[120px]" style={{ animationDelay: "-9s" }} />
      </div>
      <Galaxy className="absolute inset-0 h-full w-full lg:left-[-12%] lg:w-[80%]" />
      <div aria-hidden className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_center,transparent_40%,rgba(2,3,10,0.85)_100%)]" />

      <div className="relative z-10 mx-auto grid min-h-screen max-w-7xl items-center gap-10 px-5 py-10 lg:grid-cols-[1.2fr_1fr] lg:px-10">
        {/* Brand */}
        <section className="flex flex-col gap-6">
          <div className="animate-pop flex items-center gap-4">
            <SaigeMark size={64} />
            <Wordmark size="xl" className="text-white" />
          </div>
          <h2 className="max-w-xl text-3xl font-semibold leading-tight tracking-tight md:text-5xl [perspective:600px]">
            {"Your career, in perfect orbit.".split(" ").map((w, i) => (
              <span key={i} className="word-in mr-[0.25em]" style={{ animationDelay: `${250 + i * 110}ms` }}>
                {w}
              </span>
            ))}
          </h2>
          <p className="animate-rise max-w-lg text-lg text-white/70" style={{ animationDelay: "900ms" }}>
            Saige finds and scores jobs across the universe of job boards, tailors every resume, keeps LinkedIn and Naukri sharp, and tracks each application to offer — using only what&apos;s true about you.
          </p>
          <ul className="animate-rise flex flex-wrap gap-2 text-sm" style={{ animationDelay: "1100ms" }}>
            {["AI job matching", "Tailored resumes", "LinkedIn · Naukri sync", "Application tracking", "Zero fabrication"].map((t) => (
              <li key={t} className="rounded-full border border-white/15 bg-white/5 px-3 py-1 text-white/80 backdrop-blur">{t}</li>
            ))}
          </ul>
        </section>

        {/* Form */}
        <section className="animate-rise w-full max-w-md justify-self-center lg:justify-self-end" style={{ animationDelay: "300ms" }}>
          <div className="relative rounded-[28px] p-px [background:linear-gradient(140deg,rgba(34,211,238,0.6),rgba(109,124,255,0.25)_40%,rgba(168,85,247,0.6))]">
            <div className="rounded-[27px] bg-[#070a18]/80 p-8 shadow-[0_40px_80px_-30px_rgba(40,60,200,0.6)] backdrop-blur-2xl">
              <h1 className="text-2xl font-semibold tracking-tight">{isLogin ? "Welcome back" : "Create your account"}</h1>
              <p className="mt-1.5 text-sm text-white/60">
                {isLogin ? "Sign in to your career command center." : "Your verified profile powers everything Saige does."}
              </p>

              {/* Full-page navigation: the backend redirects to Google and back via the proxy. */}
              <a href="/api/auth/google/authorize" className="mt-7 flex h-12 w-full items-center justify-center gap-2.5 rounded-full bg-white text-[15px] font-medium text-[#111] transition hover:bg-white/90 active:scale-[0.99]">
                <GoogleMark /> Continue with Google
              </a>
              <div className="my-6 flex items-center gap-3 text-xs text-white/40">
                <span className="h-px flex-1 bg-white/10" /> or use email <span className="h-px flex-1 bg-white/10" />
              </div>

              <form onSubmit={onSubmit} className="flex flex-col gap-4 [&_input]:border-white/10 [&_input]:bg-white/5 [&_input]:text-white [&_input]:placeholder:text-white/30 [&_label]:text-white/60">
                {error && <Notice tone="error">{error}</Notice>}
                {!isLogin && (
                  <Field label="Full name" htmlFor="name">
                    <Input id="name" autoComplete="name" required value={name} onChange={(e) => setName(e.target.value)} />
                  </Field>
                )}
                <Field label="Email" htmlFor="email">
                  <Input id="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" />
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
                <button
                  type="submit"
                  disabled={busy}
                  className="sheen animate-gradient mt-2 h-12 cursor-pointer rounded-full bg-[linear-gradient(120deg,#22d3ee,#6d7cff,#a855f7,#22d3ee)] bg-[length:200%_200%] text-[15px] font-semibold text-white shadow-[0_12px_30px_-10px_rgba(109,124,255,0.8)] transition hover:brightness-110 active:scale-[0.99] disabled:opacity-60"
                >
                  {busy ? "Please wait…" : isLogin ? "Sign in" : "Create account"}
                </button>
              </form>
              <p className="mt-6 text-center text-sm text-white/60">
                {isLogin ? "New to Saige AI? " : "Already have an account? "}
                <Link href={isLogin ? "/register" : "/login"} className="font-medium text-cyan-300 hover:underline">
                  {isLogin ? "Create an account" : "Sign in"}
                </Link>
              </p>
            </div>
          </div>
        </section>
      </div>
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
