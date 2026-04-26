# Builder Instructions — Wire All Inputs to the Correlation Engine

**Date:** March 10, 2026  
**Priority:** P0 — highest ROI work in the system  
**Scope:** Backend only. No frontend. No migrations. No new APIs.  
**Spec:** `docs/specs/CORRELATION_ENGINE_FULL_INPUT_WIRING_SPEC.md`  
**Audit:** `docs/DATA_INTELLIGENCE_AUDIT_2026-03-10.md`

---

## What This Does

The correlation engine discovers personalized findings about each athlete.
It currently sees 21 input signals. There are 79 more sitting in the
database, stored daily, never correlated. This wires all of them.

After this build, the engine correlates 70 input signals against 9 output
metrics. Everything downstream (correlation math, persistence, surfacing,
finding cooldowns, layer detection) works automatically. Zero additional
work needed for new findings to appear on home page, progress, and coach.

---

## Build Loop

Work through every phase below in order. For each phase:

```bash
# 1. Implement the phase
# 2. Run tests for that phase
python -m pytest apps/api/tests/test_correlation_inputs.py -x -q -k "<PhaseSelector>"
# 3. If green, continue to next phase
# 4. If red, fix and retest before moving on
```

Use these exact selectors (copy/paste; do NOT use `phase_N` literally):

```bash
# Phase 1
python -m pytest apps/api/tests/test_correlation_inputs.py -x -q -k "Phase1"
# Phase 2
python -m pytest apps/api/tests/test_correlation_inputs.py -x -q -k "Phase2"
# Phase 3
python -m pytest apps/api/tests/test_correlation_inputs.py -x -q -k "Phase3"
# Phase 4
python -m pytest apps/api/tests/test_correlation_inputs.py -x -q -k "Phase4"
# Phase 5
python -m pytest apps/api/tests/test_correlation_inputs.py -x -q -k "Phase5"
# Phases 6-9 integration checks
python -m pytest apps/api/tests/test_correlation_inputs.py -x -q -k "Integration"
```

After ALL phases are complete, run the full validation:

```bash
# Full backend test suite (must be green — no regressions)
python -m pytest apps/api/tests/ -x -q --timeout=120

# Specifically: correlation engine tests + new input tests
python -m pytest apps/api/tests/test_correlation_engine.py apps/api/tests/test_correlation_inputs.py -x -q -v

# Show what changed
git diff --name-only
git diff --stat
```

Then commit and push your branch (PR-first, no direct push to main):

```bash
git add apps/api/services/correlation_engine.py \
      apps/api/services/n1_insight_generator.py \
      apps/api/tests/test_correlation_inputs.py
git commit -m "feat(correlation): wire 49 new input signals to correlation engine

Closes the 81% data blind spot identified in data intelligence audit.
Adds GarminDay wearable (14), activity-level (18), feedback/reflection (5),
checkin/composition/nutrition (6), and training pattern (6) signals.
Engine goes from 21 to 70 inputs. All downstream infrastructure
(persistence, surfacing, layers) works automatically."

git push -u origin <your-branch-name>
# Open PR and wait for CI green before merge
```

---

## Phase 1: GarminDay Wearable Signals (14 inputs)

### File: `apps/api/services/correlation_engine.py`

#### 1a. Add import

At the top imports block (line ~28), add `GarminDay`:

```python
from models import (
    Activity, ActivitySplit, NutritionEntry, DailyCheckin,
    WorkPattern, BodyComposition, ActivityFeedback,
    PlannedWorkout, TrainingPlan, Athlete, PersonalBest,
    GarminDay,  # <-- ADD THIS
)
```

#### 1b. Add queries to `aggregate_daily_inputs()`

After the last existing input block (the `hrv_sdnn` block, ends around
line 479), add ALL of the following. Each follows the identical pattern.

```python
# ── GarminDay wearable signals ──

_garmin_base = db.query(GarminDay).filter(
    GarminDay.athlete_id == athlete_id,
    GarminDay.calendar_date >= start_date.date(),
    GarminDay.calendar_date <= end_date.date(),
)

_gd_rows = _garmin_base.all()

_GARMIN_SIGNALS = [
    ("garmin_sleep_score", "sleep_score"),
    ("garmin_sleep_deep_s", "sleep_deep_s"),
    ("garmin_sleep_rem_s", "sleep_rem_s"),
    ("garmin_sleep_awake_s", "sleep_awake_s"),
    ("garmin_body_battery_end", "body_battery_end"),
    ("garmin_avg_stress", "avg_stress"),
    ("garmin_max_stress", "max_stress"),
    ("garmin_steps", "steps"),
    ("garmin_active_time_s", "active_time_s"),
    ("garmin_moderate_intensity_s", "moderate_intensity_s"),
    ("garmin_vigorous_intensity_s", "vigorous_intensity_s"),
    ("garmin_hrv_5min_high", "hrv_5min_high"),
    ("garmin_min_hr", "min_hr"),
    ("garmin_vo2max", "vo2max"),
]

for input_key, attr in _GARMIN_SIGNALS:
    series = []
    for row in _gd_rows:
        val = getattr(row, attr, None)
        if val is not None:
            series.append((row.calendar_date, float(val)))
    inputs[input_key] = series
```

This is a single query that fetches all GarminDay rows in the window,
then extracts each signal. Much more efficient than 14 separate queries.

---

## Phase 2: Activity-Level Signals (18 inputs)

### File: `apps/api/services/correlation_engine.py`

#### 2a. Add new function after `aggregate_daily_inputs()`

