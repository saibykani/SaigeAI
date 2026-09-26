import type { Metadata } from "next";
import { Google_Sans, Google_Sans_Code } from "next/font/google";

import { DEFAULT_THEME, themeBootScript } from "@/components/theme-config";
import { LanguageProvider } from "@/components/i18n";
import { AuthProvider } from "@/hooks/use-auth";

import "./globals.css";

const googleSans = Google_Sans({ subsets: ["latin"], variable: "--font-google-sans", display: "swap" });
const googleSansCode = Google_Sans_Code({ subsets: ["latin"], variable: "--font-google-sans-code", display: "swap" });

export const metadata: Metadata = {
  title: { default: "Saige AI", template: "%s · Saige AI" },
  description: "AI career command center: profile, resumes, jobs and applications in one place.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" data-theme={DEFAULT_THEME} suppressHydrationWarning className={`${googleSans.variable} ${googleSansCode.variable}`}>
      <head>
        {/* Applies the saved theme before first paint (no flash). */}
        <script dangerouslySetInnerHTML={{ __html: themeBootScript }} />
      </head>
      <body className="app-backdrop font-sans antialiased">
        <LanguageProvider><AuthProvider>{children}</AuthProvider></LanguageProvider>
      </body>
    </html>
  );
}
