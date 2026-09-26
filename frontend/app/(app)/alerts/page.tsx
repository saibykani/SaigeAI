"use client";

import { Bell, ClipboardCopy, FileText, Mail, MessageCircle, MessageSquare, UserPlus } from "lucide-react";
import { useState } from "react";

import { PageHeader } from "@/components/app-shell";
import { Loader3D } from "@/components/loader3d";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { WhatsAppCard } from "@/components/whatsapp-card";
import { useApi } from "@/hooks/use-api";
import { request } from "@/services/api";
import type { Integrations, OutreachTemplate } from "@/types/api";
import { cn } from "@/utils/cn";

const ALERT_GROUPS: { id: string; label: string; hint: string; tone: string }[] = [
  { id: "applications", label: "Applications", hint: "Prepared, approved, applied, auto-applier runs", tone: "yellow" },
  { id: "emails", label: "Recruiter emails", hint: "Recruiter mail, portal invites, replies ready to send", tone: "teal" },
  { id: "interviews", label: "Interviews", hint: "Invitations, reschedules, reminders", tone: "red" },
  { id: "outreach", label: "Outreach", hint: "Emails sent, follow-ups due", tone: "lime" },
  { id: "jobs", label: "Jobs", hint: "Strong matches, new jobs on followed boards", tone: "orange" },
  { id: "profile", label: "LinkedIn & Naukri", hint: "Profile refreshes with the fields changed", tone: "mint" },
];

const CHANNELS: { id: OutreachTemplate["channel"]; label: string; icon: typeof Mail; tone: string; hint: string }[] = [
  { id: "email", label: "Email", icon: Mail, tone: "orange", hint: "Copy, or open Recruiters to draft for a contact and send from Gmail." },
  { id: "whatsapp", label: "WhatsApp", icon: MessageCircle, tone: "green", hint: "Opens WhatsApp with the message ready; you pick the chat." },
  { id: "sms", label: "SMS", icon: MessageSquare, tone: "purple", hint: "Opens your phone's messages app with the text ready." },
  { id: "linkedin", label: "LinkedIn", icon: UserPlus, tone: "teal", hint: "Paste into a LinkedIn connection request (300 characters)." },
];

function Template({ t, tone }: { t: OutreachTemplate; tone: string }) {
  const [copied, setCopied] = useState(false);
  const text = t.channel === "email" ? `Subject: ${t.subject}\n\n${t.body}` : t.body;
  return (
    <Card className="lift flex flex-col" style={{ borderColor: `color-mix(in srgb, var(--tone-${tone}) 30%, transparent)` }}>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">{t.name}</CardTitle>
        <CardDescription>For {t.audience} · {t.description}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col gap-3">
        {t.channel === "email" && <p className="text-sm"><span className="text-muted-foreground">Subject: </span>{t.subject}</p>}
        <p className="flex-1 whitespace-pre-wrap rounded-xl border bg-muted/40 p-3 text-sm leading-relaxed">{t.body}</p>
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="outline" onClick={async () => { await navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 1500); }}>
            <ClipboardCopy /> {copied ? "Copied" : "Copy"}
          </Button>
          {t.wa_link && <a href={t.wa_link} target="_blank" rel="noopener noreferrer" className="inline-flex h-8 items-center gap-1.5 rounded-full px-3.5 text-xs font-medium text-[#0b0b0c]" style={{ background: "#25D366" }}><MessageCircle className="size-3.5" /> Open in WhatsApp</a>}
          {t.sms_link && <a href={t.sms_link} className="inline-flex h-8 items-center gap-1.5 rounded-full px-3.5 text-xs font-medium text-[#0b0b0c]" style={{ background: "var(--tone-purple)" }}><MessageSquare className="size-3.5" /> Open in Messages</a>}
          {t.channel === "email" && <a href="/recruiters" className="inline-flex h-8 items-center gap-1.5 rounded-full border px-3.5 text-xs font-medium hover:bg-muted"><FileText className="size-3.5" /> Draft for a contact</a>}
        </div>
      </CardContent>
    </Card>
  );
}

