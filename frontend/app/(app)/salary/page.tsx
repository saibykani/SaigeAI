"use client";

import { PageHeader } from "@/components/app-shell";
import { SalaryInsights } from "@/components/growth";

export default function SalaryPage() {
  return (
    <>
      <PageHeader title="Salary insights" description="Pay ranges for your role from job postings that list a salary, compared with your expected CTC, plus AmbitionBox and Glassdoor links for each company." />
      <SalaryInsights />
    </>
  );
}
