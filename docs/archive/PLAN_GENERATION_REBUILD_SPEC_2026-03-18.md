# Plan Generation Rebuild Specification

**Date:** 2026-03-18  
**Status:** APPROVED FOR IMPLEMENTATION  
**Authors:** Rook (primary), Vega (data layer audit), Northstar (systems audit)  
**Governing document:** `_AI_CONTEXT_/KNOWLEDGE_BASE/PLAN_GENERATION_FRAMEWORK.md`

---

## Summary

Three independent audits confirmed that the plan generation system has **three layers of failure**:

1. **Data layer** — wrong inputs reach the generator (bad RPI, inflated volume, missing race anchors)
2. **Generator engine** — the framework periodization logic is not implemented; phase metadata is dead code; two of four distances have incorrect workout selection
3. **Parallel systems** — three separate plan generators exist with no shared logic; constraint-aware produces the worst plans of any path

These are not independent bugs. Fixing any one tier without the others produces a system that generates structurally-valid garbage. All three tiers must be fixed in dependency order.

**Total estimated effort:** 5–7 focused sessions  
**Task count:** 28 tasks across 6 tiers (T0: 4, T1: 4, T2: 10, T3: 4, T4: 3, T5: 3)  
**Execution rule:** No tier begins until the previous tier's acceptance tests pass. No xfails on core acceptance tests.

---

## Tier 0 — Immediate: Crashing and Inverted Bugs

**Rationale:** These produce crashes or obviously wrong output today. Fix before any other work. Hours, not days.

---

### T0-1: Add 4-day weekly structure and fix `days_per_week` slot enforcement

**Problem:** `WEEKLY_STRUCTURES` in `generator.py` has keys 5, 6, 7 only. Any athlete requesting 4 days/week falls through to the 6-day template at line 948. Every week of every beginner plan has 6 workouts instead of 4.

**File:** `apps/api/services/plan_framework/generator.py`

**Changes:**

1. Add a 4-day structure to `WEEKLY_STRUCTURES`:
```python
4: {
    0: "rest",          # Monday
    1: "easy",          # Tuesday
    2: "rest",          # Wednesday
    3: "quality",       # Thursday
    4: "rest",          # Friday
    5: "easy_strides",  # Saturday
    6: "long",          # Sunday
},
```

2. In `_generate_workouts`, after selecting `structure`, validate the slot count matches `days_per_week`. If not, trim slots by priority: remove `easy_strides` slots first, then extra `easy` slots. Never remove `long`, `quality`, or `medium_long`.

**Acceptance test:** All 8 `sc-beginner-*` tests pass. `week.workouts.count == days_per_week` for every week.

---

### T0-2: Fix negative mileage in constraint-aware race week

**Problem:** Race week allocates race_distance + shakeout + strides first, then distributes remaining budget to easy runs. When race distance (26.2mi for marathon) exceeds the weekly budget, easy run distances go negative.

**File:** `apps/api/services/constraint_aware_planner.py`

**Change:** In race week construction, apply `max(0.0, remaining_budget)` before distributing to easy slots. If budget is exhausted after race + shakeout + strides, those days become rest days.

**Acceptance test:** `min(d.miles for d in race_week.days) >= 0` for all plans. The 3 `ca-beginner-*` failures on this must pass.

---

### T0-3: Fix medium long > long run inversion

**Problem:** `_scale_medium_long` is computed from weekly volume only (55mpw → 13mi). `_scale_long_run` for 10K/mid-tier plan peaks at 14mi and drops to 8mi in taper. Result: taper week has medium_long=13, long=8.

**File:** `apps/api/services/plan_framework/workout_scaler.py`

**Change:** In `_generate_week` in `generator.py`, after both runs are scaled, enforce the invariant:
```python
if medium_long_workout and long_run_workout:
    ml = medium_long_workout.distance_miles or 0
    lr = long_run_workout.distance_miles or 0
    if ml >= lr:
        medium_long_workout.distance_miles = max(lr - 2, lr * 0.75)
```

