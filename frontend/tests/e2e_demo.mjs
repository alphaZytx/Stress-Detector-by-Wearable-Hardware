// 4.4.b demo-mode mechanics. Needs backend + vite up.
//   node tests/e2e_demo.mjs
import pw from "/Users/kaizerdewaswala/.npm/_npx/e41f203b7505f1fb/node_modules/playwright/index.js";
const { chromium } = pw;
const BASE = "http://localhost:5173";
const email = `demo-${Date.now()}@example.com`;
const log = (...a) => console.log("•", ...a);
const pill = () => page.evaluate(() => document.querySelector('[role="status"]')?.textContent || "");
const browser = await chromium.launch({ channel: "chrome" });
const page = await browser.newPage();

try {
  await page.goto(`${BASE}/register`, { waitUntil: "networkidle" });
  await page.fill('input[type="email"]', email);
  await page.fill('input[type="password"]', "hunter2pw");
  await page.click('button[type="submit"]');
  await page.waitForURL("**/live", { timeout: 8000 });

  // Enable demo mode in Settings.
  await page.goto(`${BASE}/settings`, { waitUntil: "networkidle" });
  await page.click("#demo-mode");
  log("demo mode enabled");

  // Live: pill shows "Demo mode".
  await page.goto(`${BASE}/live`, { waitUntil: "networkidle" });
  await page.waitForFunction(() => /Demo mode/i.test(document.querySelector('[role="status"]')?.textContent || ""), { timeout: 8000 });
  log(`pill: ${(await pill()).trim()}`);

  // Recording disabled in demo mode (button disabled).
  const startBtn = page.locator('button:has-text("Start recording")');
  if (!(await startBtn.isDisabled())) throw new Error("Start recording should be disabled in demo mode");
  log("Start recording is disabled (demo)");

  // Demo data renders (some gauge/stat value appears within a few seconds).
  await page.waitForFunction(() => /\d/.test(document.body.textContent || ""), { timeout: 6000 });
  log("demo replay renders data");

  // Persists across refresh.
  await page.reload({ waitUntil: "networkidle" });
  await page.waitForFunction(() => /Demo mode/i.test(document.querySelector('[role="status"]')?.textContent || ""), { timeout: 8000 });
  log("demo mode persists across refresh");

  // Toggle demo OFF → Live returns to real WS (Connected).
  await page.goto(`${BASE}/settings`, { waitUntil: "networkidle" });
  await page.click("#demo-mode");
  await page.goto(`${BASE}/live`, { waitUntil: "networkidle" });
  await page.waitForFunction(() => /Connected/i.test(document.querySelector('[role="status"]')?.textContent || ""), { timeout: 10000 });
  log(`demo off → pill: ${(await pill()).trim()}`);

  console.log("\n4.4 DEMO-MODE MECHANICS PASSED");
} catch (e) {
  console.error("\nFAILED:", e.message, "| pill:", (await pill()).trim());
  process.exitCode = 1;
} finally {
  await browser.close();
}
