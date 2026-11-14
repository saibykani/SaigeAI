"use client";

import { BarChart3, Check, Copy, Plus, Printer, Save, Sparkles, Table2, Trash2, Wand2 } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { Notice } from "@/components/app-shell";
import { useT } from "@/components/i18n";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea } from "@/components/ui/form";
import { useApi } from "@/hooks/use-api";
import { request } from "@/services/api";
import { cn } from "@/utils/cn";

export type OfferInput = {
  name: string; company: string; basic: number; hra: number; special: number; lta: number; other_allowances: number;
  employer_pf: number | null; gratuity: number; insurance: number; employer_nps: number; variable: number; variable_payout_pct: number;
  joining_bonus: number; esop_annual: number; city: "metro" | "non_metro"; rent_paid: number; pf_mode: "12pct" | "capped";
  sec80c: number; sec80d: number; employee_nps: number; home_loan_interest: number; lta_claimed: number; state: string; pt_annual: number | null;
};
type Regime = {
  regime: "new" | "old"; gross: number; exemptions: Record<string, number>; standard_deduction: number; deductions: Record<string, number>;
  taxable_income: number; slab_tax: number; tax_after_rebate: number; surcharge: number; cess: number; total_tax: number; employee_pf: number;
  professional_tax: number; annual_in_hand: number; effective_rate: number; fixed_annual_in_hand: number; real_monthly_cash: number;
  monthly_in_hand: number; first_year_in_hand: number;
};
type Result = {
  name: string; company: string; fy: string; ctc: number; fixed_ctc: number; variable_target: number; variable_expected: number; fixed_pct: number;
  variable_pct: number; joining_bonus: number; esop_annual: number; total_first_year_value: number; regimes: { new: Regime; old: Regime };
  best_regime: "new" | "old"; regime_saving: number; real_monthly_cash: number; monthly_in_hand: number; annual_in_hand: number;
  first_year_in_hand: number; in_hand_pct_of_ctc: number; waterfall: { key: string; label: string; value: number }[]; assumptions: string[];
};
type Row = {
  result: Result; buyout: { days: number; basis: string; per_day: number; cost: number } | null; hike_ctc_pct?: number | null;
  hike_in_hand_pct?: number | null; monthly_in_hand_gain?: number; real_monthly_cash_gain?: number; break_even_months?: number | null;
};
type Compared = { offers: Row[]; current: Result | null; winner: number | null; fy: string };
type Saved = { id: string; input: OfferInput; ctc: number; monthly_in_hand: number; updated_at: string };

const blank = (name: string): OfferInput => ({
  name, company: "", basic: 0, hra: 0, special: 0, lta: 0, other_allowances: 0, employer_pf: null, gratuity: 0, insurance: 0, employer_nps: 0,
  variable: 0, variable_payout_pct: 100, joining_bonus: 0, esop_annual: 0, city: "metro", rent_paid: 0, pf_mode: "12pct", sec80c: 0, sec80d: 0,
  employee_nps: 0, home_loan_interest: 0, lta_claimed: 0, state: "KA", pt_annual: null,
});
const STATES: Record<string, string> = {
  KA: "Karnataka", TG: "Telangana", MH: "Maharashtra", TN: "Tamil Nadu", AP: "Andhra Pradesh", WB: "West Bengal", GJ: "Gujarat", KL: "Kerala",
  MP: "Madhya Pradesh", DL: "Delhi", HR: "Haryana", UP: "Uttar Pradesh", RJ: "Rajasthan", PB: "Punjab", OTHER: "Other",
};
const rs = (n: number) => `₹${Math.round(n).toLocaleString("en-IN")}`;
const lakh = (n: number) => `₹${(n / 100000).toFixed(2)} L`;
const pct = (n: number | null | undefined) => (n == null ? "–" : `${n > 0 ? "+" : ""}${n}%`);

