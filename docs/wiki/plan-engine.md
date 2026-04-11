# Plan Engine

## Current State

The plan engine uses a diagnosis-first, constraint-aware architecture. The N1 Engine V3 (`services/plan_framework/n1_engine.py`, ~1,078 lines) replaced all legacy generators (deleted Mar 29, 2026). Plans are grounded in 76 KB rules, 14 archetypes, and individual athlete data.

## How It Works

### N1 Engine Architecture

The engine follows a diagnosis-first flow:

1. **Diagnosis:** Analyze the athlete's current state — fitness bank, pace profile, race distance, timeline, experience level
2. **Archetype selection:** Match to one of 14 archetypes based on weekly mileage, days/week, experience, and race distance
3. **Phase construction:** Build training phases (base, build, peak, taper) using `phase_builder.py`
4. **Workout selection:** Select workouts from the registry using `variant_selector.py` and `workout_variant_dispatch.py`
5. **Scaling:** Scale workouts to the athlete using `workout_scaler.py`
6. **Quality gate:** Validate the plan against blocking criteria

### Key Components

| File | Role |
|------|------|
| `services/plan_framework/n1_engine.py` | Core engine — diagnosis, assembly, save |
| `services/plan_framework/phase_builder.py` | Construct training phases |
| `services/plan_framework/volume_tiers.py` | Volume tiering by experience |
| `services/plan_framework/workout_scaler.py` | Scale workouts to athlete level |
| `services/plan_framework/variant_selector.py` | Choose workout variants from registry |
| `services/plan_framework/workout_variant_dispatch.py` | Dispatch rules for variants |
| `services/plan_framework/pace_engine.py` | Pace targets and zones |
| `services/plan_framework/fingerprint_bridge.py` | Translate findings → plan params |
| `services/plan_framework/limiter_classifier.py` | Classify dominant limiter |
| `services/plan_framework/load_context.py` | Load context for scaling |
| `services/plan_framework/mp_progression.py` | Marathon pace progression |
| `services/plan_framework/registry.py` | Workout/phase registry |
| `services/plan_framework/adaptive_replanner.py` | Re-plan on divergence |
| `services/constraint_aware_planner.py` | Constraint-aware planning orchestration |
| `services/plan_quality_gate.py` | Quality gates before surfacing |

### Athlete Inputs

Respected athlete inputs (cannot be overridden):
- `race_date`, `race_distance`, `days_per_week`, `rest_days`, `long_run_day`
- `target_peak_weekly_miles`, `goal_time_seconds`, `tune_up_races`

API: `ConstraintAwarePlanRequest` in `routers/plan_generation.py`.

### 14 Archetypes

IDs 1-14, covering beginner through elite, 5K through marathon, 3-7 days/week. Each archetype defines base weekly mileage, quality density, phase lengths, and recovery patterns.

### 12 Blocking Criteria (BC)

From `docs/specs/N1_ENGINE_ADR_V2.md`:

- **BC-1:** Quality-density table by distance/experience/days
- **BC-6:** Recovery architecture
- **BC-10:** Marathon pace accumulation floors by experience/horizon
- **BC-11:** Sharp taper
- **BC-12:** No pace predictions when `rpi: None` (enforced by regex in evaluator)

Evaluated by `scripts/eval_plan_quality.py` (143 PASS / 0 FAIL / 11 WAIVED).

### KB Rule Registry

76 annotated rules in `docs/specs/KB_RULE_REGISTRY_ANNOTATED.md`. Evaluated by `scripts/eval_kb_rules.py` (445 PASS / 0 FAIL / 17 WAIVED). Categories: GP (General), PH (Phase), WS (Workout Selection), REC (Recovery), QD (Quality Density).

### Workout Registry

JSON-based registry (`workout_registry.json`) with variant definitions. 38 approved variants with phase-appropriate filtering. The variant dropdown on the calendar lets athletes choose within guardrails.

### Adaptive Re-Plan (Phase 4)

`PlanAdaptationProposal` model tracks adaptation proposals:

- **Triggers:** Missed long run, 3+ consecutive missed days, 5-day readiness tank
- **Scope:** 2-week micro-plan that fits the current training phase
- **Athlete approval:** Home page card with diff display, accept/reject
- **Expiry:** End-of-day Sunday of the second adjusted week
- **Silence = keep original** (non-negotiable)

### Save Path

`_save_constraint_plan_v2` is the canonical save path. Plans are saved as `TrainingPlan` with `PlannedWorkout` rows. `PlanModificationLog` tracks all changes.

### Phase Context

`phase_week` is **NOT** populated on `PlannedWorkout`. Phase context is derived from week number relative to plan start and phase boundaries defined in the plan's phase structure.

