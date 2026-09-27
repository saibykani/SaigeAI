"use client";

import { CalendarDays, Download, ExternalLink, Flame, Link2, Loader2, Pencil, Send, Sparkles, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

import { Notice, PageHeader } from "@/components/app-shell";
import { Loader3D } from "@/components/loader3d";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Select, Textarea } from "@/components/ui/form";
import { useApi } from "@/hooks/use-api";
import { request } from "@/services/api";
import { cn } from "@/utils/cn";
import { formatDateTime } from "@/utils/format";

type Settings = { enabled: boolean; auto_publish: boolean; time: string; days: number[]; series: string[]; topics: string[];
  format: "auto" | "text" | "image" | "carousel"; tone: string; hashtags: number; emojis: boolean; disclaimer: string };
type Status = { app_configured: boolean; connected: boolean; name: string | null; expires_at: string | null; settings: Settings; streak: number; published: number };
type Post = { id: string; date: string; series: string; theme: string; skill: string | null; title: string; text: string; format: string;
  status: "draft" | "ready" | "published" | "failed"; url: string | null; share_url: string | null; engine: string; error: string | null;
  stats: { reactions?: number; comments?: number; impressions?: number }; created_at: string; published_at: string | null };

const SERIES: [string, string][] = [["tip", "Tip of the day"], ["mistake", "Common mistake"], ["checklist", "Checklist"],
  ["interview", "Interview question"], ["tool", "Tool spotlight"], ["learned", "What I'm learning"], ["career", "Career note"]];
const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const STATUS: Record<Post["status"], { label: string; tone: string }> = {
  published: { label: "Posted", tone: "green" }, ready: { label: "Ready to post", tone: "yellow" },
  draft: { label: "Draft", tone: "purple" }, failed: { label: "Failed", tone: "red" },
};

function Media({ post }: { post: Post }) {
  const [media, setMedia] = useState<{ url: string; kind: "image" | "pdf" } | null>(null);
  useEffect(() => {
    if (post.format === "text") return;
    let u: string | null = null;
    void request<Response>(`/linkedin/posts/${post.id}/media`, { raw: true }).then(async (r) => {
      const blob = await r.blob();
      u = URL.createObjectURL(blob);
      setMedia({ url: u, kind: blob.type.startsWith("image/") ? "image" : "pdf" });
    });
    return () => { if (u) URL.revokeObjectURL(u); };
  }, [post.id, post.format]);
  if (post.format === "text") return null;
  if (!media) return <div className="skeleton aspect-[4/5] rounded-2xl" />;
  // eslint-disable-next-line @next/next/no-img-element -- generated post image
  if (media.kind === "image") return <img src={media.url} alt={post.title} className="w-full rounded-2xl border" />;
  return (
    <div className="flex flex-col gap-2">
      <iframe src={`${media.url}#toolbar=0&view=FitH`} title={post.title} className="aspect-[4/5] w-full rounded-2xl border bg-black" />
      <a href={media.url} download={`saige-${post.date}.pdf`} className="inline-flex items-center justify-center gap-1.5 text-xs text-muted-foreground hover:text-foreground">
        <Download className="size-3.5" /> {post.format === "carousel" ? "Carousel" : "Slide"} PDF
      </a>
    </div>
  );
}

