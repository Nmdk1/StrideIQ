# Plan generator trace — StrideIQ

**Date:** 2026-04-16
**Author:** session agent, read-only trace
**Scope:** `C:\Dev\StrideIQ` — every path that touches training plan generation today.
**Status:** evidence-backed. All citations are file:line.

---

## 1. Entry points

### HTTP — canonical plan creation

- **`POST /v2/plans/constraint-aware`** (`apps/api/routers/plan_generation.py`, handler `create_constraint_aware_plan` at line 2205). Body: `ConstraintAwarePlanRequest` (lines 1992–2005): `race_date`, `race_distance`, optional `goal_time_seconds`, `tune_up_races`, `race_name`, `target_peak_weekly_miles`, `target_peak_weekly_range`, `taper_weeks`. Query: `dry_run: bool = False`, `engine: Optional[str] = None`. After gates + validation, routes to either `generate_and_save_v2` (V2 path, lines 2356–2378) or `generate_constraint_aware_plan` from `services.constraint_aware_planner` (lines 2383–2396), then `_save_constraint_aware_plan` when not dry-run (lines 2452–2455).

- **`POST /v2/plans/model-driven`** (`create_model_driven_plan`, line 1760). Body: `ModelDrivenPlanRequest` (lines 1707–1713). Downstream: `generate_model_driven_plan` in `services/model_driven_plan_generator.py` (call at lines 1865–1874), then `_save_model_driven_plan` (line 1885).

- **Deprecated / frozen:** `POST /v2/plans/standard*`, `/semi-custom*`, `/custom` return **501** pointing to constraint-aware (lines 330–377). **`POST /v1/training-plans`** returns **410** — `create_plan` in `apps/api/routers/training_plans.py` lines 116–136 points clients to `/v2/plans/constraint-aware`.

- **Read-only / preview:** `GET /v2/plans/constraint-aware/preview` (line 2513) — loads `get_fitness_bank`, optional narratives; does not call a generator. `GET /v2/plans/model-driven/preview` (line 1953) — `get_or_calibrate_model_cached`, `predict_race_time`. `GET /v2/plans/entitlements` (line 275). `POST /v2/plans/classify-tier` (line 299) — `VolumeTierClassifier`.

### Admin

- **`POST /admin/users/{user_id}/plans/starter/regenerate`** (`apps/api/routers/admin.py`, `regenerate_starter_plan`, lines 1501–1566): archives active plans, marks future workouts skipped, records audit `plan.starter.regenerate.skipped`, raises **501** — *"Starter plan generation removed. N=1 engine pending."* No generator runs.

### Celery

- **`tasks.complete_expired_plans`** (`apps/api/tasks/plan_lifecycle_tasks.py` lines 41–54) — calls `complete_expired_active_plans_for_athlete`. Status transitions only, not generation.

- **`tasks.run_morning_intelligence`** (`apps/api/tasks/intelligence_tasks.py` lines 504–511, docstring 4–6): for each athlete in the morning window, runs readiness → daily intelligence → narrations → **`_check_adaptive_replan`** (lines 146–151, impl 438–486). That path can `db.add(PlanAdaptationProposal(...))` (lines 473–476) after `generate_adaptation_proposal` from `services/plan_framework/adaptive_replanner.py`. This is **micro-regeneration for a diff proposal**, not a full plan regen. Micro-plan construction calls **`generate_n1_plan`** inside `_generate_micro_plan` (`adaptive_replanner.py` lines 589–649).

### Scripts / tooling

- Multiple scripts under `apps/api/scripts/` and `apps/api/verification/regenerate_plan.py` call `generate_model_driven_plan` or `generate_constraint_aware_plan`. **`services/coach_tools/plan.py`** instantiates `ModelDrivenPlanGenerator` (~lines 202–206). **`services/ai_coaching_engine.py`** imports `generate_hybrid_plan` from `services/plan_generation`, but **`generate_hybrid_plan` raises `NotImplementedError`** (`plan_generation.py` lines 385–387).

---

## 2. The three generators

### A) V2 — `apps/api/services/plan_engine_v2/`

**Top-level entry**

