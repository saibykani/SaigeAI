"use client";

import { Download, Play, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Notice, PageHeader } from "@/components/app-shell";
import { useT } from "@/components/i18n";
import { CountUp } from "@/components/motion";
import { Button } from "@/components/ui/button";
import { useApi } from "@/hooks/use-api";
import type { Wrapped, WrappedPeriod } from "@/types/api";

const PERIODS: { key: WrappedPeriod; label: string }[] = [
  { key: "week", label: "Last 7 days" },
  { key: "month", label: "Last 30 days" },
  { key: "all", label: "All time" },
];
const SLIDE_MS = 5000;
const HOLD_MS = 180;

type Tone = "green" | "orange" | "yellow" | "purple" | "red" | "mint" | "teal" | "lime";
// Concrete colours for the PNG (canvas cannot read CSS variables reliably); the screen uses the theme tokens.
const TONE_HEX: Record<Tone, string> = {
  green: "#30d158", orange: "#ff9f0a", yellow: "#ffd60a", purple: "#bf5af2", red: "#ff453a", mint: "#63e6be", teal: "#40c8e0", lime: "#a3e635",
};

interface Slide {
  key: string;
  tone: Tone;
  kicker: string;
  big?: number;
  suffix?: string;
  text?: string; // big text instead of a number
  line: string;
  list?: { name: string; count: number }[];
  note?: string;
}

const prefersReducedMotion = () => typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

const prettyDate = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" });

function buildSlides(d: Wrapped, t: (s: string) => string): Slide[] {
  if (d.empty) {
    return [{ key: "empty", tone: "green", kicker: t("Career Wrapped"), text: t("Nothing here yet"), line: t("Apply, send outreach or tailor a resume and your story will appear here.") }];
  }
  const s: Slide[] = [
    { key: "intro", tone: "green", kicker: t("Career Wrapped"), text: t("Your job search, in numbers"), line: t("Tap to move through. Hold to pause.") },
    { key: "apps", tone: "orange", kicker: t("Applications sent"), big: d.applications, line: d.span_days ? `${t("over")} ${d.span_days} ${t("day(s)")}` : t("Every one counts.") },
    { key: "replies", tone: "purple", kicker: t("Replies received"), big: d.replies, line: d.reply_rate != null ? `${d.reply_rate}% ${t("reply rate")}` : t("No applications sent yet") },
    { key: "int", tone: "teal", kicker: t("Interviews"), big: d.interviews, line: `${d.offers} ${t("offer(s)")}` },
  ];
  if (d.busiest_day) {
    s.push({ key: "busy", tone: "yellow", kicker: t("Your busiest day"), text: prettyDate(d.busiest_day.date), line: `${d.busiest_day.count} ${t("applications sent")}` });
  }
  s.push({ key: "streak", tone: "mint", kicker: t("Longest streak"), big: d.longest_streak, suffix: ` ${t("day(s)")}`, line: t("Days in a row with real activity (India time).") });
  if (d.top_skills.length) s.push({ key: "skills", tone: "lime", kicker: t("Top skills matched"), line: t("From the jobs you applied to."), list: d.top_skills });
  if (d.top_companies.length) s.push({ key: "co", tone: "red", kicker: t("Most applied companies"), line: t("Where you showed up the most."), list: d.top_companies });
  s.push({ key: "work", tone: "orange", kicker: t("Behind the scenes"), big: d.resumes_generated, line: `${t("resumes generated")} · ${d.outreach_sent} ${t("outreach messages sent")}` });
  s.push({ key: "who", tone: "purple", kicker: t("You are"), text: d.personality.label, line: d.personality.rule, note: t("Chosen by a fixed rule from your numbers.") });
  s.push({ key: "summary", tone: "green", kicker: t("Summary"), line: "" });
  return s;
}

function summaryRows(d: Wrapped, t: (s: string) => string): [string, string][] {
  return [
    [t("Applications"), String(d.applications)],
    [t("Replies"), d.reply_rate != null ? `${d.replies} (${d.reply_rate}%)` : String(d.replies)],
    [t("Interviews"), String(d.interviews)],
    [t("Offers"), String(d.offers)],
    [t("Longest streak"), `${d.longest_streak} ${t("day(s)")}`],
    [t("Resumes generated"), String(d.resumes_generated)],
    [t("Outreach sent"), String(d.outreach_sent)],
  ];
}

