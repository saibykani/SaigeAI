import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  const shortcut = (name: string, url: string) => ({ name, short_name: name, url, icons: [{ src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" }] });
  return {
    id: "/",
    name: "Saige AI",
    short_name: "Saige",
    description: "Truthful AI career automation: jobs, resumes, applications and interviews in one place.",
    start_url: "/",
    scope: "/",
    display: "standalone",
    orientation: "portrait",
    background_color: "#000000",
    theme_color: "#000000",
    categories: ["productivity", "business"],
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icons/maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
    shortcuts: [shortcut("Jobs", "/jobs"), shortcut("Applications", "/applications"), shortcut("Interviews", "/interviews"), shortcut("Assistant", "/assistant")],
  };
}
