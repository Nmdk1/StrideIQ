# ADR-064: Effort Intensity Model and Rendering Technology

**Status:** DRAFT — prototype evidence captured, awaiting founder approval
**Date:** 2026-02-14
**Owner:** StrideIQ
**Blocks:** All RSI-Alpha frontend implementation (Hard Gate 1)

---

## Context

RSI-Alpha requires a per-second effort intensity value to drive the canvas effort gradient — a continuous color mapping that visually tells the story of the run. The Phase 2 analysis engine classifies segments (warmup, work, recovery, cooldown, steady) using the N=1 tiered model, but segment classification is discrete. The effort gradient requires a continuous scalar per data point.

Additionally, the rendering technology must support smooth continuous color gradients at per-second resolution (~3,600 points for a 1-hour run) while maintaining interactive performance on mobile viewports.

Two decisions are required:
1. How to compute effort intensity per second, respecting the tiered physiological context model.
2. What rendering technology to use for the canvas.

---

## Decision 1: Effort Intensity Computation Per Tier

### The Problem

Effort intensity must be a 0.0–1.0 scalar at every data point, driving the color gradient. But "effort" means different things depending on what physiological data is available:

- With threshold HR: effort relative to lactate threshold is physiologically grounded.
- With only max HR: percentage of max is coarser but directionally meaningful.
- With no HR data: only pace-based signals are available.
- With no physiological profile: everything is relative to this run only.

A single formula cannot serve all tiers without either losing meaning (Tier 4) or false precision (applying Tier 1 math with Tier 4 data).

### Options Considered

#### Option A: Tier-Dispatched Intensity (Recommended)

Compute effort intensity using a tier-specific formula, consistent with Phase 2 classification:

| Tier | Available Data | Intensity Formula | Range Mapping |
|------|---------------|-------------------|---------------|
| **Tier 1** | `threshold_hr` | `HR / threshold_hr` | 0.0 = rest, 0.85 = easy, 1.0 = threshold, >1.0 = supra-threshold (clamped to 1.0 for color) |
| **Tier 2** | `max_hr` + `resting_hr` | `(HR - resting_hr) / (estimated_threshold_hr - resting_hr)` using Karvonen HRR at 88% | Same mapping as Tier 1, labeled `estimated` |
| **Tier 3** | `max_hr` only | `HR / max_hr` | 0.0 = rest, 0.60 = easy, 0.82 = moderate, 0.90 = hard, 1.0 = max |
| **Tier 4** | No physiology | `percentile_rank(HR or velocity, within this run)` | 0.0 = lowest in run, 1.0 = highest in run |

When HR is unavailable at any tier, fall back to velocity-based intensity:
- Tiers 1-3: `velocity / threshold_pace_velocity` (if threshold pace known), else Tier 4.
- Tier 4: `percentile_rank(velocity, within this run)`.

**Pros:**
- Consistent with Phase 2 tiered model — same architectural pattern.
- Tier provenance is already in `StreamAnalysisResult` — no new computation needed to select tier.
- Effort gradient accuracy degrades gracefully with less data.

**Cons:**
- Tier 4 gradient is relative, not absolute — two easy runs might have identical gradients despite different actual effort. Requires UI caveat.

#### Option B: Segment-Derived Intensity

Use the Phase 2 segment classification directly: map segment type to a fixed intensity value (warmup = 0.3, steady = 0.5, work = 0.8, etc.), then interpolate between transitions.

**Pros:**
- Simple, deterministic, no new computation.
- Consistent with existing segment output.

**Cons:**
- **Loses the continuous story.** The whole point of the effort gradient is to show per-second variation WITHIN segments. A steady segment that gradually gets harder appears as a flat block. This defeats the design vision.
- Transitions are artificial (interpolated, not data-driven).

**Rejected:** Does not serve the design intent.

#### Option C: Composite Multi-Signal Intensity

Combine HR, pace, cadence, and grade into a weighted composite effort score. Weights tuned per athlete or per tier.

**Pros:**
- Richer signal than HR alone.
- Could capture muscular effort (grade + cadence) that HR misses.

**Cons:**
- Weight tuning is a research project, not a v1 feature.
- Harder to explain to the athlete ("what does the color mean?").
- More signals = more noise in the gradient.

**Rejected for v1:** Complexity/interpretability trade-off doesn't justify it. Can revisit as an enhancement.

### Recommendation

**Option A: Tier-Dispatched Intensity.** The effort scalar is HR-anchored when HR exists, velocity-anchored otherwise, with tier-specific formulas matching Phase 2 classification. Provenance and caveat are explicit.

