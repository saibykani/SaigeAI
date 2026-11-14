"use client";

import { Building2, FileStack, Trophy } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/form";
import { useApi } from "@/hooks/use-api";

type App = { application_id: string; role: string; status: string; sent: boolean; replied: boolean; applied_at: string | null };
type Version = { resume_id: string; name: string; kind: string | null; applications: App[]; sent: number; replied: number; reply_rate: number | null };
type Company = { company: string; versions: Version[]; sent: number; replied: number };
type Row = { resume_id: string; name: string; kind: string | null; sent: number; replied: number; interviews: number; reply_rate: number | null };
type Out = { companies: Company[]; resumes: Row[]; best: Row | null };

const pretty = (s: string) => s.replace(/_/g, " ").toLowerCase().replace(/^\w/, (c) => c.toUpperCase());

/** Which resume version went to which company, and which versions got replies. */
export function ResumeVersions() {
  const { data } = useApi<Out>("/resume-versions");
  const [q, setQ] = useState("");
  if (!data) return <div className="skeleton mb-6 h-40 rounded-3xl" />;
  const companies = data.companies.filter((c) => !q.trim() || c.company.toLowerCase().includes(q.trim().toLowerCase()));

  return (
    <Card className="mb-6">
      <CardHeader className="gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <CardTitle className="flex items-center gap-2 text-lg"><FileStack className="size-5 text-primary" /> Resume versions by company</CardTitle>
          <CardDescription>Which resume you sent to which company, and which versions got replies.</CardDescription>
        </div>
        {data.companies.length > 4 && <Input className="w-56" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search company" />}
      </CardHeader>
      <CardContent className="space-y-5">
        {data.resumes.length > 0 && (
          <div>
            {data.best && (
              <p className="mb-2 flex items-center gap-2 text-sm"><Trophy className="size-4" style={{ color: "var(--tone-yellow)" }} />
                Best so far: <b>{data.best.name}</b> · {data.best.reply_rate}% replies from {data.best.sent} sent</p>
            )}
            <div className="overflow-x-auto rounded-2xl border">
              <table className="w-full text-sm">
                <thead className="text-left text-xs text-muted-foreground"><tr><th className="p-3">Resume</th><th className="p-3">Sent</th><th className="p-3">Replies</th><th className="p-3">Interviews</th><th className="p-3">Reply rate</th></tr></thead>
                <tbody className="divide-y">
                  {data.resumes.map((r) => (
                    <tr key={r.resume_id}>
                      <td className="p-3 font-medium">{r.name}{r.kind && <span className="ml-2 text-xs text-muted-foreground">{r.kind}</span>}</td>
                      <td className="p-3">{r.sent}</td><td className="p-3">{r.replied}</td><td className="p-3">{r.interviews}</td>
                      <td className="p-3">{r.reply_rate == null ? "–" : `${r.reply_rate}%`}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {!data.best && <p className="mt-2 text-xs text-muted-foreground">A “best version” appears once a resume has been sent at least 3 times.</p>}
          </div>
        )}
        {companies.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">No resumes sent yet. When you apply with a resume, it shows up here under that company.</p>
        ) : (
          <ul className="space-y-3">
            {companies.map((c) => (
              <li key={c.company} className="rounded-2xl border p-4">
                <p className="flex flex-wrap items-center gap-2 font-medium"><Building2 className="size-4 text-muted-foreground" /> {c.company}
                  <span className="text-xs font-normal text-muted-foreground">{c.sent} sent · {c.replied} replied</span></p>
                <ul className="mt-2 space-y-2">
                  {c.versions.map((v) => (
                    <li key={v.resume_id} className="rounded-xl bg-muted/40 p-3 text-sm">
                      <p className="font-medium">{v.name}{v.kind && <span className="ml-2 text-xs font-normal text-muted-foreground">{v.kind}</span>}</p>
                      {v.applications.length === 0 ? <p className="text-xs text-muted-foreground">Made for this company, not sent yet</p> : (
                        <div className="mt-1 flex flex-wrap gap-1.5">
                          {v.applications.map((a) => (
                            <Badge key={a.application_id} variant={a.replied ? "success" : a.sent ? "outline" : "muted"}>
                              {a.role || "Role"} · {a.replied ? "replied" : a.sent ? pretty(a.status) : "not sent"}
                            </Badge>
                          ))}
                        </div>
                      )}
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
