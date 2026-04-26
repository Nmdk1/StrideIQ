# Data Intelligence Audit — 2026-03-10

## Purpose

Map every field the system stores against what the correlation engine
actually uses. Show the gap. Quantify how much intelligence we're leaving
on the table.

---

## What the Correlation Engine Currently Uses

### Inputs (what it correlates against)

Source: `aggregate_daily_inputs()` + `aggregate_training_load_inputs()` in
`correlation_engine.py`

| # | Input Signal | Source Table | Field |
|---|-------------|-------------|-------|
| 1 | sleep_hours | DailyCheckin | sleep_h |
| 2 | hrv_rmssd | DailyCheckin | hrv_rmssd |
| 3 | resting_hr | DailyCheckin | resting_hr |
| 4 | work_stress | WorkPattern | stress_level |
| 5 | work_hours | WorkPattern | hours_worked |
| 6 | daily_protein_g | NutritionEntry | protein_g (daily sum) |
| 7 | daily_carbs_g | NutritionEntry | carbs_g (daily sum) |
| 8 | weight_kg | BodyComposition | weight_kg |
| 9 | bmi | BodyComposition | bmi |
| 10 | stress_1_5 | DailyCheckin | stress_1_5 |
| 11 | soreness_1_5 | DailyCheckin | soreness_1_5 |
| 12 | rpe_1_10 | DailyCheckin | rpe_1_10 |
| 13 | enjoyment_1_5 | DailyCheckin | enjoyment_1_5 |
| 14 | confidence_1_5 | DailyCheckin | confidence_1_5 |
| 15 | readiness_1_5 | DailyCheckin | readiness_1_5 |
| 16 | overnight_avg_hr | DailyCheckin | overnight_avg_hr |
| 17 | hrv_sdnn | DailyCheckin | hrv_sdnn |
| 18 | tsb | TrainingLoadCalculator | derived |
| 19 | ctl | TrainingLoadCalculator | derived |
| 20 | atl | TrainingLoadCalculator | derived |
| 21 | daily_session_stress | Activity | distance_m × avg_hr (daily sum) |

**Total: 21 input signals.**

### Outputs (what it measures performance against)

| # | Output Metric | What It Measures |
|---|--------------|------------------|
| 1 | efficiency | EF with decoupling (all runs) |
| 2 | pace_easy | Pace on easy-classified runs |
| 3 | pace_threshold | Pace on threshold-classified runs |
| 4 | completion | Rolling workout completion rate |
| 5 | efficiency_threshold | EF on threshold runs |
| 6 | efficiency_race | EF on race-effort runs |
| 7 | efficiency_trend | Rolling efficiency % change |
| 8 | pb_events | Binary PB day series |
| 9 | race_pace | Pace on race-like efforts |

**Total: 9 output metrics.**

---

## THE GAP: Stored But Not Used

### Category 1: GarminDay — Complete Blackout

**The correlation engine never queries GarminDay.** Zero references.
Every Garmin wearable signal sits in the database unused for correlation
discovery.

