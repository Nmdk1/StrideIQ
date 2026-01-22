import { chromium } from "playwright";

const BASE_URL = process.env.E2E_BASE_URL || "http://localhost:3000";
const EMAIL = process.env.E2E_EMAIL;
const PASSWORD = process.env.E2E_PASSWORD;
const HEADLESS = (process.env.E2E_HEADLESS || "true").toLowerCase() !== "false";

const MOBILE_VIEWPORT = { width: 390, height: 844 }; // iPhone-ish

function hasCreds() {
  return Boolean(EMAIL && PASSWORD);
}

async function login(page) {
  if (!hasCreds()) return false;
  await page.goto(`${BASE_URL}/login`, { waitUntil: "domcontentloaded" });
  await page.getByLabel("Email").fill(EMAIL);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Login" }).click();
  await page.waitForURL("**/home", { timeout: 60_000 });
  return true;
}

async function checkOverflow(page) {
  return await page.evaluate(() => {
    const doc = document.documentElement;
    const body = document.body;
    const vw = window.innerWidth;
    const sw = Math.max(doc?.scrollWidth || 0, body?.scrollWidth || 0);
    const overflowPx = Math.max(0, sw - vw);
    const hasOverflow = overflowPx > 2;
    return { vw, sw, overflowPx, hasOverflow };
  });
}

async function checkCoachMobileSpecific(page) {
  const sidebar = page.locator('[data-testid="coach-suggestions-sidebar"]');
  const mobile = page.locator('[data-testid="coach-suggestions-mobile"]');

  const sidebarVisible = (await sidebar.count())
    ? await sidebar.evaluate((el) => window.getComputedStyle(el).display !== "none")
    : false;
  const mobileVisible = (await mobile.count())
    ? await mobile.evaluate((el) => window.getComputedStyle(el).display !== "none")
    : false;

  return { sidebarVisible, mobileVisible };
}

async function visitAndCheck(page, route) {
  await page.goto(`${BASE_URL}${route}`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(300);

  const overflow = await checkOverflow(page);
  const result = { route, overflow, notes: [] };

  if (route === "/coach") {
    const coach = await checkCoachMobileSpecific(page);
    if (coach.sidebarVisible) result.notes.push("Coach sidebar visible on mobile (should be hidden).");
    if (!coach.mobileVisible) result.notes.push("Coach mobile suggestions not visible (expected in empty state).");
  }

  return result;
}

async function main() {
  const browser = await chromium.launch({ headless: HEADLESS });

  const context = await browser.newContext({
    viewport: MOBILE_VIEWPORT,
    deviceScaleFactor: 2,
    isMobile: true,
    hasTouch: true,
    userAgent:
      "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
  });

  const page = await context.newPage();

  const authed = await login(page);

  const publicRoutes = ["/", "/mission", "/tools", "/privacy", "/terms", "/login", "/register"];
  const authedRoutes = [
    "/home",
    "/calendar",
    "/analytics",
    "/insights",
    "/coach",
    "/activities",
    "/training-load",
    "/trends",
    "/personal-bests",
    "/checkin",
    "/nutrition",
    "/compare",
    "/availability",
    "/settings",
    "/profile",
    "/plans/create",
    "/plans/preview",
    "/diagnostic",
  ];

  const routes = authed ? [...publicRoutes, ...authedRoutes] : publicRoutes;
  const failures = [];

  for (const route of routes) {
    const r = await visitAndCheck(page, route);
    if (r.overflow.hasOverflow || r.notes.length) failures.push(r);
  }

  if (failures.length) {
    console.error("MOBILE_E2E_FAILED");
    for (const f of failures) {
      console.error(
        `- ${f.route}: overflow=${f.overflow.hasOverflow ? `${f.overflow.overflowPx}px` : "none"} ${f.notes.join(" ")}`
      );
    }
    process.exit(1);
  }

  console.log("MOBILE_E2E_OK");
  console.log(`Checked ${routes.length} routes (${authed ? "authed+public" : "public-only"}).`);
  await browser.close();
}

main().catch((e) => {
  console.error("MOBILE_E2E_FAILED");
  console.error(e);
  process.exit(1);
});

