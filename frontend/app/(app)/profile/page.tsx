"use client";

import { Plus, Save, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

import { Notice, PageHeader } from "@/components/app-shell";
import { TagInput } from "@/components/tag-input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input, Select, Textarea } from "@/components/ui/form";
import { useApi } from "@/hooks/use-api";
import { request } from "@/services/api";
import {
  SKILL_CATEGORIES,
  type Certification,
  type Education,
  type Experience,
  type PersonalInfo,
  type Preferences,
  type Profile,
  type Project,
} from "@/types/api";
import { cn } from "@/utils/cn";
import { UNKNOWN, linesToList, numberOrNull } from "@/utils/format";

const TABS = ["Personal", "Skills", "Preferences", "Experience", "Projects", "Education", "Certifications"] as const;
type Tab = (typeof TABS)[number];

type Editable = Pick<Profile, "personal" | "skills" | "preferences" | "knowledge">;

const PERSONAL_TEXT: [keyof PersonalInfo, string][] = [
  ["name", "Name"],
  ["email", "Email"],
  ["phone", "Phone"],
  ["current_location", "Current Location"],
  ["country", "Country"],
  ["current_company", "Current Company"],
  ["current_designation", "Current Designation"],
  ["availability", "Availability"],
  ["ctc_currency", "CTC Currency"],
];
const PERSONAL_NUMBER: [keyof PersonalInfo, string][] = [
  ["total_experience_years", "Total Experience (years)"],
  ["current_ctc", "Current CTC"],
  ["expected_ctc", "Expected CTC"],
  ["notice_period_days", "Notice Period (days)"],
];
const PERSONAL_URL: [keyof PersonalInfo, string][] = [
  ["linkedin_url", "LinkedIn URL"],
  ["naukri_url", "Naukri URL"],
  ["github_url", "GitHub URL"],
  ["portfolio_url", "Portfolio URL"],
];
const PREF_LISTS: [keyof Preferences, string][] = [
  ["target_roles", "Target Roles"],
  ["target_industries", "Target Industries"],
  ["target_companies", "Target Companies"],
  ["excluded_companies", "Excluded Companies"],
  ["preferred_locations", "Preferred Locations"],
  ["excluded_locations", "Excluded Locations"],
  ["employment_types", "Employment Types"],
];

function TriState({ value, onChange, id }: { value: boolean | null; onChange: (v: boolean | null) => void; id: string }) {
  return (
    <Select id={id} value={value === null ? "" : String(value)} onChange={(e) => onChange(e.target.value === "" ? null : e.target.value === "true")}>
      <option value="">{UNKNOWN}</option>
      <option value="true">Yes</option>
      <option value="false">No</option>
    </Select>
  );
}

function ListEditor<T>({
  items,
  onChange,
  blank,
  addLabel,
  render,
  title,
}: {
  items: T[];
  onChange: (items: T[]) => void;
  blank: () => T;
  addLabel: string;
  title: (item: T) => string;
  render: (item: T, update: (patch: Partial<T>) => void) => React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-4">
      {items.length === 0 && <p className="text-sm text-muted-foreground">Nothing added yet.</p>}
      {items.map((item, i) => (
        // Length in the key remounts entries on add/remove so uncontrolled textareas never show stale text.
        <Card key={`${items.length}-${i}`}>
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle>{title(item) || "New entry"}</CardTitle>
            <Button variant="ghost" size="icon" aria-label="Remove" onClick={() => onChange(items.filter((_, j) => j !== i))}>
              <Trash2 />
            </Button>
          </CardHeader>
          <CardContent>{render(item, (patch) => onChange(items.map((it, j) => (j === i ? { ...it, ...patch } : it))))}</CardContent>
        </Card>
      ))}
      <div>
        <Button variant="outline" onClick={() => onChange([...items, blank()])}>
          <Plus /> {addLabel}
        </Button>
      </div>
    </div>
  );
}

const text = (v: string | null | undefined) => v ?? "";
const orNull = (v: string) => (v.trim() === "" ? null : v);

export default function ProfilePage() {
  const { data, error, loading, setData } = useApi<Profile>("/profile");
  const [form, setForm] = useState<Editable | null>(null);
  const [tab, setTab] = useState<Tab>("Personal");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ tone: "success" | "error"; text: string } | null>(null);

  useEffect(() => {
    if (data) setForm({ personal: data.personal, skills: data.skills, preferences: data.preferences, knowledge: data.knowledge });
  }, [data]);

  if (error) return <Notice tone="error">{error}</Notice>;
  if (loading || !form || !data) return <p className="text-sm text-muted-foreground">Loading profile…</p>;

  const setPersonal = (patch: Partial<PersonalInfo>) => setForm({ ...form, personal: { ...form.personal, ...patch } });
  const setPrefs = (patch: Partial<Preferences>) => setForm({ ...form, preferences: { ...form.preferences, ...patch } });
  const setKb = (patch: Partial<Editable["knowledge"]>) => setForm({ ...form, knowledge: { ...form.knowledge, ...patch } });

  async function save() {
    setSaving(true);
    setMessage(null);
    try {
      const updated = await request<Profile>("/profile", { method: "PUT", body: form });
      setData(updated);
      setMessage({ tone: "success", text: "Profile saved. Changes are recorded in your audit log." });
    } catch (e) {
      setMessage({ tone: "error", text: e instanceof Error ? e.message : "Save failed" });
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Master Profile"
        description="Your verified source of truth. Saige will never generate anything that isn't backed by this profile."
        actions={
          <Button onClick={save} disabled={saving}>
            <Save /> {saving ? "Saving…" : "Save profile"}
          </Button>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Badge variant={data.completeness >= 80 ? "success" : "warning"}>{data.completeness}% complete</Badge>
        {data.unknown_fields.length > 0 && (
          <span className="text-xs text-muted-foreground">UNKNOWN: {data.unknown_fields.join(", ")}</span>
        )}
      </div>
      {message && (
        <div className="mb-4">
          <Notice tone={message.tone}>{message.text}</Notice>
        </div>
      )}

      <div role="tablist" className="mb-5 flex gap-1 overflow-x-auto border-b">
        {TABS.map((t) => (
          <button
            key={t}
            role="tab"
            aria-selected={tab === t}
            onClick={() => setTab(t)}
            className={cn(
              "-mb-px cursor-pointer whitespace-nowrap border-b-2 px-3 py-2 text-sm transition-colors",
              tab === t ? "border-primary font-medium text-foreground" : "border-transparent text-muted-foreground hover:text-foreground",
            )}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "Personal" && (
        <Card>
          <CardContent className="grid gap-4 pt-5 sm:grid-cols-2 lg:grid-cols-3">
            {PERSONAL_TEXT.map(([k, label]) => (
              <Field key={k} label={label} htmlFor={k}>
                <Input id={k} placeholder={UNKNOWN} value={text(form.personal[k] as string | null)} onChange={(e) => setPersonal({ [k]: orNull(e.target.value) })} />
              </Field>
            ))}
            {PERSONAL_NUMBER.map(([k, label]) => (
              <Field key={k} label={label} htmlFor={k}>
                <Input
                  id={k}
                  type="number"
                  min={0}
                  step="any"
                  placeholder={UNKNOWN}
                  value={form.personal[k] === null ? "" : String(form.personal[k])}
                  onChange={(e) => setPersonal({ [k]: numberOrNull(e.target.value) })}
                />
              </Field>
            ))}
            {PERSONAL_URL.map(([k, label]) => (
              <Field key={k} label={label} htmlFor={k}>
                <Input id={k} type="url" placeholder="https://" value={text(form.personal[k] as string | null)} onChange={(e) => setPersonal({ [k]: orNull(e.target.value) })} />
              </Field>
            ))}
          </CardContent>
        </Card>
      )}

      {tab === "Skills" && (
        <Card>
          <CardHeader>
            <CardDescription>Only list skills you genuinely have. Job matching and resume tailoring can only use what is here.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-2">
            {SKILL_CATEGORIES.map(([k, label]) => (
              <Field key={k} label={label} htmlFor={`skill-${k}`}>
                <TagInput id={`skill-${k}`} value={form.skills[k]} onChange={(v) => setForm({ ...form, skills: { ...form.skills, [k]: v } })} />
              </Field>
            ))}
          </CardContent>
        </Card>
      )}

      {tab === "Preferences" && (
        <Card>
          <CardContent className="grid gap-4 pt-5 md:grid-cols-2">
            {PREF_LISTS.map(([k, label]) => (
              <Field key={k} label={label} htmlFor={`pref-${k}`}>
                <TagInput id={`pref-${k}`} value={form.preferences[k] as string[]} onChange={(v) => setPrefs({ [k]: v })} />
              </Field>
            ))}
            <div className="grid grid-cols-3 gap-3">
              <Field label="Remote" htmlFor="remote">
                <TriState id="remote" value={form.preferences.remote_preference} onChange={(v) => setPrefs({ remote_preference: v })} />
              </Field>
              <Field label="Hybrid" htmlFor="hybrid">
                <TriState id="hybrid" value={form.preferences.hybrid_preference} onChange={(v) => setPrefs({ hybrid_preference: v })} />
              </Field>
              <Field label="Relocation" htmlFor="relocation">
                <TriState id="relocation" value={form.preferences.relocation} onChange={(v) => setPrefs({ relocation: v })} />
              </Field>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <Field label="Min Salary" htmlFor="min_salary">
                <Input id="min_salary" type="number" min={0} value={form.preferences.min_salary ?? ""} onChange={(e) => setPrefs({ min_salary: numberOrNull(e.target.value) })} />
              </Field>
              <Field label="Max Salary" htmlFor="max_salary">
                <Input id="max_salary" type="number" min={0} value={form.preferences.max_salary ?? ""} onChange={(e) => setPrefs({ max_salary: numberOrNull(e.target.value) })} />
              </Field>
              <Field label="Currency" htmlFor="salary_currency">
                <Input id="salary_currency" placeholder="INR" value={text(form.preferences.salary_currency)} onChange={(e) => setPrefs({ salary_currency: orNull(e.target.value) })} />
              </Field>
            </div>
            <Field label="Visa Requirement" htmlFor="visa">
              <Input id="visa" placeholder={UNKNOWN} value={text(form.preferences.visa_requirement)} onChange={(e) => setPrefs({ visa_requirement: orNull(e.target.value) })} />
            </Field>
            <Field label="Timezone" htmlFor="tz" hint="Used for daily scheduled automation">
              <Input id="tz" value={form.preferences.timezone} onChange={(e) => setPrefs({ timezone: e.target.value || "Asia/Kolkata" })} />
            </Field>
          </CardContent>
        </Card>
      )}

      {tab === "Experience" && (
        <div className="flex flex-col gap-4">
          <Card>
            <CardContent className="pt-5">
              <Field label="Professional Summary" htmlFor="summary">
                <Textarea
                  id="summary"
                  rows={4}
                  placeholder={UNKNOWN}
                  value={text(form.knowledge.professional_summary)}
                  onChange={(e) => setKb({ professional_summary: orNull(e.target.value) })}
                />
              </Field>
              <Field label="Domains" htmlFor="domains" className="mt-4">
                <TagInput id="domains" value={form.knowledge.domains} onChange={(v) => setKb({ domains: v })} placeholder="e.g. Fintech, Healthcare" />
              </Field>
            </CardContent>
          </Card>
          <ListEditor<Experience>
            items={form.knowledge.experience}
            onChange={(experience) => setKb({ experience })}
            addLabel="Add experience"
            title={(e) => [e.title, e.company].filter(Boolean).join(" @ ")}
            blank={() => ({ company: "", title: "", location: null, start_date: null, end_date: null, is_current: false, domain: null, responsibilities: [], achievements: [], technologies: [] })}
            render={(e, update) => (
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label="Title *"><Input value={e.title} onChange={(ev) => update({ title: ev.target.value })} /></Field>
                <Field label="Company *"><Input value={e.company} onChange={(ev) => update({ company: ev.target.value })} /></Field>
                <Field label="Location"><Input value={text(e.location)} onChange={(ev) => update({ location: orNull(ev.target.value) })} /></Field>
                <Field label="Domain"><Input value={text(e.domain)} onChange={(ev) => update({ domain: orNull(ev.target.value) })} /></Field>
                <Field label="Start"><Input placeholder="Jan 2022" value={text(e.start_date)} onChange={(ev) => update({ start_date: orNull(ev.target.value) })} /></Field>
                <Field label="End">
                  <div className="flex items-center gap-2">
                    <Input disabled={e.is_current} placeholder={e.is_current ? "Present" : "Dec 2023"} value={text(e.end_date)} onChange={(ev) => update({ end_date: orNull(ev.target.value) })} />
                    <label className="flex items-center gap-1 whitespace-nowrap text-xs">
                      <input type="checkbox" checked={e.is_current} onChange={(ev) => update({ is_current: ev.target.checked, end_date: ev.target.checked ? null : e.end_date })} />
                      Current
                    </label>
                  </div>
                </Field>
                <Field label="Responsibilities (one per line)" className="sm:col-span-2">
                  <Textarea rows={4} defaultValue={e.responsibilities.join("\n")} onBlur={(ev) => update({ responsibilities: linesToList(ev.target.value) })} />
                </Field>
                <Field label="Achievements (one per line, with real metrics only)" className="sm:col-span-2">
                  <Textarea rows={3} defaultValue={e.achievements.join("\n")} onBlur={(ev) => update({ achievements: linesToList(ev.target.value) })} />
                </Field>
                <Field label="Technologies" className="sm:col-span-2">
                  <TagInput value={e.technologies} onChange={(technologies) => update({ technologies })} />
                </Field>
              </div>
            )}
          />
        </div>
      )}

      {tab === "Projects" && (
        <ListEditor<Project>
          items={form.knowledge.projects}
          onChange={(projects) => setKb({ projects })}
          addLabel="Add project"
          title={(p) => p.name}
          blank={() => ({ name: "", description: null, role: null, technologies: [], highlights: [], url: null })}
          render={(p, update) => (
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Name *"><Input value={p.name} onChange={(ev) => update({ name: ev.target.value })} /></Field>
              <Field label="Role"><Input value={text(p.role)} onChange={(ev) => update({ role: orNull(ev.target.value) })} /></Field>
              <Field label="Description" className="sm:col-span-2">
                <Textarea rows={3} value={text(p.description)} onChange={(ev) => update({ description: orNull(ev.target.value) })} />
              </Field>
              <Field label="Highlights (one per line)" className="sm:col-span-2">
                <Textarea rows={3} defaultValue={p.highlights.join("\n")} onBlur={(ev) => update({ highlights: linesToList(ev.target.value) })} />
              </Field>
              <Field label="Technologies"><TagInput value={p.technologies} onChange={(technologies) => update({ technologies })} /></Field>
              <Field label="URL"><Input type="url" value={text(p.url)} onChange={(ev) => update({ url: orNull(ev.target.value) })} /></Field>
            </div>
          )}
        />
      )}

      {tab === "Education" && (
        <ListEditor<Education>
          items={form.knowledge.education}
          onChange={(education) => setKb({ education })}
          addLabel="Add education"
          title={(e) => [e.degree, e.institution].filter(Boolean).join(" — ")}
          blank={() => ({ institution: null, degree: "", field: null, start_year: null, end_year: null, grade: null })}
          render={(e, update) => (
            <div className="grid gap-3 sm:grid-cols-3">
              <Field label="Degree *"><Input value={e.degree} onChange={(ev) => update({ degree: ev.target.value })} /></Field>
              <Field label="Field"><Input value={text(e.field)} onChange={(ev) => update({ field: orNull(ev.target.value) })} /></Field>
              <Field label="Institution"><Input value={text(e.institution)} onChange={(ev) => update({ institution: orNull(ev.target.value) })} /></Field>
              <Field label="Start year"><Input type="number" value={e.start_year ?? ""} onChange={(ev) => update({ start_year: numberOrNull(ev.target.value) })} /></Field>
              <Field label="End year"><Input type="number" value={e.end_year ?? ""} onChange={(ev) => update({ end_year: numberOrNull(ev.target.value) })} /></Field>
              <Field label="Grade"><Input value={text(e.grade)} onChange={(ev) => update({ grade: orNull(ev.target.value) })} /></Field>
            </div>
          )}
        />
      )}

      {tab === "Certifications" && (
        <ListEditor<Certification>
          items={form.knowledge.certifications}
          onChange={(certifications) => setKb({ certifications })}
          addLabel="Add certification"
          title={(c) => c.name}
          blank={() => ({ name: "", issuer: null, issued: null, expires: null, credential_url: null })}
          render={(c, update) => (
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Name *"><Input value={c.name} onChange={(ev) => update({ name: ev.target.value })} /></Field>
              <Field label="Issuer"><Input value={text(c.issuer)} onChange={(ev) => update({ issuer: orNull(ev.target.value) })} /></Field>
              <Field label="Issued"><Input placeholder="2023-05" value={text(c.issued)} onChange={(ev) => update({ issued: orNull(ev.target.value) })} /></Field>
              <Field label="Expires"><Input value={text(c.expires)} onChange={(ev) => update({ expires: orNull(ev.target.value) })} /></Field>
              <Field label="Credential URL" className="sm:col-span-2">
                <Input type="url" value={text(c.credential_url)} onChange={(ev) => update({ credential_url: orNull(ev.target.value) })} />
              </Field>
            </div>
          )}
        />
      )}
    </>
  );
}
