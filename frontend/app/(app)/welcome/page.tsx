"use client";

import { Check, FileUp, Mail, MapPin, Puzzle, UserRound } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { Notice } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/form";
import { request } from "@/services/api";
import type { Profile } from "@/types/api";
import { cn } from "@/utils/cn";

const STEPS = [
  { title: "Upload your resume", icon: FileUp },
  { title: "Check your details", icon: UserRound },
  { title: "Jobs you want", icon: MapPin },
  { title: "Connect & finish", icon: Mail },
];

type Basics = Record<"name" | "phone" | "current_location" | "current_designation" | "total_experience_years" | "notice_period_days" | "expected_ctc" | "linkedin_url", string>;
const EMPTY: Basics = { name: "", phone: "", current_location: "", current_designation: "", total_experience_years: "", notice_period_days: "", expected_ctc: "", linkedin_url: "" };
const NUM = new Set(["total_experience_years", "notice_period_days", "expected_ctc"]);
const list = (s: string) => s.split(",").map((x) => x.trim()).filter(Boolean);

/** First-run setup: 4 short steps, each skippable. The resume fills most of the profile. */
export default function WelcomePage() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const [basics, setBasics] = useState<Basics>(EMPTY);
  const [roles, setRoles] = useState("");
  const [places, setPlaces] = useState("");
  const [remote, setRemote] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  async function loadProfile() {
    const p = await request<Profile>("/profile").catch(() => null);
    if (!p) return;
    const per = p.personal as unknown as Record<string, unknown>;
    setBasics(Object.fromEntries(Object.keys(EMPTY).map((k) => [k, per[k] == null ? "" : String(per[k])])) as Basics);
    setRoles((p.preferences.target_roles ?? []).join(", "));
    setPlaces((p.preferences.preferred_locations ?? []).join(", "));
    setRemote(Boolean(p.preferences.remote_preference));
  }
  useEffect(() => { void loadProfile(); }, []);

  const next = () => { setMsg(null); setStep((s) => Math.min(s + 1, STEPS.length - 1)); };

  async function upload(file: File) {
    setBusy(true);
    setMsg(null);
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("name", file.name.replace(/\.[^.]+$/, ""));
      form.append("kind", "Master");
      const r = await request<{ id: string }>("/resumes", { method: "POST", form });
      const imp = await request<{ applied: string[]; completeness: number }>(`/resumes/${r.id}/import-to-profile`, { method: "POST" });
      await loadProfile();
      setMsg({ tone: "success", text: `Read your resume: ${imp.applied.length} sections added. Your profile is ${imp.completeness}% complete.` });
      setStep(1);
    } catch (e) {
      setMsg({ tone: "error", text: e instanceof Error ? e.message : "Couldn't read this file. Try a PDF or Word file." });
    } finally {
      setBusy(false);
    }
  }

  async function save(body: object) {
    setBusy(true);
    setMsg(null);
    try {
      await request("/profile", { method: "PUT", body });
      next();
    } catch (e) {
      setMsg({ tone: "error", text: e instanceof Error ? e.message : "Couldn't save." });
    } finally {
      setBusy(false);
    }
  }

  const saveBasics = () => {
    const personal = Object.fromEntries(Object.entries(basics).filter(([, v]) => v.trim() !== "").map(([k, v]) => [k, NUM.has(k) ? Number(v) : v.trim()]));
    return save({ personal });
  };
  const savePrefs = () => save({ preferences: { target_roles: list(roles), preferred_locations: list(places), remote_preference: remote } });

  async function finish() {
    try { localStorage.setItem("saige-welcome-done", "1"); } catch { /* private mode */ }
    await request("/suggestions/run", { method: "POST" }).catch(() => undefined);
    router.replace("/");
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-4xl font-light tracking-[-0.03em] md:text-5xl">Welcome to Saige AI</h1>
        <p className="mt-2 text-muted-foreground">Four quick steps, about 3 minutes. Skip anything and come back later.</p>
      </div>

      <ol className="grid grid-cols-4 gap-2">
        {STEPS.map((s, i) => (
          <li key={s.title}>
            <button onClick={() => setStep(i)} className="w-full text-left">
              <span className={cn("block h-1.5 rounded-full", i <= step ? "bg-primary" : "bg-muted")} />
              <span className={cn("mt-2 flex items-center gap-1.5 text-xs sm:text-sm", i === step ? "text-foreground" : "text-muted-foreground")}>
                {i < step ? <Check className="size-4 text-primary" /> : <s.icon className="size-4" />}<span className="hidden sm:inline">{s.title}</span>
              </span>
            </button>
          </li>
        ))}
      </ol>

      {msg && <Notice tone={msg.tone}>{msg.text}</Notice>}

      <section className="rounded-3xl border bg-card p-6">
        <h2 className="mb-1 text-2xl font-light">{STEPS[step].title}</h2>

        {step === 0 && (
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">Saige reads your resume and fills your profile: experience, skills, projects, education. Nothing is invented; you can edit everything.</p>
            <input ref={fileRef} type="file" accept=".pdf,.docx,.txt" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) void upload(f); }} />
            <button onClick={() => fileRef.current?.click()} disabled={busy}
              onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f) void upload(f); }}
              className="flex w-full flex-col items-center gap-2 rounded-2xl border-2 border-dashed p-10 text-center hover:bg-muted/50">
              <FileUp className="size-8 text-primary" />
              <span className="font-medium">{busy ? "Reading your resume…" : "Drop your resume here or click to choose"}</span>
              <span className="text-xs text-muted-foreground">PDF, Word or TXT, up to 5 MB</span>
            </button>
            <div className="flex justify-end"><Button variant="ghost" onClick={next}>I don&apos;t have one now</Button></div>
          </div>
        )}

        {step === 1 && (
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">Recruiters and application forms ask for these. Leave blank what you don&apos;t want to share.</p>
            <div className="grid gap-4 sm:grid-cols-2">
              {([["name", "Full name"], ["phone", "Phone"], ["current_designation", "Current role"], ["current_location", "City"],
                ["total_experience_years", "Experience (years)"], ["notice_period_days", "Notice period (days)"], ["expected_ctc", "Expected CTC (LPA)"],
                ["linkedin_url", "LinkedIn URL"]] as [keyof Basics, string][]).map(([k, label]) => (
                <Field key={k} label={label}>
                  <Input value={basics[k]} type={NUM.has(k) ? "number" : "text"} inputMode={NUM.has(k) ? "decimal" : undefined}
                    onChange={(e) => setBasics((b) => ({ ...b, [k]: e.target.value }))} />
                </Field>
              ))}
            </div>
            <div className="flex justify-between"><Button variant="ghost" onClick={next}>Skip</Button><Button onClick={() => void saveBasics()} disabled={busy}>Save &amp; continue</Button></div>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">Saige uses these to find and rank jobs every day.</p>
            <Field label="Roles (comma separated)"><Input value={roles} onChange={(e) => setRoles(e.target.value)} placeholder="QA Engineer, SDET, Automation Tester" /></Field>
            <Field label="Cities (comma separated)"><Input value={places} onChange={(e) => setPlaces(e.target.value)} placeholder="Hyderabad, Bengaluru" /></Field>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={remote} onChange={(e) => setRemote(e.target.checked)} className="size-4 accent-[var(--primary)]" /> Open to remote jobs</label>
            <div className="flex justify-between"><Button variant="ghost" onClick={next}>Skip</Button><Button onClick={() => void savePrefs()} disabled={busy}>Save &amp; continue</Button></div>
          </div>
        )}

        {step === 3 && (
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">Optional, but this is where Saige saves you the most time.</p>
            <div className="grid gap-3 sm:grid-cols-2">
              <Link href="/integrations" className="rounded-2xl border p-4 hover:bg-muted/50">
                <Mail className="mb-2 size-6 text-primary" />
                <p className="font-medium">Connect Gmail</p>
                <p className="text-sm text-muted-foreground">Track recruiter replies and send applications from your own email.</p>
              </Link>
              <a href="/saige-extension.zip" className="rounded-2xl border p-4 hover:bg-muted/50">
                <Puzzle className="mb-2 size-6 text-primary" />
                <p className="font-medium">Get the Chrome extension</p>
                <p className="text-sm text-muted-foreground">Make an ATS resume on any LinkedIn, Naukri or company job page.</p>
              </a>
            </div>
            <div className="flex justify-end"><Button size="lg" onClick={() => void finish()}>Go to my dashboard</Button></div>
          </div>
        )}
      </section>
    </div>
  );
}