```python
def aggregate_activity_level_inputs(
    athlete_id: str,
    start_date: datetime,
    end_date: datetime,
    db: Session
) -> Dict[str, List[Tuple[date_type, float]]]:
    """
    Aggregate activity-level signals into daily time series.
    For days with multiple activities, uses the primary run (longest distance).
    """
    inputs: Dict[str, List[Tuple[date_type, float]]] = {}

    activities = db.query(Activity).filter(
        Activity.athlete_id == athlete_id,
        Activity.is_duplicate == False,  # noqa: E712
        Activity.sport == "run",
        Activity.start_time >= start_date,
        Activity.start_time <= end_date,
    ).order_by(Activity.start_time).all()

    if not activities:
        return inputs

    by_date: Dict[date_type, Activity] = {}
    for a in activities:
        d = a.start_time.date()
        if d not in by_date or (a.distance_m or 0) > (by_date[d].distance_m or 0):
            by_date[d] = a

    _ACTIVITY_SIGNALS = [
        ("dew_point_f", "dew_point_f"),
        ("heat_adjustment_pct", "heat_adjustment_pct"),
        ("temperature_f", "temperature_f"),
        ("humidity_pct", "humidity_pct"),
        ("elevation_gain_m", "total_elevation_gain"),
        ("avg_cadence", "avg_cadence"),
        ("avg_stride_length_m", "avg_stride_length_m"),
        ("avg_ground_contact_ms", "avg_ground_contact_ms"),
        ("avg_vertical_oscillation_cm", "avg_vertical_oscillation_cm"),
        ("avg_vertical_ratio_pct", "avg_vertical_ratio_pct"),
        ("avg_power_w", "avg_power_w"),
        ("garmin_aerobic_te", "garmin_aerobic_te"),
        ("garmin_anaerobic_te", "garmin_anaerobic_te"),
        ("garmin_perceived_effort", "garmin_perceived_effort"),
        ("garmin_body_battery_impact", "garmin_body_battery_impact"),
        ("activity_intensity_score", "intensity_score"),
        ("active_kcal", "active_kcal"),
    ]

    for signal_key, attr in _ACTIVITY_SIGNALS:
        series = []
        for d, a in sorted(by_date.items()):
            val = getattr(a, attr, None)
            if val is not None:
                fval = float(val)
                if signal_key == "heat_adjustment_pct" and fval <= 0:
                    continue
                series.append((d, fval))
        if series:
            inputs[signal_key] = series

    tod_series = []
    for d, a in sorted(by_date.items()):
        if a.start_time:
            tod_series.append((d, float(a.start_time.hour)))
    if tod_series:
        inputs["run_start_hour"] = tod_series

    return inputs
```

#### 2b. Wire into `analyze_correlations()`

In `analyze_correlations()`, find the line (around ~1228):

```python
inputs.update(load_inputs)
```

Add immediately after it:

```python
activity_inputs = aggregate_activity_level_inputs(
    athlete_id, start_date, end_date, db
)
inputs.update(activity_inputs)
```

#### 2c. Wire into `discover_combination_correlations()`

In `discover_combination_correlations()`, find the line (around ~1392):

```python
inputs = aggregate_daily_inputs(athlete_id, start_date, end_date, db)
```

Add immediately after it:

```python
activity_inputs = aggregate_activity_level_inputs(
    athlete_id, start_date, end_date, db
)
inputs.update(activity_inputs)
```

---

## Phase 3: Feedback & Reflection Signals (5 inputs)

### File: `apps/api/services/correlation_engine.py`

#### 3a. Add import

At the top imports (line ~28), add `ActivityReflection` if not already imported:

```python
from models import (
    Activity, ActivitySplit, NutritionEntry, DailyCheckin,
    WorkPattern, BodyComposition, ActivityFeedback,
    PlannedWorkout, TrainingPlan, Athlete, PersonalBest,
    GarminDay, ActivityReflection,  # <-- ADD ActivityReflection
)
```

#### 3b. Add new function

```python
def aggregate_feedback_inputs(
    athlete_id: str,
    start_date: datetime,
    end_date: datetime,
    db: Session
) -> Dict[str, List[Tuple[date_type, float]]]:
    """
    Aggregate post-run feedback and reflection signals.
    """
    inputs: Dict[str, List[Tuple[date_type, float]]] = {}

    _LEG_FEEL_ORDINAL = {
        "fresh": 5, "normal": 4, "tired": 3,
        "heavy": 2, "sore": 1, "injured": 0,
    }

    feedback_rows = db.query(
        ActivityFeedback.submitted_at,
        ActivityFeedback.perceived_effort,
        ActivityFeedback.energy_pre,
        ActivityFeedback.energy_post,
        ActivityFeedback.leg_feel,
    ).filter(
        ActivityFeedback.athlete_id == athlete_id,
        ActivityFeedback.submitted_at >= start_date,
        ActivityFeedback.submitted_at <= end_date,
    ).all()

    perceived_effort = []
    energy_pre = []
    energy_post = []
    leg_feel = []

    for row in feedback_rows:
        d = row.submitted_at.date() if row.submitted_at else None
        if d is None:
            continue
        if row.perceived_effort is not None:
            perceived_effort.append((d, float(row.perceived_effort)))
        if row.energy_pre is not None:
            energy_pre.append((d, float(row.energy_pre)))
        if row.energy_post is not None:
            energy_post.append((d, float(row.energy_post)))
        if row.leg_feel and row.leg_feel in _LEG_FEEL_ORDINAL:
            leg_feel.append((d, float(_LEG_FEEL_ORDINAL[row.leg_feel])))

    if perceived_effort:
        inputs["feedback_perceived_effort"] = perceived_effort
    if energy_pre:
        inputs["feedback_energy_pre"] = energy_pre
    if energy_post:
        inputs["feedback_energy_post"] = energy_post
    if leg_feel:
        inputs["feedback_leg_feel"] = leg_feel

    _REFLECTION_ORDINAL = {"harder": -1, "expected": 0, "easier": 1}

    reflection_rows = db.query(
        ActivityReflection.created_at,
        ActivityReflection.response,
    ).filter(
        ActivityReflection.athlete_id == athlete_id,
        ActivityReflection.created_at >= start_date,
        ActivityReflection.created_at <= end_date,
    ).all()

    reflection_series = []
    for row in reflection_rows:
        d = row.created_at.date() if row.created_at else None
        if d is None:
            continue
        val = _REFLECTION_ORDINAL.get(row.response)
        if val is not None:
            reflection_series.append((d, float(val)))

    if reflection_series:
        inputs["reflection_vs_expected"] = reflection_series

    return inputs
```

