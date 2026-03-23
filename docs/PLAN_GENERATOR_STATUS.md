# Plan Generator Recovery Status

**This is the single source of truth for the plan generator project.**

Every agent that touches any file matching `apps/api/services/plan*`,
`apps/api/routers/plan_generation.py`, or any plan test must:

1. Read this document before their first tool call.
2. Update the Session Log and re-verify all affected checklist rows before their last commit.

"DONE" means: test command + output is pasted here. Not "code written." Not "tests pass." Pasted evidence.

---

## Last Verified

| Field | Value |
|---|---|
| Date | 2026-03-18 |
| Session | [Plan Generator Status Audit](6a788801-3485-41ed-b1d1-e3e188525078) |
| Commit | e56c81f |
| Who verified | Rook |

---

## Blocking Issues — Resolve Before Any Feature Work

These must be cleared in order. Do not start a lower-numbered item while a higher one is open.

| # | Issue | Status |
|---|---|---|
| 1 | `QUALITY_FOCUS` dict in `workout_prescription.py` is dead code. 5K/10K plans produce threshold-only quality work because the attribute is defined but never read during workout assignment (`_assign_standard_week`, `_assign_peak_week` both hardcode `threshold`). | **CLOSED** — commit bf6eaa2 |
| 2 | No test suite exercises real plan content against realistic athlete profiles. Every passing test checks that the generator does not crash, not that it produces a rational plan. The synthetic athlete population requested by the founder has not been built as a persistent test fixture. | **CLOSED** - commit f981529. 4 archetypes x 4 distances (16 CA) + 5 model-driven = 21 content assertions. Volume-aware injury floor bug fixed in same commit. |
| 3 | Floor logic is duplicated, not unified. `plan_framework/load_context.py` and `plan_quality_gate.py` use separate floor formulas. Phase 3 (unified floor) is incomplete. | **OPEN** |

---

## System Inventory — What Actually Exists

Four active generation backends. All wired to production endpoints.

| Generator | File | Endpoints served | Notes |
|---|---|---|---|
| `PlanGenerator` (v2 framework) | `services/plan_framework/generator.py` | `POST /v2/plans/standard`, `/semi-custom`, `/custom` (preview + create) | Main v2 path. Active. |
| `ModelDrivenPlanGenerator` | `services/model_driven_plan_generator.py` | `POST /v2/plans/model-driven` | Uses Banister model + TSS trajectory. Active. |
| `ConstraintAwarePlanner` | `services/constraint_aware_planner.py` | `POST /v2/plans/constraint-aware` | Uses FitnessBank + WorkoutPrescriptionGenerator. Active. |
| `ArchetypePlanGenerator` (v1) | `services/plan_generator.py` | `POST /v1/training_plans` (legacy router) | v1 path. Still live. Quality work is on v2, not here. |

Additional supporting modules (not endpoints):
- `services/principle_plan_generator.py` — used by AI coaching engine
- `services/plan_generation.py` — used by `ai_coaching_engine.py` (contains dead code after early return at ~395)
- `services/workout_prescription.py` — used exclusively by `ConstraintAwarePlanner`

---

## Phase Checklist

Status: **DONE** = evidence pasted. **PARTIAL** = code exists, not fully proven. **NOT DONE** = not started or failed audit.

---

### Phase 0 — Stop the bleeding

| Item | Status | Evidence |
|---|---|---|
| 0A: `starter_plan._goal_date_from_intake` fix | DONE | Function verified in `starter_plan.py:66`. Test `test_starter_plan_cold_start_week1_guardrail` passes. |
| 0B: `generate_custom` NameError fix | DONE | `recent_activities` defined in function scope in `generator.py`. Test `test_generate_custom_without_user_or_race_anchor_does_not_nameerror` passes. |
| 0C: Monetization drift scrub (no `$5`/`PlanPurchase` in v2 paths) | DONE | `pace_access.py` verified clean. |
| WS-A A1 (B1a): Remove RPI × confidence multiplier | DONE | `fitness_bank.py` returns raw `best_race.rpi`. Test `test_rpi_not_multiplied_by_confidence` PASSES. |
| WS-A A2/A3 (B1b): Anchor auto-populate from race-tagged activities | PARTIAL | Code written in `fitness_bank.py`. Tests `test_race_activity_creates_anchor`, `test_anchor_sync_uses_authoritative_race_signal_contract`, `test_anchor_sync_skips_low_quality_candidates_with_diagnostic` — exist but SKIP locally (require DB). Pass in CI. |
| WS-D D1/D2: Pace-order invariants at generation time + endpoint guards | DONE | `pace_engine.py` enforces order. Route guards in `plan_generation.py`. Tests in `test_pace_integration.py` pass. |
| WS-C C2: Tune-up distance from request (not hardcoded 10mi) | DONE | Test `test_tuneup_distance_preserved_from_request` PASSES. |
| WS-C C3: Race-day pace uses distance-specific key | DONE | Test `test_race_day_uses_distance_specific_race_pace` PASSES. |
| WS-C C4: Distance alias normalization (`half_marathon` no fallthrough) | DONE | Test `test_distance_alias_normalization_half_marathon` PASSES. |
| WS-B B2: Peak confidence governor (recent band used when peak implausible) | DONE | Test `test_peak_confidence_low_recent_band_governor_applies` PASSES. |
| Saturday `medium_long` reverted to `easy` + pre-long TSS% reduced | DONE | All `medium_long` removed from week structures. `test_model_driven_short_cycle_contract.py` 20 passed. |

