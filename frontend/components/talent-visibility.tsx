"use client";

import { useState } from "react";

import { Notice } from "@/components/app-shell";
import { useT } from "@/components/i18n";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useApi } from "@/hooks/use-api";
import { request } from "@/services/api";
import type { IncomingTalentRequest } from "@/types/api";

/** "Let recruiters find me" (off by default) plus recruiter interest requests to accept or decline. */
export function TalentVisibilityCard() {
  const { t } = useT();
  const settings = useApi<{ discoverable: boolean }>("/talent/settings");
  const requests = useApi<IncomingTalentRequest[]>("/talent/requests");
  const [error, setError] = useState<string | null>(null);
  const on = Boolean(settings.data?.discoverable);

  async function act(fn: () => Promise<unknown>) {
    setError(null);
    try { await fn(); } catch (e) { setError(e instanceof Error ? e.message : "Something went wrong"); }
  }

  return (
    <Card id="recruiters">
      <CardHeader>
        <CardTitle>{t("Let recruiters find me")}</CardTitle>
        <CardDescription>
          When on, recruiters on Saige AI can see your name, current role, years of experience, skills, city and published portfolio.
          Your email and phone stay hidden until you accept a request.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {error && <Notice tone="error">{error}</Notice>}
        <div className="flex items-center justify-between rounded-md border px-3 py-2 text-sm">
          <span>{on ? t("Visible to recruiters") : t("Hidden from recruiters")}</span>
          <Button size="sm" variant={on ? "outline" : "default"} disabled={settings.loading}
            onClick={() => void act(async () => settings.setData(await request<{ discoverable: boolean }>("/talent/settings", { method: "PUT", body: { discoverable: !on } })))}>
            {on ? t("Turn off") : t("Turn on")}
          </Button>
        </div>
        {(requests.data ?? []).map((r) => (
          <div key={r.id} className="rounded-md border px-3 py-2 text-sm">
            <div className="flex items-center justify-between gap-2">
              <span className="font-medium">{r.recruiter_name}{r.job_title ? ` · ${r.job_title}${r.company ? ` at ${r.company}` : ""}` : ""}</span>
              {r.status !== "pending" && <Badge variant={r.status === "accepted" ? "success" : "muted"}>{r.status}</Badge>}
            </div>
            {r.message && <p className="mt-1 text-muted-foreground">{r.message}</p>}
            {r.status === "pending" && (
              <div className="mt-2 flex gap-2">
                {[true, false].map((accept) => (
                  <Button key={String(accept)} size="sm" variant={accept ? "default" : "outline"}
                    onClick={() => void act(async () => { await request(`/talent/requests/${r.id}/respond`, { method: "POST", body: { accept } }); await requests.reload(); })}>
                    {accept ? t("Accept and share contact") : t("Decline")}
                  </Button>
                ))}
              </div>
            )}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
