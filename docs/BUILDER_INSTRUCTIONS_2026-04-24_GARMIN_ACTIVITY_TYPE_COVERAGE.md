# Builder Instruction: Garmin Activity Type Coverage Fix

**Priority:** P0 — user-visible data loss in production
**Date:** 2026-04-24
**Scoped by:** Advisor session

## Problem

Dejan Kadunc's cycling activity ("Cerklje na Gorenjskem Road Cycling", 81.5 km,
Garmin Edge 530) was silently dropped because Garmin sent `activityType: "ROAD_BIKING"`,
which is not in `_ACTIVITY_TYPE_MAP`. The activity was skipped and logged only at
DEBUG level — invisible in production logs.

This is a systemic gap: the map only covers ~15 of Garmin's ~50+ known activity types.
Any athlete using a Garmin subtype we haven't mapped loses data silently.

## Root Cause

`apps/api/services/sync/garmin_adapter.py` line 46–71: `_ACTIVITY_TYPE_MAP` is incomplete.
`apps/api/tasks/garmin_webhook_tasks.py` line 501: unmapped sport logged at `logger.debug`.

## Scope — Three Changes

### 1. Expand `_ACTIVITY_TYPE_MAP` (garmin_adapter.py, lines 46–71)

Replace the current map with a comprehensive one. Group by internal sport:

```python
_ACTIVITY_TYPE_MAP: Dict[str, Optional[str]] = {
    # --- Run ---
    "RUNNING": "run",
    "TRAIL_RUNNING": "run",
    "TREADMILL_RUNNING": "run",
    "INDOOR_RUNNING": "run",
    "VIRTUAL_RUN": "run",
    "TRACK_RUNNING": "run",
    "STREET_RUNNING": "run",
    "ULTRA_RUN": "run",
    "OBSTACLE_RUN": "run",
    "SPEED_RUNNING": "run",

    # --- Cycling ---
    "CYCLING": "cycling",
    "INDOOR_CYCLING": "cycling",
    "MOUNTAIN_BIKING": "cycling",
    "ROAD_BIKING": "cycling",
    "GRAVEL_CYCLING": "cycling",
    "CYCLOCROSS": "cycling",
    "VIRTUAL_RIDE": "cycling",
    "E_BIKE_FITNESS": "cycling",
    "E_BIKE_MOUNTAIN": "cycling",
    "RECUMBENT_CYCLING": "cycling",
    "HAND_CYCLING": "cycling",
    "TRACK_CYCLING": "cycling",
    "BMX": "cycling",
    "BIKE_COMMUTING": "cycling",
    "DOWNHILL_BIKING": "cycling",
    "MIXED_SURFACE_CYCLING": "cycling",
    "SPIN": "cycling",

    # --- Walking ---
    "WALKING": "walking",
    "CASUAL_WALKING": "walking",
    "SPEED_WALKING": "walking",
    "INDOOR_WALKING": "walking",

    # --- Hiking ---
    "HIKING": "hiking",

    # --- Swimming ---
    "SWIMMING": "swimming",
    "LAP_SWIMMING": "swimming",
    "OPEN_WATER_SWIMMING": "swimming",
    "POOL_SWIMMING": "swimming",

    # --- Strength ---
    "STRENGTH_TRAINING": "strength",
    "WEIGHT_TRAINING": "strength",
    "FUNCTIONAL_TRAINING": "strength",

    # --- Flexibility / recovery ---
    "YOGA": "flexibility",
    "PILATES": "flexibility",
    "BREATHWORK": "flexibility",

    # --- Cardio / HIIT ---
    "HIIT": "cardio",
    "CARDIO_TRAINING": "cardio",
    "JUMP_ROPE_TRAINING": "cardio",

    # --- Elliptical / indoor cardio ---
    "ELLIPTICAL": "cycling",
    "STAIR_CLIMBING": "cycling",
    "INDOOR_ROWING": "rowing",
    "ROWING": "rowing",

    # --- Winter sports ---
    "RESORT_SKIING_SNOWBOARDING": "winter_sport",
    "CROSS_COUNTRY_SKIING": "winter_sport",
    "BACKCOUNTRY_SKIING": "winter_sport",
    "SNOWBOARDING": "winter_sport",
    "SNOWSHOEING": "winter_sport",
    "SKATING": "winter_sport",

    # --- Water sports ---
    "STAND_UP_PADDLEBOARDING": "water_sport",
    "SURFING": "water_sport",
    "KAYAKING": "water_sport",
    "SAILING": "water_sport",

    # --- Other fitness ---
    "MULTI_SPORT": "multi_sport",
    "MARTIAL_ARTS": "other",
    "BOXING": "other",
    "ROCK_CLIMBING": "other",
    "GOLF": "other",
    "HORSEBACK_RIDING": "other",
    "INLINE_SKATING": "other",
    "TENNIS": "other",
    "PICKLEBALL": "other",
    "RACQUET": "other",
    "FLOOR_CLIMBING": "other",
    "MEDITATION": "other",
    "DISC_GOLF": "other",
    "DANCE": "other",
}
```

