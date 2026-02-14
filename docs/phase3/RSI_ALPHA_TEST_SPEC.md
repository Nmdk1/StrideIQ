# RSI-Alpha Tests-First Plan

**Status:** DRAFT — awaiting founder approval
**Date:** February 14, 2026
**Prerequisite:** Gate 1 (ADR-064) cleared, Gate 2 (naming), Gate 3 (priority reconciliation), Gate 6 (VISION alignment) satisfied.
**Scope:** RSI-Alpha only (A1–A12). No coach/LLM surface (AC-12 enforced).

---

## Build Order

Implementation follows this strict sequence:
1. **Backend API endpoint** (`GET /v1/activities/{id}/stream-analysis`) — A1
2. **Effort intensity computation** (tier-dispatched, per ADR-064) — A2 (data layer)
3. **Canvas foundation** (Canvas 2D hybrid scaffold, gradient render) — A2 (render layer)
4. **Trace overlay** (HR, pace on unified axis) — A3
5. **Terrain fill** (elevation area) — A4
6. **Crosshair interaction** (unified across layers) — A6
7. **Segment overlay** (color bands) — A7
8. **Story-layer toggles** (cadence, grade on/off) — A5
9. **Plan comparison card** — A8
10. **Tier/confidence badge** — A9
11. **Lab mode** — A10
12. **Loading states** — A11
13. **Performance validation** — A12 + AC-11

Each step: write tests first (red), implement (green), refactor, verify no regressions.

---

## Test File Structure

### Backend (Python — pytest)

| File | Covers | AC |
|------|--------|----|
| `apps/api/tests/test_stream_analysis_endpoint.py` | A1 endpoint: auth, 200/404/pending/unavailable, response shape | AC-1 |
| `apps/api/tests/test_effort_intensity_computation.py` | Effort scalar per tier: Tier 1–4 formulas, velocity fallback, edge cases | AC-2 (data) |

### Frontend (TypeScript — Jest + React Testing Library)

