// Render docs/architecture.mmd → docs/architecture.png using the Playwright
// Chrome (no mermaid-cli install needed). Usage: node scripts/render_mermaid.mjs
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
// Resolve playwright from wherever it is installed rather than a hardcoded
// path (the previous absolute path only existed on one developer's machine).
// Run this with `npx playwright` available, or `npm i -D playwright` first.
let chromium;
try {
  ({ chromium } = await import("playwright"));
} catch {
  console.error(
    "playwright not found. Install it first, e.g.\n" +
    "  npm i -D playwright && npx playwright install chrome\n" +
    "then re-run: node scripts/render_mermaid.mjs",
  );
  process.exit(1);
}

const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const src = readFileSync(path.join(REPO, "docs/architecture.mmd"), "utf8");
const out = path.join(REPO, "docs/architecture.png");

const html = `<!doctype html><html><head><meta charset="utf-8">
<style>body{margin:0;background:#fff;padding:24px;font-family:Inter,system-ui,sans-serif}</style>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
</head><body><div class="mermaid">${src}</div>
<script>mermaid.initialize({startOnLoad:true,theme:"default",flowchart:{useMaxWidth:false}});</script>
</body></html>`;

const browser = await chromium.launch({ channel: "chrome" });
const page = await browser.newPage({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 2 });
try {
  await page.setContent(html, { waitUntil: "networkidle" });
  const el = await page.waitForSelector(".mermaid svg", { timeout: 20000 });
  await el.screenshot({ path: out });
  console.log("wrote", out);
} catch (e) {
  console.error("FAILED:", e.message);
  process.exitCode = 1;
} finally {
  await browser.close();
}
