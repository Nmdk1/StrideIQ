# ADR-064 Browser Evidence Collection Protocol

**Date:** 2026-02-14
**Purpose:** Capture live browser benchmark data to complete ADR-064 Section A.5 verification
**Spike URL:** `http://localhost:3000/spike/rsi-rendering` (or port 3077 if that's the active server)

---

## Prerequisites

1. **Start the Next.js dev server** (if not already running):
   ```bash
   cd apps/web
   npm run dev
   ```
   
2. **Wait for compilation** — first visit to `/spike/rsi-rendering` may take 30-60s for Next.js on-demand compilation

3. **Use a modern browser** — Chrome/Edge (Chromium) recommended for accurate performance measurement

---

## Evidence Collection Steps

### Step 1: Initial Page Load and Visual Assessment

1. Navigate to `http://localhost:3000/spike/rsi-rendering` (or port 3077)
2. Wait 10-15 seconds for both charts to fully render
3. **Record from the metrics cards at top of page:**
   ```
   Option A: Recharts ReferenceArea
   - Render time: _____ ms
   - DOM nodes: _____ nodes
   
   Option B: Canvas 2D Hybrid
   - Render time: _____ ms
   - DOM nodes: _____ nodes
   ```

4. **Visual Quality Assessment:**
   - [ ] Option A (top chart): Visible block-stepping/banding in gradient? (YES/NO)
   - [ ] Option B (bottom chart): Smooth continuous gradient? (YES/NO)
   - [ ] Are the blue pace line and red HR line identical in both charts? (YES/NO)
   - [ ] Is the gray elevation fill identical in both charts? (YES/NO)

5. **Take Screenshot 1:** Full page view showing both charts and metrics cards

---

### Step 2: Runtime Benchmark Execution

1. Scroll down to the **"Runtime Benchmark (Option B)"** section
2. Click the **"Run Benchmark"** button
3. Wait ~15-20 seconds (progress indicator will show)
4. **Record the benchmark results:**

   ```
   INITIAL RENDER
   - Initial render time: _____ ms
   - Target: < 2000ms
   - Status: PASS / FAIL
   
   TOOLTIP INTERACTION (p95)
   - Tooltip p95 latency: _____ ms
   - Target: < 33ms (30fps)
   - Status: PASS / FAIL
   
   RESIZE PERFORMANCE (p95)
   - Resize p95 latency: _____ ms
   - Target: < 100ms
   - Status: PASS / FAIL
   
   CANVAS/SVG SYNCHRONIZATION PROOF
   - Resize alignment: PASS / FAIL
   - DPR scaling: PASS / FAIL
   - Detail message (if any): _____________________________________
   ```

5. **Take Screenshot 2:** Benchmark results panel showing all metrics

---

### Step 3: Additional Observations

**Device Info:**
- Browser: _____________________ (e.g., Chrome 131, Edge 130)
- Device Pixel Ratio: _____ (visible in benchmark results or browser DevTools)
- Viewport width: _____ px (visible in benchmark results)
- OS: _____________________ (Windows 11, macOS 14, etc.)

**Performance Notes:**
- Was there any visible jank during tooltip hover? (YES/NO)
- Did the benchmark complete without errors? (YES/NO)
- Any console errors or warnings? (YES/NO — if yes, paste below)

---

## Expected Results (for validation)

Based on ADR-064 Appendix A offline analysis:

| Metric | Expected | Margin |
|--------|----------|--------|
| Initial render | < 100ms | Wide headroom (offline: ~16ms) |
| Tooltip p95 | < 10ms | 3x headroom vs 30fps target |
| Resize p95 | < 5ms | 20x headroom vs 100ms target |
| Synchronization | ALL PASS | Canvas and SVG must align at all DPRs |

**If any metric significantly exceeds expected values** (e.g., initial render > 500ms, tooltip > 50ms), note environmental factors:
- Is the CPU throttled or under heavy load?
- Is the browser DevTools open (can affect performance)?
- Is this a low-end device or old browser version?

---

## Post-Collection Actions

Once all evidence is captured:

1. **Update ADR-064** Section A.5 with actual browser measurements
2. **Archive screenshots** in `docs/adr/ADR-064-evidence/` (create directory if needed)
3. **Report findings** to founder for approval
4. **If all metrics PASS** → ADR-064 status changes from DRAFT to APPROVED
5. **If any metric FAILS** → investigate root cause, optimize, re-benchmark

---

## Troubleshooting

### "Page not found" or 404 error
- Ensure Next.js dev server is running (`npm run dev` in `apps/web/`)
- Check terminal output for compilation errors
- Try `http://localhost:3001` or `http://localhost:3077` (different port)

### Charts don't render or show "Rendering..." forever
- Open browser DevTools Console (F12)
- Check for JavaScript errors (paste them in evidence)
- Verify `recharts` dependency is installed (`npm install` in `apps/web/`)

### Benchmark button doesn't appear
- The page structure may have changed — check `apps/web/app/spike/rsi-rendering/page.tsx`
- The benchmark component may be in a separate file — look for `Benchmark.tsx` in same directory

### Performance numbers seem too high/low
- Close DevTools (they affect performance measurement)
- Close other browser tabs and applications
- Run benchmark 2-3 times and record the median values
- Note if your device is significantly older/newer than typical development hardware

---

## Contact

If you encounter issues not covered here, document:
1. Exact error message or unexpected behavior
2. Browser/OS/device details
3. Screenshots or console output
4. Steps to reproduce

Report to founder with context for next session.