- **`generate_plan_v2`** — `plan_engine_v2/engine.py:142–157`. Signature:
  `(fitness_bank, fingerprint, load_ctx, *, mode, goal_event, target_date, weeks_available, previous_peak_state, units, desired_peak_weekly_miles, goal_time_seconds, tune_up_races, plan_start_date) -> V2PlanPreview` (return 394–418).
- **`generate_and_save_v2`** — `plan_engine_v2/router_adapter.py:150–168`. Loads bank/context/fingerprint, calls `generate_plan_v2`, optionally `save_v2_plan` (`plan_saver.py:92–198`), returns a dict shaped like the constraint-aware API response (lines 224–269).

**Waterfall (engine, ordered)**

1. Validate RPI for non-onramp modes (`engine.py:163–167`).
2. Pace ladder: `compute_pace_ladder` or beginner default (169–174).
3. Athlete type `_detect_athlete_type` (176–177).
4. Training metadata `_estimate_training_age`, `_is_beginner` (179–181).
5. Plan length / default weeks (183–185).
6. Readiness gate + long-run staircase (`readiness_gate`, `compute_long_run_staircase`, 187–224).
7. Phase structure `_build_phase_structure` (226–229).
8. Volume targets `compute_volume_targets` (231–235).
9. Per-week loop: `schedule_week` / `build_day_from_slot` / builders for build modes, `_reconcile_week_distances`, append `V2WeekPlan` (238–374).
10. Tune-up injection `_insert_tune_up_races` (376–381).
11. `compute_peak_workout_state`, assemble `V2PlanPreview` (383–418).

**Persisted data**

`save_v2_plan` writes `training_plan` rows with `generation_method="v2"` (`plan_saver.py:133–147`) and `planned_workout` rows for non-rest days (157–191). It does **not** insert into the `plan_preview` SQL table — that table exists in `models/plan.py:565–604` and migration `alembic/versions/plan_engine_v2_001_plan_preview.py`, but no insert path for `PlanPreview` ORM was found in application code.

**Reads**

Callers supply `FitnessBank`, `FingerprintParams`, `LoadContext`. Production adapter: `get_fitness_bank`, `build_load_context` + `history_anchor_date`, `build_fingerprint_params` (`router_adapter.py:171–174`).

**Failure / partial data**

`generate_plan_v2` raises `ValueError` if no RPI in race-like modes (163–167). Readiness refusal from `readiness_gate` raises `ValueError(refusal)` (194–204). `router_adapter` wraps V2 path in try/except → HTTP 500 (`plan_generation.py:2374–2378`).

**Flags / gates**

Reachable from `POST /v2/plans/constraint-aware` when `engine == "v2"` **and** `athlete.role in ("admin","owner")` (`plan_generation.py:2356–2357`). Same subscription + `plan.model_driven_generation` flag gate as the V1 constraint path (2238–2252) applies before the V2 branch.

### B) "V1 / plan_framework" — production path is `constraint_aware_planner` + `n1_engine`, not `phase_builder`

**Top-level entry**

`generate_constraint_aware_plan` — `services/constraint_aware_planner.py:1103–1130` — thin wrapper around `ConstraintAwarePlanner.generate_plan` (201–211), returns `ConstraintAwarePlan`.

**Waterfall (`ConstraintAwarePlanner.generate_plan:215–483`)**

1. Optional **intake** `get_intake_context` (218–230).
2. `get_fitness_bank` (233); optional overlay from intake (238–253).
3. `_build_volume_contract` (258–264).
4. Optional `build_load_context` / `history_anchor_date` (271–286).
5. Horizon, starting volume, days/week, plan start Monday, `_compute_personal_long_run_floor` (288–345).
6. `build_fingerprint_params` — correlation + profile + facts (347–362).
7. RPI resolution: bank, goal time, anchors/PBs (364–380).
8. **`generate_n1_plan`** (`services/plan_framework/n1_engine.py:1408–1456`): `resolve_athlete_state` → `plan_weeks` → `assemble_plan` → optional tune-ups.
9. Race week injection (pre/race/post) (400–444).
10. `_insert_tune_up_details` if tune-ups (446–448).
11. `_generate_insights`, `_predict_race` (450–458).
12. Return `ConstraintAwarePlan` (463–483).

`PhaseBuilder` (`plan_framework/phase_builder.py`) is exported from `plan_framework/__init__.py` but **not** referenced by `constraint_aware_planner` or `n1_engine` in the traced path. It appears in tests and comments in `plan_quality_gate.py` only.

