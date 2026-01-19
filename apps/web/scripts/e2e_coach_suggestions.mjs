import { chromium } from "playwright";

const EMAIL = process.env.E2E_EMAIL || "mbshaf@gmail.com";
const PASSWORD = process.env.E2E_PASSWORD || "StrideIQLocal!2026";
const BASE_URL = process.env.E2E_BASE_URL || "http://localhost:3000";
const HEADLESS = (process.env.E2E_HEADLESS || "true").toLowerCase() !== "false";

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

async function main() {
  const browser = await chromium.launch({ headless: HEADLESS });
  const page = await browser.newPage();

  // Login
  await page.goto(`${BASE_URL}/login`, { waitUntil: "domcontentloaded" });
  await page.getByLabel("Email").fill(EMAIL);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Login" }).click();
  await page.waitForURL("**/home", { timeout: 60_000 });

  // Navigate to Coach
  await page.goto(`${BASE_URL}/coach`, { waitUntil: "domcontentloaded" });

  // Wait for suggestions and click first one.
  const suggestionsWrapper = page.getByText("Suggested questions:").locator("..");
  const suggestionButtons = suggestionsWrapper.locator("button");
  await suggestionButtons.first().waitFor({ timeout: 60_000 });

  const suggestionText = (await suggestionButtons.first().innerText()).trim();
  await suggestionButtons.first().click();

  // Wait for assistant response (after the user message we just sent).
  // The UI shows "Thinking..." while waiting.
  await page.getByText("Thinking...").waitFor({ state: "visible", timeout: 60_000 });
  await page.getByText("Thinking...").waitFor({ state: "hidden", timeout: 120_000 });

  // Give markdown rendering a beat.
  await sleep(500);

  // Grab the latest assistant message.
  const assistantMessage = page.locator(".prose").last();
  const responseText = ((await assistantMessage.innerText()) || "").trim();

  const hasCitation = /\b20\d{2}-\d{2}-\d{2}\b/.test(responseText) &&
    /\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/i.test(responseText);

  if (!responseText) {
    throw new Error(`No assistant response text after clicking suggestion: "${suggestionText}"`);
  }
  if (/AI Coach is not configured/i.test(responseText)) {
    throw new Error("AI coach not configured (missing OPENAI_API_KEY?)");
  }
  if (!hasCitation) {
    throw new Error(
      `Assistant response did not include a date + UUID citation.\nSuggestion: "${suggestionText}"\nResponse:\n${responseText}`
    );
  }

  console.log("E2E_OK");
  console.log("SUGGESTION:", suggestionText);
  console.log("RESPONSE_PREVIEW:", responseText.slice(0, 800));

  await browser.close();
}

main().catch((e) => {
  console.error("E2E_FAILED");
  console.error(e);
  process.exit(1);
});

