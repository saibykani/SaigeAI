"use client";

import { Send, Undo2 } from "lucide-react";
import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";

export const UNDO_SECONDS = 5;

type Job = { id: number; label: string; left: number };
type Starter = (label: string, run: () => Promise<void>, opts?: { onUndo?: () => void }) => void;

const Ctx = createContext<Starter | null>(null);

/** One-tap sending: shows "Sending… Undo" for 5 seconds, then runs the single approve-and-send call. */
export function useUndoSend(): Starter {
  const fn = useContext(Ctx);
  return fn ?? ((_label, run) => void run());
}

export function UndoSendProvider({ children }: { children: React.ReactNode }) {
  const [jobs, setJobs] = useState<Job[]>([]);
  const timers = useRef<Map<number, { timer: ReturnType<typeof setInterval>; run: () => Promise<void>; onUndo?: () => void }>>(new Map());
  const seq = useRef(0);

  const drop = useCallback((id: number) => {
    const t = timers.current.get(id);
    if (t) clearInterval(t.timer);
    timers.current.delete(id);
    setJobs((j) => j.filter((x) => x.id !== id));
  }, []);

  const start: Starter = useCallback((label, run, opts) => {
    const id = ++seq.current;
    setJobs((j) => [...j, { id, label, left: UNDO_SECONDS }]);
    const timer = setInterval(() => {
      setJobs((j) => j.map((x) => (x.id === id ? { ...x, left: x.left - 1 } : x)));
    }, 1000);
    timers.current.set(id, { timer, run, onUndo: opts?.onUndo });
  }, []);

  // fire the send when the countdown reaches zero
  useEffect(() => {
    for (const j of jobs) {
      if (j.left <= 0) {
        const t = timers.current.get(j.id);
        drop(j.id);
        if (t) void t.run();
      }
    }
  }, [jobs, drop]);

  useEffect(() => {
    const map = timers.current;
    return () => map.forEach((t) => clearInterval(t.timer));
  }, []);

  function undo(id: number) {
    const t = timers.current.get(id);
    drop(id);
    t?.onUndo?.();
  }

  return (
    <Ctx.Provider value={start}>
      {children}
      <div className="pointer-events-none fixed inset-x-0 bottom-4 z-[80] flex flex-col items-center gap-2 px-4" aria-live="polite">
        {jobs.map((j) => (
          <div key={j.id} className="pointer-events-auto flex max-w-md items-center gap-3 rounded-full border bg-card-solid px-4 py-2 text-sm shadow-lg">
            <Send className="size-4 text-muted-foreground" />
            <span className="min-w-0 truncate">Sending {j.label}… {Math.max(j.left, 0)}s</span>
            <Button size="sm" variant="outline" onClick={() => undo(j.id)}><Undo2 /> Undo</Button>
          </div>
        ))}
      </div>
    </Ctx.Provider>
  );
}
