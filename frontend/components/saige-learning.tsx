"use client";

import { Brain, ExternalLink, ThumbsDown, ThumbsUp } from "lucide-react";
import { useState } from "react";

import { Notice } from "@/components/app-shell";
import { CountKpi } from "@/components/kpi";
import { Loader3D } from "@/components/loader3d";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useApi } from "@/hooks/use-api";
import { request } from "@/services/api";
import type { MlStatus, MlTask, MlTrainResult } from "@/types/api";
import { cn } from "@/utils/cn";
import { timeAgo } from "@/utils/format";

export async function sendFeedback(jobId: string, body: { rating?: "up" | "down"; category?: string }) {
  return request<{ trained: MlTrainResult | null; labels_since_training: number }>("/ml/feedback", { method: "POST", body: { job_id: jobId, ...body } });
}

/** 👍 / 👎 buttons for one posting. */
export function RateButtons({ jobId, initial, onRated }: { jobId: string; initial?: "up" | "down" | null; onRated?: (r: "up" | "down") => void }) {
  const [rating, setRating] = useState(initial ?? null);
  const [busy, setBusy] = useState(false);
  async function rate(r: "up" | "down") {
    setBusy(true);
    try {
      await sendFeedback(jobId, { rating: r });
      setRating(r);
      onRated?.(r);
    } finally {
      setBusy(false);
    }
  }
  return (
    <span className="inline-flex gap-1" role="group" aria-label="Teach Saige">
      <Button size="sm" variant={rating === "up" ? "default" : "outline"} disabled={busy} onClick={() => void rate("up")} aria-pressed={rating === "up"} aria-label="Good match for me"><ThumbsUp /></Button>
      <Button size="sm" variant={rating === "down" ? "default" : "outline"} disabled={busy} onClick={() => void rate("down")} aria-pressed={rating === "down"} aria-label="Not for me"><ThumbsDown /></Button>
    </span>
  );
}

const pct = (v: number | null | undefined) => (v == null ? "–" : `${Math.round(v * 100)}%`);

