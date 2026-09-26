"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Notice } from "@/components/app-shell";
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
  const [step, setStep] = useState<1 | 2>(1);
  const [d, setD] = useState({ phone: "", current_designation: "", total_experience_years: "", target_role: "", current_location: "",
    country: "India", notice_period_days: "", linkedin_url: "" });
  const [error, setError] = useState<string | null>(
    params.get("error") === "google_denied"
      ? "Google didn't allow this sign-in. If you saw “Access blocked”, the app owner needs to add your Google account as a test user (Google Cloud → Google Auth Platform → Audience). You can also sign in with email and password."
      : params.get("error") === "google" ? "Google sign-in failed or was cancelled." : null,
  );
  const [busy, setBusy] = useState(false);
  const next = safeNext(params.get("next"));

  useEffect(() => {
    if (!loading && user) router.replace(next);
  }, [loading, user, router, next]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (mode === "register" && step === 1) {
      setStep(2);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      if (mode === "login") await login(email, password);
      else {
        const num = (v: string) => (v.trim() === "" ? undefined : Number(v));
        await register(name, email, password, {
          phone: d.phone || undefined, current_designation: d.current_designation || undefined,
          total_experience_years: num(d.total_experience_years), target_role: d.target_role || undefined,
          current_location: d.current_location || undefined, country: d.country || undefined,
          notice_period_days: num(d.notice_period_days), linkedin_url: d.linkedin_url || undefined,
        });
      }
      router.replace(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  const isLogin = mode === "login";
  return (
    <main className="relative min-h-screen overflow-hidden bg-black text-white">
      {/* Interactive galaxy fills the page, centred */}
      <Galaxy className="absolute inset-0 h-full w-full cursor-grab" />
      <div aria-hidden className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_center,transparent_45%,rgba(0,0,0,0.75)_100%)]" />

      <div className="pointer-events-none relative z-10 mx-auto flex min-h-screen max-w-[1500px] flex-col justify-between gap-10 px-5 py-8 lg:flex-row lg:items-center lg:px-12">
        {/* Brand */}
        <section className="pointer-events-auto flex max-w-md flex-col gap-5 lg:max-w-sm xl:max-w-md">
          <h1 className="animate-pop text-5xl font-semibold tracking-tight md:text-6xl">
            Saige <span className="bg-gradient-to-r from-white via-neutral-300 to-neutral-500 bg-clip-text text-transparent">AI</span>
          </h1>
          <p className="text-2xl font-medium leading-snug tracking-tight text-white/90 md:text-3xl [perspective:600px]">
            {"Your career, in perfect orbit.".split(" ").map((w, i) => (
              <span key={i} className="word-in mr-[0.25em]" style={{ animationDelay: `${250 + i * 110}ms` }}>
                {w}
              </span>
            ))}
          </p>
          <p className="animate-rise text-[15px] leading-relaxed text-white/55" style={{ animationDelay: "900ms" }}>
            Jobs found and scored for you, resumes tailored to every role, LinkedIn and Naukri kept sharp, and every application tracked to offer — using only what&apos;s true about you.
          </p>
          <p className="animate-rise hidden text-xs text-white/35 lg:block" style={{ animationDelay: "1300ms" }}>
            Move through the stars · click to scatter them · drag to orbit
          </p>
        </section>

        {/* Form */}
        <section className="pointer-events-auto animate-rise w-full max-w-md self-center lg:self-auto" style={{ animationDelay: "300ms" }}>
          <div className="rounded-[28px] bg-[linear-gradient(145deg,rgba(255,255,255,0.35),rgba(255,255,255,0.05)_45%,rgba(255,255,255,0.22))] p-px">
            <div className="rounded-[27px] bg-black/70 p-8 shadow-[0_40px_90px_-30px_rgba(255,255,255,0.12)] backdrop-blur-2xl">
              <h2 className="text-2xl font-semibold tracking-tight">{isLogin ? "Welcome back" : "Create your account"}</h2>
              <p className="mt-1.5 text-sm text-white/55">
                {isLogin ? "Sign in to continue your job search." : "Your verified profile powers everything Saige does."}
              </p>

              {/* Full-page navigation: the backend redirects to Google and back via the proxy. */}
              <a href="/api/auth/google/authorize" className="mt-7 flex h-12 w-full items-center justify-center gap-2.5 rounded-full border border-white/15 bg-white/[0.04] text-[15px] font-medium text-white transition hover:bg-white/10 active:scale-[0.99]">
                <GoogleMark /> Continue with Google
              </a>
              <div className="my-6 flex items-center gap-3 text-xs text-white/35">
                <span className="h-px flex-1 bg-white/10" /> or use email <span className="h-px flex-1 bg-white/10" />
              </div>

              <form onSubmit={onSubmit} className="auth-dark flex flex-col gap-4">
                {error && <Notice tone="error">{error}</Notice>}
                {!isLogin && (
                  <div className="flex items-center gap-2 text-xs text-white/50">
                    {[1, 2].map((n) => <span key={n} className={`h-1 flex-1 rounded-full ${step >= n ? "bg-white" : "bg-white/15"}`} />)}
                    <span className="ml-1">Step {step} of 2 · {step === 1 ? "Account" : "Your career"}</span>
                  </div>
                )}
                {!isLogin && step === 2 && (
                  <>
                    <div className="grid grid-cols-2 gap-3">
                      <Field label="Current role" htmlFor="role"><Input id="role" required placeholder="QA Engineer" value={d.current_designation} onChange={(e) => setD({ ...d, current_designation: e.target.value })} /></Field>
                      <Field label="Experience (years)" htmlFor="exp"><Input id="exp" type="number" min={0} max={60} step={0.5} required value={d.total_experience_years} onChange={(e) => setD({ ...d, total_experience_years: e.target.value })} /></Field>
                    </div>
                    <Field label="Roles you want" htmlFor="target" hint="Comma-separated, e.g. SDET, QA Automation Engineer">
                      <Input id="target" required value={d.target_role} onChange={(e) => setD({ ...d, target_role: e.target.value })} />
                    </Field>
                    <div className="grid grid-cols-2 gap-3">
                      <Field label="City" htmlFor="city"><Input id="city" required placeholder="Hyderabad" value={d.current_location} onChange={(e) => setD({ ...d, current_location: e.target.value })} /></Field>
                      <Field label="Country" htmlFor="country"><Input id="country" required value={d.country} onChange={(e) => setD({ ...d, country: e.target.value })} /></Field>
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <Field label="Phone" htmlFor="phone"><Input id="phone" type="tel" autoComplete="tel" placeholder="+91 98765 43210" value={d.phone} onChange={(e) => setD({ ...d, phone: e.target.value })} /></Field>
                      <Field label="Notice period (days)" htmlFor="notice"><Input id="notice" type="number" min={0} max={365} value={d.notice_period_days} onChange={(e) => setD({ ...d, notice_period_days: e.target.value })} /></Field>
                    </div>
                    <Field label="LinkedIn profile (optional)" htmlFor="li"><Input id="li" type="url" placeholder="https://www.linkedin.com/in/…" value={d.linkedin_url} onChange={(e) => setD({ ...d, linkedin_url: e.target.value })} /></Field>
                  </>
                )}
                {(isLogin || step === 1) && !isLogin && (
                  <Field label="Full name" htmlFor="name">
                    <Input id="name" autoComplete="name" required value={name} onChange={(e) => setName(e.target.value)} />
                  </Field>
                )}
                {(isLogin || step === 1) && (<>
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
                </>)}
                <button
                  type="submit"
                  disabled={busy}
                  className="sheen mt-2 h-12 cursor-pointer rounded-full bg-white text-[15px] font-semibold text-black shadow-[0_0_40px_-8px_rgba(255,255,255,0.55)] transition hover:shadow-[0_0_55px_-6px_rgba(255,255,255,0.75)] active:scale-[0.99] disabled:opacity-60"
                >
                  {busy ? "Please wait…" : isLogin ? "Sign in" : step === 1 ? "Continue" : "Create account"}
                </button>
                {!isLogin && step === 2 && (
                  <button type="button" onClick={() => setStep(1)} className="-mt-1 text-sm text-white/55 hover:text-white">← Back</button>
                )}
              </form>
              <p className="mt-6 text-center text-sm text-white/55">
                {isLogin ? "New to Saige AI? " : "Already have an account? "}
                <Link href={isLogin ? "/register" : "/login"} className="font-medium text-white underline-offset-4 hover:underline">
                  {isLogin ? "Create an account" : "Sign in"}
                </Link>
              </p>
              <p className="mt-4 text-center text-xs text-white/35">
                By continuing you agree to the <Link href="/terms" className="underline-offset-4 hover:text-white/70 hover:underline">Terms</Link> and{" "}
                <Link href="/privacy" className="underline-offset-4 hover:text-white/70 hover:underline">Privacy Policy</Link>.
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
