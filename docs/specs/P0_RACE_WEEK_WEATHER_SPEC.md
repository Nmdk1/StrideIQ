# P0: Race-Week Weather — Build Spec (Revised)

**Date:** March 9, 2026  
**Priority:** P0 — ship before Saturday March 15  
**Roadmap reference:** `docs/BUILD_ROADMAP_2026-03-09.md` Priority 0  
**Estimated effort:** 1 day

---

## What This Delivers

When race is within 7 days and a forecast is set, morning voice and race assessment use:

1. Forecast conditions (temp/humidity/dew point),
2. Athlete's heat resilience finding (if present),
3. Historical runs in similar conditions,
4. Personalized heat adjustment estimate.

No external forecast API, no migration, no frontend widget in this phase.

---

## Bug Fix (must ship with feature)

Current mismatch in `apps/api/routers/home.py`:
- `race_data_dict` sets `race_name`, `days_remaining`, `goal_time`
- prompt summary reads `name`, `date`, `distance`

This causes generic blind race assessment text.

### Fix

Use consistent keys and add required fields:

```python
race_data_dict = None
if race_countdown:
    race_data_dict = {
        "name": race_countdown.race_name,
        "date": race_countdown.race_date,
        "days_remaining": race_countdown.days_remaining,
        "distance": _format_race_distance(plan),
        "goal_time": race_countdown.goal_time,
        "goal_pace": race_countdown.goal_pace,
        "predicted_time": race_countdown.predicted_time,
    }
```

Distance helper:

```python
def _format_race_distance(plan) -> str:
    dist_m = getattr(plan, "goal_race_distance_m", None)
    if not dist_m:
        return "unknown distance"
    miles = dist_m / 1609.344
    if abs(miles - 26.2) < 0.5:
        return "marathon"
    if abs(miles - 13.1) < 0.3:
        return "half marathon"
    if abs(miles - 6.2) < 0.2:
        return "10K"
    if abs(miles - 3.1) < 0.2:
        return "5K"
    return f"{miles:.1f} miles"
```

---

## Race-Week Weather Feature

### Architecture

Redis-backed manual forecast (admin-set) + prompt injection on Home briefing path.

**Data flow**
```
Admin POST forecast -> Redis key race_forecast:{athlete_id}
                         |
Home briefing (race <=7d) -> load forecast
                         -> compute generic heat adjustment
                         -> apply personal multiplier from heat finding
                         -> fetch similar-condition runs
                         -> inject "RACE WEEK WEATHER" context block
```

### Implementation

#### 1) Admin endpoint (validated body, auditable)

**File:** `apps/api/routers/admin.py`

- Add request model:
  - `athlete_id: UUID`
  - `temp_f: float` (bounds: `-20` to `120`)
  - `humidity_pct: float` (bounds: `0` to `100`)
  - `description: Optional[str]` (max length 240)
- Use `core.cache.get_redis_client()` (do not instantiate Redis client directly).
- Store JSON under `race_forecast:{athlete_id}` with TTL 14 days.
- Return deterministic payload.
- Write admin audit event if existing pattern available; if unavailable, log structured event.

#### 2) Forecast retrieval helper

**File:** `apps/api/routers/home.py`

Add:

```python
def _get_race_forecast(athlete_id: str) -> Optional[dict]:
    from core.cache import get_redis_client
    import json
    client = get_redis_client()
    if not client:
        return None
    raw = client.get(f"race_forecast:{athlete_id}")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None
```

#### 3) Personal heat adjustment logic (real personalization)

**File:** `apps/api/routers/home.py`

Add helper to derive a personal multiplier from `AthleteFinding(finding_type='heat_resilience')` receipts:

- Read `classification` and optional `resilience_ratio`.
- Compute `personal_multiplier` with safe bounds `[0.70, 1.30]`.
- Priority:
  1. if valid `resilience_ratio` present -> use bounded ratio-derived multiplier,
  2. else classification map:
     - resilient -> `0.85`
     - average -> `1.00`
     - sensitive -> `1.15`

