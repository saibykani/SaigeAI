"use client";

import { ExternalLink, FileText, Mail, Radar as RadarIcon } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Notice, PageHeader } from "@/components/app-shell";
import { useT } from "@/components/i18n";
import { Loader3D } from "@/components/loader3d";
import { RadarChart, toneFor } from "@/components/radar/radar-chart";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useApi } from "@/hooks/use-api";
import { request } from "@/services/api";
import type { RadarDigestResult, RadarJob, RadarResponse } from "@/types/api";

type Msg = { tone: "success" | "error" | "warning" | "info"; text: string } | null;

function studioHref(j: RadarJob) {
  const q = new URLSearchParams({ title: j.title, company: j.company });
  if (j.origin === "careers") q.set("career_job", j.id);
  return `/studio?${q.toString()}`;
}

function JobCard({ job, rank, active, onSelect }: { job: RadarJob; rank: number; active: boolean; onSelect: () => void }) {
  const { t } = useT();
  const router = useRouter();
  const tone = toneFor(job.score);
  return (
    <Card className={active ? "ring-1 ring-[color:var(--tone-green)]" : undefined}>
      <CardContent className="space-y-3 p-5" onClick={onSelect}>
        <div className="flex items-start gap-4">
          <div className="flex size-14 shrink-0 flex-col items-center justify-center rounded-2xl border"
            style={{ borderColor: `color-mix(in oklab, var(--tone-${tone}) 45%, transparent)` }}>
            <span className="text-lg font-semibold leading-none" style={{ color: `var(--tone-${tone})` }}>{job.score}</span>
            <span className="mt-0.5 text-[10px] text-muted-foreground">{t("match")}</span>
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-xs text-muted-foreground">#{rank} · {job.source}</p>
            <h3 className="truncate text-base font-medium">{job.title}</h3>
            <p className="truncate text-sm text-muted-foreground">{job.company}{job.location ? ` · ${job.location}` : ""}</p>
          </div>
        </div>
        {job.reasons.length > 0 && (
          <div>
            <p className="mb-1.5 text-xs text-muted-foreground">{t("Why you fit")}</p>
            <div className="flex flex-wrap gap-1.5">
              {job.reasons.map((r) => <Badge key={r} variant="outline">{r}</Badge>)}
            </div>
          </div>
        )}
        {job.missing_skills.length > 0 && (
          <p className="text-xs text-muted-foreground">
            {t("Missing skills")}: <span className="text-foreground">{job.missing_skills.slice(0, 4).join(", ")}</span>
          </p>
        )}
        <div className="flex flex-wrap gap-2 pt-1">
          <Button size="sm" variant="outline" onClick={() => router.push(studioHref(job))}>
            <FileText className="size-4" />{t("ATS resume")}
          </Button>
          {job.url && (
            <Button size="sm" variant="outline" onClick={() => window.open(job.url, "_blank", "noopener,noreferrer")}>
              <ExternalLink className="size-4" />{t("Open job")}
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export default function RadarPage() {
  const { t } = useT();
  const { data, error, loading } = useApi<RadarResponse>("/radar?top=12");
  const [active, setActive] = useState<string | null>(null);
  const [msg, setMsg] = useState<Msg>(null);
  const [sending, setSending] = useState(false);

  async function sendDigest() {
    setSending(true);
    setMsg(null);
    try {
      const r = await request<RadarDigestResult>("/radar/digest/test", { method: "POST" });
      if (r.sent > 0) setMsg({ tone: "success", text: `Sent your top ${r.sent} to ${r.to}.` });
      else if (r.notified) setMsg({ tone: "warning", text: r.error ?? "Saved as an in-app notification." });
      else setMsg({ tone: "info", text: r.reason ?? r.skipped ?? r.error ?? "Nothing was sent." });
    } catch (e) {
      setMsg({ tone: "error", text: e instanceof Error ? e.message : "Could not send the digest." });
    } finally {
      setSending(false);
    }
  }

  const items = data?.items ?? [];
  return (
    <div>
      <PageHeader title="Job Match Radar" description="Today's best-fit jobs, scored against your verified profile. The closer to the centre, the better the match."
        actions={<Button variant="outline" onClick={sendDigest} disabled={sending}><Mail className="size-4" />{t("Email me my top 5")}</Button>} />
      {msg && <div className="mb-4"><Notice tone={msg.tone}>{msg.text}</Notice></div>}
      {error && <Notice tone="error">{error}</Notice>}
      {loading && <div className="py-16"><Loader3D label="Scanning your matches" /></div>}
      {data && items.length === 0 && (
        <Notice tone="info">{t("No matches yet. Add a target role to your profile, then open Jobs for you or scan Career portals.")}</Notice>
      )}
      {items.length > 0 && data && (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,460px)_1fr]">
          <Card className="h-fit lg:sticky lg:top-6">
            <CardHeader>
              <CardTitle className="flex items-center gap-2"><RadarIcon className="size-5" />{t("Radar")}</CardTitle>
              <CardDescription>{`${items.length} of ${data.total} jobs · ${data.generated_from.feed} from your feed, ${data.generated_from.careers} from career portals`}</CardDescription>
            </CardHeader>
            <CardContent><RadarChart jobs={items} active={active} onSelect={setActive} /></CardContent>
          </Card>
          <div className="space-y-4">
            {items.map((j, i) => <JobCard key={j.id} job={j} rank={i + 1} active={active === j.id} onSelect={() => setActive(j.id)} />)}
          </div>
        </div>
      )}
    </div>
  );
}
