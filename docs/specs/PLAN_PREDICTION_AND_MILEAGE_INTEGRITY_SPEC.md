# Plan Prediction + Mileage Integrity Spec

**Date:** March 20, 2026  
**Status:** Proposed (scope-approved)  
**Priority:** P0 for mileage integrity, P0/P1 for prediction truthfulness  
**Owner:** Builder + Advisor  
**Trigger:** Repeated production regressions: inflated weekly mileage totals and untrustworthy single-number race prediction during injury return.

---

## Why This Exists

Two user-visible trust breaks are coupled but distinct:

1. **Mileage totals regression (P0):** weekly/peak totals are sometimes inflated, contaminating Fitness Bank and downstream planning outputs.
2. **Prediction truth regression (P0/P1):** a single predicted finish can be materially wrong when recent comeback races, injury recovery, and missing recent quality sessions are not modeled explicitly.

The product cannot claim N=1 trust while these failure modes persist.

---

## Problem Statements

### A) Mileage totals integrity (P0)

- Fitness Bank peak/current mileage can be overstated due to duplicate activity paths.
- Different subsystems may apply dedupe logic differently (or not at all), creating inconsistent totals across endpoints/screens.
- Inflated totals create second-order errors: too-high plan volume, bad confidence, and false narrative statements.

### B) Prediction truthfulness during return-from-injury (P0/P1)

- A single-number prediction currently over-compresses uncertainty.
- Recency and capability signals are mixed without an explicit injury-return/quality-continuity contract.
- Result: either over-penalized outputs (comeback race dominates) or over-optimistic outputs (historic peak dominates) with weak disclosure.

---

## Scope

### In Scope

1. Define and enforce one canonical mileage aggregation contract used by Fitness Bank + plan preview + related endpoints.
2. Define prediction model contract combining:
   - proven capability,
   - recent form,
   - injury-return readiness,
   - quality-session continuity.
3. Replace hard single-number certainty in injury-return contexts with bounded scenario outputs.
4. Add deterministic regression tests for both tracks.
5. Add rollout safety gates (feature flag + shadow compare + rollback).

### Out of Scope

- Full ML model retraining.
- Cross-athlete priors (must remain N=1 contract).
- Full UI redesign beyond prediction panel + rationale/disclosure changes.

---

## Product + Truth Principles

1. **Truth over neatness:** if uncertainty is high, output uncertainty.
2. **One source of numerical truth:** mileage totals must be identical for same athlete/data snapshot across services.
3. **Athlete agency:** system informs; athlete decides. Aggressive intent can be represented, but never hidden behind fake certainty.
4. **No silent optimism or pessimism:** confidence and rationale must be explicit.

---

## Track A — Mileage Totals Integrity Contract (P0)

### A0. Canonical Symbol + Location (Locked)

Canonical aggregator module:

- `apps/api/services/mileage_aggregation.py` (new)

Canonical symbols:

- `get_canonical_run_activities(athlete_id, db, *, start_time=None, end_time=None, require_trusted_duplicate_flags=True)`
- `compute_weekly_mileage(activities)`
- `compute_peak_and_current_weekly_miles(activities, now=None)`

Contract:

- Any service needing plan-critical mileage totals must call this module.
- No second dedupe implementation in planners/routers.

### A1. Canonical Aggregation Contract

Introduce/standardize a single canonical path for run-mile aggregation with:

- primary duplicate exclusion (`is_duplicate == False`) **as default**
- optional conservative in-memory near-duplicate collapse **only when duplicate flags are untrusted/missing for the queried slice**
- deterministic provider preference when collapsing duplicate records.

This contract must be used by:

- Fitness Bank peak/current calculations,
- plan preview summaries that surface peak/current volume,
- any endpoint that reports weekly/peak mileage for planning decisions.

### A2. Dedupe Rules (Conservative)

Two activities are probable duplicates if:

- start times within 10 minutes,
- distance within max(2% relative, 150m absolute),
- duration within max(10% relative, 5 minutes absolute).

When duplicate pair detected, keep preferred provider variant by explicit rank.
Must not collapse legitimate doubles (AM/PM runs).

Fallback activation rule:

- `require_trusted_duplicate_flags=True` path uses DB flag filter only.
- Fallback collapse allowed only when the caller explicitly passes `require_trusted_duplicate_flags=False` due to known stale/backfill windows.
- Fallback usage must emit telemetry (`fallback_dedupe_used=true`).

### A3. Data Consistency Requirement

For a fixed athlete and immutable activity snapshot:

- `peak_weekly_miles`, `current_weekly_miles`, and derived weekly totals must be numerically identical across all plan-generation read paths.

### A4. Required Tests

1. Cross-provider same-run duplicate collapses to one.
2. Same-day distinct doubles remain two.
3. Hard boundary: AM/PM doubles with similar distance/pace but >10 minutes separation remain two.
3. Historical duplicate flags absent -> in-memory dedupe still protects totals.
4. Peak-week calculation stable under provider order permutations.
5. End-to-end: same fixture yields identical totals across relevant endpoints.

All tests should reuse one shared golden fixture module:

- `apps/api/tests/fixtures/golden_athlete_fixture.py`

---

## Track B — Prediction Truthfulness Contract (P0/P1)

### B1. Inputs

Prediction must explicitly model four dimensions:

1. **Proven capability** (best validated race performances and strongest blocks),
2. **Recent form** (recency and current load),
3. **Injury-return readiness** (time since break, current volume recovery),
4. **Quality continuity** (recent threshold/interval/race-pace exposure).

### B2. Injury-Return Rules

If athlete is in injury-return state and recent quality continuity is weak:

- widen uncertainty band,
- reduce confidence classification,
- annotate rationale with explicit readiness caveat.

Recent races still matter, but cannot singularly override all proven capability.

### B3. Output Contract

For high-uncertainty contexts (especially injury return), response includes:

- `conservative`
- `base`
- `aggressive`

each with:

- predicted time,
- confidence level,
- rationale tags (e.g., `proven_peak`, `recent_form`, `injury_return`, `quality_gap`).

### B3.1 Explicit Schema (Locked Before Build)

Backend response schema:

```python
prediction: {
  "time": str,  # backward-compatible alias to scenarios.base.time
  "confidence_interval": str | None,  # legacy-compatible, optional
  "uncertainty_reason": str | None,
  "rationale_tags": list[str],  # enum-like strings
  "scenarios": {
    "conservative": {"time": str, "confidence": "low" | "medium" | "high"},
    "base":         {"time": str, "confidence": "low" | "medium" | "high"},
    "aggressive":   {"time": str, "confidence": "low" | "medium" | "high"},
  }
}
```

Web types must mirror this exactly in:

- `apps/web/lib/api/services/plans.ts`

If context is low-uncertainty and data-rich, UI may still show a primary estimate, but internal contract keeps scenario outputs available.

### B4. Disclosure Contract

Prediction panel must show why the estimate is bounded:

- recent quality continuity status,
- injury-return state,
- recency/capability balance note.

No presentation of false precision.

### B5. Required Tests

1. Fixture: older strong 10K + recent slower comeback marathon + no recent quality
   - expects widened range, reduced confidence, and rationale tags.
2. Fixture: healthy runner with consistent recent quality
   - expects tighter range and higher confidence.
3. Fixture: recent race only, no historical depth
   - expects uncertainty disclosure and conservative confidence.
4. Regression: prediction cannot be dominated by one low-context race without confidence penalty.
5. Monotonicity guard: confidence cannot increase when quality continuity decreases (holding other inputs constant).

All prediction tests should reuse the same shared golden fixture used in Track A.

---

## API Contract Changes

### Constraint-Aware / Plan Preview payload additions

- `prediction.scenarios.conservative.time`
- `prediction.scenarios.base.time`
- `prediction.scenarios.aggressive.time`
- `prediction.scenarios.*.confidence`
- `prediction.rationale_tags[]`
- `prediction.uncertainty_reason`

Backward compatibility:

- keep legacy `prediction.time` as alias to `base.time` during transition window.

---

## UI Contract Changes (`plans/create`)

1. Replace single hard prediction in uncertainty contexts with 3-scenario card.
2. Show short rationale chips (injury return, quality continuity, proven peak).
3. Preserve clean display; avoid overwhelming detail unless expanded.

---

## Implementation Phases

### Phase 0 — Immediate Integrity Patch (P0)

- Lock canonical mileage aggregation path in planning/Fitness Bank.
- Add regression tests for dedupe + aggregate invariance.
- Add logging metrics: `dedupe_pairs_collapsed`, `weekly_peak_before_after`.

### Phase 1 — Prediction Contract (P0/P1)

- Implement scenario-based output in prediction service path.
- Add injury-return + quality-continuity gating.
- Preserve backward-compatible fields.

### Phase 2 — UI Truth Surface (P1)

- Render scenario outputs + rationale chips in plan preview.
- Add uncertainty disclosure copy.

### Phase 3 — Rollout Safety (P1)

- Feature flag for new prediction display/contract.
- Shadow compare old vs new predictions for founder cohort.
- Promote after stability/acceptance metrics pass.

---

## Observability + Guardrails

Track per-day:

- % athletes with mileage diff across endpoints (must trend to 0),
- count of dedupe collapses,
- prediction confidence distribution by injury-return state,
- % predictions with uncertainty disclosure when quality continuity is low.

Hard alerts:

- non-zero aggregate mismatch for same athlete snapshot,
- prediction payload missing rationale tags in injury-return state.
- confidence monotonicity violation in validation suite/shadow checks.

---

## Acceptance Criteria

1. Mileage totals invariance holds across all planning read paths for fixture set.
2. Duplicate-induced peak inflation is eliminated in regression fixtures.
3. Injury-return fixtures produce bounded scenario output with explicit reduced confidence.
4. No single-number false precision shown in known high-uncertainty contexts.
5. Existing healthy/data-rich fixtures preserve plausible confidence and tighter ranges.
6. Backward compatibility maintained for clients during transition.

---

## Risks

1. Over-collapsing true doubles if dedupe thresholds are too loose.
   - Mitigation: conservative thresholds + explicit AM/PM double tests.
2. UI complexity from scenario outputs.
   - Mitigation: compact default + expandable rationale.
3. Contract drift across services.
   - Mitigation: central aggregation utility + shared fixture tests.

---

## Open Decisions (to lock before implementation)

1. Should athlete intent mode (`conservative|balanced|aggressive`) be explicit UI input now, or deferred?
2. Should scenario output be always-on or only when uncertainty trigger trips?
3. Should aggressive scenario be capped by guardrails or be unconstrained athlete expression?

---

## Build Checklist

- [ ] Canonical mileage aggregation utility (`services/mileage_aggregation.py`) consumed in all planning/Fitness Bank paths
- [ ] Regression tests for duplicates + invariance
- [ ] Prediction scenario contract implemented (backend)
- [ ] Backward-compatible API aliasing
- [ ] `plans/create` UI scenario rendering + rationale chips
- [ ] Feature-flag rollout + shadow logging
- [ ] Post-rollout audit report confirms zero mileage mismatch regressions

