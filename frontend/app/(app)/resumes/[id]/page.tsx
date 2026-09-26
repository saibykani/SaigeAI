"use client";

import { Archive, ArchiveRestore, ArrowLeft, Copy, Download, Save, Trash2, UserRoundCheck } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Notice, PageHeader } from "@/components/app-shell";
import { TagInput } from "@/components/tag-input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input, Select, Textarea } from "@/components/ui/form";
import { useApi } from "@/hooks/use-api";
import { downloadFile, request } from "@/services/api";
import { RESUME_KINDS, type ImportResult, type ParsedResume, type ResumeCompare, type ResumeDetail, type ResumeVersion } from "@/types/api";
import { display, formatDate } from "@/utils/format";

type Msg = { tone: "success" | "error" | "info"; text: React.ReactNode } | null;

export default function ResumeDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { data, error, setData } = useApi<ResumeDetail>(`/resumes/${id}`);
  const versions = useApi<ResumeVersion[]>(`/resumes/${id}/versions`);
  const [draft, setDraft] = useState<ParsedResume | null>(null);
  const [meta, setMeta] = useState({ name: "", kind: "" });
  const [note, setNote] = useState("");
  const [msg, setMsg] = useState<Msg>(null);
  const [busy, setBusy] = useState(false);
  const [cmp, setCmp] = useState<{ a: string; b: string }>({ a: "", b: "" });
  const [comparison, setComparison] = useState<ResumeCompare | null>(null);

  useEffect(() => {
    if (data) {
      setDraft(data.current_version?.parsed ?? null);
      setMeta({ name: data.name, kind: data.kind });
    }
  }, [data]);

  if (error) return <Notice tone="error">{error}</Notice>;
  if (!data) return <p className="text-sm text-muted-foreground">Loading…</p>;
  const parsed = data.current_version?.parsed;

  async function run<T>(fn: () => Promise<T>, ok?: (r: T) => Msg) {
    setBusy(true);
    setMsg(null);
    try {
      const r = await fn();
      if (ok) setMsg(ok(r));
      return r;
    } catch (e) {
      setMsg({ tone: "error", text: e instanceof Error ? e.message : "Action failed" });
    } finally {
      setBusy(false);
    }
  }

  const save = () =>
    run(
      async () => {
        const r = await request<ResumeDetail>(`/resumes/${id}`, {
          method: "PUT",
          body: { ...meta, parsed: draft, change_note: note || undefined },
        });
        setData(r);
        setNote("");
        await versions.reload();
        return r;
      },
      (r) => ({ tone: "success", text: `Saved as version ${r.version_count}.` }),
    );

  const importToProfile = () =>
    run(
      () => request<ImportResult>(`/resumes/${id}/import-to-profile`, { method: "POST" }),
      (r) => ({
        tone: "success",
        text: (
          <div className="flex flex-col gap-1">
            <span>
              Imported {r.applied.length} item(s) into your <Link href="/profile" className="underline">master profile</Link> (now {r.completeness}% complete).
            </span>
            {r.skipped.length > 0 && (
              <span className="text-xs">Kept your existing verified values for: {r.skipped.join("; ")}</span>
            )}
          </div>
        ),
      }),
    );

  const toggleArchive = () =>
    run(async () => {
      const r = await request<ResumeDetail>(`/resumes/${id}/${data.status === "archived" ? "unarchive" : "archive"}`, { method: "POST" });
      setData(r);
    });

  const duplicate = () =>
    run(async () => {
      const r = await request<ResumeDetail>(`/resumes/${id}/duplicate`, { method: "POST" });
      router.push(`/resumes/${r.id}`);
    });

  const remove = () => {
    if (!confirm(`Delete "${data.name}" and all its versions? This cannot be undone.`)) return;
    void run(async () => {
      await request(`/resumes/${id}`, { method: "DELETE" });
      router.replace("/resumes");
    });
  };

  const compare = () =>
    run(async () => {
      setComparison(await request<ResumeCompare>(`/resumes/${id}/compare`, { query: cmp }));
    });

  return (
    <>
      <Link href="/resumes" className="mb-3 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-4" /> All resumes
      </Link>
      <PageHeader
        title={data.name}
        description={`${data.kind} · version ${data.version_count}${data.filename ? ` · ${data.filename}` : ""}${data.job_id ? " · tailored for a job" : ""}`}
        actions={
          <>
            {data.filename && (
              <Button variant="outline" size="sm" disabled={busy} onClick={() => downloadFile(`/resumes/${id}/download`, data.filename ?? "resume")}>
                <Download /> Original
              </Button>
            )}
            <Button variant="outline" size="sm" disabled={busy} onClick={() => downloadFile(`/resumes/${id}/export.docx`, "resume.docx")}>
              <Download /> Word (ATS)
            </Button>
            <Button variant="outline" size="sm" disabled={busy} onClick={duplicate}>
              <Copy /> Duplicate
            </Button>
            <Button variant="outline" size="sm" disabled={busy} onClick={toggleArchive}>
              {data.status === "archived" ? <ArchiveRestore /> : <Archive />}
              {data.status === "archived" ? "Unarchive" : "Archive"}
            </Button>
            <Button variant="outline" size="sm" disabled={busy} onClick={remove}>
              <Trash2 /> Delete
            </Button>
            <Button size="sm" disabled={busy || !parsed} onClick={importToProfile}>
              <UserRoundCheck /> Import to profile
            </Button>
          </>
        }
      />

      {msg && (
        <div className="mb-4">
          <Notice tone={msg.tone}>{msg.text}</Notice>
        </div>
      )}
      {parsed && parsed.warnings.length > 0 && (
        <div className="mb-4">
          <Notice tone="warning">
            <p className="font-medium">Review needed</p>
            <ul className="mt-1 list-disc pl-5 text-xs">
              {parsed.warnings.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
          </Notice>
        </div>
      )}

      {!draft ? (
        <Notice>This resume has no parsed content.</Notice>
      ) : (
        <div className="grid gap-6 lg:grid-cols-3">
          <div className="flex flex-col gap-6 lg:col-span-2">
            <Card>
              <CardHeader>
                <CardTitle>Parsed content</CardTitle>
                <CardDescription>Correct anything the parser got wrong, then save as a new version.</CardDescription>
              </CardHeader>
              <CardContent className="grid gap-4 sm:grid-cols-2">
                <Field label="Resume name"><Input value={meta.name} onChange={(e) => setMeta({ ...meta, name: e.target.value })} /></Field>
                <Field label="Type">
                  <Select value={meta.kind} onChange={(e) => setMeta({ ...meta, kind: e.target.value })}>
                    {Array.from(new Set([meta.kind, ...RESUME_KINDS])).map((k) => (
                      <option key={k}>{k}</option>
                    ))}
                  </Select>
                </Field>
                <Field label="Candidate name"><Input placeholder="UNKNOWN" value={draft.name ?? ""} onChange={(e) => setDraft({ ...draft, name: e.target.value || null })} /></Field>
                <Field label="Email"><Input placeholder="UNKNOWN" value={draft.email ?? ""} onChange={(e) => setDraft({ ...draft, email: e.target.value || null })} /></Field>
                <Field label="Phone"><Input placeholder="UNKNOWN" value={draft.phone ?? ""} onChange={(e) => setDraft({ ...draft, phone: e.target.value || null })} /></Field>
                <Field label="LinkedIn"><Input placeholder="UNKNOWN" value={draft.links.linkedin ?? ""} onChange={(e) => setDraft({ ...draft, links: { ...draft.links, linkedin: e.target.value || null } })} /></Field>
                <Field label="Summary" className="sm:col-span-2">
                  <Textarea rows={4} placeholder="UNKNOWN" value={draft.summary ?? ""} onChange={(e) => setDraft({ ...draft, summary: e.target.value || null })} />
                </Field>
                <Field label="Skills" className="sm:col-span-2">
                  <TagInput value={draft.skills} onChange={(skills) => setDraft({ ...draft, skills })} />
                </Field>
                <Field label="Certifications" className="sm:col-span-2">
                  <TagInput value={draft.certifications} onChange={(certifications) => setDraft({ ...draft, certifications })} />
                </Field>
                <Field label="Change note (optional)" className="sm:col-span-2">
                  <Input maxLength={300} placeholder="e.g. Fixed parsed job titles" value={note} onChange={(e) => setNote(e.target.value)} />
                </Field>
                <div className="sm:col-span-2">
                  <Button disabled={busy} onClick={save}>
                    <Save /> Save new version
                  </Button>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Experience ({draft.experience.length})</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-4">
                {draft.experience.length === 0 && <p className="text-sm text-muted-foreground">No dated roles were recognised.</p>}
                {draft.experience.map((e, i) => (
                  <div key={i} className="rounded-lg border p-3">
                    <div className="flex flex-wrap items-baseline justify-between gap-2">
                      <p className="font-medium">
                        {display(e.title)} <span className="text-muted-foreground">@ {display(e.company)}</span>
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {display(e.start_date)} – {e.is_current ? "Present" : display(e.end_date)}
                        {e.location && ` · ${e.location}`}
                      </p>
                    </div>
                    {[...e.achievements, ...e.responsibilities].length > 0 && (
                      <ul className="mt-2 list-disc pl-5 text-sm text-muted-foreground">
                        {e.achievements.map((a) => (
                          <li key={a} className="text-foreground">{a}</li>
                        ))}
                        {e.responsibilities.map((r) => (
                          <li key={r}>{r}</li>
                        ))}
                      </ul>
                    )}
                    {e.technologies.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {e.technologies.map((t) => (
                          <Badge key={t} variant="muted">{t}</Badge>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </CardContent>
            </Card>

            <div className="grid gap-6 md:grid-cols-2">
              <Card>
                <CardHeader><CardTitle>Education</CardTitle></CardHeader>
                <CardContent className="text-sm">
                  {draft.education.length === 0 ? <p className="text-muted-foreground">None found</p> : (
                    <ul className="flex flex-col gap-2">
                      {draft.education.map((ed, i) => (
                        <li key={i}>
                          <span className="font-medium">{display(ed.degree)}</span>
                          {ed.field && ` in ${ed.field}`}
                          <p className="text-xs text-muted-foreground">
                            {display(ed.institution)} {ed.end_year && `· ${ed.start_year ? `${ed.start_year}–` : ""}${ed.end_year}`}
                          </p>
                        </li>
                      ))}
                    </ul>
                  )}
                </CardContent>
              </Card>
              <Card>
                <CardHeader><CardTitle>Projects</CardTitle></CardHeader>
                <CardContent className="text-sm">
                  {draft.projects.length === 0 ? <p className="text-muted-foreground">None found</p> : (
                    <ul className="flex flex-col gap-2">
                      {draft.projects.map((p) => (
                        <li key={p.name}>
                          <span className="font-medium">{p.name}</span>
                          {p.technologies.length > 0 && <p className="text-xs text-muted-foreground">{p.technologies.join(", ")}</p>}
                        </li>
                      ))}
                    </ul>
                  )}
                </CardContent>
              </Card>
            </div>
          </div>

          <div className="flex flex-col gap-6">
            <Card>
              <CardHeader>
                <CardTitle>Version history</CardTitle>
              </CardHeader>
              <CardContent>
                <ol className="flex flex-col gap-3">
                  {(versions.data ?? []).map((v) => (
                    <li key={v.id} className="text-sm">
                      <div className="flex items-center gap-2">
                        <Badge variant={v.id === data.current_version_id ? "default" : "muted"}>v{v.version}</Badge>
                        <span className="text-xs capitalize text-muted-foreground">{v.source} · {formatDate(v.created_at)}</span>
                      </div>
                      <ul className="mt-1 pl-1 text-xs text-muted-foreground">
                        {v.changes.map((c) => (
                          <li key={c}>• {c}</li>
                        ))}
                      </ul>
                    </li>
                  ))}
                </ol>
              </CardContent>
            </Card>

            {(versions.data?.length ?? 0) > 1 && (
              <Card>
                <CardHeader>
                  <CardTitle>Compare versions</CardTitle>
                </CardHeader>
                <CardContent className="flex flex-col gap-3">
                  <div className="grid grid-cols-2 gap-2">
                    {(["a", "b"] as const).map((side) => (
                      <Select key={side} aria-label={`Version ${side.toUpperCase()}`} value={cmp[side]} onChange={(e) => setCmp({ ...cmp, [side]: e.target.value })}>
                        <option value="">{side === "a" ? "From…" : "To…"}</option>
                        {versions.data!.map((v) => (
                          <option key={v.id} value={v.id}>v{v.version}</option>
                        ))}
                      </Select>
                    ))}
                  </div>
                  <Button variant="outline" size="sm" disabled={!cmp.a || !cmp.b || busy} onClick={compare}>Compare</Button>
                  {comparison && (
                    <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
                      <dt className="text-muted-foreground">Skills added</dt><dd>{display(comparison.skills_added)}</dd>
                      <dt className="text-muted-foreground">Skills removed</dt><dd>{display(comparison.skills_removed)}</dd>
                      <dt className="text-muted-foreground">Summary</dt><dd>{comparison.summary_changed ? "Changed" : "Unchanged"}</dd>
                      <dt className="text-muted-foreground">Roles</dt><dd>{comparison.experience_count.join(" → ")}</dd>
                      <dt className="text-muted-foreground">Certs added</dt><dd>{display(comparison.certifications_added)}</dd>
                    </dl>
                  )}
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      )}
    </>
  );
}