### 2. Update `_ACCEPTED_SPORTS` (garmin_adapter.py, line 73)

Add the new sport categories so they pass the ingestion filter:

```python
_ACCEPTED_SPORTS = {
    "run", "cycling", "walking", "hiking", "swimming",
    "strength", "flexibility", "cardio", "rowing",
    "winter_sport", "water_sport", "multi_sport", "other",
}
```

### 3. Update `_CADENCE_UNIT_MAP` (garmin_adapter.py, lines 75–82)

Add entries for new sport categories:

```python
_CADENCE_UNIT_MAP: Dict[str, Optional[str]] = {
    "run": "spm",
    "walking": "spm",
    "hiking": "spm",
    "cycling": "rpm",
    "swimming": None,
    "strength": None,
    "flexibility": None,
    "cardio": None,
    "rowing": "spm",
    "winter_sport": None,
    "water_sport": None,
    "multi_sport": None,
    "other": None,
}
```

### 4. Upgrade unmapped sport log level (garmin_webhook_tasks.py, line 501)

Change from `logger.debug` to `logger.warning` so unmapped types appear in
production logs and we catch future gaps immediately:

```python
    if adapted.get("sport") not in _ACCEPTED_SPORTS:
        logger.warning(
            "Skipping unmapped activity (sport=%s, type=%s, external_id=%s)",
            adapted.get("sport"),
            adapted.get("garmin_activity_type"),
            adapted.get("external_activity_id"),
        )
        return "skipped"
```

### 5. Update tests (test_garmin_d3_adapter.py)

**a)** Expand `test_cycling_maps_to_cycling` to cover `ROAD_BIKING`:

```python
    def test_cycling_maps_to_cycling(self):
        for garmin_type in ("CYCLING", "ROAD_BIKING", "GRAVEL_CYCLING"):
            out = adapt_activity_summary(self._sample_raw(activityType=garmin_type))
            assert out["sport"] == "cycling", f"Expected 'cycling' for {garmin_type}"
            assert out["cadence_unit"] == "rpm"
```

**b)** Expand `test_cross_training_types` to cover representative new types:

Add these cases to the `cases` dict:
```python
    "ROAD_BIKING": ("cycling", "rpm"),
    "GRAVEL_CYCLING": ("cycling", "rpm"),
    "VIRTUAL_RIDE": ("cycling", "rpm"),
    "E_BIKE_FITNESS": ("cycling", "rpm"),
    "TRACK_CYCLING": ("cycling", "rpm"),
    "BIKE_COMMUTING": ("cycling", "rpm"),
    "CASUAL_WALKING": ("walking", "spm"),
    "SPEED_WALKING": ("walking", "spm"),
    "INDOOR_WALKING": ("walking", "spm"),
    "SWIMMING": ("swimming", None),
    "LAP_SWIMMING": ("swimming", None),
    "OPEN_WATER_SWIMMING": ("swimming", None),
    "WEIGHT_TRAINING": ("strength", None),
    "BREATHWORK": ("flexibility", None),
    "HIIT": ("cardio", None),
    "INDOOR_ROWING": ("rowing", "spm"),
    "CROSS_COUNTRY_SKIING": ("winter_sport", None),
    "STAND_UP_PADDLEBOARDING": ("water_sport", None),
    "MULTI_SPORT": ("multi_sport", None),
    "GOLF": ("other", None),
```

**c)** Update `test_unknown_type_maps_to_none` — GOLF is now mapped. Use a truly
unknown type like `"ZORBING"` instead.

