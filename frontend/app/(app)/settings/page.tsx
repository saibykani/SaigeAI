"use client";

import { Download, Pause, Play, ShieldAlert } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Notice, PageHeader } from "@/components/app-shell";
import { MatchingWeightsCard } from "@/components/matching-weights";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input } from "@/components/ui/form";
import { useApi } from "@/hooks/use-api";
import { useAuth } from "@/hooks/use-auth";
import { downloadFile, request } from "@/services/api";
import { CAPABILITIES, type AppNotification, type AutomationMode, type AutomationSettings, type ConnectedAccount } from "@/types/api";
import { cn } from "@/utils/cn";
import { formatDate } from "@/utils/format";

const MODES: { id: AutomationMode; title: string; body: string }[] = [
  { id: "conservative", title: "Conservative", body: "AI discovers, analyzes and generates. You approve everything." },
  { id: "balanced", title: "Balanced", body: "AI performs low-risk actions automatically. You approve applications and profile changes." },
  { id: "autonomous", title: "Autonomous", body: "AI submits only through permitted integrations and sends approved outreach within limits." },
];

const LIMITS: [keyof AutomationSettings["limits"], string][] = [
  ["daily_application_limit", "Daily application limit"],
  ["daily_email_limit", "Daily email limit"],
  ["daily_recruiter_contact_limit", "Daily recruiter contact limit"],
  ["min_match_score", "Minimum match score (%)"],
];