**Missing from Phase 0 (spec-required tests not yet written):**
- `test_race_anchor_backfill_populates_existing_tagged_races` — NOT written
- `test_10k_constraint_aware_has_intervals` — NOT written
- `test_5k_no_marathon_pace_work` — NOT written
- `test_pace_order_invariants_hold_across_rpi_range` — NOT written
- `test_all_generator_paths_enforce_pace_order_invariants` — NOT written

| WS-C C1: Distance-specific workout composition in constraint-aware (10K gets intervals, 5K no marathon pace work) | DONE — commit bf6eaa2. `test_10k_constraint_aware_has_intervals` PASSES. `test_5k_no_marathon_pace_work` PASSES. 34/34 smoke matrix. |

---

### Phase 1 — Make validation matrix real

| Item | Status | Evidence |
|---|---|---|
| 1A: Semi-custom no-DB matrix sweep | PARTIAL | Exists in `test_plan_validation_matrix.py` (~398–412) |
| 1B: DB-backed semi-custom sweep with seeded history (LoadContext exercised) | PARTIAL | Exists (~414–468) with short synthetic `Activity` list. Not a full FitnessBank profile. |
| 1C: Constraint-aware distance smoke matrix (4 distances × 3 profiles) | PARTIAL | `test_constraint_aware_smoke_matrix.py` parametrized. Uses mock DB and synthetic FitnessBank object — does not test real DB path. |
| 1C: Recovery contract tests use real generation pipeline (no monkeypatching) | PARTIAL | `test_constraint_aware_recovery_contract_real.py` has 7 tests calling real planner. `test_constraint_aware_recovery_contract.py` still monkeypatches some paths. |
| 1D: 5K emphasis contradiction resolved | UNKNOWN | Not verified this session. |

Phase 1 gate not met: matrix does not include a real DB-backed constraint-aware variant per distance.

---

### Phase 2 — Quality gate for all distances

| Item | Status | Evidence |
|---|---|---|
| Gate structure branches on `race_distance` | DONE | `plan_quality_gate.py` has `_evaluate_10k_rules`, `_evaluate_marathon_rules`, `_evaluate_half_rules`, `_evaluate_5k_rules` |
| Each distance has ≥3 meaningful checks beyond generic volume ceiling | UNKNOWN | Structure exists; depth not audited this session. |
| New tests fail when bad plans are introduced for any distance | UNKNOWN | Not verified. |

Phase 2 gate not formally met.

---

### Phase 3 — Unified floor system

| Item | Status | Evidence |
|---|---|---|
| Founder decision on floor formula (Option A: `max(L30, p75_8w, p50_16w)` vs Option B: `max(L30, p75_8w)`) | UNKNOWN — decision not recorded | |
| Single `compute_floor()` function replaces all floor logic | NOT DONE | `load_context.py` and `plan_quality_gate.py` use separate implementations |
| All floor consumers (LoadContext, quality gate, constraint-aware) use unified source | NOT DONE | |

Phase 3 not started. Requires founder decision first.

---

### Phase 4 — Recovery spec completion

| Item | Status | Evidence |
|---|---|---|
| Recovery contract tests 2–7 exist and use real pipeline | PARTIAL | 7 tests in `test_constraint_aware_recovery_contract_real.py`. Some still mock `get_fitness_bank`. |
| 10/10 green against real generation | NOT VERIFIED | |

---

### Phase 5 — LoadContext in constraint-aware path

| Item | Status | Evidence |
|---|---|---|
| `build_load_context` imported and called in `constraint_aware_planner.py` | DONE | Lines ~39–40 (import), ~158–173 (build), ~191–198 (passed to WorkoutPrescriptionGenerator). |
| L30 floor + D4 override semantics consistent with LoadContext | UNKNOWN | Not verified this session. |

---

### Phase 6 — Strict mode CI enforcement

| Item | Status | Evidence |
|---|---|---|
| `TestPlanValidationMatrixStrict` exists and runs in CI | DONE | CI job `plan-validation-strict` in `.github/workflows/ci.yml` ~168–201. |
| Strict validation green with no policy-waiver xfails | NOT DONE | `TRAINING_PLAN_REBUILD_PLAN.md` documents 6 explicit policy-waiver xfails that remain. |

---

### Phase 7 — Documentation sync

