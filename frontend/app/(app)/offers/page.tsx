"use client";

import { PageHeader } from "@/components/app-shell";
import { OfferCalculator } from "@/components/offers";

export default function OffersPage() {
  return (
    <>
      <PageHeader title="Offer calculator" description="See your real monthly in-hand pay under both tax regimes, compare up to three offers with your current salary, and price the notice-period buyout." />
      <OfferCalculator />
    </>
  );
}
