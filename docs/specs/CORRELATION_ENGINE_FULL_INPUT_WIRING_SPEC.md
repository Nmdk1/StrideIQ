# Correlation Engine — Full Input Wiring Spec

**Date:** March 10, 2026  
**Priority:** P0 — highest ROI work in the system right now  
**Reference:** `docs/DATA_INTELLIGENCE_AUDIT_2026-03-10.md`  
**Principle:** The engine can only discover what it can see. 81% of stored
data is invisible to it. This spec wires all of it.

---

## Architecture Context

The correlation engine (`apps/api/services/correlation_engine.py`) works
in one loop:

1. **Collect inputs** — `aggregate_daily_inputs()` builds a dict of
   `{signal_name: [(date, value), ...]}`.
2. **Collect outputs** — efficiency, pace, completion, PB events, etc.
3. **Correlate** — `find_time_shifted_correlations()` tests each input
   against each output with lags 0–7 days.
4. **Persist** — significant findings become `CorrelationFinding` rows.
5. **Surface** — findings appear on home page, progress, coach.

Adding a new input signal requires:
- A query in `aggregate_daily_inputs()` (or a new aggregator)
- A key in the `inputs` dict
- A `FRIENDLY_NAMES` entry in `n1_insight_generator.py`
- Optionally: `DIRECTION_EXPECTATIONS` and `CONFOUNDER_MAP` entries

Everything downstream (correlation math, persistence, surfacing, finding
cooldowns, layer detection) works automatically.

---

## Phase 1: GarminDay Wearable Signals

**File:** `apps/api/services/correlation_engine.py`  
**Function:** `aggregate_daily_inputs()` (line ~247)  
**Add import:** `from models import GarminDay` (line ~28)

Add a new section after the existing DailyCheckin/WorkPattern/Nutrition
blocks (after line ~479, after `hrv_sdnn`). Each signal follows the
identical pattern.

### 1.1 Signals to Add

| # | Input Key | Source | Field | Notes |
|---|----------|--------|-------|-------|
| 1 | `garmin_sleep_score` | GarminDay | sleep_score | 0–100, Garmin's composite |
| 2 | `garmin_sleep_deep_s` | GarminDay | sleep_deep_s | Deep sleep seconds |
| 3 | `garmin_sleep_rem_s` | GarminDay | sleep_rem_s | REM sleep seconds |
| 4 | `garmin_sleep_awake_s` | GarminDay | sleep_awake_s | Awake time during sleep |
| 5 | `garmin_body_battery_end` | GarminDay | body_battery_end | End-of-day body battery |
| 6 | `garmin_avg_stress` | GarminDay | avg_stress | Daily stress score 0–100 |
| 7 | `garmin_max_stress` | GarminDay | max_stress | Peak stress in day |
| 8 | `garmin_steps` | GarminDay | steps | Daily step count |
| 9 | `garmin_active_time_s` | GarminDay | active_time_s | Total active seconds |
| 10 | `garmin_moderate_intensity_s` | GarminDay | moderate_intensity_s | Moderate zone seconds |
| 11 | `garmin_vigorous_intensity_s` | GarminDay | vigorous_intensity_s | Vigorous zone seconds |
| 12 | `garmin_hrv_5min_high` | GarminDay | hrv_5min_high | Best 5-min HRV window |
| 13 | `garmin_min_hr` | GarminDay | min_hr | Lowest HR in day |
| 14 | `garmin_vo2max` | GarminDay | vo2max | Garmin VO2max estimate |

### 1.2 Code Pattern

Every signal follows this exact pattern:

```python
# Garmin sleep score
_garmin_sleep_score = db.query(
    GarminDay.calendar_date,
    GarminDay.sleep_score
).filter(
    GarminDay.athlete_id == athlete_id,
    GarminDay.calendar_date >= start_date.date(),
    GarminDay.calendar_date <= end_date.date(),
    GarminDay.sleep_score.isnot(None)
).all()

inputs["garmin_sleep_score"] = [
    (row.calendar_date, float(row.sleep_score)) for row in _garmin_sleep_score
]
```

Repeat for all 14 signals. The query filter is always:
- `athlete_id == athlete_id`
- `calendar_date >= start_date.date()`
- `calendar_date <= end_date.date()`
- `field.isnot(None)`

