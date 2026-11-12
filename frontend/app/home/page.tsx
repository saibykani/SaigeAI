import type { Metadata } from "next";
import { Barlow, Instrument_Serif } from "next/font/google";

import { Landing } from "@/components/landing/landing";

const serif = Instrument_Serif({ subsets: ["latin"], weight: "400", style: ["normal", "italic"], variable: "--font-instrument", display: "swap" });
const barlow = Barlow({ subsets: ["latin"], weight: ["300", "400", "500", "600"], variable: "--font-barlow", display: "swap" });

const title = "Saige AI · Your truthful AI career agent";
const description =
  "Saige AI finds the right jobs, writes ATS-ready resumes from facts you have verified, tracks applications, reaches recruiters, and asks before it acts.";

export const metadata: Metadata = {
  metadataBase: new URL("https://saige-ai.vercel.app"),
  title: { absolute: title },
  description,
  alternates: { canonical: "/home" },
  openGraph: { title, description, url: "/home", siteName: "Saige AI", type: "website", locale: "en_IN" },
  twitter: { card: "summary", title, description },
};

/** Public marketing page. Signed-out visitors to "/" are sent here by the app shell. */
export default function HomePage() {
  return <Landing fontClass={`${serif.variable} ${barlow.variable}`} />;
}
