"use client";

import { CheckCircle2, ExternalLink, RefreshCw } from "lucide-react";
import { useState } from "react";

import { Notice, PageHeader } from "@/components/app-shell";
import { ProgressRing } from "@/components/motion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/form";
import { useApi } from "@/hooks/use-api";
import { request } from "@/services/api";

type Resource = { id: string; title: string; url: string; provider: string; kind: string; hours: number; done: boolean };
type Skill = {
  key: string; name: string; score: number; jobs: number; from_roles: boolean; hours: number;
  status: "todo" | "in_progress" | "done"; progress: number; confirmed: boolean; resources: Resource[];
};
type Path = {
  skills: Skill[]; hours_per_week: number;
  plan: { week: number; start: string; items: { key: string; skill: string; hours: number }[] }[];
  summary: { total: number; in_progress: number; done: number; hours_left: number };
};

const STATUS: Record<Skill["status"], string> = { todo: "To do", in_progress: "In progress", done: "Done" };
const TONE: Record<Skill["status"], string> = { todo: "stroke-[var(--tone-orange)]", in_progress: "stroke-[var(--tone-yellow)]", done: "stroke-[var(--tone-green)]" };

export default function LearningPage() {
  const { data, setData, loading, error } = useApi<Path>("/learning");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [sure, setSure] = useState<Record<string, boolean>>({});
  const [ok, setOk] = useState<string | null>(null);

  async function call(path: string, method: "POST" | "PUT", body?: unknown) {
    setBusy(true);
    setErr(null);
    try { setData(await request<Path>(path, { method, body })); } catch (e) { setErr(e instanceof Error ? e.message : "Failed."); } finally { setBusy(false); }
  }

  async function confirm(s: Skill) {
    setBusy(true);
    setErr(null);
    try {
      await request(`/learning/skills/${encodeURIComponent(s.key)}/confirm`, { method: "POST", body: { name: s.name, confirmed: true } });
      setOk(`${s.name} added to your profile.`);
      setData(await request<Path>("/learning"));
    } catch (e) { setErr(e instanceof Error ? e.message : "Failed."); } finally { setBusy(false); }
  }

  return (
    <>
      <PageHeader title="Learning path" description="Skills your target roles and strong-match jobs ask for that your profile doesn't have yet, ranked by demand, with free resources and a weekly plan."
        actions={<Button variant="outline" disabled={busy} onClick={() => void call("/learning/refresh", "POST")}><RefreshCw className="size-4" /> Refresh</Button>} />
      {(err || error) && <Notice tone="error">{err || error}</Notice>}
      {ok && <Notice tone="success">{ok}</Notice>}
      {loading && !data && <p className="text-sm text-muted-foreground">Loading…</p>}
      {data && (
        <>
          <div className="mb-6 grid gap-4 sm:grid-cols-4">
            {[["Skills to learn", data.summary.total, "--tone-orange"], ["In progress", data.summary.in_progress, "--tone-yellow"],
              ["Done", data.summary.done, "--tone-green"], ["Hours left", data.summary.hours_left, "--tone-purple"]].map(([label, v, tone]) => (
              <Card key={label as string}><CardContent className="pt-6">
                <p className="text-xs text-muted-foreground">{label}</p>
                <p className="text-3xl font-semibold" style={{ color: `var(${tone})` }}>{v}</p>
              </CardContent></Card>
            ))}
          </div>
          {!data.skills.length && <Notice>No gaps found. Save a few jobs or set target roles in your Profile, then refresh.</Notice>}
          <div className="grid gap-4 lg:grid-cols-2">
            {data.skills.map((s) => (
              <Card key={s.key} className="lift">
                <CardHeader className="flex flex-row items-center gap-4">
                  <ProgressRing value={s.progress} size={64} stroke={7} trackClass="stroke-muted" barClass={TONE[s.status]}>
                    <span className="text-sm font-semibold">{s.progress}%</span>
                  </ProgressRing>
                  <div className="min-w-0 flex-1">
                    <CardTitle className="flex flex-wrap items-center gap-2 text-lg">{s.name} <Badge>{STATUS[s.status]}</Badge></CardTitle>
                    <CardDescription>{s.jobs ? `In ${s.jobs} matching job${s.jobs > 1 ? "s" : ""}` : "Common for your target roles"} · about {s.hours} h</CardDescription>
                  </div>
                </CardHeader>
                <CardContent className="space-y-3 text-sm">
                  <ul className="space-y-1.5">
                    {s.resources.map((r) => (
                      <li key={r.id} className="flex items-center gap-2">
                        <input type="checkbox" aria-label={`Done: ${r.title}`} checked={r.done} disabled={busy}
                          onChange={(e) => void call("/learning/resources", "PUT", { skill: s.key, resource_id: r.id, done: e.target.checked, name: s.name })} />
                        <a href={r.url} target="_blank" rel="noreferrer" className="flex-1 truncate underline-offset-2 hover:underline">{r.title}</a>
                        <span className="shrink-0 text-xs text-muted-foreground">{r.provider} · {r.hours} h</span>
                        <ExternalLink className="size-3 shrink-0 text-muted-foreground" />
                      </li>
                    ))}
                  </ul>
                  <div className="flex flex-wrap gap-2">
                    {(["todo", "in_progress", "done"] as const).map((st) => (
                      <Button key={st} size="sm" variant={s.status === st ? "default" : "outline"} disabled={busy}
                        onClick={() => void call(`/learning/skills/${encodeURIComponent(s.key)}`, "PUT", { status: st, name: s.name })}>{STATUS[st]}</Button>
                    ))}
                  </div>
                  {s.status === "done" && !s.confirmed && (
                    <div className="space-y-2 rounded-xl border p-3">
                      <label className="flex items-start gap-2 text-xs">
                        <input type="checkbox" checked={!!sure[s.key]} onChange={(e) => setSure((m) => ({ ...m, [s.key]: e.target.checked }))} />
                        I have really learned or used {s.name}. Add it to my verified profile.
                      </label>
                      <Button size="sm" disabled={busy || !sure[s.key]} onClick={() => void confirm(s)}><CheckCircle2 className="size-4" /> Add to profile</Button>
                    </div>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
          {data.plan.length > 0 && (
            <Card className="mt-6">
              <CardHeader className="flex flex-row items-center justify-between gap-4">
                <div><CardTitle className="text-lg">Weekly plan</CardTitle><CardDescription>Based on your hours per week.</CardDescription></div>
                <label className="flex items-center gap-2 text-sm">Hours / week
                  <Input type="number" min={1} max={40} className="w-20" defaultValue={data.hours_per_week}
                    onBlur={(e) => { const v = Number(e.target.value); if (v >= 1 && v <= 40 && v !== data.hours_per_week) void call("/learning/settings", "PUT", { hours_per_week: v }); }} />
                </label>
              </CardHeader>
              <CardContent>
                <ol className="relative space-y-4 border-l pl-5">
                  {data.plan.map((w) => (
                    <li key={w.week}>
                      <span className="absolute -left-1.5 mt-1.5 size-3 rounded-full bg-[var(--tone-orange)]" />
                      <p className="text-sm font-medium">Week {w.week} <span className="text-muted-foreground">· from {w.start}</span></p>
                      <p className="text-sm text-muted-foreground">{w.items.map((i) => `${i.skill} (${i.hours} h)`).join(" · ")}</p>
                    </li>
                  ))}
                </ol>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </>
  );
}