### 1.3 Performance Note

These 14 queries hit GarminDay separately. An optimization would be a
single query fetching all non-null columns per date, but for v1 the
individual query pattern matches the existing code style and is clear.
Optimize later if profiling shows it matters.

---

## Phase 2: Activity-Level Signals

**File:** `apps/api/services/correlation_engine.py`

Activity-level signals need a new aggregator function because they come
from Activity, not from daily wellness tables. They are per-activity
values aggregated to a daily date for the correlation framework.

### 2.1 New Function: `aggregate_activity_level_inputs()`

Add after `aggregate_daily_inputs()`:

```python
def aggregate_activity_level_inputs(
    athlete_id: str,
    start_date: datetime,
    end_date: datetime,
    db: Session
) -> Dict[str, List[Tuple[date_type, float]]]:
    """
    Aggregate activity-level signals into daily time series.

    For days with multiple activities, uses the primary run
    (longest distance) to avoid mixing easy jog signals with
    interval session signals.
    """
    from sqlalchemy import func as sqla_func

    inputs: Dict[str, List[Tuple[date_type, float]]] = {}

    # Fetch all non-duplicate run activities in the window
    activities = db.query(Activity).filter(
        Activity.athlete_id == athlete_id,
        Activity.is_duplicate == False,  # noqa: E712
        Activity.sport == "run",
        Activity.start_time >= start_date,
        Activity.start_time <= end_date,
    ).order_by(Activity.start_time).all()

    if not activities:
        return inputs

    # Group by date, keep longest run per day
    from collections import defaultdict
    by_date: Dict[date_type, Activity] = {}
    for a in activities:
        d = a.start_time.date()
        if d not in by_date or (a.distance_m or 0) > (by_date[d].distance_m or 0):
            by_date[d] = a

    # Extract signals from the primary activity per day
    for signal_key, attr, transform in [
        ("dew_point_f", "dew_point_f", None),
        ("heat_adjustment_pct", "heat_adjustment_pct", None),
        ("temperature_f", "temperature_f", None),
        ("humidity_pct", "humidity_pct", None),
        ("elevation_gain_m", "total_elevation_gain", lambda v: float(v)),
        ("avg_cadence", "avg_cadence", None),
        ("avg_stride_length_m", "avg_stride_length_m", None),
        ("avg_ground_contact_ms", "avg_ground_contact_ms", None),
        ("avg_vertical_oscillation_cm", "avg_vertical_oscillation_cm", None),
        ("avg_vertical_ratio_pct", "avg_vertical_ratio_pct", None),
        ("avg_power_w", "avg_power_w", None),
        ("garmin_aerobic_te", "garmin_aerobic_te", None),
        ("garmin_anaerobic_te", "garmin_anaerobic_te", None),
        ("garmin_perceived_effort", "garmin_perceived_effort", None),
        ("garmin_body_battery_impact", "garmin_body_battery_impact", None),
        ("activity_intensity_score", "intensity_score", None),
        ("active_kcal", "active_kcal", None),
    ]:
        series = []
        for d, a in sorted(by_date.items()):
            val = getattr(a, attr, None)
            if val is not None:
                fval = float(val) if transform is None else transform(val)
                if signal_key == "heat_adjustment_pct" and fval <= 0:
                    continue
                series.append((d, fval))
        if series:
            inputs[signal_key] = series

    # Time-of-day: extract hour as a signal
    tod_series = []
    for d, a in sorted(by_date.items()):
        if a.start_time:
            tod_series.append((d, float(a.start_time.hour)))
    if tod_series:
        inputs["run_start_hour"] = tod_series

    return inputs
```

### 2.2 Wire Into `analyze_correlations()`

In `analyze_correlations()`, after the existing `inputs.update(load_inputs)` 
block (line ~1228), add:

```python
# Add activity-level inputs
activity_inputs = aggregate_activity_level_inputs(
    athlete_id, start_date, end_date, db
)
inputs.update(activity_inputs)
```

Also add the same call in `discover_combination_correlations()` after its
`aggregate_daily_inputs()` call (~line 1392).

### 2.3 Signals Added (18 total)

