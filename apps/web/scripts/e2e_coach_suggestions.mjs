import { chromium } from "playwright";

const EMAIL = process.env.E2E_EMAIL;
const PASSWORD = process.env.E2E_PASSWORD;
const BASE_URL = process.env.E2E_BASE_URL || "http://localhost:3000";
const HEADLESS = (process.env.E2E_HEADLESS || "true").toLowerCase() !== "false";

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

async function main() {
  if (!EMAIL || !PASSWORD) {
    throw new Error(
      "Missing E2E credentials. Set E2E_EMAIL and E2E_PASSWORD in your environment."
    );
  }

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

  // Wait for suggestions and click first one (sidebar on desktop).
  await page.getByText("Try one of these").first().waitFor({ timeout: 60_000 });
  const suggestionButtons = page.locator("button").filter({ hasText: "PR Analysis" }).first();
  const fallbackFirstButton = page.locator("button").first();
  const buttonToClick = (await suggestionButtons.count()) > 0 ? suggestionButtons : fallbackFirstButton;
  const suggestionText = ((await buttonToClick.innerText()) || "").trim();
  await buttonToClick.click();

  // Wait for assistant response (after the user message we just sent).
  // The UI shows "Thinking..." while waiting.
  await page.getByText("Thinking...").waitFor({ state: "visible", timeout: 60_000 });
  await page.getByText("Thinking...").waitFor({ state: "hidden", timeout: 120_000 });

  // Give markdown rendering a beat.
  await sleep(500);

  // Grab the latest assistant message.
  const assistantMessage = page.locator(".prose").last();
  const responseText = ((await assistantMessage.innerText()) || "").trim();

  // Evidence is collapsible; expand if present and ensure there is at least one ISO date.
  const evidenceSummary = page.getByText("Evidence (expand)").last();
  const receiptsSummary = page.getByText("Receipts (expand)").last();
  if (await evidenceSummary.count()) {
    await evidenceSummary.click();
  } else if (await receiptsSummary.count()) {
    await receiptsSummary.click();
  }
  await sleep(250);
  const fullText = ((await page.locator(".prose").last().innerText()) || "").trim();
  const hasDateReceipt = /\b20\d{2}-\d{2}-\d{2}\b/.test(fullText);

  if (!responseText) {
    throw new Error(`No assistant response text after clicking suggestion: "${suggestionText}"`);
  }
  if (/AI Coach is not configured/i.test(responseText)) {
    throw new Error("AI coach not configured (missing OPENAI_API_KEY?)");
  }
  if (!hasDateReceipt) {
    throw new Error(
      `Assistant response did not include an ISO-date receipt.\nSuggestion: "${suggestionText}"\nResponse:\n${fullText}`
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