export function LearningView() {
  const st = useApi<MlStatus>("/ml/status");
  const tasks = useApi<{ items: MlTask[] }>("/ml/tasks");
  const [msg, setMsg] = useState<{ tone: "success" | "info" | "error"; text: string } | null>(null);
  const [training, setTraining] = useState(false);
  const [done, setDone] = useState<Set<string>>(new Set());

  async function train() {
    setTraining(true);
    try {
      const r = await request<MlTrainResult>("/ml/train", { method: "POST" });
      setMsg(r.status === "trained"
        ? { tone: "success", text: `Trained version ${r.version} on ${r.samples} rated jobs: ${pct(r.metrics?.accuracy)} accurate on jobs it hadn't seen.` }
        : { tone: "info", text: r.message ?? "Rate a few more jobs first." });
      await Promise.all([st.reload(), tasks.reload()]);
    } catch (e) {
      setMsg({ tone: "error", text: e instanceof Error ? e.message : "Training failed." });
    } finally {
      setTraining(false);
    }
  }

  if (st.loading && !st.data) return <div className="py-16"><Loader3D label="Loading Saige learning" /></div>;
  if (st.error || !st.data) return <Notice tone="error">{st.error ?? "Couldn't load."}</Notice>;
  const s = st.data;
  const rel = s.relevance;
  const left = Math.max(0, rel.retrain_every - rel.labels_since);

  return (
    <div className="space-y-6">
      <Card>
        <CardContent className="flex flex-wrap items-center justify-between gap-4 pt-5">
          <div className="flex items-center gap-3">
            <Brain className="size-6 text-[var(--tone-purple)]" />
            <div>
              <p className="font-semibold">{rel.trained ? `Saige model v${rel.version}` : "Saige hasn't learned your taste yet"}</p>
              <p className="text-sm text-muted-foreground">
                {rel.trained ? `Trained ${rel.trained_at ? timeAgo(rel.trained_at) : ""} on ${rel.samples} rated jobs. Retrains after ${left} more rating(s), and every day.`
                  : `Rate at least ${rel.min_samples} jobs (some you like, some you don't) below or with 👍 / 👎 on any job.`}
              </p>
            </div>
          </div>
          <Button onClick={() => void train()} disabled={training}><Brain /> {training ? "Training…" : "Train now"}</Button>
        </CardContent>
      </Card>
      {msg && <Notice tone={msg.tone}>{msg.text}</Notice>}

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <CountKpi label="Jobs you rated" value={s.labels.total} hint={`${s.labels.liked} liked · ${s.labels.disliked} not for me`} icon={ThumbsUp} tone="green" />
        <CountKpi label="Accuracy" value={rel.metrics ? Math.round(rel.metrics.accuracy * 100) : 0} hint="On jobs it hadn't seen (cross-validated)" icon={Brain} tone="purple" delay={60} />
        <CountKpi label="Ranking quality (AUC)" value={rel.metrics?.auc != null ? Math.round(rel.metrics.auc * 100) : 0} hint="50 is a coin flip, 100 is perfect" icon={Brain} tone="orange" delay={120} />
        <CountKpi label="Job-type corrections" value={s.labels.type_corrections} hint={s.job_type.trained ? "Job-type model trained" : `${s.job_type.min_samples} needed to train`} icon={Brain} tone="teal" delay={180} />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Training tasks</CardTitle>
          <CardDescription>{rel.trained ? "Jobs Saige is least sure about. Each rating teaches it the most." : "A mix of jobs to learn what you like."}</CardDescription>
        </CardHeader>
        <CardContent>
          {tasks.loading && !tasks.data ? <p className="text-sm text-muted-foreground">Loading…</p>
            : (tasks.data?.items ?? []).length === 0 ? <p className="text-sm text-muted-foreground">Nothing to rate. Scan career portals to get more jobs.</p> : (
              <ul className="divide-y">
                {tasks.data!.items.map((t) => (
                  <li key={t.id} className={cn("flex flex-wrap items-center justify-between gap-3 py-3", done.has(t.id) && "opacity-50")}>
                    <div className="min-w-0">
                      <a href={t.url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1.5 text-sm font-medium">{t.title} <ExternalLink className="size-3.5 text-muted-foreground" /></a>
                      <p className="text-xs text-muted-foreground">{t.company}{t.location ? ` · ${t.location}` : ""} · match {t.score}%{t.ai_score != null ? ` · Saige ${t.ai_score}%` : ""}</p>
                    </div>
                    <RateButtons jobId={t.id} onRated={() => { setDone((d) => new Set(d).add(t.id)); void st.reload(); }} />
                  </li>
                ))}
              </ul>
            )}
          <div className="mt-3 flex justify-end"><Button variant="ghost" size="sm" onClick={() => { setDone(new Set()); void tasks.reload(); }}>New tasks</Button></div>
        </CardContent>
      </Card>

      {rel.trained && (
        <div className="grid gap-6 lg:grid-cols-2">
          <Card>
            <CardHeader><CardTitle>What makes you like a job</CardTitle><CardDescription>Strongest signals the model learned from your ratings</CardDescription></CardHeader>
            <CardContent><ul className="space-y-1.5 text-sm">{rel.top_positive.map(([k, v]) => <li key={k} className="flex justify-between gap-3"><span>{k}</span><span className="text-[var(--tone-green)]">+{v.toFixed(2)}</span></li>)}</ul></CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>What makes you skip a job</CardTitle><CardDescription>Signals that push a job down</CardDescription></CardHeader>
            <CardContent><ul className="space-y-1.5 text-sm">{rel.top_negative.map(([k, v]) => <li key={k} className="flex justify-between gap-3"><span>{k}</span><span className="text-[var(--tone-red)]">{v.toFixed(2)}</span></li>)}</ul></CardContent>
          </Card>
        </div>
      )}

      {s.history.length > 0 && (
        <Card>
          <CardHeader><CardTitle>Training history</CardTitle></CardHeader>
          <CardContent>
            <table className="w-full text-sm">
              <thead className="text-left text-xs text-muted-foreground"><tr><th className="py-1.5">When</th><th>Trigger</th><th>Rated jobs</th><th>Version</th><th>Accuracy</th><th>AUC</th></tr></thead>
              <tbody>
                {s.history.map((h) => (
                  <tr key={h.trained_at} className="border-t">
                    <td className="py-1.5">{timeAgo(h.trained_at)}</td><td>{h.trigger}</td><td>{h.samples}</td>
                    <td>{h.status === "trained" ? `v${h.version}` : "needs data"}</td><td>{pct(h.accuracy)}</td><td>{pct(h.auc)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}
      <p className="text-xs text-muted-foreground">Saige learns only from your own ratings, saved jobs and application outcomes (interview or offer counts as a like, rejection as a skip). It changes how jobs are ranked, never what your resume says.</p>
    </div>
  );
}