#### 3c. Wire into `analyze_correlations()`

Same location as Phase 2, add after the activity_inputs line:

```python
feedback_inputs = aggregate_feedback_inputs(
    athlete_id, start_date, end_date, db
)
inputs.update(feedback_inputs)
```

Also add the same call in `discover_combination_correlations()`.

---

## Phase 4: Missing Checkin + Composition + Nutrition (6 inputs)

### File: `apps/api/services/correlation_engine.py`

#### 4a. Add to `aggregate_daily_inputs()`

After the existing `sleep_h` block (around line 272), add:

```python
sleep_quality_data = db.query(
    DailyCheckin.date,
    DailyCheckin.sleep_quality_1_5
).filter(
    DailyCheckin.athlete_id == athlete_id,
    DailyCheckin.date >= start_date.date(),
    DailyCheckin.date <= end_date.date(),
    DailyCheckin.sleep_quality_1_5.isnot(None)
).all()

inputs["sleep_quality_1_5"] = [
    (row.date, float(row.sleep_quality_1_5)) for row in sleep_quality_data
]
```

After the existing `bmi` block (around line 375), add:

```python
body_fat_data = db.query(
    BodyComposition.date,
    BodyComposition.body_fat_pct
).filter(
    BodyComposition.athlete_id == athlete_id,
    BodyComposition.date >= start_date.date(),
    BodyComposition.date <= end_date.date(),
    BodyComposition.body_fat_pct.isnot(None)
).order_by(BodyComposition.date).all()

inputs["body_fat_pct"] = [
    (row.date, float(row.body_fat_pct)) for row in body_fat_data
]

muscle_mass_data = db.query(
    BodyComposition.date,
    BodyComposition.muscle_mass_kg
).filter(
    BodyComposition.athlete_id == athlete_id,
    BodyComposition.date >= start_date.date(),
    BodyComposition.date <= end_date.date(),
    BodyComposition.muscle_mass_kg.isnot(None)
).order_by(BodyComposition.date).all()

inputs["muscle_mass_kg"] = [
    (row.date, float(row.muscle_mass_kg)) for row in muscle_mass_data
]
```

After the existing `daily_carbs_g` block (around line 350), add:

```python
fat_data = db.query(
    NutritionEntry.date,
    func.sum(NutritionEntry.fat_g).label('total_fat')
).filter(
    NutritionEntry.athlete_id == athlete_id,
    NutritionEntry.date >= start_date.date(),
    NutritionEntry.date <= end_date.date(),
    NutritionEntry.fat_g.isnot(None)
).group_by(NutritionEntry.date).all()

inputs["daily_fat_g"] = [
    (row.date, float(row.total_fat)) for row in fat_data
]

fiber_data = db.query(
    NutritionEntry.date,
    func.sum(NutritionEntry.fiber_g).label('total_fiber')
).filter(
    NutritionEntry.athlete_id == athlete_id,
    NutritionEntry.date >= start_date.date(),
    NutritionEntry.date <= end_date.date(),
    NutritionEntry.fiber_g.isnot(None)
).group_by(NutritionEntry.date).all()

inputs["daily_fiber_g"] = [
    (row.date, float(row.total_fiber)) for row in fiber_data
]

calorie_data = db.query(
    NutritionEntry.date,
    func.sum(NutritionEntry.calories).label('total_calories')
).filter(
    NutritionEntry.athlete_id == athlete_id,
    NutritionEntry.date >= start_date.date(),
    NutritionEntry.date <= end_date.date(),
    NutritionEntry.calories.isnot(None)
).group_by(NutritionEntry.date).all()

inputs["daily_calories"] = [
    (row.date, float(row.total_calories)) for row in calorie_data
]
```

---

## Phase 5: Training Pattern Signals (6 derived inputs)

### File: `apps/api/services/correlation_engine.py`

#### 5a. Add new function

