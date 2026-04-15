# Builder Instructions — Plan Integrity Systemic Recovery (P0)

**Priority:** P0  
**Date:** 2026-03-23  
**Owner:** Builder (Rook)  
**Reviewer:** Northstar + Founder  
**Status:** Draft for review (no implementation started)

---

## 1) Mission

Restore trustworthy plan generation across all active plan paths by fixing systemic defects in:
- race anchor wiring,
- pace source-of-truth integrity,
- volume contract realism,
- distance-specific workout composition,
- tune-up/race-week correctness.

This is a production integrity incident, not a tuning pass.

---

## 2) Inputs Incorporated

This runbook explicitly incorporates:
- Advisor instruction set from commit `29df2e9`:
  - `docs/BUILDER_INSTRUCTIONS_2026-03-23_CONSTRAINT_AWARE_3_BUGS.md`
- Existing P0 recovery decisions:
  - `docs/BUILDER_INSTRUCTIONS_2026-03-20_PLAN_QUALITY_RECOVERY_V2.md`
- Additional validated production defects discovered during live audit:
  - hardcoded tune-up race distance in generator path,
  - race-day pace using marathon pace regardless of race distance,
  - distance key drift (`half` vs `half_marathon`) in constraint-aware path.

---

## 3) Locked Defect List (Must Fix In This Shipment)

### B1a — RPI confidence multiplier corrupts pace anchor
- **Symptom:** athlete pace bands become materially slower than proven race ability.
- **Root cause:** `fitness_bank.py` returns `best_race.rpi * best_race.confidence`.
- **Expected fix:** confidence affects race selection, not returned RPI scalar.

### B1b — Race-tagged activities not wired to anchor table
- **Symptom:** tagged races in `Activity` are ignored by anchor consumers.
- **Root cause:** no automatic write path from race-tagged activity to `AthleteRaceResultAnchor`.
- **Expected fix (schema-consistent):** auto-upsert single canonical anchor row per athlete + one-time backfill.

### B2 — Volume contract can be driven by wrong peak semantics
- **Symptom:** unrealistic baseline/peak volume for current cycle.
- **Root cause:** all-time peak mixed into planning where recent trusted band should dominate.
- **Expected fix:** recent-band-first volume targeting; dedupe-confirmed source.

### B3 — Constraint-aware composition not reliably distance-specific
- **Symptom:** 10K plans can become threshold-only; 5K/10K can leak marathon artifacts.
- **Root cause:** constraint-aware composition diverges from proven framework distance contracts.
- **Expected fix:** enforce distance-specific quality and long-run rules in constraint-aware output.

### B4 — Hardcoded tune-up race distance
- **Symptom:** user-entered tune-up (5K) can become 10-mile race week artifact.
- **Root cause:** fixed race mileage assignment in tune-up week logic.
- **Expected fix:** tune-up distance/date from request payload must be authoritative.

### B5 — Race-day pace source is distance-incorrect
- **Symptom:** race-day pace can inherit marathon pace for non-marathon races.
- **Root cause:** race-day pace field is set from marathon pace key in shared generator code.
- **Expected fix:** race-day pace selection by actual race distance.

### B6 — Distance alias drift in constraint-aware internals
- **Symptom:** `half_marathon` can fall through to default branches.
- **Root cause:** incomplete alias normalization in distance maps.
- **Expected fix:** single canonical normalization for all planner/gate/pace branches.

---

## 4) Concrete Implementation Plan (File-Level)

## WS-A: Race Anchor Integrity

### A1. Remove B1a multiplier
- **File:** `apps/api/services/fitness_bank.py`
- **Change:** return raw `best_race.rpi` from `_find_best_race()` (no confidence multiplier on return).

### A2. Add anchor auto-population from race-tagged activities
- **Files:**
  - `apps/api/services/fitness_bank.py` (or new focused service module)
  - `apps/api/tasks/` (background task/backfill entrypoint)
- **Changes:**
  - **Schema guard:** `AthleteRaceResultAnchor` is currently one-row-per-athlete (`athlete_id` unique).  
    P0 will **not** assume multi-row distance anchors.
  - implement `auto_populate_race_anchor(athlete_id, db)` with a single-row policy:
    - collect candidate races from authoritative race-signal contract (below),
    - select one canonical anchor using explicit policy:
      1) prefer most recent high-confidence race in standard distances,
      2) tie-break by strongest adjusted evidence quality,
      3) never degrade an existing verified anchor unless new evidence is strictly better.
    - upsert single `AthleteRaceResultAnchor` row for the athlete.
  - call on activity sync path and lazy-call during fitness bank load if anchors absent.
  - add one-time backfill script for existing athletes.
  - add fail-safe mode: if race-quality confidence is below threshold, do **not** write anchor; emit diagnostic event instead.

