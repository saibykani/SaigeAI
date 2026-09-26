"use client";

import { CalendarCheck, CalendarClock, CalendarPlus, Check, Video, X } from "lucide-react";
import Link from "next/link";

import { Notice, PageHeader } from "@/components/app-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useApi } from "@/hooks/use-api";
import { downloadFile, request } from "@/services/api";
import type { Interview } from "@/types/api";
import { formatDateTime } from "@/utils/format";

type Grouped = Record<Interview["status"], Interview[]>;

function countdown(iso: string): string {
  const ms = new Date(iso).getTime() - Date.now();
  if (ms < 0) return "started";
  const h = Math.floor(ms / 3.6e6);
  return h >= 48 ? `in ${Math.floor(h / 24)} days` : h >= 1 ? `in ${h} h` : `in ${Math.max(1, Math.floor(ms / 6e4))} min`;
}

export default function InterviewsPage() {
  const { data, error, reload } = useApi<Grouped>("/interviews");
  const upcoming = [...(data?.upcoming ?? []), ...(data?.rescheduled ?? [])].sort((a, b) => a.scheduled_at.localeCompare(b.scheduled_at));

  async function setStatus(id: string, status: Interview["status"]) {
    await request(`/interviews/${id}`, { method: "PATCH", body: { status } });
    await reload();
  }

  return (
    <>
      <PageHeader title="Interviews" description="Upcoming, completed, rescheduled and cancelled interviews — added by you or detected from Gmail. One click adds any interview to your calendar." />
      {error && <Notice tone="error">{error}</Notice>}
      {!data ? (
        <div className="skeleton h-72 rounded-3xl" />
      ) : (
        <div className="grid gap-6 lg:grid-cols-3">
          <Card className="lg:col-span-2">
            <CardHeader><CardTitle className="flex items-center gap-2 text-lg"><CalendarClock className="size-5 text-primary" /> Upcoming</CardTitle></CardHeader>
            <CardContent className="flex flex-col gap-3">
              {upcoming.length === 0 && <p className="py-8 text-center text-sm text-muted-foreground">No upcoming interviews.</p>}
              {upcoming.map((i, idx) => (
                <div key={i.id} className="lift animate-rise flex flex-wrap items-center gap-4 rounded-2xl border bg-card-solid/60 p-4" style={{ animationDelay: `${idx * 50}ms` }}>
                  <div className="grid size-14 place-items-center rounded-2xl bg-[image:var(--hero-gradient)] text-center text-white">
                    <span className="text-[10px] uppercase">{new Date(i.scheduled_at).toLocaleString(undefined, { month: "short" })}</span>
                    <span className="-mt-1 text-lg font-semibold">{new Date(i.scheduled_at).getDate()}</span>
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="font-semibold">{i.role} · {i.company}</p>
                    <p className="text-sm text-muted-foreground">{i.round || "Interview"} · {formatDateTime(i.scheduled_at)} · <span className="font-medium text-foreground">{countdown(i.scheduled_at)}</span></p>
                    {i.status === "rescheduled" && <Badge variant="warning" className="mt-1">Rescheduled</Badge>}
                  </div>
                  <div className="flex gap-1">
                    {i.meeting_url && (
                      <a href={i.meeting_url} target="_blank" rel="noopener noreferrer" className="inline-flex h-8 items-center gap-1.5 rounded-full bg-primary px-3.5 text-xs font-medium text-primary-foreground">
                        <Video className="size-3.5" /> Join
                      </a>
                    )}
                    <Button size="sm" variant="ghost" onClick={() => downloadFile(`/interviews/${i.id}.ics`, "interview.ics")}><CalendarPlus /> Calendar</Button>
                    <Button size="sm" variant="ghost" onClick={() => setStatus(i.id, "completed")}><Check /> Done</Button>
                    <Button size="sm" variant="ghost" onClick={() => setStatus(i.id, "cancelled")}><X /> Cancel</Button>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
          <div className="flex flex-col gap-6">
            {(["completed", "cancelled"] as const).map((k) => (
              <Card key={k}>
                <CardHeader><CardTitle className="flex items-center gap-2 capitalize"><CalendarCheck className="size-4 text-muted-foreground" /> {k}</CardTitle></CardHeader>
                <CardContent>
                  {data[k].length === 0 ? (
                    <p className="text-sm text-muted-foreground">None</p>
                  ) : (
                    <ul className="flex flex-col gap-2 text-sm">
                      {data[k].map((i) => (
                        <li key={i.id}>
                          {i.application_id ? <Link href={`/applications/${i.application_id}`} className="font-medium hover:underline">{i.role} · {i.company}</Link> : <span className="font-medium">{i.role} · {i.company}</span>}
                          <p className="text-xs text-muted-foreground">{i.round || "Interview"} · {formatDateTime(i.scheduled_at)}</p>
                        </li>
                      ))}
                    </ul>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}
    </>
  );
}
