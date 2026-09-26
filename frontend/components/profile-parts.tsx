"use client";

import { Check, ClipboardCopy, ExternalLink, FileText, Pencil, ShieldCheck, X } from "lucide-react";
import { useEffect, useState } from "react";

import { Notice } from "@/components/app-shell";
import { CountUp, ProgressRing } from "@/components/motion";
import { TagInput } from "@/components/tag-input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input, Textarea } from "@/components/ui/form";
import { useApi } from "@/hooks/use-api";
import { request } from "@/services/api";
import type { LinkedInSnapshot, NaukriSnapshot, ProfileChange, SyncPlatform } from "@/types/api";
import { cn } from "@/utils/cn";
import { UNKNOWN, formatDate, numberOrNull } from "@/utils/format";

export const BRAND = {
  linkedin: { name: "LinkedIn", color: "#0a66c2", mark: "in", edit: "https://www.linkedin.com/in/me/edit/intro/" },
  naukri: { name: "Naukri", color: "#275df5", mark: "N", edit: "https://www.naukri.com/mnjuser/profile" },
  resume: { name: "Master resume", color: "var(--series-3)", mark: "CV", edit: "/resumes" },
} as const;

export const FIELD_LABEL: Record<string, string> = {
  headline: "Headline",
  about: "About",
  summary: "Profile summary",
  skills: "Skills",
  key_skills: "Key skills",
  "open_to_work.titles": "Open-to-Work job titles",
  current_title: "Current title",
  preferred_locations: "Preferred locations",
  preferred_roles: "Preferred roles",
  notice_period_days: "Notice period (days)",
  expected_salary: "Expected salary",
  total_experience_years: "Total experience",
  resume_updated_on: "Resume refresh",
};

export function BrandMark({ platform, size = 40 }: { platform: SyncPlatform; size?: number }) {
  const b = BRAND[platform];
  return (
    <span
      className="grid shrink-0 place-items-center rounded-xl text-sm font-bold text-white shadow-sm"
      style={{ background: b.color, width: size, height: size }}
      aria-hidden
    >
      {platform === "resume" ? <FileText className="size-4" /> : b.mark}
    </span>
  );
}

export function asText(v: ProfileChange["after"]): string {
  if (v === null || v === undefined) return "";
  return Array.isArray(v) ? v.join(", ") : String(v);
}

