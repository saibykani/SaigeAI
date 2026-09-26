import type { Metadata } from "next";
import { Google_Sans, Google_Sans_Code } from "next/font/google";

import { AuthProvider } from "@/hooks/use-auth";

import "./globals.css";

const googleSans = Google_Sans({ subsets: ["latin"], variable: "--font-google-sans", display: "swap" });
const googleSansCode = Google_Sans_Code({ subsets: ["latin"], variable: "--font-google-sans-code", display: "swap" });

export const metadata: Metadata = {
  title: "Saige AI",
  description: "AI career command center: profile, resumes, jobs and applications in one place.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${googleSans.variable} ${googleSansCode.variable}`}>
      <body className="app-backdrop font-sans antialiased">
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