function PostCard({ post, onChange }: { post: Post; onChange: () => void }) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(post.text);
  const [busy, setBusy] = useState(false);
  const [stats, setStats] = useState({ reactions: post.stats.reactions ?? "", comments: post.stats.comments ?? "", impressions: post.stats.impressions ?? "" });
  const st = STATUS[post.status];
  async function act(fn: () => Promise<unknown>) { setBusy(true); try { await fn(); onChange(); } finally { setBusy(false); } }
  return (
    <Card className="animate-rise overflow-hidden" style={{ borderColor: `color-mix(in srgb, var(--tone-${st.tone}) 30%, transparent)` }}>
      <CardContent className="grid gap-4 p-5 md:grid-cols-[1fr_260px]">
        <div className="flex min-w-0 flex-col gap-3">
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className="rounded-full px-2.5 py-0.5 font-semibold text-[#0b0b0c]" style={{ background: `var(--tone-${st.tone})` }}>{st.label}</span>
            <span className="rounded-full border px-2 py-0.5">{post.series}</span>
            <span className="rounded-full border px-2 py-0.5 capitalize">{post.format}</span>
            {post.skill && <span className="rounded-full border px-2 py-0.5">{post.skill}</span>}
            <span className="ml-auto text-muted-foreground">{post.published_at ? `Posted ${formatDateTime(post.published_at)}` : post.date}</span>
          </div>
          {editing ? <Textarea rows={10} value={text} onChange={(e) => setText(e.target.value)} maxLength={2900} />
            : <p className="whitespace-pre-wrap text-sm leading-relaxed">{post.text}</p>}
          {post.error && <Notice tone="error">{post.error}</Notice>}
          <div className="flex flex-wrap gap-2">
            {post.status !== "published" && (
              <Button size="sm" disabled={busy} onClick={() => act(() => request(`/linkedin/posts/${post.id}/publish`, { method: "POST" }))}>
                {busy ? <Loader2 className="animate-spin" /> : <Send />} Publish on LinkedIn
              </Button>
            )}
            {post.share_url && <a href={post.share_url} target="_blank" rel="noopener noreferrer" className={buttonVariants({ size: "sm", variant: "outline" })}><ExternalLink /> Post manually</a>}
            {post.url && <a href={post.url} target="_blank" rel="noopener noreferrer" className={buttonVariants({ size: "sm", variant: "outline" })}><ExternalLink /> View on LinkedIn</a>}
            {post.status !== "published" && (editing
              ? <Button size="sm" variant="outline" onClick={() => act(async () => { await request(`/linkedin/posts/${post.id}`, { method: "PUT", body: { text } }); setEditing(false); })}>Save</Button>
              : <Button size="sm" variant="ghost" onClick={() => setEditing(true)}><Pencil /> Edit</Button>)}
            <Button size="sm" variant="ghost" onClick={() => { if (confirm("Delete this post from Saige?")) void act(() => request(`/linkedin/posts/${post.id}`, { method: "DELETE" })); }}><Trash2 /></Button>
          </div>
          {post.status === "published" && (
            <form className="flex flex-wrap items-center gap-2 text-xs" onSubmit={(e) => { e.preventDefault(); void act(() => request(`/linkedin/posts/${post.id}/stats`, { method: "POST", body: Object.fromEntries(Object.entries(stats).filter(([, v]) => v !== "").map(([k, v]) => [k, Number(v)])) })); }}>
              <span className="text-muted-foreground">Track:</span>
              {(["reactions", "comments", "impressions"] as const).map((k) => (
                <Input key={k} type="number" min={0} className="h-8 w-28" placeholder={k} value={stats[k]} onChange={(e) => setStats({ ...stats, [k]: e.target.value })} />
              ))}
              <Button size="sm" variant="outline" type="submit">Save stats</Button>
            </form>
          )}
        </div>
        <Media post={post} />
      </CardContent>
    </Card>
  );
}