/** Rupee amount that counts up to its value, formatted the Indian way. */
function Rupees({ value }: { value: number }) {
  const [shown, setShown] = useState(value);
  const from = useRef(value);
  useEffect(() => {
    const reduce = typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (reduce) { setShown(value); from.current = value; return; }
    const start = performance.now(), origin = from.current;
    let frame = 0;
    const tick = (now: number) => {
      const p = Math.min(1, (now - start) / 700);
      setShown(Math.round(origin + (value - origin) * (1 - Math.pow(1 - p, 3))));
      if (p < 1) frame = requestAnimationFrame(tick); else from.current = value;
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [value]);
  return <>{rs(shown)}</>;
}

function Money({ label, value, onChange, hint, placeholder }: { label: string; value: number | null; onChange: (n: number | null) => void; hint?: string; placeholder?: string }) {
  const { t } = useT();
  return (
    <Field label={t(label)} hint={hint ? t(hint) : undefined}>
      <Input inputMode="numeric" placeholder={placeholder ? t(placeholder) : "0"} value={value ? value.toLocaleString("en-IN") : ""}
        onChange={(e) => { const d = e.target.value.replace(/\D/g, ""); onChange(d ? Number(d) : placeholder ? null : 0); }} />
    </Field>
  );
}

const CASH: [keyof OfferInput, string][] = [["basic", "Basic"], ["hra", "HRA"], ["special", "Special allowance"], ["lta", "LTA"], ["other_allowances", "Other allowances"], ["variable", "Variable / bonus (target)"]];
const EMPLOYER: [keyof OfferInput, string][] = [["gratuity", "Gratuity"], ["insurance", "Insurance (employer paid)"], ["employer_nps", "Employer NPS (80CCD(2))"]];
const OLD: [keyof OfferInput, string][] = [["sec80c", "80C (ELSS, LIC, tuition)"], ["sec80d", "80D (health insurance)"], ["employee_nps", "NPS own (80CCD(1B))"], ["home_loan_interest", "Home loan interest"], ["lta_claimed", "LTA you claim with bills"]];

const TONE: Record<string, string> = {
  ctc: "var(--chart-2)", employer_only: "var(--chart-4)", variable_unpaid: "var(--chart-4)", employee_pf: "var(--chart-3)",
  pt: "var(--chart-1)", tax: "var(--chart-1)", in_hand: "var(--chart-3)",
};
const LEGEND: [string, string][] = [["var(--chart-2)", "CTC"], ["var(--chart-4)", "Not paid in cash"], ["var(--chart-1)", "Tax and professional tax"], ["var(--chart-3)", "PF savings and in-hand"]];

function Waterfall({ r }: { r: Result }) {
  const { t } = useT();
  const [table, setTable] = useState(false);
  let run = 0;
  const data = r.waterfall.map((w) => {
    const label = t(w.label);
    if (w.key === "ctc" || w.key === "in_hand") { run = w.value; return { key: w.key, label, base: 0, bar: w.value, value: w.value }; }
    run += w.value;
    return { key: w.key, label, base: run, bar: -w.value, value: w.value };
  });
  return (
    <section className="rounded-3xl border bg-card p-5">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-xl">{t("From CTC to in-hand")}</h2>
        <Button variant="outline" size="sm" onClick={() => setTable(!table)}>{table ? <BarChart3 /> : <Table2 />}{table ? t("Chart view") : t("Table view")}</Button>
      </div>
      {table ? (
        <table className="w-full text-sm">
          <thead><tr className="text-left text-muted-foreground"><th className="py-1.5 font-medium">{t("Item")}</th><th className="py-1.5 text-right font-medium">{t("Per year")}</th><th className="py-1.5 text-right font-medium">{t("Per month")}</th></tr></thead>
          <tbody>{data.map((d) => (
            <tr key={d.key} className="border-t"><td className="py-1.5">{d.label}</td><td className="py-1.5 text-right tabular-nums">{rs(d.value)}</td><td className="py-1.5 text-right tabular-nums">{rs(d.value / 12)}</td></tr>
          ))}</tbody>
        </table>
      ) : (
        <>
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data} layout="vertical" margin={{ top: 4, right: 70, bottom: 4, left: 8 }} barCategoryGap={8}>
                <CartesianGrid horizontal={false} stroke="var(--grid)" />
                <XAxis type="number" tickFormatter={(v: number) => `${(v / 100000).toFixed(0)}L`} tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} axisLine={false} tickLine={false} />
                <YAxis dataKey="label" type="category" width={150} tick={{ fontSize: 12, fill: "var(--foreground)" }} axisLine={false} tickLine={false} />
                <Tooltip cursor={{ fill: "var(--muted)" }} formatter={(v, n) => (n === "base" ? [null, null] : [rs(Number(v)), t("Amount")])} filterNull
                  contentStyle={{ background: "var(--card-solid)", border: "1px solid var(--border)", borderRadius: 12, fontSize: 12 }} labelStyle={{ color: "var(--foreground)", fontWeight: 600 }} />
                <Bar dataKey="base" stackId="w" fill="transparent" isAnimationActive={false} />
                <Bar dataKey="bar" stackId="w" radius={6} maxBarSize={26} animationDuration={800}>
                  {data.map((d) => <Cell key={d.key} fill={TONE[d.key]} />)}
                  <LabelList dataKey="bar" position="right" formatter={(v) => lakh(Number(v))} style={{ fontSize: 11.5, fill: "var(--muted-foreground)" }} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
            {LEGEND.map(([c, l]) => <li key={l} className="flex items-center gap-1.5"><span className="size-2.5 rounded-sm" style={{ background: c }} />{t(l)}</li>)}
          </ul>
        </>
      )}
    </section>
  );
}

