"use client";

import { BarChart3, Check, Pencil, Plus, Table2, Trash2, Wand2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { Notice } from "@/components/app-shell";
import { useT } from "@/components/i18n";
import type { OfferInput } from "@/components/offers";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea } from "@/components/ui/form";
import { useApi } from "@/hooks/use-api";
import { request } from "@/services/api";
import type { Application, OfferDecision, OfferFactor, OfferMeta } from "@/types/api";
import { cn } from "@/utils/cn";

type Saved = { id: string; input: OfferInput; meta: Partial<OfferMeta>; ctc: number; monthly_in_hand: number };

const EMPTY_META: OfferMeta = {
  location: "", commute_minutes: 0, wfh_days: 0, notice_days: 0, buyout_amount: 0, benefits: [], health_cover: 0, learning_budget: 0, growth_notes: "",
  esop_grant_value: 0, esop_vesting_years: 4, esop_cliff_months: 12, growth_rating: null, learning_rating: null, user_rating: null, application_id: null,
};
const FACTOR_LABELS: Record<OfferFactor, string> = {
  money: "Money (4-year total)", growth: "Growth", work_life: "Work-life (WFH days)", commute: "Commute time", learning: "Learning", user_set: "My gut feeling",
};
const FACTORS = Object.keys(FACTOR_LABELS) as OfferFactor[];
const DEFAULT_WEIGHTS: Record<OfferFactor, number> = { money: 40, growth: 20, work_life: 15, commute: 10, learning: 10, user_set: 5 };
const rs = (n: number) => `₹${Math.round(n).toLocaleString("en-IN")}`;
const lakh = (n: number) => `₹${(n / 100000).toFixed(1)} L`;

function Num({ label, value, onChange, max, hint }: { label: string; value: number; onChange: (n: number) => void; max?: number; hint?: string }) {
  const { t } = useT();
  return (
    <Field label={t(label)} hint={hint ? t(hint) : undefined}>
      <Input type="number" min={0} max={max} value={value || ""} placeholder="0" onChange={(e) => onChange(Math.min(max ?? 1e10, Math.max(0, Number(e.target.value) || 0)))} />
    </Field>
  );
}

function Rating({ label, value, onChange }: { label: string; value: number | null; onChange: (n: number | null) => void }) {
  const { t } = useT();
  return (
    <Field label={t(label)} hint={t("0 to 10. Leave blank if unsure.")}>
      <Input type="number" min={0} max={10} value={value ?? ""} placeholder="–" onChange={(e) => onChange(e.target.value === "" ? null : Math.min(10, Math.max(0, Math.round(Number(e.target.value) || 0))))} />
    </Field>
  );
}