export function ChangeCard({ change, onChange, delay }: { change: ProfileChange; onChange: () => void; delay: number }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(asText(change.after));
  const [msg, setMsg] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const [copied, setCopied] = useState(false);
  const b = BRAND[change.platform];
  const isList = Array.isArray(change.after);
  const added = isList && Array.isArray(change.before) ? (change.after as string[]).filter((x) => !(change.before as string[]).includes(x)) : isList ? (change.after as string[]) : [];

  async function act(path: string, method: "POST" | "PUT" = "POST", body?: unknown) {
    setMsg(null);
    try {
      await request(`/profile-changes/${change.id}${path}`, { method, body });
      onChange();
    } catch (e) {
      setMsg({ tone: "error", text: e instanceof Error ? e.message : "Action failed" });
    }
  }

  async function copy() {
    await navigator.clipboard.writeText(asText(change.after));
    setCopied(true);
    setTimeout(() => setCopied(false), 1600);
  }

  const status = change.applied_at ? "Updated" : change.approval_status === "USER_APPROVED" ? "Approved" : change.approval_status === "USER_REJECTED" ? "Rejected" : "Needs review";
  const statusTone = change.applied_at ? "success" : change.approval_status === "USER_REJECTED" ? "muted" : change.approval_status === "USER_APPROVED" ? "default" : "warning";

  return (
    <Card className="lift animate-rise overflow-hidden" style={{ animationDelay: `${delay}ms` }}>
      <div className="h-1 w-full" style={{ background: b.color }} aria-hidden />
      <CardHeader className="flex-row items-start gap-3">
        <BrandMark platform={change.platform} size={36} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <CardTitle>{FIELD_LABEL[change.field] ?? change.field}</CardTitle>
            <Badge variant={statusTone as "success" | "muted" | "default" | "warning"}>{status}</Badge>
            <Badge variant="outline" title="How confident Saige is that this change helps">
              {Math.round(change.ai_confidence * 100)}% confidence
            </Badge>
            {change.validation.status === "PASSED" && (
              <Badge variant="success" title="Checked against your verified profile — nothing fabricated">
                <ShieldCheck className="size-3" /> Verified
              </Badge>
            )}
          </div>
          <CardDescription className="mt-1">{change.reason}</CardDescription>
          {change.source_jobs.length > 0 && (
            <p className="mt-1 text-xs text-muted-foreground">Based on {change.source_jobs.length} recent job description(s)</p>
          )}
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {!isList && (
          <div className="grid gap-3 md:grid-cols-2">
            <div className="rounded-xl border bg-muted/50 p-3">
              <p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Before</p>
              <p className="whitespace-pre-wrap text-sm text-muted-foreground">{asText(change.before) || UNKNOWN}</p>
            </div>
            <div className="rounded-xl border border-primary/30 bg-accent/60 p-3">
              <p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-accent-foreground">After</p>
              {editing ? (
                <Textarea rows={4} value={draft} onChange={(e) => setDraft(e.target.value)} />
              ) : (
                <p className="whitespace-pre-wrap text-sm">{asText(change.after)}</p>
              )}
            </div>
          </div>
        )}
        {isList && (
          <div className="rounded-xl border bg-muted/40 p-3">
            <p className="mb-2 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
              {added.length} to add · {(change.after as string[]).length} total
            </p>
            {editing ? (
              <TagInput value={draft ? draft.split(",").map((s) => s.trim()).filter(Boolean) : []} onChange={(v) => setDraft(v.join(", "))} />
            ) : (
              <div className="flex flex-wrap gap-1.5">
                {(change.after as string[]).map((s) => (
                  <span
                    key={s}
                    className={cn(
                      "rounded-full px-2.5 py-0.5 text-xs font-medium",
                      added.includes(s) ? "bg-success/15 text-success ring-1 ring-success/30" : "bg-card-solid text-muted-foreground ring-1 ring-border",
                    )}
                  >
                    {added.includes(s) && "+ "}
                    {s}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}
        {msg && <Notice tone={msg.tone}>{msg.text}</Notice>}
        <div className="flex flex-wrap items-center gap-2">
          {editing ? (
            <>
              <Button
                size="sm"
                onClick={async () => {
                  await act("", "PUT", { after: isList ? draft.split(",").map((s) => s.trim()).filter(Boolean) : draft });
                  setEditing(false);
                }}
              >
                <Check /> Save edit
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>Cancel</Button>
            </>
          ) : (
            <>
              <Button size="sm" variant="gradient" className="animate-gradient" onClick={copy}>
                <ClipboardCopy /> {copied ? "Copied!" : `Copy for ${b.name}`}
              </Button>
              {change.platform !== "resume" && (
                <a href={b.edit} target="_blank" rel="noopener noreferrer" className="inline-flex h-8 items-center gap-1.5 rounded-full border px-3.5 text-xs font-medium hover:bg-muted">
                  <ExternalLink className="size-3.5" /> Open {b.name}
                </a>
              )}
              {!change.applied_at && change.approval_status !== "USER_REJECTED" && (
                <>
                  <Button size="sm" variant="outline" onClick={() => act("/applied")}>
                    <Check /> {change.platform === "resume" ? "Apply to resume" : "Mark as updated"}
                  </Button>
                  {change.approval_status === "USER_APPROVAL_REQUIRED" && (
                    <Button size="sm" variant="ghost" onClick={() => act("/approve")}>Approve</Button>
                  )}
                  <Button size="sm" variant="ghost" onClick={() => { setDraft(asText(change.after)); setEditing(true); }}>
                    <Pencil /> Edit
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => act("/reject")}>
                    <X /> Reject
                  </Button>
                </>
              )}
              {change.applied_at && <span className="text-xs text-muted-foreground">Updated {formatDate(change.applied_at)}</span>}
            </>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export function PlatformScore({ platform, completeness, alignment, pending, delay }: { platform: "linkedin" | "naukri"; completeness: number; alignment: number; pending: number; delay: number }) {
  const b = BRAND[platform];
  return (
    <Card className="lift animate-rise relative overflow-hidden p-5" style={{ animationDelay: `${delay}ms` }}>
      <div aria-hidden className="pointer-events-none absolute -right-10 -top-10 size-32 rounded-full opacity-15 blur-2xl" style={{ background: b.color }} />
      <div className="flex items-center gap-3">
        <BrandMark platform={platform} />
        <div>
          <p className="font-semibold">{b.name}</p>
          <p className="text-xs text-muted-foreground">{pending} suggestion(s) waiting</p>
        </div>
      </div>
      <div className="mt-5 flex items-center gap-5">
        <ProgressRing value={completeness} size={84} stroke={8} trackClass="stroke-muted" barClass="stroke-[var(--series-1)]">
          <span className="text-lg font-semibold"><CountUp value={completeness} suffix="%" /></span>
        </ProgressRing>
        <div className="flex-1 text-sm">
          <p className="text-muted-foreground">Profile completeness</p>
          <p className="mt-3 text-muted-foreground">Keyword alignment</p>
          <div className="mt-1 flex items-center gap-2">
            <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
              <div className="animate-grow-x h-full rounded-full" style={{ width: `${alignment}%`, background: b.color }} />
            </div>
            <span className="w-10 text-right font-medium">{alignment}%</span>
          </div>
        </div>
      </div>
    </Card>
  );
}

export function SnapshotEditors({ onSaved, only }: { onSaved: () => void; only?: "linkedin" | "naukri" }) {
  const li = useApi<LinkedInSnapshot>("/profile/linkedin");
  const nk = useApi<NaukriSnapshot>("/profile/naukri");
  const [l, setL] = useState<LinkedInSnapshot | null>(null);
  const [n, setN] = useState<NaukriSnapshot | null>(null);
  const [msg, setMsg] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  useEffect(() => { if (li.data) setL(li.data); }, [li.data]);
  useEffect(() => { if (nk.data) setN(nk.data); }, [nk.data]);
  if (!l || !n) return <div className="skeleton h-96 rounded-2xl" />;
  const orNull = (v: string) => (v.trim() ? v : null);

  async function save(platform: "linkedin" | "naukri") {
    setMsg(null);
    try {
      await request(`/profile/${platform}`, { method: "PUT", body: platform === "linkedin" ? l : n });
      setMsg({ tone: "success", text: `${BRAND[platform].name} snapshot saved. Run optimization to refresh suggestions.` });
      onSaved();
    } catch (e) {
      setMsg({ tone: "error", text: e instanceof Error ? e.message : "Save failed" });
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <Notice>
        Paste what is currently on your LinkedIn and Naukri profiles. Saige compares it with your verified master profile and recent job descriptions — it never logs in to either site.
      </Notice>
      {msg && <Notice tone={msg.tone}>{msg.text}</Notice>}
      <div className={cn("grid gap-6", !only && "xl:grid-cols-2")}>
        {only !== "naukri" && <Card>
          <CardHeader className="flex-row items-center gap-3"><BrandMark platform="linkedin" size={32} /><CardTitle>Your LinkedIn today</CardTitle></CardHeader>
          <CardContent className="grid gap-3">
            <Field label="Profile URL"><Input value={l.profile_url ?? ""} onChange={(e) => setL({ ...l, profile_url: orNull(e.target.value) })} placeholder="https://www.linkedin.com/in/…" /></Field>
            <Field label={`Headline (${(l.headline ?? "").length}/220)`}><Input maxLength={220} value={l.headline ?? ""} onChange={(e) => setL({ ...l, headline: orNull(e.target.value) })} /></Field>
            <Field label={`About (${(l.about ?? "").length}/2600)`}><Textarea rows={5} maxLength={2600} value={l.about ?? ""} onChange={(e) => setL({ ...l, about: orNull(e.target.value) })} /></Field>
            <Field label="Current title"><Input value={l.current_title ?? ""} onChange={(e) => setL({ ...l, current_title: orNull(e.target.value) })} /></Field>
            <Field label="Skills"><TagInput value={l.skills} onChange={(skills) => setL({ ...l, skills })} /></Field>
            <Field label="Education"><TagInput value={l.education} onChange={(education) => setL({ ...l, education })} placeholder="e.g. B.Tech, JNTU" /></Field>
            <Field label="Certifications"><TagInput value={l.certifications} onChange={(certifications) => setL({ ...l, certifications })} /></Field>
            <Field label="Open-to-Work job titles"><TagInput value={l.open_to_work.titles} onChange={(titles) => setL({ ...l, open_to_work: { ...l.open_to_work, titles } })} /></Field>
            <div><Button onClick={() => save("linkedin")}>Save LinkedIn snapshot</Button></div>
          </CardContent>
        </Card>}
        {only !== "linkedin" && <Card>
          <CardHeader className="flex-row items-center gap-3"><BrandMark platform="naukri" size={32} /><CardTitle>Your Naukri today</CardTitle></CardHeader>
          <CardContent className="grid gap-3">
            <Field label="Profile URL"><Input value={n.profile_url ?? ""} onChange={(e) => setN({ ...n, profile_url: orNull(e.target.value) })} placeholder="https://www.naukri.com/mnjuser/profile" /></Field>
            <Field label={`Resume headline (${(n.headline ?? "").length}/250)`}><Input maxLength={250} value={n.headline ?? ""} onChange={(e) => setN({ ...n, headline: orNull(e.target.value) })} /></Field>
            <Field label={`Profile summary (${(n.summary ?? "").length}/1000)`}><Textarea rows={5} maxLength={1000} value={n.summary ?? ""} onChange={(e) => setN({ ...n, summary: orNull(e.target.value) })} /></Field>
            <Field label="Key skills"><TagInput value={n.key_skills} onChange={(key_skills) => setN({ ...n, key_skills })} /></Field>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Current designation"><Input value={n.current_designation ?? ""} onChange={(e) => setN({ ...n, current_designation: orNull(e.target.value) })} /></Field>
              <Field label="Current company"><Input value={n.current_company ?? ""} onChange={(e) => setN({ ...n, current_company: orNull(e.target.value) })} /></Field>
              <Field label="Total experience (years)"><Input type="number" min={0} step="any" value={n.total_experience_years ?? ""} onChange={(e) => setN({ ...n, total_experience_years: numberOrNull(e.target.value) })} /></Field>
              <Field label="Notice period (days)"><Input type="number" min={0} value={n.notice_period_days ?? ""} onChange={(e) => setN({ ...n, notice_period_days: numberOrNull(e.target.value) })} /></Field>
              <Field label="Expected salary"><Input type="number" min={0} value={n.expected_salary ?? ""} onChange={(e) => setN({ ...n, expected_salary: numberOrNull(e.target.value) })} /></Field>
              <Field label="Resume last updated"><Input type="date" value={n.resume_updated_on ?? ""} onChange={(e) => setN({ ...n, resume_updated_on: orNull(e.target.value) })} /></Field>
            </div>
            <Field label="Preferred roles"><TagInput value={n.preferred_roles} onChange={(preferred_roles) => setN({ ...n, preferred_roles })} /></Field>
            <Field label="Preferred locations"><TagInput value={n.preferred_locations} onChange={(preferred_locations) => setN({ ...n, preferred_locations })} /></Field>
            <div><Button onClick={() => save("naukri")}>Save Naukri snapshot</Button></div>
          </CardContent>
        </Card>}
      </div>
    </div>
  );
}

