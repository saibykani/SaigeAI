"use client";

import { ExternalLink, Pencil, Plus, X } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Notice } from "@/components/app-shell";
import { ProgressRing } from "@/components/motion";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/form";
import { useApi } from "@/hooks/use-api";
import { request } from "@/services/api";
import { cn } from "@/utils/cn";

type Goal = { key: string; label: string; target: number; done: number; pct: number };
type Goals = { week_of: string; goals: Goal[] };
type Ghost = { id: string; title: string; company: string; status: string; silent_days: number; link: string; suggestion: string };
type SLink = { label: string; url: string };
type Salary = {
  role: string; currency: string; expected_ctc: number | null; current_ctc: number | null; verdict: string | null;
  overall: { min: number; median: number; max: number; postings: number } | null;
  companies: { company: string; min: number; max: number; median: number; postings: number; links: SLink[] }[];
  research: { company: string; links: SLink[] }[];
};
type Roles = { picked: string[]; related: string[]; from_companies: string[]; hide_words: string[]; hidden_now: string[] };

const card = "rounded-3xl border bg-card p-5";

/** Weekly goals with progress rings (counted from what you actually did this week). */
export function GoalsCard({ compact = false }: { compact?: boolean }) {
  const { data, setData } = useApi<Goals>("/growth/goals");
  const [edit, setEdit] = useState<Record<string, string> | null>(null);
  async function save() {
    if (!edit) return;
    const body = Object.fromEntries(Object.entries(edit).map(([k, v]) => [k, Math.max(0, Number(v) || 0)]));
    setData(await request<Goals>("/growth/goals", { method: "PUT", body }));
    setEdit(null);
  }
  return (
    <section className={card}>
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h2 className="text-xl">Weekly goals</h2>
          <p className="text-sm text-muted-foreground">Week of {data?.week_of ?? "…"}. Progress updates as you work.</p>
        </div>
        {!compact && !edit && data && (
          <Button variant="outline" size="sm" onClick={() => setEdit(Object.fromEntries(data.goals.map((g) => [g.key, String(g.target)])))}><Pencil /> Set goals</Button>
        )}
      </div>
      {edit ? (
        <div className="grid gap-4 sm:grid-cols-2">
          {data?.goals.map((g) => (
            <Field key={g.key} label={`${g.label} per week`}>
              <Input type="number" min={0} value={edit[g.key]} onChange={(e) => setEdit({ ...edit, [g.key]: e.target.value })} />
            </Field>
          ))}
          <div className="flex gap-2 sm:col-span-2"><Button onClick={() => void save()}>Save goals</Button><Button variant="ghost" onClick={() => setEdit(null)}>Cancel</Button></div>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          {data?.goals.map((g) => (
            <div key={g.key} className="flex flex-col items-center text-center">
              <ProgressRing value={g.pct} size={compact ? 76 : 96} stroke={8} trackClass="stroke-muted" barClass="stroke-[var(--primary)]">
                <span className="text-lg font-semibold">{g.done}<span className="text-xs font-normal text-muted-foreground">/{g.target}</span></span>
              </ProgressRing>
              <p className="mt-2 text-sm">{g.label}</p>
            </div>
          ))}
        </div>
      )}
      {compact && <Link href="/goals" className="mt-4 block text-sm text-primary">Set your goals →</Link>}
    </section>
  );
}

/** Applications with no reply for 10+ days, with the next step. */
export function GhostingList({ limit }: { limit?: number }) {
  const { data } = useApi<Ghost[]>("/growth/ghosting");
  const rows = limit ? data?.slice(0, limit) : data;
  return (
    <section className={card}>
      <h2 className="text-xl">No reply for 10+ days</h2>
      <p className="mb-3 text-sm text-muted-foreground">A short, polite follow-up often gets a reply. Saige reminds you every Monday and Thursday.</p>
      {data?.length === 0 && <p className="py-6 text-center text-sm text-muted-foreground">No silent applications. Nice.</p>}
      <ul className="divide-y">
        {rows?.map((g) => (
          <li key={g.id} className="flex flex-wrap items-center gap-3 py-3">
            <span className="grid size-10 place-items-center rounded-xl bg-accent font-medium text-primary">{(g.company || g.title).charAt(0)}</span>
            <div className="min-w-0 flex-1">
              <p className="truncate">{g.title}{g.company ? ` · ${g.company}` : ""}</p>
              <p className="text-sm text-muted-foreground">Silent for {g.silent_days} days · {g.suggestion}</p>
            </div>
            <Link href={g.link}><Button size="sm" variant="outline">Draft follow-up</Button></Link>
          </li>
        ))}
      </ul>
      {limit && data && data.length > limit && <Link href="/followups" className="mt-2 block text-sm text-primary">See all {data.length} →</Link>}
    </section>
  );
}