| # | Input Key | Source Field | What It Measures |
|---|----------|-------------|------------------|
| 1 | dew_point_f | Activity.dew_point_f | Heat stress |
| 2 | heat_adjustment_pct | Activity.heat_adjustment_pct | N=1 heat penalty |
| 3 | temperature_f | Activity.temperature_f | Temperature |
| 4 | humidity_pct | Activity.humidity_pct | Humidity |
| 5 | elevation_gain_m | Activity.total_elevation_gain | Vertical gain |
| 6 | avg_cadence | Activity.avg_cadence | Running cadence |
| 7 | avg_stride_length_m | Activity.avg_stride_length_m | Stride length |
| 8 | avg_ground_contact_ms | Activity.avg_ground_contact_ms | Ground contact |
| 9 | avg_vertical_oscillation_cm | Activity.avg_vertical_oscillation_cm | Vertical bounce |
| 10 | avg_vertical_ratio_pct | Activity.avg_vertical_ratio_pct | Stride efficiency |
| 11 | avg_power_w | Activity.avg_power_w | Running power |
| 12 | garmin_aerobic_te | Activity.garmin_aerobic_te | Aerobic training effect |
| 13 | garmin_anaerobic_te | Activity.garmin_anaerobic_te | Anaerobic training effect |
| 14 | garmin_perceived_effort | Activity.garmin_perceived_effort | Garmin RPE |
| 15 | garmin_body_battery_impact | Activity.garmin_body_battery_impact | Battery drain from run |
| 16 | activity_intensity_score | Activity.intensity_score | Computed intensity |
| 17 | active_kcal | Activity.active_kcal | Calories burned |
| 18 | run_start_hour | Activity.start_time (hour) | Time of day |

**Note:** This supersedes the separate heat correlation builder
instructions in `BUILDER_INSTRUCTIONS_2026-03-10_HEAT_CORRELATION_INPUT.md`.
Heat signals `dew_point_f` and `heat_adjustment_pct` are included here.

---

## Phase 3: Feedback & Reflection Signals

These models store athlete perceptual data that is never queried by the
engine despite `ActivityFeedback` being imported.

### 3.1 New Function: `aggregate_feedback_inputs()`

**File:** `apps/api/services/correlation_engine.py`

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

    # ActivityFeedback
    from models import ActivityFeedback, ActivityReflection

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

    LEG_FEEL_ORDINAL = {
        "fresh": 5, "normal": 4, "tired": 3,
        "heavy": 2, "sore": 1, "injured": 0,
    }

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
        if row.leg_feel and row.leg_feel in LEG_FEEL_ORDINAL:
            leg_feel.append((d, float(LEG_FEEL_ORDINAL[row.leg_feel])))

    if perceived_effort:
        inputs["feedback_perceived_effort"] = perceived_effort
    if energy_pre:
        inputs["feedback_energy_pre"] = energy_pre
    if energy_post:
        inputs["feedback_energy_post"] = energy_post
    if leg_feel:
        inputs["feedback_leg_feel"] = leg_feel

    # ActivityReflection — harder/expected/easier → -1/0/+1
    REFLECTION_ORDINAL = {"harder": -1, "expected": 0, "easier": 1}

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
        val = REFLECTION_ORDINAL.get(row.response)
        if val is not None:
            reflection_series.append((d, float(val)))

    if reflection_series:
        inputs["reflection_vs_expected"] = reflection_series

    return inputs