| File | Covers | AC |
|------|--------|----|
| `apps/web/__tests__/rsi-canvas-effort-gradient.test.tsx` | Effort gradient render: color mapping, Tier 4 caveat, smooth gradient (no block-stepping check via DOM structure) | AC-2 |
| `apps/web/__tests__/rsi-canvas-crosshair.test.tsx` | Unified crosshair: all channels at timestamp, Story↔Lab sync | AC-3 |
| `apps/web/__tests__/rsi-canvas-story-toggles.test.tsx` | Cadence/grade toggles, default state, persistence within session | AC-4 |
| `apps/web/__tests__/rsi-canvas-terrain.test.tsx` | Elevation fill, grade-aware color variation | AC-5 |
| `apps/web/__tests__/rsi-canvas-segments.test.tsx` | Segment overlay bands: colors, alignment with analysis times | AC-6 |
| `apps/web/__tests__/rsi-canvas-plan-card.test.tsx` | Plan comparison card: render/hide logic, content assertions | AC-7 |
| `apps/web/__tests__/rsi-canvas-tier-badge.test.tsx` | Tier badge: label, confidence, Tier 4 caveat visibility | AC-8 |
| `apps/web/__tests__/rsi-canvas-lab-mode.test.tsx` | Lab toggle: raw traces, zone overlays (athlete's own or hidden), segment table, drift metrics | AC-9 |
| `apps/web/__tests__/rsi-canvas-loading-states.test.tsx` | Loading states: spinner, retry hint, hidden, rendered | AC-10 |
| `apps/web/__tests__/rsi-canvas-performance.test.tsx` | Render performance: point count after LTTB, render budget, no coach surface (AC-12) | AC-11, AC-12 |

### E2E (Playwright — if needed for interaction fidelity)

| Script | Covers |
|--------|--------|
| `apps/web/scripts/e2e_rsi_canvas.mjs` | Full interaction smoke: load → gradient visible → crosshair hover → toggle cadence → switch Lab → plan card renders. Real API mocking. |

---

## Test Specifications by AC

### AC-1: Analysis Endpoint

**File:** `apps/api/tests/test_stream_analysis_endpoint.py`

```python
# Test group: Endpoint auth and response shape
# Prerequisite fixtures: test_athlete, test_activity_with_stream, test_activity_no_stream

def test_returns_200_with_full_result_when_stream_exists():
    """GET /v1/activities/{id}/stream-analysis → 200 with all StreamAnalysisResult fields."""
    # Assert: status 200
    # Assert: response JSON contains all 11 fields:
    #   segments, drift, moments, plan_comparison, channels_present,
    #   channels_missing, point_count, confidence, tier_used,
    #   estimated_flags, cross_run_comparable
    # Assert: segments is a list, each with type/start_time_s/end_time_s/avg_hr/avg_pace
    # Assert: drift has cardiac_drift_pct, pace_drift_pct
    # Assert: tier_used is one of tier1_threshold_hr/tier2_estimated_hrr/tier3_max_hr/tier4_stream_relative
    # Assert: confidence is float in [0.0, 1.0]
    # Assert: cross_run_comparable is boolean

def test_returns_404_when_activity_not_found():
    """GET /v1/activities/{nonexistent}/stream-analysis → 404."""

def test_returns_404_when_activity_owned_by_other_user():
    """GET /v1/activities/{other_user_activity}/stream-analysis → 404 (not 403)."""

def test_returns_pending_when_stream_status_fetching():
    """GET when stream_fetch_status = 'fetching' → 200 with {"status": "pending"}."""

def test_returns_pending_when_stream_status_pending():
    """GET when stream_fetch_status = 'pending' → 200 with {"status": "pending"}."""

def test_returns_unavailable_when_stream_status_unavailable():
    """GET when stream_fetch_status = 'unavailable' → 200 with {"status": "unavailable"}."""

def test_returns_401_without_auth():
    """GET without auth header → 401."""

def test_result_includes_plan_comparison_when_plan_linked():
    """When activity has linked PlannedWorkout, plan_comparison is non-null."""

def test_result_plan_comparison_null_when_no_plan():
    """When activity has no linked PlannedWorkout, plan_comparison is null."""

def test_response_includes_effort_intensity_array():
    """Response includes per-point effort_intensity array (or effort field in stream data)
    matching the point_count dimension."""
```

### AC-2: Effort Gradient

**File (backend):** `apps/api/tests/test_effort_intensity_computation.py`

```python
# Test group: Tier-dispatched effort intensity scalar

def test_tier1_effort_hr_divided_by_threshold():
    """Tier 1: effort = HR / threshold_hr, clamped [0, 1]."""
    # threshold_hr=165, HR=132 → effort=0.800
    # threshold_hr=165, HR=165 → effort=1.000
    # threshold_hr=165, HR=186 → effort=1.000 (clamped)

def test_tier2_effort_karvonen_hrr():
    """Tier 2: effort = (HR - resting_hr) / (est_threshold - resting_hr), clamped."""
    # resting=48, max=186, est_threshold = 48 + 0.88*(186-48) = 169.4
    # HR=132 → effort = (132-48)/(169.4-48) = 0.692

def test_tier3_effort_pct_max_hr():
    """Tier 3: effort = HR / max_hr, clamped [0, 1]."""
    # max_hr=186, HR=149 → effort=0.801

def test_tier4_effort_percentile_rank():
    """Tier 4: effort = percentile_rank(HR, within this run), [0, 1]."""
    # 3601-point dataset, known min/max HR → rank is relative

def test_velocity_fallback_when_hr_absent():
    """When HR channel is missing, effort uses velocity-based formula."""
    # Tier 1-3 with threshold_pace: velocity / threshold_velocity
    # Tier 4: percentile_rank(velocity, within run)

def test_effort_array_length_matches_point_count():
    """Effort intensity array has exactly point_count entries."""

def test_effort_values_clamped_0_1():
    """All effort values are within [0.0, 1.0] regardless of tier."""

def test_tier4_cross_run_comparable_false():
    """Tier 4 effort computation sets cross_run_comparable = false."""
```

**File (frontend):** `apps/web/__tests__/rsi-canvas-effort-gradient.test.tsx`

```typescript
// Test group: Effort gradient rendering

test('renders canvas element for gradient', () => {
  // Assert: <canvas> element exists within the RSI canvas component
});

test('canvas uses effort-to-color mapping', () => {
  // Mock StreamAnalysisResult with known effort array
  // Assert: canvas draw function is called (mock drawGradient)
});

test('Tier 4 caveat label is visible when cross_run_comparable is false', () => {
  // Render with cross_run_comparable=false, tier_used='tier4_stream_relative'
  // Assert: text "Effort colors show the shape of this run" is in the document
  // Assert: text "Connect a heart rate monitor" is in the document
});

test('Tier 4 caveat label is hidden when cross_run_comparable is true', () => {
  // Render with cross_run_comparable=true, tier_used='tier1_threshold_hr'
  // Assert: caveat text is NOT in the document
});

test('no visible block-stepping in DOM structure', () => {
  // Assert: gradient is rendered via single <canvas> element, NOT via multiple
  // <rect> or ReferenceArea elements (architecture enforcement)
  // Assert: zero <rect> elements inside the gradient container
});
```

### AC-3: Unified Crosshair

**File:** `apps/web/__tests__/rsi-canvas-crosshair.test.tsx`

```typescript
test('hovering shows values for all visible channels', async () => {
  // Render canvas with HR + pace visible
  // Simulate mousemove at known x position
  // Assert: tooltip/crosshair panel shows HR value at that timestamp
  // Assert: tooltip/crosshair panel shows pace value at that timestamp
  // Assert: tooltip shows time value
});

test('crosshair shows values for toggled-on secondary channels', async () => {
  // Enable cadence toggle
  // Simulate hover
  // Assert: cadence value appears in tooltip
});

test('crosshair hides values for toggled-off channels', async () => {
  // Disable cadence toggle (default state)
  // Assert: cadence does NOT appear in tooltip
});

test('crosshair position syncs between Story and Lab views', async () => {
  // Simulate hover in Story mode at timestamp T
  // Switch to Lab mode
  // Assert: crosshair is at same timestamp T (or equivalent position)
});
```

### AC-4: Story-Layer Toggles

**File:** `apps/web/__tests__/rsi-canvas-story-toggles.test.tsx`

```typescript
test('default state shows HR + pace + elevation, cadence and grade OFF', () => {
  // Render canvas with default props
  // Assert: HR trace visible (has Line element or path data)
  // Assert: pace trace visible
  // Assert: elevation area visible
  // Assert: cadence trace NOT visible
  // Assert: grade trace NOT visible
});

test('toggling cadence ON makes cadence trace visible', async () => {
  // Render canvas
  // Click cadence toggle
  // Assert: cadence trace is now visible
});

test('toggling grade ON makes grade trace visible', async () => {
  // Render canvas
  // Click grade toggle
  // Assert: grade trace is now visible
});

test('toggle state persists across rerender (no reset on resize)', async () => {
  // Toggle cadence ON
  // Trigger window resize event
  // Assert: cadence is still ON
});

test('multiple toggles can be active simultaneously', async () => {
  // Toggle cadence ON, grade ON
  // Assert: both traces visible alongside HR/pace/elevation
});
```

### AC-5: Terrain Fill

**File:** `apps/web/__tests__/rsi-canvas-terrain.test.tsx`

```typescript
test('elevation profile renders as filled area', () => {
  // Assert: Area component for altitude exists in rendered tree
});

test('elevation renders at bottom of canvas', () => {
  // Assert: altitude Area is rendered behind (lower z-index than) traces
});

test('grade-severe sections have distinct fill color', () => {
  // Provide data with grade > 5% sections
  // Assert: terrain fill has color variation (steep sections differ from flat)
});
```

### AC-6: Segment Overlay

**File:** `apps/web/__tests__/rsi-canvas-segments.test.tsx`

```typescript
test('renders segment bands for each segment in analysis result', () => {
  // Provide analysis with 5 segments
  // Assert: 5 background band elements rendered
});

test('segment bands use correct colors per type', () => {
  // warmup → amber, work → red, recovery → green, cooldown → blue, steady → gray
  // Assert each segment band has the expected color/class
});

test('segment bands align with start_time_s and end_time_s', () => {
  // Provide segment with start_time_s=480, end_time_s=720
  // Assert: band spans the correct x-axis range
});

test('no segment overlay when segments array is empty', () => {
  // Assert: no background bands rendered
});
```

### AC-7: Plan Comparison Card

**File:** `apps/web/__tests__/rsi-canvas-plan-card.test.tsx`

```typescript
test('card renders when plan_comparison is non-null', () => {
  // Provide analysis with plan_comparison data
  // Assert: card element is in the document
  // Assert: shows planned vs actual duration
  // Assert: shows planned vs actual distance
  // Assert: shows planned vs actual pace
});

test('card shows interval count match when available', () => {
  // Provide plan_comparison with interval_count_planned and interval_count_actual
  // Assert: text shows both counts (e.g., "Intervals: 5/6")
});

test('card is hidden when plan_comparison is null', () => {
  // Provide analysis with plan_comparison = null
  // Assert: no card element in the document
});

test('card handles missing optional fields gracefully', () => {
  // plan_comparison with only duration (no distance, no intervals)
  // Assert: renders without error, shows available fields
});
```

### AC-8: Confidence + Tier Badge

**File:** `apps/web/__tests__/rsi-canvas-tier-badge.test.tsx`

```typescript
test('badge renders on every canvas view', () => {
  // Assert: badge element always present
});

test('badge shows correct tier label for each tier', () => {
  // tier1_threshold_hr → "Tier 1: Threshold HR"
  // tier2_estimated_hrr → "Tier 2: Estimated HR"
  // tier3_max_hr → "Tier 3: Max HR"
  // tier4_stream_relative → "Tier 4: Relative to this run"
});

test('badge shows confidence as percentage', () => {
  // confidence=0.85 → "85%"
});

test('Tier 4 badge uses amber indicator, Tier 1-3 uses green', () => {
  // Render with tier4 → Assert amber dot class
  // Render with tier1 → Assert green dot class
});

test('Tier 4 caveat subtitle is always visible, not tooltip-gated', () => {
  // Assert: caveat text is in the document, not hidden in a tooltip
});
```

### AC-9: Lab Mode

**File:** `apps/web/__tests__/rsi-canvas-lab-mode.test.tsx`

```typescript
test('Lab toggle switches to raw data mode', async () => {
  // Click Lab toggle
  // Assert: full-precision traces are rendered for all available channels
});

test('zone overlays use athlete physiological data', () => {
  // Provide AthleteContext with threshold_hr=165, max_hr=186
  // Assert: zone lines/bands correspond to athlete's own values
});

test('zone overlays hidden when no physiological data exists', () => {
  // Provide AthleteContext with all nulls (Tier 4)
  // Assert: NO zone overlay rendered (NOT population defaults)
});

test('segment table shows required columns', () => {
  // Assert: table has columns: type, start, end, duration, avg pace, avg HR, avg cadence, avg grade
});

test('drift metrics are displayed', () => {
  // Assert: cardiac drift %, pace drift %, cadence trend are shown
  // Assert: ambiguous metrics use neutral language (no "improved/worsened")
});

test('Lab mode does not render coach interaction elements', () => {
  // Assert: no moment markers, no "ask coach" button, no LLM surface (AC-12)
});
```

### AC-10: Loading States

**File:** `apps/web/__tests__/rsi-canvas-loading-states.test.tsx`

```typescript
test('pending status shows loading spinner', () => {
  // Mock API returning { status: "pending" }
  // Assert: spinner element visible
  // Assert: text "Stream data loading..." visible
});

test('failed status shows retry hint', () => {
  // Mock API returning error / stream_fetch_status = 'failed'
  // Assert: retry hint visible ("Stream data unavailable. Tap to retry.")
  // Assert: retry button/tap target exists
});

test('unavailable status hides stream panel entirely', () => {
  // Mock API returning { status: "unavailable" }
  // Assert: entire RSI canvas container is NOT in the document
});

test('success status renders full canvas', () => {
  // Mock API returning full StreamAnalysisResult
  // Assert: canvas container is in the document
  // Assert: gradient canvas is rendered
  // Assert: traces are rendered
});

test('retry action re-fetches analysis', async () => {
  // Click retry button
  // Assert: API called again
});
```

### AC-11 + AC-12: Performance + No Coach Surface

**File:** `apps/web/__tests__/rsi-canvas-performance.test.tsx`

```typescript
test('display data is downsampled to 500 points or fewer', () => {
  // Provide 3601-point stream
  // Assert: Recharts receives ≤ 500 data points
});

test('LTTB downsampling preserves first and last points', () => {
  // Assert: first point time === 0
  // Assert: last point time === max time
});

test('no LLM calls made from canvas in RSI-Alpha', () => {
  // Assert: no fetch/API call to any coach/narration/LLM endpoint
  // Assert: no moment markers rendered
  // Assert: no "tap to discuss" interaction exists
  // Assert: no "ask coach" button
});

test('no moment markers rendered on canvas', () => {
  // Even if analysis has moments array populated
  // Assert: zero moment marker elements in the DOM
});
```

---

## Backend Test Fixtures Required

```python
# Shared fixtures for test_stream_analysis_endpoint.py

@pytest.fixture
def test_athlete(db_session):
    """Creates an authenticated test athlete."""

@pytest.fixture
def test_athlete_with_context(db_session, test_athlete):
    """Creates athlete with threshold_hr, max_hr, resting_hr populated (Tier 1)."""

@pytest.fixture
def test_activity_with_stream(db_session, test_athlete):
    """Creates an activity with stream_fetch_status='success' and populated ActivityStream."""

@pytest.fixture
def test_activity_pending_stream(db_session, test_athlete):
    """Creates an activity with stream_fetch_status='pending', no stream data."""

@pytest.fixture
def test_activity_unavailable_stream(db_session, test_athlete):
    """Creates an activity with stream_fetch_status='unavailable'."""

@pytest.fixture
def test_activity_with_plan(db_session, test_athlete, test_activity_with_stream):
    """Links a PlannedWorkout to the activity."""

@pytest.fixture
def other_athlete_activity(db_session):
    """Creates an activity owned by a different athlete."""
```

## Frontend Test Fixtures Required

```typescript
// Shared mock data for RSI canvas tests

export const mockStreamAnalysisResult: StreamAnalysisResult = {
  segments: [
    { type: 'warmup', start_time_s: 0, end_time_s: 480, ... },
    { type: 'work', start_time_s: 480, end_time_s: 720, ... },
    { type: 'recovery', start_time_s: 720, end_time_s: 900, ... },
    // ...
  ],
  drift: { cardiac_drift_pct: 4.2, pace_drift_pct: 1.8, cadence_trend_bpm_per_km: -0.3 },
  moments: [],  // RSI-Alpha: empty or ignored
  plan_comparison: null,  // or populated for plan card tests
  channels_present: ['hr', 'pace', 'altitude', 'cadence'],
  channels_missing: ['power'],
  point_count: 3601,
  confidence: 0.85,
  tier_used: 'tier1_threshold_hr',
  estimated_flags: [],
  cross_run_comparable: true,
};

export const mockStreamData: StreamPoint[] = generateIntervalSession(); // reuse spike data gen

export const mockTier4Result: StreamAnalysisResult = {
  ...mockStreamAnalysisResult,
  tier_used: 'tier4_stream_relative',
  confidence: 0.45,
  cross_run_comparable: false,
  estimated_flags: ['stream_relative_classification'],
};

export const mockPendingResponse = { status: 'pending' };
export const mockUnavailableResponse = { status: 'unavailable' };
```

---

## Acceptance Criteria Coverage Map

| AC | Backend Test | Frontend Test | E2E |
|----|-------------|---------------|-----|
| AC-1 | `test_stream_analysis_endpoint.py` (10 tests) | — | smoke |
| AC-2 | `test_effort_intensity_computation.py` (8 tests) | `rsi-canvas-effort-gradient.test.tsx` (5 tests) | visual |
| AC-3 | — | `rsi-canvas-crosshair.test.tsx` (4 tests) | smoke |
| AC-4 | — | `rsi-canvas-story-toggles.test.tsx` (5 tests) | — |
| AC-5 | — | `rsi-canvas-terrain.test.tsx` (3 tests) | — |
| AC-6 | — | `rsi-canvas-segments.test.tsx` (4 tests) | — |
| AC-7 | — | `rsi-canvas-plan-card.test.tsx` (4 tests) | — |
| AC-8 | — | `rsi-canvas-tier-badge.test.tsx` (5 tests) | — |
| AC-9 | — | `rsi-canvas-lab-mode.test.tsx` (6 tests) | — |
| AC-10 | — | `rsi-canvas-loading-states.test.tsx` (5 tests) | smoke |
| AC-11 | — | `rsi-canvas-performance.test.tsx` (2 tests) | — |
| AC-12 | — | `rsi-canvas-performance.test.tsx` (2 tests) | — |

**Total: 18 backend tests + 45 frontend tests + E2E smoke = 63+ tests**

---

## First Checkpoint Criteria

Before moving past checkpoint 1:
1. All backend test files created and running RED (expected failures).
2. All frontend test files created and running RED.
3. Coverage map above is accurate (each AC has at least one failing test).
4. No production code written yet.
5. Founder reviews test coverage and approves before implementation begins.

---

## Trust Contract Enforcement Tests (Embedded in Above)

These tests specifically enforce the Canvas Trust Contract from the proposal:

| Trust Rule | Enforced By |
|------------|-------------|
| Tier 4 → no cross-run claims | `tier-badge.test` (caveat visibility), `effort-gradient.test` (Tier 4 label) |
| Ambiguous metrics → neutral language | `lab-mode.test` (drift metrics language) |
| Low confidence → suppress | `loading-states.test` (confidence < 0.3 behavior) |
| No coach in RSI-Alpha | `performance.test` (no LLM calls, no moments, no tap-to-discuss) |
| Zone overlays use athlete's own data | `lab-mode.test` (athlete zones or hidden) |

---

## Component Architecture (Proposed)

```
components/activities/rsi/
├── RunShapeCanvas.tsx          # Main container: manages data fetch, loading states, view mode
├── EffortGradientLayer.tsx     # Canvas 2D gradient render (ADR-064 Option B)
├── TraceOverlay.tsx            # Recharts SVG: HR, pace, cadence, grade lines
├── TerrainFill.tsx             # Elevation area fill with grade-aware color
├── SegmentOverlay.tsx          # Background segment bands
├── UnifiedCrosshair.tsx        # Crosshair + tooltip spanning all layers
├── StoryToggles.tsx            # Toggle controls for secondary traces
├── PlanComparisonCard.tsx      # Plan vs actual summary card
├── TierBadge.tsx               # Tier/confidence provenance badge + Tier 4 caveat
├── LabMode.tsx                 # Full data mode: raw traces, zone overlays, tables
├── types.ts                    # StreamAnalysisResult, StreamPoint, etc.
└── hooks/
    ├── useStreamAnalysis.ts    # React Query hook for GET /v1/activities/{id}/stream-analysis
    └── useEffortColor.ts       # Effort → color mapping hook (ADR-064 color spec)
```

---

## Open Items

- [ ] Founder approval of test spec
- [ ] Confirm API response includes raw stream data (StreamPoint[]) or separate endpoint
- [ ] Confirm Canvas 2D mocking strategy for Jest/jsdom (jsdom has no real Canvas — may need jest-canvas-mock or structural tests)
- [ ] Confirm if `generate_interval_session` should be shared between spike and test fixtures
