"use client";

import { MessageSquare, Send } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/form";
import { request } from "@/services/api";

type Turn = { who: "you" | "saige"; text: string };
const HINTS = ["remove Healthcare", "move Playwright to top", "shorten summary", "change Rest Assured to REST Assured", "remove the Payment Gateway project"];

/** Chat box that edits the generated resume: remove, reorder, shorten or reword what is already there. Never adds new facts. */
export function ResumeChat({ resumeId, template, onApplied }: { resumeId: string; template: string; onApplied: (html: string) => void }) {
  const [text, setText] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);

  async function send(msg: string) {
    const t = msg.trim();
    if (!t || busy) return;
    setText("");
    setTurns((x) => [...x, { who: "you", text: t }]);
    setBusy(true);
    try {
      const r = await request<{ changes: string[]; saved: boolean; html: string }>(`/studio/resumes/${resumeId}/instruct`, { method: "POST", body: { text: t, template } });
      setTurns((x) => [...x, { who: "saige", text: r.changes.join("\n") + (r.saved ? "\n\nSaved as a new version." : "") }]);
      if (r.saved) onApplied(r.html);
    } catch (e) {
      setTurns((x) => [...x, { who: "saige", text: e instanceof Error ? e.message : "Couldn't make that change." }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-2xl border p-4">
      <p className="flex items-center gap-2 text-sm font-medium"><MessageSquare className="size-4 text-primary" /> Tell Saige what to change</p>
      <p className="mt-1 text-xs text-muted-foreground">Remove, reorder, shorten or reword what&apos;s already there. Saige never adds anything that isn&apos;t in your verified profile.</p>
      {turns.length === 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {HINTS.map((h) => <button key={h} type="button" onClick={() => void send(h)} className="rounded-full border px-2.5 py-1 text-xs hover:bg-muted">{h}</button>)}
        </div>
      )}
      {turns.length > 0 && (
        <div className="mt-3 max-h-64 space-y-2 overflow-y-auto text-sm">
          {turns.map((tn, i) => (
            <div key={i} className={tn.who === "you" ? "ml-8 rounded-2xl bg-primary px-3 py-2 text-primary-foreground" : "mr-8 whitespace-pre-wrap rounded-2xl bg-muted/60 px-3 py-2"}>{tn.text}</div>
          ))}
        </div>
      )}
      <form className="mt-3 flex gap-2" onSubmit={(e) => { e.preventDefault(); void send(text); }}>
        <Input value={text} onChange={(e) => setText(e.target.value)} placeholder="e.g. remove Healthcare and SaaS, move Playwright to top" disabled={busy} />
        <Button type="submit" disabled={busy || !text.trim()}><Send /> {busy ? "Working…" : "Apply"}</Button>
      </form>
    </div>
  );
}
