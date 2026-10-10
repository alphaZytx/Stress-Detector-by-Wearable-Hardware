// 3.2 exit-gate browser check. Needs backend (csv_replay, raised speed) + vite up.
import pw from "/Users/kaizerdewaswala/.npm/_npx/e41f203b7505f1fb/node_modules/playwright/index.js";
const { chromium } = pw;

const BASE = "http://localhost:5173";
const API = "http://127.0.0.1:8010";
const email = `live-${Date.now()}@example.com`;
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

try {
  await page.goto(`${BASE}/register`, { waitUntil: "networkidle" });
  await page.fill('input[type="email"]', email);
  await page.fill('input[type="password"]', "hunter2pw");
  await page.click('button[type="submit"]');
  await page.waitForURL("**/live", { timeout: 8000 });
  log("registered → /live");

  // Connection pill connects.
  await page.waitForFunction(
    () => document.querySelector('[role="status"]')?.textContent?.includes("Connected"),
    { timeout: 8000 },
  );
  log("pill: Connected");

  // Gauges populate with a numeric BPM (not "-").
  await page.waitForFunction(
    () => {
      const els = [...document.querySelectorAll(".tnum")];
      return els.some((e) => /^\d{2,3}$/.test((e.textContent || "").trim()));
    },
    { timeout: 10000 },
  );
  log("gauges show numeric values");

  // Stress indicator flips to STRESS as the CSV transitions baseline→stress.
  await page.waitForFunction(
    () => document.body.textContent?.includes("STRESS"),
    { timeout: 20000 },
  );
  log("stress indicator reached STRESS");

  // Start recording via the dialog.
  await page.click("text=Start recording");
  await page.waitForSelector("text=Start a recording", { timeout: 4000 });
  await page.fill('input[placeholder="e.g. Morning baseline"]', "e2e-live");
  await page.click('button:has-text("Start"):not(:has-text("recording"))');
  await page.waitForFunction(
    () => document.body.textContent?.includes("Recording ·"),
    { timeout: 6000 },
  );
  log("recording started");

  // Verify the session exists via the API.
  const list = await (
    await fetch(`${API}/session/list`, {
      headers: { Authorization: `Bearer ${token}` },
    })
  ).json();
  if (!list.some((s) => s.user_label === "e2e-live"))
    throw new Error("started session not found in /session/list");
  log(`session persisted (${list.length} for this user)`);

  // Stop recording.
  await page.click("text=Stop recording");
  await page.waitForFunction(
    () => !document.body.textContent?.includes("Recording ·"),
    { timeout: 6000 },
  );
  log("recording stopped");

  console.log("\n3.2 LIVE EXIT-GATE CHECKS PASSED");
} catch (e) {
  console.error("\nFAILED:", e.message);
  process.exitCode = 1;
} finally {
  await browser.close();
}
