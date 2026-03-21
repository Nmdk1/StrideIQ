# Workout variant KB (pilot)

**Spec:** [`docs/specs/WORKOUT_FLUENCY_REGISTRY_SPEC.md`](../../../../docs/specs/WORKOUT_FLUENCY_REGISTRY_SPEC.md) (v0.2.10)

**Purpose:** Per-variant depth (execution, risks, N=1 notes, closed `build_context_tag` set) for plan intelligence and future registry wiring. This directory is **KB**, not runtime code.

**Build order (define → tools → wire):** [`docs/specs/WORKOUT_FLUENCY_BUILD_SEQUENCE.md`](../../../../docs/specs/WORKOUT_FLUENCY_BUILD_SEQUENCE.md)

## Index

| File | Scope | Status |
|------|--------|--------|
| [`threshold_pilot_v1.md`](threshold_pilot_v1.md) | Pilot 1 — threshold / threshold_intervals | **9 variants `sme_status: approved`** (founder 2026-03-22) |
| [`long_run_pilot_v1.md`](long_run_pilot_v1.md) | Pilot 2 — long / medium_long / long_mp / long_hmp | **8 variants `sme_status: draft`** — await founder SME |

## Authority

- Breadth taxonomy remains in [`../WORKOUT_LIBRARY.md`](../WORKOUT_LIBRARY.md); **where a variant exists here, these definitions override** population-style summaries in the library for that variant ID.
- Pilot 1 threshold rows are **`approved`** (see `threshold_pilot_v1.md`). Pilot 2 long-family rows are **`draft`** until founder explicit SME sign-off (`long_run_pilot_v1.md`). Additional pilots remain **`draft`** until founder sign-off. Runtime wiring still follows spec §2 (P0 gate).

## PR / gate

- Runtime changes to `plan_framework` still require **P0-GATE** attestation — see [`docs/specs/WORKOUT_FLUENCY_REGISTRY_PR_CHECKLIST.md`](../../../../docs/specs/WORKOUT_FLUENCY_REGISTRY_PR_CHECKLIST.md).
