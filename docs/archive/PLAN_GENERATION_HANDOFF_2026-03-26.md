# Plan Generation — Full Technical Handoff
**Date:** 2026-03-26  
**State:** CI green. Data infrastructure fixed. Plan prescription logic broken at its core.

---

## 1. What This Document Is

A new agent reading this document should be able to understand exactly what exists, what is broken, and what needs to be rebuilt — without reading any prior conversation transcripts.

---

## 2. Production Environment

- **Server:** `root@187.124.67.153` (Hostinger KVM 8)
- **Repo on server:** `/opt/strideiq/repo`
- **Deploy:** `cd /opt/strideiq/repo && git pull origin main && docker compose -f docker-compose.prod.yml up -d --build api`
- **Founder account:** `mbshaf@gmail.com`
- **API container:** `strideiq_api`
- **Redis container:** `strideiq_redis`
- **Run scripts in container:** `docker exec strideiq_api bash -c 'PYTHONPATH=/app python3 /tmp/script.py'`
- **Flush fitness bank cache:** `docker exec strideiq_redis redis-cli DEL 'fitness_bank:<athlete_uuid>'`

---

## 3. Plan Generation Entry Point

**Endpoint:** `POST /v2/plans/constraint-aware`  
**Router:** `apps/api/routers/plan_generation.py` — function `create_constraint_aware_plan()` (~line 2440)  
**Core planner:** `apps/api/services/constraint_aware_planner.py` — class `ConstraintAwarePlanner`, method `generate_plan()`

**Request shape (relevant fields):**
```python
race_distance: str          # "10k", "5k", "half_marathon", "marathon"
race_date: date             # goal race date
peak_weekly_miles: float    # athlete-specified peak (65.0 for this athlete)
tune_up_races: List[dict]   # [{"date": "2026-04-25", "distance": "5k", "name": "..."}]
goal_time_seconds: Optional[int]  # if provided, use this; else system predicts
```

**Save function:** `_save_constraint_aware_plan()` in `plan_generation.py` — saves `TrainingPlan` + `PlannedWorkout` rows to DB.

---

## 4. The Data That Should Drive Plan Generation

### 4a. Fitness Bank (`apps/api/services/fitness_bank.py`)

The canonical N=1 data source. Computed by `get_fitness_bank(athlete_id, db)`.

**After the dedup fix (this session), these values are now correct:**
```
current_long_run_miles:   13.0   (max non-race run in last 4 weeks, excluding >24mi activities)
current_weekly_miles:     33.1   (trailing 4-week average)
peak_weekly_miles:        68.0   (best 4-consecutive-week rolling average, post-dedup)
best_rpi:                 53.18  (after _find_best_race fix — was 48.66 from wrong recency bias)
experience_level:         elite
constraint_type:          none
recent_quality_sessions_28d: 0   (post-marathon recovery — correctly no penalty now)
```

**Race performances (the ones that matter for pacing):**
```
2025-08-30  5K   RPI 53.26  (best — valid race)
2025-12-13  10K  RPI 53.18  finish_time 2379s = 39:39  (the 39:14 the athlete references)
2025-11-29  half RPI 52.91
2026-03-07  10mi RPI 48.66  (post-marathon effort — was wrongly selected as best_rpi before fix)
```

**NOTE:** `best_rpi` fix (`_find_best_race`) is in code but **not yet CI-validated or deployed**. Current production still has 48.66.

### 4b. Load Context (`apps/api/services/plan_framework/load_context.py`)

Used by the planner to get the athlete's L30 baselines:
```
l30_max_easy_long_mi:     13.0   (longest non-race, non->24mi run in last 30 days)
l30_floor:                14.0   (l30_max_easy_long_mi + 1 = week-1 long run minimum)
current_weekly_miles:     33.1
recent_16w_p90_weekly_miles: ~60
```

### 4c. What the Athlete Told the System

For the failing plan:
- Race distance: `10k`
- Race date: `2026-05-02` (Saturday)
- Peak weekly miles: `65`
- Tune-up: 5K on `2026-04-25`
- No explicit goal time set

---

## 5. The Plan That Was Generated (and Why It's Wrong)

The plan generated on 2026-03-26 20:06 (plan id: `cfd4e85f-efa5-44e5-84ef-f1cdf5396f6f`):