```

### 3.2 Wire Into `analyze_correlations()`

Same location as Phase 2:

```python
# Add feedback/reflection inputs
feedback_inputs = aggregate_feedback_inputs(
    athlete_id, start_date, end_date, db
)
inputs.update(feedback_inputs)
```

### 3.3 Signals Added (5 total)

| # | Input Key | Source | What It Measures |
|---|----------|--------|------------------|
| 1 | feedback_perceived_effort | ActivityFeedback.perceived_effort | Post-run RPE |
| 2 | feedback_energy_pre | ActivityFeedback.energy_pre | Pre-run energy (1–10) |
| 3 | feedback_energy_post | ActivityFeedback.energy_post | Post-run energy (1–10) |
| 4 | feedback_leg_feel | ActivityFeedback.leg_feel | Leg freshness (ordinal 0–5) |
| 5 | reflection_vs_expected | ActivityReflection.response | -1/0/+1 (harder/expected/easier) |

---

## Phase 4: Missing Checkin + Composition Signals

### 4.1 DailyCheckin — `sleep_quality_1_5`

Add to `aggregate_daily_inputs()`, after the existing sleep_h block:

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

### 4.2 BodyComposition — `body_fat_pct`, `muscle_mass_kg`

Add to `aggregate_daily_inputs()`, after the existing bmi block:

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

### 4.3 NutritionEntry — `fat_g`, `fiber_g`, `calories`

Add to `aggregate_daily_inputs()`, after the existing carbs block:

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

### 4.4 Signals Added (6 total)

| # | Input Key | Source | What It Measures |
|---|----------|--------|------------------|
| 1 | sleep_quality_1_5 | DailyCheckin | Subjective sleep quality |
| 2 | body_fat_pct | BodyComposition | Body fat percentage |
| 3 | muscle_mass_kg | BodyComposition | Muscle mass |
| 4 | daily_fat_g | NutritionEntry | Daily fat intake |
| 5 | daily_fiber_g | NutritionEntry | Daily fiber intake |
| 6 | daily_calories | NutritionEntry | Daily total calories |

---

## Phase 5: Derived Training Pattern Signals

These signals don't live in a single column — they must be computed from
activity history.

### 5.1 New Function: `aggregate_training_pattern_inputs()`

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

    QUALITY_TYPES = {"intervals", "tempo", "threshold", "race", "fartlek", "hills"}

    # Build daily lookups
    from collections import defaultdict
    daily_distance: Dict[date_type, float] = defaultdict(float)
    daily_elevation: Dict[date_type, float] = defaultdict(float)
    daily_quality: Dict[date_type, bool] = defaultdict(bool)

    for a in activities:
        d = a.start_time.date()
        daily_distance[d] += float(a.distance_m or 0)
        daily_elevation[d] += float(a.total_elevation_gain or 0)
        if a.workout_type and a.workout_type.lower() in QUALITY_TYPES:
            daily_quality[d] = True

    # --- Days since last quality session ---
    days_since_quality = []
    last_quality_date = None
    current = start_date.date()
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

    # --- Consecutive run days ---
    consec_series = []
    for d in activity_dates:
        if d < start_date.date():
            continue
        streak = 0
        check = d
        while check in activity_date_set:
            streak += 1
            check -= timedelta(days=1)
        consec_series.append((d, float(streak)))

    if consec_series:
        inputs["consecutive_run_days"] = consec_series

    # --- Days since last rest day ---
    rest_day_series = []
    for d in activity_dates:
        if d < start_date.date():
            continue
        gap = 0
        check = d - timedelta(days=1)
        while check in activity_date_set:
            gap += 1
            check -= timedelta(days=1)
        rest_day_series.append((d, float(gap + 1)))

    if rest_day_series:
        inputs["days_since_rest"] = rest_day_series

    # --- Weekly volume (7-day rolling sum, km) ---
    weekly_vol_series = []
    for d in activity_dates:
        if d < start_date.date():
            continue
        week_total = sum(
            daily_distance.get(d - timedelta(days=i), 0)
            for i in range(7)
        )
        weekly_vol_series.append((d, week_total / 1000.0))

    if weekly_vol_series:
        inputs["weekly_volume_km"] = weekly_vol_series

    # --- Long run ratio (longest run / weekly volume) ---
    long_run_ratio_series = []
    for d in activity_dates:
        if d < start_date.date():
            continue
        week_distances = [
            daily_distance.get(d - timedelta(days=i), 0)
            for i in range(7)
        ]
        week_total = sum(week_distances)
        if week_total > 0:
            longest = max(week_distances)
            long_run_ratio_series.append((d, longest / week_total))

    if long_run_ratio_series:
        inputs["long_run_ratio"] = long_run_ratio_series

    # --- Weekly elevation trend (7-day rolling sum) ---
    weekly_elev_series = []
    for d in activity_dates:
        if d < start_date.date():
            continue
        week_elev = sum(
            daily_elevation.get(d - timedelta(days=i), 0)
            for i in range(7)
        )
        if week_elev > 0:
            weekly_elev_series.append((d, week_elev))

    if weekly_elev_series:
        inputs["weekly_elevation_m"] = weekly_elev_series

    return inputs
```

