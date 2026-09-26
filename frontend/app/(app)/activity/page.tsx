"use client";

import { ExternalLink } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { PageHeader } from "@/components/app-shell";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/form";
import { useApi } from "@/hooks/use-api";
import { cn } from "@/utils/cn";
import { formatDateTime } from "@/utils/format";

type Item = { id: string; at: string | null; group: string; action: string; title: string; detail: string };
type Run = { key: string; job_id: string | null; company: string; role: string | null; url: string | null; people: string[];
  sent: number; replied: number; drafts: number; status: "replied" | "completed" | "in_progress" | "draft"; last_activity: string | null };

const GROUP_TONE: Record<string, string> = {
  applications: "yellow", jobs: "orange", emails: "teal", outreach: "lime", profile: "mint", resumes: "purple", settings: "red", account: "green", other: "green",
};
const STATUS: Record<Run["status"], { label: string; tone: string }> = {
  replied: { label: "Replied", tone: "green" }, completed: { label: "Completed", tone: "teal" },
  in_progress: { label: "In progress", tone: "yellow" }, draft: { label: "Draft", tone: "orange" },
};

export default function ActivityPage() {
  const [view, setView] = useState<"all" | "referrals">("all");
  const [group, setGroup] = useState("");
  const [q, setQ] = useState("");
  const acts = useApi<{ items: Item[]; groups: Record<string, number> }>("/activity?limit=300");
  const runs = useApi<Run[]>("/activity/referrals");
  const items = (acts.data?.items ?? []).filter((i) => (!group || i.group === group) && (!q || `${i.title} ${i.detail}`.toLowerCase().includes(q.toLowerCase())));
  const rows = (runs.data ?? []).filter((r) => !q || `${r.company} ${r.role ?? ""}`.toLowerCase().includes(q.toLowerCase()));

  return (
    <>
      <PageHeader title="Activity" description="Everything your Saige agent did: applications, emails and replies, referral outreach, profile updates and job discovery." />
      <div className="mb-5 flex flex-wrap items-center gap-2">
        {([["all", `All activity${acts.data ? ` · ${acts.data.items.length}` : ""}`], ["referrals", `Referral runs${runs.data ? ` · ${runs.data.length}` : ""}`]] as const).map(([id, label]) => (
          <button key={id} type="button" onClick={() => setView(id)}
            className={cn("rounded-full border px-4 py-1.5 text-sm", view === id ? "border-transparent font-medium text-[#0b0b0c]" : "text-muted-foreground")}
            style={view === id ? { background: "var(--tone-purple)" } : undefined}>{label}</button>
        ))}
        <Input className="ml-auto h-9 max-w-xs" placeholder="Company or role…" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>

      {view === "all" && (
        <>
          <div className="mb-4 flex flex-wrap gap-1.5">
            <button type="button" onClick={() => setGroup("")} className={cn("rounded-full border px-3 py-1 text-xs", !group && "bg-muted font-medium")}>All</button>
            {Object.entries(acts.data?.groups ?? {}).map(([g, n]) => (
              <button key={g} type="button" onClick={() => setGroup(g)}
                className={cn("rounded-full border px-3 py-1 text-xs capitalize", group === g ? "border-transparent font-medium text-[#0b0b0c]" : "")}
                style={group === g ? { background: `var(--tone-${GROUP_TONE[g] ?? "green"})` } : undefined}>{g} {n}</button>
            ))}
          </div>
          {!acts.data ? <div className="skeleton h-72 rounded-3xl" /> : (
            <Card className="divide-y overflow-hidden p-0">
              {items.length === 0 && <p className="p-8 text-center text-sm text-muted-foreground">No activity yet.</p>}
              {items.map((i) => (
                <div key={i.id} className="flex items-center gap-3 px-4 py-3">
                  <span className="size-2.5 shrink-0 rounded-full" style={{ background: `var(--tone-${GROUP_TONE[i.group] ?? "green"})` }} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">{i.title}</p>
                    {i.detail && <p className="truncate text-xs text-muted-foreground">{i.detail}</p>}
                  </div>
                  <span className="shrink-0 text-xs text-muted-foreground">{i.at ? formatDateTime(i.at) : ""}</span>
                </div>
              ))}
            </Card>
          )}
        </>
      )}

      {view === "referrals" && (
        !runs.data ? <div className="skeleton h-72 rounded-3xl" /> : (
          <Card className="overflow-x-auto p-0">
            <table className="w-full min-w-[720px] text-sm">
              <thead className="border-b text-left text-xs text-muted-foreground">
                <tr><th className="px-4 py-3">#</th><th className="px-4 py-3">Company</th><th className="px-4 py-3">Role</th><th className="px-4 py-3">People reached</th><th className="px-4 py-3">Status</th><th className="px-4 py-3">Last activity</th></tr>
              </thead>
              <tbody className="divide-y">
                {rows.length === 0 && <tr><td colSpan={6} className="px-4 py-10 text-center text-muted-foreground">No referral outreach yet. Open a job and use “Get a referral”, or draft from Recruiters.</td></tr>}
                {rows.map((r, i) => (
                  <tr key={r.key}>
                    <td className="px-4 py-3 text-muted-foreground">{i + 1}</td>
                    <td className="px-4 py-3 font-medium">{r.company}</td>
                    <td className="px-4 py-3">
                      {r.job_id ? <Link href={`/jobs/${r.job_id}`} className="underline">{r.role ?? "Job"}</Link> : <span className="text-muted-foreground">Company outreach</span>}
                      {r.url && <a href={r.url} target="_blank" rel="noopener noreferrer" className="ml-1 inline-block align-middle text-muted-foreground"><ExternalLink className="size-3" /></a>}
                    </td>
                    <td className="px-4 py-3 text-xs">{r.people.join(", ") || "—"} <span className="text-muted-foreground">({r.sent} sent{r.replied ? `, ${r.replied} replied` : ""})</span></td>
                    <td className="px-4 py-3"><span className="rounded-full px-2.5 py-0.5 text-xs font-semibold text-[#0b0b0c]" style={{ background: `var(--tone-${STATUS[r.status].tone})` }}>{STATUS[r.status].label}</span></td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">{r.last_activity ? formatDateTime(r.last_activity) : ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        )
      )}
    </>
  );
}