### A3. Authoritative race-signal contract (no single-string matching)
- **Files:**
  - shared helper module under `apps/api/services/` (new or existing)
  - all call sites that infer races (`fitness_bank`, `race_predictor`, anchor sync)
- **Race candidate criteria (locked):**
  - `user_verified_race == True`, OR
  - `workout_type` normalized in race set (`race`, `race_effort`, case-insensitive), OR
  - `is_race_candidate == True AND race_confidence >= 0.7`.
- **Do not** use only `workout_type == "race"` as the sole gate.
- **Acceptance:** all race consumers use this shared contract.

---

## WS-B: Volume Contract Realism

### B1. Verify dedupe + peak derivation
- **Files:**
  - `apps/api/services/fitness_bank.py`
  - `apps/api/services/constraint_aware_planner.py`
- **Changes:**
  - ensure constraint-aware volume targets consume canonical deduped operating band.
  - when recent-band and all-time peak conflict materially, use recent-band governor for current cycle targeting.
  - preserve peak as historical metadata but not dominant current-cycle driver when implausible.
  - lock failure condition to avoid refactor fog:
    - if `peak_confidence == "low"` and `peak_weekly_miles > recent_16w_p90_weekly_miles * 1.35`,
    - then applied peak must be bounded by recent-band ceiling (or explicit athlete override clamp path).

### B2. Baseline save contract
- **File:** `apps/api/routers/plan_generation.py`
- **Change:** baseline volume fields used for persisted plan metadata must reflect recent trusted band logic, not stale all-time artifacts.

---

## WS-C: Distance-Specific Composition Contracts

### C1. Enforce distance workout competency in constraint-aware output
- **Files:**
  - `apps/api/services/workout_prescription.py`
  - `apps/api/services/constraint_aware_planner.py`
- **Changes:**
  - 5K/10K race-specific weeks must include interval/VO2 competency.
  - 5K/10K disallow marathon pace long-run artifacts.
  - half-marathon enforces HMP-related long-run competency.
  - marathon enforces MP progression competency.

### C2. Fix tune-up/race-week authority
- **File:** `apps/api/services/workout_prescription.py`
- **Changes:**
  - **Confirmed current defect exists in code now** (`race_miles = 10` in tune-up assignment path).
  - remove hardcoded tune-up race miles.
  - map tune-up miles from user-entered distance.
  - ensure tune-up date/distance is preserved through final plan output.

### C3. Fix race-day pace mapping
- **File:** `apps/api/services/workout_prescription.py`
- **Change:** race-day pace uses distance-specific race pace key, not marathon pace default.
- **Confirmed current defect exists in code now** (`paces={"race": self.pace_strs["marathon"]}` in race-day generator path).

### C4. Normalize distance aliases everywhere
- **Files:**
  - `apps/api/services/constraint_aware_planner.py`
  - `apps/api/services/workout_prescription.py`
  - any helper maps used by gate/predictor
- **Change:** canonical distance normalizer used before all distance branching.
- **Explicit required fixes in current failing maps:**
  - `constraint_aware_planner._estimate_race_pace()` adjustment map must normalize/handle `half_marathon`,
  - `constraint_aware_planner._predict_race()` distance map must normalize/handle `half_marathon`.
- **Acceptance:** `half_marathon` input cannot fall through to default adjustments in these paths.

---

## WS-E: Full Path Coverage (All Active Generators)

P0 applies to **all active plan paths**, not only constraint-aware.

### E1. Path inventory and parity checks
- **Files:**
  - `apps/api/services/plan_generator.py`
  - `apps/api/services/model_driven_plan_generator.py`
  - `apps/api/services/constraint_aware_planner.py`
  - `apps/api/services/workout_prescription.py`
  - `apps/api/services/plan_framework/generator.py`
- **Changes:**
  - run parity audit for pace-order invariants and distance-specific workout competency across:
    - standard,
    - semi-custom,
    - custom,
    - model-driven,
    - constraint-aware.
  - lock minimum invariants all paths must satisfy (same pace-order contract).
  - any path violating invariant is in-scope for P0 fix.