**Persisted data**

Router `_save_constraint_aware_plan` (`plan_generation.py:2044–2202`): archives active plans, inserts `training_plan` with `generation_method="constraint_aware"` (2107) and `planned_workout` rows with `workout_variant_id` from `variant_selector.select_variant` (2173–2197).

**Reads**

Same family as V2 for bank + fingerprint + load context; plus intake questionnaire via `intake_context`.

**Failure**

Intake gate HTTP 422 in router (2324–2348). Pace-order checks raise HTTP 422 (2397–2404). Quality gate may re-call `generate_constraint_aware_plan` with fallback volume parameters (2406–2425). Exceptions → HTTP 500 (2503–2509).

**Flags / gates**

`FeatureFlagService.is_enabled("plan.model_driven_generation", athlete)` must be true for constraint-aware (2238–2252) — **same flag key** as model-driven naming suggests historical coupling. `_has_paid_subscription_access` (2254–2262). Rate limit 5/day unless admin/owner (2265–2270).

### C) Legacy / parallel — `services/model_driven_plan_generator.py`

**Top-level entry**

`generate_model_driven_plan` (2145–2173) → `ModelDrivenPlanGenerator.generate` (319–448) → returns `ModelDrivenPlan`.

**Waterfall (`generate:355–448`)**

1. `get_or_calibrate_model` — reads/writes `AthleteCalibratedModel` via `individual_performance_model.get_or_calibrate_model` (355–357; persistence `individual_performance_model.py:804–896`).
2. `_get_current_state`, `_get_established_baseline` (359–368).
3. `OptimalLoadCalculator.calculate_trajectory` (370–378).
4. `_get_training_paces` (380–381).
5. `_convert_trajectory_to_weeks` (384–386).
6. `_apply_decay_interventions` (388–389).
7. `_insert_tune_up_races` (392–393).
8. `RacePredictor.predict` (396–402).
9. Notes and personalization (404–424).
10. Build `ModelDrivenPlan` (430–447).

**Persisted data**

`_save_model_driven_plan` (`plan_generation.py:541–586+`): `generation_method="model_driven"` (585), `planned_workout` from week/day loop.

**Reads**

Banister model calibration from training history (via `IndividualPerformanceModel`), CTL/ATL, mileage aggregation, race predictor — **not** the same `generate_n1_plan` stack.

**Failure**

Router wraps in broad `except` → HTTP 500 (`plan_generation.py:1923–1927`).

**Flags**

`plan.model_driven_generation` (1783–1792). Optional `plan.3d_workout_selection` / `plan.3d_workout_selection_shadow` for `WorkoutSelector` (`model_driven_plan_generator.py:224–250, 312–317`).

---

## 3. Which one is live?

| Scenario | What runs | Evidence |
|---|---|---|
| **(a) Onboarding / starter plans** | **No generator.** Admin starter regen returns 501 (`admin.py:1553–1566`). No HTTP path auto-creates a starter plan after signup. | |
| **(b) Scheduled "full plan refresh"** | **No Celery task** regenerates a full training plan. Beat runs `tasks.complete_expired_plans` (lifecycle only) and `tasks.run_morning_intelligence` (intelligence + optional adaptation proposal, not full regen). | |
| **(c) Manual regeneration (product API)** | **Default: `generate_constraint_aware_plan` → `ConstraintAwarePlanner` → `generate_n1_plan`.** Branch: `POST /v2/plans/constraint-aware` with `engine != "v2"` or non-admin (`plan_generation.py:2355–2396`). | |
| **(c) Alt: V2** | `generate_and_save_v2` only if `engine == "v2"` **and** role admin/owner (2356–2371). | |
| **(c) Alt: model-driven** | `POST /v2/plans/model-driven` → `generate_model_driven_plan` (1760–1874). Separate product surface; same paid + `plan.model_driven_generation` gate. | |
| **(d) Adaptation proposals** | `adaptive_replanner.generate_adaptation_proposal` → `_generate_micro_plan` calls `generate_n1_plan` (`adaptive_replanner.py:589–649`), triggered from `_check_adaptive_replan` inside `run_morning_intelligence` (`intelligence_tasks.py:438–476`). Writes `plan_adaptation_proposal` only, not a new `training_plan`. | |

