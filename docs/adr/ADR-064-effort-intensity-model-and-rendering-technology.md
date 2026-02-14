# ADR-064: Effort Intensity Model and Rendering Technology

**Status:** DRAFT — requires prototype evidence and founder approval before implementation
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

#### Option A: Always-Visible Badge (Recommended)

When `cross_run_comparable == false`:
- The tier badge reads: **"Tier 4 · Relative to this run"**
- A subtitle or tooltip: **"Effort colors show the shape of this run. Connect a heart rate monitor for personalized zones."**
- Badge is persistent (not dismissible) — it's provenance, not a notification.

#### Option B: First-View Tooltip Only

Show a one-time tooltip explaining Tier 4 relativity, then hide it. Badge shows "Tier 4" without the caveat text.

**Rejected:** Violates trust transparency — the caveat matters every time the athlete looks at the canvas, not just the first time.

#### Option C: No Caveat (Rejected)

Trust risk — the gradient implies physiological grounding that doesn't exist.

### Recommendation

**Option A.** Persistent badge with caveat text. Exact copy to be finalized in implementation spec.

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

### Prototype Evidence Required

Before selecting, build a minimal prototype comparing Option A and Option B:

1. **Render 3,600 data points** with effort gradient coloring.
2. **Overlay HR + pace traces** with crosshair interaction.
3. **Measure:** initial render time, interaction FPS, DOM node count.
4. **Test on:** desktop Chrome, mobile Safari (iPhone 13 or equivalent), mobile Chrome (mid-range Android).
5. **Visual comparison:** does Option A produce visible block stepping? Does Option B achieve smooth gradient?

### Preliminary Recommendation

**Option B (Hybrid): Canvas 2D gradient + SVG/Recharts interactive layer.** This is the most likely path to achieving the "F1 telemetry aesthetic" while keeping interactive elements manageable. But the recommendation is provisional pending prototype evidence.

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

## Open Items (Must Resolve Before Approval)

- [ ] Prototype evidence: Option A vs Option B rendering comparison
- [ ] Mobile performance benchmarks (iPhone + mid-range Android)
- [ ] Color mapping tuned against real run data (easy run, interval, hill, race)
- [ ] Tier 4 caveat copy finalized
- [ ] Velocity-based fallback thresholds defined for HR-absent runs
- [ ] Founder approval