### RPI-to-Training-Pace Calculator

Training paces are derived from a **hardcoded lookup table** (`_RPI_PACE_TABLE` in `services/rpi_calculator.py`) covering RPI 20-85 with linear interpolation for fractional values. This replaced a formula-based intensity-percentage pipeline that regressed 3+ times.

**Derivation (see `services/rpi_pace_derivation.py` for full proof):**

1. Start from the two published Daniels/Gilbert equations: oxygen cost of running + time-to-exhaustion fraction
2. Derive velocity function: `v = 29.54 + 5.000663*vdot - 0.007546*vdot^2` (quadratic regression of the exact inverse of the oxygen cost equation)
3. Apply fixed effort fractions: Easy 70%/62%, Threshold 88%, Interval 97.5%
4. Apply slow-runner correction for RPI < 39: `adjusted = RPI*(2/3) + 13` — compensates for the oxygen cost equation's systematic underestimation at low velocities
5. Marathon pace: Newton's method on the time-to-exhaustion equation
6. Repetition: I pace minus 24.1 sec/mi (6 sec per 400m)

Verified against the official Daniels reference calculator (vdoto2.com) at RPI 31 (10K = 1:02:00): all 6 zones match within +/- 1 second.

| RPI | Easy | Threshold | Interval | Rep |
|-----|------|-----------|----------|-----|
| 25 | 12:22 | 11:04 | 9:35 | 9:11 |
| 31 | 11:14 | 9:43 | 8:40 | 8:16 |
| 45 | 8:58 | 7:28 | 6:52 | 6:28 |
| 60 | 7:07 | 5:54 | 5:26 | 5:02 |
| 75 | 5:56 | 4:56 | 4:32 | 4:08 |

**Critical rule:** DO NOT replace `_RPI_PACE_TABLE` with formula-based approaches. The table is the single source of truth for training paces.

## Key Decisions

- **Diagnosis-first:** Plan generation starts with diagnosing the athlete, not selecting a template
- **KB-grounded:** Every plan decision traces to an annotated rule
- **RPI-only predictions:** Race predictions and training paces come from the individual performance model, never population formulas
- **Table-based training paces:** Hardcoded lookup table derived from first principles, not intensity-percentage formulas (which regressed 3+ times)
- **Athlete agency within guardrails:** Variant dropdown with 38 variants, phase-appropriate filtering
- **No silent swaps:** Adaptations require explicit approval

## Known Issues

- **`phase_week` not populated:** Phase context must be derived, not read directly
- **Fingerprint bridge partial consumption:** Only `cutback_frequency` and `quality_spacing_min_hours` are consumed; `limiter` and `primary_quality_emphasis` are computed but not wired to session scheduling
- **7-day archetype (ID 14):** Requires lifting the `max(3, min(6, ...))` clamp in `constraint_aware_planner.py`
- **Marathon pace at very low RPIs (< 28):** Marathon pace can exceed easy pace because the iterative Newton's method correctly models extreme fatigue over marathon duration for very slow runners. Not a bug — these athletes would not train for marathons.

## Next-Generation Algorithm Spec (V2)

A full rewrite of the plan generator algorithm is specified in `docs/specs/PLAN_GENERATOR_ALGORITHM_SPEC.md`. This is the builder's single source of truth for the generator rewrite.

### New Plan Modes

The current engine only generates race-specific plans. V2 adds:

| Mode | Sub-modes | Duration | Use case |
|------|-----------|----------|----------|
| **Race** | M/HM, 5K/10K, Ultra (50K-100mi) | 6-16 weeks | Preparing for a specific race |
| **Build** | Onramp (8wk), Volume (6wk repeatable), Intensity (4wk) | 4-8 weeks | General fitness without a race |
| **Maintain** | — | 4 weeks, repeating | Hold fitness between goals |

All modes use the **same unified engine** — same segments schema, same pace ladder, same progression rules. The difference is dosage and periodization structure, not architecture.

### Key Architectural Additions

- **Extension-based progression:** Within a block, pace stays CONSTANT. The segment duration extends week over week (e.g., 400m → 800m → 1200m → mile at the same pace). This replaces "do the same workout faster."
- **Build-over-build memory:** `peak_workout_state` stored on `TrainingPlan`. Each successive block seeds its starting point from the previous block's peak, ensuring continuous adaptation across cycles.
- **Unified segments schema:** All structured workouts populate `PlannedWorkout.segments` with types: `warmup`, `cooldown`, `work`, `float`, `jog_rest`, `easy`, `threshold`, `interval`, `stride`, `steady`, `hike`, `fatigue_resistance`, `uphill_tm`.
- **Effort-based descriptions:** Athlete-facing text uses effort language (10K effort, threshold, easy/mod) with pace as secondary guidance. Internal `pace_pct_mp` is never shown to the athlete.
- **Fueling targets:** Every workout ≥90 min includes `fueling_target_g_per_hr` in the segments schema and a fueling reminder in the description.
- **Distance ranges:** Prescribed as ranges (e.g., "8-16 mi") for athlete self-selection — central to the "plans written in pencil" philosophy.
- **Three rotating long run types:** Easy progressive (A), threshold segments (B), fatigue resistance (C) — rotating weekly to prevent staleness.
- **Auto-renewal:** Build and Maintain plans auto-generate the next block before the current one ends, ensuring the calendar is never empty.

