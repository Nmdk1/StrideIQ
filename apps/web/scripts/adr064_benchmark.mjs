/**
 * ADR-064 — Browser Benchmark Evidence Capture
 *
 * Automates the Gate 1 evidence collection:
 * 1. Navigates to /spike/rsi-rendering
 * 2. Waits for both charts to render
 * 3. Takes visual comparison screenshot
 * 4. Runs the benchmark harness
 * 5. Captures all numeric metrics + sync proof
 * 6. Takes results screenshot
 * 7. Outputs JSON evidence file
 *
 * Usage:
 *   npx playwright install chromium   (one-time)
 *   node scripts/adr064_benchmark.mjs
 *
 * Prerequisites: dev server running on localhost:3000
 */

import { chromium } from 'playwright';
import { writeFileSync, mkdirSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const EVIDENCE_DIR = join(__dirname, '..', 'evidence', 'adr-064');
const BASE_URL = process.env.BASE_URL || 'http://localhost:3000';
const PAGE_URL = `${BASE_URL}/spike/rsi-rendering`;

mkdirSync(EVIDENCE_DIR, { recursive: true });

async function run() {
  console.log('╔══════════════════════════════════════════════╗');
  console.log('║  ADR-064 Browser Benchmark Evidence Capture  ║');
  console.log('╚══════════════════════════════════════════════╝');
  console.log();

  const browser = await chromium.launch({ headless: false });

  // ── Desktop viewport ──
  console.log('▸ Desktop viewport (1280×800)');
  const desktopCtx = await browser.newContext({
    viewport: { width: 1280, height: 800 },
    deviceScaleFactor: 1,
  });
  const desktopPage = await desktopCtx.newPage();
  const desktopResults = await captureEvidence(desktopPage, 'desktop');
  await desktopCtx.close();

  // ── Mobile viewport ──
  console.log('\n▸ Mobile viewport (375×812, DPR 3)');
  const mobileCtx = await browser.newContext({
    viewport: { width: 375, height: 812 },
    deviceScaleFactor: 3,
    isMobile: true,
    hasTouch: true,
  });
  const mobilePage = await mobileCtx.newPage();
  const mobileResults = await captureEvidence(mobilePage, 'mobile');
  await mobileCtx.close();

  await browser.close();

  // ── Evidence summary ──
  const evidence = {
    timestamp: new Date().toISOString(),
    page: PAGE_URL,
    desktop: desktopResults,
    mobile: mobileResults,
  };

  const evidencePath = join(EVIDENCE_DIR, 'benchmark-results.json');
  writeFileSync(evidencePath, JSON.stringify(evidence, null, 2));

  console.log('\n╔══════════════════════════════════════════════╗');
  console.log('║  EVIDENCE SUMMARY                            ║');
  console.log('╚══════════════════════════════════════════════╝');
  console.log();
  printResults('Desktop', desktopResults);
  printResults('Mobile', mobileResults);
  console.log(`\nEvidence saved to: ${EVIDENCE_DIR}/`);
  console.log('  benchmark-results.json');
  console.log('  desktop-charts.png');
  console.log('  desktop-benchmark.png');
  console.log('  mobile-charts.png');
  console.log('  mobile-benchmark.png');
}

async function captureEvidence(page, label) {
  // Navigate and wait for page to fully load
  console.log(`  Navigating to ${PAGE_URL}...`);
  await page.goto(PAGE_URL, { waitUntil: 'networkidle', timeout: 120000 });

  // Wait for both charts to render (look for Recharts containers)
  console.log('  Waiting for charts to render...');
  await page.waitForSelector('.recharts-wrapper', { timeout: 30000 });
  await page.waitForTimeout(3000); // extra settle time for Canvas draw

  // Screenshot 1: Visual comparison of both charts
  const chartsPath = join(EVIDENCE_DIR, `${label}-charts.png`);
  await page.screenshot({ path: chartsPath, fullPage: false });
  console.log(`  Screenshot: ${label}-charts.png`);

  // Collect Option A/B metrics from the page header
  const headerMetrics = await page.evaluate(() => {
    const cards = document.querySelectorAll('.grid > div');
    const metrics = {};
    cards.forEach(card => {
      const text = card.textContent || '';
      if (text.includes('Option A')) {
        const renderMatch = text.match(/(\d+(?:\.\d+)?)\s*ms/);
        const domMatch = text.match(/(\d+)\s*nodes/);
        metrics.optionA = {
          renderMs: renderMatch ? parseFloat(renderMatch[1]) : null,
          domNodes: domMatch ? parseInt(domMatch[1]) : null,
        };
      }
      if (text.includes('Option B')) {
        const renderMatch = text.match(/(\d+(?:\.\d+)?)\s*ms/);
        const domMatch = text.match(/(\d+)\s*nodes/);
        metrics.optionB = {
          renderMs: renderMatch ? parseFloat(renderMatch[1]) : null,
          domNodes: domMatch ? parseInt(domMatch[1]) : null,
        };
      }
    });
    return metrics;
  });
  console.log('  Header metrics:', JSON.stringify(headerMetrics));

  // Scroll to benchmark panel and run it
  console.log('  Scrolling to benchmark panel...');
  const benchmarkBtn = await page.waitForSelector('button:has-text("Run Benchmark")', { timeout: 10000 });
  await benchmarkBtn.scrollIntoViewIfNeeded();
  await page.waitForTimeout(500);

  console.log('  Running benchmark...');
  await benchmarkBtn.click();

  // Wait for benchmark to complete (button text changes back from "Running...")
  await page.waitForFunction(() => {
    const btn = document.querySelector('button');
    if (!btn) return false;
    const buttons = [...document.querySelectorAll('button')];
    const benchBtn = buttons.find(b => b.textContent?.includes('Run Benchmark') || b.textContent?.includes('Running'));
    return benchBtn && benchBtn.textContent?.includes('Run Benchmark');
  }, { timeout: 60000 });

  await page.waitForTimeout(1000); // settle

  // Screenshot 2: Benchmark results
  const benchPath = join(EVIDENCE_DIR, `${label}-benchmark.png`);
  await page.screenshot({ path: benchPath, fullPage: true });
  console.log(`  Screenshot: ${label}-benchmark.png`);

  // Extract benchmark results from the DOM
  const benchResults = await page.evaluate(() => {
    const results = {};

    // Find metric cards (Initial Render, Tooltip p95, Resize p95)
    const metricCards = document.querySelectorAll('.bg-slate-800.rounded-lg.p-3');
    metricCards.forEach(card => {
      const label = card.querySelector('.text-slate-500')?.textContent || '';
      const value = card.querySelector('.font-mono')?.textContent || '';
      if (label.includes('Initial Render')) results.initialRenderMs = value;
      if (label.includes('Tooltip p95')) results.tooltipP95Ms = value;
      if (label.includes('Resize p95')) results.resizeP95Ms = value;
    });

    // Find sync proof
    const syncSection = document.querySelector('h3');
    if (syncSection && syncSection.textContent?.includes('Synchronization')) {
      const parent = syncSection.parentElement;
      const statusItems = parent?.querySelectorAll('.flex.items-center.gap-2 span') || [];
      statusItems.forEach(span => {
        const text = span.textContent || '';
        if (text.includes('Resize alignment')) results.resizeAlignment = text;
        if (text.includes('DPR scaling')) results.dprScaling = text;
      });

      const details = parent?.querySelectorAll('.font-mono') || [];
      results.syncDetails = [];
      details.forEach(d => {
        if (d.textContent && d.textContent.length > 10) {
          results.syncDetails.push(d.textContent);
        }
      });
    }

    return results;
  });

  console.log('  Benchmark results:', JSON.stringify(benchResults, null, 2));
  return { headerMetrics, benchResults };
}

function printResults(label, results) {
  console.log(`\n  ${label}:`);
  if (results.headerMetrics?.optionA) {
    console.log(`    Option A: ${results.headerMetrics.optionA.renderMs}ms render, ${results.headerMetrics.optionA.domNodes} DOM nodes`);
  }
  if (results.headerMetrics?.optionB) {
    console.log(`    Option B: ${results.headerMetrics.optionB.renderMs}ms render, ${results.headerMetrics.optionB.domNodes} DOM nodes`);
  }
  const b = results.benchResults || {};
  console.log(`    Initial Render: ${b.initialRenderMs || 'N/A'}`);
  console.log(`    Tooltip p95:    ${b.tooltipP95Ms || 'N/A'}`);
  console.log(`    Resize p95:     ${b.resizeP95Ms || 'N/A'}`);
  console.log(`    Resize align:   ${b.resizeAlignment || 'N/A'}`);
  console.log(`    DPR scaling:    ${b.dprScaling || 'N/A'}`);
  if (b.syncDetails?.length) {
    b.syncDetails.forEach(d => console.log(`    Sync detail:    ${d}`));
  }
}

run().catch(err => {
  console.error('Benchmark failed:', err);
  process.exit(1);
});
