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

## Key Decisions

- **Diagnosis-first:** Plan generation starts with diagnosing the athlete, not selecting a template
- **KB-grounded:** Every plan decision traces to an annotated rule
- **RPI-only predictions:** Race predictions and training paces come from the individual performance model, never population formulas
- **Athlete agency within guardrails:** Variant dropdown with 38 variants, phase-appropriate filtering
- **No silent swaps:** Adaptations require explicit approval

## Known Issues

- **`phase_week` not populated:** Phase context must be derived, not read directly
- **Fingerprint bridge partial consumption:** Only `cutback_frequency` and `quality_spacing_min_hours` are consumed; `limiter` and `primary_quality_emphasis` are computed but not wired to session scheduling
- **7-day archetype (ID 14):** Requires lifting the `max(3, min(6, ...))` clamp in `constraint_aware_planner.py`

## What's Next

- Wire limiter + primary quality emphasis from fingerprint bridge into session scheduling
- Archetype 14 (7-day) support
- Full P4 load context implementation (fields: `target_duration_hours`, RPE, nutrition JSONB)

## Sources

- `docs/specs/N1_ENGINE_ADR_V2.md` — requirements, blocking criteria, archetypes
- `docs/specs/N1_PLAN_ENGINE_SPEC.md` — engine spec
- `docs/TRAINING_PLAN_REBUILD_PLAN.md` — phased build plan, operational status
- `docs/specs/KB_RULE_REGISTRY_ANNOTATED.md` — 76 rules
- `docs/specs/WORKOUT_FLUENCY_REGISTRY_SPEC.md` — workout registry
- `docs/specs/PLAN_COACHED_OUTPUT_AND_LOAD_CONTRACT.md` — load contract
- `apps/api/services/plan_framework/` — all framework code