### Coaching Science KB

The generator is grounded in a comprehensive knowledge base of modern coaching science:

| Document | Content |
|----------|---------|
| `ROCHE_SWAP_TRAINING_PHILOSOPHY_UNIFIED_2026-04-10.md` | **Start here.** Unified synthesis: hierarchy of interventions, sliding bottleneck model, speed theory, threshold theory, fatigue resistance, coaching voice |
| `ROCHE_SWAP_COACHING_PHILOSOPHY_2026-04-10.md` | Plan-level analysis of 8 SWAP plans (beginner ultra, base building, 5K/10K, champion ultra, onramp, 50K int/adv, marathon) |
| `ROCHE_SWAP_EFFORT_DICTIONARY_2026-04-10.md` | Canonical effort term mapping — mandatory for all workout descriptions |
| `ROCHE_SWAP_WORKOUT_EXECUTION_GUIDE_2026-04-10.md` | Execution protocols for every workout type (strides, hills, TM, easy/mod, Power Hour, fatigue resistance, combos) |
| `ROCHE_SWAP_12WK_MARATHON_PLAN_2026-04-10.md` | Quality bar: advanced 12-week marathon plan |
| `ROCHE_SWAP_PLANS_SUPPLEMENTARY_2026-04-10.md` | Quality bar: HM 6wk, track/vVO2 6wk, 100K-100mi 16wk |
| `ROCHE_SWAP_FUELING_REFERENCE_2026-04-10.md` | Carb tiers, hydration, caffeine, in-training fueling practice |
| `GREEN_COACHING_PHILOSOPHY_REFERENCE_NOTE_2026-04-10.md` | Jon Green: adaptive coaching, "plans written in pencil" |
| `DAVIS_MODERN_MARATHON_APPROACH_REFERENCE_NOTE_2026-04-10.md` | John Davis: 5 principles, ladder of support, three-phase periodization |
| `DAVIS_FIVE_PRINCIPLES_MARATHON_TRAINING_2026-04-10.md` | Davis: 4 components of marathon fitness, stress/recovery, full-spectrum training |
| `SSMAX_STEADY_STATE_MAX_REFERENCE_NOTE_2026-04-10.md` | SSmax = critical power = MLSS = LT2 |
| `COE_STYLE_TRAINING_REFERENCE_NOTE_2026-04-10.md` | Peter Coe: multi-pace, circuit training |
| `ADVANCED_EXERCISE_PHYSIOLOGY_SYNTHESIS_2026-04-10.md` | CP/W', HRV, biomechanical wear, Norwegian model |

### The Hierarchy (Single Species, Sliding Bottleneck)

There is no separate "elite" vs "recreational" hierarchy. One hierarchy governs all athletes — the bottleneck shifts based on training age:

1. Health → 2. Consistency → 3. Nutrition/fueling → 4. Easy volume → 5. Strides → 6. Threshold → 7. vVO2 → 8. Long run structure → 9. Strength → 10. Race-specific → 11. Heat → 12. Doubles → 13. Supplements → 14. Lactate monitoring

Early-development athletes are bottlenecked at items 1-4. Established athletes at items 6-10. The generator applies the same science at the appropriate dose.

## V2 Engine — Production Status

Plan Engine V2 is deployed and live behind a feature flag. V1 remains the default for all users. V2 is activated by passing `engine=v2` on the constraint-aware endpoint, gated to `admin`/`owner` roles.

### V2 Architecture

V2 is a ground-up rewrite of the plan generator, informed by modern coaching science (Davis, Green, Roche, Coe). It replaces V1's generation logic while preserving V1's intelligence infrastructure (FitnessBank, FingerprintParams, LoadContext, QualityGate).

