"use client";

import { CalendarClock, Mail, RefreshCw, Video } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Notice } from "@/components/app-shell";
import { DotRing } from "@/components/dot-ring";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useApi } from "@/hooks/use-api";
import { request } from "@/services/api";
import { formatDateTime } from "@/utils/format";

type Mailx = {
  id: string; sender: string; subject: string; snippet: string; received_at: string; category: string; application_id: string | null;
  extracted: { sender_name?: string | null; sender_domain?: string; interview_at?: string | null; meeting_url?: string | null; interview_round?: string | null; deadline?: string | null };
};
type ScanOut = { scanned: number; interview_emails: number; emails: Mailx[] };

const TONE: Record<string, string> = { "Interview Invitation": "green", "Interview Reschedule": "yellow", "Coding Test": "purple", "Assessment": "orange" };

/** Interview mail pulled from the connected mailbox: invites, reschedules, coding tests and assessments, with date, round and link. */
export function InterviewEmails() {
  const { data, reload } = useApi<Mailx[]>("/emails/interviews");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ tone: "success" | "error"; text: string } | null>(null);

  async function scan() {
    setBusy(true);
    setMsg(null);
    try {
      const r = await request<ScanOut>("/emails/sync-interviews", { method: "POST" });
      setMsg({ tone: "success", text: `Scanned ${r.scanned} new email(s) from the last 6 months: ${r.interview_emails} interview email(s) found.` });
      await reload();
    } catch (e) {
      setMsg({ tone: "error", text: e instanceof Error ? e.message : "Couldn't sync your mail." });
    } finally {
      setBusy(false);
    }
  }

  const company = (m: Mailx) => m.extracted.sender_name || (m.extracted.sender_domain || "").split(".")[0] || m.sender;

  return (
    <Card className="mb-6">
      <CardHeader className="gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <CardTitle className="flex items-center gap-2 text-lg"><Mail className="size-5 text-primary" /> Interview emails</CardTitle>
          <CardDescription>Invites, reschedules, coding tests and assessments found in your connected mailbox, with the date, round and meeting link.</CardDescription>
        </div>
        <Button onClick={() => void scan()} disabled={busy}><RefreshCw /> {busy ? "Syncing…" : "Sync mail now"}</Button>
      </CardHeader>
      <CardContent className="space-y-3">
        {msg && <Notice tone={msg.tone}>{msg.text}{msg.tone === "error" && msg.text.includes("Connect") && <> · <Link className="underline" href="/integrations">Open Integrations</Link></>}</Notice>}
        {busy && <DotRing label="Scanning" sub="your mailbox" />}
        {!busy && data && data.length === 0 && (
          <p className="py-6 text-center text-sm text-muted-foreground">No interview emails yet. Press “Sync mail now” to search the last 6 months.</p>
        )}
        {!busy && data?.map((m) => (
          <div key={m.id} className="flex flex-wrap items-start gap-4 rounded-2xl border p-4">
            <span className="mt-1 size-2.5 shrink-0 rounded-full" style={{ background: `var(--tone-${TONE[m.category] ?? "green"})` }} />
            <div className="min-w-0 flex-1">
              <p className="font-medium">{m.subject}</p>
              <p className="text-sm text-muted-foreground">{company(m)} · received {formatDateTime(m.received_at)}</p>
              <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">{m.snippet}</p>
              <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
                <Badge variant="outline">{m.category}</Badge>
                {m.extracted.interview_round && <Badge variant="outline">{m.extracted.interview_round}</Badge>}
                {m.extracted.interview_at && <span className="flex items-center gap-1 font-medium"><CalendarClock className="size-3.5" /> {formatDateTime(m.extracted.interview_at)}</span>}
                {m.extracted.deadline && <span className="text-muted-foreground">Due {formatDateTime(m.extracted.deadline)}</span>}
              </div>
            </div>
            {m.extracted.meeting_url && (
              <a href={m.extracted.meeting_url} target="_blank" rel="noopener noreferrer" className="inline-flex h-8 items-center gap-1.5 rounded-full bg-primary px-3.5 text-xs font-medium text-primary-foreground">
                <Video className="size-3.5" /> Join
              </a>
            )}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
