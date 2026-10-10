// 3.2 reconnect check: kill backend → pill Disconnected → restart → Connected.
import { exec, spawn } from "node:child_process";
import { openSync } from "node:fs";
import { promisify } from "node:util";
import pw from "/Users/kaizerdewaswala/.npm/_npx/e41f203b7505f1fb/node_modules/playwright/index.js";
const { chromium } = pw;
const sh = promisify(exec);
const REPO = "/Users/kaizerdewaswala/Documents/HRV/stress-detection";
const BASE = "http://localhost:5173";
const email = `recon-${Date.now()}@example.com`;
const log = (...a) => console.log("•", ...a);
const pill = () =>
  page.evaluate(() => document.querySelector('[role="status"]')?.textContent || "");

const browser = await chromium.launch({ channel: "chrome" });
const page = await browser.newPage();

function startBackend() {
  // Detached + stdio→file + unref so this node process can exit cleanly
  // (an inherited/piped child would keep the event loop alive → hang).
  const out = openSync("/tmp/hrv_service.log", "a");
  const child = spawn("python3", ["scripts/run_service.py"], {
    cwd: REPO,
    detached: true,
    stdio: ["ignore", out, out],
  });
  child.unref();
}

try {
  await page.goto(`${BASE}/register`, { waitUntil: "networkidle" });
  await page.fill('input[type="email"]', email);
  await page.fill('input[type="password"]', "hunter2pw");
  await page.click('button[type="submit"]');
  await page.waitForURL("**/live", { timeout: 8000 });
  await page.waitForFunction(() => document.querySelector('[role="status"]')?.textContent?.includes("Connected"), { timeout: 8000 });
  log(`initial pill: ${(await pill()).trim()}`);

  // Kill the backend → should escalate to "Disconnected" (red) after the grace.
  await sh("pkill -f run_service.py").catch(() => {});
  await page.waitForFunction(
    () => document.querySelector('[role="status"]')?.textContent?.includes("Reconnecting"),
    { timeout: 8000 },
  );
  log(`after kill (immediate): ${(await pill()).trim()}`);
  await page.waitForFunction(
    () => document.querySelector('[role="status"]')?.textContent?.includes("Disconnected"),
    { timeout: 12000 },
  );
  log(`after grace: ${(await pill()).trim()}`);

  // Restart the backend.
  await startBackend();
  await page.waitForFunction(() => document.querySelector('[role="status"]')?.textContent?.includes("Connected"), { timeout: 20000 });
  log(`after restart: ${(await pill()).trim()}`);

  console.log("\n3.2 RECONNECT CHECK PASSED");
} catch (e) {
  console.error("\nFAILED:", e.message, "| pill:", (await pill()).trim());
  process.exitCode = 1;
} finally {
  await browser.close();
}