Then:

```python
generic_adj_pct = calculate_heat_adjustment_pct(temp_f, dew_point_f)
personal_adj_pct = generic_adj_pct * personal_multiplier
personal_adj_pct = max(0.0, min(personal_adj_pct, 0.15))
```

#### 4) Weather context builder (strict filters + UUID-safe queries)

**File:** `apps/api/routers/home.py`

`_build_race_weather_context(...)` requirements:

- Convert `athlete_id` to UUID for DB filters.
- Query `AthleteFinding` with UUID athlete id and `is_active=True`.
- Similar-runs query must filter:
  - `Activity.athlete_id == athlete_uuid`
  - `Activity.sport.ilike("run")`
  - `Activity.is_duplicate == False`
  - temp/dew point present and within tolerance window
  - `Activity.distance_m >= 5000`
- Summarize similar-run count and average `heat_adjustment_pct` if available.
- Include clear instruction to LLM:
  - coaching language only,
  - no raw internal metrics (`resilience_ratio`, `*_pct`, etc.).

#### 5) Inject context only in race week

In `generate_coach_home_briefing`:

```python
if race_data and race_data.get("days_remaining", 99) <= 7:
    forecast = _get_race_forecast(athlete_id)
    if forecast:
        weather_section = _build_race_weather_context(athlete_id, db, forecast, race_data)
        if weather_section:
            parts.extend([weather_section, ""])
```

#### 6) Enrich race summary string

Ensure `race_summary` includes:
- `name`, `date`, `distance`, `days_remaining`
- optional `goal_time`, `goal_pace`

---

## Acceptance Criteria

1. `race_assessment` receives real race fields (no `"Race: ? on ?, distance: ?"` placeholder path).
2. Admin can set forecast via validated endpoint; forecast stored in Redis via cache client.
3. Weather context is injected only when race is within 7 days and forecast exists.
4. Personalized adjustment is used (`personal_adj_pct`), not only generic formula.
5. No internal numeric jargon is surfaced to athlete output.
6. If no forecast exists, behavior remains unchanged.
7. If forecast payload malformed or Redis unavailable, path fails gracefully (no crash).

---

## Test Plan

### Unit tests (`apps/api/tests/test_race_week_weather.py`)

1. `test_race_data_dict_keys_match_prompt`
2. `test_format_race_distance_marathon`
3. `test_format_race_distance_half`
4. `test_format_race_distance_custom`
5. `test_get_race_forecast_returns_none_when_empty`
6. `test_get_race_forecast_returns_none_on_malformed_json`
7. `test_personal_multiplier_from_resilience_ratio_bounded`
8. `test_personal_multiplier_from_classification_defaults`
9. `test_build_race_weather_context_includes_forecast`
10. `test_build_race_weather_context_filters_to_real_runs_non_duplicates`
11. `test_race_weather_only_injected_within_7_days`
12. `test_race_weather_injected_at_7_days`
13. `test_admin_forecast_validation_bounds_reject_invalid_values`

### Integration tests

14. `test_home_endpoint_race_assessment_has_real_race_fields_when_plan_exists`
15. `test_home_endpoint_graceful_when_forecast_absent_or_cache_unavailable`

---

## Deployment Steps

1. Fix race key mismatch (`race_data_dict` + `race_summary`).
2. Add validated admin forecast endpoint.
3. Add forecast retrieval + personal weather context helpers.
4. Add race-week conditional injection.
5. Add tests.
6. Run tests and CI.
7. Deploy.
8. Set founder race forecast in production.
9. Verify next briefing reflects race-week weather in coaching language.

---

## Out of Scope (Horizon 2)

- Forecast provider integration (OpenWeather, etc.)
- Auto refresh/scheduling of forecast
- Forecast UI card/widget
- Multi-race forecast support
- Persistent weather forecast storage in DB
