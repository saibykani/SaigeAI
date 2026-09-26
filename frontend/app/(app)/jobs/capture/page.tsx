"use client";

import { Bookmark, Loader2, Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Notice, PageHeader } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input, Textarea } from "@/components/ui/form";
import { request } from "@/services/api";
import type { JobDetail } from "@/types/api";

type Captured = { type: "saige-job"; url: string; title: string; text: string };

function guessTitleCompany(pageTitle: string): { title: string; company: string } {
  // Common patterns: "Senior SDET - PayCo | LinkedIn", "Senior SDET at PayCo", "PayCo hiring Senior SDET"
  const clean = pageTitle.replace(/\s*[|·–-]\s*(LinkedIn|Naukri\.com|Naukri|Indeed(\.com)?|Glassdoor|Wellfound|Instahyre|Foundit).*$/i, "").trim();
  const at = clean.match(/^(.+?)\s+(?:at|@)\s+(.+)$/i);
  if (at) return { title: at[1].trim(), company: at[2].trim() };
  const dash = clean.split(/\s+[-–|]\s+/);
  if (dash.length >= 2) return { title: dash[0].trim(), company: dash[1].trim() };
  return { title: clean, company: "" };
}

export default function CapturePage() {
  const router = useRouter();
  const [form, setForm] = useState({ title: "", company: "", location: "", application_url: "", description: "" });
  const [received, setReceived] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    const onMessage = (e: MessageEvent) => {
      const d = e.data as Captured;
      if (!d || d.type !== "saige-job" || e.source !== window.opener) return;
      const { title, company } = guessTitleCompany(String(d.title || ""));
      setForm((f) => ({ ...f, title: title.slice(0, 200), company: company.slice(0, 200), application_url: String(d.url || "").slice(0, 1000), description: String(d.text || "").slice(0, 40000) }));
      setReceived(true);
    };
    window.addEventListener("message", onMessage);
    // Tell the bookmarklet on the job page that we're ready to receive the posting.
    window.opener?.postMessage("saige-ready", "*");
    return () => window.removeEventListener("message", onMessage);
  }, []);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      const r = await request<{ job: JobDetail }>("/jobs/import", {
        method: "POST",
        body: { ...form, location: form.location || null, application_url: /^https?:\/\//.test(form.application_url) ? form.application_url : null, source: "capture" },
      });
      router.replace(`/jobs/${r.job.id}`);
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : "Could not save the job");
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader title="Save job to Saige" description="Review what was captured from the page, fix the title or company if needed, then save to score it." />
      {!received && (
        <Notice>
          <span className="inline-flex items-center gap-2"><Loader2 className="size-4 animate-spin" /> Waiting for the posting… Open this page with the “Save to Saige” bookmark from a job page, or fill it in yourself.</span>
        </Notice>
      )}
      <Card className="mt-4">
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><Bookmark className="size-4" /> Captured posting</CardTitle>
          <CardDescription>Only the page you chose is sent — Saige never visits job sites on its own.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={save} className="flex flex-col gap-3">
            <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
              <Field label="Job title *"><Input required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></Field>
              <Field label="Company *"><Input required value={form.company} onChange={(e) => setForm({ ...form, company: e.target.value })} /></Field>
              <Field label="Location"><Input value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} /></Field>
              <Field label="Posting URL"><Input value={form.application_url} onChange={(e) => setForm({ ...form, application_url: e.target.value })} /></Field>
            </div>
            <Field label="Job description *" hint="Trim navigation or unrelated page text for the best match.">
              <Textarea required minLength={30} rows={14} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
            </Field>
            {err && <Notice tone="error">{err}</Notice>}
            <div><Button type="submit" disabled={busy}><Plus /> {busy ? "Scoring…" : "Save & score"}</Button></div>
          </form>
        </CardContent>
      </Card>
    </>
  );
}
