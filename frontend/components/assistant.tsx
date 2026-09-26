"use client";

import { ArrowUp, Loader2, Sparkles, Trash2, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { request } from "@/services/api";
import { cn } from "@/utils/cn";

type Msg = { role: "user" | "assistant"; content: string; actions?: { label: string; href: string }[]; engine?: string };
const KEY = "saige-chat";
const SUGGESTIONS = [
  "What are my best jobs today?",
  "How are my applications doing?",
  "Any upcoming interviews?",
  "Show my latest recruiter emails",
  "Write a short LinkedIn headline for me",
  "How do I get more interview calls?",
];

function load(): Msg[] {
  try {
    return JSON.parse(localStorage.getItem(KEY) || "[]") as Msg[];
  } catch {
    return [];
  }
}

function save(msgs: Msg[]) {
  try {
    localStorage.setItem(KEY, JSON.stringify(msgs.slice(-40)));
    window.dispatchEvent(new Event("saige-chat"));
  } catch {
    /* storage unavailable: the chat still works for this page view */
  }
}

/** Shared conversation state (the corner bubble and the Saige AI page show the same chat). */
function useChat() {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    setMsgs(load());
    const on = () => setMsgs(load());
    window.addEventListener("saige-chat", on);
    return () => window.removeEventListener("saige-chat", on);
  }, []);

  async function send(text: string) {
    const q = text.trim();
    if (!q || busy) return;
    const next: Msg[] = [...msgs, { role: "user", content: q }];
    setMsgs(next);
    save(next);
    setBusy(true);
    try {
      const r = await request<{ reply: string; engine: string; actions: Msg["actions"] }>("/assistant/chat", {
        method: "POST", body: { messages: next.slice(-16).map(({ role, content }) => ({ role, content: content.slice(0, 4000) })) },
      });
      const done: Msg[] = [...next, { role: "assistant", content: r.reply, actions: r.actions, engine: r.engine }];
      setMsgs(done);
      save(done);
    } catch (e) {
      const done: Msg[] = [...next, { role: "assistant", content: e instanceof Error ? e.message : "Something went wrong. Try again." }];
      setMsgs(done);
      save(done);
    } finally {
      setBusy(false);
    }
  }

  return { msgs, busy, send, clear: () => { setMsgs([]); save([]); } };
}

/** A glossy 3D orb in one tone (the assistant's mark). */
export function Orb({ size = 40, spinning = false }: { size?: number; spinning?: boolean }) {
  return (
    <span className="relative inline-grid shrink-0 place-items-center" style={{ width: size, height: size }}>
      <span className="absolute inset-0 rounded-full" style={{
        background: "radial-gradient(circle at 32% 28%, #fff 0%, color-mix(in srgb, var(--tone-purple) 70%, #fff) 16%, var(--tone-purple) 48%, color-mix(in srgb, var(--tone-purple) 45%, #000) 100%)",
        boxShadow: "0 8px 24px -6px color-mix(in srgb, var(--tone-purple) 70%, transparent), inset -4px -6px 12px rgba(0,0,0,.35)",
      }} />
      <span className={cn("absolute -inset-1 rounded-full border border-white/25", spinning && "orb-ring")} style={{ transform: "rotateX(70deg)" }} />
      <Sparkles className="relative size-[45%] text-white drop-shadow" />
    </span>
  );
}

function Bubble({ m }: { m: Msg }) {
  const mine = m.role === "user";
  return (
    <div className={cn("flex gap-2.5", mine && "flex-row-reverse")}>
      {!mine && <Orb size={28} />}
      <div className={cn("max-w-[85%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed",
        mine ? "text-[#0b0b0c]" : "border bg-card-solid")} style={mine ? { background: "var(--tone-purple)" } : undefined}>
        <p className="whitespace-pre-wrap">{m.content}</p>
        {m.actions && m.actions.length > 0 && (
          <span className="mt-2 flex flex-wrap gap-1.5">
            {m.actions.map((a) => <Link key={a.href + a.label} href={a.href} className="rounded-full border px-2.5 py-1 text-xs font-medium hover:bg-muted">{a.label} →</Link>)}
          </span>
        )}
      </div>
    </div>
  );
}

