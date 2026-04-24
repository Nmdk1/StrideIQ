# N=1 Plan Engine — Build Execution Plan

**Created:** 2026-03-28
**Spec:** `docs/specs/N1_PLAN_ENGINE_SPEC.md`
**Status:** Phase 0 COMPLETE. Phase 1 IN PROGRESS.

---

## Origin

Founder directive: 10+ agents failed to produce a single usable plan.
All existing generators (archetype, semi-custom, KB-driven, principle,
starter) have been deleted. The codebase is clean for a rebuild.

**Conversation → Scope → Spec path:**
1. Founder reviewed a failed plan from a prior session and identified systemic
   issues: generators invented rules, adhered to population averages, ignored
   the athlete's actual data and the KB.
2. Founder specified the vision: one engine, all distances, all levels, N=1.
3. Founder dictated domain-specific rules:
   - Long runs don't begin below 14mi for marathon. Below that is not a long run.
   - For sub-3:45 marathoners, cap long run at 20mi.
   - Medium-long = 75% of long run, hard cap 15mi.
   - MP progression is N=1 (not a fixed 4mi → 8mi → 14mi ladder — that's a
     session-terminating offense).
   - Abbreviated builds (≤5w): no phases, no cutbacks, all systems touched
     simultaneously with progressive overload.
   - 5K advanced: 200/300m reps at 1500m pace (ceiling work).
   - T-block is a 6-step progression, scaled by tier.
   - Readiness gate: marathon requires 12mi capability BEFORE starting.
   - Couch-to-10K: walk/run progression for day-one athletes (specified verbatim).
4. Spec written: `docs/specs/N1_PLAN_ENGINE_SPEC.md` (435 lines).
5. Phase 0 executed: 45 files deleted (~16,920 lines), CI green.

---

## Completed Work

### Phase 0 — Cleanup (DONE)
- Deleted 6 generator modules, 9 JSON archetypes/workouts, 3 generated HTMLs,
  3 eval scripts, 15 test files (~16,920 lines total).
- Stubbed `constraint_aware_planner.generate_plan()` → `NotImplementedError`.
- Deprecated `/v2/plans/standard`, `/semi-custom`, `/custom` → 501.
- Admin starter plan regen → 501.
- xfailed ~190 tests that depend on old generators or stubbed endpoints.
- CI green: 3937 passed, ~190 xfailed, 0 failures.
- Commits: `bccbae8` (cleanup), `dfe2037` (CI fix).

---

## Phase 1 — Build the Engine

### Target file
`apps/api/services/plan_framework/n1_engine.py`

### Wiring point
`apps/api/services/constraint_aware_planner.py` → `generate_plan()` method,
line 334 (currently raises `NotImplementedError`).

The existing code in `generate_plan()` (lines 230-332) already resolves:
- `bank` (FitnessBank) — athlete's proven capabilities
- `intake` overlay — cold-start self-reports
- `load_ctx` — L30 data from load context
- `volume_contract` — applied peak, band, clamp info
- `starting_vol` — highest of trailing avg, 8w median, last complete week
- `days_per_week` — from intake or bank rest day patterns
- `_current_lr` — best of L30, bank, or derived from volume
- `_experience` — mapped from ExperienceLevel enum
- `horizon_weeks` — weeks until race
- `plan_start` — normalized to Monday

The engine receives these resolved values and returns `List[WeekPlan]`.

### Output data structures (already exist)
- `WeekPlan` — `apps/api/services/workout_prescription.py` line 270
- `DayPlan` — `apps/api/services/workout_prescription.py` line 243
- `ConstraintAwarePlan` — `apps/api/services/constraint_aware_planner.py` line 116

