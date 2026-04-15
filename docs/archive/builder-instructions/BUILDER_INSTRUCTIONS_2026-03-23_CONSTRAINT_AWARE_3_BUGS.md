# Builder Instructions: 3 Systemic Constraint-Aware Plan Bugs

**Priority:** P0 — every plan generated via constraint-aware is broken for 75% of athletes  
**Date:** 2026-03-23  
**Author:** Top Advisor (Vega)  
**Evidence:** Production diagnosis on all 16 athletes. Full data below.

---

## Context

The constraint-aware planner (`apps/api/services/constraint_aware_planner.py`) is a **completely separate code path** from the framework `PlanGenerator` (`apps/api/services/plan_framework/generator.py`). All the P1-P3 improvements (long-run progression, weighted easy fill, narrative) only live in PlanGenerator. Constraint-aware uses `WorkoutPrescriptionGenerator` from `apps/api/services/workout_prescription.py` instead.

The founder generated a 10K plan via constraint-aware. Every pace was 50-60 sec/mi too slow (threshold 7:00/mi when it should be ~6:10). The baseline volume was 114 mpw when the athlete runs ~55-65 mpw. The plan had zero intervals for a 10K. The 5K plan had 25mi long runs with marathon pace sessions.

**Root cause chain:**
1. No `AthleteRaceResultAnchor` → FitnessBank estimates RPI → gets it wrong (47.7 vs ~51.5)
2. FitnessBank `peak_weekly_miles` is inflated → constraint-aware trusts it → 114 mpw volume
3. `WorkoutPrescriptionGenerator` produces threshold-only quality work for 10K → no VO2/interval work

---

## Production Evidence

```
Total athletes: 16
Athletes with race anchors: 4 (UltraRunner26, Larry, Belle, Adam Stewart)
Athletes WITHOUT anchors who have activity data: 4 (founder 10 races, Jim 125 acts, Mark 877 acts, BHL 114 acts)

Founder's constraint-aware plans (ALL use wrong data):
  RPI=47.7 (should be ~51.5 from 39:12 10K PR)
  Vol=114 mpw (should be ~55-65)
  Easy pace: 8:38-8:48/mi (should be ~7:45-8:00)
  Threshold: 7:00/mi (should be ~6:10-6:15)

Athletes with race-tagged activities: founder (10 races), Belle (1 race)
Race anchors in DB: 12 rows — but NONE for founder despite 10 tagged races
```

---

## Bug 1: Race Activities Never Create Race Anchors

### Problem

Activities can be tagged `workout_type = "race"` in the Activity table. The `AthleteRaceResultAnchor` table stores the race result used for pace calculation. **Nothing connects them.** An athlete can have 10 tagged races and still get default/estimated RPI because `AthleteRaceResultAnchor` is empty for them.

The founder tagged 10 races during activity review. Zero anchors exist. The constraint-aware planner calls `get_fitness_bank()` → `FitnessBankCalculator.calculate()` → `_find_best_race()`. This function DOES detect races from activities (line 666-668 in fitness_bank.py: `if is_race and distance_type: rpi = calculate_rpi(...)`). So it's finding SOME race data — but the RPI comes out as 47.7 instead of ~51.5.

**Two sub-issues:**

**1a.** The RPI returned from `_find_best_race` is `best_race.rpi * best_race.confidence` (fitness_bank.py line 731-732). If confidence is < 1.0, the returned RPI is **lower than the actual race performance.** This is mathematically wrong — confidence should affect **which race is selected**, not reduce the RPI value. A 39:12 10K is a 39:12 10K regardless of confidence. This single multiplication could explain 47.7: if the race RPI is ~53 and confidence is ~0.9, then 53 * 0.9 ≈ 47.7.

**1b.** Even if the FitnessBank detects races from activities, the `AthleteRaceResultAnchor` table should be populated so that other systems (pace profile, onboarding, coach) can use the same data. Currently it's only populated by the onboarding flow or admin action.

