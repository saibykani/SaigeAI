"use client";

import { ExternalLink, KeyRound, Link2, Mail, ShieldCheck } from "lucide-react";
import { useState } from "react";

import { Notice } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input } from "@/components/ui/form";
import { request } from "@/services/api";

/** Connect Gmail: an App Password (works right away) or Google sign-in (needs the Google project set up). */
export function GmailConnectCard({ oauthAvailable, onConnected, onOAuth }: { oauthAvailable: boolean; onConnected: () => void; onOAuth: () => void }) {
  const [email, setEmail] = useState("");
  const [pw, setPw] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function connect(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      await request("/auth/connect/gmail-app-password", { method: "POST", body: { email, app_password: pw } });
      setPw("");
      onConnected();
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : "Could not connect Gmail");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="animate-rise mb-6" style={{ borderColor: "color-mix(in srgb, var(--tone-red) 30%, transparent)", backgroundImage: "radial-gradient(120% 80% at 100% 0%, color-mix(in srgb, var(--tone-red) 12%, transparent), transparent 60%)" }}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <span className="grid size-8 place-items-center rounded-lg text-[#0b0b0c]" style={{ background: "var(--tone-red)" }}><Mail className="size-4" /></span>
          Connect Gmail
        </CardTitle>
        <CardDescription>Saige reads job-search mail (confirmations, interviews, rejections, offers) and updates your applications. Read-only: it never sends, deletes or marks mail as read.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-6 lg:grid-cols-2">
        <form onSubmit={connect} className="flex flex-col gap-3">
          <p className="flex items-center gap-2 text-sm font-semibold"><KeyRound className="size-4" style={{ color: "var(--tone-green)" }} /> Option 1 · App Password <span className="rounded-full px-2 py-0.5 text-[10px] font-semibold text-black" style={{ background: "var(--tone-green)" }}>Works now</span></p>
          <ol className="list-decimal space-y-1 pl-5 text-sm text-muted-foreground">
            <li>Turn on <a className="font-medium text-foreground underline" href="https://myaccount.google.com/signinoptions/twosv" target="_blank" rel="noopener noreferrer">2-Step Verification</a> for your Google account, if it's off.</li>
            <li>Open <a className="font-medium text-foreground underline" href="https://myaccount.google.com/apppasswords" target="_blank" rel="noopener noreferrer">App Passwords <ExternalLink className="inline size-3" /></a>, name it “Saige AI”, and click Create.</li>
            <li>Paste the 16-letter password below. Revoke it there any time to disconnect.</li>
          </ol>
          <Field label="Gmail address"><Input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@gmail.com" autoComplete="email" /></Field>
          <Field label="App Password"><Input required value={pw} onChange={(e) => setPw(e.target.value)} placeholder="abcd efgh ijkl mnop" autoComplete="off" spellCheck={false} /></Field>
          {err && <Notice tone="error">{err}</Notice>}
          <div><Button type="submit" disabled={busy || pw.replace(/\s/g, "").length < 16}>{busy ? "Checking with Gmail…" : "Connect Gmail"}</Button></div>
          <p className="flex items-start gap-1.5 text-xs text-muted-foreground"><ShieldCheck className="mt-0.5 size-3.5 shrink-0" /> Stored encrypted. It's not your Google password, and it can only be used with Gmail's mail protocols.</p>
        </form>
        <div className="flex flex-col gap-3 rounded-2xl border p-4">
          <p className="flex items-center gap-2 text-sm font-semibold"><Link2 className="size-4" style={{ color: "var(--tone-teal)" }} /> Option 2 · Sign in with Google</p>
          <p className="text-sm text-muted-foreground">
            Uses Google's official read-only Gmail permission. While the Google Cloud project is in <b>Testing</b>, Google shows “Access blocked” unless your account is a listed test user:
          </p>
          <ol className="list-decimal space-y-1 pl-5 text-sm text-muted-foreground">
            <li>Open <a className="font-medium text-foreground underline" href="https://console.cloud.google.com/auth/audience" target="_blank" rel="noopener noreferrer">Google Cloud → Google Auth Platform → Audience</a>.</li>
            <li>Under <b>Test users</b>, click <b>Add users</b> and add your Gmail address.</li>
            <li>Make sure the Gmail API is enabled and <code className="rounded bg-muted px-1">gmail.readonly</code> is added under <b>Data access</b>.</li>
          </ol>
          <div><Button variant="outline" disabled={!oauthAvailable} onClick={onOAuth}><Link2 /> Connect with Google</Button></div>
        </div>
      </CardContent>
    </Card>
  );
}
