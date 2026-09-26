"use client";

import { AppWindow, Bookmark, Briefcase, CalendarDays, Check, Globe, Link2, Mail, Sparkles, Unplug, UserRound } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";

import { Notice, PageHeader } from "@/components/app-shell";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useApi } from "@/hooks/use-api";
import { request } from "@/services/api";
import type { Integrations } from "@/types/api";
import { formatDateTime } from "@/utils/format";

type Tile = {
  name: string;
  icon: typeof Mail;
  status: { label: string; tone: "success" | "muted" | "warning" | "default" };
  body: string;
  action?: React.ReactNode;
};

function bookmarkletFor(origin: string): string {
  // Opens Saige's capture page, then hands over the posting you are looking at via postMessage.
  // Runs only when you click it, on the page you chose - it never visits sites by itself.
  const code = `(()=>{const d={type:'saige-job',url:location.href,title:document.title,text:(String(getSelection()||'').trim()||document.body.innerText).slice(0,40000)};const w=window.open('${origin}/jobs/capture','_blank');if(!w)return alert('Allow pop-ups to save this job to Saige AI');const h=e=>{if(e.origin==='${origin}'&&e.data==='saige-ready'){w.postMessage(d,'${origin}');removeEventListener('message',h)}};addEventListener('message',h)})()`;
  return `javascript:${encodeURIComponent(code)}`;
}

