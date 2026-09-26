import Link from "next/link";

import { Wordmark } from "@/components/brand";

// Shown on the public Privacy and Terms pages (Google's OAuth review requires a reachable contact).
export const CONTACT_EMAIL = "info.saigeai@gmail.com";
export const UPDATED = "26 September 2026";

/** Shared layout for public legal pages: readable, black, no sign-in required. */
export function LegalPage({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-black text-white">
      <header className="mx-auto flex max-w-3xl items-center justify-between px-4 py-6">
        <Link href="/login" aria-label="Saige AI home"><Wordmark className="text-[19px] text-white" /></Link>
        <nav className="flex gap-5 text-sm text-white/60">
          <Link href="/privacy" className="hover:text-white">Privacy</Link>
          <Link href="/terms" className="hover:text-white">Terms</Link>
          <Link href="/login" className="hover:text-white">Sign in</Link>
        </nav>
      </header>
      <main className="mx-auto max-w-3xl px-4 pb-20">
        <h1 className="text-4xl font-semibold tracking-tight">{title}</h1>
        <p className="mt-2 text-sm text-white/50">Last updated {UPDATED}</p>
        <div className="legal mt-10 space-y-8 text-[15px] leading-relaxed text-white/80">{children}</div>
      </main>
    </div>
  );
}

export function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h2 className="mb-3 text-xl font-semibold text-white">{title}</h2>
      <div className="space-y-3">{children}</div>
    </section>
  );
}