### 5.2 Wire Into `analyze_correlations()`

```python
# Add training pattern inputs
pattern_inputs = aggregate_training_pattern_inputs(
    athlete_id, start_date, end_date, db
)
inputs.update(pattern_inputs)
```

### 5.3 Signals Added (6 total)

| # | Input Key | What It Measures |
|---|----------|------------------|
| 1 | days_since_quality | Rest gap before current run |
| 2 | consecutive_run_days | Run streak length |
| 3 | days_since_rest | Recovery gap |
| 4 | weekly_volume_km | 7-day rolling mileage |
| 5 | long_run_ratio | Long run as % of weekly volume |
| 6 | weekly_elevation_m | 7-day rolling elevation |

---

## Phase 6: FRIENDLY_NAMES

**File:** `apps/api/services/n1_insight_generator.py`  
**Dict:** `FRIENDLY_NAMES` (line ~89)

Add all new input signals:

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

---

## Phase 7: DIRECTION_EXPECTATIONS

**File:** `apps/api/services/correlation_engine.py`  
**Dict:** `DIRECTION_EXPECTATIONS` (line ~85)

Add entries where direction is physiologically clear:

```python
# GarminDay — higher = better recovery
("garmin_sleep_score", "efficiency"): "positive",
("garmin_sleep_deep_s", "efficiency"): "positive",
("garmin_sleep_rem_s", "efficiency"): "positive",
("garmin_body_battery_end", "efficiency"): "positive",
("garmin_hrv_5min_high", "efficiency"): "positive",
("garmin_sleep_score", "pace_easy"): "positive",
("garmin_body_battery_end", "pace_easy"): "positive",

# GarminDay — higher = more stress
("garmin_avg_stress", "efficiency"): "negative",
("garmin_max_stress", "efficiency"): "negative",

# Heat — higher = worse performance
("dew_point_f", "efficiency"): "negative",
("heat_adjustment_pct", "efficiency"): "negative",
("dew_point_f", "pace_easy"): "negative",

# Feedback — higher energy/freshness = better
("feedback_energy_pre", "efficiency"): "positive",
("feedback_leg_feel", "efficiency"): "positive",

# Sleep quality
("sleep_quality_1_5", "efficiency"): "positive",
("sleep_quality_1_5", "pace_easy"): "positive",

# Training patterns
("consecutive_run_days", "efficiency"): "negative",
("days_since_rest", "efficiency"): "negative",
```

Leave others without expectations — let the engine discover direction
empirically. Counterintuitive findings are flagged automatically.

---

## Phase 8: CONFOUNDER_MAP

**File:** `apps/api/services/correlation_engine.py`  
**Dict:** `CONFOUNDER_MAP` (line ~52)

Add entries where confounding is plausible:

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

# Cadence confounded by pace (faster running = higher cadence naturally)
# Leave out for v1 — cadence and pace are co-determined, not confounded.