export default function IntegrationsPage() {
  const { data, error, reload } = useApi<Integrations>("/integrations");
  const [origin, setOrigin] = useState("");
  const [msg, setMsg] = useState<{ tone: "success" | "error" | "warning"; text: string } | null>(null);

  useEffect(() => {
    setOrigin(window.location.origin);
    const p = new URLSearchParams(window.location.search).get("gmail");
    if (p === "error") setMsg({ tone: "error", text: "Gmail connection failed or was cancelled." });
    if (p === "scope") setMsg({ tone: "warning", text: "Gmail access wasn't granted. Tick the Gmail permission on Google's consent screen and try again." });
  }, []);
  const bookmarklet = useMemo(() => (origin ? bookmarkletFor(origin) : "#"), [origin]);
  const linkRef = useRef<HTMLAnchorElement>(null);
  // React blocks javascript: URLs in JSX, so the bookmarklet href is set directly on the element.
  useEffect(() => { if (linkRef.current && origin) linkRef.current.setAttribute("href", bookmarklet); }, [bookmarklet, origin]);

  if (error) return <Notice tone="error">{error}</Notice>;
  if (!data) return <div className="skeleton h-96 rounded-3xl" />;

  const connectGmail = async () => {
    const r = await request<{ url: string }>("/auth/connect/gmail", { method: "POST" });
    window.location.href = r.url;
  };
  const disconnectGmail = async () => {
    if (!confirm("Disconnect Gmail? Saige will revoke its access. Imported emails are kept unless you delete them in Privacy.")) return;
    await request("/auth/connect/gmail", { method: "DELETE" });
    setMsg({ tone: "success", text: "Gmail disconnected and access revoked." });
    await reload();
  };

  const tiles: Tile[] = [
    {
      name: "Gmail", icon: Mail,
      status: data.gmail.connected ? { label: "Connected", tone: "success" } : { label: "Not connected", tone: "muted" },
      body: data.gmail.connected
        ? `Reading job-search mail for ${data.gmail.email}. ${data.gmail.last_sync_at ? `Last sync ${formatDateTime(data.gmail.last_sync_at)}.` : ""}`
        : "Detect confirmations, interviews, assessments, rejections and offers; update applications automatically. Read-only.",
      action: data.gmail.connected
        ? <div className="flex gap-2"><Link href="/inbox" className={buttonVariants({ size: "sm" })}>Open inbox</Link><Button size="sm" variant="ghost" onClick={disconnectGmail}><Unplug /> Disconnect</Button></div>
        : <Button size="sm" disabled={!data.gmail.available} onClick={connectGmail}><Link2 /> Connect</Button>,
    },
    {
      name: "Google sign-in", icon: Globe,
      status: data.google.connected ? { label: "Linked", tone: "success" } : { label: data.google.available ? "Available" : "Not configured", tone: "muted" },
      body: "Sign in with your Google account. Sessions last 30 days and renew as you use Saige.",
    },
    {
      name: "LinkedIn", icon: UserRound,
      status: { label: data.linkedin.snapshot ? "Profile added" : "Add your profile", tone: data.linkedin.snapshot ? "success" : "warning" },
      body: "Daily headline, About and skills suggestions from real job descriptions, truth-checked. LinkedIn offers no profile-edit API, so changes are copy-ready.",
      action: <Link href="/profiles?tab=linkedin" className={buttonVariants({ size: "sm", variant: "outline" })}>Manage profile</Link>,
    },
    {
      name: "Naukri", icon: UserRound,
      status: { label: data.naukri.snapshot ? "Profile added" : "Add your profile", tone: data.naukri.snapshot ? "success" : "warning" },
      body: "Resume headline, key skills and summary tuned to your target roles, plus resume-freshness reminders. Copy-ready updates — no login automation.",
      action: <Link href="/profiles?tab=naukri" className={buttonVariants({ size: "sm", variant: "outline" })}>Manage profile</Link>,
    },
    {
      name: "Greenhouse · Lever · Ashby", icon: Briefcase,
      status: { label: `${data.ats_boards.count} board(s) followed`, tone: data.ats_boards.count ? "success" : "muted" },
      body: "Follow companies' official job boards. New postings are fetched, analyzed, scored and de-duplicated.",
      action: <Link href="/jobs" className={buttonVariants({ size: "sm", variant: "outline" })}>Manage boards</Link>,
    },
    {
      name: "Indeed · Naukri · LinkedIn jobs", icon: AppWindow,
      status: { label: "Via capture", tone: "default" },
      body: "These sites don't allow automated access. Use “Save to Saige” below on any posting you're viewing, or paste the description in Jobs.",
    },
    {
      name: "Chrome extension", icon: AppWindow,
      status: { label: "Recommended", tone: "success" },
      body: "Score the job you're viewing, save it in one click, and copy your prepared answers. Reads only the tab you click it on.",
      action: <Link href="/settings#extension" className={buttonVariants({ size: "sm", variant: "outline" })}>Set up</Link>,
    },
    {
      name: "Calendar", icon: CalendarDays,
      status: { label: "Export", tone: "default" },
      body: "Add any interview to Google Calendar, Outlook or Apple Calendar with one click from the Interviews page (.ics).",
      action: <Link href="/interviews" className={buttonVariants({ size: "sm", variant: "outline" })}>Interviews</Link>,
    },
    {
      name: "Claude AI", icon: Sparkles,
      status: data.claude.enabled ? { label: `On · ${data.claude.model}`, tone: "success" } : { label: "Optional", tone: "muted" },
      body: "Optional polish for JD analysis, summaries and cover letters. Every AI output is verified against your profile before use.",
    },
  ];

  return (
    <>
      <PageHeader title="Integrations" description="Everything Saige connects to — through official APIs, OAuth or your own clicks. Never passwords, never scraping." />
      {msg && <div className="mb-4"><Notice tone={msg.tone}>{msg.text}</Notice></div>}

      <Card className="animate-rise mb-6 overflow-hidden">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg"><Bookmark className="size-4" /> Save to Saige — capture any job posting</CardTitle>
          <CardDescription>
            Drag this button to your browser&apos;s bookmarks bar. On any job page (LinkedIn, Naukri, Indeed, company sites), click it to send the posting to Saige for scoring. Select text first to send just that part.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center gap-4">
          <a
            ref={linkRef}
            href="#"
            onClick={(e) => { e.preventDefault(); setMsg({ tone: "warning", text: "Drag the button to your bookmarks bar, then click it while viewing a job posting." }); }}
            className="inline-flex h-11 cursor-grab items-center gap-2 rounded-full bg-primary px-5 text-sm font-semibold text-primary-foreground shadow-[var(--shadow-lift)] active:cursor-grabbing"
            draggable
          >
            <Bookmark className="size-4" /> Save to Saige
          </a>
          <p className="max-w-xl text-xs text-muted-foreground">
            It runs only when you click it, only on the page you&apos;re viewing, and opens Saige where you review the job before it&apos;s saved.
          </p>
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {tiles.map((t, i) => (
          <Card key={t.name} className="lift animate-rise flex flex-col p-5" style={{ animationDelay: `${i * 40}ms` }}>
            <div className="flex items-center gap-3">
              <span className="grid size-10 place-items-center rounded-xl border bg-muted/60"><t.icon className="size-5" /></span>
              <div className="min-w-0">
                <p className="truncate font-semibold">{t.name}</p>
                <Badge variant={t.status.tone} className="mt-0.5">{t.status.tone === "success" && <Check className="size-3" />}{t.status.label}</Badge>
              </div>
            </div>
            <p className="mt-3 flex-1 text-sm text-muted-foreground">{t.body}</p>
            {t.action && <div className="mt-4">{t.action}</div>}
          </Card>
        ))}
      </div>
    </>
  );
}