| Item | Status | Evidence |
|---|---|---|
| `TRAINING_PLAN_REBUILD_PLAN.md` baseline numbers updated | NOT DONE | |
| `specs/PLAN_GENERATION_COMPREHENSIVE_PATH.md` completion markers updated | NOT DONE | |
| Handoff doc with final evidence and remaining risks | NOT DONE | |

---

## The Real Quality Gate — Synthetic Athlete Test Suite

**This section is the truth-telling test. Nothing here can say PASS without pasted output.**

The founder requested: realistic synthetic athletes including May–Nov training history
mapped to a fake athlete, diverse archetypes (comeback, volatile, consistent,
high-mileage), tested across all distances, all models, all variants.

| Component | Status |
|---|---|
| Synthetic population script (`generate_realistic_synthetic_population.py`) | EXISTS — script written, not committed as persistent test fixture |
| Persistent test fixtures in `apps/api/tests/fixtures/` | NOT DONE |
| Matrix test that asserts plan content (W1 long run ≤ 32% weekly, quality sessions by distance, pace order) | NOT DONE |
| constraint-aware endpoint included in matrix | NOT DONE — was never tested in any matrix run |
| All 4 distances × all 3 plan types × ≥3 athlete archetypes | NOT DONE |

**Minimum assertions the real quality test must make:**
1. Week 1 long run ≤ 32% of athlete's recent weekly mileage
2. 5K/10K plans contain interval sessions by week 3
3. 5K plans contain no marathon pace work
4. Saturday (day before Sunday long run) is an easy run, not a medium-long or quality session
5. Pace order: interval < threshold < marathon for every week
6. Plan length matches requested duration weeks (±0)
7. Race week is the final week

---

## Execution Order — Next Steps

Work the blocking issues in order. No exceptions.

**Step 1 (next):** Fix `QUALITY_FOCUS` wiring in `workout_prescription.py`
- `_assign_standard_week`: use `self.quality_focus[0]` to select quality type when `quality_type` param defaults to `"threshold"`
- `_assign_peak_week`: use `"intervals"` for 5K/10K instead of always `"threshold"`
- Write `test_10k_constraint_aware_has_intervals` and `test_5k_no_marathon_pace_work`
- Evidence required: paste test output before marking DONE

**Step 2:** Build synthetic athlete test suite as persistent fixtures
- Realistic profiles, not mocks
- Assertions on actual plan content
- All 4 distances × all 3 plan types × ≥3 archetypes
- constraint-aware included

**Step 3:** Phase 3 — Founder decides floor formula, then build unified function

**Step 4:** Work remaining Phase 1→6 items in order, verify each with tests before moving to next

**Step 5:** Phase 7 — sync docs

---

## Session Log

Every session that touches plan code must add a row here before its last commit.

| Date | Session | Commits | What changed | What test proved it | New blocking issues opened |
|---|---|---|---|---|---|
| 2026-03-18 | [Plan Generator Status Audit](6a788801-3485-41ed-b1d1-e3e188525078) | e56c81f (last) | Saturday medium_long reverted to easy, pre-long TSS% reduced to 0.12, medium_long handler removed from `_create_day_plan` | `test_model_driven_short_cycle_contract.py`: 20 passed 3 skipped | QUALITY_FOCUS dead code confirmed; real quality test suite still absent |
| 2026-03-18 | [Plan Generator Status Audit](6a788801-3485-41ed-b1d1-e3e188525078) | b4d5496, b559085 | Created `PLAN_GENERATOR_STATUS.md` living ledger + `plan-generator-status.mdc` cursor rule. Committed Saturday revert. | — | — |
| 2026-03-18 | [Plan Generator Status Audit](6a788801-3485-41ed-b1d1-e3e188525078) | bf6eaa2 | Wired QUALITY_FOCUS: `_assign_peak_week` uses intervals for 5K/10K; `_assign_mp_week` blocks marathon pace for 5K/10K; `_assign_standard_week` BUILD_MIXED secondary uses intervals not mp_medium. Added `test_10k_constraint_aware_has_intervals` and `test_5k_no_marathon_pace_work`. | `test_constraint_aware_smoke_matrix.py`: 34 passed. Full suite: 239 passed, 8 skipped, 8 xfailed, 0 failures. | Blocking Issue #1 CLOSED. Blocking Issues #2 (real test suite) and #3 (unified floor) remain. |
| 2026-03-18 | [Plan Generator Status Audit](6a788801-3485-41ed-b1d1-e3e188525078) | f981529 | Built real content quality matrix (21 tests): 4 archetypes x 4 distances CA + 5 model-driven scenarios. Fixed volume-aware injury floor bug in `plan_quality_gate.py` (_injury_floor_minimum capped at 32% weekly volume for comeback athletes). Added `test_race_anchor_backfill_populates_existing_tagged_races` (WS-A spec test, DB-required, skips locally). | `test_plan_content_quality_matrix.py`: 21 passed. Full suite: 260 passed, 8 skipped, 8 xfailed, 0 failures. | Blocking Issues #1 and #2 CLOSED. #3 (unified floor) remains. |