This is a hard post-scaler enforcement — it cannot be bypassed by any distance/tier/phase combination.

**Acceptance test:** Assert `medium_long_miles < long_run_miles` for every week across all 10 athletes × 4 distances × all generators. Zero exceptions.

---

### T0-4: Fix generate_custom NameError

**Problem:** At `generator.py:684`, `best_run` is referenced inside a conditional block that only executes if `recent_activities` is non-empty, but the `best_run` variable is used outside where it can be unset.

**File:** `apps/api/services/plan_framework/generator.py`

**Change:** Guard the reference: `if not paces and recent_activities:` block must have `best_run` properly scoped, or the outer block must check `if best_run is not None`.

**Acceptance test:** `generate_custom` does not raise NameError when no activities exist for the athlete.

---

## Tier 1 — Data Integrity

**Rationale:** Wrong inputs produce wrong plans regardless of generator quality. Fix data first.

---

### T1-1: Verify RPI confidence multiplier (regression hardening)

**Status:** Likely already correct — `fitness_bank.py` stores `best_race.rpi` directly from `_find_best_race`. Verify before treating as open work.

**File:** `apps/api/services/fitness_bank.py`

**Action:** Audit the `_find_best_race` call chain (lines 465–509). Confirm that the value stored as `best_rpi` is the raw RPI from the verified race with no confidence haircut applied. If a multiplier exists, remove it — confidence signals belong in the planner's trust decisions, not in the stored RPI value. If no multiplier exists, this task is closed as verified.

**Acceptance test:** An athlete with a verified 3:14 marathon produces an RPI that, when passed to `calculate_training_paces`, yields a marathon pace of ~7:27/mi ± 10 seconds. Add this as a regression test regardless of whether a fix was needed.

---

### T1-2: Verify peak_weekly_miles computation

**Problem:** `peak_weekly_miles` may include outlier weeks (single big week, race-week artifact) that inflate the volume tier classification.

**File:** `apps/api/services/fitness_bank.py`, `apps/api/services/mileage_aggregation.py`

**Change:** Audit `compute_peak_and_current_weekly_miles`. The peak should use a smoothed signal — not the single highest week ever, but the best 4-consecutive-week average (or a 4-week rolling max). A one-off 80-mile week in a sea of 45-mile weeks should not classify an athlete as a "high" tier athlete.

**Acceptance test:** A synthetic athlete with 12 weeks at 45mpw and 1 outlier week at 80mpw produces `peak_weekly_miles` in the 50-55 range, not 80.

---

### T1-3: Verify race anchor auto-population (regression hardening)

**Status:** Likely already wired — `_sync_anchor_from_authoritative_race_signals` is called inside `FitnessBankCalculator.calculate()`. Verify the call path is reachable on import before treating as open work.

**File:** `apps/api/services/fitness_bank.py` + Strava/Garmin import hooks

**Action:** Trace the import pipeline to confirm `FitnessBankCalculator.calculate()` is triggered (or the anchor sync is called directly) after a batch of activities is imported for an athlete. If the trigger is missing — i.e., the sync only fires when the FitnessBank is explicitly rebuilt but not during the initial import — add the post-import hook. If it is already wired, this task is closed as verified.

**Acceptance test:** An athlete who imports a verified race activity has a populated `AthleteRaceResultAnchor` row within the same transaction. Add this as a regression test regardless of whether a fix was needed.

---

### T1-4: Fix starter plan goal-date default

**Problem:** `starter_plan.py:205` defaults to `date.today() + timedelta(weeks=8)` when no goal date is provided. This gives new athletes an 8-week plan regardless of their fitness level or stated mileage. A 50mpw athlete with no race date gets an 8-week plan when they should get an open-ended base-building plan.

**File:** `apps/api/services/starter_plan.py`

**Change:** When `goal_date` is None, generate a base-building plan of appropriate length for the athlete's experience level rather than defaulting to 8 weeks toward a fictional race date. A beginner with no race goal gets a 12-week base block. An experienced athlete with no race goal gets an 18-week base/threshold cycle. The plan type should be `STANDARD` (not race-targeted) when no goal date is present.

