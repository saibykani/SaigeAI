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

export default function Announcements() {
  const list = useApi<Announcement[]>("/superadmin/announcements");
  const [title, setTitle] = useState("");
  const [message, setMessage] = useState("");
  const [level, setLevel] = useState("info");
  const [days, setDays] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [del, setDel] = useState<Announcement | null>(null);

  async function publish() {
    setError(null);
    try {
      await request("/superadmin/announcements", { method: "POST", body: { title, message, level, expires_in_days: days ? Number(days) : null } });
      setTitle(""); setMessage(""); setDays("");
      await list.reload();
    } catch (e) { setError(e instanceof Error ? e.message : "Could not publish"); }
  }
  async function remove(a: Announcement) {
    setDel(null);
    try { await request(`/superadmin/announcements/${a.id}`, { method: "DELETE" }); await list.reload(); } catch (e) { setError(e instanceof Error ? e.message : "Could not delete"); }
  }

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold">Announcements</h1>
      <Err message={error ?? list.error} />
      <Card>
        <CardHeader><CardTitle className="text-base">New announcement</CardTitle><CardDescription>Shown to every user as a dismissible banner.</CardDescription></CardHeader>
        <CardContent className="flex flex-col gap-3">
          <Input placeholder="Title" value={title} maxLength={120} onChange={(e) => setTitle(e.target.value)} aria-label="Title" />
          <Textarea placeholder="Message" value={message} maxLength={1000} onChange={(e) => setMessage(e.target.value)} aria-label="Message" />
          <div className="flex flex-wrap gap-2">
            <Select value={level} onChange={(e) => setLevel(e.target.value)} className="w-40" aria-label="Level">
              <option value="info">Info</option><option value="warning">Warning</option><option value="success">Success</option>
            </Select>
            <Input type="number" min={1} max={365} placeholder="Expires in days (optional)" value={days} onChange={(e) => setDays(e.target.value)} className="w-64" aria-label="Expires in days" />
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
              <div><p className="font-medium">{a.title} <span className="text-xs text-muted-foreground">· {a.level}</span></p><p className="text-muted-foreground">{a.message}</p>
                <p className="mt-1 text-xs text-muted-foreground">{fmt(a.created_at)}{a.expires_at ? ` · expires ${fmt(a.expires_at)}` : ""}</p></div>
              <Button size="icon" variant="ghost" onClick={() => setDel(a)} aria-label="Delete announcement"><Trash2 className="size-4" /></Button>
            </div>
          ))}
        </CardContent>
      </Card>
      {del && <ConfirmDialog title="Delete announcement?" body={`"${del.title}" will disappear for everyone.`} confirmLabel="Delete" onConfirm={() => void remove(del)} onCancel={() => setDel(null)} />}
    </div>
  );
}
