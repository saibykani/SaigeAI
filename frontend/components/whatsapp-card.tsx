"use client";

import { ExternalLink, MessageCircle } from "lucide-react";
import { useState } from "react";

import { Notice } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input } from "@/components/ui/form";
import { request } from "@/services/api";
import type { Integrations } from "@/types/api";

/** Mirror every Saige notification to the user's WhatsApp via CallMeBot. */
export function WhatsAppCard({ info, onChange }: { info: Integrations["whatsapp"]; onChange: () => void }) {
  const [phone, setPhone] = useState("");
  const [apikey, setApikey] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const [editing, setEditing] = useState(!info.connected);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setMsg(null);
    try {
      await request("/integrations/whatsapp", { method: "PUT", body: { phone, apikey, enabled: true } });
      setMsg({ tone: "success", text: "Connected. Check WhatsApp for the confirmation message." });
      setEditing(false);
      setApikey("");
      onChange();
    } catch (err) {
      setMsg({ tone: "error", text: err instanceof Error ? err.message : "Could not connect WhatsApp" });
    } finally {
      setBusy(false);
    }
  }

  async function toggle() {
    await request(`/integrations/whatsapp/toggle?enabled=${!info.enabled}`, { method: "POST" });
    onChange();
  }

  const green = "#25D366";
  return (
    <Card id="whatsapp" className="animate-rise mb-6 scroll-mt-24" style={{ borderColor: `color-mix(in srgb, ${green} 32%, transparent)`, backgroundImage: `radial-gradient(120% 80% at 100% 0%, color-mix(in srgb, ${green} 12%, transparent), transparent 60%)` }}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <span className="grid size-8 place-items-center rounded-lg text-[#0b0b0c]" style={{ background: green }}><MessageCircle className="size-4" /></span>
          WhatsApp notifications
          {info.connected && <span className="rounded-full px-2 py-0.5 text-[11px] font-semibold text-black" style={{ background: info.enabled ? green : "var(--muted-foreground)" }}>{info.enabled ? "On" : "Paused"}</span>}
        </CardTitle>
        <CardDescription>
          Get a WhatsApp message for everything Saige does: applications prepared or updated, emails sent, recruiter replies and interview emails received, profile refreshes with the exact fields changed, and follow-ups due.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {info.connected && !editing ? (
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <span>Sending to <b>{info.phone}</b></span>
            {info.error && <span className="text-destructive">Last attempt failed: {info.error}</span>}
            <Button size="sm" variant="outline" onClick={toggle}>{info.enabled ? "Pause" : "Resume"}</Button>
            <Button size="sm" variant="ghost" onClick={() => setEditing(true)}>Change number</Button>
            <Button size="sm" variant="ghost" onClick={async () => { await request("/integrations/whatsapp", { method: "DELETE" }); onChange(); setEditing(true); }}>Remove</Button>
          </div>
        ) : (
          <form onSubmit={save} className="grid gap-4 lg:grid-cols-2">
            <ol className="list-decimal space-y-1.5 pl-5 text-sm text-muted-foreground">
              <li>Open <a className="font-medium text-foreground underline" href="https://www.callmebot.com/blog/free-api-whatsapp-messages/" target="_blank" rel="noopener noreferrer">CallMeBot&apos;s WhatsApp setup page <ExternalLink className="inline size-3" /></a> and save the phone number shown there in your contacts.</li>
              <li>From your WhatsApp, send that contact: <code className="rounded bg-muted px-1">I allow callmebot to send me messages</code></li>
              <li>It replies with your personal <b>API key</b>. Enter it and your number (with country code) here.</li>
              <li className="list-none pt-1 text-xs">CallMeBot is a free third-party relay that can only message your own number. Message text passes through it.</li>
            </ol>
            <div className="flex flex-col gap-3">
              <Field label="Your WhatsApp number"><Input required value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+91 98765 43210" inputMode="tel" /></Field>
              <Field label="CallMeBot API key"><Input required value={apikey} onChange={(e) => setApikey(e.target.value)} placeholder="e.g. 1234567" autoComplete="off" /></Field>
              {msg && <Notice tone={msg.tone}>{msg.text}</Notice>}
              <div className="flex gap-2">
                <Button type="submit" disabled={busy}>{busy ? "Sending test message…" : "Connect & send test"}</Button>
                {info.connected && <Button type="button" variant="ghost" onClick={() => setEditing(false)}>Cancel</Button>}
              </div>
            </div>
          </form>
        )}
        {msg && !editing && <div className="mt-3"><Notice tone={msg.tone}>{msg.text}</Notice></div>}
      </CardContent>
    </Card>
  );
}
