"use client";

import { FileText, Upload } from "lucide-react";
import Link from "next/link";
import { useRef, useState } from "react";

import { Notice, PageHeader } from "@/components/app-shell";
import { AtsScorer, ResumeHealth } from "@/components/ats-scorer";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input, Select } from "@/components/ui/form";
import { useApi } from "@/hooks/use-api";
import { request } from "@/services/api";
import { RESUME_KINDS, type Resume, type ResumeDetail } from "@/types/api";
import { formatBytes, formatDate } from "@/utils/format";

export default function ResumesPage() {
  const [showArchived, setShowArchived] = useState(false);
  const { data, error, loading, reload } = useApi<Resume[]>(`/resumes?include_archived=${showArchived}`);
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [kind, setKind] = useState(RESUME_KINDS[0]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ tone: "success" | "error"; text: React.ReactNode } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  async function onUpload(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setBusy(true);
    setMessage(null);
    const form = new FormData();
    form.append("file", file);
    form.append("name", name || file.name.replace(/\.[^.]+$/, ""));
    form.append("kind", kind);
    try {
      const r = await request<ResumeDetail>("/resumes", { method: "POST", form });
      const warnings = r.current_version?.parsed.warnings ?? [];
      setMessage({
        tone: "success",
        text: (
          <>
            Uploaded and parsed <Link className="font-medium underline" href={`/resumes/${r.id}`}>{r.name}</Link>.
            {warnings.length > 0 && ` ${warnings.length} item(s) need your review.`}
          </>
        ),
      });
      setFile(null);
      setName("");
      if (fileRef.current) fileRef.current.value = "";
      await reload();
    } catch (err) {
      setMessage({ tone: "error", text: err instanceof Error ? err.message : "Upload failed" });
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader title="Resumes" description="Upload, parse and version every resume variant, and score any of them against a job like an ATS would. Originals are kept untouched." />

      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Upload a resume</CardTitle>
          <CardDescription>PDF, DOCX or TXT up to 5 MB. Scanned image PDFs need OCR and won&apos;t parse.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onUpload} className="grid gap-4 md:grid-cols-[2fr_1.5fr_1.5fr_auto] md:items-end">
            <Field label="File" htmlFor="file">
              <Input
                ref={fileRef}
                id="file"
                type="file"
                required
                accept=".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain"
                className="py-1.5 file:mr-3 file:rounded file:border-0 file:bg-muted file:px-2 file:py-0.5 file:text-xs"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
            </Field>
            <Field label="Name" htmlFor="rname">
              <Input id="rname" placeholder="e.g. SDET – 2026" value={name} maxLength={120} onChange={(e) => setName(e.target.value)} />
            </Field>
            <Field label="Type" htmlFor="kind">
              <Select id="kind" value={kind} onChange={(e) => setKind(e.target.value)}>
                {RESUME_KINDS.map((k) => (
                  <option key={k}>{k}</option>
                ))}
              </Select>
            </Field>
            <Button type="submit" disabled={!file || busy}>
              <Upload /> {busy ? "Parsing…" : "Upload"}
            </Button>
          </form>
          {message && (
            <div className="mt-4">
              <Notice tone={message.tone}>{message.text}</Notice>
            </div>
          )}
        </CardContent>
      </Card>

      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-medium">Your resumes</h2>
        <label className="flex items-center gap-2 text-xs text-muted-foreground">
          <input type="checkbox" checked={showArchived} onChange={(e) => setShowArchived(e.target.checked)} />
          Show archived
        </label>
      </div>

      {error && <Notice tone="error">{error}</Notice>}
      {loading && !data && <p className="text-sm text-muted-foreground">Loading…</p>}
      {data && data.length === 0 && (
        <Card className="p-8 text-center text-sm text-muted-foreground">No resumes yet. Upload your master resume to get started.</Card>
      )}
      {data && data.length > 0 && (
        <div className="grid gap-3 md:grid-cols-2">
          {data.map((r) => (
            <Link key={r.id} href={`/resumes/${r.id}`}>
              <Card className="flex items-start gap-3 p-4 transition-colors hover:bg-muted/60">
                <FileText className="mt-0.5 size-5 text-muted-foreground" />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <p className="truncate font-medium">{r.name}</p>
                    {r.status === "archived" && <Badge variant="muted">Archived</Badge>}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {r.kind} · v{r.version_count} · {formatBytes(r.size)} · updated {formatDate(r.updated_at)}
                  </p>
                </div>
              </Card>
            </Link>
          ))}
        </div>
      )}
      {data && data.length > 0 && (
        <div className="mt-6">
          <ResumeHealth resumes={data.filter((r) => r.status === "active")} />
          <AtsScorer resumes={data.filter((r) => r.status === "active")} />
        </div>
      )}
    </>
  );
}