**Acceptance test:** An athlete with `goal_event_date=None` who submits intake at 40mpw receives a plan >8 weeks with no `long_mp` workouts and no taper phase.

---

## Tier 2 — Generator Engine Rebuild

**Rationale:** The framework periodization logic must be implemented, not documented. This is the largest tier and the most impactful for plan quality.

### Architecture principle for all T2 changes

Every change in this tier must respect this constraint: `phase.allowed_workouts` and `phase.key_sessions` are the **authoritative source** for what can appear in a week. The if/else chains in `_get_quality_workout` are the *sequencing logic within* those constraints — not an override of them. After T2 is complete, it must be impossible for a workout type not in `phase.allowed_workouts` to appear in that phase.

**Cutback logic ownership:** `volume_tiers.py` owns the volume reduction math (`CUTBACK_RULES` — frequency and reduction percentage). The generator owns the workout *type* selection during a cutback week (e.g., drop quality sessions, keep long run). These are two separate concerns. Do not duplicate the cutback frequency/reduction logic in `generator.py` — call `volume_tiers.py`. After T2, there is one source of truth for cutback volume and one source of truth for cutback workout selection.

---

### T2-1: Wire phase.allowed_workouts and key_sessions into workout selection

**Problem:** `allowed_workouts` and `key_sessions` in `TrainingPhase` are defined per phase in `phase_builder.py` but never read by `generator.py`. The generator's if/else chains operate independently. This is the root cause of phase boundary violations (threshold appearing in base phase, intervals appearing in taper).

**File:** `apps/api/services/plan_framework/generator.py`

**Changes:**

1. In `_get_quality_workout`, prepend a guard:
```python
# Key sessions for this phase (framework constraint)
key = phase.key_sessions  # e.g. ["threshold_intervals", "threshold"]
allowed = set(phase.allowed_workouts)
```

2. The return value of `_get_quality_workout` must be a member of `key` when selecting primary quality, and a member of `allowed` when selecting secondary quality. If the current if/else logic would return something not in `allowed`, return the first item of `key` instead and log a warning.

3. Add a runtime assertion (debug mode only) that verifies the returned workout type is in `phase.allowed_workouts`. This surfaces any remaining violations during test runs.

**Acceptance test:** No plan across the full matrix contains a workout type that violates its phase's `allowed_workouts`. Assert this programmatically in the test matrix.

---

### T2-2: T-Block 6-step progression

**Problem:** The T-block implementation uses two states: `threshold_intervals` (weeks 1-2) and `threshold` (weeks 3+). The framework specifies a 6-step progression (6×5min → 5×6min → 4×8min → 3×10min → 2×15min → 30-40min continuous). The existing 4-step scaler approximation is reasonable but does not produce visible session-to-session progression that an athlete can track.

**File:** `apps/api/services/plan_framework/workout_scaler.py`

**Changes:**

Refactor `_scale_threshold_intervals` and `_scale_threshold_continuous` to accept `(week_in_phase, total_threshold_weeks)` and produce a progression that:

- Maps the 6 canonical steps proportionally to `total_threshold_weeks`
- Scales starting format by tier: Low = 4×4min start, Mid = 5×5min start, High = 6×5min start
- Ensures each week produces a structurally different session (different reps×duration combination)
- Continuous threshold sessions increase by 3-5 minutes per week, not all at once

Step mapping (for a 4-week threshold block, mid-tier):
```
Week 1: 5×5min (threshold_intervals)
Week 2: 4×7min (threshold_intervals)  
Week 3: 3×10min (threshold_intervals → transitioning)
Week 4: 20min continuous (threshold)
```

For a 6-week threshold block, add steps 4×8min and 2×15min between.

**Acceptance test:** In any threshold block with ≥3 weeks, every threshold session has a different `(reps, duration)` combination than the preceding week. Assert this in the test matrix.

---

### T2-3: MP in medium-long + MPProgressionPlanner

