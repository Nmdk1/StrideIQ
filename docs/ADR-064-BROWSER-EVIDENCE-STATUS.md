# ADR-064 Browser Evidence Collection — Status Report

**Date:** 2026-02-14
**Agent:** Current session
**Task:** Navigate to spike page and capture browser benchmark evidence

---

## Situation

ADR-064 is in DRAFT status awaiting browser-level verification (Section A.5). The spike page at `/spike/rsi-rendering` includes an interactive `Benchmark.tsx` component that measures:

1. **Initial render time** — mount to first paint with gradient
2. **Tooltip p95 latency** — 95th percentile over 100 synthetic mousemove events
3. **Resize p95 latency** — 95th percentile over 20 resize cycles
4. **Canvas/SVG synchronization proof** — pixel alignment verification at current DPR

The spike implementation is complete and ready for testing. All code analysis and offline benchmarks (Node.js) are complete. What remains is **live browser execution** to capture real-world performance data.

---

## Blocker: Browser Automation Tools Not Available

The user requested browser navigation and screenshot capture using "cursor-ide-browser tools" mentioned in system reminders. However:

- **MCP browser tools are not configured** in the current environment
- Attempts to call `CallMcpTool` with browser tools return "MCP file system options are required"
- `ListMcpResources` returns no available resources
- No browser automation libraries (Playwright, Puppeteer) are accessible via Shell

**Root cause:** The browser automation capability mentioned in system reminders is not actually provisioned in this Cursor environment.

---

## What I've Done Instead

Since browser automation is unavailable, I've created comprehensive guidance for manual evidence collection:

### 1. Evidence Collection Protocol
**File:** `docs/ADR-064-BROWSER-EVIDENCE-COLLECTION-PROTOCOL.md`

This document provides:
- Step-by-step instructions for navigating to the spike page
- Exact metrics to record from the page and benchmark
- Screenshot requirements
- Expected values for validation
- Troubleshooting guide for common issues
- Template for recording results

### 2. Code Analysis
I've read and analyzed:
- `page.tsx` — main spike page with side-by-side chart comparison
- `OptionA.tsx` — Recharts ReferenceArea implementation
- `OptionB.tsx` — Canvas 2D + SVG hybrid implementation
- `Benchmark.tsx` — runtime measurement harness
- `ADR-064` — current draft status and open items

### 3. Environment Check
- Confirmed Next.js server is listening on port 3000 (via netstat)
- Verified spike page files exist in `apps/web/app/spike/rsi-rendering/`
- Checked for `Benchmark.tsx` integration in main page (confirmed)

---

## What the Founder Needs to Do

To complete ADR-064 browser verification:

### Option 1: Manual Evidence Collection (Recommended)
1. Open browser and navigate to `http://localhost:3000/spike/rsi-rendering`
2. Follow the protocol in `ADR-064-BROWSER-EVIDENCE-COLLECTION-PROTOCOL.md`
3. Record the benchmark results manually
4. Report back the metrics so I can update ADR-064 Section A.5

### Option 2: Configure Browser Automation (Future Sessions)
If browser automation is desired for future spikes:
1. Install and configure the MCP browser server in Cursor settings
2. Verify with `ListMcpResources` or attempt browser tool calls
3. Once working, browser tasks can be fully automated

### Option 3: Playwright Script (Alternative)
I can write a Playwright script that:
- Navigates to the spike page
- Waits for charts to render
- Clicks the benchmark button
- Extracts the results from the DOM
- Takes screenshots
- Outputs a structured JSON result

This would run via `npm run` command and bypass the need for browser tool integration.

---

## Next Steps

**If founder prefers Option 1 (manual):**
- Founder runs the spike page and collects evidence using the protocol
- Reports back numeric values + observations
- I update ADR-064 Section A.5 with browser-level results
- ADR-064 status changes from DRAFT to APPROVED (if metrics pass)

**If founder prefers Option 3 (Playwright script):**
- I write `apps/web/scripts/adr-064-benchmark.mjs` (Playwright script)
- Founder runs `npm run adr-064:benchmark` (add to package.json)
- Script outputs `docs/adr/ADR-064-evidence/browser-results.json`
- I parse and integrate into ADR-064

**If founder wants to investigate browser tool availability:**
- Check Cursor settings for MCP browser server configuration
- Verify if it needs to be manually enabled or installed
- Test with a simple navigation task

---

## Key Observations from Code Analysis

While I can't see the live page, I can confirm from the code:

### Benchmark Implementation Quality
- **Accurate measurement:** Uses `performance.now()` for precise timing
- **Statistical rigor:** p95 computed from 100-sample distributions
- **Comprehensive sync proof:** Checks logical width alignment, DPR scaling, and position offset
- **Conservative thresholds:** 2px tolerance for alignment (accounts for rounding/subpixel)

### Expected Performance
Based on ADR-064 offline benchmarks (Node.js):
- Initial render: ~16ms (desktop), well under 2,000ms mobile target
- Tooltip p95: < 8ms (sub-frame latency), 4x headroom vs 30fps
- Resize p95: < 1ms (gradient redraw), 100x headroom vs 100ms target
- Synchronization: Should PASS at all tested DPRs (1x, 1.25x, 1.5x, 2x, 3x)

Browser measurements will be higher due to real DOM overhead, but should still pass comfortably.

### Visual Quality
From code structure:
- **Option A** batches similar effort values into discrete ReferenceArea bands (threshold=0.02 → ~29 bands)
- **Option B** draws one vertical `fillRect` per pixel column (~800-1200 px wide chart)
- Visual block-stepping in Option A is mathematically guaranteed (28px average band width)
- Option B smoothness is guaranteed by per-pixel rendering

---

## Files Modified/Created

1. **Created:** `docs/ADR-064-BROWSER-EVIDENCE-COLLECTION-PROTOCOL.md`
   - Comprehensive manual testing guide
   - Evidence template
   - Expected values for validation

2. **Created:** `docs/ADR-064-BROWSER-EVIDENCE-STATUS.md` (this file)
   - Status report for founder
   - Options analysis
   - Next steps

---

## Recommendation

**Manual collection (Option 1) is fastest path to ADR-064 approval.** The protocol is comprehensive, the spike is ready, and the measurements take < 5 minutes to capture. Once evidence is reported, I can:

1. Update ADR-064 Section A.5 with actual browser measurements
2. Change status from DRAFT → APPROVED (if metrics pass)
3. Archive screenshots in `docs/adr/ADR-064-evidence/`
4. Close the "browser-level verification" open item

If the founder anticipates many future spike benchmarks, investing in Playwright automation (Option 3) would pay dividends.

---

**Awaiting founder input on preferred approach.**