/** Salary ranges from postings that list pay, vs your expected CTC, with AmbitionBox / Glassdoor research links. */
export function SalaryInsights() {
  const [role, setRole] = useState("");
  const [q, setQ] = useState("");
  const { data, loading } = useApi<Salary>(`/growth/salary${q ? `?role=${encodeURIComponent(q)}` : ""}`);
  const o = data?.overall;
  const pos = (v: number) => (o && o.max > o.min ? Math.min(100, Math.max(0, ((v - o.min) / (o.max - o.min)) * 100)) : 50);
  return (
    <div className="space-y-6">
      <form className="flex flex-wrap items-end gap-3" onSubmit={(e) => { e.preventDefault(); setQ(role.trim()); }}>
        <Field label="Role" className="min-w-64 flex-1"><Input value={role} onChange={(e) => setRole(e.target.value)} placeholder={data?.role || "e.g. SDET"} /></Field>
        <Button type="submit">Show salaries</Button>
      </form>
      {loading && !data && <div className="skeleton h-40 rounded-3xl" />}
      {data && !o && <Notice tone="info">No postings for “{data.role}” list a salary yet. Scan Career portals for more, or use the AmbitionBox / Glassdoor links below.</Notice>}
      {o && (
        <section className={card}>
          <p className="text-sm text-muted-foreground">{data.role} · {o.postings} postings with a listed salary · {data.currency}</p>
          <div className="mt-3 grid grid-cols-3 gap-4 text-center">
            {([["Lowest", o.min], ["Median", o.median], ["Highest", o.max]] as const).map(([l, v]) => (
              <div key={l}><p className="text-4xl font-light text-primary">{v}</p><p className="text-sm text-muted-foreground">{l} (LPA)</p></div>
            ))}
          </div>
          {data.expected_ctc != null && (
            <div className="mt-6">
              <div className="relative h-2 rounded-full bg-muted">
                <span className="absolute -top-1.5 size-5 -translate-x-1/2 rounded-full border-4 border-card bg-primary" style={{ left: `${pos(data.expected_ctc)}%` }} />
              </div>
              <p className="mt-3 text-sm">Your expected CTC <b>{data.expected_ctc} LPA</b> is <b>{data.verdict}</b>.{data.current_ctc ? ` Current: ${data.current_ctc} LPA.` : ""}</p>
            </div>
          )}
        </section>
      )}
      {data && data.companies.length > 0 && (
        <section className={card}>
          <h2 className="mb-3 text-xl">By company</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-xs text-muted-foreground"><tr><th className="py-2 font-normal">Company</th><th className="font-normal">Range (LPA)</th><th className="font-normal">Median</th><th className="font-normal">Postings</th><th className="font-normal">Research</th></tr></thead>
              <tbody className="divide-y">
                {data.companies.map((co) => (
                  <tr key={co.company}>
                    <td className="py-2.5">{co.company}</td><td>{co.min}–{co.max}</td><td className="text-primary">{co.median}</td><td>{co.postings}</td>
                    <td className="space-x-3">{co.links.map((l) => <a key={l.label} href={l.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-primary hover:underline">{l.label}<ExternalLink className="size-3" /></a>)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
      {data && data.research.length > 0 && (
        <section className={card}>
          <h2 className="text-xl">Check pay at companies you track</h2>
          <p className="mb-3 text-sm text-muted-foreground">These postings don&apos;t list pay. Open the company&apos;s salary page on AmbitionBox or Glassdoor (they don&apos;t allow apps to read their data).</p>
          <ul className="grid gap-2 sm:grid-cols-2">
            {data.research.map((r) => (
              <li key={r.company} className="flex items-center justify-between rounded-2xl border px-4 py-2.5 text-sm">
                <span>{r.company}</span>
                <span className="space-x-3">{r.links.map((l) => <a key={l.label} href={l.url} target="_blank" rel="noreferrer" className="text-primary hover:underline">{l.label}</a>)}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

/** Pick several target roles, with related roles and the titles companies actually use; hide unwanted titles (e.g. manual testing). */
export function RolePicker({ value, onChange, hidden, onHiddenChange }: {
  value: string[]; onChange: (v: string[]) => void; hidden: string[]; onHiddenChange: (v: string[]) => void;
}) {
  const [typed, setTyped] = useState("");
  const { data } = useApi<Roles>(`/growth/roles?q=${encodeURIComponent(value.join(","))}`);
  const add = (r: string) => { const v = r.trim(); if (v && !value.some((x) => x.toLowerCase() === v.toLowerCase())) onChange([...value, v]); };
  const chip = "inline-flex items-center gap-1 rounded-full border px-3 py-1 text-sm";
  const suggestions = [...(data?.related ?? []), ...(data?.from_companies ?? [])].filter((r, i, a) => a.indexOf(r) === i && !value.some((x) => x.toLowerCase() === r.toLowerCase()));
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        {value.map((r) => (
          <span key={r} className={cn(chip, "border-primary bg-primary text-primary-foreground")}>
            {r}<button type="button" aria-label={`Remove ${r}`} onClick={() => onChange(value.filter((x) => x !== r))}><X className="size-3.5" /></button>
          </span>
        ))}
        <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); add(typed); setTyped(""); }}>
          <Input className="h-9 w-56" value={typed} onChange={(e) => setTyped(e.target.value)} placeholder="Add a role, e.g. SDET" />
          <Button type="submit" size="sm" variant="outline"><Plus /> Add</Button>
        </form>
      </div>
      {suggestions.length > 0 && (
        <div>
          <p className="mb-1.5 text-xs text-muted-foreground">Suggested for you (related roles and titles companies use)</p>
          <div className="flex flex-wrap gap-2">
            {suggestions.slice(0, 14).map((r) => <button key={r} type="button" onClick={() => add(r)} className={cn(chip, "hover:bg-muted")}><Plus className="size-3.5 text-primary" /> {r}</button>)}
          </div>
        </div>
      )}
      {(data?.hide_words ?? []).map((w) => (
        <label key={w} className="flex items-center gap-2 text-sm">
          <input type="checkbox" className="size-4 accent-[var(--primary)]" checked={hidden.includes(w)}
            onChange={(e) => onHiddenChange(e.target.checked ? [...hidden, w] : hidden.filter((x) => x !== w))} />
          Hide jobs with “{w}” in the title (e.g. {w} testing roles)
        </label>
      ))}
    </div>
  );
}
