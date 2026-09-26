"use client";

import { PageHeader } from "@/components/app-shell";
import { Chat } from "@/components/assistant";
import { Card } from "@/components/ui/card";

export default function AssistantPage() {
  return (
    <>
      <PageHeader title="Saige AI" description="Chat with your job-search assistant. It knows your profile, jobs, applications, inbox and contacts, and never invents facts about you." />
      <Card className="animate-rise h-[calc(100vh-15rem)] min-h-[480px] overflow-hidden p-0">
        <Chat />
      </Card>
    </>
  );
}