```
Week 1 (Mar 24):  long run 14mi  [OK — close to l30_floor+1]
Week 2 (Apr 05):  long run 10mi  [WRONG — below 13mi floor]
Week 3 (Apr 12):  long run 11mi  [WRONG — below floor]
Week 4 (Apr 19):  long run 11mi  [WRONG — flat, not building]
Week 5 (Apr 26):  long run  8mi  [WRONG — day AFTER tune-up race Apr 25]
Week 6 (May 03):  long run  8mi  [CATASTROPHIC — day AFTER goal race May 02]

May 02 (race day): shows "easy_strides" — race was not injected correctly
May 03 (day after race): shows "Long Run: 8mi"
Apr 26 (day after tune-up): shows "Long Run: 8mi"

Goal time predicted: ~44 min  [WRONG — athlete ran 39:14 in December]
```

**What the plan should look like for this athlete:**
```
Week 1 (Mar 24):  ~40-42 mpw  long run 14mi (l30+1)
Week 2 (Mar 31):  ~48-50 mpw  long run 16mi
Week 3 (Apr 07):  ~56-58 mpw  long run 18mi
Week 4 (Apr 14):  ~42mpw CUT  long run 14mi (cutback)
Week 5 (Apr 21):  ~60-62 mpw  long run 17mi  [pre-taper peak]
Week 6 (Apr 25):  TAPER — 5K tune-up Saturday, rest Sunday
Week 7 (May 02):  RACE WEEK — 10K Saturday May 02, REST Sunday
```

---

## 6. Root Cause: Template-Driven Prescription

### The Core Architectural Failure

The `WorkoutScaler._scale_long_run()` (`apps/api/services/plan_framework/workout_scaler.py`, line 299) computes long run size from **population-average lookup tables**, not athlete history:

```python
peak = peak_long_miles(goal, tier)          # Population constant: 10K HIGH = 15mi
start_long = standard_start_long_miles(goal, tier)  # Population constant
curve = start_long + (peak - start_long) * frac     # Linear interpolation
```

`previous_easy_long_mi` and `easy_long_floor_mi` exist as parameters but are only protective overrides (prevent regression below history) — they don't drive the prescription. The system builds from a population baseline and applies history as a constraint, when it should be the reverse: **build from athlete history, use population constants only as guardrails.**

### Why Long Runs Drop to 10-11mi in Weeks 2-4

- Population `start_long` for 10K HIGH tier is ~8-9mi
- Population `peak_long` for 10K HIGH tier is ~15mi
- With 7 weeks, `frac` for weeks 2-4 is 0.2-0.6
- That gives `curve = 8 + (15-8)*0.3 = 10.1mi` for week 2
- `previous_easy_long_mi` (13mi from week 1) applies a spike cap that LIMITS growth, not a floor that forces it up
- Result: week 2 target = min(10.1, 13+step_cap) = 10mi despite athlete having run 13mi already

**The fix required:** In `constraint_aware_planner.py`, the L30 long run history must set the STARTING POINT of the progression curve, not just a floor on week 1. Every week's target long run must be computed as:
```
week_n_long = previous_week_long + 2mi   (capped at athlete's chosen peak)
```
Not interpolated from a population curve.

### Why Goal Time Is Wrong

`_predict_race()` in `constraint_aware_planner.py` (line 921):
1. Gets `base_rpi = bank.best_rpi`
2. Applies penalties: `-0.8` if current mileage < 60% of peak, `-1.5` if no quality sessions 28d
3. With old `best_rpi = 48.66` and both penalties: `base_rpi = 48.66 - 0.8 - 1.5 = 46.36`
4. `rpi_equivalent_time(46.36, 10000)` → ~44 minutes

**Fixes applied in code (not yet deployed/tested):**
- `_find_best_race` now uses `max(r.rpi * r.confidence)` not recency-weighted pick → `best_rpi = 53.18`
- Quality sessions penalty skipped within 35 days of marathon
- After these fixes: `base_rpi = 53.18 - 0.8 = 52.38` → projected ~40-41 minutes

### Why Race Day Is Wrong

`_insert_tune_up_details()` (line 728) uses:
```python
week_idx = days_to_tune // 7   # calculated from today's Monday, not plan_start
```
This can index into the wrong week. When the tune-up is April 25 and today is March 26, `week_idx = 33 // 7 = 4`. That's weeks[4], which happens to be correct in this case. But the main race injection (step 5, line 506) injects into `weeks[-1]` replacing the existing workout for `race_date.weekday()` — this works — but then **nothing removes or replaces post-race workouts in the same week**. Sunday May 3 (after Saturday May 2 race) still gets whatever was generated.

Also: `_insert_tune_up_details` handles the day BEFORE the tune-up (pre_race), but does NOT handle the day AFTER (recovery). So April 26 gets whatever was generated (long run 8mi).

---

## 7. Files That Matter — What Each One Does