---

## Decision 2: Tier 4 UI Caveat Contract

### The Problem

Tier 4 effort intensity is relative to this run's own distribution. The color gradient shows the shape of effort within the run but cannot be compared across runs. An athlete might see "cool blue" on a section that was objectively hard for them (if the rest of the run was even harder).

Without a visible caveat, the visualization implies a precision it doesn't have.

### Options Considered

#### Option A: Always-Visible Badge (Selected)

When `cross_run_comparable == false`:
- The tier badge reads: **"Tier 4 · Relative to this run"**
- Subtitle text (always visible, not tooltip-gated): **"Effort colors show the shape of this run. Connect a heart rate monitor for personalized effort zones."**
- Badge is persistent (not dismissible) — it's provenance, not a notification.
- Badge uses amber indicator dot to distinguish from green dot used by Tier 1–3.

When `cross_run_comparable == true` (Tier 1, 2, or 3):
- Badge reads: **"Tier N · [Threshold HR | Estimated | Max HR]"**
- Subtitle: **"Confidence: XX%"** with optional "Cross-run comparable" label.
- Green indicator dot.

**Finalized copy** (implemented in spike Tier 4 caveat preview):
```
Badge:    ● Tier 4 · Relative to this run
Subtitle: Effort colors show the shape of this run.
          Connect a heart rate monitor for personalized effort zones.
```

#### Option B: First-View Tooltip Only

Show a one-time tooltip explaining Tier 4 relativity, then hide it. Badge shows "Tier 4" without the caveat text.

**Rejected:** Violates trust transparency — the caveat matters every time the athlete looks at the canvas, not just the first time.

#### Option C: No Caveat (Rejected)

Trust risk — the gradient implies physiological grounding that doesn't exist.

### Decision: Option A (Always-Visible Badge)

**Selected.** Persistent badge with finalized caveat copy. Amber dot for Tier 4, green dot for Tier 1–3.

---

## Decision 3: Rendering Technology

### The Problem

The effort gradient requires per-pixel color mapping across a time axis. Standard charting libraries (Recharts, Chart.js) render discrete SVG elements — lines, bars, areas. A continuous color gradient mapped to ~3,600 data points is fundamentally a raster operation.

The canvas also requires: interactive crosshair, multiple trace overlays, zoom/pan, responsive layout, and ≥ 30fps interaction on mobile.

### Options Considered

#### Option A: Recharts with ReferenceArea Approximation

Use Recharts (existing library). Approximate the gradient with N thin `ReferenceArea` components, each colored to its effort intensity.

**Pros:**
- Existing library — no new dependency.
- Built-in tooltips, axes, responsive container.
- Consistent with existing chart components.

**Cons:**
- At 500 ReferenceAreas + trace lines + axes = 2,000+ SVG DOM nodes. Mobile performance risk.
- ReferenceAreas create visible block steps, not smooth gradients.
- "F1 telemetry aesthetic" is unlikely achievable with SVG rectangles.

#### Option B: Canvas 2D for Gradient + Recharts for Axes/Tooltips (Hybrid)

Render the effort gradient and trace fills on an HTML5 Canvas element. Overlay Recharts (or custom SVG) for axes, labels, crosshair tooltip, and interactive elements.

**Pros:**
- Canvas handles raster operations natively — smooth gradient at any resolution.
- Thousands of data points render in <1ms on Canvas (pixel operations, not DOM nodes).
- Recharts handles the interactive layer (tooltips, axes) where SVG excels.
- Separation: Canvas = visual beauty, SVG = interactivity.

**Cons:**
- Two rendering layers must stay synchronized (scroll, zoom, resize).
- Canvas content is not accessible to screen readers (SVG layer handles that).
- More implementation complexity than pure Recharts.

#### Option C: Full Canvas 2D (No Recharts)

Render everything — gradient, traces, axes, crosshair, tooltips — on a single Canvas 2D element with a custom rendering pipeline.

**Pros:**
- Maximum rendering performance.
- Complete visual control — no library constraints.

**Cons:**
- Rebuilds tooltip, axis, responsive layout from scratch.
- Loses Recharts' battle-tested interaction patterns.
- Highest implementation effort.
- Accessibility harder without SVG layer.

#### Option D: WebGL (Three.js / deck.gl)

Use GPU-accelerated rendering for the canvas.

**Pros:**
- Handles millions of data points trivially.

**Cons:**
- Massive overkill for ~3,600 points.
- Heavy dependency.
- Mobile WebGL support is inconsistent.

