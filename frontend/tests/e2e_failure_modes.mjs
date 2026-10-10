// 4.3.b/c failure-mode + bug-sweep probe. Needs backend + vite up.
//   node tests/e2e_failure_modes.mjs
import pw from "/Users/kaizerdewaswala/.npm/_npx/e41f203b7505f1fb/node_modules/playwright/index.js";
const { chromium } = pw;
const BASE = "http://localhost:5173";
const email = `fail-${Date.now()}@example.com`;
const log = (...a) => console.log("•", ...a);
const browser = await chromium.launch({ channel: "chrome" });
const page = await browser.newPage();

try {
  // Route gating: unauthenticated /live → /login.
  await page.goto(`${BASE}/live`, { waitUntil: "networkidle" });
  await page.waitForURL("**/login", { timeout: 6000 });
  log("unauthenticated /live → redirected to /login");

  // Register a fresh user (no sessions, no calibration).
  await page.goto(`${BASE}/register`, { waitUntil: "networkidle" });
  await page.fill('input[type="email"]', email);
  await page.fill('input[type="password"]', "hunter2pw");
  await page.click('button[type="submit"]');
  await page.waitForURL("**/live", { timeout: 8000 });
  log("registered fresh user");

  // Empty state: /history with no sessions.
  await page.goto(`${BASE}/history`, { waitUntil: "networkidle" });
  await page.waitForFunction(() => /No sessions yet/i.test(document.body.textContent || ""), { timeout: 6000 });
  log("/history shows empty state for new user");

  // Empty state: /settings shows Not calibrated.
  await page.goto(`${BASE}/settings`, { waitUntil: "networkidle" });
  await page.waitForFunction(() => /Not calibrated/i.test(document.body.textContent || ""), { timeout: 6000 });
  log("/settings shows 'Not calibrated'");

  // Nonexistent session detail → graceful error, no crash.
  await page.goto(`${BASE}/history/does-not-exist-123`, { waitUntil: "networkidle" });
  await page.waitForFunction(() => /Failed to load session/i.test(document.body.textContent || ""), { timeout: 8000 });
  log("/history/:bad-id → 'Failed to load session.' (graceful)");

  // Expired/invalid token → ProtectedRoute kicks back to /login.
  await page.evaluate(() => {
    const expired = { state: { token: "bad.token.value", user: null }, version: 0 };
    localStorage.setItem("stress-auth", JSON.stringify(expired));
  });
  await page.goto(`${BASE}/live`, { waitUntil: "networkidle" });
  await page.waitForURL("**/login", { timeout: 6000 });
  log("invalid/expired token → redirected to /login");

  console.log("\n4.3 FAILURE-MODE PROBES PASSED");
} catch (e) {
  console.error("\nFAILED:", e.message);
  process.exitCode = 1;
} finally {
  await browser.close();
}
