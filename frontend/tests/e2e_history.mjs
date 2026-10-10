// 3.3 exit-gate browser check. Needs backend (csv_replay, raised speed) + vite up.
import pw from "/Users/kaizerdewaswala/.npm/_npx/e41f203b7505f1fb/node_modules/playwright/index.js";
const { chromium } = pw;
const BASE = "http://localhost:5173";
const email = `hist-${Date.now()}@example.com`;
const log = (...a) => console.log("•", ...a);

const browser = await chromium.launch({ channel: "chrome" });
const ctx = await browser.newContext({ acceptDownloads: true });
const page = await ctx.newPage();

async function record(seconds, label) {
  await page.click("text=Start recording");
  await page.waitForSelector("text=Start a recording", { timeout: 4000 });
  await page.fill('input[placeholder="e.g. Morning baseline"]', label);
  await page.click('button:has-text("Start"):not(:has-text("recording"))');
  await page.waitForFunction(() => document.body.textContent?.includes("Recording ·"), { timeout: 6000 });
  await page.waitForTimeout(seconds * 1000);
  await page.click("text=Stop recording");
  await page.waitForFunction(() => !document.body.textContent?.includes("Recording ·"), { timeout: 6000 });
}

try {
  await page.goto(`${BASE}/register`, { waitUntil: "networkidle" });
  await page.fill('input[type="email"]', email);
  await page.fill('input[type="password"]', "hunter2pw");
  await page.click('button[type="submit"]');
  await page.waitForURL("**/live", { timeout: 8000 });
  await page.waitForFunction(() => document.querySelector('[role="status"]')?.textContent?.includes("Connected"), { timeout: 8000 });

  // Record two sessions (high replay speed → plenty of samples/predictions fast).
  await record(6, "session-A");
  await record(5, "session-B");
  log("recorded 2 sessions");

  // History list shows both.
  await page.click('a[href="/history"]');
  await page.waitForSelector("text=session-A", { timeout: 6000 });
  await page.waitForSelector("text=session-B", { timeout: 6000 });
  log("both sessions listed in /history");

  // Open session-A detail.
  await page.click("text=session-A");
  await page.waitForURL("**/history/**", { timeout: 6000 });
  await page.waitForSelector("text=Stress timeline", { timeout: 6000 });
  log("detail view + stress timeline rendered");

  // Drag the playhead and confirm the at-playhead readout updates.
  const slider = page.locator('input[type="range"]');
  await slider.focus();
  for (let i = 0; i < 10; i++) await page.keyboard.press("ArrowRight");
  const playheadLabel = await page.locator('label[for="scrub"]').textContent();
  if (!/Playhead · [1-9]/.test(playheadLabel || "")) throw new Error(`playhead did not move: ${playheadLabel}`);
  log(`playhead moved (${playheadLabel?.trim()})`);

  // Add an annotation.
  await page.click("text=Add annotation");
  await page.waitForSelector('input[placeholder="e.g. felt anxious"]', { timeout: 4000 });
  await page.fill('input[placeholder="e.g. felt anxious"]', "manual-marker");
  await page.click('button:has-text("Save annotation")');
  await page.waitForFunction(() => document.body.textContent?.includes("manual-marker"), { timeout: 6000 });
  log("annotation saved + visible on timeline");

  // Export JSON via the History row dropdown.
  await page.click('a[href="/history"]');
  await page.waitForSelector("text=session-A", { timeout: 6000 });
  // Open the actions menu on the first row.
  await page.locator('button[aria-label="Session actions"]').first().click();
  const [dl] = await Promise.all([
    page.waitForEvent("download", { timeout: 8000 }),
    page.click("text=Export JSON"),
  ]);
  log(`export JSON downloaded: ${dl.suggestedFilename()}`);

  // Delete a session with confirmation.
  const before = await page.locator("[data-session-card]").count();
  await page.locator('button[aria-label="Session actions"]').first().click();
  await page.click("text=Delete");
  await page.waitForSelector("text=Delete session?", { timeout: 4000 });
  await page.click('button:has-text("Delete"):not(:has-text("session"))');
  await page.waitForFunction(
    (n) => document.querySelectorAll("[data-session-card]").length === n - 1,
    before,
    { timeout: 8000 },
  );
  log(`session deleted (${before} → ${before - 1} cards)`);

  console.log("\n3.3 HISTORY EXIT-GATE CHECKS PASSED");
} catch (e) {
  console.error("\nFAILED:", e.message);
  process.exitCode = 1;
} finally {
  await browser.close();
}
