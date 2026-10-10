// 4.6.b - capture dashboard screenshots for the BE report.
// Needs backend (csv_replay, speed≈10) + vite up. Writes to docs/report/figures/.
//   node tests/capture_screenshots.mjs
import { fileURLToPath } from "node:url";
import path from "node:path";
import pw from "/Users/kaizerdewaswala/.npm/_npx/e41f203b7505f1fb/node_modules/playwright/index.js";
const { chromium } = pw;
const BASE = "http://localhost:5173";
const FIG = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../docs/report/figures");
const email = `shot-${Date.now()}@example.com`;
const log = (...a) => console.log("•", ...a);

const browser = await chromium.launch({ channel: "chrome" });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
const shot = (name) => page.screenshot({ path: path.join(FIG, name) });

try {
  await page.goto(`${BASE}/register`, { waitUntil: "networkidle" });
  await page.fill('input[type="email"]', email);
  await page.fill('input[type="password"]', "hunter2pw");
  await page.click('button[type="submit"]');
  await page.waitForURL("**/live", { timeout: 8000 });

  // --- Calibration capture screen ---
  await page.goto(`${BASE}/calibration?dev_seconds=30`, { waitUntil: "networkidle" });
  await page.click("text=Begin");
  await page.waitForTimeout(2500); // let the progress ring + live readouts populate
  await shot("calibration_capture.png");
  log("calibration_capture.png");

  // --- Breathing exercise mid-cycle ---
  await page.goto(`${BASE}/breathing`, { waitUntil: "networkidle" });
  await page.click('button:has-text("Coherent")');
  await page.click("text=Start breathing");
  await page.waitForFunction(() => /Breathe (in|out)/.test(document.body.textContent || ""), { timeout: 6000 });
  await page.waitForTimeout(1500); // mid-phase, disc enlarged
  await shot("breathing_midcycle.png");
  log("breathing_midcycle.png");

  // --- Record a session long enough to span baseline → stress (speed≈10) ---
  await page.goto(`${BASE}/live`, { waitUntil: "networkidle" });
  await page.waitForFunction(() => document.querySelector('[role="status"]')?.textContent?.includes("Connected"), { timeout: 8000 });
  await page.click("text=Start recording");
  await page.waitForSelector("text=Start a recording", { timeout: 4000 });
  await page.fill('input[placeholder="e.g. Morning baseline"]', "report-capture");
  await page.click('button:has-text("Start"):not(:has-text("recording"))');
  await page.waitForFunction(() => document.body.textContent?.includes("Recording ·"), { timeout: 6000 });
  log("recording… (~62s to span baseline→stress at speed 10)");

  // Capture the Live view once a STRESS prediction shows (poll up to ~80s).
  let gotStress = false;
  for (let i = 0; i < 80; i++) {
    await page.waitForTimeout(1000);
    const txt = (await page.textContent("body")) || "";
    if (/stress/i.test(txt) && /\d/.test(txt)) {
      // Heuristic: capture once the stress state is visible after some data.
      if (i > 8) { gotStress = true; break; }
    }
  }
  await shot("live_dashboard.png");
  log(`live_dashboard.png (stress visible: ${gotStress})`);
  await page.click("text=Stop recording");
  await page.waitForFunction(() => !document.body.textContent?.includes("Recording ·"), { timeout: 6000 });

  // --- History detail: timeline showing the baseline→stress arc ---
  await page.click('a[href="/history"]');
  await page.waitForSelector("text=report-capture", { timeout: 6000 });
  await shot("history_list.png");
  await page.click("text=report-capture");
  await page.waitForURL("**/history/**", { timeout: 6000 });
  await page.waitForSelector("text=Stress timeline", { timeout: 8000 });
  await page.waitForTimeout(1000);
  await shot("session_detail.png");
  log("session_detail.png + history_list.png");

  console.log("\n4.6 SCREENSHOTS CAPTURED →", FIG);
} catch (e) {
  console.error("\nFAILED:", e.message);
  process.exitCode = 1;
} finally {
  await browser.close();
}