| Component | File | Role |
|-----------|------|------|
| `engine.py` | `services/plan_engine_v2/engine.py` | Orchestrator — loads athlete data, builds phases, produces weeks |
| `pace_ladder.py` | `services/plan_engine_v2/pace_ladder.py` | Percentage-based pace ladder from RPI |
| `periodizer.py` | `services/plan_engine_v2/periodizer.py` | Phase structure (general → supportive → specific → taper) |
| `volume.py` | `services/plan_engine_v2/volume.py` | Long run staircase, volume targets, readiness gate |
| `workout_library.py` | `services/plan_engine_v2/workout_library.py` | 22+ workout types with concrete segments |
| `day_scheduler.py` | `services/plan_engine_v2/day_scheduler.py` | Assigns workout types to days (hard-easy, MLR spacing) |
| `models.py` | `services/plan_engine_v2/models.py` | V2 dataclasses (V2DayPlan, V2WeekPlan, V2PlanPreview, WorkoutSegment) |
| `plan_saver.py` | `services/plan_engine_v2/plan_saver.py` | Maps V2 output → TrainingPlan + PlannedWorkout DB rows |
| `router_adapter.py` | `services/plan_engine_v2/router_adapter.py` | Request mapping, FitnessBank/FingerprintParams/LoadContext loading, response stitching |

### V2 Key Differences from V1

| Aspect | V1 | V2 |
|--------|----|----|
| Phase model | Theme-driven (rebuild_easy, build_t, etc.) | Coaching periodization (general, supportive, specific, taper) |
| Workout output | Flat paces dict + description | Rich segments JSONB (warmup → work → cooldown with pace, distance, duration) |
| Long run | Single type per week | Three rotating types (easy progressive, threshold segments, fatigue resistance) + oscillation at peak |
| Volume control | `sustainable_peak_weekly` ceiling | `desired_peak_weekly_miles` (athlete decides peak) |
| Fueling | Not present | Automatic on all runs exceeding 90 minutes |
| Distance prescription | Single target | Ranges (min, max) for athlete self-selection |
| Effort language | Zone names | Effort-based descriptions (10K effort, easy/mod) with pace as secondary |
| Medium-long runs | Implicit | Explicit mid-week MLR slot with optimal spacing from quality/long days |
| Tune-up races | V1 planner handling | Surgical insertion preserving midweek quality, recovery long run post-race |
| Extension progression | N/A | Pace constant, duration grows within a block |
| `generation_method` | `"constraint_aware"` | `"v2"` |

### API Access

```
POST /v2/plans/constraint-aware?engine=v2&dry_run=true
```

Same request body as V1 (`ConstraintAwarePlanRequest`). V2 response is shape-compatible with V1 (same top-level keys: `success`, `plan_id`, `fitness_bank`, `model`, `prediction`, `weeks`, etc.) plus `"engine": "v2"`.

### Production Verification (April 11, 2026)

- V2 dry-run: 23-week marathon plan, 1208 total miles, 62.6 peak weekly miles
- Long run staircase: 14 → 16 → 18 → cutback → 20 → 21 → cutback → 18 → tune-up → 21 → cutback → taper
- W1 structure: rest, easy, threshold_cruise, easy_strides, medium_long, easy, long_easy
- V1 default path: unaffected, still generates correctly
- All containers healthy

### Coaching Science KB

V2 is grounded in 13 coaching science documents in `docs/references/`. See the "Coaching Science KB" table below.

### What's Next (V2 Rollout)

1. Founder live testing with `engine=v2` on real plan generation (not just dry-run)
2. 7-day monitoring: verify calendar display, detail views, exports all work with V2 segments
3. Beta athlete rollout
4. V1 archived after 4 weeks stable

## What's Next (V1 Engine — legacy)

- Wire limiter + primary quality emphasis from fingerprint bridge into session scheduling (deferred — V2 handles this)
- Archetype 14 (7-day) support (deferred — V2 handles this)
- Full P4 load context implementation (deferred — V2 handles this)

## Sources

- `docs/specs/PLAN_GENERATOR_ALGORITHM_SPEC.md` — **V2 algorithm spec (single source of truth for rewrite)**
- `docs/specs/N1_ENGINE_ADR_V2.md` — V1 requirements, blocking criteria, archetypes
- `docs/specs/N1_PLAN_ENGINE_SPEC.md` — V1 engine spec
- `docs/TRAINING_PLAN_REBUILD_PLAN.md` — phased build plan, operational status
- `docs/BUILDER_INSTRUCTIONS_2026-04-10_TRAINING_LIFECYCLE.md` — Training Lifecycle Product (Build/Maintain/Custom modes)
- `docs/specs/KB_RULE_REGISTRY_ANNOTATED.md` — 76 rules
- `docs/specs/WORKOUT_FLUENCY_REGISTRY_SPEC.md` — workout registry
- `docs/specs/PLAN_COACHED_OUTPUT_AND_LOAD_CONTRACT.md` — load contract
- `docs/references/` — 13 coaching science KB documents
- `apps/api/services/plan_framework/` — all framework code
