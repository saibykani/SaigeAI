import type { NextConfig } from "next";

// On Vercel the API is its own project (saige-ai-api); BACKEND_URL overrides either default.
const backend =
  process.env.BACKEND_URL || (process.env.VERCEL ? "https://saige-ai-api.vercel.app" : "http://localhost:8000");

const nextConfig: NextConfig = {
  output: "standalone",
  // Lets a verification build run without clobbering a running dev server's .next folder.
  distDir: process.env.NEXT_DIST_DIR || ".next",
  // Next 16 blocks dev-only assets for non-localhost origins; allow the loopback IP too.
  allowedDevOrigins: ["127.0.0.1"],
  poweredByHeader: false,
  // Same-origin proxy: the browser only ever talks to the Next.js origin, so the refresh-token
  // cookie stays first-party and no backend URL or secret reaches client code.
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        ],
      },
    ];
  },
};

export default nextConfig;