### Supporting infrastructure (already exists)
- `calculate_paces_from_rpi(rpi)` → `{"easy": 8.5, "threshold": 6.5, ...}` (min/mi floats internally; display uses athlete's preferred units via `useUnits()`)
- `format_pace(pace_minutes)` → `"6:30"` string
- `WorkoutStructure` dataclass + `THRESHOLD_STRUCTURES`, `INTERVAL_STRUCTURES`, `MP_LONG_RUN_STRUCTURES`
- `ExperienceLevel` enum: BEGINNER, INTERMEDIATE, EXPERIENCED, ELITE

### Build steps (in order)

#### Step 1 — Athlete State Resolution
**Input:** bank, intake, load_ctx, volume_contract
**Output:** `AthleteState` dataclass with all resolved fields from spec §3.1

This is mostly done by the existing code in `generate_plan()`. The engine
function signature receives these pre-resolved values. The engine adds:
- `training_recency` (BUILDING/MAINTAINING/REBUILDING/NEW) from bank fields
- `easy_pace_per_mile` from RPI or conservative default
<!-- Note: easy_pace_per_mile is an internal engine field. Verify if renamed in canonical units migration. -->
- Readiness gate check (marathon: current_lr must reach 12mi before starting)

#### Step 2 — Phase Schedule
**Input:** AthleteState, race_distance, horizon_weeks
**Output:** `List[PhaseWeek]` — ordered list of (week_number, phase_name, is_cutback)

Rules from spec §3.2:
- Full/medium/short plan tables by distance
- Abbreviated builds (≤5w): all weeks = "peak", no cutbacks
- Readiness gate enforcement

#### Step 3 — Volume and Long Run Curves
**Input:** AthleteState, phase_schedule
**Output:** per-week targets: `(weekly_miles, long_run_miles, is_cutback)`

Volume curve rules (spec §3.3):
- Start at `current_weekly_miles`, ramp linearly to peak
- Tier-based step ceiling: 6-8 mi/week for HIGH/ELITE
- Cutback: -25% at phase boundaries
- Taper: -30% / -50% / race-week minimal
- No 10% rule

Long run curve rules (spec §3.3 + KB 03):
- Start: L30_non_race_max + 1mi
- Build: +2mi/week (non-cutback), +3 for experienced
- Cutback: 60-70% of prior peak long
- Ceilings: marathon 22mi (20mi for sub-3:45), half 16-18mi, 10K 18mi, 5K 15mi
- Marathon minimum 14mi (below that is just a run)
- Long run must be meaningfully above daily average
- MLR = 75% of long run, hard cap 15mi

#### Step 4 — Quality Session Scheduling
**Input:** AthleteState, phase_schedule, distance
**Output:** per-week quality prescription: `List[(workout_type, structure_name)]`

Rules from spec §3.4 + KB 03:
- Base phase: NO quality. Strides and hills only. (Exception: intervals for
  short-distance athletes in base.)
- Never ramp volume AND quality simultaneously
- Max 2 quality/week. Never 3.
- Quality → easy/recovery before next quality
- Saturday before Sunday long = always easy
- Distance-specific focus:
  - 5K: VO2 intervals primary, threshold secondary, 200/300 reps at 1500 pace (advanced)
  - 10K: Threshold primary, VO2 secondary, 10K rhythm in peak
  - Half: T-block → HMP in long runs → dress rehearsal
  - Marathon: T-block → MP integration → cumulative MP ≥ 40mi before taper
- T-block 6-step progression scaled by tier
- MP progression: N=1 (not a fixed ladder)

#### Step 5 — Day-by-Day Assembly
**Input:** weekly targets, quality prescription, days_per_week, paces
**Output:** `List[WeekPlan]`

Rules from spec §3.5:
1. Place long run (Sunday or athlete-specified)
2. Place rest (Monday or athlete-specified)
3. Place quality sessions with spacing rules
4. Saturday before Sunday long = always easy
5. Fill remaining: easy / medium-long / recovery
6. MLR only for 40+ mpw athletes; 15mi hard cap
7. Structure A/B for marathon/half in build/peak
8. Trim: easy days first, then MLR; preserve long + quality + rest
9. Race day / tune-up handling

### After engine build
- Wire into `constraint_aware_planner.generate_plan()` replacing the
  `NotImplementedError` raise.
- Re-enable downstream code (race day injection, tune-up insertion,
  counter-conventional notes, prediction, final ConstraintAwarePlan assembly).
- The dead code that was removed after the raise (race day, tune-ups,
  notes, predictions, return) needs to be restored from git history
  (`bccbae8~1`) when wiring.

---

## Phase 2 — Deploy + Validate

- Generate plans for founder's account first.
- Run `eval_realistic_athletes.py` synthetic population.
- Founder qualitative review.
- Deploy to production.

---

## Phase 3 — Variant Dropdown (future)

Wire workout registry (36 approved variants) to plan output. Frontend dropdown
filtered by build_context_tags, weekly stimulus ledger, contraindications.

---

## Phase 4 — Adaptive Re-Plan (future)

"Coach noticed..." trigger system. Diff engine. Athlete approval flow.

---

## Key Files Reference

| File | Role |
|------|------|
| `docs/specs/N1_PLAN_ENGINE_SPEC.md` | Product/engineering spec (435 lines) |
| `docs/specs/N1_ENGINE_BUILD_PLAN.md` | THIS FILE — execution plan |
| `apps/api/services/plan_framework/n1_engine.py` | Engine (to be created) |
| `apps/api/services/constraint_aware_planner.py` | Orchestrator (wire point) |
| `apps/api/services/fitness_bank.py` | N=1 data source |
| `apps/api/services/workout_prescription.py` | DayPlan, WeekPlan, pace utils, workout structures |
| `apps/api/services/plan_framework/load_context.py` | L30 baselines |
| `apps/api/services/rpi_calculator.py` | RPI → training paces |
| `apps/api/services/plan_quality_gate.py` | Structural + coaching validation |
| `_AI_CONTEXT_/KNOWLEDGE_BASE/03_WORKOUT_TYPES.md` | KB: stress taxonomy, sizing rules, spacing |

---

## Founder Rules (non-negotiable)

1. Long runs never begin below 14mi for marathon programs.
2. Sub-3:45 marathoners: 20mi long run cap.
3. MP progression is N=1 — no fixed population ladder.
4. MLR = 75% of long run, 15mi hard cap.
5. No 10% weekly volume rule. The spike rule is single-session.
6. Abbreviated builds (≤5w): no phases, no cutbacks, all systems simultaneously.
7. 5K advanced: 200/300m reps at 1500m pace.
8. T-block: 6 steps, scaled by tier.
9. Marathon readiness: must be able to do 12mi BEFORE starting.
10. Day-one athletes: Couch-to-10K walk/run progression (see spec §7).
11. The athlete decides, the system informs. Never auto-apply.
12. Suppression over hallucination. If uncertain, say nothing.
13. CI green before moving to next task. Always.

---

## Commit Protocol

All commits touching `plan_framework/` or `routers/plan_generation.py` must
include `P0-GATE: GREEN` in the commit message. Watch CI until green before
proceeding.
