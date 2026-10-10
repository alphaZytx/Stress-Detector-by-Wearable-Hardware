// Standalone Playwright smoke test for the 3.1 exit gate (run manually).
// Requires: backend on :8010, vite dev on :5173.
import pw from "/Users/kaizerdewaswala/.npm/_npx/e41f203b7505f1fb/node_modules/playwright/index.js";
const { chromium } = pw;

const BASE = "http://localhost:5173";
const email = `e2e-${Date.now()}@example.com`;
const log = (...a) => console.log("•", ...a);

const browser = await chromium.launch({ channel: "chrome" });
const page = await browser.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));

try {
  // 1. Unauthenticated root redirects to /login.
  await page.goto(BASE, { waitUntil: "networkidle" });
  if (!page.url().includes("/login")) throw new Error(`expected /login, got ${page.url()}`);
  log("root → /login redirect OK");

  // 2. Go to register, create a user → redirect to /live.
  await page.goto(`${BASE}/register`, { waitUntil: "networkidle" });
  await page.fill('input[type="email"]', email);
  await page.fill('input[type="password"]', "hunter2pw");
  await page.click('button[type="submit"]');
  await page.waitForURL("**/live", { timeout: 8000 });
  log("register → /live redirect OK");

  // 3. Connection pill renders a known status.
  await page.waitForTimeout(1500);
  const pill = await page.locator('[role="status"]').first().textContent();
  const known = ["Connected", "Connecting", "Reconnecting", "Disconnected", "Demo"];
  if (!known.some((k) => (pill || "").includes(k)))
    throw new Error(`unexpected pill text: ${pill}`);
  log(`connection pill shows: "${pill?.trim()}"`);

  // 4. Placeholder text present.
  const body = await page.locator("body").textContent();
  if (!body?.includes("coming in 3.2")) throw new Error("Live placeholder missing");
  log("Live placeholder OK");

  // 5. Logout returns to /login.
  await page.click('button[aria-label="Log out"]');
  await page.waitForURL("**/login", { timeout: 8000 });
  log("logout → /login OK");

  // 6. Protected route now bounces to /login.
  await page.goto(`${BASE}/history`, { waitUntil: "networkidle" });
  if (!page.url().includes("/login")) throw new Error("protected route not gated");
  log("protected route gating OK");

  if (errors.length) throw new Error(`page errors: ${errors.join("; ")}`);
  console.log("\nALL 3.1 EXIT-GATE CHECKS PASSED");
} catch (e) {
  console.error("\nFAILED:", e.message);
  if (errors.length) console.error("page errors:", errors);
  process.exitCode = 1;
} finally {
  await browser.close();
}
