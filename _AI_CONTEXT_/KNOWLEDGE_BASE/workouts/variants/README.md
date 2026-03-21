# Workout variant KB (pilot)

**Spec:** [`docs/specs/WORKOUT_FLUENCY_REGISTRY_SPEC.md`](../../../../docs/specs/WORKOUT_FLUENCY_REGISTRY_SPEC.md) (v0.2.14)

**Purpose:** Per-variant depth (execution, risks, N=1 notes, closed `build_context_tag` set) for **deterministic plan construction**—selection matrix, future registry rows, and tests. **Canonical consumer is code**, not casual reading (see spec §7.0). This directory is **KB**, not runtime code.

**Build order (define → tools → wire):** [`docs/specs/WORKOUT_FLUENCY_BUILD_SEQUENCE.md`](../../../../docs/specs/WORKOUT_FLUENCY_BUILD_SEQUENCE.md)

## Index

| File | Scope | Status |
|------|--------|--------|
| [`threshold_pilot_v1.md`](threshold_pilot_v1.md) | Pilot 1 — threshold / threshold_intervals | **9 variants `sme_status: approved`** (founder 2026-03-22) |
| [`long_run_pilot_v1.md`](long_run_pilot_v1.md) | Pilot 2 — long / medium_long / long_mp / long_hmp | **1/8 `approved`** (`long_easy_aerobic_staple`, 2026-03-20); **7 `draft`** — see file header + summary **rollup** (authoritative; overrides any stale “all 8 approved” claim) |

## Authority

- Breadth taxonomy remains in [`../WORKOUT_LIBRARY.md`](../WORKOUT_LIBRARY.md); **where a variant exists here, these definitions override** population-style summaries in the library for that variant ID.
- Pilot 1 threshold and Pilot 2 long-family rows are **`approved`** (see respective pilot files). Additional pilots (**easy**, **VO2**, …) remain **`draft`** until founder sign-off. **Phase 3 wiring** waits on **all v1-scoped** pilots per `WORKOUT_FLUENCY_BUILD_SEQUENCE.md`. Runtime wiring still follows spec §2 (P0 gate).

## PR / gate

- Runtime changes to `plan_framework` still require **P0-GATE** attestation — see [`docs/specs/WORKOUT_FLUENCY_REGISTRY_PR_CHECKLIST.md`](../../../../docs/specs/WORKOUT_FLUENCY_REGISTRY_PR_CHECKLIST.md).
