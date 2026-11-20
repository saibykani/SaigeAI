"use client";

import { Swords } from "lucide-react";
import Link from "next/link";

import { Notice, PageHeader } from "@/components/app-shell";
import { useT } from "@/components/i18n";
import { Card, CardContent } from "@/components/ui/card";
import { useApi } from "@/hooks/use-api";
import type { WarRoomListItem } from "@/types/api";
import { formatDateTime } from "@/utils/format";

export default function WarRoomListPage() {
  const { t } = useT();
  const { data, error } = useApi<{ interviews: WarRoomListItem[] }>("/war-room");
  return (
    <>
      <PageHeader title="Interview war room" description="Prep right before an interview: your brief, likely questions with your own stories, and a checklist." />
      {error && <Notice tone="error">{error}</Notice>}
      {!data ? (
        <div className="skeleton h-48 rounded-3xl" />
      ) : data.interviews.length === 0 ? (
        <Card><CardContent className="py-12 text-center text-sm text-muted-foreground">{t("No upcoming interviews in the next 14 days.")}</CardContent></Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {data.interviews.map((i) => (
            <Link key={i.interview_id} href={`/war-room/${i.interview_id}`}>
              <Card className="lift p-5" style={{ borderColor: "color-mix(in srgb, var(--tone-orange) 28%, transparent)" }}>
                <div className="flex items-start gap-3">
                  <Swords className="mt-1 size-5" style={{ color: "var(--tone-orange)" }} />
                  <div className="min-w-0 flex-1">
                    <p className="font-semibold">{i.role} · {i.company}</p>
                    <p className="text-sm text-muted-foreground">{i.round || t("Interview")} · {formatDateTime(i.scheduled_at)}</p>
                    <p className="mt-2 text-xs text-muted-foreground">{t("Checklist")} {i.checklist_done}/{i.checklist_total}</p>
                  </div>
                </div>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </>
  );
}