| File | Purpose | State |
|------|---------|-------|
| `services/constraint_aware_planner.py` | Orchestrates full plan generation. Calls phase builder, workout scaler, inserts race day. | Core logic present but population-biased. ~1100 lines. |
| `services/plan_framework/workout_scaler.py` | Sizes every workout (long run, threshold, intervals, easy). | Template-driven. Athlete history enters only as soft override. ~1300 lines. |
| `services/plan_framework/phase_builder.py` | Assigns phases (base/build/peak/taper) and per-phase `long_run_modifier` and `volume_modifier`. | Uses fixed modifiers (0.75, 0.85, 1.0, 0.52) not athlete-specific. |
| `services/plan_framework/volume_tiers.py` | Computes week-by-week volume progression from starting volume to peak. | Fixed this session — uses linear steps toward user-specified peak, no 10% cap. |
| `services/plan_framework/load_context.py` | Computes L30 baselines (l30_max_easy_long_mi, l30_floor) from athlete's actual Garmin data. | Working correctly post-dedup. |
| `services/fitness_bank.py` | Computes athlete's fitness profile (peak_weekly_miles, best_rpi, current_long_run, etc.). | Fixed this session: now uses `is_duplicate=False` filter, `_find_best_race` uses peak not recency. |
| `services/plan_quality_gate.py` | Validates generated plan passes rules (floor, dominance, spacing). | Passes — does not validate coaching quality. |
| `services/mileage_aggregation.py` | Computes canonical weekly mileage from activities. | Fixed this session. |
| `services/activity_deduplication.py` | Dedup logic. TIME_WINDOW_S = 28800 (8h) after this session. | Fixed. |
| `services/duplicate_scanner.py` | Retroactive scanner. 164 pairs marked for this athlete. | Fixed. |
| `routers/plan_generation.py` | API handler + DB save function `_save_constraint_aware_plan`. | Has fixes from this session (plan_start normalization, date calc, dedup safety net). |

---

## 8. What Needs to Be Built

### The Prescription Core (what's actually broken)

The `_scale_long_run` function and the main generation loop in `constraint_aware_planner.py` need to be driven by **athlete history first**. The required logic (from the knowledge base):

```
LONG RUN PROGRESSION (per PLAN_GENERATION_FRAMEWORK.md + 03_WORKOUT_TYPES.md):

Week 1 long run = l30_max_non_race_miles + 1
Subsequent weeks = previous_week_long + 2 miles (not cutback weeks)
Cutback week long = previous_peak_long * 0.75 (every 3-4 weeks)
Maximum for 10K = min(18, peak_weekly_miles * 0.28)   [not 22 — that's marathon]
Maximum for marathon = 22mi (HIGH tier), 24mi (ELITE)

VOLUME PROGRESSION:
Week 1 volume = max(current_weekly_miles * 1.1, l30_median * 1.0)
Target peak = user-specified (65 mpw for this athlete)
Build: linear steps of (peak - start) / build_weeks per week
No percentage caps. Absolute step ceiling: ~6-8mi/week for HIGH/ELITE tier.

QUALITY WORK:
Do not increase quality sessions while volume is increasing (no simultaneous ramp)
Quality volume = 8-12% of weekly volume for threshold/interval weeks
Paces come from: rpi_calculator.calculate_training_paces(bank.best_rpi)
  → best_rpi = max(r.rpi * r.confidence for valid races in last 24 months)
```

### Race Day and Post-Race Logic (broken scheduling)

In `_insert_tune_up_details` and the race day injection (step 5):

1. After inserting race day, **replace all workouts on days AFTER the race in the same week with rest**
2. After inserting tune-up race, **replace the day AFTER with a recovery run (easy 4-6mi)**
3. The day BEFORE any race must be pre_race (already handled for tune-up, not for main race week)

### Paces (currently generic)

Paces are computed via `calculate_paces_from_rpi(bank.best_rpi)` → `rpi_calculator.calculate_training_paces(rpi)`. After the `_find_best_race` fix, `best_rpi = 53.18`, giving:
- Easy: ~8:00-8:30/mi
- Threshold: ~6:35-6:45/mi  
- 10K race pace: ~6:22/mi

These flow from `best_rpi` automatically once `_find_best_race` is fixed and deployed.

---

## 9. What Was Fixed This Session (All Deployed and CI Green Except Last Two)

