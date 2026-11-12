"use client";

import { ArrowRight, FileDown, Info, LifeBuoy, PlayCircle, Rocket, Search, ShieldCheck, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";

import { PageHeader } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { VideoTour, type Scene } from "@/components/video-tour";
import { CONTACT_EMAIL } from "@/components/legal";
import { Input } from "@/components/ui/form";

import { FAQ, MANUAL, QUICK_START, type ManualSection } from "./manual";

const same = (t: string) => ({ en: t, te: t, hi: t, ta: t, kn: t, ml: t });
/** Every manual screen as a narrated scene (English): purpose + each step, read aloud by the presenter. */
const FULL: Scene[] = MANUAL.map((m) => ({ image: m.image, title: same(m.title), say: same(`${m.purpose} ${m.steps.map((x) => x.replace(/^Step \d+ · /, "")).join(" ")}`) }));

const fullAudio = (i: number) => (MANUAL[i] ? `/help/audio/m-${MANUAL[i].id}.mp3` : null);

function Section({ s, onZoom, onWatch }: { s: ManualSection; onZoom: (src: string) => void; onWatch: () => void }) {
  const tone = `var(--tone-${s.tone})`;
  return (
    <section id={s.id} className="scroll-mt-24">
      <Card className="overflow-hidden" style={{ borderColor: `color-mix(in srgb, ${tone} 26%, transparent)` }}>
        <div className="grid gap-0 lg:grid-cols-[1fr_1.15fr]">
          <div className="flex flex-col gap-4 p-6">
            <div className="flex items-center gap-3">
              <span aria-hidden className="h-8 w-1.5 rounded-full" style={{ background: tone, boxShadow: `0 0 14px ${tone}` }} />
              <h2 className="text-2xl font-semibold tracking-tight">{s.title}</h2>
            </div>
            <p className="text-[15px] text-muted-foreground">{s.purpose}</p>
            <div>
              <p className="mb-2 text-xs font-semibold uppercase tracking-wider" style={{ color: tone }}>How to use it</p>
              <ol className="flex flex-col gap-2">
                {s.steps.map((step, i) => (
                  <li key={step} className="flex gap-3 text-sm">
                    <span className="grid size-6 shrink-0 place-items-center rounded-full text-xs font-semibold text-[#0b0b0c]" style={{ background: tone }}>{i + 1}</span>
                    <span className="pt-0.5">{step}</span>
                  </li>
                ))}
              </ol>
            </div>
            {s.tips?.map((t) => (
              <p key={t} className="rounded-xl border bg-muted/40 p-3 text-xs text-muted-foreground"><b className="text-foreground">Tip:</b> {t}</p>
            ))}
            <button type="button" onClick={onWatch} className="no-print inline-flex w-fit items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm font-medium hover:bg-muted"><PlayCircle className="size-4 text-primary" /> Watch the video explainer</button>
            <Link href={s.href} className="mt-auto inline-flex items-center gap-1 text-sm font-medium hover:underline">Open {s.title} <ArrowRight className="size-3.5" /></Link>
          </div>
          <button type="button" onClick={() => onZoom(s.image)} className="group relative block overflow-hidden border-t bg-black lg:border-l lg:border-t-0" aria-label={`Enlarge screenshot of ${s.title}`}>
            {/* eslint-disable-next-line @next/next/no-img-element -- static screenshots, no optimisation needed */}
            <img src={s.image} alt={`Screenshot of the ${s.title} screen`} loading="lazy" width={1280} height={800}
              className="h-full w-full object-cover object-left-top transition-transform duration-500 group-hover:scale-[1.02]" />
            <span className="absolute bottom-3 right-3 rounded-full bg-black/70 px-2.5 py-1 text-[11px] text-white opacity-0 transition-opacity group-hover:opacity-100">Click to enlarge</span>
          </button>
        </div>
      </Card>
    </section>
  );
}

export default function HelpPage() {
  const [q, setQ] = useState("");
  const [zoom, setZoom] = useState<string | null>(null);
  const [tour, setTour] = useState<{ mode: "quick" | "full"; start: number; play: boolean }>({ mode: "quick", start: 0, play: false });
  const watch = (id: string) => { setTour({ mode: "full", start: Math.max(0, MANUAL.findIndex((m) => m.id === id)), play: true }); document.getElementById("video-tour")?.scrollIntoView({ behavior: "smooth" }); };
  useEffect(() => {
    if (!zoom) return;
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setZoom(null); };
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [zoom]);
  const needle = q.trim().toLowerCase();
  const sections = useMemo(() => MANUAL.filter((s) => !needle || `${s.title} ${s.purpose} ${s.steps.join(" ")} ${(s.tips ?? []).join(" ")}`.toLowerCase().includes(needle)), [needle]);
  const faq = useMemo(() => FAQ.filter((f) => !needle || `${f.q} ${f.a}`.toLowerCase().includes(needle)), [needle]);

  return (
    <>
      <PageHeader title="Help & Guide" description="Step-by-step guides (get started, search jobs, apply, 100% ATS resume, extension) and the manual for every screen, with screenshots." />

      <div className="no-print mb-8 flex flex-wrap items-center gap-3">
      <div className="relative max-w-xl flex-1">
        <Search className="pointer-events-none absolute left-4 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search the manual…" className="h-12 rounded-full pl-11" />
      </div>
        <Button variant="outline" size="lg" onClick={() => window.print()}><FileDown /> Download PDF guide</Button>
      </div>

      <div className="grid gap-8 xl:grid-cols-[15rem_1fr]">
        <nav aria-label="Manual contents" className="hidden xl:block">
          <div className="sticky top-24 flex flex-col gap-0.5 text-sm">
            <a href="#video-tour" className="rounded-lg px-3 py-1.5 font-medium hover:bg-muted">Video tour</a>
            <a href="#quick-start" className="rounded-lg px-3 py-1.5 font-medium hover:bg-muted">Quick start</a>
            {MANUAL.map((s) => (
              <a key={s.id} href={`#${s.id}`} className="flex items-center gap-2 rounded-lg px-3 py-1.5 text-muted-foreground hover:bg-muted hover:text-foreground">
                <span className="size-1.5 rounded-full" style={{ background: `var(--tone-${s.tone})` }} /> {s.title}
              </a>
            ))}
            <a href="#faq" className="rounded-lg px-3 py-1.5 font-medium hover:bg-muted">FAQ</a>
            <a href="#about" className="rounded-lg px-3 py-1.5 font-medium hover:bg-muted">About Saige AI</a>
          </div>
        </nav>

        <div className="flex min-w-0 flex-col gap-8">
          {!needle && (
            <section id="video-tour" className="no-print scroll-mt-24">
              <h2 className="mb-1 flex items-center gap-2 text-2xl font-semibold tracking-tight"><PlayCircle className="size-5 text-primary" /> Video tour with voice</h2>
              <p className="mb-4 text-sm text-muted-foreground">An AI presenter walks you through of setup and every main feature. Choose English, Telugu, Hindi, Tamil, Kannada or Malayalam. Press Record video to save it as a file you can share.</p>
              <div className="mb-3 flex flex-wrap gap-2">
                <Button size="sm" variant={tour.mode === "quick" ? "default" : "outline"} onClick={() => setTour({ mode: "quick", start: 0, play: false })}>Quick tour · 6 languages</Button>
                <Button size="sm" variant={tour.mode === "full" ? "default" : "outline"} onClick={() => setTour({ mode: "full", start: 0, play: false })}>Every screen · {MANUAL.length} videos (English)</Button>
              </div>
              {tour.mode === "quick" ? <VideoTour key="q" /> : <VideoTour key={`f${tour.start}`} scenes={FULL} englishOnly start={tour.start} autoPlay={tour.play} audioFor={fullAudio} />}
            </section>
          )}
          {!needle && (
            <Card id="quick-start" className="scroll-mt-24 p-6" style={{ borderColor: "color-mix(in srgb, var(--tone-green) 30%, transparent)", backgroundImage: "radial-gradient(120% 80% at 100% 0%, color-mix(in srgb, var(--tone-green) 12%, transparent), transparent 60%)" }}>
              <h2 className="flex items-center gap-2 text-2xl font-semibold tracking-tight"><Rocket className="size-5" style={{ color: "var(--tone-green)" }} /> Quick start: set up in 3 minutes</h2>
              <ol className="mt-4 grid gap-2 md:grid-cols-2">
                {QUICK_START.map((step, i) => (
                  <li key={step} className="flex gap-3 rounded-xl border bg-card-solid/50 p-3 text-sm">
                    <span className="grid size-6 shrink-0 place-items-center rounded-full text-xs font-semibold text-[#0b0b0c]" style={{ background: "var(--tone-green)" }}>{i + 1}</span>
                    {step}
                  </li>
                ))}
              </ol>
            </Card>
          )}

          {sections.map((s) => <Section key={s.id} s={s} onZoom={setZoom} onWatch={() => watch(s.id)} />)}

          <section id="faq" className="scroll-mt-24">
            <h2 className="mb-4 flex items-center gap-2 text-2xl font-semibold tracking-tight"><LifeBuoy className="size-5" /> Frequently asked</h2>
            <div className="flex flex-col gap-2">
              {faq.map((f) => (
                <details key={f.q} className="glass rounded-2xl border p-4 open:shadow-[var(--shadow-card)]">
                  <summary className="cursor-pointer list-none font-medium">{f.q}</summary>
                  <p className="mt-2 text-sm text-muted-foreground">{f.a}</p>
                </details>
              ))}
              {!faq.length && !sections.length && <p className="text-sm text-muted-foreground">Nothing matches “{q}”.</p>}
            </div>
          </section>

          <Card id="about" className="scroll-mt-24 p-6">
            <h2 className="flex items-center gap-2 text-2xl font-semibold tracking-tight"><Info className="size-5 text-primary" /> About Saige AI</h2>
            <p className="mt-3 text-sm text-muted-foreground">Saige AI is a truthful career assistant for one job seeker at a time. It finds jobs, matches them to your verified profile, builds ATS resumes and cover letters, tracks applications and recruiter mail, and builds your portfolio website. It does the repetitive work so you can focus on interviews.</p>
            <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {[["Truthful", "Every claim is checked against your own profile. Numbers come only from you."],
                ["You approve", "Applications, emails and messages wait for your OK unless you turn on an auto mode."],
                ["Private", "Your data is visible only to your account. Export or delete it any time in Settings."],
                ["No scraping", "Official APIs, OAuth and your own clicks only. We never log in to LinkedIn or Naukri for you."]].map(([t, d]) => (
                <div key={t} className="rounded-2xl border p-4"><p className="font-medium">{t}</p><p className="mt-1 text-xs text-muted-foreground">{d}</p></div>
              ))}
            </div>
            <p className="mt-4 text-sm text-muted-foreground">Languages: English, తెలుగు, हिन्दी, தமிழ், ಕನ್ನಡ, മലയാളം (video tour). Contact: <a className="text-primary underline" href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a></p>
          </Card>

          <Card className="flex flex-wrap items-center gap-4 p-5">
            <ShieldCheck className="size-6" style={{ color: "var(--tone-green)" }} />
            <p className="flex-1 text-sm text-muted-foreground">Saige&apos;s promise: no fabricated experience, no scraping, no logging in to LinkedIn or Naukri for you, and nothing sent without your approval.</p>
          </Card>
        </div>
      </div>

      {/* Portalled to <body>: the page container is animated (transform), which would trap a fixed overlay. */}
      {zoom && typeof document !== "undefined" && createPortal(
        <div role="dialog" aria-modal="true" aria-label="Screenshot" className="fixed inset-0 z-[100] flex items-center justify-center bg-black/90 p-4 md:p-10" onClick={() => setZoom(null)}>
          <button className="absolute right-4 top-4 grid size-10 place-items-center rounded-full bg-white/15 text-white hover:bg-white/25" aria-label="Close"><X /></button>
          {/* eslint-disable-next-line @next/next/no-img-element -- static screenshot */}
          <img src={zoom} alt="Enlarged screenshot" className="animate-pop max-h-[92vh] max-w-[96vw] rounded-xl object-contain shadow-2xl" onClick={(e) => e.stopPropagation()} />
        </div>,
        document.body,
      )}
    </>
  );
}