# Volume confounded by fitness
("weekly_volume_km", "efficiency"): "ctl",
("weekly_volume_km", "pace_easy"): "ctl",
```

---

## Phase 9: _VOICE_INTERNAL_METRICS Check

**File:** `apps/api/routers/home.py`

Verify that NONE of the new input keys are on the ban list. These are
all athlete-meaningful terms. The existing ban list covers internal
abbreviations (TSB, CTL, ATL, etc.) and should not need changes.

If any new key matches a ban-list pattern, rename the friendly name —
do NOT add it to the ban list.

---

## Signal Count Summary

| Phase | Category | New Signals |
|-------|----------|:-----------:|
| 1 | GarminDay wearable | 14 |
| 2 | Activity-level | 18 |
| 3 | Feedback & Reflection | 5 |
| 4 | Checkin + Composition + Nutrition | 6 |
| 5 | Training Patterns (derived) | 6 |
| | **Total new inputs** | **49** |

Combined with the existing 21 inputs, the engine will correlate
**70 input signals** against **9 output metrics**.

---

## Tests

### Unit Tests (all in `apps/api/tests/test_correlation_engine.py`)

**Phase 1 tests:**
1. `test_garmin_sleep_score_in_inputs` — GarminDay rows with sleep_score → `inputs["garmin_sleep_score"]` populated
2. `test_garmin_body_battery_in_inputs` — body_battery_end → `inputs["garmin_body_battery_end"]` populated
3. `test_garmin_stress_in_inputs` — avg_stress → `inputs["garmin_avg_stress"]` populated
4. `test_garmin_no_data_returns_empty` — no GarminDay rows → all garmin_* keys have empty lists
5. `test_garmin_null_fields_excluded` — rows with NULL fields → not in output

**Phase 2 tests:**
6. `test_activity_dew_point_input` — activities with dew_point_f → `inputs["dew_point_f"]` populated
7. `test_activity_cadence_input` — activities with avg_cadence → populated
8. `test_activity_multi_run_day_takes_longest` — two runs on same day → longest run's values used
9. `test_activity_run_start_hour` — activity at 6am → `inputs["run_start_hour"]` = [(date, 6.0)]
10. `test_activity_elevation_input` — total_elevation_gain → `inputs["elevation_gain_m"]` populated

**Phase 3 tests:**
11. `test_feedback_leg_feel_ordinal` — leg_feel="fresh" → 5, "sore" → 1
12. `test_reflection_ordinal` — "easier" → 1, "harder" → -1
13. `test_feedback_empty_when_no_data` — no ActivityFeedback → empty dict

**Phase 4 tests:**
14. `test_sleep_quality_in_inputs` — sleep_quality_1_5 populated
15. `test_body_fat_pct_in_inputs` — body_fat_pct populated
16. `test_daily_calories_in_inputs` — calories summed per day

**Phase 5 tests:**
17. `test_days_since_quality` — interval on Mon, easy Tue/Wed → Wed days_since_quality = 2
18. `test_consecutive_run_days` — runs Mon-Wed → Wed streak = 3
19. `test_weekly_volume_km` — known distances → correct 7-day sum
20. `test_long_run_ratio` — one 20km + four 5km in week → ratio = 0.5

**Integration tests:**
21. `test_all_inputs_count_at_least_70` — mock all sources → len(inputs) >= 70
22. `test_friendly_names_cover_all_inputs` — every key in inputs dict has a FRIENDLY_NAMES entry
23. `test_no_new_inputs_on_ban_list` — no new input key appears in _VOICE_INTERNAL_METRICS

---

## Build Order

The phases are independent and can be built in any order. Recommended
sequence for incremental value:

1. **Phase 1** (GarminDay) — biggest gap, most daily data points
2. **Phase 2** (Activity-level) — second biggest gap
3. **Phase 6** (FRIENDLY_NAMES) — must ship with Phases 1+2
4. **Phase 7** (DIRECTION_EXPECTATIONS) — ship with 1+2
5. **Phase 8** (CONFOUNDER_MAP) — ship with 1+2
6. **Phase 4** (missing checkin/composition) — quick wins
7. **Phase 3** (feedback/reflection) — depends on athlete usage
8. **Phase 5** (derived patterns) — most complex logic
9. **Phase 9** (ban list check) — final verification

Phases 1-2, 6-8, and 9 should ship together as one commit.
Phases 3-5 can follow in a second commit.

---

## What This Does NOT Do

- Does not change any frontend surface
- Does not change the output metrics (still 9)
- Does not change correlation math, persistence, or surfacing
- Does not add new database tables or migrations
- Does not require API changes
- Does not change the daily sweep schedule

Everything downstream works automatically. The engine discovers
correlations, persists them, and the existing surfaces (home page
findings, progress, coach) pick them up.

---

## Acceptance Criteria

1. `aggregate_daily_inputs()` returns >= 35 keys (21 existing + 14 GarminDay)
2. `aggregate_activity_level_inputs()` returns up to 18 keys per activity day
3. `aggregate_feedback_inputs()` returns up to 5 keys
4. `aggregate_training_pattern_inputs()` returns up to 6 keys
5. `analyze_correlations()` tests all new inputs against all output metrics
6. Every new input key has a `FRIENDLY_NAMES` entry
7. No new input key appears in `_VOICE_INTERNAL_METRICS` ban list
8. All 23 tests pass
9. Daily correlation sweep completes without error for founder account
10. CI green