export default function AlertsPage() {
  const integ = useApi<Integrations>("/integrations");
  const tpls = useApi<OutreachTemplate[]>("/outreach/templates");
  const [channel, setChannel] = useState<OutreachTemplate["channel"]>("email");
  const wa = integ.data?.whatsapp;
  const muted = new Set(wa?.muted ?? []);

  async function toggleGroup(id: string) {
    const next = new Set(muted);
    if (next.has(id)) next.delete(id); else next.add(id);
    await request("/integrations/whatsapp/prefs", { method: "PUT", body: { muted: [...next] } });
    await integ.reload();
  }

  const ch = CHANNELS.find((c) => c.id === channel)!;
  return (
    <>
      <PageHeader title="Alerts & templates" description="Where Saige tells you what happened (in the app and on WhatsApp), and every ready-to-send email, WhatsApp, SMS and LinkedIn template." />
      {!integ.data ? <div className="grid place-items-center py-16"><Loader3D size={56} /></div> : (
        <>
          <WhatsAppCard info={integ.data.whatsapp} onChange={integ.reload} />
          <Card className="animate-rise mb-6">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-lg">
                <span className="grid size-8 place-items-center rounded-lg text-[#0b0b0c]" style={{ background: "var(--tone-yellow)" }}><Bell className="size-4" /></span>
                What to send to WhatsApp
              </CardTitle>
              <CardDescription>Everything always appears in the bell (top right). Choose which kinds of update also reach your WhatsApp.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {ALERT_GROUPS.map((g) => {
                const on = !muted.has(g.id);
                return (
                  <button key={g.id} type="button" disabled={!wa?.connected} onClick={() => toggleGroup(g.id)}
                    className={cn("flex items-start gap-3 rounded-2xl border p-3 text-left transition-colors disabled:opacity-50", on && wa?.connected && "bg-muted/50")}>
                    <span className="mt-0.5 grid size-5 shrink-0 place-items-center rounded-md border text-[11px] font-bold text-[#0b0b0c]" style={on && wa?.connected ? { background: `var(--tone-${g.tone})`, borderColor: "transparent" } : undefined}>{on && wa?.connected ? "✓" : ""}</span>
                    <span><span className="block text-sm font-medium">{g.label}</span><span className="block text-xs text-muted-foreground">{g.hint}</span></span>
                  </button>
                );
              })}
              {!wa?.connected && <p className="text-xs text-muted-foreground sm:col-span-2 lg:col-span-3">Connect WhatsApp above to choose.</p>}
            </CardContent>
          </Card>
        </>
      )}

      <section className="animate-rise">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <h2 className="mr-2 text-lg font-semibold">Templates</h2>
          {CHANNELS.map((c) => (
            <button key={c.id} type="button" onClick={() => setChannel(c.id)}
              className={cn("inline-flex items-center gap-1.5 rounded-full border px-3.5 py-1.5 text-sm", channel === c.id ? "border-transparent font-medium text-[#0b0b0c]" : "text-muted-foreground hover:text-foreground")}
              style={channel === c.id ? { background: `var(--tone-${c.tone})` } : undefined}>
              <c.icon className="size-4" /> {c.label} <span className="opacity-70">{(tpls.data ?? []).filter((t) => t.channel === c.id).length}</span>
            </button>
          ))}
        </div>
        <p className="mb-4 text-sm text-muted-foreground">{ch.hint} Templates use only your verified profile; [First name], [Company] and [Role] are filled in when you draft for a contact.</p>
        {!tpls.data ? <div className="skeleton h-64 rounded-3xl" /> : (
          <div className="grid gap-4 lg:grid-cols-2">
            {tpls.data.filter((t) => t.channel === channel).map((t) => <Template key={t.kind} t={t} tone={ch.tone} />)}
          </div>
        )}
      </section>
    </>
  );
}
