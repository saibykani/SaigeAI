"use client";

import { Pencil, Plus, Save, Trash2, X } from "lucide-react";
import { useEffect, useState } from "react";

import { Notice } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Field, Input, Textarea } from "@/components/ui/form";
import { request } from "@/services/api";

type Exp = { title?: string | null; company?: string | null; responsibilities?: string[]; achievements?: string[]; [k: string]: unknown };
type Proj = { name?: string | null; description?: string | null; highlights?: string[]; technologies?: string[]; [k: string]: unknown };
type Parsed = { summary?: string | null; skills?: string[]; experience?: Exp[]; projects?: Proj[]; [k: string]: unknown };
type Detail = { name: string; current_version: { parsed: Parsed } | null };

const lines = (s: string) => s.split("\n").map((x) => x.trim()).filter(Boolean);
const list = (s: string) => s.split(",").map((x) => x.trim()).filter(Boolean);

/** Edit a resume version in place: summary, skills, experience bullets, projects. Saves a new version (old ones kept). */
export function ResumeEditor({ resumeId, onClose, onSaved }: { resumeId: string; onClose: () => void; onSaved?: () => void }) {
  const [p, setP] = useState<Parsed | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    request<Detail>(`/resumes/${resumeId}`).then((d) => setP(d.current_version?.parsed ?? {})).catch((e) => setErr(e instanceof Error ? e.message : "Couldn't load the resume."));
  }, [resumeId]);

  async function save() {
    if (!p) return;
    setBusy(true);
    setErr(null);
    try {
      await request(`/resumes/${resumeId}`, { method: "PUT", body: { parsed: p, change_note: "Edited by you" } });
      onSaved?.();
      onClose();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Couldn't save.");
    } finally {
      setBusy(false);
    }
  }

  const setExp = (i: number, patch: Partial<Exp>) => setP((x) => x && { ...x, experience: (x.experience ?? []).map((e, k) => (k === i ? { ...e, ...patch } : e)) });
  const setProj = (i: number, patch: Partial<Proj>) => setP((x) => x && { ...x, projects: (x.projects ?? []).map((e, k) => (k === i ? { ...e, ...patch } : e)) });

  return (
    <div className="space-y-4 rounded-2xl border p-4">
      <div className="flex items-center justify-between">
        <p className="flex items-center gap-2 font-medium"><Pencil className="size-4 text-primary" /> Edit resume</p>
        <Button size="sm" variant="ghost" onClick={onClose} aria-label="Close"><X /></Button>
      </div>
      {err && <Notice tone="error">{err}</Notice>}
      {!p ? <div className="skeleton h-40 rounded-xl" /> : (
        <>
          <Field label="Professional summary"><Textarea rows={5} value={p.summary ?? ""} onChange={(e) => setP({ ...p, summary: e.target.value })} /></Field>
          <Field label="Skills (comma separated)"><Textarea rows={3} value={(p.skills ?? []).join(", ")} onChange={(e) => setP({ ...p, skills: list(e.target.value) })} /></Field>
          <div className="space-y-3">
            <p className="text-sm font-medium">Experience</p>
            {(p.experience ?? []).map((e, i) => (
              <div key={i} className="space-y-2 rounded-xl bg-muted/40 p-3">
                <div className="grid gap-2 sm:grid-cols-2">
                  <Input value={e.title ?? ""} onChange={(ev) => setExp(i, { title: ev.target.value })} placeholder="Title" />
                  <Input value={e.company ?? ""} onChange={(ev) => setExp(i, { company: ev.target.value })} placeholder="Company" />
                </div>
                <Textarea rows={5} value={[...(e.achievements ?? []), ...(e.responsibilities ?? [])].join("\n")} onChange={(ev) => setExp(i, { achievements: lines(ev.target.value), responsibilities: [] })} placeholder="One bullet per line" />
              </div>
            ))}
          </div>
          <div className="space-y-3">
            <p className="text-sm font-medium">Projects</p>
            {(p.projects ?? []).map((pr, i) => (
              <div key={i} className="space-y-2 rounded-xl bg-muted/40 p-3">
                <div className="flex gap-2">
                  <Input value={pr.name ?? ""} onChange={(ev) => setProj(i, { name: ev.target.value })} placeholder="Project name" />
                  <Button size="sm" variant="ghost" onClick={() => setP({ ...p, projects: (p.projects ?? []).filter((_, k) => k !== i) })} aria-label="Remove project"><Trash2 /></Button>
                </div>
                <Textarea rows={3} value={(pr.highlights ?? []).join("\n")} onChange={(ev) => setProj(i, { highlights: lines(ev.target.value) })} placeholder="Highlights, one per line" />
                <Input value={(pr.technologies ?? []).join(", ")} onChange={(ev) => setProj(i, { technologies: list(ev.target.value) })} placeholder="Technologies, comma separated" />
              </div>
            ))}
            <Button size="sm" variant="outline" onClick={() => setP({ ...p, projects: [...(p.projects ?? []), { name: "", highlights: [], technologies: [] }] })}><Plus /> Add project</Button>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button onClick={() => void save()} disabled={busy}><Save /> {busy ? "Saving…" : "Save changes"}</Button>
            <span className="text-xs text-muted-foreground">Saved as a new version; downloads and emails use it. Only write what is true.</span>
          </div>
        </>
      )}
    </div>
  );
}
