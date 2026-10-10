// 4.3.a full-stack smoke. Needs backend (csv_replay, speed≈10) + vite dev up.
//   Backend:  (set input.csv_replay.speed: 10 in config/service.yaml) python3 scripts/run_service.py
//   Frontend: cd frontend && pnpm dev
//   Run:      node tests/e2e_fullstack.mjs
import pw from "/Users/kaizerdewaswala/.npm/_npx/e41f203b7505f1fb/node_modules/playwright/index.js";
const { chromium } = pw;
const BASE = "http://localhost:5173";
const API = "http://127.0.0.1:8010";
const email = `full-${Date.now()}@example.com`;
const log = (...a) => console.log("•", ...a);

const browser = await chromium.launch({ channel: "chrome" });
const page = await browser.newPage();
let token = "";
page.on("response", async (r) => {
  if (r.url().endsWith("/auth/register")) {
    try { token = (await r.json()).access_token; } catch {}
  }
});
const authed = (p) => fetch(`${API}${p}`, { headers: { Authorization: `Bearer ${token}` } });

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

try {
  // 3. Register a new user → lands on /live.
  await page.goto(`${BASE}/register`, { waitUntil: "networkidle" });
  await page.fill('input[type="email"]', email);
  await page.fill('input[type="password"]', "hunter2pw");
  await page.click('button[type="submit"]');
  await page.waitForURL("**/live", { timeout: 8000 });
  log("registered new user → /live");

  // 4. Calibration (dev short capture).
  await page.goto(`${BASE}/calibration?dev_seconds=5`, { waitUntil: "networkidle" });
  await page.click("text=Begin");
  await page.waitForSelector("text=Your baseline", { timeout: 20000 });
  await page.click("text=Save baseline");
  await page.waitForSelector("text=Calibration saved", { timeout: 8000 });
  const cal = await (await authed("/calibration")).json();
  if (!cal.calibrated) throw new Error("calibration not stored");
  log("calibration captured + saved");

  // 5–7. Start recording, let ≥6 predictions flow, stop.
  await page.goto(`${BASE}/live`, { waitUntil: "networkidle" });
  await page.waitForFunction(() => document.querySelector('[role="status"]')?.textContent?.includes("Connected"), { timeout: 8000 });
  await startRecording("fullstack-session");
  await page.waitForTimeout(9000); // speed≈10 → first emit ~2.9s, then 1 per ~0.5s
  await stopRecording();
  log("recorded a session");

  // Confirm ≥6 predictions persisted for the session.
  const summaries = await (await authed("/session/summaries")).json();
  const sess = summaries.find((s) => s.user_label === "fullstack-session");
  if (!sess) throw new Error("session missing from summaries");
  const exp = await (await authed(`/session/${sess.session_id}/export?format=json`)).json();
  if (exp.predictions.length < 6) throw new Error(`only ${exp.predictions.length} predictions (<6)`);
  log(`session has ${exp.predictions.length} predictions, dominant=${sess.dominant_state}`);

  // 8. /history shows the session.
  await page.click('a[href="/history"]');
  await page.waitForSelector("text=fullstack-session", { timeout: 6000 });
  log("session appears in /history");

  // 9. Detail view: timeline + stat cards render.
  await page.click("text=fullstack-session");
  await page.waitForURL("**/history/**", { timeout: 6000 });
  await page.waitForFunction(
    () => /Stress timeline/.test(document.body.textContent || "") &&
          /Avg|Average|Peak|P\(stress\)/.test(document.body.textContent || ""),
    { timeout: 8000 },
  );
  log("detail view: timeline + stat cards rendered");

  // 10. Add an annotation.
  await page.click("text=Add annotation");
  await page.waitForSelector('input[placeholder="e.g. felt anxious"]', { timeout: 4000 });
  await page.fill('input[placeholder="e.g. felt anxious"]', "fullstack-marker");
  await page.click('button:has-text("Save annotation")');
  await page.waitForFunction(() => document.body.textContent?.includes("fullstack-marker"), { timeout: 6000 });
  log("annotation added + visible");

  // 11. Export the session JSON.
  await page.click('a[href="/history"]');
  await page.waitForSelector("text=fullstack-session", { timeout: 6000 });
  await page.locator('button[aria-label="Session actions"]').first().click();
  const [dl] = await Promise.all([
    page.waitForEvent("download", { timeout: 8000 }),
    page.click("text=Export JSON"),
  ]);
  log(`exported JSON: ${dl.suggestedFilename()}`);

  // 12. Logout → back to /login.
  await page.click('[aria-label="Log out"]');
  await page.waitForURL("**/login", { timeout: 6000 });
  log("logged out → /login");

  console.log("\n4.3 FULL-STACK E2E PASSED");
} catch (e) {
  console.error("\nFAILED:", e.message);
  process.exitCode = 1;
} finally {
  await browser.close();
}