**Rejected:** Scale doesn't justify GPU rendering.

### Prototype Evidence (February 14, 2026)

Prototype spike at `apps/web/app/spike/rsi-rendering/`:
- `data.ts` — synthetic 6×800m interval session generator (3,601 points)
- `OptionA.tsx` — Recharts ComposedChart with batched ReferenceArea gradient
- `OptionB.tsx` — Canvas 2D gradient with Recharts SVG overlay
- `analyze.ts` — offline analysis producing concrete DOM/visual metrics

**Test data:** 3,601 data points, 60 minutes, HR 128–186 bpm, effort 0.776–1.000 (Tier 1: HR/threshold at 165).

#### Evidence: DOM Node Count

| Approach | Gradient nodes | SVG overlay | Total estimated |
|----------|---------------|-------------|-----------------|
| **Option A** (ReferenceArea, threshold=0.02) | 29 bands → ~145 SVG nodes | ~140 | **~285** |
| **Option B** (Canvas 2D) | 1 `<canvas>` element | ~140 | **~145** |

Option B uses ~50% fewer DOM nodes. Both are well under the 2,000-node concern threshold, but Option A's advantage of "lower effort" is marginal since the SVG overlay is identical.

#### Evidence: Gradient Visual Fidelity

| Metric | Option A | Option B |
|--------|----------|----------|
| Gradient method | Batched ReferenceArea bands | Per-pixel `fillRect` |
| Band width at threshold=0.02 | **~28px per band** | 1px per column |
| Visible block-stepping | **Yes — 28px bands are clearly visible** | No — pixel-perfect smooth |
| Max effort change per pixel | N/A (batched) | 2.4% (sub-perceptual) |
| Avg effort change per pixel | N/A | 0.15% |

**Critical finding:** At the 0.02 effort threshold used in the prototype, Option A produces 29 discrete color bands averaging 28 pixels wide. These are visually obvious as block steps — not a gradient. Lowering the threshold to 0.01 increases to 78 bands (~10px wide), still visible as stepping on HiDPI displays. Only at ~1px band width (3,600 bands) would Option A approximate smoothness — but that creates 18,000+ SVG nodes, defeating the purpose.

#### Evidence: Performance Projection

| Operation | Option A | Option B |
|-----------|----------|----------|
| Gradient render | 29 SVG `<rect>` creation + layout | ~800 `fillRect` calls → single bitmap |
| Resize/reflow | Full SVG reflow of all 285 nodes | Canvas `clearRect` + redraw (~5ms) |
| Tooltip hit-testing | 285+ SVG nodes in hit test | ~140 SVG nodes (gradient is Canvas, not in SVG tree) |
| Mobile concern | Moderate (285 nodes manageable) | Low (Canvas is GPU-composited) |

Both options are performant enough for the data volume. The performance gap becomes significant at zoom/pan interaction and on low-end mobile, where Option B's Canvas redraw is constant-time while Option A's SVG reflow scales with node count.

#### Evidence: Visual Assessment

Prototype available at `/spike/rsi-rendering` (dev server). Key observations:
- Option A: effort gradient appears as a series of colored rectangles. Transitions between effort levels are sharp horizontal lines. Does not convey "continuous effort story."
- Option B: effort gradient is smooth — color transitions are imperceptible at pixel level. The continuous gradient visually communicates the gradual shift in effort intensity.
- Both options render the HR (red) and pace (blue) traces identically via Recharts Line components.
- The elevation fill (altitude area) renders identically in both.

### Decision: Option B (Canvas 2D Hybrid)

**Selected.** The Canvas 2D hybrid approach achieves pixel-perfect smooth gradients with fewer DOM nodes, better resize performance, and visual fidelity that meets the F1-telemetry aesthetic bar. The implementation cost premium (Canvas+SVG synchronization) is justified by the visual quality difference, which is the core differentiator of the product's identity.

**Rejected: Option A.** Discrete ReferenceArea bands produce visible 28px block-stepping that fails the "run comes alive" design intent. No batching threshold can produce both smooth gradients and reasonable SVG node counts.

**Rejected: Option C** (full Canvas). Rebuilding tooltips, axes, and responsive layout from scratch is not justified when Recharts handles these well.

**Rejected: Option D** (WebGL). Overkill for ~3,600 points. Mobile WebGL support is inconsistent.

---

## Color Mapping Specification (Preliminary)

Effort intensity (0.0 → 1.0) maps to a color gradient:

| Intensity Range | Color Region | HSL Approximate |
|---|---|---|
| 0.0 – 0.3 | Cool blue (recovery/rest) | HSL(200, 70%, 60%) → HSL(180, 60%, 50%) |
| 0.3 – 0.6 | Teal → Warm amber (easy/moderate) | HSL(180, 60%, 50%) → HSL(40, 80%, 55%) |
| 0.6 – 0.8 | Amber → Orange (tempo/steady) | HSL(40, 80%, 55%) → HSL(20, 90%, 50%) |
| 0.8 – 0.95 | Orange → Red (threshold/hard) | HSL(20, 90%, 50%) → HSL(0, 85%, 45%) |
| 0.95 – 1.0 | Deep crimson (max) | HSL(0, 85%, 45%) → HSL(350, 90%, 35%) |

Exact values to be tuned against real run data during prototype. Must look correct on dark background (slate-900).

### Terrain Fill Color (Grade-Aware)

| Grade | Fill Color |
|---|---|
| < 2% | Slate-700 (neutral) |
| 2% – 5% | Amber-800 (moderate) |
| > 5% | Red-900 (steep) |

---

## Consequences

### If Option A (Tier-Dispatched Intensity) Selected
- Effort gradient is physiologically grounded for Tier 1-3 athletes.
- Tier 4 athletes see a useful within-run shape but require visible caveat.
- Implementation mirrors Phase 2 tier dispatch — familiar pattern.

### If Option B (Hybrid Rendering) Selected
- Visual quality achieves the "F1 telemetry" bar.
- Synchronized Canvas + SVG layers add implementation complexity.
- Future layers (coach moments, comparison overlays) can be added to the SVG layer.

### Risks Accepted
- Tier 4 gradient accuracy is limited — mitigated by caveat label.
- Hybrid rendering requires coordinate synchronization — mitigated by shared state in React component.
- Color mapping is subjective — mitigated by prototype tuning against real data.

---

## Appendix A: Runtime Evidence (February 14, 2026)

Source: `apps/web/app/spike/rsi-rendering/bench-runtime.ts` — Node.js benchmark measuring
computation hot paths. Test data: 3,601-point synthetic interval session. Benchmark run on
development machine (Windows, Node.js).

### A.1 Initial Render Time

| Viewport | Computation p95 | SVG Overlay Estimate | **Total Estimate** | Target | Status |
|----------|----------------|---------------------|--------------------|--------|--------|
| Desktop 1200px | 0.9ms | ~15ms | **~16ms** | < 2,000ms | **PASS** |
| Mobile 375px | 1.0ms | ~15ms | **~16ms** | < 2,000ms | **PASS** |

Computation includes: data generation (p95: 2.3ms), LTTB downsampling 3601→500 (p95: 0.42ms),
and gradient pixel computation (desktop p95: 0.27ms, mobile p95: 0.01ms). SVG overlay estimate
(15ms) accounts for Recharts ComposedChart mount with 500 points, 2 Lines, and 1 Area.

Total initial render is **~125x under the 2,000ms mobile target.** Even accounting for real
browser DOM overhead (React hydration, layout, paint), there is massive headroom.

### A.2 Crosshair/Tooltip Interaction Latency

| Viewport | Data Lookup p95 | Paint/Reflow Overhead | **Combined p95 Estimate** | Target | Status |
|----------|----------------|----------------------|--------------------------|--------|--------|
| Desktop | 0.001ms | ~2–8ms | **< 8ms** | < 33ms (30fps) | **PASS** |
| Mobile | 0.000ms | ~2–8ms | **< 8ms** | < 33ms (30fps) | **PASS** |

Measured over 200 synthetic mousemove events across the chart width. Data lookup is O(1)
(direct index calculation from mouse position), so latency is dominated by browser paint.
At < 8ms combined, this achieves **4x headroom** against the 30fps frame budget.

### A.3 Resize Latency

| Resize Path | Gradient Redraw + LTTB p95 | Target | Status |
|-------------|---------------------------|--------|--------|
| Desktop → Tablet (1090→658px) | 0.1ms | < 100ms | **PASS** |
| Tablet → Mobile (658→265px) | 0.0ms | < 100ms | **PASS** |
| Mobile → Desktop (265→1090px) | 0.1ms | < 100ms | **PASS** |
| Desktop → Wide (1090→1350px) | 0.1ms | < 100ms | **PASS** |

Gradient redraw is linear in pixel count (O(chartWidth)) and completes in < 1ms for any
viewport. LTTB re-downsampling is technically not required on resize (point count doesn't
change), but included as worst-case. Total resize latency is **1000x under the 100ms target.**

