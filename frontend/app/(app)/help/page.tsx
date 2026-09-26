"use client";

import { ArrowRight, LifeBuoy, Rocket, Search, ShieldCheck, X } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { PageHeader } from "@/components/app-shell";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/form";

import { FAQ, MANUAL, QUICK_START, type ManualSection } from "./manual";

function Section({ s, onZoom }: { s: ManualSection; onZoom: (src: string) => void }) {
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
  const needle = q.trim().toLowerCase();
  const sections = useMemo(() => MANUAL.filter((s) => !needle || `${s.title} ${s.purpose} ${s.steps.join(" ")} ${(s.tips ?? []).join(" ")}`.toLowerCase().includes(needle)), [needle]);
  const faq = useMemo(() => FAQ.filter((f) => !needle || `${f.q} ${f.a}`.toLowerCase().includes(needle)), [needle]);

  return (
    <>
      <PageHeader title="Help & Docs" description="The complete Saige AI user manual: what every screen does and how to use it, step by step, with screenshots." />

      <div className="relative mb-8 max-w-xl">
        <Search className="pointer-events-none absolute left-4 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search the manual…" className="h-12 rounded-full pl-11" />
      </div>

      <div className="grid gap-8 xl:grid-cols-[15rem_1fr]">
        <nav aria-label="Manual contents" className="hidden xl:block">
          <div className="sticky top-24 flex flex-col gap-0.5 text-sm">
            <a href="#quick-start" className="rounded-lg px-3 py-1.5 font-medium hover:bg-muted">Quick start</a>
            {MANUAL.map((s) => (
              <a key={s.id} href={`#${s.id}`} className="flex items-center gap-2 rounded-lg px-3 py-1.5 text-muted-foreground hover:bg-muted hover:text-foreground">
                <span className="size-1.5 rounded-full" style={{ background: `var(--tone-${s.tone})` }} /> {s.title}
              </a>
            ))}
            <a href="#faq" className="rounded-lg px-3 py-1.5 font-medium hover:bg-muted">FAQ</a>
          </div>
        </nav>

        <div className="flex min-w-0 flex-col gap-8">
          {!needle && (
            <Card id="quick-start" className="scroll-mt-24 p-6" style={{ borderColor: "color-mix(in srgb, var(--tone-green) 30%, transparent)", backgroundImage: "radial-gradient(120% 80% at 100% 0%, color-mix(in srgb, var(--tone-green) 12%, transparent), transparent 60%)" }}>
              <h2 className="flex items-center gap-2 text-2xl font-semibold tracking-tight"><Rocket className="size-5" style={{ color: "var(--tone-green)" }} /> Quick start: set up in 10 minutes</h2>
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

          {sections.map((s) => <Section key={s.id} s={s} onZoom={setZoom} />)}

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

          <Card className="flex flex-wrap items-center gap-4 p-5">
            <ShieldCheck className="size-6" style={{ color: "var(--tone-green)" }} />
            <p className="flex-1 text-sm text-muted-foreground">Saige&apos;s promise: no fabricated experience, no scraping, no logging in to LinkedIn or Naukri for you, and nothing sent without your approval.</p>
          </Card>
        </div>
      </div>

      {zoom && (
        <div role="dialog" aria-modal="true" aria-label="Screenshot" className="fixed inset-0 z-[70] grid place-items-center bg-black/85 p-4 backdrop-blur-sm" onClick={() => setZoom(null)}>
          <button className="absolute right-4 top-4 grid size-10 place-items-center rounded-full bg-white/10 text-white" aria-label="Close"><X /></button>
          {/* eslint-disable-next-line @next/next/no-img-element -- static screenshot */}
          <img src={zoom} alt="Enlarged screenshot" className="max-h-full max-w-full rounded-xl shadow-2xl" />
        </div>
      )}
    </>
  );
}
