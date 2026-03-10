# Builder Instructions — Add Heat/Weather as Correlation Engine Input

**Date:** March 10, 2026
**Priority:** P1 — ship this week
**Estimated effort:** 1-2 hours
**Principle:** The engine should learn how each athlete adapts to heat, not just apply population averages.

---

## What

Add `dew_point_f` and `heat_adjustment_pct` as input signals to the correlation engine. Same pattern as sleep, HRV, soreness, and every other input. The daily correlation sweep will then discover each athlete's personal relationship with heat — their adaptation curve, their vulnerability threshold, how heat interacts with sleep, recovery, and training load.

## Why

Heat data exists on every activity (`Activity.dew_point_f`, `Activity.heat_adjustment_pct`). `investigate_heat_tax` does a standalone hot-vs-cool comparison. But the correlation engine — the system that discovers personalized, reproducible findings — has no idea weather exists. It cannot discover "your efficiency drops 12% above dew point 62°F" or "you adapt after 3 consecutive heat days" because dew point is not in its input dictionary.

## Where

**File:** `apps/api/services/correlation_engine.py`

**Function:** `aggregate_checkin_inputs` (starts around line 240) — this is where all input signals are collected into the `inputs` dictionary.

**Add after the last existing input block (around line 479, after `hrv_sdnn`):**

```python
# --- Weather / Heat inputs (from Activity) ---

# Daily average dew point (primary heat stress indicator)
from models import Activity as _Activity
dew_point_data = db.query(
    func.date(_Activity.start_time).label('day'),
    func.avg(_Activity.dew_point_f).label('avg_dew_point')
).filter(
    _Activity.athlete_id == athlete_id,
    _Activity.start_time >= start_date,
    _Activity.start_time <= end_date,
    _Activity.dew_point_f.isnot(None),
).group_by(func.date(_Activity.start_time)).all()

inputs["dew_point_f"] = [(row.day, float(row.avg_dew_point)) for row in dew_point_data]

# Daily average heat adjustment percentage
heat_adj_data = db.query(
    func.date(_Activity.start_time).label('day'),
    func.avg(_Activity.heat_adjustment_pct).label('avg_heat_adj')
).filter(
    _Activity.athlete_id == athlete_id,
    _Activity.start_time >= start_date,
    _Activity.start_time <= end_date,
    _Activity.heat_adjustment_pct.isnot(None),
    _Activity.heat_adjustment_pct > 0,
).group_by(func.date(_Activity.start_time)).all()

inputs["heat_adjustment_pct"] = [(row.day, float(row.avg_heat_adj)) for row in heat_adj_data]
```

## Additional Wiring

### 1. Add to FRIENDLY_NAMES

**File:** `apps/api/services/n1_insight_generator.py`, `FRIENDLY_NAMES` dict:

```python
"dew_point_f": "dew point",
"heat_adjustment_pct": "heat impact",
```

### 2. Add to DIRECTION_EXPECTATIONS (if applicable)

**File:** `apps/api/services/correlation_engine.py`, `DIRECTION_EXPECTATIONS` dict.

Check if this dict exists and whether heat inputs need expected direction entries. For most athletes:
- `dew_point_f` vs `efficiency` → expected direction: `"negative"` (higher dew point = lower efficiency)
- `heat_adjustment_pct` vs `pace_easy` → expected direction: `"positive"` (higher adjustment = slower pace, which is positive in sec/mi)

If the dict doesn't cover these, add them. If you're unsure about direction, leave them out — the engine will discover the direction empirically and flag counterintuitive results.

### 3. Add to CONFOUNDER_MAP (if applicable)

**File:** `apps/api/services/correlation_engine.py`, `CONFOUNDER_MAP` dict.

Heat is a potential confounder for efficiency findings. Consider:
- `("dew_point_f", "efficiency")` → confounder: `"atl"` (fatigue could explain both)
- Or leave it out for v1 and let the engine discover uncontrolled correlations first

### 4. Verify _VOICE_INTERNAL_METRICS

**File:** `apps/api/routers/home.py`, `_VOICE_INTERNAL_METRICS` list.

`dew_point_f` and `heat_adjustment_pct` should NOT be on the ban list — they are athlete-meaningful terms (unlike TSB/CTL/ATL). The friendly names "dew point" and "heat impact" are fine for athlete-facing surfaces.

## Tests

1. `test_dew_point_in_correlation_inputs` — mock activities with `dew_point_f` values → `inputs["dew_point_f"]` populated
2. `test_heat_adjustment_in_correlation_inputs` — mock activities with `heat_adjustment_pct > 0` → `inputs["heat_adjustment_pct"]` populated
3. `test_no_heat_inputs_when_no_weather_data` — activities without weather data → both inputs empty lists
4. `test_dew_point_aggregated_per_day` — two activities on same day → averaged
5. `test_friendly_names_includes_heat` — `FRIENDLY_NAMES["dew_point_f"]` returns "dew point"

## What This Enables

Once wired, the daily correlation sweep automatically discovers:
- "Your efficiency drops X% above dew point Y°F" — personal heat threshold
- "Heat impact correlates with next-day soreness" — recovery cost of heat
- "Your pace degrades Z% per degree of dew point above your threshold" — personal heat curve
- Heat × sleep cascades: "Heat + poor sleep compounds the efficiency drop"
- Adaptation over time: findings strengthen or weaken as the athlete acclimates through summer

All of this happens with zero additional code beyond the input wiring. The engine, persistence, surfacing, and finding cooldown infrastructure handles the rest.

## What This Does NOT Do

- Does not change the chart or any frontend surface
- Does not replace `investigate_heat_tax` (that remains a standalone investigation for race analysis)
- Does not add per-point heat data to streams
- Does not require weather API integration (uses data already stored on activities from Garmin/Strava weather)
