"use client";

import { CheckCircle2 } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { request } from "@/services/api";
import { cn } from "@/utils/cn";

/** JD keywords missing from the verified profile: tick the ones you really have, Saige adds them and rebuilds the resume. */
export function SkillConfirm({ required, preferred = [], onConfirmed }: { required: string[]; preferred?: string[]; onConfirmed: () => Promise<void> | void }) {
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const all = [...required.map((k) => [k, true] as const), ...preferred.map((k) => [k, false] as const)];
  if (!all.length) return <p className="flex items-center gap-2 text-sm text-[var(--tone-green)]"><CheckCircle2 className="size-4" /> Every JD keyword is on your resume.</p>;

  async function confirm() {
    setBusy(true);
    try {
      await request("/studio/skills/confirm", { method: "POST", body: { skills: [...picked] } });
      setPicked(new Set());
      await onConfirmed();
    } finally {
      setBusy(false);
    }
  }

  const toggle = (k: string) => setPicked((s) => { const n = new Set(s); if (n.has(k)) n.delete(k); else n.add(k); return n; });
  return (
    <div className="space-y-2">
      <p className="text-xs font-medium text-muted-foreground">
        Not in your profile yet. Tick only the ones you have really worked with: Saige adds them to your Profile and rebuilds the resume to fit the JD.
      </p>
      <div className="flex flex-wrap gap-1.5">
        {all.map(([k, req]) => (
          <button key={k} type="button" onClick={() => toggle(k)} aria-pressed={picked.has(k)}
            className={cn("rounded-full border px-2.5 py-1 text-xs", picked.has(k) ? "border-[var(--tone-green)] text-[var(--tone-green)]" : "text-muted-foreground")}>
            {picked.has(k) ? "✓ " : ""}{k}{req ? "" : " · nice to have"}
          </button>
        ))}
      </div>
      <Button size="sm" disabled={busy || picked.size === 0} onClick={() => void confirm()}>
        {busy ? "Rebuilding…" : `I have ${picked.size || "these"}: add & rebuild`}
      </Button>
    </div>
  );
}