| Field | What It Is | Intelligence Value |
|-------|-----------|-------------------|
| `avg_stress` | Daily Garmin stress score (0-100) | **HIGH** — Garmin's autonomic stress reading, independent of athlete perception. Compare to self-reported stress_1_5. |
| `max_stress` | Peak stress in day | Spike detection — did a stress spike the night before affect next-day running? |
| `stress_qualifier` | Garmin's categorical stress label | Qualitative filter for stress correlations |
| `steps` | Daily step count | Total daily movement load beyond running. Could explain fatigue on "rest" days. |
| `active_time_s` | Daily active time | Non-running activity volume — cross-training, walking, physical job. |
| `active_kcal` | Daily active calories | Total energy expenditure proxy. |
| `moderate_intensity_s` | Time in moderate intensity zones | Non-running moderate effort (gym, cycling, hiking). |
| `vigorous_intensity_s` | Time in vigorous intensity zones | Non-running hard effort. |
| `min_hr` | Daily minimum heart rate | Lowest resting HR — better recovery signal than resting_hr. |
| `max_hr` | Daily maximum heart rate | Peak exertion signal. |
| `sleep_score` | Garmin sleep score (0-100) | **HIGH** — Objective sleep quality, should be correlated against performance. |
| `sleep_deep_s` | Deep sleep seconds | **HIGH** — Deep sleep is the recovery phase. HRV alone doesn't capture sleep architecture. |
| `sleep_light_s` | Light sleep seconds | Sleep architecture completeness. |
| `sleep_rem_s` | REM sleep seconds | **HIGH** — REM is cognitive recovery and motor learning consolidation. |
| `sleep_awake_s` | Awake time during sleep | Sleep fragmentation — interrupted sleep vs continuous. |
| `hrv_5min_high` | Highest 5-min HRV window | Peak parasympathetic capacity — more sensitive than overnight average. |
| `body_battery_end` | End-of-day body battery | **HIGH** — Garmin's composite readiness metric. Already computed, never correlated. |
| `vo2max` | Garmin VO2max estimate | Fitness trend tracked by Garmin. |
| `stress_samples` | Intraday stress time series (JSONB) | Could derive: pre-run stress, post-run stress recovery speed. |
| `body_battery_samples` | Intraday body battery curve (JSONB) | Could derive: morning body battery (run readiness), battery drain rate. |
| `sleep_score_qualifier` | Garmin's sleep quality label | Qualitative filter. |

**Impact: 20+ fields from GarminDay are stored daily and NEVER used for
correlation. This is the single largest intelligence gap.**

### Category 2: Activity-Level Signals — Partial Blindness

The engine uses avg_hr, distance_m, duration_s from Activity. But it
ignores all of these stored fields:

| Field | What It Is | Intelligence Value |
|-------|-----------|-------------------|
| `dew_point_f` | Dew point at activity time | **HIGH** — Already discussed. Heat stress signal for weather correlations. |
| `heat_adjustment_pct` | Computed heat pace penalty | **HIGH** — N=1 heat resilience tracking. |
| `temperature_f` | Temperature at activity time | Environmental context. |
| `humidity_pct` | Humidity at activity time | Environmental context. |
| `total_elevation_gain` | Elevation gain in meters | **HIGH** — Hilly runs stress different systems. Elevation vs efficiency, elevation vs recovery. |
| `avg_cadence` | Average steps per minute | **HIGH** — Running economy marker. Cadence trends vs injury, vs efficiency. |
| `avg_stride_length_m` | Average stride length | Economy and fatigue signal. |
| `avg_ground_contact_ms` | Ground contact time | Running form degradation under fatigue. |
| `avg_vertical_oscillation_cm` | Vertical bounce | Economy metric — bouncing = wasted energy. |
| `avg_vertical_ratio_pct` | Vertical ratio | Stride efficiency composite. |
| `avg_power_w` | Running power (Garmin) | Direct mechanical output. |
| `garmin_aerobic_te` | Aerobic training effect | **HIGH** — Garmin's load assessment for each run. |
| `garmin_anaerobic_te` | Anaerobic training effect | Intensity profile of workout. |
| `garmin_perceived_effort` | Garmin's perceived effort | Garmin's own RPE estimate. |
| `garmin_body_battery_impact` | How much this run drained body battery | **HIGH** — Actual physiological cost. |
| `intensity_score` | Computed intensity score | Already computed, never correlated. |
| `workout_type` | Classified workout type (easy, intervals, etc.) | Not used as a correlation input. |
| `start_time` (hour) | Time of day | Morning vs evening performance differences. |
| `avg_gap_min_per_mile` | Grade-adjusted pace | Terrain-normalized performance. |
| `moving_time_s` | Time actually moving | Removes stops. |
| `active_kcal` | Calories burned on activity | Energy cost of the run. |

**Impact: 21 activity fields are stored and never used for correlation.**

### Category 3: Derived Signals Never Computed

These aren't stored as fields — they can be derived from stored data but
the engine never computes them.