function OfferForm({ editing, apps, onDone }: { editing: Saved | null; apps: Application[]; onDone: () => void }) {
  const { t } = useT();
  const [name, setName] = useState(editing?.input.name ?? "");
  const [company, setCompany] = useState(editing?.input.company ?? "");
  const [ctc, setCtc] = useState(0);
  const [varPct, setVarPct] = useState(0);
  const [meta, setMeta] = useState<OfferMeta>({ ...EMPTY_META, ...(editing?.meta ?? {}) });
  const [benefits, setBenefits] = useState((editing?.meta.benefits ?? []).join(", "));
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (p: Partial<OfferMeta>) => setMeta((m) => ({ ...m, ...p }));

  async function submit() {
    setBusy(true);
    setErr(null);
    try {
      const m = { ...meta, benefits: benefits.split(",").map((b) => b.trim()).filter(Boolean).slice(0, 20) };
      if (editing) {
        await request(`/offers/saved/${editing.id}`, { method: "PUT", body: { input: { ...editing.input, name, company }, meta: m } });
      } else {
        if (!ctc) { setErr(t("Enter the yearly CTC so the in-hand pay can be worked out. You can refine the breakup in the calculator.")); return; }
        const s = await request<Record<string, number | string>>("/offers/split", { method: "POST", body: { ctc, variable_pct: varPct } });
        await request("/offers/saved", { method: "POST", body: { input: { ...s, name, company }, meta: m } });
      }
      onDone();
    } catch (e) {
      setErr(e instanceof Error ? e.message : t("Could not save"));
    } finally {
      setBusy(false);
    }
  }

  const h = "mb-3 mt-5 text-sm font-medium";
  return (
    <section className="rounded-3xl border bg-card p-5">
      <h2 className="mb-3 text-xl">{editing ? t("Edit offer details") : t("Add an offer")}</h2>
      {err && <div className="mb-3"><Notice tone="error">{err}</Notice></div>}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Field label={t("Offer name")}><Input value={name} onChange={(e) => setName(e.target.value)} placeholder={t("Offer")} /></Field>
        <Field label={t("Company")}><Input value={company} onChange={(e) => setCompany(e.target.value)} /></Field>
        {!editing && <Num label="Total CTC per year" value={ctc} onChange={setCtc} />}
        {!editing && <Num label="Variable % of CTC" value={varPct} onChange={setVarPct} max={60} />}
      </div>
      {editing ? <p className="mt-2 text-xs text-muted-foreground">{t("The pay breakup is edited in the Calculator tab (Load, change, Save).")}</p>
        : <p className="mt-2 text-xs text-muted-foreground">{t("Split into a typical structure. Edit any number to match your offer letter.")}</p>}

      <h3 className={h}>{t("Place and time")}</h3>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Field label={t("Location")}><Input value={meta.location} onChange={(e) => set({ location: e.target.value })} /></Field>
        <Num label="Commute one way (minutes)" value={meta.commute_minutes} onChange={(n) => set({ commute_minutes: n })} max={300} />
        <Field label={t("Work-from-home days per week")}><Select value={meta.wfh_days} onChange={(e) => set({ wfh_days: Number(e.target.value) })}>{[0, 1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n}</option>)}</Select></Field>
        <Num label="Notice period (days)" value={meta.notice_days} onChange={(n) => set({ notice_days: n })} max={365} />
        <Num label="Buyout amount" value={meta.buyout_amount} onChange={(n) => set({ buyout_amount: n })} />
      </div>

      <h3 className={h}>{t("Equity (value you enter, never guessed)")}</h3>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Num label="Total ESOP / RSU grant value" value={meta.esop_grant_value} onChange={(n) => set({ esop_grant_value: n })} hint="At the value you believe in. Leave 0 to use the per-year value from the calculator." />
        <Num label="Vesting years" value={meta.esop_vesting_years} onChange={(n) => set({ esop_vesting_years: Math.max(1, n) })} max={8} />
        <Num label="Cliff (months)" value={meta.esop_cliff_months} onChange={(n) => set({ esop_cliff_months: n })} max={48} />
      </div>

      <h3 className={h}>{t("Benefits and growth")}</h3>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Num label="Health cover" value={meta.health_cover} onChange={(n) => set({ health_cover: n })} />
        <Num label="Learning budget per year" value={meta.learning_budget} onChange={(n) => set({ learning_budget: n })} />
        <Field label={t("Other benefits")} hint={t("Comma separated")} className="col-span-2"><Input value={benefits} onChange={(e) => setBenefits(e.target.value)} placeholder={t("Insurance, gym, cab")} /></Field>
        <Rating label="Growth rating" value={meta.growth_rating} onChange={(n) => set({ growth_rating: n })} />
        <Rating label="Learning rating" value={meta.learning_rating} onChange={(n) => set({ learning_rating: n })} />
        <Rating label="My gut feeling" value={meta.user_rating} onChange={(n) => set({ user_rating: n })} />
        <Field label={t("Linked application")}>
          <Select value={meta.application_id ?? ""} onChange={(e) => set({ application_id: e.target.value || null })}>
            <option value="">{t("None")}</option>
            {apps.map((a) => <option key={a.id} value={a.id}>{a.company} · {a.role}</option>)}
          </Select>
        </Field>
        <Field label={t("Growth notes")} className="col-span-2 md:col-span-4"><Textarea rows={2} maxLength={1500} value={meta.growth_notes} onChange={(e) => set({ growth_notes: e.target.value })} /></Field>
      </div>
      <div className="mt-4 flex gap-2">
        <Button onClick={() => void submit()} disabled={busy}><Check />{editing ? t("Save changes") : t("Add offer")}</Button>
        <Button variant="outline" onClick={onDone}>{t("Cancel")}</Button>
      </div>
    </section>
  );
}