**Problem:** MP work only appears in the Sunday long run. The framework requires MP blocks inside the Tuesday medium-long on specific weeks (e.g., weeks 9 and 11 of an 18-week plan). Total MP mileage is not tracked against the 40-50mi minimum.

**Files:** `apps/api/services/plan_framework/generator.py`, new `apps/api/services/plan_framework/mp_progression.py`

**Changes:**

1. Create `MPProgressionPlanner` class in `mp_progression.py`:
```python
class MPProgressionPlanner:
    def build_sequence(self, tier: str, total_mp_weeks: int) -> List[MPWeek]:
        """
        Returns a week-by-week sequence for the MP block.
        Each MPWeek specifies:
          - long_type: "long_mp" | "long" (easy)
          - medium_long_type: "mp_touch" | "medium_long" (easy)
          - target_mp_miles: float (cumulative tracking)
        """
```

2. For a mid-tier marathon, the sequence should produce alternating Structure A (T + easy long) and Structure B (MP in long, no T) weeks, with MP also appearing in the medium-long on select Structure A weeks.

3. Track cumulative MP miles. For marathon plans with `peak_weekly_miles >= 40`, assert total MP miles >= 35 before taper begins.

4. In `generator.py`, replace `_will_week_have_mp_long` with a call to `MPProgressionPlanner.build_sequence()` for the MP-containing phases.

**Acceptance test:**  
- A mid-tier 18-week marathon plan produces ≥ 35 total MP miles before the taper phase.  
- At least 2 weeks have MP work inside the medium-long run (not only the long run).  
- No MP work appears in base or threshold phases.

---

### T2-4: Phase-boundary cutbacks

**Problem:** `is_cutback = week % cutback_freq == 0` is arithmetic, not structural. Cutbacks can land mid-phase (e.g., week 8 of a 12-week 10K plan interrupts the threshold block). The framework specifies cutbacks at phase transitions: after the base block, after the threshold block, after the MP introduction block.

**File:** `apps/api/services/plan_framework/generator.py`, `apps/api/services/plan_framework/phase_builder.py`

**Changes:**

1. In `phase_builder.py`, when building phases, explicitly designate the week *before* each phase transition as a cutback week. Store this in the phase metadata or as a separate list returned alongside the phases.

2. In `generator.py`, replace `week % cutback_freq == 0` with a lookup: `week in cutback_weeks` where `cutback_weeks` is derived from phase boundaries.

3. Cutback week behavior: keep the phase's primary key session at 70% of normal distance, eliminate secondary quality sessions entirely, reduce long run to approximately 70% of the preceding peak long run.

