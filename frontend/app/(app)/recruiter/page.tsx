"use client";

import { Briefcase, Send, Trash2, UserCheck } from "lucide-react";
import { useState } from "react";

import { Notice, PageHeader } from "@/components/app-shell";
import { CountKpi } from "@/components/kpi";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input, Select, Textarea } from "@/components/ui/form";
import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { request } from "@/services/api";
import type { RecruiterJob, SentTalentRequest, TalentCandidate } from "@/types/api";

const EMPTY = { title: "", company: "", location: "", description: "", skills: "" };

export default function RecruiterPage() {
  const { user } = useAuth();
  const allowed = user?.role === "recruiter" || user?.role === "admin";
  const jobs = useApi<RecruiterJob[]>(allowed ? "/hiring/jobs" : null);
  const sent = useApi<SentTalentRequest[]>(allowed ? "/hiring/requests" : null);
  const [form, setForm] = useState(EMPTY);
  const [jobId, setJobId] = useState("");
  const [q, setQ] = useState("");
  const [msg, setMsg] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const candidates = useApi<TalentCandidate[]>(allowed ? `/hiring/candidates?${jobId ? `job_id=${jobId}&` : ""}q=${encodeURIComponent(q)}` : null);

  if (!allowed) return (<><PageHeader title="Hiring" /><Notice tone="warning">This page is for recruiter accounts.</Notice></>);

  async function run(fn: () => Promise<unknown>, ok: string) {
    setMsg(null);
    try {
      await fn();
      setMsg({ tone: "success", text: ok });
    } catch (e) {
      setMsg({ tone: "error", text: e instanceof Error ? e.message : "Something went wrong" });
    }
  }

  const postJob = (e: React.FormEvent) => {
    e.preventDefault();
    void run(async () => {
      const job = await request<RecruiterJob>("/hiring/jobs", { method: "POST", body: { ...form, skills: form.skills.split(",").map((s) => s.trim()).filter(Boolean) } });
      setForm(EMPTY);
      setJobId(job.id);
      await jobs.reload();
    }, "Job posted. Matching candidates are ranked below.");
  };

  const accepted = (sent.data ?? []).filter((r) => r.status === "accepted").length;
  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Hiring" description="Post roles and find candidates who chose to be discoverable. You see their verified profile facts; contact details appear only after they accept your request." />
      {msg && <Notice tone={msg.tone}>{msg.text}</Notice>}
      <div className="grid gap-4 sm:grid-cols-3">
        <CountKpi label="Open jobs" value={jobs.data?.length ?? 0} icon={Briefcase} tone="teal" />
        <CountKpi label="Requests sent" value={sent.data?.length ?? 0} icon={Send} tone="orange" delay={40} />
        <CountKpi label="Accepted" value={accepted} icon={UserCheck} tone="green" delay={80} />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="animate-rise">
          <CardHeader><CardTitle className="text-base">Post a job</CardTitle><CardDescription>Skills drive the candidate ranking. Leave blank to detect them from the description.</CardDescription></CardHeader>
          <CardContent>
            <form onSubmit={postJob} className="flex flex-col gap-3">
              <div className="grid grid-cols-2 gap-3">
                <Field label="Title" htmlFor="jt"><Input id="jt" required minLength={2} value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></Field>
                <Field label="Company" htmlFor="jc"><Input id="jc" required value={form.company} onChange={(e) => setForm({ ...form, company: e.target.value })} /></Field>
              </div>
              <Field label="Location" htmlFor="jl"><Input id="jl" value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} /></Field>
              <Field label="Skills" htmlFor="js" hint="Comma-separated"><Input id="js" value={form.skills} onChange={(e) => setForm({ ...form, skills: e.target.value })} /></Field>
              <Field label="Description" htmlFor="jd"><Textarea id="jd" rows={4} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></Field>
              <Button type="submit" className="self-start">Post job</Button>
            </form>
          </CardContent>
        </Card>

        <Card className="animate-rise">
          <CardHeader><CardTitle className="text-base">Your jobs</CardTitle></CardHeader>
          <CardContent className="flex flex-col gap-2">
            {(jobs.data ?? []).length === 0 && <p className="text-sm text-muted-foreground">No jobs yet.</p>}
            {(jobs.data ?? []).map((j) => (
              <div key={j.id} className="flex items-start justify-between gap-3 rounded-xl border px-3 py-2.5 text-sm">
                <button type="button" className="min-w-0 text-left" onClick={() => setJobId(j.id)}>
                  <span className="block font-medium">{j.title} · {j.company}</span>
                  <span className="block truncate text-xs text-muted-foreground">{j.location || "Location not set"} · {j.skills.join(", ") || "no skills"}</span>
                </button>
                <Button size="icon" variant="ghost" className="size-8" aria-label={`Delete ${j.title}`}
                  onClick={() => void run(async () => { await request(`/hiring/jobs/${j.id}`, { method: "DELETE" }); if (jobId === j.id) setJobId(""); await jobs.reload(); }, "Job deleted.")}>
                  <Trash2 className="size-4" />
                </Button>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      <Card className="animate-rise">
        <CardHeader className="gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div><CardTitle className="text-base">Candidates</CardTitle><CardDescription>Only people who turned on “Let recruiters find me”, ranked by skill match.</CardDescription></div>
          <div className="flex gap-2">
            <Select value={jobId} onChange={(e) => setJobId(e.target.value)} aria-label="Rank for job" className="w-48">
              <option value="">Any job</option>
              {(jobs.data ?? []).map((j) => <option key={j.id} value={j.id}>{j.title}</option>)}
            </Select>
            <Input placeholder="Skills, e.g. Selenium, Java" value={q} onChange={(e) => setQ(e.target.value)} className="w-56" aria-label="Search skills" />
          </div>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-2">
          {(candidates.data ?? []).length === 0 && <p className="text-sm text-muted-foreground">No discoverable candidates match yet.</p>}
          {(candidates.data ?? []).map((cand) => {
            const done = (sent.data ?? []).some((r) => r.candidate_id === cand.id);
            return (
              <div key={cand.id} className="rounded-2xl border p-4 text-sm">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-medium">{cand.name}</p>
                    <p className="text-xs text-muted-foreground">{[cand.role, cand.years != null ? `${cand.years} yrs` : null, cand.location].filter(Boolean).join(" · ") || "Details not shared"}</p>
                  </div>
                  {cand.match != null && <Badge variant={cand.match >= 70 ? "success" : "muted"}>{cand.match}% match</Badge>}
                </div>
                <p className="mt-2 text-xs text-muted-foreground">{cand.skills.slice(0, 12).join(", ")}</p>
                {cand.missing_skills.length > 0 && <p className="mt-1 text-xs text-muted-foreground">Missing: {cand.missing_skills.join(", ")}</p>}
                <div className="mt-3 flex gap-2">
                  {cand.portfolio_url && <a href={cand.portfolio_url} target="_blank" rel="noreferrer" className="text-xs text-primary underline-offset-4 hover:underline">Portfolio</a>}
                  <Button size="sm" className="ml-auto" disabled={done}
                    onClick={() => void run(async () => { await request("/hiring/requests", { method: "POST", body: { candidate_id: cand.id, job_id: jobId || null } }); await sent.reload(); }, `Interest sent to ${cand.name}.`)}>
                    {done ? "Request sent" : "Send interest"}
                  </Button>
                </div>
              </div>
            );
          })}
        </CardContent>
      </Card>

      <Card className="animate-rise">
        <CardHeader><CardTitle className="text-base">Interest requests</CardTitle></CardHeader>
        <CardContent>
          <ul className="divide-y text-sm">
            {(sent.data ?? []).map((r) => (
              <li key={r.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                <span><span className="font-medium">{r.candidate_name}</span> <span className="text-muted-foreground">{r.job_title ?? "General interest"}</span></span>
                <span className="flex items-center gap-2">
                  {r.contact && <span className="text-xs">{[r.contact.email, r.contact.phone].filter(Boolean).join(" · ")}</span>}
                  <Badge variant={r.status === "accepted" ? "success" : r.status === "declined" ? "destructive" : "muted"}>{r.status}</Badge>
                </span>
              </li>
            ))}
          </ul>
          {(sent.data ?? []).length === 0 && <p className="text-sm text-muted-foreground">No requests yet.</p>}
        </CardContent>
      </Card>
    </div>
  );
}