### A.4 Canvas/SVG Synchronization Correctness Proof

**Architecture:**
- Canvas: `position: absolute; top: 0; left: 0` in parent `<div>`
- SVG (Recharts): `position: relative; z-index: 1` in same parent `<div>`
- Both share identical `MARGIN = { top: 10, right: 60, left: 50, bottom: 30 }`
- Canvas logical width = `chartWidth + MARGIN.left + MARGIN.right` = container width
- SVG logical width = `ResponsiveContainer width="100%"` = container width
- Canvas physical width = `logicalWidth × devicePixelRatio`
- Canvas drawing coordinates: `ctx.scale(dpr, dpr)` keeps all drawing in logical pixels

**Proof:** Canvas `style.width` and SVG `clientWidth` are both derived from the same parent
container width. The `drawGradient()` function uses the same `MARGIN` constants as the
Recharts `<ComposedChart margin={MARGIN}>`. Both layers resize via the same `resize` event
listener. DPR scaling is handled in `drawGradient()` by setting `canvas.width = totalWidth * dpr`
and `ctx.scale(dpr, dpr)`, ensuring crisp rendering on HiDPI displays without affecting
logical coordinate alignment.

| Scenario | Canvas Logical | SVG Logical | Canvas Physical | Expected Physical | Aligned | DPR |
|----------|---------------|-------------|-----------------|-------------------|---------|-----|
| Desktop 1200px (1x) | 1200px | 1200px | 1200px | 1200px | **PASS** | **PASS** |
| Desktop 1200px (2x) | 1200px | 1200px | 2400px | 2400px | **PASS** | **PASS** |
| Laptop 960px (1.25x) | 960px | 960px | 1200px | 1200px | **PASS** | **PASS** |
| Tablet 768px (2x) | 768px | 768px | 1536px | 1536px | **PASS** | **PASS** |
| Mobile 375px (3x) | 375px | 375px | 1125px | 1125px | **PASS** | **PASS** |
| Mobile 375px (2x) | 375px | 375px | 750px | 750px | **PASS** | **PASS** |
| After resize: 1200→600 (1x) | 600px | 600px | 600px | 600px | **PASS** | **PASS** |
| After resize: 600→1440 (1.5x) | 1440px | 1440px | 2160px | 2160px | **PASS** | **PASS** |

**Result: ALL 8 SCENARIOS PASS** — Canvas and SVG layers remain aligned under all tested
viewport sizes, resize operations, and device pixel ratios.

**Zoom/Pan note:** RSI-Alpha spec does not include zoom/pan (time-range selection only). If
added in a future phase, the same `drawGradient()` function would be called with an adjusted
time range, preserving all synchronization guarantees.

### A.5 Browser-Level Benchmark

**Status: PENDING** — artifacts not yet captured. Required before green-state sign-off.

Two tools exist to capture live browser evidence:

**Interactive harness:** `apps/web/app/spike/rsi-rendering/Benchmark.tsx`
- Captures: initial render time, p95 tooltip latency, p95 resize latency, sync proof
- Accessible at `/spike/rsi-rendering` → "Run Benchmark" button

**Automated Playwright script:** `apps/web/scripts/adr064_benchmark.mjs`
- Runs desktop (1280x800, 1x DPR) + mobile (375x812, 3x DPR) benchmarks
- Outputs JSON results + screenshots to `apps/web/evidence/adr-064/`
- Run: `node scripts/adr064_benchmark.mjs` (requires dev server + `npx playwright install chromium`)

When captured, artifacts will be:
- `apps/web/evidence/adr-064/benchmark-results.json`
- `apps/web/evidence/adr-064/{desktop,mobile}-{charts,benchmark}.png`

---

## Open Items

- [x] Prototype evidence: Option A vs Option B rendering comparison — **DONE** (Feb 14, 2026)
- [x] Tier 4 caveat copy finalized — **DONE** (Feb 14, 2026)
- [x] Runtime evidence (computational): initial render, p95 crosshair, p95 resize, synchronization proof — **DONE** (Feb 14, 2026)
- [ ] Browser-level verification via Playwright script — **PENDING**, required before green-state sign-off
- [ ] Color mapping tuned against real run data (easy run, interval, hill, race) — to be done during RSI-Alpha implementation with real Strava data
- [ ] Velocity-based fallback thresholds defined for HR-absent runs — to be defined in RSI-Alpha test spec
- [ ] Founder approval