| Derived Signal | Source | Intelligence Value |
|---------------|--------|-------------------|
| Days since last quality session | Activity.workout_type + start_time | **HIGH** — Rest period before quality work. |
| Consecutive run days | Activity.start_time | Streak fatigue. |
| Weekly volume trend | Activity.distance_m | Volume ramp rate vs performance. |
| Long run ratio | Activity.distance_m | Proportion of weekly volume in long run. |
| Weekly elevation trend | Activity.total_elevation_gain | Elevation exposure adaptation. |
| Time of day (hour bucket) | Activity.start_time | Morning runner vs evening runner effect. |
| Days since last rest day | Activity.start_time | Recovery adequacy. |
| Sleep architecture ratio | GarminDay deep/rem/light | Quality of sleep composition. |
| Body battery recovery rate | GarminDay.body_battery_samples | How fast the athlete recharges. |
| Pre-run body battery | GarminDay.body_battery_samples | Readiness at run start. |
| Pre-run stress level | GarminDay.stress_samples | Stress state at run start. |
| Post-run stress recovery | GarminDay.stress_samples | Parasympathetic recovery speed. |
| Sleep consistency | GarminDay.sleep_total_s | Variance in sleep timing/duration. |
| Run surface type | Activity.name (parsed) | Track vs trail vs road. |

### Category 4: Existing Models — Completely Disconnected

These models store athlete intelligence that the correlation engine
never touches.

| Model | Fields Available | Intelligence Value |
|-------|-----------------|-------------------|
| **ActivityFeedback** | perceived_effort, leg_feel, mood_pre, mood_post, energy_pre, energy_post | **HIGH** — Post-run subjective state. leg_feel vs next-day efficiency. mood_post vs next-day readiness. energy_post vs recovery speed. Imported in correlation_engine.py but never queried. |
| **ActivityReflection** | response (harder/expected/easier) | **HIGH** — Athlete's perception vs reality. "Easier than expected" on a hard day = strong adaptation signal. |
| **DailyReadiness** | score, components, signals_available, confidence | Already computed daily. Never fed back as a correlation input. |
| **SelfRegulationLog** | delta_type, delta_direction, readiness_at_decision, outcome_efficiency_delta, outcome_classification | **HIGH** — When athletes deviate from plan, do they get better or worse? This is meta-intelligence about self-regulation. |
| **ThresholdCalibrationLog** | readiness_score, outcome, efficiency_delta, subjective_feel | Readiness prediction accuracy. |
| **AthleteLearning** | learning_type, subject, evidence, confidence | Existing "what works" discoveries. Not looped back. |
| **AthleteWorkoutResponse** | stimulus_type, avg_rpe_gap, completion_rate | How the athlete responds to each workout type. |
| **BodyComposition** | body_fat_pct, muscle_mass_kg | Stored, only weight_kg and bmi used. |
| **NutritionEntry** | fat_g, fiber_g, calories, timing | fat_g and fiber_g stored but not used. Timing never analyzed (pre-race nutrition?). |

### Category 5: DailyCheckin Fields Used Correctly ✓

| Field | Status |
|-------|--------|
| sleep_h | ✓ Used |
| sleep_quality_1_5 | **NOT USED** — Self-reported sleep quality, never fed to engine. |
| stress_1_5 | ✓ Used |
| soreness_1_5 | ✓ Used |
| rpe_1_10 | ✓ Used |
| notes | Not applicable (free text) |
| hrv_rmssd | ✓ Used |
| hrv_sdnn | ✓ Used |
| resting_hr | ✓ Used |
| overnight_avg_hr | ✓ Used |
| enjoyment_1_5 | ✓ Used |
| confidence_1_5 | ✓ Used |
| readiness_1_5 | ✓ Used |

**1 field missing: `sleep_quality_1_5`.**

---

## Gap Summary

| Category | Stored Fields | Used by Engine | Unused | % Wasted |
|----------|:------------:|:--------------:|:------:|:--------:|
| GarminDay (wearable) | 20 | 0 | **20** | 100% |
| Activity (per-run) | 21 | 3 | **18** | 86% |
| DailyCheckin | 13 | 12 | **1** | 8% |
| ActivityFeedback | 6 | 0 | **6** | 100% |
| ActivityReflection | 1 | 0 | **1** | 100% |
| DailyReadiness | 4 | 0 | **4** | 100% |
| SelfRegulationLog | 8 | 0 | **8** | 100% |
| BodyComposition | 5 | 2 | **3** | 60% |
| NutritionEntry | 6 | 2 | **4** | 67% |
| Derivable signals | 14 | 0 | **14** | 100% |
| **TOTAL** | **98** | **19** | **79** | **81%** |

