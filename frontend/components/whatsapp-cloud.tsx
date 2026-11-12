"use client";

import { MessageCircle } from "lucide-react";
import { useState } from "react";

import { Notice } from "@/components/app-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/form";
import { useApi } from "@/hooks/use-api";
import { request } from "@/services/api";

type Wa = { available: boolean; connected: boolean; pending: boolean; phone: string | null; digest: boolean };

/** Saige on WhatsApp: two-way chat through the official WhatsApp Business Cloud API. */
export function WhatsAppChatCard() {
  const { data, setData } = useApi<Wa>("/integrations/whatsapp-cloud");
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  async function run(path: string, method: "POST" | "PUT" | "DELETE", body?: unknown) {
    setBusy(true);
    setErr(null);
    try { setData(await request<Wa>(path, { method, body })); } catch (e) { setErr(e instanceof Error ? e.message : "WhatsApp failed."); } finally { setBusy(false); }
  }
  return (
    <Card className="mb-6">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg"><MessageCircle className="size-5 text-[var(--tone-green)]" /> Saige on WhatsApp
          {data?.connected && <Badge variant="success">Linked · {data.phone}</Badge>}</CardTitle>
        <CardDescription>Chat with Saige: <b>jobs</b>, <b>apply 2</b> (then <b>yes</b>), <b>status</b>, <b>digest</b>, <b>pause</b>, <b>resume</b>, <b>help</b>. Nothing is sent until you reply yes.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {err && <Notice tone="error">{err}</Notice>}
        {data && !data.available && <p className="text-muted-foreground">Not configured on this server yet: the admin adds the WhatsApp Business Cloud API keys (WHATSAPP_TOKEN).</p>}
        {data?.available && !data.connected && (
          <div className="space-y-2">
            <div className="flex flex-wrap gap-2">
              <Input className="max-w-xs" placeholder="+91 98765 43210" value={phone} onChange={(e) => setPhone(e.target.value)} />
              <Button disabled={busy || phone.length < 8} onClick={() => void run("/integrations/whatsapp-cloud/link", "POST", { phone })}>{data.pending ? "Resend code" : "Send code"}</Button>
            </div>
            {data.pending && (
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-muted-foreground">Reply with the 6-digit code on WhatsApp, or enter it:</span>
                <Input className="w-32" inputMode="numeric" maxLength={6} value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} />
                <Button size="sm" disabled={busy || code.length !== 6} onClick={() => void run("/integrations/whatsapp-cloud/verify", "POST", { code })}>Verify</Button>
              </div>
            )}
          </div>
        )}
        {data?.connected && (
          <div className="flex flex-wrap items-center gap-3">
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={data.digest} onChange={(e) => void run("/integrations/whatsapp-cloud", "PUT", { digest: e.target.checked })} />
              Daily digest on WhatsApp
            </label>
            <Button variant="outline" size="sm" onClick={() => void run("/integrations/whatsapp-cloud", "DELETE")} disabled={busy}>Unlink</Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
