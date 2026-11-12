"use client";

import { PageHeader } from "@/components/app-shell";
import { GhostingList } from "@/components/growth";

export default function FollowupsPage() {
  return (
    <>
      <PageHeader title="Follow-ups" description="Applications that haven't had a reply for 10 days or more. Open one to draft a polite follow-up; nothing is sent without your approval." />
      <GhostingList />
    </>
  );
}