### 6. Replay Dejan's dropped cycling activity

After deploying the fix, run this one-off recovery on the production server:

```bash
ssh root@187.124.67.153

# Write recovery script
cat > /tmp/replay_dejan.py << 'PYEOF'
import sys, json
sys.path.insert(0, '/app')

from database import SessionLocal
from core.redis_client import get_redis_client
from tasks.garmin_webhook_tasks import process_garmin_activity_task

ATHLETE_ID = "6764d1a0-e246-4f8b-85f3-be80d1e7157e"
GARMIN_ACTIVITY_ID = 22644444515
REDIS_KEY = f"garmin_detail_pending:{ATHLETE_ID}:{GARMIN_ACTIVITY_ID}"

r = get_redis_client()
raw_values = r.lrange(REDIS_KEY, 0, 0)
if not raw_values:
    print("ERROR: No deferred detail payload found in Redis")
    sys.exit(1)

detail_payload = json.loads(raw_values[0])
summary = detail_payload.get("summary", {})
if not summary:
    print("ERROR: No summary in deferred detail")
    sys.exit(1)

# Build a minimal activity summary payload from the detail's summary
activity_payload = {
    "summaryId": str(summary["activityId"]),
    "activityId": summary["activityId"],
    "activityType": summary.get("activityType", "ROAD_BIKING"),
    "activityName": summary.get("activityName", ""),
    "startTimeInSeconds": summary.get("startTimeInSeconds"),
    "startTimeOffsetInSeconds": summary.get("startTimeOffsetInSeconds", 0),
    "durationInSeconds": summary.get("durationInSeconds"),
    "distanceInMeters": summary.get("distanceInMeters"),
    "averageHeartRateInBeatsPerMinute": summary.get("averageHeartRateInBeatsPerMinute"),
    "maxHeartRateInBeatsPerMinute": summary.get("maxHeartRateInBeatsPerMinute"),
    "averageSpeedInMetersPerSecond": summary.get("averageSpeedInMetersPerSecond"),
    "maxSpeedInMetersPerSecond": summary.get("maxSpeedInMetersPerSecond"),
    "totalElevationGainInMeters": summary.get("totalElevationGainInMeters"),
    "totalElevationLossInMeters": summary.get("totalElevationLossInMeters"),
    "startingLatitudeInDegree": summary.get("startingLatitudeInDegree"),
    "startingLongitudeInDegree": summary.get("startingLongitudeInDegree"),
    "activeKilocalories": summary.get("activeKilocalories"),
    "deviceName": summary.get("deviceName"),
    "averageBikeCadenceInRoundsPerMinute": summary.get("averageBikeCadenceInRoundsPerMinute"),
    "maxBikeCadenceInRoundsPerMinute": summary.get("maxBikeCadenceInRoundsPerMinute"),
}

print(f"Replaying activity: {activity_payload['activityName']}")
print(f"  Type: {activity_payload['activityType']}")
print(f"  Distance: {activity_payload['distanceInMeters']}m")
print(f"  Duration: {activity_payload['durationInSeconds']}s")

result = process_garmin_activity_task(ATHLETE_ID, activity_payload)
print(f"Result: {result}")
PYEOF

docker exec -w /app strideiq_api python /tmp/replay_dejan.py
```

Verify after replay:
```sql
SELECT id, sport, name, distance_m, start_time
FROM activity
WHERE athlete_id = '6764d1a0-e246-4f8b-85f3-be80d1e7157e'::uuid
  AND sport = 'cycling'
ORDER BY start_time DESC LIMIT 3;
```

## Out of Scope

- Frontend display changes for new sport categories (swimming, rowing, etc.)
  are cosmetic — activities will appear with the sport label but no
  sport-specific detail views. That's acceptable for now.
- Garmin DI Connect importer (`services/provider_import/garmin_di_connect.py`)
  uses its own mapping — audit separately.

## Verification

1. `pytest apps/api/tests/test_garmin_d3_adapter.py -v` — all pass
2. `pytest apps/api/tests/test_garmin_d5_activity_sync.py -v` — all pass
3. Full CI green
4. Deploy, then replay Dejan's activity
5. Verify activity appears at https://strideiq.run for Dejan
