"use client";

import { CalendarPlus, ChevronDown, Plus, Trash2, Video } from "lucide-react";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Notice, PageHeader } from "@/components/app-shell";
import { useT } from "@/components/i18n";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/form";
import { useApi } from "@/hooks/use-api";
import { downloadFile, request } from "@/services/api";
import type { WarRoom, WarRoomChecklist } from "@/types/api";
import { formatDateTime } from "@/utils/format";

function useCountdown(iso: string | undefined) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);
  if (!iso) return null;
  const ms = new Date(iso).getTime() - now;
  const abs = Math.abs(ms);
  const d = Math.floor(abs / 864e5);
  const h = Math.floor((abs % 864e5) / 36e5);
  const m = Math.floor((abs % 36e5) / 6e4);
  const s = Math.floor((abs % 6e4) / 1e3);
  return { started: ms < 0, d, h, m, s };
}

function Unit({ value, label }: { value: number; label: string }) {
  return (
    <div className="flex flex-col items-center">
      <span className="text-5xl font-light tabular-nums tracking-tight md:text-7xl" style={{ color: "var(--tone-orange)" }}>{String(value).padStart(2, "0")}</span>
      <span className="text-xs uppercase tracking-widest text-muted-foreground">{label}</span>
    </div>
  );
}

export default function WarRoomPage() {
  const { id } = useParams<{ id: string }>();
  const { t } = useT();
  const { data, error } = useApi<WarRoom>(`/war-room/${id}`);
  const [checklist, setChecklist] = useState<WarRoomChecklist | null>(null);
  const [open, setOpen] = useState<number | null>(null);
  const [draft, setDraft] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const cd = useCountdown(data?.scheduled_at);
  const list = checklist ?? data?.checklist ?? null;

  async function patch(body: { item_id?: string; done?: boolean; add?: string; remove?: string }) {
    setErr(null);
    try {
      setChecklist(await request<WarRoomChecklist>(`/war-room/${id}/checklist`, { method: "PATCH", body }));
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not update the checklist");
    }
  }

  if (error) return <Notice tone="error">{error}</Notice>;
  if (!data) return <div className="skeleton h-96 rounded-3xl" />;

  return (
    <>
      <PageHeader
        title={`${data.role ?? "Interview"} · ${data.company ?? ""}`}
        description={`${data.round || "Interview"} · ${formatDateTime(data.scheduled_at)} · ${data.duration_minutes} min`}
        actions={
          <>
            <Button variant="ghost" onClick={() => downloadFile(`/interviews/${id}.ics`, "interview.ics")}><CalendarPlus /> {t("Calendar")}</Button>
            {data.links.join && (
              <a href={data.links.join} target="_blank" rel="noopener noreferrer" className="inline-flex h-10 items-center gap-2 rounded-full bg-primary px-5 text-sm font-medium text-primary-foreground">
                <Video className="size-4" /> {t("Join")}
              </a>
            )}
          </>
        }
      />
      {err && <Notice tone="error">{err}</Notice>}
      <div className="mx-auto flex max-w-4xl flex-col gap-6">
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-10">
            {cd && (cd.started ? (
              <p className="text-2xl font-light">{t("Started")} {cd.h > 0 ? `${cd.h} h ` : ""}{cd.m} min {t("ago")}</p>
            ) : (
              <div className="flex gap-6 md:gap-10">
                <Unit value={cd.d} label={t("days")} /><Unit value={cd.h} label={t("hours")} />
                <Unit value={cd.m} label={t("min")} /><Unit value={cd.s} label={t("sec")} />
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>{t("Brief")}</CardTitle></CardHeader>
          <CardContent className="flex flex-col gap-3 text-sm">
            {!data.has_job && <p className="text-muted-foreground">{t("No saved job description matched this interview, so requirements and questions are generic. Save the job to sharpen them.")}</p>}
            {data.interviewer && <p>{t("Interviewer")}: <span className="font-medium">{data.interviewer}</span></p>}
            <div className="flex flex-wrap gap-1.5">
              {data.skills.map((s) => <Badge key={s} variant={data.brush_up.includes(s) ? "warning" : "default"}>{s}</Badge>)}
            </div>
            {data.brush_up.length > 0 && <p className="text-muted-foreground">{t("Brush up on")}: {data.brush_up.join(", ")}</p>}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>{t("Requirements vs your evidence")}</CardTitle></CardHeader>
          <CardContent>
            {data.requirements.length === 0 ? <p className="text-sm text-muted-foreground">UNKNOWN</p> : (
              <ul className="flex flex-col gap-2 text-sm">
                {data.requirements.map((r) => (
                  <li key={r.text} className="flex items-start justify-between gap-4 rounded-2xl border p-3">
                    <span>{r.text}</span>
                    <span className="shrink-0 text-xs" style={{ color: r.evidence ? "var(--tone-green)" : "var(--tone-yellow)" }}>
                      {r.evidence ?? t("No evidence in your profile")}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>{t("Likely questions")}</CardTitle></CardHeader>
          <CardContent className="flex flex-col gap-2">
            {data.questions.map((q, n) => (
              <div key={q.text} className="rounded-2xl border">
                <button type="button" onClick={() => setOpen(open === n ? null : n)} className="flex w-full items-center justify-between gap-3 p-3 text-left text-sm">
                  <span>{q.text}</span>
                  <ChevronDown className={`size-4 shrink-0 text-muted-foreground transition-transform ${open === n ? "rotate-180" : ""}`} />
                </button>
                {open === n && (
                  <div className="border-t px-3 py-3 text-sm">
                    <p className="text-xs uppercase tracking-widest text-muted-foreground">{t("Your story")}{q.story.name ? ` · ${q.story.name}` : ""}</p>
                    <p className={q.story.line === "UNKNOWN" ? "mt-1 text-muted-foreground" : "mt-1"}>
                      {q.story.line === "UNKNOWN" ? t("UNKNOWN: nothing in your verified profile matches. Add a real example to your profile.") : q.story.line}
                    </p>
                  </div>
                )}
              </div>
            ))}
          </CardContent>
        </Card>

        {list && (
          <Card>
            <CardHeader><CardTitle>{t("Checklist")} · {list.done}/{list.total}</CardTitle></CardHeader>
            <CardContent className="flex flex-col gap-2">
              {list.items.map((it) => (
                <div key={it.id} className="flex items-center gap-3 text-sm">
                  <input type="checkbox" className="size-4 accent-[var(--tone-green)]" checked={it.done} onChange={(e) => patch({ item_id: it.id, done: e.target.checked })} />
                  <span className={`flex-1 ${it.done ? "text-muted-foreground line-through" : ""}`}>{it.text}</span>
                  {it.custom && <button type="button" aria-label={t("Remove")} onClick={() => patch({ remove: it.id })}><Trash2 className="size-4 text-muted-foreground" /></button>}
                </div>
              ))}
              <form className="mt-2 flex gap-2" onSubmit={(e) => { e.preventDefault(); if (draft.trim()) { patch({ add: draft.trim() }); setDraft(""); } }}>
                <Input value={draft} onChange={(e) => setDraft(e.target.value)} placeholder={t("Add your own item")} />
                <Button type="submit" variant="ghost"><Plus /> {t("Add")}</Button>
              </form>
            </CardContent>
          </Card>
        )}
      </div>
    </>
  );
}
