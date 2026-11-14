"use client";

import { Copy, FileText, Pencil, Plus, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { Notice } from "@/components/app-shell";
import { useT } from "@/components/i18n";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input, Select, Textarea } from "@/components/ui/form";
import { request } from "@/services/api";
import type { EmailTemplate } from "@/types/api";

const PLACEHOLDERS = ["hr_name", "company", "my_name", "my_role", "years", "top_skills", "phone", "linkedin", "portfolio"];
type Draft = { id: string | null; name: string; subject: string; body: string; kind: EmailTemplate["kind"]; attach_resume: boolean };
const BLANK: Draft = { id: null, name: "", subject: "", body: "", kind: "cold", attach_resume: false };

/** Built-in and own email templates for bulk emails to HR contacts. Built-ins are copied, not edited. */
export function EmailTemplatesManager() {
  const { t } = useT();
  const [list, setList] = useState<EmailTemplate[] | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const load = useCallback(() => { request<EmailTemplate[]>("/recruiters/email-templates").then(setList).catch((e) => setErr(e instanceof Error ? e.message : "Error")); }, []);
  useEffect(load, [load]);

  async function save() {
    if (!draft) return;
    setErr(null);
    const body = { name: draft.name, subject: draft.subject, body: draft.body, kind: draft.kind, attach_resume: draft.attach_resume };
    try {
      await request(draft.id ? `/recruiters/email-templates/${draft.id}` : "/recruiters/email-templates", { method: draft.id ? "PUT" : "POST", body });
      setDraft(null);
      load();
    } catch (e) { setErr(e instanceof Error ? e.message : "Could not save"); }
  }

  return (
    <div className="flex flex-col gap-4">
      <Notice>{t("Placeholders are filled only from your verified profile. A line whose value is missing is removed, never invented. The hr_name placeholder becomes “Hiring Team” for generic contacts.")}</Notice>
      {err && <Notice tone="error">{err}</Notice>}
      <div><Button onClick={() => setDraft(BLANK)}><Plus /> {t("New template")}</Button></div>
      {draft && (
        <Card className="animate-rise">
          <CardHeader><CardTitle className="text-base">{draft.id ? t("Edit template") : t("New template")}</CardTitle>
            <CardDescription className="flex flex-wrap gap-1">{PLACEHOLDERS.map((p) => <code key={p} className="rounded bg-muted px-1.5 text-[11px]">{`{{${p}}}`}</code>)}</CardDescription></CardHeader>
          <CardContent className="grid gap-3">
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label={t("Name")}><Input value={draft.name} maxLength={80} onChange={(e) => setDraft({ ...draft, name: e.target.value })} /></Field>
              <Field label={t("Type")}>
                <Select value={draft.kind} onChange={(e) => setDraft({ ...draft, kind: e.target.value as Draft["kind"] })}>
                  <option value="cold">{t("Cold / application")}</option><option value="referral">{t("Referral request")}</option>
                  <option value="hiring_manager">{t("Hiring manager")}</option><option value="followup">{t("Follow-up")}</option><option value="thank_you">{t("Thank you")}</option>
                </Select>
              </Field>
            </div>
            <Field label={t("Subject")}><Input value={draft.subject} maxLength={200} onChange={(e) => setDraft({ ...draft, subject: e.target.value })} /></Field>
            <Field label={t("Message")}><Textarea rows={10} value={draft.body} maxLength={5000} onChange={(e) => setDraft({ ...draft, body: e.target.value })} /></Field>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={draft.attach_resume} onChange={(e) => setDraft({ ...draft, attach_resume: e.target.checked })} /> {t("Attach my resume")}</label>
            <div className="flex gap-2">
              <Button disabled={!draft.name.trim() || !draft.subject.trim() || !draft.body.trim()} onClick={save}>{t("Save template")}</Button>
              <Button variant="ghost" onClick={() => setDraft(null)}>{t("Cancel")}</Button>
            </div>
          </CardContent>
        </Card>
      )}
      {!list ? <div className="skeleton h-48 rounded-3xl" /> : (
        <div className="grid gap-4 lg:grid-cols-2">
          {list.map((x) => (
            <Card key={x.id}>
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-base"><FileText className="size-4 text-muted-foreground" /> {x.name}
                  {x.builtin && <Badge variant="outline">{t("Built-in")}</Badge>}{x.attach_resume && <Badge variant="outline">{t("Resume attached")}</Badge>}</CardTitle>
                <CardDescription>{x.subject}</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                <p className="max-h-40 overflow-auto whitespace-pre-wrap rounded-xl border bg-muted/40 p-3 text-xs leading-relaxed">{x.body}</p>
                <div className="flex gap-2">
                  <Button size="sm" variant="outline" onClick={() => setDraft({ id: null, name: x.builtin ? `${x.name} (copy)` : `${x.name} 2`, subject: x.subject, body: x.body, kind: x.kind, attach_resume: x.attach_resume })}><Copy /> {t("Duplicate")}</Button>
                  {!x.builtin && <Button size="sm" variant="outline" onClick={() => setDraft({ id: x.id, name: x.name, subject: x.subject, body: x.body, kind: x.kind, attach_resume: x.attach_resume })}><Pencil /> {t("Edit")}</Button>}
                  {!x.builtin && <Button size="sm" variant="ghost" onClick={() => { if (confirm(t("Delete this template?"))) void request(`/recruiters/email-templates/${x.id}`, { method: "DELETE" }).then(load); }}><Trash2 /> {t("Delete")}</Button>}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