**Production default** for the main builder API: **`constraint_aware` + `n1_engine`** via `POST /v2/plans/constraint-aware`, unless the client is admin/owner and passes `engine=v2`, or the client uses `/model-driven`.

---

## 4. Overlap and debt

**Shared components**

- `FitnessBank` / `get_fitness_bank`: V2 adapter and constraint-aware planner.
- `build_fingerprint_params` + `build_load_context`: V2 (`router_adapter.py:171–174`) and constraint-aware (`constraint_aware_planner.py:271–283, 347–362`).
- `FingerprintParams` drives cutback spacing, limiter, TSS sensitivity (`fingerprint_bridge.py`); consumed by `generate_plan_v2` and `generate_n1_plan`.
- Pace math: `rpi_calculator` / `calculate_paces_from_rpi` appears in multiple layers (e.g. `n1_engine` imports; model-driven uses its own `_get_training_paces`).
- `variant_selector.select_variant` used when **persisting** constraint-aware plans (`plan_generation.py:2019–2041, 2173–2179`), not in the `ModelDrivenPlan` saver.

**Duplication / tension**

- **Two full-plan engines** (constraint-aware/n1 vs model-driven Banister/TSS) both target `training_plan` + `planned_workout` with different `generation_method` values and different week structures.
- **Flag name `plan.model_driven_generation` gates constraint-aware**, not only model-driven (`plan_generation.py:2238–2241` vs 1783–1785) — naming/behavior mismatch.
- `ConstraintAwarePlanner` module docstring still describes week themes + `WorkoutPrescriptionGenerator` (`constraint_aware_planner.py:1–10, 186–196`), but `generate_plan` uses `generate_n1_plan` (382–398) — documentation drift.
- `PhaseBuilder`, `VolumeTierClassifier` (beyond `/classify-tier`), `workout_scaler`: not on the main constraint-aware execution path; framework inventory with test/endpoint usage rather than live-generator usage.

**Dead / unreachable from live routers**

- `_save_plan` and `_plan_to_preview` in `plan_generation.py:415–538`: no references from other production modules (only xfailed test imports `_save_plan`).
- `generate_hybrid_plan` in `plan_generation.py` raises (385–387).
- `plan_preview` SQL table: model exists; no writer found for `PlanPreview` ORM.
- `services/plans/`: does not exist in the repo.

---

## 5. Where it reads N=1 signal

**Correlation engine (`CorrelationFinding`)** — yes, via `build_fingerprint_params`: queries `CorrelationFinding` with `is_active` and `times_confirmed >= 3` (`fingerprint_bridge.py:336–358`), feeding limiter/TSS/consecutive-day logic (360–441). Used by constraint-aware and V2 adapter.

**`AthleteFact`** — yes, in `build_fingerprint_params` (`fingerprint_bridge.py:443–457`).

**`AthletePlanProfileService` / recovery half-life** — yes, in `build_fingerprint_params` (296–334).

**`AthleteCalibratedModel`** — model-driven path only, via `get_or_calibrate_model` (`individual_performance_model.py:804–896`). Constraint-aware / n1 / V2 traced paths do **not** call `get_or_calibrate_model`.

**`AthleteWorkoutResponse` / `AthleteLearning`** — not read inside `constraint_aware_planner` or `plan_engine_v2/engine.py`. Model-driven can engage them **indirectly** when `WorkoutSelector` runs with `plan.3d_workout_selection` flags (`workout_templates.py:788–837`). Adaptive replanner micro-plan uses `generate_n1_plan` + fingerprint bank path — same correlation bridge as full plans; no `AthleteWorkoutResponse` in `adaptive_replanner.py` itself.

**Explicit "does not"**

- `plan_engine_v2`: no imports of correlation models in `engine.py`; fingerprint is passed in from `build_fingerprint_params`.
- Full constraint-aware generation does not read `AthleteCalibratedModel` in the traced call stack.

---

## 6. The waterfall (production default)

Single ordered call chain for the default shipped path — `POST /v2/plans/constraint-aware`, non-V2:

1. `create_constraint_aware_plan` — `plan_generation.py:2205` — auth, `FeatureFlagService.is_enabled("plan.model_driven_generation")`, paid check, rate limit, validation, intake safety gate (2324–2348), V2 branch skipped (2355+).
2. `generate_constraint_aware_plan` — `constraint_aware_planner.py:1103` — `ConstraintAwarePlanner.generate_plan`.
3. `ConstraintAwarePlanner.generate_plan` — `constraint_aware_planner.py:201` — intake → `get_fitness_bank` (233) → volume contract (258) → `build_load_context` (278) → `build_fingerprint_params` (352) → `generate_n1_plan` (382).
4. `generate_n1_plan` — `n1_engine.py:1408` — `resolve_athlete_state` (1430) → `plan_weeks` (1445) → `assemble_plan` (1446).
5. Post-process in planner: race week injection (400+), `_insert_tune_up_details` (446), `_generate_insights`, `_predict_race` (450–458).
6. `evaluate_constraint_aware_plan` — `plan_generation.py:2406` — optional second `generate_constraint_aware_plan` if gate fails (2414).
7. `_save_constraint_aware_plan` — `plan_generation.py:2454` — `TrainingPlan` + `PlannedWorkout` (2044–2202), `select_variant` for `workout_variant_id` (2173–2197).

If `engine=v2` and admin/owner, steps 2–7 are replaced by `generate_and_save_v2` (`router_adapter.py:150`) → `generate_plan_v2` (`engine.py:142`) → `save_v2_plan` (`plan_saver.py:92`).

---

## 7. Known weak points (code-observable)

1. **Flag coupling:** `plan.model_driven_generation` controls constraint-aware and is named for a different generator (`plan_generation.py:2238–2241`). Real configuration footgun.
2. **Doc vs code:** `ConstraintAwarePlanner` docstring/class comment describes older pipeline (`constraint_aware_planner.py:1–10, 186–196`) while `generate_n1_plan` is the actual core (382–398).
3. **Router helpers `_save_plan` / `_plan_to_preview`** appear unused by live endpoints (415–538, no call sites).
4. **`plan_preview` table** exists in `models/plan.py:565+` but no writer — schema drift vs runtime behavior.
5. **V2 adapter time base:** `generate_and_save_v2` uses `date.today()` for `weeks_to_race` (`router_adapter.py:179–180`) while the constraint-aware router uses `athlete_local_today(get_athlete_timezone(athlete))` (`plan_generation.py:2281–2289`) — potential off-by-one-day/week inconsistency for edge-timezone athletes.
6. **Adaptive micro-plan date mapping:** `_generate_micro_plan` builds `workout_date` with `week_start_date + timedelta(days=day.day_of_week)` (`adaptive_replanner.py:652–655`) while full constraint-aware saving normalizes Monday week start (`plan_generation.py:2154–2159`) — risk of misaligned dates when comparing diffs.
7. **Tests vs removed code:** References to `plan_framework.generator.PlanGenerator` are xfail with "removed" (`test_p4_load_context.py`, `test_workout_variant_dispatch.py`) — debt marker.
8. **Test coverage asymmetry:** Large surface area in `n1_engine.py` and `engine.py`; matrix tests cover many behaviors, but **adaptive replanner micro-plan vs calendar alignment** is a fragile integration point with limited structural guarantees.

---

## Plain-language summary for the founder

- **One engine actually generates plans in production: `constraint_aware_planner` → `n1_engine`.** Everything else — V2, model-driven, starter regen — is either admin-gated, a separate product surface, or frozen.
- **Correlation findings, recovery half-life, and athlete facts already flow in** through `build_fingerprint_params`. The N=1 signal is in the plan.
- **Banister calibration (`AthleteCalibratedModel`), `AthleteWorkoutResponse`, and `AthleteLearning`** are **not** read by the live path. They feed the model-driven generator and the flagged 3D workout selector only.
- **Starter plans are dead** — the admin endpoint returns 501 with a comment about the "N=1 engine pending."
- **Scheduled full-plan refresh does not exist.** Morning intelligence can produce adaptation diff *proposals*, but nothing regenerates a full plan on a clock.
- **Three places are real schema/timezone debt:** the misnamed `plan.model_driven_generation` flag, V2 adapter's `date.today()` vs athlete local date, and the adaptive replanner's week-start math vs the saver's Monday normalization. None of these are urgent, all three are silent-bug material.
