// Screenshot helper for the visual redesign pass (run manually, not part of pnpm test).
// Usage: node tests/shoot.mjs <name> [theme]   e.g. node tests/shoot.mjs breathing dark
import pw from "/Users/kaizerdewaswala/.npm/_npx/e41f203b7505f1fb/node_modules/playwright/index.js";
const { chromium } = pw;
const BASE = "http://localhost:5173";
const OUT = "/tmp/shots";
const theme = process.argv[3] === "dark" ? "dark" : "light";

const browser = await chromium.launch({ channel: "chrome" });
const ctx = await browser.newContext({
  viewport: { width: 1440, height: 960 },
  deviceScaleFactor: 2,
  colorScheme: theme === "dark" ? "dark" : "light",
});
const page = await ctx.newPage();
const email = `shot-${Date.now()}@example.com`;
const shot = (n) => page.screenshot({ path: `${OUT}/${n}-${theme}.png` });
const sleep = (ms) => page.waitForTimeout(ms);

// register + set theme
await page.goto(`${BASE}/register`, { waitUntil: "networkidle" });
await page.fill('input[type="email"]', email);
await page.fill('input[type="password"]', "hunter2pw");
await page.click('button[type="submit"]');
await page.waitForURL("**/live", { timeout: 8000 });
await page.evaluate((t) => {
  const s = JSON.parse(localStorage.getItem("stress-settings") || '{"state":{},"version":0}');
  s.state.theme = t;
  localStorage.setItem("stress-settings", JSON.stringify(s));
}, theme);
await page.reload({ waitUntil: "networkidle" });
await page.waitForFunction(() => document.querySelector('[role="status"]')?.textContent?.includes("Connected"), { timeout: 8000 }).catch(() => {});

async function breathing() {
  await page.goto(`${BASE}/breathing`, { waitUntil: "networkidle" });
  await sleep(400);
  await shot("breathing-setup");
  await page.click("text=Start breathing");
  await sleep(5400); // catch the held-full state (box: inhale 4s + into hold)
  await shot("breathing-running");
}
async function live() {
  await page.goto(`${BASE}/live`, { waitUntil: "networkidle" });
  await sleep(16000); // catch baseline→stress transition (raise replay speed first)
  await shot("live");
  // Collapse the sidebar to capture the rail state too.
  await page.click('[aria-label="Collapse menu"]').catch(() => {});
  await sleep(500);
  await shot("live-collapsed");
}
async function settings() {
  await page.goto(`${BASE}/settings`, { waitUntil: "networkidle" });
  await sleep(600);
  await shot("settings");
}
async function calibration() {
  await page.goto(`${BASE}/calibration`, { waitUntil: "networkidle" });
  await sleep(500);
  await shot("calibration-welcome");
  await page.click("text=Begin");
  await sleep(1500);
  await shot("calibration-capture");
}
async function history() {
  await page.goto(`${BASE}/history`, { waitUntil: "networkidle" });
  await sleep(500);
  await shot("history-empty");
}
async function login() {
  await ctx.clearCookies();
  await page.evaluate(() => localStorage.removeItem("stress-auth"));
  await page.goto(`${BASE}/login`, { waitUntil: "networkidle" });
  await sleep(400);
  await shot("login");
}

const target = process.argv[2] || "all";
const map = { breathing, live, settings, calibration, history, login };
if (target === "all") {
  for (const f of Object.values(map)) await f();
} else if (map[target]) {
  await map[target]();
}
console.log(`shot ${target} (${theme}) → ${OUT}`);
await browser.close();