function BreakdownTable({ r }: { r: Result }) {
  const { t } = useT();
  const { new: n, old: o } = r.regimes;
  const sum = (x: Record<string, number>) => Object.values(x).reduce((a, b) => a + b, 0);
  const rows: [string, number, number, boolean?][] = [
    ["Gross taxable pay", n.gross, o.gross], ["Exemptions (HRA, LTA)", -sum(n.exemptions), -sum(o.exemptions)],
    ["Standard deduction", -n.standard_deduction, -o.standard_deduction], ["Other deductions (80C, 80D, NPS, loan, PT)", -sum(n.deductions), -sum(o.deductions)],
    ["Taxable income", n.taxable_income, o.taxable_income, true], ["Tax after rebate", n.tax_after_rebate, o.tax_after_rebate],
    ["Surcharge", n.surcharge, o.surcharge], ["Cess (4%)", n.cess, o.cess], ["Total tax", n.total_tax, o.total_tax, true],
    ["Employee PF", n.employee_pf, o.employee_pf], ["Professional tax", n.professional_tax, o.professional_tax],
    ["In-hand per year", n.annual_in_hand, o.annual_in_hand, true], ["In-hand per month (with variable)", n.monthly_in_hand, o.monthly_in_hand],
    ["Real monthly cash (fixed pay only)", n.real_monthly_cash, o.real_monthly_cash, true],
  ];
  return (
    <section className="rounded-3xl border bg-card p-5">
      <h2 className="mb-3 text-xl">{t("Tax breakdown, both regimes")}</h2>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[420px] text-sm">
          <thead><tr className="text-left text-muted-foreground"><th className="py-1.5 font-medium">{t("Item")}</th>
            <th className="py-1.5 text-right font-medium">{t("New regime")}{r.best_regime === "new" && " ✓"}</th>
            <th className="py-1.5 text-right font-medium">{t("Old regime")}{r.best_regime === "old" && " ✓"}</th></tr></thead>
          <tbody>{rows.map(([l, a, b, bold]) => (
            <tr key={l} className={cn("border-t", bold && "font-semibold")}><td className="py-1.5">{t(l)}</td><td className="py-1.5 text-right tabular-nums">{rs(a)}</td><td className="py-1.5 text-right tabular-nums">{rs(b)}</td></tr>
          ))}</tbody>
        </table>
      </div>
    </section>
  );
}

