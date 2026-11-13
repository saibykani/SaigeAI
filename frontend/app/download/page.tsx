import type { Metadata } from "next";

import { AppDownload } from "@/components/app-download";

export const metadata: Metadata = {
  title: { absolute: "Get the Saige AI app · Android & iPhone" },
  description: "Download the Saige AI Android app, or add Saige AI to your iPhone home screen.",
};

/** Public download page (no sign-in needed): Android APK + iPhone home-screen install. */
export default function DownloadPage() {
  return (
    <main className="min-h-dvh bg-black px-4 py-12 text-white">
      <div className="mx-auto max-w-3xl">
        <AppDownload />
      </div>
    </main>
  );
}
