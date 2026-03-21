# Workout variant KB (pilot)

**Spec:** [`docs/specs/WORKOUT_FLUENCY_REGISTRY_SPEC.md`](../../../../docs/specs/WORKOUT_FLUENCY_REGISTRY_SPEC.md) (v0.2.22)

**Purpose:** Per-variant depth (execution, risks, N=1 notes, closed `build_context_tag` set) for **deterministic plan construction**—selection matrix, future registry rows, and tests. **Canonical consumer is code**, not casual reading (see spec §7.0). This directory is **KB**, not runtime code.

**Machine index (Phase 2):** [`workout_registry.json`](workout_registry.json) — **38** v1 rows; CI-validated against pilot `## \`id\`` headers and `workout_scaler` stem aliases via `apps/api/tests/test_workout_registry.py`.

**Build order (define → tools → wire):** [`docs/specs/WORKOUT_FLUENCY_BUILD_SEQUENCE.md`](../../../../docs/specs/WORKOUT_FLUENCY_BUILD_SEQUENCE.md)

## Index

| File | Scope | Status |
|------|--------|--------|
| [`threshold_pilot_v1.md`](threshold_pilot_v1.md) | Pilot 1 — threshold / threshold_intervals | **9 variants `sme_status: approved`** (founder 2026-03-22) |
| [`long_run_pilot_v1.md`](long_run_pilot_v1.md) | Pilot 2 — long / medium_long / long_mp / long_hmp | **9 variants `sme_status: approved`** |
| [`easy_pilot_v1.md`](easy_pilot_v1.md) | Pilot 3 — easy / recovery / easy_strides / rest / hills / strides | **6 variants `approved`** (rollup) |
| [`intervals_pilot_v1.md`](intervals_pilot_v1.md) | Pilot 4 — intervals / VO2 (`interval`, `vo2max` aliases) | **12 `approved`** (3 advanced ids KB-only until scaler — see pilot **Engine gaps**) |
| [`repetitions_pilot_v1.md`](repetitions_pilot_v1.md) | Pilot 5 — repetitions (`reps` alias) | **2 `approved`** |
| [`STEM_COVERAGE.md`](STEM_COVERAGE.md) | Engine `workout_type` → pilot file (inventory) | Living index |

## Authority

- Breadth taxonomy remains in [`../WORKOUT_LIBRARY.md`](../WORKOUT_LIBRARY.md); **where a variant exists here, these definitions override** population-style summaries in the library for that variant ID.
- Pilot **1**–**5** v1 KB files: **all** variant rows **`approved`** per each pilot rollup (**38** rows across threshold, long, easy, intervals, repetitions). **Intervals:** last **3** ids are **approved definitions** with documented **`_scale_intervals` gaps** — not runtime emission yet. **Phase 2** tools + spec **§2** still gate **Phase 3** wiring. Runtime wiring still follows spec §2 (P0 gate).

## PR / gate

- Runtime changes to `plan_framework` still require **P0-GATE** attestation — see [`docs/specs/WORKOUT_FLUENCY_REGISTRY_PR_CHECKLIST.md`](../../../../docs/specs/WORKOUT_FLUENCY_REGISTRY_PR_CHECKLIST.md).