### Fix

**1a — Stop multiplying RPI by confidence:**

```python
# fitness_bank.py line 731-732
# BEFORE:
return best_race.rpi * best_race.confidence, best_race

# AFTER:
return best_race.rpi, best_race
```

Confidence should be used in the selection/weighting logic (which race is "best"), not as a multiplier on the returned RPI. The Daniels formula already accounts for the actual performance — multiplying by 0.9 makes a 39:12 10K runner look like a 43:30 runner.

**1b — Auto-populate `AthleteRaceResultAnchor` from race activities:**

Add a function (in `fitness_bank.py` or a new small module) that:
1. Queries activities with `workout_type = "race"` for the athlete
2. Groups by distance bucket (5K, 10K, half, marathon) using `distance_m`
3. For each distance, finds the best (fastest) performance
4. Upserts into `AthleteRaceResultAnchor`

Call this:
- During `get_fitness_bank()` (lazy population)
- During activity sync (when a new race is detected)
- As a one-time backfill for existing athletes

**Verification:** After fix, founder's `AthleteRaceResultAnchor` should contain their 10K at 39:12. `FitnessBank.best_rpi` should be ~51.5, not 47.7. All constraint-aware paces shift by ~50 sec/mi faster.

---

## Bug 2: Peak Weekly Miles Still Inflated in FitnessBank

### Problem

`FitnessBank.peak_weekly_miles` is 114 for the founder. The founder does not run 114 mpw. This value drives `baseline_weekly_volume_km` on saved plans (router line 2145-2146: `peak.weekly_miles * 1.609`).

FitnessBank DOES use `get_canonical_run_activities()` for dedup (line 396-410). However, `peak_weekly_miles` is an **all-time peak** computed from the deduplicated activity set. If the dedup is working correctly, 114 mpw should be impossible for this athlete.

### Diagnosis needed

Run this on production to verify:

```python
from services.fitness_bank import FitnessBankCalculator, get_fitness_bank
from database import SessionLocal

db = SessionLocal()
bank = get_fitness_bank("4368ec7f-c30d-45ff-a6ee-58db7716be24", db)
print(f"peak_weekly_miles: {bank.peak_weekly_miles}")
print(f"current_weekly_miles: {bank.current_weekly_miles}")
print(f"recent_8w_median: {bank.recent_8w_median_weekly_miles}")
print(f"recent_16w_p90: {bank.recent_16w_p90_weekly_miles}")
print(f"best_rpi: {bank.best_rpi}")
print(f"constraint: {bank.constraint_type}")
db.close()
```

If `peak_weekly_miles` is still 114 after dedup, the dedup is not catching all duplicates. Check:
- Are there Strava + Garmin activities on the same day/time that aren't being collapsed?
- Is `get_canonical_run_activities` using `require_trusted_duplicate_flags=False` correctly?
- What does `dedupe_meta` show? How many pairs were collapsed?

### Fix

If dedup is working but peak is legitimately 114 from a historical week: the constraint-aware planner should use **recent peak** (e.g. 8-week or 16-week), not **all-time peak**, for volume targeting. The volume contract already has `recent_8w_median_weekly_miles` and `recent_16w_p90_weekly_miles` — use those instead of the all-time peak for `baseline_weekly_volume_km`.

If dedup is NOT catching the duplicates: trace the specific week that produces 114 mpw and find the duplicate activities.

---

## Bug 3: Constraint-Aware Plans Ignore Distance-Specific Workout Rules

### Problem

The constraint-aware planner uses `WorkoutPrescriptionGenerator` (from `apps/api/services/workout_prescription.py`), NOT `PlanGenerator` (from `apps/api/services/plan_framework/generator.py`). 

The framework `PlanGenerator` has extensive distance-specific logic:
- `_get_quality_workout`: 5K/10K → intervals in race-specific phase; marathon/half → threshold variants
- `_get_long_run_type`: marathon → `long_mp`; half → `long_hmp`; 10K/5K → easy long only
- Phase builder: separate phase graphs per distance
- Cutback quality: 5K → repetitions; 10K → strides; marathon/half → easy_strides

