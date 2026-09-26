// Builds the Chrome extension download: renders PNG icons from frontend/app/icon.svg, then zips
// extension/ into frontend/public/saige-extension.zip (served at /saige-extension.zip).
// Run after changing anything in extension/:  node scripts/build-extension.mjs
// Needs playwright-core (run from a folder where it is installed, or set PLAYWRIGHT_DIR) and
// Edge or Chrome for the icon render.
import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const ext = path.join(root, "extension");
const svg = fs.readFileSync(path.join(root, "frontend/app/icon.svg"), "utf8");

// Resolve playwright-core from the current directory (or PLAYWRIGHT_DIR), so it needn't be a repo dependency.
const require = createRequire(path.join(process.env.PLAYWRIGHT_DIR || process.cwd(), "noop.js"));
const { chromium } = require("playwright-core");
const browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL || "msedge", headless: true });
const page = await browser.newPage();
fs.mkdirSync(path.join(ext, "icons"), { recursive: true });
for (const size of [16, 32, 48, 128]) {
  await page.setViewportSize({ width: size, height: size });
  await page.setContent(`<style>html,body{margin:0;background:transparent}svg{width:${size}px;height:${size}px;display:block}</style>${svg}`);
  await page.screenshot({ path: path.join(ext, "icons", `${size}.png`), omitBackground: true });
}
await browser.close();

const out = path.join(root, "frontend/public/saige-extension.zip");
fs.rmSync(out, { force: true });
// Python's zipfile is available wherever the backend runs; it keeps paths relative to extension/.
execFileSync("python", ["-c", `
import os, sys, zipfile
src, out = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for base, _, files in os.walk(src):
        for f in files:
            full = os.path.join(base, f)
            z.write(full, os.path.relpath(full, src))
`, ext, out]);
console.log(`Built ${path.relative(root, out)} (${fs.statSync(out).size} bytes)`);
