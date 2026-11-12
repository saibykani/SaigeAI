"use client";

import { Code2, HardDrive, Send } from "lucide-react";
import { useState } from "react";

import { Notice } from "@/components/app-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/form";
import { useApi } from "@/hooks/use-api";
import { request } from "@/services/api";

type Tg = { available: boolean; connected: boolean; name: string | null; bot: string | null; link: string | null };

/** Telegram alerts via the official Bot API: open the bot, press Start, confirm. */
export function TelegramCard() {
  const { data, setData } = useApi<Tg>("/integrations/telegram");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  async function run(path: string, method: "POST" | "DELETE") {
    setBusy(true);
    setErr(null);
    try { setData(await request<Tg>(path, { method })); } catch (e) { setErr(e instanceof Error ? e.message : "Telegram failed."); } finally { setBusy(false); }
  }
  return (
    <Card className="mb-6">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg"><Send className="size-5 text-primary" /> Telegram alerts {data?.connected && <Badge variant="success">Connected · {data.name}</Badge>}</CardTitle>
        <CardDescription>Free, instant alerts for new matches, replies, interviews and follow-ups, through Telegram&apos;s official bot API.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {err && <Notice tone="error">{err}</Notice>}
        {data && !data.available && <p className="text-muted-foreground">Not switched on for this server yet: the admin adds a Telegram bot token (TELEGRAM_BOT_TOKEN).</p>}
        {data?.available && !data.connected && (
          !data.link ? <Button onClick={() => void run("/integrations/telegram/start", "POST")} disabled={busy}>Connect Telegram</Button> : (
            <ol className="list-decimal space-y-2 pl-5">
              <li><a href={data.link} target="_blank" rel="noreferrer" className="text-primary underline">Open @{data.bot} in Telegram</a> and press <b>Start</b>.</li>
              <li>Come back and press <Button size="sm" onClick={() => void run("/integrations/telegram/confirm", "POST")} disabled={busy}>I pressed Start</Button></li>
            </ol>)
        )}
        {data?.connected && <Button variant="outline" size="sm" onClick={() => void run("/integrations/telegram", "DELETE")} disabled={busy}>Disconnect</Button>}
      </CardContent>
    </Card>
  );
}

/** Google Drive backup status (uses the Google sign-in; drive.file scope = only files Saige creates). */
export function DriveCard({ connected, onConnect }: { connected: boolean; onConnect: () => void }) {
  return (
    <Card className="mb-6">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg"><HardDrive className="size-5 text-primary" /> Google Drive backup {connected && <Badge variant="success">On</Badge>}</CardTitle>
        <CardDescription>Every resume you generate is saved as a PDF in a “Saige AI Resumes” folder in your own Drive. Saige can only see files it creates there.</CardDescription>
      </CardHeader>
      <CardContent className="text-sm">
        {connected ? <p className="text-muted-foreground">New ATS resumes are backed up automatically.</p>
          : <Button variant="outline" onClick={onConnect}>Sign in with Google to turn on</Button>}
      </CardContent>
    </Card>
  );
}

type Plan = {
  leetcode: { username: string; solved: number; easy: number; medium: number; hard: number; ranking: number | null };
  hackerrank: { name: string; stars: number }[]; practise: { topic: string; solved: number; url: string }[]; tip: string;
} | null;
type Coding = { usernames: { leetcode?: string; hackerrank?: string }; plan: Plan };

/** LeetCode / HackerRank public profiles: stats here, and a coding section in interview prep. */
export function CodingCard() {
  const { data, setData } = useApi<Coding>("/connectors/coding");
  const [lc, setLc] = useState("");
  const [hr, setHr] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  async function save() {
    setBusy(true);
    setErr(null);
    try {
      setData(await request<Coding>("/connectors/coding", { method: "PUT",
        body: { leetcode: (lc || data?.usernames.leetcode) || null, hackerrank: (hr || data?.usernames.hackerrank) || null } }));
    } catch (e) { setErr(e instanceof Error ? e.message : "Couldn't read the profile."); } finally { setBusy(false); }
  }
  const p = data?.plan;
  return (
    <Card className="mb-6">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg"><Code2 className="size-5 text-primary" /> Coding practice (LeetCode · HackerRank)</CardTitle>
        <CardDescription>Link your public profiles. Saige shows your progress and adds a coding plan (your weakest core topics) to every interview prep.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <div className="flex flex-wrap gap-2">
          <Input className="min-w-0 flex-1" value={lc} onChange={(e) => setLc(e.target.value)} placeholder={data?.usernames.leetcode ? `LeetCode: ${data.usernames.leetcode}` : "LeetCode username"} />
          <Input className="min-w-0 flex-1" value={hr} onChange={(e) => setHr(e.target.value)} placeholder={data?.usernames.hackerrank ? `HackerRank: ${data.usernames.hackerrank}` : "HackerRank username"} />
          <Button variant="outline" onClick={() => void save()} disabled={busy}>{busy ? "Reading…" : p ? "Refresh" : "Link"}</Button>
        </div>
        {err && <Notice tone="error">{err}</Notice>}
        {p && (
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-2xl border p-3">
              <p className="font-medium">LeetCode · {p.leetcode.solved} solved{p.leetcode.ranking ? ` · rank ${p.leetcode.ranking.toLocaleString()}` : ""}</p>
              <p className="text-muted-foreground">Easy {p.leetcode.easy} · Medium {p.leetcode.medium} · Hard {p.leetcode.hard}</p>
              {p.hackerrank.length > 0 && <p className="mt-1 text-muted-foreground">HackerRank: {p.hackerrank.map((b) => `${b.name} ${"★".repeat(b.stars)}`).join(" · ")}</p>}
            </div>
            <div className="rounded-2xl border p-3">
              <p className="font-medium">Practise next</p>
              {p.practise.map((t) => <a key={t.topic} href={t.url} target="_blank" rel="noreferrer" className="block text-primary hover:underline">{t.topic} ({t.solved} solved) →</a>)}
              <p className="mt-1 text-xs text-muted-foreground">{p.tip}</p>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
