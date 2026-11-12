"use client";

import { Check, Copy, Download, ExternalLink, Eye, Globe, Laptop, Smartphone, Sparkles } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Notice, PageHeader } from "@/components/app-shell";
import { ScanLoader } from "@/components/scan-loader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input } from "@/components/ui/form";
import { useApi } from "@/hooks/use-api";
import { downloadFile, request } from "@/services/api";
import { cn } from "@/utils/cn";

type Template = { id: string; name: string; vibe: string; colors: string[] };
type Settings = { template: string; slug: string; published: boolean; tagline: string; show_email: boolean; show_phone: boolean; open_to_work: boolean; views: number; published_at: string | null };

export default function PortfolioPage() {
  const templates = useApi<Template[]>("/portfolio/templates");
  const saved = useApi<Settings>("/portfolio");
  const [s, setS] = useState<Settings | null>(null);
  const [html, setHtml] = useState("");
  const [device, setDevice] = useState<"desktop" | "mobile">("desktop");
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const [msg, setMsg] = useState<{ tone: "success" | "error" | "info"; text: string } | null>(null);

  useEffect(() => { if (saved.data && !s) setS(saved.data); }, [saved.data, s]);
  const origin = typeof window === "undefined" ? "" : window.location.origin;
  const url = s ? `${origin}/p/${s.slug}` : "";

  const loadPreview = useCallback(async (st: Settings) => {
    const q = new URLSearchParams({ template: st.template, tagline: st.tagline, show_email: String(st.show_email), show_phone: String(st.show_phone), open_to_work: String(st.open_to_work) });
    const res = await request<Response>(`/portfolio/preview?${q}`, { raw: true });
    setHtml(await res.text());
  }, []);
  // Re-render the preview shortly after any change (typing the tagline doesn't refetch on every key).
  useEffect(() => {
    if (!s) return;
    const t = setTimeout(() => void loadPreview(s).catch(() => undefined), 350);
    return () => clearTimeout(t);
  }, [s, loadPreview]);

  const current = useMemo(() => templates.data?.find((t) => t.id === s?.template), [templates.data, s?.template]);
  const body = s && { template: s.template, slug: s.slug, tagline: s.tagline, show_email: s.show_email, show_phone: s.show_phone, open_to_work: s.open_to_work };

  async function act(kind: "save" | "publish" | "unpublish") {
    if (!s) return;
    setBusy(true);
    setMsg(null);
    try {
      const r = kind === "save" ? await request<Settings>("/portfolio", { method: "PUT", body })
        : kind === "publish" ? await request<Settings>("/portfolio/publish", { method: "POST", body })
        : await request<Settings>("/portfolio/unpublish", { method: "POST" });
      setS(r);
      setMsg({ tone: "success", text: kind === "publish" ? "Your portfolio is live. Share the link on LinkedIn, your resume and email signature." : kind === "save" ? "Saved." : "Unpublished: the link no longer works." });
    } catch (e) {
      setMsg({ tone: "error", text: e instanceof Error ? e.message : "Something went wrong." });
    } finally {
      setBusy(false);
    }
  }
  async function copy() {
    await navigator.clipboard.writeText(url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  if (!s || !templates.data) return <div className="skeleton h-96 rounded-3xl" />;

  return (
    <>
      <PageHeader title="Portfolio" description="Turn your verified profile into a personal website in one click. Pick a template, preview it with your own data, and publish it to your own link."
        actions={s.published ? <Badge variant="success" className="h-8 px-3"><Globe className="size-3.5" /> Live · {s.views} views</Badge> : <Badge variant="outline" className="h-8 px-3">Not published</Badge>} />
      {msg && <div className="mb-4"><Notice tone={msg.tone}>{msg.text}</Notice></div>}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-6">
          {/* Live preview */}
          <Card className="overflow-hidden">
            <div className="flex flex-wrap items-center gap-3 border-b px-5 py-3">
              <div className="flex gap-1.5"><i className="size-3 rounded-full bg-[#ff5f56]" /><i className="size-3 rounded-full bg-[#ffbd2e]" /><i className="size-3 rounded-full bg-[#27c93f]" /></div>
              <span className="min-w-0 flex-1 truncate rounded-full bg-muted px-3 py-1 font-mono text-xs text-muted-foreground">{url}</span>
              <div className="inline-flex rounded-full border p-0.5">
                {(["desktop", "mobile"] as const).map((d) => (
                  <button key={d} onClick={() => setDevice(d)} aria-pressed={device === d} className={cn("rounded-full px-3 py-1", device === d && "bg-primary text-primary-foreground")}>
                    {d === "desktop" ? <Laptop className="size-4" /> : <Smartphone className="size-4" />}
                  </button>
                ))}
              </div>
            </div>
            <div className="flex justify-center bg-muted/40 p-4">
              {!html ? <ScanLoader title="Building your website" messages={["Reading your profile…", "Laying out your story…", "Adding animations…", "Styling the template…"]} /> :
              <iframe title="Portfolio preview" srcDoc={html} sandbox="allow-scripts allow-popups" className={cn("h-[640px] rounded-xl border bg-white shadow-sm transition-all", device === "desktop" ? "w-full" : "w-[390px]")} />}
            </div>
          </Card>

          {/* Template gallery */}
          <section>
            <div className="mb-3 flex items-baseline justify-between">
              <h2 className="text-xl">Templates <span className="text-sm text-muted-foreground">· {templates.data.length}</span></h2>
              {current && <span className="text-sm text-muted-foreground">Selected: <b className="text-foreground">{current.name}</b></span>}
            </div>
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {templates.data.map((t) => (
                <button key={t.id} onClick={() => setS({ ...s, template: t.id })} aria-pressed={s.template === t.id}
                  className={cn("group overflow-hidden rounded-2xl border bg-card text-left transition-shadow hover:shadow-md", s.template === t.id && "ring-2 ring-primary")}>
                  <div className="relative h-24" style={{ background: t.colors[0] }}>
                    <span className="absolute left-4 top-4 h-3 w-24 rounded-full" style={{ background: t.colors[1] }} />
                    <span className="absolute left-4 top-10 h-2 w-36 rounded-full opacity-70" style={{ background: t.colors[2] }} />
                    <span className="absolute bottom-3 right-3 size-9 rounded-xl" style={{ background: t.colors[1] }} />
                    {s.template === t.id && <span className="absolute right-3 top-3 grid size-6 place-items-center rounded-full bg-primary text-primary-foreground"><Check className="size-3.5" /></span>}
                  </div>
                  <div className="p-3">
                    <p className="font-medium">{t.name}</p>
                    <p className="text-xs text-muted-foreground">{t.vibe}</p>
                  </div>
                </button>
              ))}
            </div>
          </section>
        </div>

        {/* Settings & publish */}
        <div className="space-y-6 xl:sticky xl:top-24 xl:self-start">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2"><Sparkles className="size-5 text-primary" /> Publish</CardTitle>
              <CardDescription>Your site updates by itself whenever you change your Profile.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Field label="Your link">
                <div className="flex items-center rounded-xl border bg-card pl-3 text-sm">
                  <span className="shrink-0 text-muted-foreground">{origin.replace(/^https?:\/\//, "")}/p/</span>
                  <input value={s.slug} onChange={(e) => setS({ ...s, slug: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "") })} maxLength={40}
                    className="h-10 min-w-0 flex-1 bg-transparent px-1 outline-none" aria-label="Link name" />
                </div>
              </Field>
              <Field label="Tagline (optional)" hint="A line under your name, e.g. “I make releases boring (in a good way)”.">
                <Input value={s.tagline} maxLength={160} onChange={(e) => setS({ ...s, tagline: e.target.value })} />
              </Field>
              <div className="space-y-2 text-sm">
                {([["show_email", "Show my email"], ["show_phone", "Show my phone number"], ["open_to_work", "Show “Open to opportunities”"]] as const).map(([k, l]) => (
                  <label key={k} className="flex items-center gap-2"><input type="checkbox" className="size-4 accent-[var(--primary)]" checked={s[k]} onChange={(e) => setS({ ...s, [k]: e.target.checked })} /> {l}</label>
                ))}
              </div>
              <div className="flex flex-wrap gap-2">
                <Button size="lg" onClick={() => void act("publish")} disabled={busy}><Globe /> {s.published ? "Update live site" : "Publish my portfolio"}</Button>
                <Button variant="outline" onClick={() => void act("save")} disabled={busy}>Save draft</Button>
              </div>
              {s.published && (
                <div className="space-y-2 rounded-2xl border bg-accent/40 p-3 text-sm">
                  <p className="font-medium">Live at</p>
                  <a href={url} target="_blank" rel="noreferrer" className="block truncate text-primary underline">{url}</a>
                  <div className="flex flex-wrap gap-2">
                    <Button size="sm" variant="outline" onClick={() => void copy()}>{copied ? <Check /> : <Copy />} {copied ? "Copied" : "Copy link"}</Button>
                    <a href={url} target="_blank" rel="noreferrer"><Button size="sm" variant="outline"><ExternalLink /> Open</Button></a>
                    <Button size="sm" variant="ghost" onClick={() => void act("unpublish")} disabled={busy}>Unpublish</Button>
                  </div>
                  <p className="flex items-center gap-1 text-xs text-muted-foreground"><Eye className="size-3.5" /> {s.views} visits since publishing</p>
                </div>
              )}
              <Button variant="ghost" size="sm" onClick={() => void downloadFile("/portfolio/download", "index.html")}><Download /> Download HTML (host it anywhere)</Button>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="space-y-2 pt-5 text-sm text-muted-foreground">
              <p className="font-medium text-foreground">What goes on your site</p>
              <p>Only what&apos;s in your verified <Link href="/profile" className="text-primary underline">Profile</Link>: name, role, summary, skills, experience, projects, education and links. Nothing is invented.</p>
              <p>Want more on it? Add projects (or import them from GitHub in Integrations) and they appear instantly.</p>
            </CardContent>
          </Card>
        </div>
      </div>
    </>
  );
}