### E2. Endpoint coverage
- **Files:**
  - `apps/api/routers/plan_generation.py`
- **Changes:**
  - ensure route-level tests hit each generator endpoint with race/tune-up scenarios.
  - add cross-endpoint assertions for tune-up integrity and pace ordering.

---

## WS-D: Pace Sanity Invariants (Hard Contract)

### D1. Add explicit pace-order invariants at generation time
- **File:** `apps/api/services/workout_prescription.py`
- **Invariant examples (required):**
  - interval pace faster than threshold pace
  - threshold pace faster than marathon pace
  - 5K/10K race pace faster than marathon pace
- **Behavior:** if violated, hard-correct/abort with explicit diagnostic tag.

### D2. Add endpoint contract checks
- **File:** `apps/api/routers/plan_generation.py`
- **Behavior:** no successful response may violate pace-order invariants.

---

## 5) Required Test Additions

### New tests (must be added)
- `test_rpi_not_multiplied_by_confidence`
- `test_race_activity_creates_anchor`
- `test_race_anchor_backfill_populates_existing_tagged_races`
- `test_anchor_sync_uses_authoritative_race_signal_contract`
- `test_anchor_sync_skips_low_quality_candidates_with_diagnostic`
- `test_10k_constraint_aware_has_intervals`
- `test_5k_no_marathon_pace_work`
- `test_tuneup_distance_preserved_from_request`
- `test_race_day_uses_distance_specific_race_pace`
- `test_distance_alias_normalization_half_marathon`
- `test_pace_order_invariants_hold_across_rpi_range`
- `test_peak_confidence_low_recent_band_governor_applies`
- `test_all_generator_paths_enforce_pace_order_invariants`

### Existing suites that must pass
- `apps/api/tests/test_plan_quality_recovery_v2.py`
- `apps/api/tests/test_constraint_aware_smoke_matrix.py`
- `apps/api/tests/test_constraint_aware_recovery_contract_real.py`
- `apps/api/tests/test_model_driven_full_flow.py`
- `apps/api/tests/test_plan_validation_matrix.py::TestPlanValidationMatrixStrict`
- `apps/api/tests/test_plan_validation_matrix.py`
- endpoint tests for each route:
  - `/v2/plans/standard`
  - `/v2/plans/semi-custom`
  - `/v2/plans/custom`
  - `/v2/plans/model-driven`
  - `/v2/plans/constraint-aware`

---

## 6) Production Verification Matrix (Post-Deploy)

Run live generation and capture payload evidence for:
- 10K goal + tune-up 5K (founder scenario; exact dates provided at run time)
- 5K goal + tune-up
- Half-marathon goal + tune-up
- Marathon goal + tune-up

For each response, record:
- `plan_id`
- requested tune-up `{date,distance}` vs applied tune-up `{date,distance}`
- race-day distance
- key pace ordering (`interval`, `threshold`, `marathon`, `race`)
- `quality_gate_fallback` and `quality_gate_reasons`
- `volume_contract` source and bounds

Additionally record path coverage:
- which generator endpoint produced each sample,
- whether any endpoint violates pace-order or tune-up integrity contracts.

---

## 7) Execution Discipline (No Exceptions)

1. Implement WS-A through WS-E in scoped commits.
2. Push each commit, wait for CI green before next.
3. Deploy only after full CI green for final commit.
4. Run production verification matrix.
5. Ship only with full evidence block.

No broad refactor, no speculative behavior changes outside locked defects.

---

## 8) Evidence Package Required In Handoff

1. Commit SHAs + exact changed files per commit.
2. Full test outputs (pasted).
3. Before/after comparison table:
   - pace anchors,
   - volume contract values,
   - tune-up/race-day integrity,
   - composition deltas by distance.
4. CI run URLs + status.
5. Production payload samples from verification matrix.

---

## 9) Done Definition (Binary)

This incident is resolved only when all are true:
- race-tagged activities feed anchor table automatically,
- pace anchor no longer reduced by confidence multiplier,
- valid tune-up requests are preserved exactly (date + distance),
- pace-order invariants hold,
- distance-specific composition rules hold for all target distances,
- all active generator endpoints satisfy the same integrity contracts,
- full test + CI + production verification matrix passes.

