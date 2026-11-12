"use client";

import { CalendarDays, Check, Copy, GitBranch, RefreshCw, Star } from "lucide-react";
import { useState } from "react";

import { Notice } from "@/components/app-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/form";
import { useApi } from "@/hooks/use-api";
import { request } from "@/services/api";

/** Private iCal feed of interviews and follow-ups to subscribe to in any calendar app. */
export function CalendarFeedCard() {
  const { data, setData } = useApi<{ url: string }>("/connectors/calendar");
  const [copied, setCopied] = useState(false);
  async function copy() {
    if (!data) return;
    await navigator.clipboard.writeText(data.url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }
  async function rotate() {
    setData(await request<{ url: string }>("/connectors/calendar/rotate", { method: "POST" }));
  }
  return (
    <Card className="mb-6">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg"><CalendarDays className="size-5 text-primary" /> Calendar: interviews &amp; follow-ups</CardTitle>
        <CardDescription>Subscribe once and every interview Saige finds in your email, plus follow-up dates, shows up in your calendar automatically. No calendar password needed.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap gap-2">
          <Input readOnly value={data?.url ?? "Creating your private link…"} className="min-w-0 flex-1 font-mono text-xs" onFocus={(e) => e.currentTarget.select()} />
          <Button variant="outline" onClick={() => void copy()} disabled={!data}>{copied ? <Check /> : <Copy />} {copied ? "Copied" : "Copy link"}</Button>
          <Button variant="ghost" onClick={() => void rotate()} title="Make a new link; the old one stops working"><RefreshCw /> New link</Button>
        </div>
        <ol className="list-decimal space-y-1 pl-5 text-sm text-muted-foreground">
          <li><b>Google Calendar:</b> Other calendars → + → <i>From URL</i> → paste → Add calendar.</li>
          <li><b>Outlook:</b> Add calendar → <i>Subscribe from web</i> → paste.</li>
          <li><b>iPhone / Mac:</b> Calendar → File → <i>New Calendar Subscription</i> → paste.</li>
        </ol>
        <p className="text-xs text-muted-foreground">Keep the link private: anyone with it can see your interview times. Use “New link” if you shared it by mistake.</p>
      </CardContent>
    </Card>
  );
}

type Repo = { name: string; description: string | null; language: string | null; topics: string[]; stars: number; url: string; in_profile: boolean };

/** Import public GitHub repositories as profile projects (your own repos, you pick which). */
export function GithubCard() {
  const [user, setUser] = useState("");
  const [repos, setRepos] = useState<Repo[] | null>(null);
  const [owner, setOwner] = useState("");
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ tone: "success" | "error"; text: string } | null>(null);

  async function load() {
    setBusy(true);
    setMsg(null);
    try {
      const r = await request<{ username: string; repos: Repo[] }>(`/connectors/github/repos${user ? `?username=${encodeURIComponent(user)}` : ""}`);
      setOwner(r.username);
      setRepos(r.repos);
      setPicked(new Set(r.repos.filter((x) => !x.in_profile).slice(0, 5).map((x) => x.name)));
    } catch (e) {
      setMsg({ tone: "error", text: e instanceof Error ? e.message : "Couldn't reach GitHub." });
    } finally {
      setBusy(false);
    }
  }
  async function importNow() {
    setBusy(true);
    try {
      const r = await request<{ added: string[] }>("/connectors/github/import", { method: "POST", body: { username: owner, repos: [...picked] } });
      setMsg({ tone: "success", text: r.added.length ? `Added to your Profile projects: ${r.added.join(", ")}. They now feed your resumes and interview prep.` : "These projects are already in your profile." });
      await load();
    } catch (e) {
      setMsg({ tone: "error", text: e instanceof Error ? e.message : "Import failed." });
    } finally {
      setBusy(false);
    }
  }
  return (
    <Card className="mb-6">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg"><GitBranch className="size-5 text-primary" /> GitHub projects</CardTitle>
        <CardDescription>Bring your public repositories into your Profile as projects (name, description, language, topics, link). Resumes, the ATS coach and interview prep then use them.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <form className="flex flex-wrap gap-2" onSubmit={(e) => { e.preventDefault(); void load(); }}>
          <Input value={user} onChange={(e) => setUser(e.target.value)} placeholder="GitHub username (blank = from your Profile)" className="min-w-0 flex-1" />
          <Button type="submit" variant="outline" disabled={busy}>{busy && !repos ? "Loading…" : "Show my repositories"}</Button>
        </form>
        {msg && <Notice tone={msg.tone}>{msg.text}</Notice>}
        {repos && repos.length === 0 && <p className="text-sm text-muted-foreground">No public, non-fork repositories found for {owner}.</p>}
        {repos && repos.length > 0 && (
          <>
            <ul className="max-h-80 divide-y overflow-y-auto rounded-2xl border">
              {repos.map((r) => (
                <li key={r.name}>
                  <label className="flex cursor-pointer items-start gap-3 p-3 text-sm">
                    <input type="checkbox" className="mt-1 size-4 accent-[var(--primary)]" disabled={r.in_profile} checked={r.in_profile || picked.has(r.name)}
                      onChange={(e) => setPicked((s) => { const n = new Set(s); if (e.target.checked) n.add(r.name); else n.delete(r.name); return n; })} />
                    <span className="min-w-0 flex-1">
                      <span className="flex flex-wrap items-center gap-2 font-medium">
                        {r.name}{r.language && <Badge variant="outline">{r.language}</Badge>}
                        {r.stars > 0 && <span className="inline-flex items-center gap-0.5 text-xs text-muted-foreground"><Star className="size-3" />{r.stars}</span>}
                        {r.in_profile && <Badge variant="success">In profile</Badge>}
                      </span>
                      {r.description && <span className="block text-muted-foreground">{r.description}</span>}
                    </span>
                  </label>
                </li>
              ))}
            </ul>
            <Button onClick={() => void importNow()} disabled={busy || picked.size === 0}>Add {picked.size} to my Profile</Button>
          </>
        )}
      </CardContent>
    </Card>
  );
}