function Hero({ r, view, setView }: { r: Result; view: "auto" | Regime["regime"]; setView: (v: "auto" | Regime["regime"]) => void }) {
  const { t } = useT();
  const reg = r.regimes[view === "auto" ? r.best_regime : view];
  const tabs: ["auto" | "new" | "old", string][] = [["auto", "Recommended"], ["new", "New regime"], ["old", "Old regime"]];
  return (
    <section className="rounded-3xl border bg-card p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted-foreground">{t("Real monthly cash in your bank")}</p>
        <div className="flex gap-1 rounded-full bg-muted p-1 print:hidden" role="group" aria-label={t("Tax regime")}>
          {tabs.map(([k, l]) => (
            <button key={k} type="button" onClick={() => setView(k)} aria-pressed={view === k}
              className={cn("rounded-full px-3 py-1 text-xs", view === k ? "bg-card font-medium text-primary shadow-sm" : "text-muted-foreground")}>
              {t(l)}{k !== "auto" && r.best_regime === k && " ★"}
            </button>
          ))}
        </div>
      </div>
      <p className="mt-2 text-5xl font-light tracking-tight md:text-6xl"><Rupees value={reg.real_monthly_cash} /><span className="ml-2 text-lg text-muted-foreground">{t("/ month")}</span></p>
      <p className="mt-1 text-sm text-muted-foreground">{t("Fixed pay only. Variable, joining bonus and ESOP are not counted.")}</p>
      <div className="mt-5 grid grid-cols-2 gap-3 md:grid-cols-4">
        {[
          ["Average monthly with variable", reg.monthly_in_hand], ["Annual in-hand", reg.annual_in_hand], ["First year in-hand", reg.first_year_in_hand], ["Total tax and cess", reg.total_tax],
        ].map(([l, v]) => (
          <div key={l as string} className="rounded-2xl bg-muted/60 p-3"><p className="text-xs text-muted-foreground">{t(l as string)}</p><p className="mt-0.5 text-lg font-medium tabular-nums"><Rupees value={v as number} /></p></div>
        ))}
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-2 text-sm">
        <Badge variant="success"><Sparkles className="size-3" />{r.best_regime === "new" ? t("New regime is better") : t("Old regime is better")}</Badge>
        <span className="text-muted-foreground">{t("You keep {n} more per year.", { n: rs(r.regime_saving) })}</span>
        <span className="text-muted-foreground">· {t("CTC {a}, in-hand is {b}% of CTC", { a: lakh(r.ctc), b: r.in_hand_pct_of_ctc })}</span>
        <span className="text-muted-foreground">· {t("Fixed {f}% / variable {v}%", { f: r.fixed_pct, v: r.variable_pct })}</span>
      </div>
      {(r.esop_annual > 0 || r.joining_bonus > 0) && (
        <p className="mt-2 text-xs text-muted-foreground">{t("Not in cash: joining bonus {j} (taxed in year one), ESOP/RSU paper value {e} per year.", { j: rs(r.joining_bonus), e: rs(r.esop_annual) })}</p>
      )}
    </section>
  );
}

