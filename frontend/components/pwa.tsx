"use client";

import { BellRing, Download, Share, X } from "lucide-react";
import { useEffect, useState } from "react";

import { Notice } from "@/components/app-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { request } from "@/services/api";

type InstallEvent = Event & { prompt: () => Promise<void>; userChoice: Promise<{ outcome: string }> };
const DISMISS_KEY = "saige.install.dismissed";

function isStandalone(): boolean {
  return window.matchMedia("(display-mode: standalone)").matches || (navigator as Navigator & { standalone?: boolean }).standalone === true;
}

/** Registers the service worker once (production only, so dev hot reload is not cached). */
export function PwaRegister() {
  useEffect(() => {
    if (process.env.NODE_ENV !== "production" || !("serviceWorker" in navigator)) return;
    navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(() => undefined);
  }, []);
  return null;
}

/** Dismissible "Install app" card: native prompt on Android/desktop, Share > Add to Home Screen steps on iOS. */
export function InstallCard() {
  const [evt, setEvt] = useState<InstallEvent | null>(null);
  const [ios, setIos] = useState(false);
  const [hidden, setHidden] = useState(true);

  useEffect(() => {
    let dismissed = false;
    try { dismissed = localStorage.getItem(DISMISS_KEY) === "1"; } catch { /* storage blocked */ }
    if (dismissed || isStandalone()) return;
    const isIos = /iphone|ipad|ipod/i.test(navigator.userAgent) && !/crios|fxios/i.test(navigator.userAgent);
    setIos(isIos);
    setHidden(!isIos);
    const onPrompt = (e: Event) => { e.preventDefault(); setEvt(e as InstallEvent); setHidden(false); };
    const onInstalled = () => setHidden(true);
    window.addEventListener("beforeinstallprompt", onPrompt);
    window.addEventListener("appinstalled", onInstalled);
    return () => { window.removeEventListener("beforeinstallprompt", onPrompt); window.removeEventListener("appinstalled", onInstalled); };
  }, []);

  function dismiss() {
    setHidden(true);
    try { localStorage.setItem(DISMISS_KEY, "1"); } catch { /* ignore */ }
  }
  if (hidden) return null;
  return (
    <div className="mb-4 flex items-start gap-3 rounded-2xl border border-border bg-card/70 p-4 text-sm backdrop-blur">
      <Download className="mt-0.5 size-5 shrink-0 text-[var(--tone-green)]" />
      <div className="flex-1">
        <p className="font-medium">Install Saige AI on your phone</p>
        {ios && !evt ? (
          <p className="mt-1 text-muted-foreground">Tap <Share className="inline size-4" /> Share in Safari, then <b>Add to Home Screen</b>.</p>
        ) : (
          <p className="mt-1 text-muted-foreground">Open it like an app and get job and interview alerts.</p>
        )}
        {evt && (
          <Button size="sm" className="mt-2" onClick={async () => { await evt.prompt(); await evt.userChoice; setEvt(null); setHidden(true); }}>Install app</Button>
        )}
      </div>
      <button type="button" aria-label="Dismiss" onClick={dismiss} className="text-muted-foreground"><X className="size-4" /></button>
    </div>
  );
}

function b64ToBytes(v: string): Uint8Array<ArrayBuffer> {
  const raw = atob((v + "=".repeat((4 - (v.length % 4)) % 4)).replace(/-/g, "+").replace(/_/g, "/"));
  const out = new Uint8Array(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
}

/** Settings > Integrations: enable web push on this device. */
export function PhoneNotificationsCard() {
  const [supported, setSupported] = useState(true);
  const [on, setOn] = useState(false);
  const [configured, setConfigured] = useState(true);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ tone: "error" | "success"; text: string } | null>(null);

  useEffect(() => {
    const ok = "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
    setSupported(ok);
    request<{ configured: boolean }>("/integrations/push/public-key").then((r) => setConfigured(r.configured)).catch(() => undefined);
    if (!ok) return;
    navigator.serviceWorker.getRegistration("/").then((reg) => reg?.pushManager.getSubscription()).then((s) => setOn(!!s)).catch(() => undefined);
  }, []);

  async function enable() {
    setBusy(true);
    setMsg(null);
    try {
      if ((await Notification.requestPermission()) !== "granted") throw new Error("Notifications are blocked. Allow them in your browser or phone settings.");
      const reg = (await navigator.serviceWorker.getRegistration("/")) ?? (await navigator.serviceWorker.register("/sw.js", { scope: "/" }));
      await navigator.serviceWorker.ready;
      const { public_key } = await request<{ public_key: string | null }>("/integrations/push/public-key");
      if (!public_key) throw new Error("Phone notifications are not configured on the server yet.");
      const sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: b64ToBytes(public_key) });
      await request("/integrations/push/subscribe", { method: "POST", body: { ...sub.toJSON(), device: navigator.userAgent.slice(0, 120) } });
      setOn(true);
      setMsg({ tone: "success", text: "Enabled on this device." });
    } catch (e) {
      setMsg({ tone: "error", text: e instanceof Error ? e.message : "Could not enable notifications." });
    } finally { setBusy(false); }
  }
  async function disable() {
    setBusy(true);
    try {
      const reg = await navigator.serviceWorker.getRegistration("/");
      const sub = await reg?.pushManager.getSubscription();
      await request("/integrations/push/subscribe", { method: "DELETE", body: { endpoint: sub?.endpoint } });
      await sub?.unsubscribe();
      setOn(false);
    } catch (e) {
      setMsg({ tone: "error", text: e instanceof Error ? e.message : "Could not disable." });
    } finally { setBusy(false); }
  }
  async function test() {
    setMsg(null);
    try { const r = await request<{ sent: number }>("/integrations/push/test", { method: "POST" }); setMsg({ tone: r.sent ? "success" : "error", text: r.sent ? "Test sent." : "No device received it." }); }
    catch (e) { setMsg({ tone: "error", text: e instanceof Error ? e.message : "Test failed." }); }
  }
  return (
    <Card className="mb-6">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg"><BellRing className="size-5 text-[var(--tone-orange)]" /> Phone notifications {on && <Badge variant="success">On</Badge>}</CardTitle>
        <CardDescription>Get job, interview and application alerts as push notifications. Install Saige to your home screen first (required on iPhone).</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {msg && <Notice tone={msg.tone}>{msg.text}</Notice>}
        {!supported && <p className="text-muted-foreground">This browser does not support push notifications.</p>}
        {supported && !configured && <p className="text-muted-foreground">Not configured on this server yet: the admin sets VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY.</p>}
        {supported && configured && (
          <div className="flex flex-wrap gap-2">
            {on ? (<><Button variant="outline" disabled={busy} onClick={test}>Send test</Button><Button variant="outline" disabled={busy} onClick={disable}>Turn off</Button></>)
              : <Button disabled={busy} onClick={enable}>Enable on this device</Button>}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