/** Draws the summary card to a PNG by hand (no dependencies). */
function downloadSummary(d: Wrapped, t: (s: string) => string, periodLabel: string) {
  const W = 1080, H = 1350;
  const cv = document.createElement("canvas");
  cv.width = W;
  cv.height = H;
  const g = cv.getContext("2d");
  if (!g) return;
  const font = '"Google Sans", "Segoe UI", system-ui, sans-serif';
  const accent = TONE_HEX.green;
  g.fillStyle = "#000";
  g.fillRect(0, 0, W, H);
  g.fillStyle = "#0e0e10";
  g.beginPath();
  g.roundRect(60, 60, W - 120, H - 120, 56);
  g.fill();
  g.textBaseline = "alphabetic";
  g.fillStyle = accent;
  g.font = `500 34px ${font}`;
  g.fillText("SAIGE AI · CAREER WRAPPED", 120, 160);
  g.fillStyle = "#8e8e93";
  g.font = `400 30px ${font}`;
  g.fillText(periodLabel, 120, 206);
  g.fillStyle = "#fff";
  g.font = `300 84px ${font}`;
  g.fillText(d.personality.label, 120, 330);
  g.fillStyle = "#8e8e93";
  g.font = `400 28px ${font}`;
  g.fillText(d.personality.rule.slice(0, 64), 120, 378);

  let y = 500;
  for (const [label, value] of summaryRows(d, t)) {
    g.fillStyle = "#8e8e93";
    g.font = `400 36px ${font}`;
    g.textAlign = "left";
    g.fillText(label, 120, y);
    g.fillStyle = accent;
    g.font = `500 52px ${font}`;
    g.textAlign = "right";
    g.fillText(value, W - 120, y + 4);
    g.fillStyle = "#222226";
    g.fillRect(120, y + 30, W - 240, 2);
    y += 100;
  }
  g.textAlign = "left";
  if (d.top_companies.length) {
    g.fillStyle = "#8e8e93";
    g.font = `400 30px ${font}`;
    g.fillText(`${t("Top companies")}: ${d.top_companies.slice(0, 3).map((x) => x.name).join(", ")}`.slice(0, 70), 120, y + 40);
  }
  g.fillStyle = "#636366";
  g.font = `400 26px ${font}`;
  g.fillText("saige-ai.vercel.app", 120, H - 110);
  cv.toBlob((blob) => {
    if (!blob) return;
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `career-wrapped-${d.period}.png`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }, "image/png");
}