/** The chat itself (used full-page and in the corner panel). */
export function Chat({ compact = false }: { compact?: boolean }) {
  const { msgs, busy, send, clear } = useChat();
  const [text, setText] = useState("");
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [msgs, busy]);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-4">
        {msgs.length === 0 && (
          <div className="flex flex-col items-center gap-4 py-6 text-center">
            <Orb size={compact ? 56 : 84} spinning />
            <div>
              <p className="text-lg font-semibold">Hi, I&apos;m Saige</p>
              <p className="text-sm text-muted-foreground">Ask about your jobs, applications, interviews, recruiters or resume.</p>
            </div>
            <div className={cn("grid w-full gap-2", !compact && "sm:grid-cols-2")}>
              {SUGGESTIONS.slice(0, compact ? 4 : 6).map((s) => (
                <button key={s} type="button" onClick={() => send(s)} className="lift rounded-2xl border px-3 py-2.5 text-left text-sm hover:bg-muted">{s}</button>
              ))}
            </div>
          </div>
        )}
        {msgs.map((m, i) => <Bubble key={i} m={m} />)}
        {busy && <div className="flex items-center gap-2 text-sm text-muted-foreground"><Orb size={28} spinning /> Thinking…</div>}
        <div ref={end} />
      </div>
      <form onSubmit={(e) => { e.preventDefault(); void send(text); setText(""); }} className="flex items-end gap-2 border-t p-3">
        {msgs.length > 0 && (
          <button type="button" onClick={clear} aria-label="Clear chat" className="grid size-10 shrink-0 place-items-center rounded-full text-muted-foreground hover:bg-muted"><Trash2 className="size-4" /></button>
        )}
        <textarea value={text} onChange={(e) => setText(e.target.value)} rows={1} placeholder="Ask Saige anything about your job search…"
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void send(text); setText(""); } }}
          className="max-h-32 min-h-10 flex-1 resize-none rounded-2xl border bg-transparent px-3.5 py-2.5 text-sm outline-none focus:ring-2 focus:ring-[var(--tone-purple)]" />
        <button type="submit" disabled={busy || !text.trim()} aria-label="Send"
          className="grid size-10 shrink-0 place-items-center rounded-full text-[#0b0b0c] disabled:opacity-40" style={{ background: "var(--tone-purple)" }}>
          {busy ? <Loader2 className="size-4 animate-spin" /> : <ArrowUp className="size-4" />}
        </button>
      </form>
    </div>
  );
}

/** Floating assistant in the bottom-right corner of every page. */
export function AssistantBubble() {
  const [open, setOpen] = useState(false);
  return (
    <>
      {open && (
        <div className="animate-pop fixed bottom-24 right-4 z-50 flex h-[min(620px,75vh)] w-[min(400px,calc(100vw-2rem))] flex-col overflow-hidden rounded-3xl border bg-card-solid shadow-[0_30px_80px_-20px_rgba(0,0,0,.6)]">
          <div className="flex items-center gap-2 border-b px-4 py-3">
            <Orb size={30} />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold">Saige AI</p>
              <p className="text-xs text-muted-foreground">Your job-search assistant</p>
            </div>
            <Link href="/assistant" className="rounded-full px-2.5 py-1 text-xs hover:bg-muted" onClick={() => setOpen(false)}>Full screen</Link>
            <button type="button" onClick={() => setOpen(false)} aria-label="Close assistant" className="grid size-8 place-items-center rounded-full hover:bg-muted"><X className="size-4" /></button>
          </div>
          <Chat compact />
        </div>
      )}
      <button type="button" onClick={() => setOpen(!open)} aria-label={open ? "Close Saige AI" : "Ask Saige AI"}
        className="orb-float fixed bottom-5 right-5 z-50 rounded-full transition-transform hover:scale-110 active:scale-95">
        <Orb size={58} spinning={open} />
      </button>
    </>
  );
}
