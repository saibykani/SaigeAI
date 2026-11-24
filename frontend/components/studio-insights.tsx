"use client";

import { ArrowDown, ArrowUp, ShieldCheck, Sparkles, UserSearch, Wand2 } from "lucide-react";
import { useState } from "react";

import { Notice } from "@/components/app-shell";
import { SkillConfirm } from "@/components/skill-confirm";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useApi } from "@/hooks/use-api";
import { request } from "@/services/api";
import type {
  AutoImproveResult, BulletCheck, CoverageChip, RecruiterReview, RecruiterView, ResumeVersionRow, StudioInsightsData, VersionDiff,
} from "@/types/api";
import { cn } from "@/utils/cn";

const SECTION_NAMES: Record<string, string> = {
  summary: "Summary", skills: "Skills", experience: "Experience", projects: "Projects", education: "Education", certifications: "Certifications",
};
const VERDICT_TONE = { shortlist: "var(--tone-green)", maybe: "var(--tone-yellow)", reject: "var(--tone-red)" } as const;

/** Everything that explains and improves one generated resume: before/after, checklist, order, review, auto-improve, bullets, 6-second view, versions. */
export function StudioInsights({ resumeId, data, onChanged }: { resumeId: string; data: StudioInsightsData; onChanged: () => Promise<void> | void }) {
  const [order, setOrder] = useState<string[]>(data.section_order ?? []);
  const [review, setReview] = useState<RecruiterReview | null>(null);
  const [improve, setImprove] = useState<AutoImproveResult | null>(null);
  const [view, setView] = useState<RecruiterView | null>(null);
  const [bullets, setBullets] = useState<{ items: (BulletCheck & { text: string })[]; weak: number; total: number; score: number | null } | null>(null);
  const [cover, setCover] = useState<{ chips: CoverageChip[]; covered: number; total: number } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [metric, setMetric] = useState<Record<number, string>>({});
  const [fixed, setFixed] = useState<Record<number, string>>({});
  const versions = useApi<{ items: ResumeVersionRow[] }>("/studio/versions");
  const [cmp, setCmp] = useState<string[]>([]);
  const [diff, setDiff] = useState<VersionDiff | null>(null);
  const ba = data.before_after;

  async function run<T>(key: string, fn: () => Promise<T>, set: (v: T) => void) {
    setBusy(key);
    setErr(null);
    try { set(await fn()); } catch (e) { setErr(e instanceof Error ? e.message : "Something went wrong."); } finally { setBusy(null); }
  }
  const base = `/studio/resumes/${resumeId}`;

  async function move(i: number, d: -1 | 1) {
    const next = [...order];
    const j = i + d;
    if (j < 0 || j >= next.length) return;
    [next[i], next[j]] = [next[j], next[i]];
    setOrder(next);
    await request(`${base}/order`, { method: "POST", body: { order: next } });
    await onChanged();
  }

  async function fixBullet(i: number, text: string) {
    const r = await request<BulletCheck>("/studio/bullets/check", { method: "POST", body: { text, metric: metric[i] || undefined } });
    setFixed((f) => ({ ...f, [i]: r.rewrite ?? text }));
  }

  return (
    <div className="space-y-6">
      {err && <Notice tone="error">{err}</Notice>}

      {ba && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><Sparkles className="size-4" /> ATS score before and after</CardTitle>
            <CardDescription>
              {ba.before == null ? "No base resume to compare with." : `${ba.before} → ${ba.after} (${(ba.delta ?? 0) >= 0 ? "+" : ""}${ba.delta}) compared with the resume you'd send without tailoring.`}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="space-y-1.5 text-sm">
              {ba.items.map((it, i) => (
                <li key={i} className="flex gap-2"><Badge variant={it.kind === "warning" ? "warning" : it.kind === "keywords" ? "success" : "muted"}>{it.kind}</Badge><span>{it.text}</span></li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {(data.skill_checklist ?? []).length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Missing, but true?</CardTitle>
            <CardDescription>The JD asks for these and your verified profile doesn&apos;t have them. Nothing is added unless you tick it.</CardDescription>
          </CardHeader>
          <CardContent>
            <SkillConfirm required={data.skill_checklist!.filter((s) => s.kind === "required").map((s) => s.skill)}
              preferred={data.skill_checklist!.filter((s) => s.kind === "preferred").map((s) => s.skill)} onConfirmed={onChanged} />
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Improve this resume</CardTitle>
          <CardDescription>Safe fixes only: Saige never adds a skill or number you haven&apos;t verified.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" disabled={!!busy} onClick={() => void run("improve", () => request<AutoImproveResult>(`${base}/auto-improve`, { method: "POST" }), (r) => { setImprove(r); void onChanged(); })}>
              <Wand2 /> {busy === "improve" ? "Improving…" : "Auto-improve (up to 3 rounds)"}
            </Button>
            <Button variant="outline" disabled={!!busy} onClick={() => void run("review", () => request<RecruiterReview>(`${base}/review`), setReview)}>
              <UserSearch /> {busy === "review" ? "Reviewing…" : "Recruiter review"}
            </Button>
            <Button variant="outline" disabled={!!busy} onClick={() => void run("view", () => request<RecruiterView>(`${base}/recruiter-view`), setView)}>6-second view</Button>
            <Button variant="outline" disabled={!!busy} onClick={() => void run("bullets", () => request<NonNullable<typeof bullets>>(`${base}/bullets`), setBullets)}>Check bullets</Button>
            <Button variant="outline" disabled={!!busy} onClick={() => void run("cover", () => request<NonNullable<typeof cover>>(`${base}/coverage`), setCover)}>Keyword coverage</Button>
          </div>

          {improve && (
            <div className="rounded-2xl border p-3 text-sm">
              <p className="font-medium">{improve.before} → {improve.after}{improve.saved ? " (saved as a new version)" : ""}</p>
              <p className={cn("mt-1", improve.reached_100 ? "text-[var(--tone-green)]" : "text-muted-foreground")}>{improve.message}</p>
              <ul className="mt-2 list-disc space-y-0.5 pl-5 text-muted-foreground">{improve.applied.map((a) => <li key={a}>{a}</li>)}</ul>
              <p className="mt-2 text-xs text-muted-foreground">Rounds: {improve.rounds.map((r) => `#${r.round} → ${r.score}`).join(" · ")}</p>
              {!improve.reached_100 && improve.blockers.missing_skills.length > 0 && (
                <div className="mt-3 space-y-2">
                  <p className="text-xs font-medium">Missing from your profile: {improve.blockers.missing_skills.map((m) => m.skill).join(", ")}
                    {improve.score_if_confirmed != null ? `. If you really have them, the score would be ${improve.score_if_confirmed}.` : ""}</p>
                  <SkillConfirm required={improve.blockers.missing_skills.filter((m) => m.kind === "required").map((m) => m.skill)}
                    preferred={improve.blockers.missing_skills.filter((m) => m.kind === "preferred").map((m) => m.skill)} onConfirmed={onChanged} />
                </div>
              )}
              {improve.blockers.failed_checks.length > 0 && <p className="mt-2 text-xs text-muted-foreground">Needs your data: {improve.blockers.failed_checks.join(", ")}.</p>}
            </div>
          )}

          {review && (
            <div className="rounded-2xl border p-3 text-sm">
              <p className="flex items-center gap-2 font-semibold"><ShieldCheck className="size-4" style={{ color: VERDICT_TONE[review.verdict] }} />
                Recruiter verdict: <span style={{ color: VERDICT_TONE[review.verdict] }}>{review.verdict}</span> · {review.score}/100</p>
              {review.note && <p className="mt-1 text-muted-foreground">{review.note}</p>}
              <p className="mt-2 text-xs font-medium">Top fixes, ranked by impact</p>
              <ol className="list-decimal space-y-1 pl-5">{review.top_fixes.map((f) => <li key={f.fix}>{f.fix} <span className="text-xs text-muted-foreground">(+{f.points}) {f.how}</span></li>)}</ol>
              {review.rewrites.length > 0 && (
                <div className="mt-2 space-y-2">
                  <p className="text-xs font-medium">Rewritten from your own words</p>
                  {review.rewrites.map((r, i) => (
                    <div key={i} className="rounded-xl bg-muted/40 p-2 text-xs"><p className="text-muted-foreground line-through">{r.original}</p><p>{r.rewrite}</p>{r.ask && <p className="text-[var(--tone-yellow)]">{r.ask.prompt}</p>}</div>
                  ))}
                </div>
              )}
            </div>
          )}

          {view && (
            <div className="rounded-2xl border p-3 text-sm">
              <p className="font-medium">What a recruiter sees first</p>
              <p className="text-muted-foreground">{view.seen_first.latest_role ?? "—"} · {view.seen_first.top_skills.slice(0, 5).join(", ")}</p>
              <p className="mt-1 text-xs">Top third: {view.top_third_sections.join(", ")} · must-haves visible there: {view.top_third_coverage ?? "–"}%</p>
              <p className={cn("text-xs", view.one_page.fits ? "text-[var(--tone-green)]" : "text-[var(--tone-yellow)]")}>
                {view.one_page.fits ? `Fits one page (~${view.one_page.estimated_lines} lines)` : view.one_page.hint}
              </p>
              <div className="mt-2 overflow-x-auto">
                <table className="w-full text-xs">
                  <thead><tr className="text-left text-muted-foreground"><th className="py-1 pr-2">Must-have</th>{["summary", "skills", "experience", "projects"].map((s) => <th key={s} className="px-2">{SECTION_NAMES[s]}</th>)}</tr></thead>
                  <tbody>
                    {view.heatmap.map((h) => (
                      <tr key={h.keyword}>
                        <td className="py-0.5 pr-2">{h.keyword}{h.in_top_third ? " ✓" : ""}</td>
                        {(["summary", "skills", "experience", "projects"] as const).map((s) => (
                          <td key={s} className="px-2 text-center" style={{ background: `color-mix(in srgb, var(--tone-green) ${Math.min(80, h.counts[s] * 25)}%, transparent)` }}>{h.counts[s] || ""}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {bullets && (
            <div className="rounded-2xl border p-3 text-sm">
              <p className="font-medium">{bullets.weak} of {bullets.total} bullets need work{bullets.score != null ? ` · strength ${bullets.score}/100` : ""}</p>
              <ul className="mt-2 space-y-2">
                {bullets.items.map((b, i) => b.flags.length > 0 && (
                  <li key={i} className="rounded-xl bg-muted/40 p-2 text-xs">
                    <p>{b.text}</p>
                    <p className="text-muted-foreground">{b.flags.map((f) => f.message).join(" ")}</p>
                    {b.ask && (
                      <div className="mt-1 flex flex-wrap items-center gap-2">
                        <input className="h-8 rounded-lg border bg-transparent px-2" placeholder="Your real result, e.g. cut test time by 30%" value={metric[i] ?? ""}
                          onChange={(e) => setMetric((m) => ({ ...m, [i]: e.target.value }))} aria-label="Real result for this bullet" />
                        <Button size="sm" variant="outline" onClick={() => void fixBullet(i, b.text)}>Rewrite</Button>
                      </div>
                    )}
                    {!b.ask && b.rewrite && <Button size="sm" variant="ghost" onClick={() => void fixBullet(i, b.text)}>Show rewrite</Button>}
                    {fixed[i] && <p className="mt-1 font-medium">{fixed[i]}</p>}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {cover && (
            <div className="rounded-2xl border p-3 text-sm">
              <p className="font-medium">{cover.covered} of {cover.total} JD keywords on the resume</p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {cover.chips.map((c) => (
                  <span key={c.keyword} className="inline-flex items-center gap-1">
                    <Badge variant={c.state === "on_resume" ? "success" : c.state === "can_add" ? "warning" : "muted"}>{c.keyword}{c.required ? "" : " · nice"}</Badge>
                    {c.state === "can_add" && (
                      <Button size="sm" variant="ghost" onClick={() => void run("add", () => request(`${base}/add-skill`, { method: "POST", body: { skill: c.keyword } }),
                        async () => { setCover((v) => v && { ...v, covered: v.covered + 1, chips: v.chips.map((x) => (x.keyword === c.keyword ? { ...x, state: "on_resume" } : x)) }); await onChanged(); })}>Add</Button>
                    )}
                  </span>
                ))}
              </div>
              <p className="mt-2 text-xs text-muted-foreground">&quot;Add&quot; appears only for skills already in your verified profile. Grey chips need your confirmation in the checklist above.</p>
            </div>
          )}
        </CardContent>
      </Card>

      {order.length > 0 && (
        <Card>
          <CardHeader><CardTitle>Section order</CardTitle><CardDescription>Used for the preview and every download (PDF, Word, text).</CardDescription></CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            {order.map((s, i) => (
              <span key={s} className="inline-flex items-center gap-1 rounded-full border px-3 py-1 text-sm">
                {SECTION_NAMES[s] ?? s}
                <button type="button" aria-label={`Move ${s} up`} disabled={i === 0} onClick={() => void move(i, -1)}><ArrowUp className="size-3.5" /></button>
                <button type="button" aria-label={`Move ${s} down`} disabled={i === order.length - 1} onClick={() => void move(i, 1)}><ArrowDown className="size-3.5" /></button>
              </span>
            ))}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader><CardTitle>Resume versions</CardTitle><CardDescription>Every resume generated, with the replies and interviews each one got. Pick two to compare.</CardDescription></CardHeader>
        <CardContent className="space-y-3">
          {(versions.data?.items ?? []).length === 0 ? <p className="text-sm text-muted-foreground">No versions yet.</p> : (
            <ul className="divide-y text-sm">
              {versions.data!.items.map((v) => (
                <li key={v.id} className="flex flex-wrap items-center gap-3 py-2">
                  <input type="checkbox" aria-label={`Compare ${v.name}`} checked={cmp.includes(v.id)} onChange={() => setCmp((c) => (c.includes(v.id) ? c.filter((x) => x !== v.id) : [...c, v.id].slice(-2)))} />
                  <span className="min-w-0 flex-1 truncate">{v.name}</span>
                  <span className="text-xs text-muted-foreground">ATS {v.ats_score ?? "–"} · sent {v.sent} · replies {v.replies}{v.reply_rate != null ? ` (${v.reply_rate}%)` : ""} · interviews {v.interviews}</span>
                </li>
              ))}
            </ul>
          )}
          <Button size="sm" variant="outline" disabled={cmp.length !== 2 || !!busy}
            onClick={() => void run("diff", () => request<VersionDiff>(`/studio/versions/compare?a=${cmp[0]}&b=${cmp[1]}`), setDiff)}>Compare selected</Button>
          {diff && (
            <div className="grid gap-3 text-xs sm:grid-cols-2">
              <div className="rounded-xl border p-2"><p className="font-medium">Only in B</p>
                {[...diff.diff.skills_added.map((s) => `Skill: ${s}`), ...diff.diff.bullets_added].map((x) => <p key={x} className="text-[var(--tone-green)]">+ {x}</p>)}</div>
              <div className="rounded-xl border p-2"><p className="font-medium">Only in A</p>
                {[...diff.diff.skills_removed.map((s) => `Skill: ${s}`), ...diff.diff.bullets_removed].map((x) => <p key={x} className="text-[var(--tone-red)]">− {x}</p>)}</div>
              {diff.diff.summary.changed && <p className="sm:col-span-2 text-muted-foreground">Summary differs between the two.</p>}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
