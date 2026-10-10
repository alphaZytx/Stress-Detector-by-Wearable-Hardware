// 3.5 exit-gate browser check. Needs backend + vite up.
import pw from "/Users/kaizerdewaswala/.npm/_npx/e41f203b7505f1fb/node_modules/playwright/index.js";
const { chromium } = pw;
const BASE = "http://localhost:5173";
const email = `breath-${Date.now()}@example.com`;
const log = (...a) => console.log("•", ...a);

const browser = await chromium.launch({ channel: "chrome" });
const page = await browser.newPage();

try {
  await page.goto(`${BASE}/register`, { waitUntil: "networkidle" });
  await page.fill('input[type="email"]', email);
  await page.fill('input[type="password"]', "hunter2pw");
  await page.click('button[type="submit"]');
  await page.waitForURL("**/live", { timeout: 8000 });

  await page.goto(`${BASE}/breathing`, { waitUntil: "networkidle" });
  await page.waitForSelector("text=Breathing exercise", { timeout: 6000 });
  log("breathing setup screen");

  // Switch pattern → card becomes selected (re-times the circle on start).
  await page.click('button:has-text("4-7-8")');
  const selected = await page
    .locator('button:has-text("4-7-8")')
    .evaluate((el) => el.className.includes("border-wellness-accent"));
  if (!selected) throw new Error("pattern selection did not apply");
  log("pattern switched to 4-7-8");

  // Pick Coherent (fast 10s cycles) + 3 cycles for a quick auto-complete.
  await page.click('button:has-text("Coherent")');
  await page.click('button:has-text("3")');
  await page.click("text=Start breathing");

  // Circle animates: the inhale label appears, then advances to exhale.
  await page.waitForFunction(() => document.body.textContent?.includes("Breathe in"), { timeout: 5000 });
  log("circle animating (Breathe in)");
  await page.waitForFunction(() => document.body.textContent?.includes("Breathe out"), { timeout: 10000 });
  log("phase advanced (Breathe out)");

  // After 3 coherent cycles (~30s) the end screen shows.
  await page.waitForFunction(() => document.body.textContent?.includes("Session complete"), { timeout: 45000 });
  log("auto-completed → Session complete screen");

  // End screen reports cycles + offers a new session.
  if (!(await page.locator("text=cycles of Coherent").count()))
    throw new Error("end screen missing cycle summary");
  await page.waitForSelector("text=New session", { timeout: 4000 });
  log("end screen shows cycle summary + New session");

  console.log("\n3.5 BREATHING EXIT-GATE CHECKS PASSED");
} catch (e) {
  console.error("\nFAILED:", e.message);
  process.exitCode = 1;
} finally {
  await browser.close();
}