```python
def aggregate_training_pattern_inputs(
    athlete_id: str,
    start_date: datetime,
    end_date: datetime,
    db: Session
) -> Dict[str, List[Tuple[date_type, float]]]:
    """
    Compute derived training pattern signals from activity history.
    """
    inputs: Dict[str, List[Tuple[date_type, float]]] = {}

    activities = db.query(
        Activity.start_time,
        Activity.distance_m,
        Activity.workout_type,
        Activity.total_elevation_gain,
    ).filter(
        Activity.athlete_id == athlete_id,
        Activity.is_duplicate == False,  # noqa: E712
        Activity.sport == "run",
        Activity.start_time >= start_date - timedelta(days=14),
        Activity.start_time <= end_date,
    ).order_by(Activity.start_time).all()

    if not activities:
        return inputs

    activity_dates = sorted(set(a.start_time.date() for a in activities))
    activity_date_set = set(activity_dates)
    analysis_start = start_date.date()

    _QUALITY_TYPES = {
        "intervals", "tempo", "threshold", "race", "fartlek", "hills",
    }

    from collections import defaultdict
    daily_distance: Dict[date_type, float] = defaultdict(float)
    daily_elevation: Dict[date_type, float] = defaultdict(float)
    daily_quality: Dict[date_type, bool] = defaultdict(bool)

    for a in activities:
        d = a.start_time.date()
        daily_distance[d] += float(a.distance_m or 0)
        daily_elevation[d] += float(a.total_elevation_gain or 0)
        if a.workout_type and a.workout_type.lower() in _QUALITY_TYPES:
            daily_quality[d] = True

    # Days since last quality session
    days_since_quality = []
    last_quality_date = None
    current = analysis_start
    end = end_date.date()
    while current <= end:
        if daily_quality.get(current):
            last_quality_date = current
        if last_quality_date and current in activity_date_set:
            gap = (current - last_quality_date).days
            days_since_quality.append((current, float(gap)))
        current += timedelta(days=1)
    if days_since_quality:
        inputs["days_since_quality"] = days_since_quality

    # Consecutive run days
    consec_series = []
    for d in activity_dates:
        if d < analysis_start:
            continue
        streak = 0
        check = d
        while check in activity_date_set:
            streak += 1
            check -= timedelta(days=1)
        consec_series.append((d, float(streak)))
    if consec_series:
        inputs["consecutive_run_days"] = consec_series

    # Days since last rest day
    rest_day_series = []
    for d in activity_dates:
        if d < analysis_start:
            continue
        gap = 0
        check = d - timedelta(days=1)
        while check in activity_date_set:
            gap += 1
            check -= timedelta(days=1)
        rest_day_series.append((d, float(gap + 1)))
    if rest_day_series:
        inputs["days_since_rest"] = rest_day_series

    # Weekly volume (7-day rolling sum, km)
    weekly_vol_series = []
    for d in activity_dates:
        if d < analysis_start:
            continue
        week_total = sum(
            daily_distance.get(d - timedelta(days=i), 0) for i in range(7)
        )
        weekly_vol_series.append((d, week_total / 1000.0))
    if weekly_vol_series:
        inputs["weekly_volume_km"] = weekly_vol_series

    # Long run ratio (longest run / weekly volume)
    long_run_ratio_series = []
    for d in activity_dates:
        if d < analysis_start:
            continue
        week_distances = [
            daily_distance.get(d - timedelta(days=i), 0) for i in range(7)
        ]
        week_total = sum(week_distances)
        if week_total > 0:
            longest = max(week_distances)
            long_run_ratio_series.append((d, longest / week_total))
    if long_run_ratio_series:
        inputs["long_run_ratio"] = long_run_ratio_series

    # Weekly elevation (7-day rolling sum)
    weekly_elev_series = []
    for d in activity_dates:
        if d < analysis_start:
            continue
        week_elev = sum(
            daily_elevation.get(d - timedelta(days=i), 0) for i in range(7)
        )
        if week_elev > 0:
            weekly_elev_series.append((d, week_elev))
    if weekly_elev_series:
        inputs["weekly_elevation_m"] = weekly_elev_series

    return inputs
```

#### 5b. Wire into `analyze_correlations()`

Same location, add after the feedback_inputs line:

```python
pattern_inputs = aggregate_training_pattern_inputs(
    athlete_id, start_date, end_date, db
)
inputs.update(pattern_inputs)
```

Also add in `discover_combination_correlations()`.

---

## Phase 6: FRIENDLY_NAMES

### File: `apps/api/services/n1_insight_generator.py`

Find the `FRIENDLY_NAMES` dict (line ~89). Add ALL of these entries:

```python
# GarminDay wearable
"garmin_sleep_score": "Garmin sleep score",
"garmin_sleep_deep_s": "deep sleep time",
"garmin_sleep_rem_s": "REM sleep time",
"garmin_sleep_awake_s": "awake time during sleep",
"garmin_body_battery_end": "end-of-day body battery",
"garmin_avg_stress": "Garmin stress score",
"garmin_max_stress": "peak daily stress",
"garmin_steps": "daily step count",
"garmin_active_time_s": "daily active time",
"garmin_moderate_intensity_s": "moderate intensity time",
"garmin_vigorous_intensity_s": "vigorous intensity time",
"garmin_hrv_5min_high": "peak HRV window",
"garmin_min_hr": "lowest daily heart rate",
"garmin_vo2max": "Garmin VO2max",

# Activity-level
"dew_point_f": "dew point",
"heat_adjustment_pct": "heat impact",
"temperature_f": "temperature",
"humidity_pct": "humidity",
"elevation_gain_m": "elevation gain",
"avg_cadence": "running cadence",
"avg_stride_length_m": "stride length",
"avg_ground_contact_ms": "ground contact time",
"avg_vertical_oscillation_cm": "vertical bounce",
"avg_vertical_ratio_pct": "vertical ratio",
"avg_power_w": "running power",
"garmin_aerobic_te": "aerobic training effect",
"garmin_anaerobic_te": "anaerobic training effect",
"garmin_perceived_effort": "Garmin perceived effort",
"garmin_body_battery_impact": "body battery drain",
"activity_intensity_score": "session intensity",
"active_kcal": "calories burned",
"run_start_hour": "time of day",

# Feedback/reflection
"feedback_perceived_effort": "post-run perceived effort",
"feedback_energy_pre": "pre-run energy",
"feedback_energy_post": "post-run energy",
"feedback_leg_feel": "leg freshness",
"reflection_vs_expected": "run vs expectations",

# Checkin/composition/nutrition
"sleep_quality_1_5": "sleep quality",
"body_fat_pct": "body fat percentage",
"muscle_mass_kg": "muscle mass",
"daily_fat_g": "daily fat intake",
"daily_fiber_g": "daily fiber intake",
"daily_calories": "daily calorie intake",

# Training patterns
"days_since_quality": "rest since last hard session",
"consecutive_run_days": "consecutive running days",
"days_since_rest": "days without rest",
"weekly_volume_km": "weekly running volume",
"long_run_ratio": "long run proportion",
"weekly_elevation_m": "weekly elevation gain",
```

**IMPORTANT:** The key `"weekly_volume_km"` may already exist in the dict
as `"weekly running volume"`. If so, don't duplicate — just verify it's
there. Same for `"elevation_gain"` which may map to a different key.
Check for conflicts before adding.

---

## Phase 7: DIRECTION_EXPECTATIONS

### File: `apps/api/services/correlation_engine.py`

Find the `DIRECTION_EXPECTATIONS` dict (line ~85). Add:

```python
# GarminDay — recovery signals (higher = better)
("garmin_sleep_score", "efficiency"): "positive",
("garmin_sleep_deep_s", "efficiency"): "positive",
("garmin_sleep_rem_s", "efficiency"): "positive",
("garmin_body_battery_end", "efficiency"): "positive",
("garmin_hrv_5min_high", "efficiency"): "positive",
("garmin_sleep_score", "pace_easy"): "positive",
("garmin_body_battery_end", "pace_easy"): "positive",

# GarminDay — stress signals (higher = worse)
("garmin_avg_stress", "efficiency"): "negative",
("garmin_max_stress", "efficiency"): "negative",

# Heat (higher = worse performance)
("dew_point_f", "efficiency"): "negative",
("heat_adjustment_pct", "efficiency"): "negative",
("dew_point_f", "pace_easy"): "negative",

# Feedback (higher = better)
("feedback_energy_pre", "efficiency"): "positive",
("feedback_leg_feel", "efficiency"): "positive",

# Sleep quality
("sleep_quality_1_5", "efficiency"): "positive",
("sleep_quality_1_5", "pace_easy"): "positive",

# Training patterns (more consecutive days / less rest = worse)
("consecutive_run_days", "efficiency"): "negative",
("days_since_rest", "efficiency"): "negative",
```

---

## Phase 8: CONFOUNDER_MAP

### File: `apps/api/services/correlation_engine.py`

Find the `CONFOUNDER_MAP` dict (line ~52). Add:

```python
# Heat confounded by training load
("dew_point_f", "efficiency"): "daily_session_stress",
("heat_adjustment_pct", "efficiency"): "daily_session_stress",

# Garmin stress confounded by training load
("garmin_avg_stress", "efficiency"): "daily_session_stress",

# Body battery confounded by training load
("garmin_body_battery_end", "efficiency"): "daily_session_stress",

# Feedback confounded by training load
("feedback_perceived_effort", "efficiency"): "daily_session_stress",
("feedback_leg_feel", "efficiency"): "daily_session_stress",
("feedback_energy_pre", "efficiency"): "daily_session_stress",

# Steps confounded by training load
("garmin_steps", "efficiency"): "daily_session_stress",

# Volume confounded by fitness
("weekly_volume_km", "efficiency"): "ctl",
("weekly_volume_km", "pace_easy"): "ctl",
```

---

## Phase 9: Ban List Verification

### File: `apps/api/routers/home.py`

Find `_VOICE_INTERNAL_METRICS` (search for this variable name). Verify
that NONE of the new input keys appear on that list. They should not —
these are all athlete-meaningful terms.

If any new key appears on the ban list:
1) Confirm whether it is truly athlete-facing (not an internal model metric).
2) Remove only that specific key.
3) Add/adjust test coverage in `test_correlation_inputs.py` to lock the decision.
4) Document the key and rationale in the PR summary.

---

## Tests

### New file: `apps/api/tests/test_correlation_inputs.py`

Create this test file. All tests use the existing test infrastructure
(conftest fixtures, in-memory or test DB).

