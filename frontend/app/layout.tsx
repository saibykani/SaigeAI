import type { Metadata } from "next";
import { Inter } from "next/font/google";

import { AuthProvider } from "@/hooks/use-auth";

import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "Saige AI",
  description: "AI career command center: profile, resumes, jobs and applications in one place.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="font-sans antialiased">
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