function CompareCards({ data, activeIdx }: { data: Compared; activeIdx: number }) {
  const { t } = useT();
  const cards: { key: string; r: Result; row?: Row; current?: boolean }[] = [
    ...(data.current ? [{ key: "cur", r: data.current, current: true }] : []),
    ...data.offers.map((row, i) => ({ key: `o${i}`, r: row.result, row, current: false, i })),
  ];
  if (cards.length < 2) return null;
  const line = (l: string, v: React.ReactNode, strong?: boolean) => (
    <div className={cn("flex items-baseline justify-between gap-3 border-t py-1.5 text-sm", strong && "font-semibold")}><span className="text-muted-foreground">{t(l)}</span><span className="tabular-nums">{v}</span></div>
  );
  return (
    <section className="rounded-3xl border bg-card p-5">
      <h2 className="mb-3 text-xl">{t("Side by side")}</h2>
      <div className={cn("grid gap-4", cards.length === 2 ? "md:grid-cols-2" : cards.length === 3 ? "md:grid-cols-3" : "md:grid-cols-2 xl:grid-cols-4")}>
        {cards.map((c, idx) => {
          const win = data.winner !== null && !c.current && data.offers.indexOf(c.row as Row) === data.winner;
          return (
            <div key={c.key} className={cn("rounded-2xl border p-4", win && "border-success ring-1 ring-success", !c.current && idx - (data.current ? 1 : 0) === activeIdx && "bg-muted/40")}>
              <div className="mb-2 flex flex-wrap items-center gap-2"><h3 className="text-base font-medium">{c.r.name || t("Offer")}</h3>
                {c.current && <Badge variant="muted">{t("Current")}</Badge>}{win && <Badge variant="success"><Check className="size-3" />{t("Highest in-hand")}</Badge>}</div>
              {c.r.company && <p className="-mt-1 mb-1 text-xs text-muted-foreground">{c.r.company}</p>}
              {line("CTC", lakh(c.r.ctc))}
              {line("Real monthly cash", rs(c.r.real_monthly_cash), true)}
              {line("Average monthly in-hand", rs(c.r.monthly_in_hand))}
              {line("Annual in-hand", rs(c.r.annual_in_hand))}
              {line("Variable share", `${c.r.variable_pct}%`)}
              {line("Better regime", c.r.best_regime === "new" ? t("New") : t("Old"))}
              {c.row && data.current && (
                <>
                  {line("Hike on CTC", pct(c.row.hike_ctc_pct))}
                  {line("Hike on in-hand", pct(c.row.hike_in_hand_pct), true)}
                  {line("Monthly in-hand change", rs(c.row.monthly_in_hand_gain ?? 0))}
                  {c.row.buyout && line("Notice buyout", rs(c.row.buyout.cost))}
                  {c.row.buyout && line("Break-even", c.row.break_even_months != null ? t("{n} months", { n: c.row.break_even_months }) : t("No monthly gain"))}
                </>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}

export function OfferCalculator() {
  const { t } = useT();
  const [offers, setOffers] = useState<OfferInput[]>([blank("Offer 1")]);
  const [current, setCurrent] = useState<OfferInput | null>(null);
  const [active, setActive] = useState(0); // -1 = current salary
  const [view, setView] = useState<"auto" | "new" | "old">("auto");
  const [notice, setNotice] = useState(60);
  const [basis, setBasis] = useState<"basic" | "gross">("basic");
  const [data, setData] = useState<Compared | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [ctcQuick, setCtcQuick] = useState<number | null>(null);
  const [varPct, setVarPct] = useState(0);
  const [paste, setPaste] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const saved = useApi<Saved[]>("/offers/saved");
  const seq = useRef(0);

  const form = active === -1 && current ? current : offers[Math.min(active, offers.length - 1)] ?? offers[0];
  const patch = useCallback((p: Partial<OfferInput>) => {
    if (active === -1) setCurrent((c) => (c ? { ...c, ...p } : c));
    else setOffers((os) => os.map((o, i) => (i === active ? { ...o, ...p } : o)));
  }, [active]);

  // Debounced live recalculation. The server is the single source of truth for every number.
  useEffect(() => {
    const id = ++seq.current;
    const timer = setTimeout(async () => {
      try {
        const res = await request<Compared>("/offers/compare", { method: "POST", body: { offers, current, notice_days: current ? notice : 0, buyout_basis: basis } });
        if (id === seq.current) { setData(res); setError(null); }
      } catch (e) {
        if (id === seq.current) setError(e instanceof Error ? e.message : "Could not calculate");
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [offers, current, notice, basis]);

  const result: Result | null = data ? (active === -1 ? data.current : data.offers[Math.min(active, data.offers.length - 1)]?.result) ?? null : null;

  async function autoSplit() {
    if (!ctcQuick) return;
    const s = await request<Record<string, number | string>>("/offers/split", { method: "POST", body: { ctc: ctcQuick, variable_pct: varPct, pf_mode: form.pf_mode } });
    patch({ basic: s.basic as number, hra: s.hra as number, special: s.special as number, employer_pf: s.employer_pf as number, gratuity: s.gratuity as number, variable: s.variable as number });
    setMsg(t("Split into a typical structure. Edit any number to match your offer letter."));
  }
  async function readBreakup() {
    if (!paste.trim()) return;
    const p = await request<{ fields: Partial<OfferInput>; ctc: number | null; unmatched: string[] }>("/offers/parse", { method: "POST", body: { text: paste } });
    let fields = p.fields;
    if (!fields.basic && p.ctc) {
      const s = await request<Record<string, number>>("/offers/split", { method: "POST", body: { ctc: p.ctc, variable_pct: 0, pf_mode: form.pf_mode } });
      fields = { basic: s.basic, hra: s.hra, special: s.special, employer_pf: s.employer_pf, gratuity: s.gratuity, ...fields };
    }
    patch(fields);
    setMsg(Object.keys(fields).length ? t("Read {n} fields from your text. Check them against your offer letter.", { n: Object.keys(fields).length }) : t("No amounts found. Try lines like Basic 6,00,000."));
  }
  async function save() {
    await request("/offers/saved", { method: "POST", body: { input: form } });
    await saved.reload();
    setMsg(t("Saved."));
  }
  async function remove(id: string) {
    await request(`/offers/saved/${id}`, { method: "DELETE" });
    await saved.reload();
  }
  function load(s: Saved) {
    if (active === -1) setCurrent({ ...s.input }); else patch({ ...s.input });
  }
  async function copySummary() {
    if (!result) return;
    const reg = result.regimes[result.best_regime];
    const text = [`${result.name}${result.company ? ` (${result.company})` : ""} - ${result.fy}`, `CTC: ${rs(result.ctc)}`,
      `Real monthly cash: ${rs(result.real_monthly_cash)} (${result.best_regime} regime)`, `Annual in-hand: ${rs(reg.annual_in_hand)}`, `Total tax: ${rs(reg.total_tax)}`,
      "Estimate from the published slabs. Not tax advice."].join("\n");
    try { await navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 1800); } catch { /* clipboard blocked */ }
  }

  const tabBtn = "rounded-full px-3.5 py-1.5 text-sm";
  const group = "mb-4 text-sm font-medium";
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-2 print:hidden">
        {current && <button type="button" onClick={() => setActive(-1)} className={cn(tabBtn, active === -1 ? "bg-accent font-medium text-primary" : "bg-muted text-muted-foreground")}>{t("Current salary")}</button>}
        {offers.map((o, i) => (
          <button key={i} type="button" onClick={() => setActive(i)} className={cn(tabBtn, active === i ? "bg-accent font-medium text-primary" : "bg-muted text-muted-foreground")}>{o.name || `${t("Offer")} ${i + 1}`}</button>
        ))}
        {offers.length < 3 && <Button variant="outline" size="sm" onClick={() => { setOffers([...offers, blank(`Offer ${offers.length + 1}`)]); setActive(offers.length); }}><Plus />{t("Add offer")}</Button>}
        {!current && <Button variant="outline" size="sm" onClick={() => { setCurrent(blank("Current")); setActive(-1); }}><Plus />{t("Add current salary")}</Button>}
        {active === -1 && current && <Button variant="ghost" size="sm" onClick={() => { setCurrent(null); setActive(0); }}><Trash2 />{t("Remove")}</Button>}
        {active >= 0 && offers.length > 1 && <Button variant="ghost" size="sm" onClick={() => { setOffers(offers.filter((_, i) => i !== active)); setActive(0); }}><Trash2 />{t("Remove")}</Button>}
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,420px)_minmax(0,1fr)]">
        <div className="space-y-4 print:hidden">
          <section className="rounded-3xl border bg-card p-5">
            <h2 className="mb-3 text-xl">{t("Quick start")}</h2>
            <div className="grid grid-cols-2 gap-3">
              <Field label={t("Name")}><Input value={form.name} onChange={(e) => patch({ name: e.target.value })} /></Field>
              <Field label={t("Company")}><Input value={form.company} onChange={(e) => patch({ company: e.target.value })} /></Field>
              <Money label="Total CTC per year" value={ctcQuick} onChange={(n) => setCtcQuick(n || null)} />
              <Field label={t("Variable % of CTC")}><Input type="number" min={0} max={60} value={varPct} onChange={(e) => setVarPct(Math.min(60, Math.max(0, Number(e.target.value) || 0)))} /></Field>
            </div>
            <Button className="mt-3" size="sm" onClick={() => void autoSplit()} disabled={!ctcQuick}><Wand2 />{t("Auto-split a typical structure")}</Button>
            <Field className="mt-4" label={t("Or paste your CTC breakup")} hint="Lines like Basic 6,00,000 or HRA 20,000 per month. Nothing is guessed.">
              <Textarea rows={4} value={paste} onChange={(e) => setPaste(e.target.value)} placeholder={"Basic 6,00,000\nHRA 2,40,000\nSpecial allowance 50,000 per month"} />
            </Field>
            <Button className="mt-2" size="sm" variant="outline" onClick={() => void readBreakup()} disabled={!paste.trim()}>{t("Read breakup")}</Button>
            {msg && <p className="mt-2 text-xs text-muted-foreground">{msg}</p>}
          </section>

          <section className="rounded-3xl border bg-card p-5">
            <h3 className={group}>{t("Pay you receive (per year)")}</h3>
            <div className="grid grid-cols-2 gap-3">
              {CASH.map(([k, l]) => <Money key={k} label={l} value={form[k] as number} onChange={(n) => patch({ [k]: n ?? 0 })} />)}
              <Field label={t("Variable payout expected %")}><Input type="number" min={0} max={300} value={form.variable_payout_pct} onChange={(e) => patch({ variable_payout_pct: Math.max(0, Number(e.target.value) || 0) })} /></Field>
            </div>
            <h3 className={cn(group, "mt-5")}>{t("Paid by employer, never in your bank")}</h3>
            <div className="grid grid-cols-2 gap-3">
              <Money label="Employer PF" value={form.employer_pf} onChange={(n) => patch({ employer_pf: n })} placeholder="Same as your PF" />
              {EMPLOYER.map(([k, l]) => <Money key={k} label={l} value={form[k] as number} onChange={(n) => patch({ [k]: n ?? 0 })} />)}
            </div>
            <h3 className={cn(group, "mt-5")}>{t("One-time and equity (not counted as cash)")}</h3>
            <div className="grid grid-cols-2 gap-3">
              <Money label="Joining bonus" value={form.joining_bonus} onChange={(n) => patch({ joining_bonus: n ?? 0 })} />
              <Money label="ESOP / RSU value per year" value={form.esop_annual} onChange={(n) => patch({ esop_annual: n ?? 0 })} />
            </div>
            <h3 className={cn(group, "mt-5")}>{t("Tax setup")}</h3>
            <div className="grid grid-cols-2 gap-3">
              <Field label={t("City")}><Select value={form.city} onChange={(e) => patch({ city: e.target.value as OfferInput["city"] })}><option value="metro">{t("Metro (Delhi, Mumbai, Kolkata, Chennai)")}</option><option value="non_metro">{t("Non-metro")}</option></Select></Field>
              <Field label={t("State (professional tax)")}><Select value={form.state} onChange={(e) => patch({ state: e.target.value })}>{Object.entries(STATES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</Select></Field>
              <Field label={t("Employee PF")}><Select value={form.pf_mode} onChange={(e) => patch({ pf_mode: e.target.value as OfferInput["pf_mode"] })}><option value="12pct">{t("12% of basic")}</option><option value="capped">{t("Capped at ₹15,000 basic")}</option></Select></Field>
              <Money label="Professional tax per year" value={form.pt_annual} onChange={(n) => patch({ pt_annual: n })} placeholder="Default for state" />
              <Money label="Rent you pay per year" value={form.rent_paid} onChange={(n) => patch({ rent_paid: n ?? 0 })} hint="Used for HRA exemption in the old regime." />
            </div>
            <h3 className={cn(group, "mt-5")}>{t("Old regime deductions")}</h3>
            <div className="grid grid-cols-2 gap-3">{OLD.map(([k, l]) => <Money key={k} label={l} value={form[k] as number} onChange={(n) => patch({ [k]: n ?? 0 })} />)}</div>
          </section>

          <section className="rounded-3xl border bg-card p-5">
            <div className="mb-3 flex items-center justify-between gap-2"><h3 className="text-base font-medium">{t("Saved offers")}</h3>
              <Button size="sm" onClick={() => void save()}><Save />{t("Save this offer")}</Button></div>
            {saved.data && saved.data.length > 0 ? (
              <ul className="space-y-2">{saved.data.map((s) => (
                <li key={s.id} className="flex items-center justify-between gap-2 rounded-xl bg-muted/50 px-3 py-2 text-sm">
                  <span className="min-w-0 truncate">{s.input.name}{s.input.company ? ` · ${s.input.company}` : ""} <span className="text-muted-foreground">{lakh(s.ctc)}</span></span>
                  <span className="flex shrink-0 gap-1"><Button size="sm" variant="outline" onClick={() => load(s)}>{t("Load")}</Button>
                    <Button size="sm" variant="ghost" aria-label={t("Delete")} onClick={() => void remove(s.id)}><Trash2 /></Button></span>
                </li>))}</ul>
            ) : <p className="text-sm text-muted-foreground">{t("Nothing saved yet.")}</p>}
          </section>
        </div>

        <div className="min-w-0 space-y-6">
          {error && <Notice tone="error">{error}</Notice>}
          {result && result.ctc > 0 ? (
            <>
              <Hero r={result} view={view} setView={setView} />
              <div className="flex flex-wrap gap-2 print:hidden">
                <Button variant="outline" size="sm" onClick={() => window.print()}><Printer />{t("Print summary")}</Button>
                <Button variant="outline" size="sm" onClick={() => void copySummary()}>{copied ? <Check /> : <Copy />}{copied ? t("Copied") : t("Copy summary")}</Button>
              </div>
              <Waterfall r={result} />
              {data && <CompareCards data={data} activeIdx={active} />}
              {current && (
                <section className="rounded-3xl border bg-card p-5 print:hidden">
                  <h2 className="mb-1 text-xl">{t("Notice period buyout")}</h2>
                  <p className="mb-3 text-sm text-muted-foreground">{t("Priced on your current salary. Break-even is buyout cost divided by the monthly gain in real cash.")}</p>
                  <div className="grid max-w-md grid-cols-2 gap-3">
                    <Field label={t("Days to buy out")}><Input type="number" min={0} max={365} value={notice} onChange={(e) => setNotice(Math.min(365, Math.max(0, Number(e.target.value) || 0)))} /></Field>
                    <Field label={t("Per-day pay based on")}><Select value={basis} onChange={(e) => setBasis(e.target.value as "basic" | "gross")}><option value="basic">{t("Basic")}</option><option value="gross">{t("Gross cash pay")}</option></Select></Field>
                  </div>
                  {data?.offers[0]?.buyout && <p className="mt-3 text-sm">{t("Buyout for {d} days: {c} ({p} per day)", { d: data.offers[0].buyout.days, c: rs(data.offers[0].buyout.cost), p: rs(data.offers[0].buyout.per_day) })}</p>}
                </section>
              )}
              <BreakdownTable r={result} />
              <section className="rounded-3xl border bg-card p-5">
                <h2 className="mb-2 text-xl">{t("Assumptions")}</h2>
                <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">{result.assumptions.map((a) => <li key={a}>{a}</li>)}</ul>
              </section>
            </>
          ) : (
            <section className="grid place-items-center rounded-3xl border bg-card p-10 text-center">
              <p className="text-lg">{t("Enter a CTC or paste your breakup to see your real monthly cash.")}</p>
              <p className="mt-1 max-w-md text-sm text-muted-foreground">{t("Both tax regimes are calculated live from the published slabs, and the better one is recommended.")}</p>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}
