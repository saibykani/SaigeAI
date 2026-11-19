"use client";

import { Trash2 } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Select, Textarea } from "@/components/ui/form";
import { ConfirmDialog, Err, fmt } from "@/components/super-admin";
import { useApi } from "@/hooks/use-api";
import { request } from "@/services/api";
import type { Announcement } from "@/types/api";

type AdminAnn = Announcement & { audience: string; starts_at: string | null; status: string };

export default function Announcements() {
  const list = useApi<AdminAnn[]>("/superadmin/announcements");
  const [title, setTitle] = useState("");
  const [message, setMessage] = useState("");
  const [level, setLevel] = useState("info");
  const [audience, setAudience] = useState("all");
  const [starts, setStarts] = useState("");
  const [ends, setEnds] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [del, setDel] = useState<AdminAnn | null>(null);

  async function publish() {
    setError(null);
    try {
      await request("/superadmin/announcements", { method: "POST", body: { title, message, level, audience, starts_at: starts ? new Date(starts).toISOString() : null, ends_at: ends ? new Date(ends).toISOString() : null } });
      setTitle(""); setMessage(""); setStarts(""); setEnds("");
      await list.reload();
    } catch (e) { setError(e instanceof Error ? e.message : "Could not publish"); }
  }
  async function remove(a: AdminAnn) {
    setDel(null);
    try { await request(`/superadmin/announcements/${a.id}`, { method: "DELETE" }); await list.reload(); } catch (e) { setError(e instanceof Error ? e.message : "Could not delete"); }
  }

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-xl font-semibold">Announcements</h1>
      <Err message={error ?? list.error} />
      <Card>
        <CardHeader><CardTitle className="text-base">New announcement</CardTitle><CardDescription>Shown as a dismissible banner to the chosen audience between the start and end times (empty start = now, empty end = until deleted).</CardDescription></CardHeader>
        <CardContent className="flex flex-col gap-3">
          <Input placeholder="Title" value={title} maxLength={120} onChange={(e) => setTitle(e.target.value)} aria-label="Title" />
          <Textarea placeholder="Message" value={message} maxLength={1000} onChange={(e) => setMessage(e.target.value)} aria-label="Message" />
          <div className="flex flex-wrap gap-2">
            <Select value={level} onChange={(e) => setLevel(e.target.value)} className="w-40" aria-label="Level">
              <option value="info">Info</option><option value="warning">Warning</option><option value="success">Success</option>
            </Select>
            <Select value={audience} onChange={(e) => setAudience(e.target.value)} className="w-40" aria-label="Audience">
              <option value="all">Everyone</option><option value="jobseeker">Job seekers</option><option value="recruiter">Recruiters</option>
            </Select>
            <label className="flex items-center gap-2 text-xs text-muted-foreground">Starts<Input type="datetime-local" value={starts} onChange={(e) => setStarts(e.target.value)} className="w-52" aria-label="Start" /></label>
            <label className="flex items-center gap-2 text-xs text-muted-foreground">Ends<Input type="datetime-local" value={ends} onChange={(e) => setEnds(e.target.value)} className="w-52" aria-label="End" /></label>
            <Button disabled={!title.trim() || !message.trim()} onClick={() => void publish()}>Publish</Button>
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle className="text-base">Published</CardTitle></CardHeader>
        <CardContent className="flex flex-col gap-2">
          {(list.data ?? []).length === 0 && <p className="text-sm text-muted-foreground">No announcements.</p>}
          {(list.data ?? []).map((a) => (
            <div key={a.id} className="flex items-start justify-between gap-3 rounded-xl border p-3 text-sm">
              <div><p className="font-medium">{a.title} <span className="text-xs text-muted-foreground">· {a.level} · {a.audience} · {a.status}</span></p><p className="text-muted-foreground">{a.message}</p>
                <p className="mt-1 text-xs text-muted-foreground">{fmt(a.created_at)}{a.starts_at ? ` · starts ${fmt(a.starts_at)}` : ""}{a.expires_at ? ` · ends ${fmt(a.expires_at)}` : ""}</p></div>
              <Button size="icon" variant="ghost" onClick={() => setDel(a)} aria-label="Delete announcement"><Trash2 className="size-4" /></Button>
            </div>
          ))}
        </CardContent>
      </Card>
      {del && <ConfirmDialog title="Delete announcement?" body={`"${del.title}" will disappear for everyone.`} confirmLabel="Delete" onConfirm={() => void remove(del)} onCancel={() => setDel(null)} />}
    </div>
  );
}
