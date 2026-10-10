// 3.6 exit-gate browser check. Needs backend + vite up.
import pw from "/Users/kaizerdewaswala/.npm/_npx/e41f203b7505f1fb/node_modules/playwright/index.js";
const { chromium } = pw;
const BASE = "http://localhost:5173";
const email = `set-${Date.now()}@example.com`;
const log = (...a) => console.log("•", ...a);

const browser = await chromium.launch({ channel: "chrome" });
const ctx = await browser.newContext({ acceptDownloads: true });
const page = await ctx.newPage();

try {
  await page.goto(`${BASE}/register`, { waitUntil: "networkidle" });
  await page.fill('input[type="email"]', email);
  await page.fill('input[type="password"]', "hunter2pw");
  await page.click('button[type="submit"]');
  await page.waitForURL("**/live", { timeout: 8000 });
  await page.waitForFunction(() => document.querySelector('[role="status"]')?.textContent?.includes("Connected"), { timeout: 8000 });

  // Record one session so export-all has content.
  await page.click("text=Start recording");
  await page.waitForSelector("text=Start a recording", { timeout: 4000 });
  await page.fill('input[placeholder="e.g. Morning baseline"]', "for-export");
  await page.click('button:has-text("Start"):not(:has-text("recording"))');
  await page.waitForFunction(() => document.body.textContent?.includes("Recording ·"), { timeout: 6000 });
  await page.waitForTimeout(2000);
  await page.click("text=Stop recording");
  log("recorded a session for export");

  // Settings: all sections render.
  await page.goto(`${BASE}/settings`, { waitUntil: "networkidle" });
  for (const s of ["Account", "Calibration", "Live view preferences", "Stress sensitivity", "Data export", "Demo mode", "About"]) {
    if (!(await page.locator(`text=${s}`).count())) throw new Error(`missing section: ${s}`);
  }
  log("all settings sections render");

  // Export all sessions → ZIP downloads.
  const [dl] = await Promise.all([
    page.waitForEvent("download", { timeout: 8000 }),
    page.click("text=Export all sessions (ZIP)"),
  ]);
  if (!dl.suggestedFilename().endsWith(".zip")) throw new Error("export-all not a zip");
  log(`export-all downloaded: ${dl.suggestedFilename()}`);

  // Toggle demo mode on.
  await page.click("#demo-mode");
  log("demo mode enabled");

  // Live view replays the canned session: pill "Demo mode", gauges populate.
  await page.goto(`${BASE}/live`, { waitUntil: "networkidle" });
  await page.waitForFunction(() => document.querySelector('[role="status"]')?.textContent?.includes("Demo mode"), { timeout: 8000 });
  log("Live pill: Demo mode");
  await page.waitForFunction(
    () => [...document.querySelectorAll(".tnum")].some((e) => /^\d{2,3}$/.test((e.textContent || "").trim())),
    { timeout: 10000 },
  );
  log("demo gauges populated");

  // Recording disabled in demo mode.
  const disabled = await page.locator('button:has-text("Start recording")').isDisabled();
  if (!disabled) throw new Error("Start recording not disabled in demo mode");
  log("recording disabled in demo mode");

  // Re-calibrate link from Settings navigates to the calibration flow.
  await page.goto(`${BASE}/settings`, { waitUntil: "networkidle" });
  await page.click('a[href="/calibration"]');
  await page.waitForURL("**/calibration", { timeout: 6000 });
  log("re-calibrate link → /calibration");

  console.log("\n3.6 SETTINGS EXIT-GATE CHECKS PASSED");
} catch (e) {
  console.error("\nFAILED:", e.message);
  process.exitCode = 1;
} finally {
  await browser.close();
}
