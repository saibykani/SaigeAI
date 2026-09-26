"use client";

import { Check, ExternalLink, Globe2, Mail, Save } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/form";
import { useApi } from "@/hooks/use-api";
import { request } from "@/services/api";
import type { HiringPortal } from "@/types/api";
import { cn } from "@/utils/cn";

const STATE: Record<HiringPortal["state"], { label: string; tone: string }> = {
  connected: { label: "Automatic", tone: "green" },
  receiving: { label: "Receiving alerts", tone: "green" },
  waiting: { label: "Waiting for first alert", tone: "yellow" },
  needs_gmail: { label: "Connect Gmail", tone: "orange" },
  setup: { label: "Set up alerts", tone: "muted" },
};

function PortalRow({ p, onSaved }: { p: HiringPortal; onSaved: () => void }) {
  const [open, setOpen] = useState(false);
  const [url, setUrl] = useState(p.profile_url ?? "");
  const [alertsOn, setAlertsOn] = useState(p.alerts_on);
  const [err, setErr] = useState<string | null>(null);
  const st = STATE[p.state];

  async function save() {
    setErr(null);
    try {
      await request(`/integrations/portals/${p.key}`, { method: "PUT", body: { profile_url: url || null, alerts_on: alertsOn } });
      setOpen(false);
      onSaved();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not save");
    }
  }

  return (
    <li className="rounded-2xl border p-3">
      <div className="flex flex-wrap items-center gap-3">
        <span className="grid size-9 shrink-0 place-items-center rounded-xl text-sm font-semibold text-[#0b0b0c]" style={{ background: `var(--tone-${p.method === "api" ? "teal" : "orange"})` }}>
          {p.name[0]}
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate font-medium">{p.name}</p>
          <p className="truncate text-xs text-muted-foreground">{p.region}{p.jobs ? ` · ${p.jobs} job(s) in your feed` : ""}</p>
        </div>
        <span className={cn("rounded-full px-2 py-0.5 text-[11px] font-semibold", st.tone === "muted" ? "bg-muted text-muted-foreground" : "text-[#0b0b0c]")}
          style={st.tone === "muted" ? undefined : { background: `var(--tone-${st.tone})` }}>
          {p.state === "connected" || p.state === "receiving" ? <Check className="mr-0.5 inline size-3" /> : null}{st.label}
        </span>
        <a href={p.url} target="_blank" rel="noopener noreferrer" className="text-muted-foreground hover:text-foreground" aria-label={`Open ${p.name}`}><ExternalLink className="size-4" /></a>
        {p.method === "alerts" && <Button size="sm" variant="ghost" onClick={() => setOpen(!open)}>{open ? "Close" : "Set up"}</Button>}
      </div>
      {open && p.method === "alerts" && (
        <div className="mt-3 grid gap-3 border-t pt-3 text-sm md:grid-cols-2">
          <ol className="list-decimal space-y-1 pl-5 text-muted-foreground">
            <li>{p.alert_help}</li>
            <li>Use the email address you connected in Gmail above.</li>
            <li>Saige reads those alert emails (read-only) and lists every job in <b>Jobs → Job alerts</b>.</li>
          </ol>
          <div className="flex flex-col gap-2">
            <Input value={url} onChange={(e) => setUrl(e.target.value)} placeholder={`Your ${p.name} profile URL (optional)`} type="url" />
            <label className="inline-flex items-center gap-2">
              <input type="checkbox" className="size-4 accent-[var(--tone-orange)]" checked={alertsOn} onChange={(e) => setAlertsOn(e.target.checked)} /> I&apos;ve turned on job alerts
            </label>
            {err && <p className="text-xs text-destructive">{err}</p>}
            <Button size="sm" className="w-fit" onClick={save}><Save /> Save</Button>
          </div>
        </div>
      )}
      {p.profile_url && !open && <a href={p.profile_url} target="_blank" rel="noopener noreferrer" className="mt-1 block truncate pl-12 text-xs underline">{p.profile_url}</a>}
    </li>
  );
}

/** Every hiring portal and how it reaches Saige: automatic job APIs, or job-alert emails in your Gmail. */
export function HiringPortalsCard() {
  const { data, reload } = useApi<{ gmail_connected: boolean; portals: HiringPortal[] }>("/integrations/portals");
  const api = data?.portals.filter((p) => p.method === "api") ?? [];
  const alerts = data?.portals.filter((p) => p.method === "alerts") ?? [];
  return (
    <Card id="portals" className="animate-rise mb-6 scroll-mt-24" style={{ borderColor: "color-mix(in srgb, var(--tone-orange) 28%, transparent)" }}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <span className="grid size-8 place-items-center rounded-lg text-[#0b0b0c]" style={{ background: "var(--tone-orange)" }}><Globe2 className="size-4" /></span>
          Hiring portals
        </CardTitle>
        <CardDescription>
          Job sites with public APIs are fetched automatically. LinkedIn, Naukri, Indeed and the other portals don&apos;t allow automated access, so Saige reads the job-alert
          emails they send you (with Gmail connected) and lists those jobs too. Saige never logs into these sites or asks for their passwords.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-6 lg:grid-cols-2">
        <section>
          <p className="mb-2 text-sm font-medium">Automatic · {api.length}</p>
          <ul className="flex flex-col gap-2">{api.map((p) => <PortalRow key={p.key} p={p} onSaved={reload} />)}</ul>
        </section>
        <section>
          <p className="mb-2 flex items-center gap-1.5 text-sm font-medium"><Mail className="size-4" /> Through job-alert emails · {alerts.length}
            {data && !data.gmail_connected && <span className="font-normal text-muted-foreground">· connect Gmail first</span>}
          </p>
          <ul className="flex flex-col gap-2">{alerts.map((p) => <PortalRow key={p.key} p={p} onSaved={reload} />)}</ul>
        </section>
      </CardContent>
    </Card>
  );
}
