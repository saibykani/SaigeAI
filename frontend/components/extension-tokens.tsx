"use client";

import { ClipboardCopy, Download, KeyRound, Puzzle, Trash2 } from "lucide-react";
import { useState } from "react";

import { Notice } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/form";
import { useApi } from "@/hooks/use-api";
import { request } from "@/services/api";
import { formatDate } from "@/utils/format";

type Token = { id: string; name: string; prefix: string; created_at: string; last_used_at: string | null };

/** Settings card: download the Chrome extension and manage the tokens it signs in with. */
export function ExtensionTokensCard() {
  const { data, reload } = useApi<Token[]>("/auth/tokens");
  const [name, setName] = useState("Chrome extension");
  const [fresh, setFresh] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function create() {
    setErr(null);
    try {
      const r = await request<Token & { token: string }>("/auth/tokens", { method: "POST", body: { name } });
      setFresh(r.token);
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not create a token");
    }
  }

  async function revoke(t: Token) {
    if (!confirm(`Revoke "${t.name}"? The extension using it will stop working.`)) return;
    await request(`/auth/tokens/${t.id}`, { method: "DELETE" });
    await reload();
  }

  return (
    <Card id="extension" className="scroll-mt-24 lg:col-span-2" style={{ borderColor: "color-mix(in srgb, var(--tone-teal) 28%, transparent)" }}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2"><Puzzle className="size-4" style={{ color: "var(--tone-teal)" }} /> Browser extension</CardTitle>
        <CardDescription>
          Score and save any job you&apos;re viewing, fill application forms on company career sites with your verified details and resume, and put prepared
          LinkedIn / Naukri edits into the right field with one click. It only acts on the tab you click it on, and never presses Submit or Save for you.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-6 md:grid-cols-2">
        <div className="flex flex-col gap-3 text-sm">
          <p className="font-medium">Install (Chrome, Edge, Brave)</p>
          <ol className="list-decimal space-y-1 pl-5 text-muted-foreground">
            <li>Download and unzip the extension (v1.1; if you had v1.0, remove it and load this one).</li>
            <li>Open <code className="rounded bg-muted px-1">chrome://extensions</code> and turn on <b>Developer mode</b>.</li>
            <li>Click <b>Load unpacked</b> and choose the unzipped folder.</li>
            <li>Create a token here, then paste it in the extension&apos;s Settings.</li>
          </ol>
          <a href="/saige-extension.zip" download className="inline-flex h-9 w-fit items-center gap-2 rounded-full bg-primary px-4 text-sm font-medium text-primary-foreground">
            <Download className="size-4" /> Download extension
          </a>
        </div>
        <div className="flex flex-col gap-3">
          <p className="flex items-center gap-2 text-sm font-medium"><KeyRound className="size-4" /> Extension tokens</p>
          <div className="flex gap-2">
            <Input value={name} maxLength={60} onChange={(e) => setName(e.target.value)} aria-label="Token name" />
            <Button onClick={create} disabled={!name.trim()}>Create</Button>
          </div>
          {fresh && (
            <Notice tone="success">
              <span className="block font-medium">Copy this token now. It won&apos;t be shown again.</span>
              <span className="mt-1 flex items-center gap-2">
                <code className="min-w-0 flex-1 truncate rounded bg-black/20 px-2 py-1 text-xs">{fresh}</code>
                <Button size="sm" variant="outline" onClick={async () => { await navigator.clipboard.writeText(fresh); setCopied(true); }}>
                  <ClipboardCopy /> {copied ? "Copied" : "Copy"}
                </Button>
              </span>
            </Notice>
          )}
          {err && <Notice tone="error">{err}</Notice>}
          <ul className="flex flex-col gap-2 text-sm">
            {data?.length === 0 && <li className="text-muted-foreground">No tokens yet.</li>}
            {data?.map((t) => (
              <li key={t.id} className="flex items-center gap-3 rounded-xl border p-2.5">
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium">{t.name} <span className="font-mono text-xs text-muted-foreground">{t.prefix}…</span></p>
                  <p className="text-xs text-muted-foreground">Created {formatDate(t.created_at)} · {t.last_used_at ? `last used ${formatDate(t.last_used_at)}` : "never used"}</p>
                </div>
                <Button size="icon" variant="ghost" aria-label={`Revoke ${t.name}`} onClick={() => revoke(t)}><Trash2 className="size-4" /></Button>
              </li>
            ))}
          </ul>
        </div>
      </CardContent>
    </Card>
  );
}