function SummaryCard({ d, tone }: { d: Wrapped; tone: Tone }) {
  const { t } = useT();
  return (
    <div className="w-full max-w-md rounded-[2rem] bg-[#0e0e10] p-7 text-left">
      <p className="text-xs font-medium tracking-[0.2em]" style={{ color: `var(--tone-${tone})` }}>SAIGE AI · {t("CAREER WRAPPED")}</p>
      <p className="mt-3 text-3xl font-light tracking-[-0.02em] text-white">{d.personality.label}</p>
      <dl className="mt-5 flex flex-col">
        {summaryRows(d, t).map(([k, v]) => (
          <div key={k} className="flex items-baseline justify-between border-b border-white/10 py-2">
            <dt className="text-sm text-white/60">{k}</dt>
            <dd className="text-lg font-medium tabular-nums" style={{ color: `var(--tone-${tone})` }}>{v}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function Story({ data, periodLabel, onClose }: { data: Wrapped; periodLabel: string; onClose: () => void }) {
  const { t } = useT();
  const slides = useMemo(() => buildSlides(data, t), [data, t]);
  const [index, setIndex] = useState(0);
  const [progress, setProgress] = useState(0);
  const [held, setHeld] = useState(false);
  const reduced = useRef(false);
  const press = useRef<{ x: number; at: number; timer: number | null; wasHold: boolean } | null>(null);
  const last = slides.length - 1;
  const slide = slides[Math.min(index, last)];

  useEffect(() => { reduced.current = prefersReducedMotion(); }, []);

  const go = useCallback((delta: number) => {
    setProgress(0);
    setIndex((i) => Math.max(0, Math.min(last, i + delta)));
  }, [last]);

  // Auto-advance: ~5 s per slide, paused while held, off with reduced motion, and the last slide stays.
  useEffect(() => {
    if (held || index >= last || prefersReducedMotion()) return;
    let frame = 0;
    const start = performance.now() - progress * SLIDE_MS;
    const tick = (now: number) => {
      const p = Math.min(1, (now - start) / SLIDE_MS);
      setProgress(p);
      if (p >= 1) go(1);
      else frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [held, index, last, go]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight" || e.key === " ") go(1);
      else if (e.key === "ArrowLeft") go(-1);
      else if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [go, onClose]);

  const onDown = (e: React.PointerEvent) => {
    const p = { x: e.clientX, at: Date.now(), timer: null as number | null, wasHold: false };
    p.timer = window.setTimeout(() => { p.wasHold = true; setHeld(true); }, HOLD_MS);
    press.current = p;
  };
  const onUp = (e: React.PointerEvent) => {
    const p = press.current;
    press.current = null;
    if (!p) return;
    if (p.timer) clearTimeout(p.timer);
    setHeld(false);
    const dx = e.clientX - p.x;
    if (Math.abs(dx) > 50) go(dx < 0 ? 1 : -1);
    else if (!p.wasHold) go(e.clientX < window.innerWidth / 3 ? -1 : 1);
  };
  const onCancel = () => {
    if (press.current?.timer) clearTimeout(press.current.timer);
    press.current = null;
    setHeld(false);
  };

  const accent = `var(--tone-${slide.tone})`;
  return (
    <div
      className="fixed inset-0 z-[80] flex select-none flex-col bg-black text-white"
      onPointerDown={onDown}
      onPointerUp={onUp}
      onPointerCancel={onCancel}
      onPointerLeave={onCancel}
      role="dialog"
      aria-label={t("Career Wrapped")}
    >
      <div className="flex gap-1.5 px-4 pt-4" aria-hidden>
        {slides.map((s, i) => (
          <span key={s.key} className="h-1 flex-1 overflow-hidden rounded-full bg-white/20">
            <span className="block h-full rounded-full" style={{ width: `${i < index ? 100 : i === index ? (index >= last || reduced.current ? 100 : progress * 100) : 0}%`, background: accent }} />
          </span>
        ))}
      </div>
      <div className="flex items-center justify-between px-5 pt-4">
        <span className="text-sm text-white/60">{periodLabel}</span>
        <button
          type="button"
          aria-label={t("Close")}
          className="rounded-full bg-white/10 p-2 text-white"
          onPointerDown={(e) => e.stopPropagation()}
          onPointerUp={(e) => e.stopPropagation()}
          onClick={onClose}
        >
          <X className="size-5" />
        </button>
      </div>

      <div key={slide.key} className="animate-rise flex flex-1 flex-col items-center justify-center gap-5 px-8 text-center">
        <p className="text-sm font-medium uppercase tracking-[0.2em]" style={{ color: accent }}>{slide.kicker}</p>
        {slide.big !== undefined && (
          <p className="text-[clamp(5rem,26vw,11rem)] font-light leading-none tracking-[-0.04em] tabular-nums" style={{ color: accent }}>
            <CountUp value={slide.big} duration={1100} suffix={slide.suffix} />
          </p>
        )}
        {slide.text && <p className="max-w-2xl text-[clamp(2.2rem,8vw,4.5rem)] font-light leading-tight tracking-[-0.03em]" style={{ color: accent }}>{slide.text}</p>}
        {slide.list && (
          <ol className="flex w-full max-w-md flex-col gap-3">
            {slide.list.map((x, i) => (
              <li key={x.name} className="animate-rise flex items-center justify-between rounded-full px-5 py-3 text-left" style={{ animationDelay: `${i * 90}ms`, background: `color-mix(in srgb, ${accent} 16%, #000)` }}>
                <span className="truncate text-lg">{i + 1}. {x.name}</span>
                <span className="ml-3 tabular-nums" style={{ color: accent }}>{x.count}×</span>
              </li>
            ))}
          </ol>
        )}
        {slide.key === "summary" && (
          <>
            <SummaryCard d={data} tone={slide.tone} />
            <Button
              onPointerDown={(e) => e.stopPropagation()}
              onPointerUp={(e) => e.stopPropagation()}
              onClick={() => downloadSummary(data, t, periodLabel)}
            >
              <Download className="size-4" /> {t("Download image")}
            </Button>
          </>
        )}
        {slide.line && <p className="max-w-md text-lg text-white/70">{slide.line}</p>}
        {slide.note && <p className="text-sm text-white/40">{slide.note}</p>}
      </div>
      <p className="pb-5 text-center text-xs text-white/30">{index + 1} / {slides.length}</p>
    </div>
  );
}

export default function WrappedPage() {
  const { t } = useT();
  const router = useRouter();
  const [period, setPeriod] = useState<WrappedPeriod>("all");
  const [open, setOpen] = useState(true);
  const { data, error } = useApi<Wrapped>(`/wrapped?period=${period}`);
  const periodLabel = t(PERIODS.find((p) => p.key === period)?.label ?? "All time");

  const close = useCallback(() => setOpen(false), []);

  return (
    <>
      <PageHeader
        title="Career Wrapped"
        description="Your job search as a story, built only from your real records."
        actions={
          <>
            {PERIODS.map((p) => (
              <Button key={p.key} variant={p.key === period ? "default" : "outline"} onClick={() => setPeriod(p.key)}>{t(p.label)}</Button>
            ))}
            <Button variant="outline" onClick={() => setOpen(true)} disabled={!data}><Play className="size-4" /> {t("Play story")}</Button>
          </>
        }
      />
      {error && <Notice tone="error">{error}</Notice>}
      {data?.empty && <Notice>{t("No activity in this period yet. Zero is shown as zero.")}</Notice>}
      {data && !data.empty && (
        <div className="flex flex-col items-start gap-4">
          <SummaryCard d={data} tone="green" />
          <Button onClick={() => downloadSummary(data, t, periodLabel)}><Download className="size-4" /> {t("Download image")}</Button>
        </div>
      )}
      {data && open && (
        <Story key={`${period}-${data.generated_at}`} data={data} periodLabel={periodLabel} onClose={() => { close(); if (data.empty) router.push("/dashboard"); }} />
      )}
    </>
  );
}