**The system stores ~98 meaningful signals. The correlation engine uses 19
of them. 81% of stored intelligence is invisible to the engine.**

---

## Priority Ranking: What to Wire First

### Tier 1 — High Value, Low Effort (add as inputs to `aggregate_daily_inputs`)

These are already stored as daily values. Adding them is a query + append.

1. **GarminDay.sleep_score** — Objective sleep quality (the athlete already has this on their watch)
2. **GarminDay.sleep_deep_s** — Deep sleep quantity
3. **GarminDay.sleep_rem_s** — REM sleep quantity
4. **GarminDay.body_battery_end** — End-of-day readiness composite
5. **GarminDay.avg_stress** — Objective autonomic stress (Garmin)
6. **GarminDay.steps** — Total daily movement
7. **GarminDay.hrv_5min_high** — Peak parasympathetic window
8. **DailyCheckin.sleep_quality_1_5** — Subjective sleep quality
9. **Activity.dew_point_f** — Heat stress (builder instructions already written)
10. **Activity.heat_adjustment_pct** — N=1 heat resilience

### Tier 2 — High Value, Medium Effort (needs aggregation logic)

These require activity-level → daily aggregation or derivation.

1. **Activity.total_elevation_gain** — Sum per day or per-activity
2. **Activity.avg_cadence** — Activity-level correlation against efficiency
3. **Activity.garmin_aerobic_te** — Per-activity training effect
4. **Activity.garmin_body_battery_impact** — Per-activity battery cost
5. **Activity.intensity_score** — Already computed per activity
6. **ActivityFeedback.leg_feel** — Encode as ordinal, correlate
7. **ActivityFeedback.energy_post** — Post-run energy level
8. **ActivityReflection.response** — harder=1, expected=0, easier=-1
9. **GarminDay.active_time_s** — Total non-running active time
10. **BodyComposition.body_fat_pct** — Body fat trend vs performance

### Tier 3 — High Value, Higher Effort (needs derivation or JSONB parsing)

1. Days since last quality session
2. Consecutive run days
3. Pre-run body battery (from body_battery_samples JSONB)
4. Pre-run stress (from stress_samples JSONB)
5. Sleep architecture ratio (deep+REM vs light+awake)
6. Time of day bucket
7. SelfRegulationLog outcome patterns
8. NutritionEntry timing + fat_g/fiber_g

---

## Architecture Note

All Tier 1 items follow the same pattern as the existing 21 inputs:

```python
# In aggregate_daily_inputs():
garmin_sleep_score = db.query(
    GarminDay.calendar_date,
    GarminDay.sleep_score
).filter(
    GarminDay.athlete_id == athlete_id,
    GarminDay.calendar_date >= start_date.date(),
    GarminDay.calendar_date <= end_date.date(),
    GarminDay.sleep_score.isnot(None)
).all()

inputs["garmin_sleep_score"] = [
    (row.calendar_date, float(row.sleep_score)) for row in garmin_sleep_score
]
```

Each Tier 1 input is ~10 lines of code. Tier 1 alone (10 signals) could
be done in a single builder session.

The `DIRECTION_EXPECTATIONS` and `CONFOUNDER_MAP` dictionaries should
also be extended for the new inputs (e.g., expect positive correlation
between sleep_score and efficiency, body_battery_end and efficiency).

`FRIENDLY_NAMES` in `n1_insight_generator.py` must be updated for every
new input so findings surface with human-readable labels.

---

## What This Means

The engine has been running correlations on 21 signals. There are at least
79 more sitting in the database. The most egregious gap is GarminDay —
an entire wearable data pipeline that feeds no intelligence.

For Brian Levesque, who wears a Garmin: his deep sleep, body battery,
stress score, and step count are all stored every single day. The engine
has never once checked whether any of them predict his running performance.

That's the size of the blind spot.