export default function SettingsPage() {
  const auto = useApi<AutomationSettings>("/automation/status");
  const connections = useApi<ConnectedAccount[]>("/auth/connections");
  const notifications = useApi<AppNotification[]>("/notifications");
  const { logout } = useAuth();
  const router = useRouter();
  const [draft, setDraft] = useState<AutomationSettings | null>(null);
  const [msg, setMsg] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const [confirmText, setConfirmText] = useState("");

  useEffect(() => {
    if (auto.data) setDraft(auto.data);
  }, [auto.data]);

  async function save(next: AutomationSettings) {
    setMsg(null);
    try {
      const r = await request<AutomationSettings>("/automation/settings", {
        method: "PUT",
        body: { mode: next.mode, pauses: next.pauses, schedules: next.schedules, limits: next.limits },
      });
      auto.setData(r);
      setMsg({ tone: "success", text: "Automation settings saved." });
    } catch (e) {
      setMsg({ tone: "error", text: e instanceof Error ? e.message : "Save failed" });
    }
  }

  async function togglePauseAll() {
    if (!draft) return;
    auto.setData(await request<AutomationSettings>(draft.paused_all ? "/automation/resume-all" : "/automation/pause-all", { method: "POST" }));
  }

  async function deleteAccount() {
    await request("/privacy/account", { method: "DELETE" });
    await logout().catch(() => undefined);
    router.replace("/register");
  }

  return (
    <>
      <PageHeader title="Automation & Privacy" description="Control what Saige may do on your behalf, and manage your data." />
      {msg && (
        <div className="mb-4">
          <Notice tone={msg.tone}>{msg.text}</Notice>
        </div>
      )}

      {draft && (
        <div className="flex flex-col gap-6">
          <Card className={cn(draft.paused_all && "border-warning")}>
            <CardHeader className="flex-row items-center justify-between gap-4">
              <div>
                <CardTitle>Emergency control</CardTitle>
                <CardDescription>
                  {draft.paused_all ? "All automation is currently paused." : "Stops every agent immediately: discovery, applications, email, outreach and profile updates."}
                </CardDescription>
              </div>
              <Button variant={draft.paused_all ? "default" : "destructive"} onClick={togglePauseAll}>
                {draft.paused_all ? <Play /> : <Pause />}
                {draft.paused_all ? "Resume all" : "PAUSE ALL AUTOMATION"}
              </Button>
            </CardHeader>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Automation mode</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-3">
              {MODES.map((m) => (
                <button
                  key={m.id}
                  type="button"
                  aria-pressed={draft.mode === m.id}
                  onClick={() => setDraft({ ...draft, mode: m.id })}
                  className={cn(
                    "cursor-pointer rounded-lg border p-4 text-left transition-colors",
                    draft.mode === m.id ? "border-primary bg-accent" : "hover:bg-muted",
                  )}
                >
                  <p className="text-sm font-medium">{m.title}</p>
                  <p className="mt-1 text-xs text-muted-foreground">{m.body}</p>
                </button>
              ))}
            </CardContent>
          </Card>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Pause individual capabilities</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-2">
                {CAPABILITIES.map(([k, label]) => (
                  <label key={k} className="flex items-center justify-between rounded-md border px-3 py-2 text-sm">
                    {label}
                    <span className="flex items-center gap-2 text-xs text-muted-foreground">
                      {draft.pauses[k] ? "Paused" : "Active"}
                      <input
                        type="checkbox"
                        checked={draft.pauses[k]}
                        onChange={(e) => setDraft({ ...draft, pauses: { ...draft.pauses, [k]: e.target.checked } })}
                      />
                    </span>
                  </label>
                ))}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Limits & schedule</CardTitle>
                <CardDescription>Schedules run in your timezone ({draft.schedules.timezone}).</CardDescription>
              </CardHeader>
              <CardContent className="grid gap-3 sm:grid-cols-2">
                {LIMITS.map(([k, label]) => (
                  <Field key={k} label={label}>
                    <Input
                      type="number"
                      min={0}
                      value={draft.limits[k]}
                      onChange={(e) => setDraft({ ...draft, limits: { ...draft.limits, [k]: Number(e.target.value) || 0 } })}
                    />
                  </Field>
                ))}
                <Field label="Profile optimization window">
                  <Input value={draft.schedules.profile_optimization_window} onChange={(e) => setDraft({ ...draft, schedules: { ...draft.schedules, profile_optimization_window: e.target.value } })} />
                </Field>
                <Field label="Timezone">
                  <Input value={draft.schedules.timezone} onChange={(e) => setDraft({ ...draft, schedules: { ...draft.schedules, timezone: e.target.value } })} />
                </Field>
              </CardContent>
            </Card>
          </div>
          <div>
            <Button onClick={() => save(draft)}>Save automation settings</Button>
          </div>
        </div>
      )}

      <div className="mt-8 grid gap-6 lg:grid-cols-2">
        <div className="lg:col-span-2">
          <MatchingWeightsCard />
        </div>
        <Card>
          <CardHeader>
            <CardTitle>Connected accounts</CardTitle>
            <CardDescription>Saige never stores Gmail, LinkedIn or Naukri passwords, OTPs or 2FA codes — only official OAuth grants.</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-2">
            {(connections.data ?? []).map((c) => (
              <div key={c.provider} className="flex items-center justify-between rounded-md border px-3 py-2 text-sm">
                <span className="capitalize">{c.provider}</span>
                {c.connected ? (
                  <Badge variant="success">Connected</Badge>
                ) : c.status.startsWith("planned") ? (
                  <Badge variant="muted">Phase {c.status.split("_").pop()}</Badge>
                ) : (
                  <Badge variant="outline">Not connected</Badge>
                )}
              </div>
            ))}
          </CardContent>
        </Card>

        <Card id="notifications">
          <CardHeader>
            <CardTitle>Notifications</CardTitle>
          </CardHeader>
          <CardContent>
            {(notifications.data ?? []).length === 0 ? (
              <p className="text-sm text-muted-foreground">You&apos;re all caught up.</p>
            ) : (
              <ul className="divide-y">
                {notifications.data!.map((n) => (
                  <li key={n.id} className="flex items-start justify-between gap-3 py-2 text-sm">
                    <div>
                      <p className={cn(!n.read && "font-medium")}>{n.title}</p>
                      {n.body && <p className="text-xs text-muted-foreground">{n.body}</p>}
                      <p className="text-xs text-muted-foreground">{formatDate(n.created_at)}</p>
                    </div>
                    {!n.read && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={async () => {
                          await request(`/notifications/${n.id}/read`, { method: "POST" });
                          await notifications.reload();
                        }}
                      >
                        Mark read
                      </Button>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Your data</CardTitle>
            <CardDescription>Export everything Saige stores about you, or permanently delete your account.</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <div>
              <Button variant="outline" onClick={() => downloadFile("/privacy/export", "saige-ai-export.json")}>
                <Download /> Export my data
              </Button>
            </div>
            <div className="rounded-lg border border-destructive/40 p-4">
              <p className="flex items-center gap-2 text-sm font-medium text-destructive">
                <ShieldAlert className="size-4" /> Delete my account
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                Removes your profile, resumes, applications, history and sessions. Type DELETE to confirm.
              </p>
              <div className="mt-3 flex gap-2">
                <Input className="max-w-40" value={confirmText} onChange={(e) => setConfirmText(e.target.value)} aria-label="Type DELETE to confirm" />
                <Button variant="destructive" disabled={confirmText !== "DELETE"} onClick={deleteAccount}>
                  Delete permanently
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </>
  );
}