export default function LinkedInPostsPage() {
  const status = useApi<Status>("/linkedin/status");
  const posts = useApi<Post[]>("/linkedin/posts");
  const [s, setS] = useState<Settings | null>(null);
  const [msg, setMsg] = useState<{ tone: "success" | "error" | "info"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (status.data) setS(status.data.settings); }, [status.data]);
  useEffect(() => {
    const q = new URLSearchParams(window.location.search);
    if (q.get("connected")) setMsg({ tone: "success", text: "LinkedIn connected. Daily posts will now publish automatically." });
    if (q.get("error")) setMsg({ tone: "error", text: "LinkedIn didn't connect. Try again." });
  }, []);

  async function save(patch: Partial<Settings>) {
    if (!s) return;
    const next = { ...s, ...patch };
    setS(next);
    await request("/automation/settings", { method: "PUT", body: { linkedin_posts: next } });
    await status.reload();
  }
  async function connect() {
    try { window.location.href = (await request<{ url: string }>("/linkedin/connect")).url; }
    catch (e) { setMsg({ tone: "info", text: e instanceof Error ? e.message : "Couldn't connect" }); }
  }
  const reload = () => { void posts.reload(); void status.reload(); };

  if (!status.data || !s) return <div className="grid place-items-center py-24"><Loader3D size={64} /></div>;
  const st = status.data;
  const byDate = new Map((posts.data ?? []).filter((p) => p.status === "published").map((p) => [p.date, p]));
  const days = Array.from({ length: 28 }, (_, i) => { const d = new Date(); d.setDate(d.getDate() - (27 - i)); return d.toISOString().slice(0, 10); });

  return (
    <>
      <PageHeader title="LinkedIn Posts" description="Your daily LinkedIn presence on autopilot: a post every day from your role and verified skills, with a designed image or carousel, hashtags and your disclaimer, published through LinkedIn's official API and tracked day by day." />
      {msg && <div className="mb-4"><Notice tone={msg.tone}>{msg.text}</Notice></div>}

      <div className="mb-6 grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2" style={{ borderColor: "color-mix(in srgb, var(--tone-teal) 30%, transparent)" }}>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg"><Link2 className="size-4" style={{ color: "var(--tone-teal)" }} /> LinkedIn connection</CardTitle>
            <CardDescription>
              {st.connected ? <>Connected as <b>{st.name}</b>. Posts publish automatically.</>
                : st.app_configured ? "Connect once with LinkedIn's official sign-in. Saige can then publish your posts; it can't read your messages or change your profile."
                : "Automatic publishing needs the server's LinkedIn app keys (see Help → LinkedIn Posts). Until then, each post is prepared with its image and a one-click “Post manually” button."}
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            {st.connected
              ? <Button variant="outline" onClick={async () => { await request("/linkedin/connection", { method: "DELETE" }); reload(); }}>Disconnect</Button>
              : <Button onClick={connect} disabled={!st.app_configured}>Connect LinkedIn</Button>}
            <Button variant="outline" disabled={busy} onClick={async () => { setBusy(true); try { await request("/linkedin/posts/generate", { method: "POST" }); reload(); } finally { setBusy(false); } }}>
              {busy ? <Loader2 className="animate-spin" /> : <Sparkles />} Write a post now
            </Button>
          </CardContent>
        </Card>
        <Card style={{ borderColor: "color-mix(in srgb, var(--tone-orange) 30%, transparent)" }}>
          <CardHeader className="pb-2"><CardTitle className="flex items-center gap-2 text-lg"><Flame className="size-4" style={{ color: "var(--tone-orange)" }} /> {st.streak}-day streak</CardTitle>
            <CardDescription>{st.published} post(s) published · last 4 weeks</CardDescription></CardHeader>
          <CardContent>
            <div className="grid grid-cols-7 gap-1.5">
              {days.map((d) => <span key={d} title={d} className="aspect-square rounded-md" style={{ background: byDate.has(d) ? "var(--tone-green)" : "var(--muted)" }} />)}
            </div>
          </CardContent>
        </Card>
      </div>

      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg"><CalendarDays className="size-4" /> Posting agent</CardTitle>
          <CardDescription>Saige writes and posts at this time on the chosen days. Content uses only your verified profile: no invented results.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4 text-sm">
          <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
            <label className="inline-flex items-center gap-2 font-medium"><input type="checkbox" className="size-4 accent-[var(--tone-teal)]" checked={s.enabled} onChange={(e) => save({ enabled: e.target.checked })} /> Post every day</label>
            <label className="inline-flex items-center gap-2"><input type="checkbox" className="size-4 accent-[var(--tone-teal)]" checked={s.auto_publish} onChange={(e) => save({ auto_publish: e.target.checked })} /> Publish automatically (no review)</label>
            <label className="inline-flex items-center gap-2">Time <Input type="time" className="h-8 w-32" value={s.time} onChange={(e) => save({ time: e.target.value })} /></label>
            <label className="inline-flex items-center gap-2">Format
              <Select className="h-8 w-40" value={s.format} onChange={(e) => save({ format: e.target.value as Settings["format"] })}>
                <option value="auto">Rotate (image · carousel · text)</option><option value="image">Image card</option><option value="carousel">Carousel (PDF)</option><option value="text">Text only</option>
              </Select>
            </label>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {DAYS.map((d, i) => (
              <button key={d} type="button" onClick={() => save({ days: s.days.includes(i) ? s.days.filter((x) => x !== i) : [...s.days, i].sort() })}
                className={cn("rounded-full border px-3 py-1 text-xs", s.days.includes(i) && "border-transparent font-semibold text-[#0b0b0c]")}
                style={s.days.includes(i) ? { background: "var(--tone-teal)" } : undefined}>{d}</button>
            ))}
          </div>
          <div>
            <p className="mb-1.5 font-medium">Series (rotates daily)</p>
            <div className="flex flex-wrap gap-1.5">
              {SERIES.map(([id, label]) => (
                <button key={id} type="button" onClick={() => save({ series: s.series.includes(id) ? s.series.filter((x) => x !== id) : [...s.series, id] })}
                  className={cn("rounded-full border px-3 py-1 text-xs", s.series.includes(id) && "border-transparent font-semibold text-[#0b0b0c]")}
                  style={s.series.includes(id) ? { background: "var(--tone-purple)" } : undefined}>{label}</button>
              ))}
            </div>
          </div>
          <div className="grid gap-3 md:grid-cols-3">
            <label className="flex flex-col gap-1">Topics (comma-separated; empty = your skills)
              <Input defaultValue={s.topics.join(", ")} onBlur={(e) => save({ topics: e.target.value.split(",").map((x) => x.trim()).filter(Boolean) })} placeholder="Selenium, API testing, Playwright" />
            </label>
            <label className="flex flex-col gap-1">Tone <Input defaultValue={s.tone} onBlur={(e) => save({ tone: e.target.value })} /></label>
            <label className="flex flex-col gap-1">Disclaimer (added at the end)
              <Input defaultValue={s.disclaimer} onBlur={(e) => save({ disclaimer: e.target.value })} placeholder="Views are my own." />
            </label>
          </div>
          <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
            <label className="inline-flex items-center gap-2">Hashtags
              <Select className="h-8 w-20" value={s.hashtags} onChange={(e) => save({ hashtags: Number(e.target.value) })}>{[0, 3, 5, 7, 10].map((n) => <option key={n} value={n}>{n}</option>)}</Select>
            </label>
            <label className="inline-flex items-center gap-2"><input type="checkbox" className="size-4" checked={s.emojis} onChange={(e) => save({ emojis: e.target.checked })} /> Emojis</label>
          </div>
        </CardContent>
      </Card>

      <h2 className="mb-3 text-lg font-semibold">Posts · day by day</h2>
      {!posts.data ? <div className="skeleton h-64 rounded-3xl" /> : posts.data.length === 0
        ? <Card className="p-8 text-center text-sm text-muted-foreground">No posts yet. Click “Write a post now”, or turn on “Post every day”.</Card>
        : <div className="flex flex-col gap-4">{posts.data.map((p) => <PostCard key={p.id} post={p} onChange={reload} />)}</div>}
      <p className="mt-6 text-xs text-muted-foreground">
        Comments: LinkedIn doesn&apos;t let apps read comments without partner approval. Open your post on LinkedIn and use the Saige extension → “Draft replies” to answer each comment in one click.
      </p>
    </>
  );
}