`WorkoutPrescriptionGenerator` has SOME distance awareness (long-run caps, `quality_focus`, `use_mp_long_runs`) but the production output shows:
- **10K plan:** All quality sessions are threshold. Zero intervals. Zero VO2max work.
- **5K plan:** Has `long_mp` (marathon pace) sessions and 25mi long runs.
- **Half plan:** 21mi long runs every week with no progression.

### Fix

`WorkoutPrescriptionGenerator.generate_week()` needs distance-specific workout selection that matches what `PlanGenerator._get_quality_workout()` does:

| Distance | Base-speed phase | Threshold phase | Race-specific phase |
|----------|------------------|-----------------|---------------------|
| 5K | reps/hills/strides | threshold_intervals → threshold | **intervals** (800/1000m) |
| 10K | reps/hills/strides | threshold_intervals → threshold | **intervals** (1000/1200m) |
| Half | hills/strides | threshold_intervals → threshold | threshold + **long_hmp** |
| Marathon | hills/strides | threshold_intervals → threshold | threshold + **long_mp** |

Rules that must be enforced:
- **5K/10K:** No `long_mp`, no marathon pace work. Long runs capped at 15mi (10K) / 13mi (5K).
- **5K/10K race-specific:** Must include interval/VO2 work, not threshold-only.
- **Half:** No `long_mp`. `long_hmp` in race-specific. Long run cap ~20mi.
- **Marathon:** `long_mp` in marathon-specific/race-specific. Long run progresses to ~22-24mi.

### Verification

Generate constraint-aware plans for all 4 distances with the founder's profile. Verify:
- 10K plan has interval workouts in weeks 3+
- 5K plan has no marathon pace sessions and no 25mi long runs
- Half plan has HMP work and long run progression (not 21mi every week)
- Marathon plan is structurally sound (already closest to correct)

---

## Execution Order

1. **Bug 1a first** (RPI confidence multiplier) — one line change, immediate pace fix for all athletes
2. **Bug 1b** (auto-populate anchors from race activities) — ensures correct RPI source data
3. **Bug 2** (volume verification + fix) — diagnose first, then fix based on findings
4. **Bug 3** (distance-specific workouts) — largest scope but bounded; match WorkoutPrescriptionGenerator behavior to PlanGenerator's distance rules

## One-Time Backfill

After Bug 1b is implemented, run a backfill for all athletes with race-tagged activities:
- Founder: 10 races
- Belle: 1 race  
- Any future athletes with synced race data

## CI / Tests

- Add test: `test_race_activity_creates_anchor` — tag activity as race, verify anchor is created
- Add test: `test_rpi_not_multiplied_by_confidence` — verify `_find_best_race` returns raw RPI
- Add test: `test_10k_constraint_aware_has_intervals` — generate 10K plan, verify interval workouts exist
- Add test: `test_5k_no_marathon_pace_work` — generate 5K plan, verify no `long_mp` or `mp_touch`

---

## Files to Change

| File | Bug | Change |
|------|-----|--------|
| `apps/api/services/fitness_bank.py:731-732` | 1a | Remove `* best_race.confidence` from return |
| `apps/api/services/fitness_bank.py` (new function) | 1b | `auto_populate_race_anchor(athlete_id, db)` |
| `apps/api/tasks/` or `apps/api/services/` | 1b | Call auto-populate on sync + backfill script |
| `apps/api/services/fitness_bank.py` | 2 | Verify peak_weekly_miles; potentially use recent peak |
| `apps/api/routers/plan_generation.py:2145-2146` | 2 | Use recent peak not all-time for baseline_weekly_volume_km |
| `apps/api/services/workout_prescription.py` | 3 | Distance-specific workout selection in `generate_week` |
| `apps/api/tests/` | All | New tests per CI section above |