| Fix | Commit | Status |
|-----|--------|--------|
| Dedup window 1h → 8h (Garmin/Strava sync delay) | `e1a2e35` | Deployed, CI green |
| Test boundary uses TIME_WINDOW_S constant | `3a9d865` | Deployed, CI green |
| Plan start normalize to Monday | `45980f4` | Deployed, CI green |
| Horizon weeks ceiling division | `ab6bf3d` | Deployed, CI green |
| Workout date fix + dedup in save | `c637502` | Deployed, CI green |
| >24mi race exclusion from l30 floor | `ba08c0e` + `28561d8` | Deployed, CI green |
| W1 10K/5K long run dominance cap | `da91751` + `8419df3` | Deployed, CI green |
| is_cutback flag on WeekPlan | `7f48cb5` | Deployed, CI green |
| Tune-up null title fallback | `2d0b947` | Deployed, CI green |
| 164 Garmin/Strava duplicates marked in DB | backfill script | Done in DB, not code |
| Fitness bank: require_trusted_duplicate_flags=True | code change | **NOT DEPLOYED** |
| _find_best_race: peak RPI not recency-biased | code change | **NOT DEPLOYED** |
| Quality sessions penalty skip post-marathon | code change | **NOT DEPLOYED** |

The three undeployed changes are in `apps/api/services/fitness_bank.py` and `apps/api/services/constraint_aware_planner.py`. They need CI validation before deployment.

---

## 10. The Athlete's Training — Actual Recent Data

```
2026-03-26:  8.0mi easy
2026-03-25:  8.0mi easy
2026-03-24: 12.0mi (longest in recent window)
2026-03-22:  4.6mi
2026-03-21:  9.2mi
2026-03-20:  6.0mi
2026-03-19:  6.0mi
2026-03-15: 26.4mi (BAY ST LOUIS MARATHON — excluded from long run baseline)
Current weekly: 33.1 mpw (post-marathon recovery)
Peak 4-week average (post-dedup): 68.0 mpw (Oct-Nov 2025)
Best 10K: 39:39 (December 2025, RPI 53.18)
Best 5K: 18:45 approx (August 2025, RPI 53.26)
Best half: 1:27:40 approx (November 2025, RPI 52.91)
```

---

## 11. Knowledge Base Documents That Govern Plan Generation

All in `_AI_CONTEXT_/KNOWLEDGE_BASE/`:
- `PLAN_GENERATION_FRAMEWORK.md` — governing rules, archetype creation
- `03_WORKOUT_TYPES.md` — long run progression rules, spacing contracts, quality session sizing

Key rules:
1. Long run starts at l30_non_race_max + 1, progresses +2mi/week
2. NO 10% weekly mileage cap (see mbshaf.substack.com/p/forget-the-10-rule — author is the athlete)
3. No simultaneous ramp of volume AND intensity
4. Long run max: 22mi for marathon HIGH, 18mi for 10K, not 26+
5. Quality work freeze when volume is ramping week-over-week

---

## 12. What a Correct Plan Looks Like for This Athlete

**Input:** 10K on May 2, 5K tune-up April 25, peak 65 mpw, starting from 33 mpw

```
Week  Dates          Volume  Long   Key session
1     Mar 23–29      40      14mi   Easy base, strides
2     Mar 30–Apr 5   48      16mi   Easy base, strides  
3     Apr 6–12       56      18mi   Threshold intro
4     Apr 13–19      40 CUT  14mi   Cutback
5     Apr 20–26      60      17mi   Threshold intervals — Sat: 5K tune-up (replace long)
6     Apr 27–May 3   ~35     REST   Taper — Sat May 2: 10K RACE, Sun: REST
```

Long run paces: ~8:00-8:30/mi easy  
Threshold paces: ~6:35-6:45/mi  
Race goal: 39:30-41:00 (based on best_rpi 53.18, conservatively discounted for recovery period)

---

## 13. Test Command

Run the full backend test suite:
```bash
cd apps/api && python -m pytest tests/ -v --timeout=120
```

Run plan-specific tests:
```bash
python -m pytest tests/test_full_athlete_plan_matrix.py tests/test_plan_validation_matrix.py tests/test_t3_constraint_aware_convergence.py -v
```

CI: GitHub Actions, workflow `.github/workflows/ci.yml`. Must pass all 10 jobs including `P0 plan registry gate` (requires commit message line `P0-GATE: GREEN` when touching `plan_framework/` or `plan_generation` runtime code).

---

## 14. The Honest Summary

T0-T5 was a tiered rebuild spec executed over several weeks. The infrastructure work (dedup, data integrity, DB errors, quality gate passing) is solid. The prescription logic — what workouts get assigned at what distances, in what order, for what athlete — is still fundamentally population-average template interpolation with athlete history as a set of soft constraints on top.

The fix requires restructuring the core prescription loop in `constraint_aware_planner.py` and `workout_scaler._scale_long_run()` so that athlete history (l30_max, current_long, peak_weekly) is the starting point, and population tables are ceiling/floor guardrails only.
