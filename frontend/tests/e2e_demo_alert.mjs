// 4.4.b - confirm the stress-alert banner fires during the canned demo replay.
// MANUAL / HEADED ONLY: the replay is 1 Hz wall-clock and the banner needs >30s
// of sustained smoothed stress (fires ~t=129s). Headless Chrome throttles
// background-tab timers, so the replay can't reach t=129 in real time - run this
// HEADED with the window focused. The firing LOGIC is covered deterministically
// by vitest (StressAlert.test.tsx) and the demo asset is guarded by the backend
// test test_demo_session_triggers_breathing_banner. Needs backend + vite up.
//   node tests/e2e_demo_alert.mjs
import pw from "/Users/kaizerdewaswala/.npm/_npx/e41f203b7505f1fb/node_modules/playwright/index.js";
const { chromium } = pw;
const BASE = "http://localhost:5173";
const email = `demoalert-${Date.now()}@example.com`;
const log = (...a) => console.log("•", ...a);
const browser = await chromium.launch({ channel: "chrome", headless: false });
const page = await browser.newPage();

try {
  await page.goto(`${BASE}/register`, { waitUntil: "networkidle" });
  await page.fill('input[type="email"]', email);
  await page.fill('input[type="password"]', "hunter2pw");
  await page.click('button[type="submit"]');
  await page.waitForURL("**/live", { timeout: 8000 });

  await page.goto(`${BASE}/settings`, { waitUntil: "networkidle" });
  await page.click("#demo-mode");
  await page.goto(`${BASE}/live`, { waitUntil: "networkidle" });
  await page.waitForFunction(() => /Demo mode/i.test(document.querySelector('[role="status"]')?.textContent || ""), { timeout: 8000 });
  log("demo replay started; waiting for the breathing banner (~130s)…");

  await page.waitForFunction(
    () => /Stress has been elevated|Try breathing/i.test(document.body.textContent || ""),
    undefined, // arg (none) - must be present so the next object is parsed as options
    { timeout: 160000 },
  );
  log("stress-alert banner appeared");

  // The 'Try breathing' link routes to the breathing exercise.
  await page.click("text=Try breathing");
  await page.waitForURL("**/breathing", { timeout: 6000 });
  log("'Try breathing' → /breathing");

  console.log("\n4.4 DEMO STRESS-ALERT BANNER FIRED");
} catch (e) {
  console.error("\nFAILED:", e.message);
  process.exitCode = 1;
} finally {
  await browser.close();
}