**Acceptance test:**  
- For an 18-week marathon plan, cutback weeks land at weeks 4, 8, 12, and 16 (matching phase boundaries), not at weeks 4, 8, 12, 16 by coincidence but by phase-boundary logic.  
- For a 12-week 10K plan, no cutback week interrupts the middle of the threshold progression.  
- Every cutback week retains exactly 1 quality session (the phase's primary key session, shortened).

---

### T2-5: Phase-aware weekly structure variants + lower secondary quality gate

**Problem:** `WEEKLY_STRUCTURES[6]` is static. Tuesday is always `medium_long` regardless of phase. On Structure B weeks (MP long run), Tuesday should be easy (recovery from the weekend MP effort). The secondary quality gate is `weekly_volume >= 55`, cutting off legitimate 45-50mpw athletes in race-specific phases.

**File:** `apps/api/services/plan_framework/generator.py`

**Changes:**

1. In `_get_workout_for_day`, when `structure_type == "medium_long"` and `is_mp_long_week == True`:
   - Return `"easy"` instead of `"medium_long"` (Structure B week — Tuesday is recovery, not medium-long)
   
2. Lower secondary quality gate from `weekly_volume >= 55` to `weekly_volume >= 40` for race-specific phases only.

3. For 5K and 10K race-specific phases, explicitly allow two quality sessions when `experience_level >= RECREATIONAL`, regardless of mileage.

**Acceptance test:**  
- On any MP-long week (Structure B) in a marathon plan, Tuesday is `easy`, not `medium_long`.  
- A 45mpw 10K athlete in race-specific phase receives 2 quality sessions per week (intervals + threshold maintenance).

---

### T2-6: Fix 10K interval pace — 5K pace, not 10K pace

**Problem:** `workout_scaler.py:882-883` labels race-specific 10K intervals as "10K race pace." The framework is explicit: VO2max sharpening in the 10K race-specific phase uses **5K pace**, not 10K pace. The purpose is to stress the VO2max system above race pace, not simulate the race.

**File:** `apps/api/services/plan_framework/workout_scaler.py`

**Change:**  
In `_scale_intervals_10k` (or equivalent function around line 875), change the race-specific interval pace label from `"10K_pace"` to `"5K_pace"` and update the description to: "5K effort — faster than 10K race pace to stress the VO2max system."

Also update the rep distance: 1200m at 5K pace is appropriate for VO2max development. Keep reps 4-6.

**Acceptance test:**  
- Race-specific 10K plans have intervals described as "5K effort" or "5K pace."  
- Validation contract updated: assert `10K_race_specific_intervals_pace == "5K_pace"`.

---

### T2-7: Medium-long run progression and taper reduction

**Problem:** `_scale_medium_long` returns the same distance for all weeks of a plan. It has no week-in-phase awareness and no taper reduction.

**File:** `apps/api/services/plan_framework/workout_scaler.py`

**Changes:**

Add `week_in_phase: int`, `total_phase_weeks: int`, `is_taper: bool`, and `is_race_week: bool` parameters to `_scale_medium_long`.

Apply progression:
```python
# Build ramp: 0–10% over the phase
build_factor = 1.0 + (week_in_phase / max(1, total_phase_weeks)) * 0.10
base_distance = volume_based_distance * build_factor

# Taper reduction
if is_race_week:
    return base_distance * 0.50
if is_taper:
    return base_distance * 0.70
```

**Acceptance test:**  
- In any plan ≥8 weeks, the medium-long distance in taper weeks is visibly less than in peak-phase weeks.  
- No week shows identical medium-long distance to both the preceding and following week (progression is visible).

---

### T2-8: Gate long_mp/long_hmp on experience + volume

**Problem:** `long_mp` and `long_hmp` are assigned to beginner athletes from week 2 onwards. A 15mpw beginner receives marathon-pace long runs.

**File:** `apps/api/services/plan_framework/generator.py`

**Change:**  
In `_get_long_run_type` and `_will_week_have_mp_long`, add guards:
```python
# MP long runs require:
# 1. Experience level INTERMEDIATE or above, OR weekly_miles >= 35
# 2. Week >= 50% through the plan (not in the first half)
# 3. Phase is marathon_specific or race_specific
if (
    experience_level < ExperienceLevel.INTERMEDIATE
    and (current_weekly_miles or 0) < 35
):
    return "long"  # plain easy long run

if week < ceil(total_weeks * 0.5):
    return "long"
```

**Acceptance test:** Beginner archetype produces zero `long_mp` or `long_hmp` sessions. Sub-3 aspirant (70mpw) receives `long_mp` from the marathon-specific phase onward.

---

### T2-9: Threshold session volume cap for low-mileage athletes

**Problem:** A 15mpw beginner receives 5.2mi threshold sessions (35% of weekly volume). The framework caps threshold at 10% of weekly mileage in a single session.

**File:** `apps/api/services/plan_framework/workout_scaler.py`

**Change:**  
Add a hard cap by experience level before returning from threshold scalers:
- `BEGINNER`: max threshold session = `min(computed, weekly_volume * 0.12, 3.5mi)`
- `RECREATIONAL`: max = `min(computed, weekly_volume * 0.15, 5.0mi)`
- `INTERMEDIATE` and above: existing Source B cap applies (10% of weekly volume)

**Acceptance test:** For every beginner-archetype plan, threshold session distance ≤ 3.5mi. For every athlete: `threshold_session_miles / weekly_miles <= 0.18`.

---

### T2-10: Long run floor from athlete history — all generators

**Problem:** `easy_long_floor_mi` from `FitnessBank.l30_max_easy_long_run_miles` is wired for the standard/semi-custom paths when DB context is available, but the `LONG_RUN_PEAKS` hard cap overrides it for athletes whose historical long runs exceed the table values.

**File:** `apps/api/services/plan_framework/workout_scaler.py`

**Change:**  
In `_scale_long_run`, when `easy_long_floor_mi` is provided:
```python
# Athlete history takes precedence over population-average caps
if easy_long_floor_mi is not None:
    peak_cap = max(LONG_RUN_PEAKS[goal][tier], easy_long_floor_mi * 1.05)
else:
    peak_cap = LONG_RUN_PEAKS[goal][tier]
```

This means a runner who routinely runs 18mi long runs will have their 10K plan's long run ceiling elevated to ~18.9mi, not capped at 14mi.

**Acceptance test:** A `high_mileage` archetype (peak_long=18mi) produces long runs ≥ 15mi during base/build phases in a 10K plan. The `LONG_RUN_PEAKS` value is a floor for beginners, not a ceiling for experienced athletes.

---

## Tier 3 — Constraint-Aware Convergence

**Rationale:** The constraint-aware path is the highest-tier product (it uses FitnessBank, N=1 signals, predictions) but produces the worst plans (no framework logic, no volume build, wrong workout types including "Marathon pace focus" weeks in 5K plans).

**Decision: Option A — Replace constraint-aware workout generation internals with the framework generator.**

Keep everything in `ConstraintAwarePlanner` that is not workout generation:
- FitnessBank signal reading
- Volume contracts (L30, D4)
- Counter-conventional notes
- Race predictions
- Tune-up event detection

Replace:
- `WeekThemeGenerator` → `PhaseBuilder`
- `WorkoutPrescriptionGenerator.generate_week()` → `PlanGenerator._generate_week()`
- The theme-rotation volume curve → proper build curve via `VolumeTierClassifier.calculate_volume_progression()`

---

### T3-1: Replace WeekThemeGenerator with PhaseBuilder

**File:** `apps/api/services/constraint_aware_planner.py`

**Change:**  
Instead of `self.theme_generator.generate(bank, race_distance, horizon_weeks)`, call:
```python
phases = PhaseBuilder().build_phases(
    distance=race_distance,
    duration_weeks=horizon_weeks,
    tier=tier.value,
)
weekly_volumes = VolumeTierClassifier().calculate_volume_progression(
    tier=tier,
    distance=race_distance,
    starting_volume=bank.current_weekly_miles,
    plan_weeks=horizon_weeks,
    taper_weeks=2,
)
```

The phase list and volume progression from the framework generator now drive the constraint-aware plan.

---

### T3-2: Route through a public WeekGenerator interface, not PlanGenerator._generate_week directly

**File:** `apps/api/services/plan_framework/generator.py`, `apps/api/services/constraint_aware_planner.py`

**Problem with direct call:** `PlanGenerator._generate_week` is a private method (underscore prefix). Calling it directly from the constraint-aware planner creates tight coupling that will break silently on any future refactor of the generator internals.

**Change:**  
Before wiring T3 into T2's output, extract the week-generation logic into a public, standalone function or class:

```python
# plan_framework/week_generator.py  (new file)
def generate_plan_week(
    week: int,
    phase: TrainingPhase,
    week_in_phase: int,
    weekly_volume: float,
    days_per_week: int,
    distance: str,
    tier: str,
    paces: Optional[TrainingPaces],
    athlete_ctx: Dict[str, Any],
    easy_long_floor_mi: Optional[float],
    # ... other parameters
) -> List[GeneratedWorkout]:
    """Public interface consumed by both PlanGenerator and ConstraintAwarePlanner."""
```

`PlanGenerator._generate_week` becomes a thin wrapper calling this function. The constraint-aware planner calls the same public function. This makes the T3 convergence a stable API contract, not a fragile internal dependency.

**Note:** This extraction is a prerequisite for T3-2. Do T3-2 after T2 is complete and the week-generation logic is stable enough to extract cleanly.

Pass `easy_long_floor_mi = bank.average_long_run_miles` to ensure the history floor is always applied.

---

### T3-3: Populate WeekPlan.theme from PhaseBuilder output

**File:** `apps/api/services/constraint_aware_planner.py`

**Change:**  
Each `WeekPlan` must have its `theme` (or an equivalent phase name) populated from the `TrainingPhase.name` for that week. This eliminates the `[?]` phase display issue.

---

### T3-4: Fix constraint-aware W1 long run cap

**File:** `apps/api/services/constraint_aware_planner.py`

**Change:**  
Week 1 long run = `min(computed_from_phase_curve, bank.current_weekly_miles / bank.days_per_week * 2.0, 10.0)`.  
This prevents a beginner at 15mpw from receiving a 10mi long run in week 1.

**Combined acceptance test for all T3:**
- All `ca-*` tests pass with zero `[?]` phase names
- Constraint-aware marathon plan produces ≥ 35 total MP miles
- Constraint-aware 10K plan has VO2max intervals in race-specific phase at 5K pace
- Volume builds across all constraint-aware plans: `max_week_volume > entry_week_volume * 1.10`

---

## Tier 4 — Legacy Path Cleanup

**Rationale:** Three parallel plan generators exist. Until the new generator is fully validated, don't delete the legacy paths. But gate them clearly so no new plan creation flows through them.

---

### T4-1: Freeze /v1/training-plans plan creation

**File:** `apps/api/routers/` (wherever the v1 endpoint lives)

**Change:**  
The `/v1/training-plans` **POST** endpoint (which calls `ArchetypePlanGenerator`) must be disabled or redirected to the canonical engine. Add a response header `X-Plan-Generator: archetype-legacy` to any plan created through this path so it can be identified. The endpoint itself should return a 410 Gone or 301 redirect to v2.

**Important:** Only freeze the creation (POST) endpoint. The v1 **read and calendar** endpoints (`GET /v1/training-plans`, `/v1/training-plans/{id}`, calendar/schedule reads) may still be actively used by web frontend code during migration. Do not break those. Leave them intact and note them in migration tracking.

**Acceptance test:** No new `TrainingPlan` rows are created via `ArchetypePlanGenerator` after this change. Existing plan reads still return 200.

---

### T4-2: Deprecate principle_plan_generator

**File:** `apps/api/services/principle_plan_generator.py`

**Change:**  
Add a deprecation warning at the entry point of `generate_principle_based_plan`. Identify all callers (in `ai_coaching_engine` or elsewhere). Replace callers with canonical engine calls. Mark the file with a deprecation header.

**Do not delete** until callers are confirmed migrated and no active plans reference it.

---

### T4-3: Remove dead quality_focus code

**File:** `apps/api/services/workout_prescription.py`

**Change:**  
Remove `self.quality_focus = QUALITY_FOCUS.get(...)` (line 495) and the `QUALITY_FOCUS` constant if it is only referenced here. This is pure dead code — it was never read after being set.

---

## Tier 5 — Test Infrastructure Overhaul

**Rationale:** The existing test matrix gives false confidence. It has 119 xfails for core distances and only covers `generate_standard`. Passing CI does not prove coaching correctness. This must be fixed after the engine is correct, not before.

---

### T5-1: Convert 7.5 assertions to hard test failures

**File:** `apps/api/tests/test_full_athlete_plan_matrix.py`

All 10 assertions from Section 7.5 of the framework document must be hard `pytest.fail()` calls, not xfails, for the following generator-distance combinations:

| Assertion | Standard | Semi-custom | Constraint-aware |
|-----------|----------|------------|-----------------|
| medium_long < long_run | ALL | ALL | ALL |
| No negative mileage | ALL | ALL | ALL |
| workout_count == days_per_week | ALL | ALL | ALL |
| LR ≥ 12mi for 50mpw+ athletes (base/build) | ALL | ALL | ALL |
| Volume builds ≥ 10% | ALL | ALL | ALL |
| Threshold ≤ 18% of weekly volume | ALL | ALL | ALL |
| No long_mp for beginners | ALL | ALL | ALL |
| Marathon: ≥ 35 total MP miles | marathon | marathon | marathon |
| No [?] phase names | N/A | N/A | ALL |
| T-block progression visible | ALL | ALL | N/A |

---

### T5-2: Add 10K pace contract assertion

**File:** `apps/api/tests/test_plan_validation_matrix.py`

Add a new test class `TestDistancePaceContracts` with:
- `test_10k_race_specific_intervals_are_5k_pace`: for every race-specific week in a 10K plan, any intervals workout must have `pace_label == "5K_pace"` or equivalent in its segments.
- `test_marathon_mp_cumulative_minimum`: total MP miles in marathon plans with `tier in (mid, high)` must reach ≥ 35mi.

---

### T5-3: Reduce xfail footprint

**File:** `apps/api/tests/test_plan_validation_matrix.py`

The current `xfail` markers on `marathon-mid-18w-6d` and `marathon-mid-18w-5d` in `TestPlanValidationMatrixStrict` should be reviewed after Tier 2 is complete. If the engine now correctly generates these plans, the xfails must be converted to passing tests. Any remaining xfails must have a documented reason in the test itself explaining *why* the behavior is acceptable and *when* the xfail will be lifted.

---

## Acceptance Gates by Tier

| Tier | Gate |
|------|------|
| T0 | `sc-beginner-*` 8 tests pass, no negative mileage, no medium_long ≥ long_run |
| T1 | Spot-check RPI for known athletes, race anchor present after import, starter plan correct |
| T2 | Full matrix: all 10 assertions green for standard + semi-custom generators, 10K pace contract passes |
| T3 | Full matrix: all 10 assertions green for constraint-aware, `[?]` phase names zero, volume builds |
| T4 | No new plans created via legacy paths |
| T5 | CI green with zero xfails on core distance/generator combinations |

---

## File Change Summary

| File | Tiers Touching It |
|------|-------------------|
| `services/fitness_bank.py` | T1-1, T1-2, T1-3 |
| `services/starter_plan.py` | T1-4 |
| `services/plan_framework/generator.py` | T0-1, T0-4, T2-1, T2-4, T2-5, T2-8 |
| `services/plan_framework/workout_scaler.py` | T0-3, T2-2, T2-6, T2-7, T2-9, T2-10 |
| `services/plan_framework/phase_builder.py` | T2-4 |
| `services/plan_framework/mp_progression.py` | T2-3 (new file) |
| `services/plan_framework/constants.py` | T2-10 (LONG_RUN_PEAKS annotation) |
| `services/constraint_aware_planner.py` | T0-2, T3-1, T3-2, T3-3, T3-4 |
| `services/workout_prescription.py` | T4-3 |
| `services/principle_plan_generator.py` | T4-2 |
| `routers/` (v1 plans endpoint) | T4-1 |
| `tests/test_full_athlete_plan_matrix.py` | T5-1 |
| `tests/test_plan_validation_matrix.py` | T5-2, T5-3 |

---

## What Builders Must Not Do

1. **Do not tune tests to pass the code.** If an assertion fails, fix the code, not the test.
2. **Do not add xfails to silence failures in Tier 5.** A failing test means the plan is wrong.
3. **Do not implement Tier 3 before Tier 2 is complete.** The constraint-aware path will consume `generate_plan_week()` from the public `plan_framework/week_generator.py` interface — that function must be correct and extracted first.
4. **Do not use `easy_long_floor_mi` only when DB is available.** For athletes with a FitnessBank object (even in tests), the floor must always be applied.
5. **Do not remove the `allowed_workouts` enforcement check once added.** Future phases that add new allowed workout types must update `phase_builder.py`, not bypass the enforcement.

---

*This spec is the implementation contract. Every change must trace to a finding in this document or in `PLAN_GENERATION_FRAMEWORK.md Part 7`. No speculative improvements.*
