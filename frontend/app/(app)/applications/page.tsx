"use client";

import { Building2, Send } from "lucide-react";
import Link from "next/link";

import { Notice, PageHeader } from "@/components/app-shell";
import { CountUp } from "@/components/motion";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useApi } from "@/hooks/use-api";
import type { Application, ApplicationStatus } from "@/types/api";
import { formatDate, humanStatus } from "@/utils/format";

/** Pipeline columns; each groups related statuses. Stage order drives an ordinal blue accent. */
const COLUMNS: { title: string; statuses: ApplicationStatus[]; ord: number }[] = [
  { title: "To apply", statuses: ["SHORTLISTED", "READY_TO_APPLY", "APPROVAL_REQUIRED", "APPLYING", "APPLICATION_FAILED"], ord: 1 },
  { title: "Applied", statuses: ["APPLIED", "RECRUITER_CONTACTED"], ord: 3 },
  { title: "In process", statuses: ["RECRUITER_REPLIED", "SCREENING", "ASSESSMENT"], ord: 5 },
  { title: "Interviewing", statuses: ["INTERVIEW_SCHEDULED", "INTERVIEW_COMPLETED"], ord: 7 },
  { title: "Offer", statuses: ["OFFER"], ord: 8 },
];
const CLOSED: ApplicationStatus[] = ["REJECTED", "WITHDRAWN", "CLOSED"];

function statusTone(s: ApplicationStatus): "success" | "warning" | "destructive" | "default" | "muted" {
  if (s === "OFFER") return "success";
  if (s === "APPROVAL_REQUIRED" || s === "APPLYING") return "warning";
  if (s === "APPLICATION_FAILED" || s === "REJECTED") return "destructive";
  if (CLOSED.includes(s)) return "muted";
  return "default";
}

function AppCard({ a, delay }: { a: Application; delay: number }) {
  return (
    <Link href={`/applications/${a.id}`} className="block animate-rise" style={{ animationDelay: `${delay}ms` }}>
      <div className="lift rounded-2xl border bg-card-solid p-4 shadow-[var(--shadow-card)]">
        <div className="flex items-start gap-3">
          <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-muted text-muted-foreground">
            <Building2 className="size-4" />
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold">{a.role}</p>
            <p className="truncate text-xs text-muted-foreground">{a.company}</p>
          </div>
          {a.match_score != null && <span className="rounded-lg bg-success/15 px-1.5 py-0.5 text-xs font-semibold text-success">{a.match_score}%</span>}
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-1.5">
          <Badge variant={statusTone(a.status)}>{humanStatus(a.status)}</Badge>
          <span className="ml-auto text-[11px] text-muted-foreground">
            {a.applied_at ? `Applied ${formatDate(a.applied_at)}` : `Updated ${formatDate(a.updated_at)}`}
          </span>
        </div>
      </div>
    </Link>
  );
}

export default function ApplicationsPage() {
  const { data, error, loading } = useApi<Application[]>("/applications");
  const closed = (data ?? []).filter((a) => CLOSED.includes(a.status));

  return (
    <>
      <PageHeader
        title="Applications"
        description="Every application from preparation to offer. Final submission always happens on the employer's site — Saige prepares everything else."
        actions={<Link href="/jobs" className={buttonVariants({ variant: "gradient", className: "animate-gradient" })}><Send /> Prepare from a job</Link>}
      />
      {error && <Notice tone="error">{error}</Notice>}
      {loading && !data && <div className="grid gap-4 md:grid-cols-5">{COLUMNS.map((c) => <div key={c.title} className="skeleton h-64 rounded-2xl" />)}</div>}
      {data && data.length === 0 && (
        <Card className="flex flex-col items-center gap-3 py-14 text-center">
          <Send className="size-8 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">No applications yet. Open a job and click “Prepare application”.</p>
          <Link href="/jobs" className={buttonVariants({ size: "sm" })}>Go to Jobs</Link>
        </Card>
      )}
      {data && data.length > 0 && (
        <>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
            {COLUMNS.map((col, ci) => {
              const items = data.filter((a) => col.statuses.includes(a.status));
              return (
                <section key={col.title} className="animate-rise flex flex-col gap-3 rounded-3xl border bg-muted/40 p-3" style={{ animationDelay: `${ci * 60}ms` }}>
                  <header className="flex items-center gap-2 px-1">
                    <span className="size-2.5 rounded-full" style={{ background: `var(--ord-${col.ord})` }} aria-hidden />
                    <h2 className="text-sm font-semibold">{col.title}</h2>
                    <span className="ml-auto rounded-full bg-card-solid px-2 text-xs font-medium text-muted-foreground"><CountUp value={items.length} /></span>
                  </header>
                  {items.length === 0 ? (
                    <p className="px-1 py-6 text-center text-xs text-muted-foreground">Nothing here</p>
                  ) : (
                    items.map((a, i) => <AppCard key={a.id} a={a} delay={ci * 60 + i * 40} />)
                  )}
                </section>
              );
            })}
          </div>
          {closed.length > 0 && (
            <div className="mt-8">
              <h2 className="mb-3 text-sm font-semibold text-muted-foreground">Closed ({closed.length})</h2>
              <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-4">
                {closed.map((a, i) => <AppCard key={a.id} a={a} delay={i * 30} />)}
              </div>
            </div>
          )}
        </>
      )}
    </>
  );
}