```python
"""
Tests for correlation engine input wiring.

Phase 1: GarminDay signals
Phase 2: Activity-level signals
Phase 3: Feedback/reflection signals
Phase 4: Checkin/composition/nutrition signals
Phase 5: Training pattern signals
Phase 6-9: FRIENDLY_NAMES, DIRECTION_EXPECTATIONS, CONFOUNDER_MAP, ban list
"""
import uuid
from datetime import datetime, timedelta, date, timezone
from unittest.mock import MagicMock

import pytest


# ── Phase 1: GarminDay ──

class TestPhase1GarminDay:

    def test_garmin_sleep_score_in_inputs(self, db, athlete):
        """GarminDay rows with sleep_score populate inputs['garmin_sleep_score']."""
        from models import GarminDay
        from services.correlation_engine import aggregate_daily_inputs

        gd = GarminDay(
            athlete_id=athlete.id,
            calendar_date=date.today(),
            sleep_score=82,
        )
        db.add(gd)
        db.commit()

        end = datetime.now(timezone.utc)
        start = end - timedelta(days=7)
        inputs = aggregate_daily_inputs(str(athlete.id), start, end, db)

        assert "garmin_sleep_score" in inputs
        assert len(inputs["garmin_sleep_score"]) >= 1
        assert inputs["garmin_sleep_score"][0][1] == 82.0

    def test_garmin_body_battery_in_inputs(self, db, athlete):
        """body_battery_end populates inputs['garmin_body_battery_end']."""
        from models import GarminDay
        from services.correlation_engine import aggregate_daily_inputs

        gd = GarminDay(
            athlete_id=athlete.id,
            calendar_date=date.today(),
            body_battery_end=45,
        )
        db.add(gd)
        db.commit()

        end = datetime.now(timezone.utc)
        start = end - timedelta(days=7)
        inputs = aggregate_daily_inputs(str(athlete.id), start, end, db)

        assert "garmin_body_battery_end" in inputs
        assert inputs["garmin_body_battery_end"][0][1] == 45.0

    def test_garmin_stress_in_inputs(self, db, athlete):
        """avg_stress populates inputs['garmin_avg_stress']."""
        from models import GarminDay
        from services.correlation_engine import aggregate_daily_inputs

        gd = GarminDay(
            athlete_id=athlete.id,
            calendar_date=date.today(),
            avg_stress=38,
        )
        db.add(gd)
        db.commit()

        end = datetime.now(timezone.utc)
        start = end - timedelta(days=7)
        inputs = aggregate_daily_inputs(str(athlete.id), start, end, db)

        assert "garmin_avg_stress" in inputs
        assert inputs["garmin_avg_stress"][0][1] == 38.0

    def test_garmin_no_data_returns_empty(self, db, athlete):
        """No GarminDay rows → all garmin_* keys have empty lists."""
        from services.correlation_engine import aggregate_daily_inputs

        end = datetime.now(timezone.utc)
        start = end - timedelta(days=7)
        inputs = aggregate_daily_inputs(str(athlete.id), start, end, db)

        for key in [
            "garmin_sleep_score", "garmin_body_battery_end",
            "garmin_avg_stress", "garmin_steps",
        ]:
            assert key in inputs
            assert inputs[key] == []

    def test_garmin_null_fields_excluded(self, db, athlete):
        """Rows with NULL fields produce empty series for those signals."""
        from models import GarminDay
        from services.correlation_engine import aggregate_daily_inputs

        gd = GarminDay(
            athlete_id=athlete.id,
            calendar_date=date.today(),
            sleep_score=None,
            body_battery_end=55,
        )
        db.add(gd)
        db.commit()

        end = datetime.now(timezone.utc)
        start = end - timedelta(days=7)
        inputs = aggregate_daily_inputs(str(athlete.id), start, end, db)

        assert inputs["garmin_sleep_score"] == []
        assert len(inputs["garmin_body_battery_end"]) == 1


# ── Phase 2: Activity-level ──

class TestPhase2ActivityLevel:

    def _make_activity(self, db, athlete, **kwargs):
        from models import Activity
        defaults = dict(
            athlete_id=athlete.id,
            start_time=datetime.now(timezone.utc),
            sport="run",
            source="strava",
            distance_m=5000,
            duration_s=1500,
            avg_hr=145,
        )
        defaults.update(kwargs)
        a = Activity(**defaults)
        db.add(a)
        db.commit()
        return a

    def test_activity_dew_point_input(self, db, athlete):
        from services.correlation_engine import aggregate_activity_level_inputs
        self._make_activity(db, athlete, dew_point_f=62.5)
        end = datetime.now(timezone.utc) + timedelta(days=1)
        start = end - timedelta(days=7)
        inputs = aggregate_activity_level_inputs(str(athlete.id), start, end, db)
        assert "dew_point_f" in inputs
        assert inputs["dew_point_f"][0][1] == 62.5

    def test_activity_cadence_input(self, db, athlete):
        from services.correlation_engine import aggregate_activity_level_inputs
        self._make_activity(db, athlete, avg_cadence=178)
        end = datetime.now(timezone.utc) + timedelta(days=1)
        start = end - timedelta(days=7)
        inputs = aggregate_activity_level_inputs(str(athlete.id), start, end, db)
        assert "avg_cadence" in inputs
        assert inputs["avg_cadence"][0][1] == 178.0

    def test_activity_multi_run_day_takes_longest(self, db, athlete):
        """Two runs on same day → longest run's values used."""
        from services.correlation_engine import aggregate_activity_level_inputs
        now = datetime.now(timezone.utc)
        self._make_activity(
            db, athlete, start_time=now, distance_m=3000,
            avg_cadence=170,
        )
        self._make_activity(
            db, athlete, start_time=now + timedelta(hours=4),
            distance_m=10000, avg_cadence=180,
        )
        end = now + timedelta(days=1)
        start = end - timedelta(days=7)
        inputs = aggregate_activity_level_inputs(str(athlete.id), start, end, db)
        assert inputs["avg_cadence"][0][1] == 180.0

    def test_activity_run_start_hour(self, db, athlete):
        from services.correlation_engine import aggregate_activity_level_inputs
        morning = datetime(2026, 3, 10, 6, 30, tzinfo=timezone.utc)
        self._make_activity(db, athlete, start_time=morning)
        end = morning + timedelta(days=1)
        start = end - timedelta(days=7)
        inputs = aggregate_activity_level_inputs(str(athlete.id), start, end, db)
        assert "run_start_hour" in inputs
        assert inputs["run_start_hour"][0][1] == 6.0

    def test_activity_elevation_input(self, db, athlete):
        from services.correlation_engine import aggregate_activity_level_inputs
        self._make_activity(db, athlete, total_elevation_gain=125.5)
        end = datetime.now(timezone.utc) + timedelta(days=1)
        start = end - timedelta(days=7)
        inputs = aggregate_activity_level_inputs(str(athlete.id), start, end, db)
        assert "elevation_gain_m" in inputs
        assert inputs["elevation_gain_m"][0][1] == 125.5


# ── Phase 3: Feedback/Reflection ──

class TestPhase3Feedback:

    def test_feedback_leg_feel_ordinal(self, db, athlete):
        from models import ActivityFeedback, Activity
        from services.correlation_engine import aggregate_feedback_inputs

        a = Activity(
            athlete_id=athlete.id, start_time=datetime.now(timezone.utc),
            sport="run", source="strava",
        )
        db.add(a)
        db.flush()

        fb = ActivityFeedback(
            activity_id=a.id, athlete_id=athlete.id,
            leg_feel="fresh",
            submitted_at=datetime.now(timezone.utc),
        )
        db.add(fb)
        db.commit()

        end = datetime.now(timezone.utc) + timedelta(days=1)
        start = end - timedelta(days=7)
        inputs = aggregate_feedback_inputs(str(athlete.id), start, end, db)
        assert "feedback_leg_feel" in inputs
        assert inputs["feedback_leg_feel"][0][1] == 5.0

    def test_reflection_ordinal(self, db, athlete):
        from models import ActivityReflection, Activity
        from services.correlation_engine import aggregate_feedback_inputs

        a = Activity(
            athlete_id=athlete.id, start_time=datetime.now(timezone.utc),
            sport="run", source="strava",
        )
        db.add(a)
        db.flush()

        ref = ActivityReflection(
            activity_id=a.id, athlete_id=athlete.id,
            response="easier",
            created_at=datetime.now(timezone.utc),
        )
        db.add(ref)
        db.commit()

        end = datetime.now(timezone.utc) + timedelta(days=1)
        start = end - timedelta(days=7)
        inputs = aggregate_feedback_inputs(str(athlete.id), start, end, db)
        assert "reflection_vs_expected" in inputs
        assert inputs["reflection_vs_expected"][0][1] == 1.0

    def test_feedback_empty_when_no_data(self, db, athlete):
        from services.correlation_engine import aggregate_feedback_inputs
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=7)
        inputs = aggregate_feedback_inputs(str(athlete.id), start, end, db)
        assert inputs == {}


# ── Phase 4: Checkin/Composition/Nutrition ──

class TestPhase4CheckinComposition:

    def test_sleep_quality_in_inputs(self, db, athlete):
        from models import DailyCheckin
        from services.correlation_engine import aggregate_daily_inputs

        dc = DailyCheckin(
            athlete_id=athlete.id,
            date=date.today(),
            sleep_quality_1_5=4,
        )
        db.add(dc)
        db.commit()

        end = datetime.now(timezone.utc)
        start = end - timedelta(days=7)
        inputs = aggregate_daily_inputs(str(athlete.id), start, end, db)
        assert "sleep_quality_1_5" in inputs
        assert inputs["sleep_quality_1_5"][0][1] == 4.0

    def test_body_fat_pct_in_inputs(self, db, athlete):
        from models import BodyComposition
        from services.correlation_engine import aggregate_daily_inputs

        bc = BodyComposition(
            athlete_id=athlete.id,
            date=date.today(),
            body_fat_pct=15.2,
        )
        db.add(bc)
        db.commit()

        end = datetime.now(timezone.utc)
        start = end - timedelta(days=7)
        inputs = aggregate_daily_inputs(str(athlete.id), start, end, db)
        assert "body_fat_pct" in inputs
        assert inputs["body_fat_pct"][0][1] == 15.2

    def test_daily_calories_in_inputs(self, db, athlete):
        from models import NutritionEntry
        from services.correlation_engine import aggregate_daily_inputs

        n1 = NutritionEntry(
            athlete_id=athlete.id,
            date=date.today(),
            calories=800,
            entry_type="daily",
        )
        n2 = NutritionEntry(
            athlete_id=athlete.id,
            date=date.today(),
            calories=1200,
            entry_type="daily",
        )
        db.add_all([n1, n2])
        db.commit()

        end = datetime.now(timezone.utc)
        start = end - timedelta(days=7)
        inputs = aggregate_daily_inputs(str(athlete.id), start, end, db)
        assert "daily_calories" in inputs
        assert inputs["daily_calories"][0][1] == 2000.0


# ── Phase 5: Training Patterns ──

class TestPhase5TrainingPatterns:

    def _make_run(self, db, athlete, days_ago, distance_m=5000, workout_type=None):
        from models import Activity
        a = Activity(
            athlete_id=athlete.id,
            start_time=datetime.now(timezone.utc) - timedelta(days=days_ago),
            sport="run", source="strava",
            distance_m=distance_m, duration_s=1500, avg_hr=140,
            workout_type=workout_type,
        )
        db.add(a)
        return a

    def test_days_since_quality(self, db, athlete):
        from services.correlation_engine import aggregate_training_pattern_inputs
        self._make_run(db, athlete, days_ago=3, workout_type="intervals")
        self._make_run(db, athlete, days_ago=2)
        self._make_run(db, athlete, days_ago=1)
        db.commit()

        end = datetime.now(timezone.utc)
        start = end - timedelta(days=7)
        inputs = aggregate_training_pattern_inputs(str(athlete.id), start, end, db)
        assert "days_since_quality" in inputs
        values = {d: v for d, v in inputs["days_since_quality"]}
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date()
        assert values.get(yesterday) == 2.0

    def test_consecutive_run_days(self, db, athlete):
        from services.correlation_engine import aggregate_training_pattern_inputs
        self._make_run(db, athlete, days_ago=3)
        self._make_run(db, athlete, days_ago=2)
        self._make_run(db, athlete, days_ago=1)
        db.commit()

        end = datetime.now(timezone.utc)
        start = end - timedelta(days=7)
        inputs = aggregate_training_pattern_inputs(str(athlete.id), start, end, db)
        assert "consecutive_run_days" in inputs
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date()
        values = {d: v for d, v in inputs["consecutive_run_days"]}
        assert values.get(yesterday) == 3.0

    def test_weekly_volume_km(self, db, athlete):
        from services.correlation_engine import aggregate_training_pattern_inputs
        self._make_run(db, athlete, days_ago=1, distance_m=10000)
        self._make_run(db, athlete, days_ago=2, distance_m=5000)
        db.commit()

        end = datetime.now(timezone.utc)
        start = end - timedelta(days=7)
        inputs = aggregate_training_pattern_inputs(str(athlete.id), start, end, db)
        assert "weekly_volume_km" in inputs
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date()
        values = {d: v for d, v in inputs["weekly_volume_km"]}
        assert values.get(yesterday) == 15.0

    def test_long_run_ratio(self, db, athlete):
        from services.correlation_engine import aggregate_training_pattern_inputs
        self._make_run(db, athlete, days_ago=1, distance_m=20000)
        self._make_run(db, athlete, days_ago=3, distance_m=5000)
        self._make_run(db, athlete, days_ago=5, distance_m=5000)
        self._make_run(db, athlete, days_ago=6, distance_m=5000)
        self._make_run(db, athlete, days_ago=7, distance_m=5000)
        db.commit()

        end = datetime.now(timezone.utc)
        start = end - timedelta(days=10)
        inputs = aggregate_training_pattern_inputs(str(athlete.id), start, end, db)
        assert "long_run_ratio" in inputs
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date()
        values = {d: v for d, v in inputs["long_run_ratio"]}
        assert values.get(yesterday) == 0.5


# ── Phase 6-9: Integration ──

class TestPhaseIntegration:

    def test_friendly_names_cover_all_new_inputs(self):
        """Every new input key has a FRIENDLY_NAMES entry."""
        from services.n1_insight_generator import FRIENDLY_NAMES

        ALL_NEW_KEYS = [
            # GarminDay
            "garmin_sleep_score", "garmin_sleep_deep_s", "garmin_sleep_rem_s",
            "garmin_sleep_awake_s", "garmin_body_battery_end",
            "garmin_avg_stress", "garmin_max_stress", "garmin_steps",
            "garmin_active_time_s", "garmin_moderate_intensity_s",
            "garmin_vigorous_intensity_s", "garmin_hrv_5min_high",
            "garmin_min_hr", "garmin_vo2max",
            # Activity
            "dew_point_f", "heat_adjustment_pct", "temperature_f",
            "humidity_pct", "elevation_gain_m", "avg_cadence",
            "avg_stride_length_m", "avg_ground_contact_ms",
            "avg_vertical_oscillation_cm", "avg_vertical_ratio_pct",
            "avg_power_w", "garmin_aerobic_te", "garmin_anaerobic_te",
            "garmin_perceived_effort", "garmin_body_battery_impact",
            "activity_intensity_score", "active_kcal", "run_start_hour",
            # Feedback
            "feedback_perceived_effort", "feedback_energy_pre",
            "feedback_energy_post", "feedback_leg_feel",
            "reflection_vs_expected",
            # Checkin/comp/nutrition
            "sleep_quality_1_5", "body_fat_pct", "muscle_mass_kg",
            "daily_fat_g", "daily_fiber_g", "daily_calories",
            # Training patterns
            "days_since_quality", "consecutive_run_days",
            "days_since_rest", "weekly_volume_km", "long_run_ratio",
            "weekly_elevation_m",
        ]

        missing = [k for k in ALL_NEW_KEYS if k not in FRIENDLY_NAMES]
        assert missing == [], f"Missing FRIENDLY_NAMES: {missing}"

    def test_no_new_inputs_on_ban_list(self):
        """No new input key appears in _VOICE_INTERNAL_METRICS."""
        import importlib
        import sys

        home_mod = importlib.import_module("routers.home")
        ban_list = getattr(home_mod, "_VOICE_INTERNAL_METRICS", [])

        ALL_NEW_KEYS = [
            "garmin_sleep_score", "garmin_body_battery_end",
            "dew_point_f", "avg_cadence", "feedback_leg_feel",
            "sleep_quality_1_5", "days_since_quality",
        ]

        banned = [k for k in ALL_NEW_KEYS if k in ban_list]
        assert banned == [], f"These should NOT be banned: {banned}"
```

