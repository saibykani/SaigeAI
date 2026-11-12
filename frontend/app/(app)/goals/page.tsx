"use client";

import { PageHeader } from "@/components/app-shell";
import { GoalsCard } from "@/components/growth";

export default function GoalsPage() {
  return (
    <>
      <PageHeader title="Weekly goals" description="Set a target for each week. Progress counts what you actually did: applications sent, recruiters contacted, tailored resumes and interview preps." />
      <GoalsCard />
    </>
  );
}
