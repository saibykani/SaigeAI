"use client";

import { Apple, Download, Share, Smartphone, SquarePlus } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { LATEST, RELEASES, releaseDate } from "@/components/app-releases";
import { SaigeMark } from "@/components/brand";

export const APK_URL = "/downloads/saige-ai-android.apk";

/** "Get the app" block: Android APK download and iPhone Add-to-Home-Screen steps. Highlights the visitor's platform. */
export function AppDownload({ compact = false }: { compact?: boolean }) {
  const [os, setOs] = useState<"android" | "ios" | "other">("other");
  useEffect(() => {
    const ua = navigator.userAgent;
    setOs(/android/i.test(ua) ? "android" : /iphone|ipad|ipod/i.test(ua) ? "ios" : "other");
  }, []);
  const card = "rounded-3xl border border-white/10 bg-white/[0.04] p-6";
  const ring = "ring-2 ring-[var(--primary,#e11d48)]";

  return (
    <section aria-labelledby="get-app" className="space-y-6">
      {!compact && (
        <div className="flex items-center gap-4">
          <SaigeMark className="size-14 rounded-2xl" />
          <div>
            <h1 id="get-app" className="text-3xl font-semibold tracking-tight md:text-4xl">Get the Saige AI app</h1>
            <p className="text-white/60">Jobs, applications, interviews and your voice assistant in your pocket.</p>
          </div>
        </div>
      )}
      <div className="grid gap-4 md:grid-cols-2">
        <div className={`${card} ${os === "android" ? ring : ""}`}>
          <Smartphone className="mb-3 size-7" />
          <h2 className="text-xl font-semibold">Android</h2>
          <p className="mt-1 text-sm text-white/60">The native Saige app. Android 7 or newer, {LATEST.size}.</p>
          <p className="mt-2 inline-flex rounded-full bg-white/10 px-3 py-1 text-xs text-white/80">Version {LATEST.version} · updated {releaseDate(LATEST.date)}</p>
          <a href={APK_URL} download className="mt-4 inline-flex items-center gap-2 rounded-full bg-white px-5 py-3 text-sm font-semibold text-black">
            <Download className="size-4" /> Download for Android
          </a>
          <ol className="mt-4 list-decimal space-y-1 pl-5 text-xs text-white/60">
            <li>Open the downloaded file.</li>
            <li>If Android asks, allow “Install unknown apps” for your browser.</li>
            <li>Open Saige AI and sign in with your account.</li>
          </ol>
        </div>
        <div className={`${card} ${os === "ios" ? ring : ""}`}>
          <Apple className="mb-3 size-7" />
          <h2 className="text-xl font-semibold">iPhone & iPad</h2>
          <p className="mt-1 text-sm text-white/60">Apple doesn&apos;t allow app files outside the App Store, so install Saige from Safari. It opens full-screen like an app, with notifications (iOS 16.4+).</p>
          <ol className="mt-4 space-y-2 text-sm">
            <li className="flex items-center gap-2"><span className="grid size-6 place-items-center rounded-full bg-white/10 text-xs">1</span> Open <b>saige-ai.vercel.app</b> in Safari</li>
            <li className="flex items-center gap-2"><span className="grid size-6 place-items-center rounded-full bg-white/10 text-xs">2</span> Tap <Share className="size-4" /> Share</li>
            <li className="flex items-center gap-2"><span className="grid size-6 place-items-center rounded-full bg-white/10 text-xs">3</span> Tap <SquarePlus className="size-4" /> Add to Home Screen</li>
          </ol>
          {os === "ios" ? null : <p className="mt-4 text-xs text-white/50">On your iPhone, open this page to see these steps.</p>}
        </div>
      </div>
      {!compact && (
        <div className="rounded-3xl border border-white/10 bg-white/[0.04] p-6">
          <h2 className="text-xl font-semibold">What&apos;s new</h2>
          <ol className="mt-4 space-y-5">
            {RELEASES.map((r, i) => (
              <li key={r.version} className="relative border-l border-white/15 pl-5">
                <span className={`absolute -left-[5px] top-1.5 size-2.5 rounded-full ${i === 0 ? "bg-white" : "bg-white/40"}`} />
                <p className="flex flex-wrap items-baseline gap-2">
                  <b>Version {r.version}</b>
                  {i === 0 && <span className="rounded-full bg-white px-2 py-0.5 text-[10px] font-semibold text-black">LATEST</span>}
                  <span className="text-xs text-white/50">{releaseDate(r.date)} · {r.size}</span>
                </p>
                <ul className="mt-2 list-disc space-y-1 pl-4 text-sm text-white/70">{r.notes.map((n) => <li key={n}>{n}</li>)}</ul>
              </li>
            ))}
          </ol>
        </div>
      )}
      {!compact && <p className="text-sm text-white/50"><Link href="/home" className="underline">Back to Saige AI</Link></p>}
    </section>
  );
}
