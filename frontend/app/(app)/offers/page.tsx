"use client";

import { useState } from "react";

import { PageHeader } from "@/components/app-shell";
import { useT } from "@/components/i18n";
import { OfferCompare } from "@/components/offer-compare";
import { SalaryInsights } from "@/components/growth";
import { OfferCalculator } from "@/components/offers";
import { cn } from "@/utils/cn";

export default function OffersPage() {
  const { t } = useT();
  const [tab, setTab] = useState<"calc" | "compare" | "salary">("calc");
  const tabs: ["calc" | "compare" | "salary", string][] = [["calc", "Calculator"], ["compare", "Compare offers"], ["salary", "Salary insights"]];
  return (
    <>
      <PageHeader title="Offer calculator" description="See your real monthly in-hand pay under both tax regimes, compare up to three offers with your current salary, and price the notice-period buyout. Then weigh saved offers on money, growth, commute and what matters to you." />
      <div className="mb-6 flex gap-1 rounded-full bg-muted p-1 w-fit print:hidden" role="group" aria-label={t("Offers")}>
        {tabs.map(([k, l]) => (
          <button key={k} type="button" aria-pressed={tab === k} onClick={() => setTab(k)}
            className={cn("rounded-full px-4 py-1.5 text-sm", tab === k ? "bg-card font-medium text-primary shadow-sm" : "text-muted-foreground")}>{t(l)}</button>
        ))}
      </div>
      {tab === "calc" ? <OfferCalculator /> : tab === "compare" ? <OfferCompare /> : <SalaryInsights />}
    </>
  );
}