---

## Files Changed (for git add)

```
apps/api/services/correlation_engine.py    # Phases 1-5, 7-8
apps/api/services/n1_insight_generator.py  # Phase 6
apps/api/tests/test_correlation_inputs.py  # New test file
```

---

## What This Does NOT Touch

- No frontend files
- No database migrations
- No new API endpoints
- No celerybeat schedule changes
- No model changes
- No Docker/deploy changes

---

## Deploy

After CI green:

```bash
ssh root@strideiq.run
cd /opt/strideiq/repo && git pull origin main && docker compose -f docker-compose.prod.yml up -d --build
```

The next daily correlation sweep (08:00 UTC) will automatically run all
70 inputs against all 9 output metrics for every active athlete.

## Post-Deploy Verification

```bash
docker exec -w /app strideiq_api python -c "
from datetime import datetime, timedelta, timezone
from core.database import SessionLocal
from models import Athlete
from services.correlation_engine import (
    aggregate_daily_inputs,
    aggregate_activity_level_inputs,
    aggregate_feedback_inputs,
    aggregate_training_pattern_inputs,
)
db = SessionLocal()
user = db.query(Athlete).filter(Athlete.email=='mbshaf@gmail.com').first()
aid = str(user.id)
end = datetime.now(timezone.utc)
start = end - timedelta(days=90)

daily = aggregate_daily_inputs(aid, start, end, db)
activity = aggregate_activity_level_inputs(aid, start, end, db)
feedback = aggregate_feedback_inputs(aid, start, end, db)
patterns = aggregate_training_pattern_inputs(aid, start, end, db)

print(f'Daily inputs: {len(daily)} signals')
for k, v in sorted(daily.items()):
    print(f'  {k}: {len(v)} data points')

print(f'Activity inputs: {len(activity)} signals')
for k, v in sorted(activity.items()):
    print(f'  {k}: {len(v)} data points')

print(f'Feedback inputs: {len(feedback)} signals')
for k, v in sorted(feedback.items()):
    print(f'  {k}: {len(v)} data points')

print(f'Pattern inputs: {len(patterns)} signals')
for k, v in sorted(patterns.items()):
    print(f'  {k}: {len(v)} data points')

total = len(daily) + len(activity) + len(feedback) + len(patterns)
print(f'TOTAL: {total} input signals')

# Hard verification gates (fail-fast)
required_daily = {
    'garmin_sleep_score', 'garmin_body_battery_end', 'garmin_avg_stress',
    'sleep_quality_1_5', 'body_fat_pct', 'daily_calories'
}
required_activity = {
    'dew_point_f', 'avg_cadence', 'run_start_hour', 'activity_intensity_score'
}
required_feedback = {
    'feedback_perceived_effort', 'feedback_leg_feel', 'reflection_vs_expected'
}
required_patterns = {
    'days_since_quality', 'consecutive_run_days', 'weekly_volume_km', 'long_run_ratio'
}

missing = []
missing += [f'daily:{k}' for k in required_daily if k not in daily]
missing += [f'activity:{k}' for k in required_activity if k not in activity]
missing += [f'feedback:{k}' for k in required_feedback if k not in feedback]
missing += [f'patterns:{k}' for k in required_patterns if k not in patterns]
if missing:
    raise SystemExit(f'MISSING REQUIRED WIRED KEYS: {missing}')

if total < 70:
    raise SystemExit(f'INPUT WIRING INCOMPLETE: expected >=70 keys, got {total}')
db.close()
"
```

Expected:
- `TOTAL: >= 70 input signals`
- No `MISSING REQUIRED WIRED KEYS` failure
- Some series may have zero points for athletes without that data; that's fine.
