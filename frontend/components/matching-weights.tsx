"use client";

import { useEffect, useState } from "react";

import { Notice } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useApi } from "@/hooks/use-api";
import { request } from "@/services/api";
import type { MatchWeights } from "@/types/api";

const LABELS: [keyof MatchWeights, string][] = [
  ["skills", "Skills"],
  ["experience", "Experience"],
  ["role", "Role"],
  ["location", "Location"],
  ["salary", "Salary"],
  ["domain", "Domain"],
  ["notice_period", "Notice period"],
  ["education", "Education"],
  ["work_authorization", "Work authorization"],
];

export function MatchingWeightsCard() {
  const { data, setData } = useApi<MatchWeights>("/jobs/matching/config");
  const [draft, setDraft] = useState<MatchWeights | null>(null);
  const [msg, setMsg] = useState<{ tone: "success" | "error"; text: string } | null>(null);

  useEffect(() => {
    if (data) setDraft(data);
  }, [data]);
  if (!draft) return null;
  const total = Object.values(draft).reduce((a, b) => a + b, 0);

  async function save(rescore: boolean) {
    setMsg(null);
    try {
      setData(await request<MatchWeights>("/jobs/matching/config", { method: "PUT", body: draft }));
      if (rescore) await request("/jobs/rematch-all", { method: "POST" });
      setMsg({ tone: "success", text: rescore ? "Weights saved and all jobs re-scored." : "Weights saved." });
    } catch (e) {
      setMsg({ tone: "error", text: e instanceof Error ? e.message : "Save failed" });
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Job match scoring</CardTitle>
        <CardDescription>How much each factor counts toward a job&apos;s match score. Factors with no information are skipped automatically.</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {LABELS.map(([k, label]) => (
          <label key={k} className="grid grid-cols-[140px_1fr_48px] items-center gap-3 text-sm">
            <span className="text-muted-foreground">{label}</span>
            <input
              type="range"
              min={0}
              max={50}
              step={1}
              value={draft[k]}
              aria-label={`${label} weight`}
              onChange={(e) => setDraft({ ...draft, [k]: Number(e.target.value) })}
              className="accent-[var(--primary)]"
            />
            <span className="text-right tabular-nums">{total ? Math.round((draft[k] / total) * 100) : 0}%</span>
          </label>
        ))}
        {msg && <Notice tone={msg.tone}>{msg.text}</Notice>}
        <div className="flex gap-2">
          <Button onClick={() => save(true)} disabled={total <= 0}>Save & re-score jobs</Button>
          <Button variant="ghost" onClick={() => save(false)} disabled={total <= 0}>Save only</Button>
        </div>
      </CardContent>
    </Card>
  );
}