function TotalsChart({ d }: { d: OfferDecision }) {
  const { t } = useT();
  const [table, setTable] = useState(false);
  const data = d.offers.map((o) => ({ name: o.name || o.company, y1: o.year1_total, y4: o.total_4y }));
  const y1 = t("Year 1 total"), y4 = t("4-year total");
  return (
    <section className="rounded-3xl border bg-card p-5">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-xl">{t("Year 1 and 4-year totals")}</h2>
        <Button variant="outline" size="sm" onClick={() => setTable(!table)}>{table ? <BarChart3 /> : <Table2 />}{table ? t("Chart view") : t("Table view")}</Button>
      </div>
      <p className="mb-3 text-xs text-muted-foreground">{t("In-hand cash after tax plus vested ESOP at the value you entered. ESOP is not cash until you sell.")}</p>
      {table ? (
        <table className="w-full text-sm">
          <thead><tr className="text-left text-muted-foreground"><th className="py-1.5 font-medium">{t("Offer")}</th><th className="py-1.5 text-right font-medium">{y1}</th><th className="py-1.5 text-right font-medium">{y4}</th></tr></thead>
          <tbody>{data.map((r) => <tr key={r.name} className="border-t"><td className="py-1.5">{r.name}</td><td className="py-1.5 text-right tabular-nums">{rs(r.y1)}</td><td className="py-1.5 text-right tabular-nums">{rs(r.y4)}</td></tr>)}</tbody>
        </table>
      ) : (
        <div className="h-72 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 8, right: 8, bottom: 4, left: 0 }}>
              <CartesianGrid vertical={false} stroke="var(--grid)" />
              <XAxis dataKey="name" tick={{ fontSize: 12, fill: "var(--muted-foreground)" }} axisLine={false} tickLine={false} />
              <YAxis tickFormatter={(v: number) => lakh(v)} width={64} tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} axisLine={false} tickLine={false} />
              <Tooltip cursor={{ fill: "var(--muted)" }} formatter={(v) => rs(Number(v))} contentStyle={{ background: "var(--card-solid)", border: "1px solid var(--border)", borderRadius: 12, fontSize: 12 }} />
              <Legend wrapperStyle={{ fontSize: 12, color: "var(--muted-foreground)" }} />
              <Bar dataKey="y1" name={y1} fill="var(--chart-2)" radius={6} maxBarSize={44} animationDuration={800} />
              <Bar dataKey="y4" name={y4} fill="var(--chart-3)" radius={6} maxBarSize={44} animationDuration={800} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </section>
  );
}

function Weights({ w, setW }: { w: Record<OfferFactor, number>; setW: (w: Record<OfferFactor, number>) => void }) {
  const { t } = useT();
  const total = FACTORS.reduce((a, f) => a + w[f], 0) || 1;
  return (
    <section className="rounded-3xl border bg-card p-5">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-xl">{t("What matters to you")}</h2>
        <Button variant="outline" size="sm" onClick={() => setW(DEFAULT_WEIGHTS)}>{t("Reset")}</Button>
      </div>
      <div className="grid gap-x-8 gap-y-3 md:grid-cols-2">
        {FACTORS.map((f) => (
          <label key={f} className="block text-sm">
            <span className="flex justify-between"><span>{t(FACTOR_LABELS[f])}</span><span className="tabular-nums text-muted-foreground">{Math.round((w[f] / total) * 100)}%</span></span>
            <input type="range" min={0} max={100} step={5} value={w[f]} className="mt-1 w-full accent-[var(--chart-3)]" onChange={(e) => setW({ ...w, [f]: Number(e.target.value) })} />
          </label>
        ))}
      </div>
    </section>
  );
}

function Comparison({ d }: { d: OfferDecision }) {
  const { t } = useT();
  const rows: [string, (o: OfferDecision["offers"][number]) => React.ReactNode, boolean?][] = [
    ["Score (0 to 100)", (o) => o.score.toFixed(1), true],
    ["Yearly CTC", (o) => lakh(o.ctc)],
    ["Monthly in-hand (average)", (o) => rs(o.monthly_in_hand)],
    ["Real monthly cash (fixed pay)", (o) => rs(o.real_monthly_cash)],
    ["Year 1 total", (o) => rs(o.year1_total), true],
    ["4-year total", (o) => rs(o.total_4y), true],
    ["of which ESOP vested (4 years)", (o) => rs(o.esop_4y)],
    ["Commute hours per month", (o) => `${o.commute_hours_month} h`],
    ["Work-from-home days", (o) => o.wfh_days],
    ["Location", (o) => o.location || "–"],
    ["Notice (days)", (o) => o.notice_days || "–"],
    ["Buyout amount", (o) => (o.buyout_amount ? rs(o.buyout_amount) : "–")],
    ["Health cover", (o) => (o.health_cover ? rs(o.health_cover) : "–")],
    ["Learning budget per year", (o) => (o.learning_budget ? rs(o.learning_budget) : "–")],
    ["Benefits", (o) => o.benefits.join(", ") || "–"],
    ["Growth notes", (o) => o.growth_notes || "–"],
  ];
  return (
    <section className="rounded-3xl border bg-card p-5">
      <h2 className="mb-3 text-xl">{t("Side by side")}</h2>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[520px] text-sm">
          <thead>
            <tr className="text-left">
              <th className="py-2 font-medium text-muted-foreground">{t("Item")}</th>
              {d.offers.map((o, i) => (
                <th key={o.id} className={cn("px-3 py-2 align-top font-medium", d.winner === i && "rounded-t-2xl bg-success/10")}>
                  <div>{o.name}</div>
                  {o.company && <div className="text-xs font-normal text-muted-foreground">{o.company}</div>}
                  {d.winner === i && <Badge variant="success" className="mt-1"><Check className="size-3" />{t("Best fit")}</Badge>}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map(([l, f, bold]) => (
              <tr key={l} className={cn("border-t", bold && "font-semibold")}>
                <td className="py-1.5 pr-3 text-muted-foreground">{t(l)}</td>
                {d.offers.map((o, i) => <td key={o.id} className={cn("px-3 py-1.5 tabular-nums", d.winner === i && "bg-success/10")}>{f(o)}</td>)}
              </tr>
            ))}
            {FACTORS.map((f) => (
              <tr key={f} className="border-t">
                <td className="py-1.5 pr-3 text-muted-foreground">{t("Factor")}: {t(FACTOR_LABELS[f])}</td>
                {d.offers.map((o, i) => (
                  <td key={o.id} className={cn("px-3 py-1.5 tabular-nums", d.winner === i && "bg-success/10")}>
                    {o.breakdown[f].score.toFixed(0)} <span className="text-xs text-muted-foreground">({o.breakdown[f].contribution.toFixed(1)}){o.unrated.includes(f) && " *"}</span>
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-xs text-muted-foreground">{t("Each factor is scored 0 to 100, then weighted. Bracket shows points added to the score. * means you did not rate it, so a neutral 50 is used.")} {t(d.esop_note)}</p>
    </section>
  );
}

export function OfferCompare() {
  const { t } = useT();
  const saved = useApi<Saved[]>("/offers/saved");
  const apps = useApi<Application[]>("/applications");
  const [picked, setPicked] = useState<string[]>([]);
  const [weights, setWeights] = useState(DEFAULT_WEIGHTS);
  const [decision, setDecision] = useState<OfferDecision | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState<"none" | "new" | string>("none");
  const seq = useRef(0);
  const list = saved.data ?? [];
  const ids = useMemo(() => picked.filter((id) => list.some((s) => s.id === id)), [picked, list]);
  const key = ids.join(",");
  const wkey = FACTORS.map((f) => `${f}:${weights[f]}`).join(",");

  // Re-score as sliders move. The server owns every number.
  useEffect(() => {
    if (!key) { setDecision(null); return; }
    const id = ++seq.current;
    const timer = setTimeout(async () => {
      try {
        const res = await request<OfferDecision>(`/offers/compare?ids=${encodeURIComponent(key)}&weights=${encodeURIComponent(wkey)}`);
        if (id === seq.current) { setDecision(res); setError(null); }
      } catch (e) {
        if (id === seq.current) setError(e instanceof Error ? e.message : t("Could not compare"));
      }
    }, 250);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, wkey]);

  const toggle = (id: string) => setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : p.length < 6 ? [...p, id] : p));
  async function remove(id: string) {
    await request(`/offers/saved/${id}`, { method: "DELETE" });
    setPicked((p) => p.filter((x) => x !== id));
    await saved.reload();
  }
  const editing = form !== "none" && form !== "new" ? list.find((s) => s.id === form) ?? null : null;

  return (
    <div className="space-y-6">
      <section className="rounded-3xl border bg-card p-5">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-xl">{t("Your saved offers")}</h2>
          <Button size="sm" onClick={() => setForm("new")}><Plus />{t("Add offer")}</Button>
        </div>
        {list.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("Nothing saved yet.")} {t("Add two or more offers to compare them. Up to 6 can be compared at once.")}</p>
        ) : (
          <ul className="space-y-2">
            {list.map((s) => (
              <li key={s.id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-muted/50 px-3 py-2 text-sm">
                <label className="flex min-w-0 cursor-pointer items-center gap-2">
                  <input type="checkbox" checked={ids.includes(s.id)} onChange={() => toggle(s.id)} className="size-4 accent-[var(--chart-3)]" />
                  <span className="truncate">{s.input.name || t("Offer")}{s.input.company ? ` · ${s.input.company}` : ""} <span className="text-muted-foreground">{lakh(s.ctc)}</span></span>
                </label>
                <span className="flex shrink-0 gap-1">
                  <Button size="sm" variant="outline" onClick={() => setForm(s.id)}><Pencil />{t("Edit")}</Button>
                  <Button size="sm" variant="ghost" aria-label={t("Delete")} onClick={() => void remove(s.id)}><Trash2 /></Button>
                </span>
              </li>
            ))}
          </ul>
        )}
        <p className="mt-3 flex items-center gap-1.5 text-xs text-muted-foreground"><Wand2 className="size-3" />{t("Pay is calculated by the Calculator tab, so tax and in-hand numbers match everywhere.")}</p>
      </section>

      {form !== "none" && (form === "new" || editing) && (
        <OfferForm key={form} editing={editing} apps={apps.data ?? []} onDone={() => { setForm("none"); void saved.reload(); }} />
      )}

      {error && <Notice tone="error">{error}</Notice>}
      {ids.length === 0 && list.length > 0 && <Notice>{t("Tick the offers you want to compare.")}</Notice>}
      {ids.length > 0 && <Weights w={weights} setW={setWeights} />}
      {decision && ids.length > 0 && (
        <>
          <Comparison d={decision} />
          <TotalsChart d={decision} />
        </>
      )}
    </div>
  );
}
