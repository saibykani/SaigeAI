"use client";

import { CheckSquare, ExternalLink, Loader2, Radar, Search, Square } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { Notice } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/form";
import { request } from "@/services/api";
import type { DiscoverResponse, DiscoverResult } from "@/types/api";
import { cn } from "@/utils/cn";

const SOURCE_LABEL: Record<string, string> = { adzuna: "Adzuna", remotive: "Remotive", arbeitnow: "Arbeitnow" };

function scoreTone(s: number) {
  return s >= 85 ? "green" : s >= 70 ? "yellow" : s >= 55 ? "orange" : "red";
}

/** Search official job APIs for your target role, pick results, save them and prepare applications in bulk. */
export function JobDiscover({ onSaved }: { onSaved: () => void }) {
  const [query, setQuery] = useState("");
  const [location, setLocation] = useState("");
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [data, setData] = useState<DiscoverResponse | null>(null);
  const [picked, setPicked] = useState<Set<number>>(new Set());
  const [minScore, setMinScore] = useState(0);
  const [msg, setMsg] = useState<{ tone: "success" | "error" | "warning"; text: string } | null>(null);

  const shown = useMemo(() => (data?.results ?? []).map((r, i) => ({ r, i })).filter(({ r }) => r.score >= minScore), [data, minScore]);

  async function search(e?: React.FormEvent) {
    e?.preventDefault();
    setBusy(true);
    setMsg(null);
    try {
      const r = await request<DiscoverResponse>("/jobs/discover", { method: "POST", body: { query: query || null, location: location || null } });
      setData(r);
      setQuery(r.query);
      setLocation(r.location ?? "");
      setPicked(new Set(r.results.map((x, i) => (x.score >= 70 && !x.saved_job_id ? i : -1)).filter((i) => i >= 0)));
      if (Object.keys(r.errors).length) setMsg({ tone: "warning", text: `Some sources were unavailable: ${Object.keys(r.errors).map((k) => SOURCE_LABEL[k] ?? k).join(", ")}.` });
    } catch (err) {
      setMsg({ tone: "error", text: err instanceof Error ? err.message : "Search failed" });
    } finally {
      setBusy(false);
    }
  }

  async function save(prepare: boolean) {
    if (!data) return;
    const items: DiscoverResult[] = [...picked].map((i) => data.results[i]).filter((x) => x && !x.saved_job_id);
    if (!items.length) return;
    setSaving(true);
    setMsg(null);
    try {
      const r = await request<{ saved: number; applications_prepared: number }>("/jobs/discover/save", { method: "POST", body: { items, prepare_applications: prepare } });
      setMsg({ tone: "success", text: prepare ? `Saved ${r.saved} job(s) and prepared ${r.applications_prepared} application(s). Open Applications to review and apply.` : `Saved ${r.saved} job(s) to your list.` });
      onSaved();
      await search();
    } catch (err) {
      setMsg({ tone: "error", text: err instanceof Error ? err.message : "Save failed" });
    } finally {
      setSaving(false);
    }
  }

  const toggle = (i: number) => setPicked((p) => { const n = new Set(p); if (n.has(i)) n.delete(i); else n.add(i); return n; });
  const selectable = shown.filter(({ r }) => !r.saved_job_id);
  const allPicked = selectable.length > 0 && selectable.every(({ i }) => picked.has(i));

  return (
    <Card className="animate-rise mb-6" style={{ borderColor: "color-mix(in srgb, var(--tone-orange) 30%, transparent)", backgroundImage: "radial-gradient(120% 80% at 100% 0%, color-mix(in srgb, var(--tone-orange) 12%, transparent), transparent 60%)" }}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <span className="grid size-8 place-items-center rounded-lg text-[#0b0b0c]" style={{ background: "var(--tone-orange)" }}><Radar className="size-4" /></span>
          Discover jobs for your role
        </CardTitle>
        <CardDescription>
          Searches official job APIs (Adzuna for India, Remotive, Arbeitnow) and scores every result against your verified profile. Nothing is saved until you choose.
          LinkedIn, Naukri and Indeed don&apos;t allow automated searches, so use the Chrome extension on their pages.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <form onSubmit={search} className="flex flex-wrap gap-2">
          <Input className="min-w-[14rem] flex-1" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Role (defaults to your target role), e.g. SDET" />
          <Input className="w-48" value={location} onChange={(e) => setLocation(e.target.value)} placeholder="Location, e.g. Hyderabad" />
          <Button type="submit" disabled={busy}>{busy ? <Loader2 className="animate-spin" /> : <Search />} {busy ? "Searching…" : "Search"}</Button>
        </form>
        {msg && <Notice tone={msg.tone}>{msg.text}</Notice>}
        {data && (
          <>
            <div className="flex flex-wrap items-center gap-3 text-sm">
              <button type="button" onClick={() => setPicked(allPicked ? new Set() : new Set(selectable.map(({ i }) => i)))} className="inline-flex items-center gap-1.5 font-medium">
                {allPicked ? <CheckSquare className="size-4" style={{ color: "var(--tone-orange)" }} /> : <Square className="size-4" />} Select all
              </button>
              <span className="text-muted-foreground">{shown.length} result(s) · {picked.size} selected</span>
              <label className="ml-auto flex items-center gap-2 text-xs text-muted-foreground">
                Min match
                <select value={minScore} onChange={(e) => setMinScore(Number(e.target.value))} className="h-8 rounded-full border bg-transparent px-2">
                  {[0, 55, 70, 85].map((v) => <option key={v} value={v}>{v ? `${v}%+` : "Any"}</option>)}
                </select>
              </label>
              <Button size="sm" variant="outline" disabled={!picked.size || saving} onClick={() => save(false)}>Save selected</Button>
              <Button size="sm" disabled={!picked.size || saving} onClick={() => save(true)}>{saving ? "Working…" : "Save & prepare applications"}</Button>
            </div>
            {!data.providers.includes("adzuna") && (
              <p className="text-xs text-muted-foreground">Tip: add a free Adzuna key (ADZUNA_APP_ID / ADZUNA_APP_KEY in the backend settings) for India-wide results.</p>
            )}
            <ul className="flex max-h-[34rem] flex-col gap-2 overflow-y-auto pr-1">
              {shown.length === 0 && <li className="py-8 text-center text-sm text-muted-foreground">No results. Try a broader role or remove the location.</li>}
              {shown.map(({ r, i }) => (
                <li key={`${r.source}-${r.source_job_id ?? i}`}>
                  <label className={cn("flex cursor-pointer items-start gap-3 rounded-2xl border p-3 transition-colors hover:bg-muted/40", picked.has(i) && "bg-muted/50")}>
                    <input type="checkbox" className="mt-1.5 size-4 accent-[var(--tone-orange)]" checked={picked.has(i)} disabled={!!r.saved_job_id} onChange={() => toggle(i)} />
                    <span className="grid size-11 shrink-0 place-items-center rounded-xl text-sm font-semibold text-[#0b0b0c]" style={{ background: `var(--tone-${scoreTone(r.score)})` }}>{r.score}</span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-medium">{r.title}</span>
                      <span className="block truncate text-sm text-muted-foreground">{r.company || "Company not listed"} · {r.location || "Location not listed"} · {SOURCE_LABEL[r.source] ?? r.source}{r.posted ? ` · ${r.posted}` : ""}</span>
                      {r.matched_skills.length > 0 && <span className="mt-1 block truncate text-xs" style={{ color: "var(--tone-green)" }}>✓ {r.matched_skills.join(" · ")}</span>}
                    </span>
                    <span className="flex shrink-0 flex-col items-end gap-1 text-xs">
                      {r.saved_job_id ? <Link href={`/jobs/${r.saved_job_id}`} className="font-medium underline">Saved</Link> : null}
                      {r.url && <a href={r.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-muted-foreground hover:text-foreground" onClick={(e) => e.stopPropagation()}>View <ExternalLink className="size-3" /></a>}
                    </span>
                  </label>
                </li>
              ))}
            </ul>
          </>
        )}
      </CardContent>
    </Card>
  );
}
