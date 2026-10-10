// 3.4 exit-gate browser check. Needs backend (csv_replay, raised speed) + vite up.
import pw from "/Users/kaizerdewaswala/.npm/_npx/e41f203b7505f1fb/node_modules/playwright/index.js";
const { chromium } = pw;
const BASE = "http://localhost:5173";
const API = "http://127.0.0.1:8010";
const email = `calib-${Date.now()}@example.com`;
const log = (...a) => console.log("•", ...a);

const browser = await chromium.launch({ channel: "chrome" });
const page = await browser.newPage();
let token = "";
page.on("response", async (r) => {
  if (r.url().endsWith("/auth/register")) {
    try {
      token = (await r.json()).access_token;
    } catch {}
  }
});

async function startRecording(label) {
  await page.click("text=Start recording");
  await page.waitForSelector("text=Start a recording", { timeout: 4000 });
  await page.fill('input[placeholder="e.g. Morning baseline"]', label);
  await page.click('button:has-text("Start"):not(:has-text("recording"))');
  await page.waitForFunction(() => document.body.textContent?.includes("Recording ·"), { timeout: 6000 });
}
async function stopRecording() {
  await page.click("text=Stop recording");
  await page.waitForFunction(() => !document.body.textContent?.includes("Recording ·"), { timeout: 6000 });
}
const calibratedBadgeVisible = () =>
  page.evaluate(() => !!document.querySelector(".text-clinical-accent") &&
    [...document.querySelectorAll("*")].some((e) => e.childElementCount === 0 && e.textContent?.trim() === "calibrated"));

try {
  await page.goto(`${BASE}/register`, { waitUntil: "networkidle" });
  await page.fill('input[type="email"]', email);
  await page.fill('input[type="password"]', "hunter2pw");
  await page.click('button[type="submit"]');
  await page.waitForURL("**/live", { timeout: 8000 });

  // 1. Full calibration flow (dev short capture).
  await page.goto(`${BASE}/calibration?dev_seconds=4`, { waitUntil: "networkidle" });
  await page.click("text=Begin");
  await page.waitForSelector("text=Your baseline", { timeout: 15000 });
  log("capture complete → confirm step");
  await page.click("text=Save baseline");
  await page.waitForSelector("text=Calibration saved", { timeout: 8000 });
  log("calibration saved");

  // 2. Backend stored it.
  const cal = await (
    await fetch(`${API}/calibration`, { headers: { Authorization: `Bearer ${token}` } })
  ).json();
  if (!cal.calibrated) throw new Error("backend did not store calibration");
  log(`backend calibrated: hr=${cal.hr_baseline?.toFixed?.(1)} gsr=${cal.gsr_baseline?.toFixed?.(1)}`);

  // 3. Start a session (calibration ON) → a prediction shows calibration_applied.
  await page.goto(`${BASE}/live`, { waitUntil: "networkidle" });
  await page.waitForFunction(() => document.querySelector('[role="status"]')?.textContent?.includes("Connected"), { timeout: 8000 });
  await startRecording("calibrated-session");
  await page.waitForFunction(
    () => [...document.querySelectorAll("*")].some((e) => e.childElementCount === 0 && e.textContent?.trim() === "calibrated"),
    { timeout: 12000 },
  );
  log("Live prediction shows calibration_applied=true (calibrated badge)");
  await stopRecording();

  // 4. Disable calibration in Settings → new session → NOT calibrated.
  await page.goto(`${BASE}/settings`, { waitUntil: "networkidle" });
  await page.click("#use-calibration");
  await page.goto(`${BASE}/live`, { waitUntil: "networkidle" });
  await page.waitForFunction(() => document.querySelector('[role="status"]')?.textContent?.includes("Connected"), { timeout: 8000 });
  await startRecording("uncalibrated-session");
  await page.waitForTimeout(4000); // let several predictions arrive
  if (await calibratedBadgeVisible()) throw new Error("calibrated badge present when disabled");
  log("calibration disabled → predictions calibration_applied=false (no badge)");
  await stopRecording();

  // 5. Clear calibration in Settings → Not calibrated.
  await page.goto(`${BASE}/settings`, { waitUntil: "networkidle" });
  await page.waitForSelector("text=Clear calibration", { timeout: 6000 });
  await page.click("text=Clear calibration");
  await page.waitForSelector("text=Not calibrated", { timeout: 6000 });
  log("calibration cleared → Not calibrated");

  console.log("\n3.4 CALIBRATION EXIT-GATE CHECKS PASSED");
} catch (e) {
  console.error("\nFAILED:", e.message);
  process.exitCode = 1;
} finally {
  await browser.close();
}
