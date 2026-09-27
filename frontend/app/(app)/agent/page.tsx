"use client";

import { Ban, Hand, MailQuestion, Repeat, Save, X, Zap } from "lucide-react";
import { useState } from "react";

import { Notice, PageHeader } from "@/components/app-shell";
import { AutoApplyCard } from "@/components/jobs-feed";
import { Loader3D } from "@/components/loader3d";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/form";
import { useApi } from "@/hooks/use-api";
import { request } from "@/services/api";
import type { AutomationSettings } from "@/types/api";

const REPLY_TOPICS: { key: "talent_details" | "resume" | "next_step" | "job_details"; label: string; hint: string }[] = [
  { key: "talent_details", label: "Talent details", hint: "CTC, notice period, location, relocation and experience, from your verified profile." },
  { key: "resume", label: "Resume / CV", hint: "Attach your latest resume when they ask for it." },
  { key: "next_step", label: "Application next step", hint: "Confirm you're happy to talk and ask for time slots." },
  { key: "job_details", label: "Job details", hint: "Ask for the job ID or posting link when it's missing." },
];

function Section({ icon: Icon, tone, title, desc, children }: { icon: typeof Ban; tone: string; title: string; desc: string; children: React.ReactNode }) {
  return (
    <Card className="animate-rise mb-6" style={{ borderColor: `color-mix(in srgb, var(--tone-${tone}) 28%, transparent)` }}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <span className="grid size-8 place-items-center rounded-lg text-[#0b0b0c]" style={{ background: `var(--tone-${tone})` }}><Icon className="size-4" /></span>
          {title}
        </CardTitle>
        <CardDescription>{desc}</CardDescription>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

export default function AgentPage() {
  const { data, reload } = useApi<AutomationSettings>("/automation/status");
  const [company, setCompany] = useState("");
  const [days, setDays] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [tplKind, setTplKind] = useState("cold");
  const [tplText, setTplText] = useState<string | null>(null);

  async function save(patch: Partial<AutomationSettings>) {
    setErr(null);
    try {
      await request("/automation/settings", { method: "PUT", body: patch });
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not save");
    }
  }

  if (!data) return <div className="grid place-items-center py-24"><Loader3D size={64} /></div>;
  const ar = data.auto_reply;
  const fu = data.followups;
  const om = data.outreach;
  const tpl = tplText ?? om.templates[tplKind] ?? "";
  return (
    <>
      <PageHeader title="Agent" description="How your Saige agent works for you: replies to recruiters, follow-ups, the auto-applier and companies to avoid." />
      {err && <div className="mb-4"><Notice tone="error">{err}</Notice></div>}

      <Section icon={Zap} tone="orange" title="Outreach mode"
        desc="Choose how your agent sends email. Auto mode is your standing approval: Saige sends truth-checked messages from your Gmail within the limits (10 a day, 3 people per company a week) and tells you on WhatsApp each time.">
        <div className="grid gap-3 md:grid-cols-2">
          {([["auto", "Auto mode", "Recommended · the agent handles outreach", Zap, ["Sends its replies to recruiters", "Sends follow-ups when there's no reply", "Optional: emails HR contacts listed in jobs you applied to", "Every message truth-checked and within limits"]],
             ["manual", "Manual mode", "Review before anything is sent", Hand, ["Drafts wait in Recruiters → Queue", "You edit and approve each message", "Nothing is sent without your click"]]] as const).map(([id, title, sub, Icon, points]) => (
            <button key={id} type="button" onClick={() => save({ outreach: { ...om, mode: id } })}
              className="flex flex-col gap-2 rounded-2xl border p-4 text-left transition-colors"
              style={om.mode === id ? { borderColor: "var(--tone-orange)", background: "color-mix(in srgb, var(--tone-orange) 8%, transparent)" } : undefined}>
              <span className="flex items-center gap-2 text-base font-semibold"><Icon className="size-5" style={{ color: "var(--tone-orange)" }} /> {title}
                {om.mode === id && <span className="ml-auto rounded-full px-2 py-0.5 text-[11px] font-semibold text-[#0b0b0c]" style={{ background: "var(--tone-orange)" }}>Selected</span>}</span>
              <span className="text-xs text-muted-foreground">{sub}</span>
              <ul className="mt-1 list-disc space-y-0.5 pl-5 text-sm text-muted-foreground">{points.map((p) => <li key={p}>{p}</li>)}</ul>
            </button>
          ))}
        </div>
        {om.mode === "auto" && (
          <div className="mt-4 flex flex-wrap gap-x-6 gap-y-2 text-sm">
            {([["send_replies", "Send replies to recruiters"], ["send_followups", "Send follow-ups"], ["cold_email_jobs", "Email HR contacts in jobs I applied to"]] as const).map(([k, label]) => (
              <label key={k} className="inline-flex items-center gap-2">
                <input type="checkbox" className="size-4 accent-[var(--tone-orange)]" checked={om[k]} onChange={(e) => save({ outreach: { ...om, [k]: e.target.checked } })} /> {label}
              </label>
            ))}
          </div>
        )}
      </Section>

      <Section icon={Save} tone="purple" title="Your message templates"
        desc="Write your own email for each kind of message. Variables are filled in for each person and job. Leave empty to use Saige's template. Every message is still checked against your verified profile.">
        <div className="mb-3 flex flex-wrap gap-1.5">
          {([["cold", "Cold email to HR"], ["referral", "Referral request"], ["hiring_manager", "Hiring manager"], ["followup", "Follow-up"], ["thank_you", "Thank-you"]] as const).map(([k, label]) => (
            <button key={k} type="button" onClick={() => { setTplKind(k); setTplText(null); }}
              className="rounded-full border px-3 py-1 text-xs" style={tplKind === k ? { background: "var(--tone-purple)", color: "#0b0b0c", borderColor: "transparent", fontWeight: 600 } : undefined}>
              {label}{om.templates[k] ? " ✓" : ""}
            </button>
          ))}
        </div>
        <textarea rows={7} value={tpl} onChange={(e) => setTplText(e.target.value)}
          placeholder={"Hi {{firstName}},\n\nI'm {{myName}}, a {{myRole}}. I'm applying for the {{jobTitle}} role at {{companyName}} ({{jobLink}}). If you're comfortable referring me, I'd really appreciate it.\n\nThanks,\n{{myName}}"}
          className="w-full rounded-2xl border bg-transparent p-3 text-sm outline-none focus:ring-2 focus:ring-[var(--tone-purple)]" />
        <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs">
          <span className="text-muted-foreground">Insert:</span>
          {["firstName", "fullName", "companyName", "jobTitle", "jobLink", "myName", "myRole", "myPhone"].map((v) => (
            <button key={v} type="button" className="rounded-md border px-1.5 py-0.5 font-mono hover:bg-muted" onClick={() => setTplText(`${tpl}{{${v}}}`)}>{`{{${v}}}`}</button>
          ))}
          <Button size="sm" className="ml-auto" onClick={async () => { await save({ outreach: { ...om, templates: { ...om.templates, [tplKind]: tpl } } }); setTplText(null); }}>Save template</Button>
        </div>
      </Section>

      <Section icon={MailQuestion} tone="teal" title="Auto-reply to recruiters"
        desc="When a recruiter emails you, Saige drafts the answer to what they asked, using only your verified profile, and attaches your resume if they asked for it. In Manual mode you send it from Recruiters → Queue; in Auto mode it's sent for you.">
        <label className="mb-4 inline-flex items-center gap-2 text-sm font-medium">
          <input type="checkbox" className="size-4 accent-[var(--tone-teal)]" checked={ar.enabled} onChange={(e) => save({ auto_reply: { ...ar, enabled: e.target.checked } })} />
          Draft replies automatically
        </label>
        <div className="grid gap-2 md:grid-cols-2">
          {REPLY_TOPICS.map((t) => (
            <label key={t.key} className="flex items-start gap-3 rounded-2xl border p-3 text-sm">
              <input type="checkbox" className="mt-0.5 size-4 accent-[var(--tone-teal)]" disabled={!ar.enabled} checked={ar[t.key]}
                onChange={(e) => save({ auto_reply: { ...ar, [t.key]: e.target.checked } })} />
              <span><span className="block font-medium">{t.label}</span><span className="text-xs text-muted-foreground">{t.hint}</span></span>
            </label>
          ))}
        </div>
      </Section>

      <Section icon={Repeat} tone="lime" title="Follow-ups"
        desc="After an outreach email is sent, Saige reminds you (and drafts the follow-up) on these days. Follow-ups stop automatically when they reply.">
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <label className="inline-flex items-center gap-2 font-medium">
            <input type="checkbox" className="size-4 accent-[var(--tone-lime)]" checked={fu.enabled} onChange={(e) => save({ followups: { ...fu, enabled: e.target.checked } })} /> Schedule follow-ups
          </label>
          <span className="text-muted-foreground">Days after sending:</span>
          {fu.days.map((d) => <span key={d} className="rounded-full px-2.5 py-0.5 font-semibold text-[#0b0b0c]" style={{ background: "var(--tone-lime)" }}>Day {d}</span>)}
          <Input className="h-8 w-40" placeholder="e.g. 3, 7, 14" value={days} onChange={(e) => setDays(e.target.value)} />
          <Button size="sm" variant="outline" disabled={!days.trim()} onClick={async () => {
            const list = days.split(/[,\s]+/).map(Number).filter((n) => n >= 1 && n <= 60);
            await save({ followups: { ...fu, days: list } });
            setDays("");
          }}>Save days</Button>
        </div>
      </Section>

      <AutoApplyCard />

      <Section icon={Ban} tone="red" title="Blocked companies"
        desc="Saige never shows jobs from, auto-applies to, or emails people at these companies (for example your current employer).">
        <form className="mb-3 flex gap-2" onSubmit={async (e) => {
          e.preventDefault();
          if (!company.trim()) return;
          await save({ blocked_companies: [...data.blocked_companies, company.trim()] });
          setCompany("");
        }}>
          <Input className="max-w-sm" placeholder="Company name" value={company} onChange={(e) => setCompany(e.target.value)} />
          <Button type="submit" variant="outline">Block</Button>
        </form>
        <div className="flex flex-wrap gap-2">
          {data.blocked_companies.length === 0 && <p className="text-sm text-muted-foreground">No blocked companies.</p>}
          {data.blocked_companies.map((b) => (
            <span key={b} className="inline-flex items-center gap-1 rounded-full border px-3 py-1 text-sm">
              {b}
              <button type="button" aria-label={`Unblock ${b}`} onClick={() => save({ blocked_companies: data.blocked_companies.filter((x) => x !== b) })}><X className="size-3.5" /></button>
            </span>
          ))}
        </div>
      </Section>
    </>
  );
}
