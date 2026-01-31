# Session Summary: 2026-01-31 - Workout Classification & Data Sync Fixes

## Problem Statement
User reported that an 8-mile regular training run was incorrectly classified as "Long Run" with 50% confidence. This was identified as a trust-breaking issue for the platform.

## Root Cause Analysis

### Issue 1: Naive Duration Thresholds
The `run_analysis_engine.py` used hardcoded thresholds:
- 60+ minutes → "Long Run" at 0.5 confidence
- This is absurd for experienced runners (user's long runs start at 2+ hours)

### Issue 2: Wrong Classification Order
Duration checks happened BEFORE HR-based classification, causing:
- Runs above medium-long duration threshold returned early
- HR data was never evaluated even when available

### Issue 3: Missing avg_hr Data
Strava's list endpoint often omits `average_heartrate`:
- Activities were created with null avg_hr
- HR-based classification couldn't work without this data

### Issue 4: Missing Temperature Data
- Temperature wasn't being synced from Strava
- Frontend displayed hardcoded `°C` instead of user's preferred units

## Fixes Implemented

### 1. Athlete-Relative Thresholds (`run_analysis_engine.py`)
```python
def _get_athlete_run_thresholds(self, athlete_id: UUID) -> Dict:
    # Calculates from athlete's last 90 days:
    # - long_run_duration_min: 90th percentile (top 10% = long runs)
    # - medium_long_duration_min: 75th percentile
    # - typical_duration_min: median
```

### 2. HR as Primary Signal
Reordered classification logic:
1. Race detection (explicit flag)
2. **HR-based classification (PRIMARY)** - uses athlete's max_hr
3. Duration only upgrades to "Long Run" if effort is easy AND duration is in top 10%
4. Duration-based fallback only when no HR data

### 3. Confidence Threshold
```python
MIN_DISPLAY_CONFIDENCE = 0.65
```
- Below 65% confidence → shows generic "Run" instead of guessing wrong
- Frontend updated to display gray "Run" badge when uncertain

### 4. avg_hr Backfill (`strava_tasks.py`)
```python
# After fetching activity details
if activity.avg_hr is None and details.get("average_heartrate"):
    activity.avg_hr = _coerce_int(details.get("average_heartrate"))
```

### 5. Temperature Sync (`strava_tasks.py`)
```python
# Convert Celsius to Fahrenheit
if a.get("average_temp") is not None:
    temp_f = round(a.get("average_temp") * 9 / 5 + 32, 1)
```
- Added to both new activity creation and existing activity backfill
- Frontend displays `°F` for US users

### 6. Type Definition Fix
Added `temperature_f: number | null` to Activity interface in `page.tsx`

## Files Modified
1. `apps/api/services/run_analysis_engine.py` - Classification logic overhaul
2. `apps/api/tasks/strava_tasks.py` - avg_hr and temperature backfill
3. `apps/web/components/activities/RunContextAnalysis.tsx` - Confidence threshold display
4. `apps/web/app/activities/[id]/page.tsx` - Temperature display and type

## Commits
- `6924e1c` - fix(classification): use athlete-relative thresholds for workout type detection
- `5f1064b` - fix(classification): HR data is primary signal
- `d362bd3` - fix(strava): backfill avg_hr from activity details
- `441c542` - feat(strava): sync temperature from Strava, display as Fahrenheit
- `86df231` - fix(types): add temperature_f to Activity interface

## Result
- 8-mile run now correctly shows "Moderate" (75% confidence based on HR)
- avg_hr: 142 bpm (was missing, now populated)
- Temperature: 68°F (device reading - Garmin sensor)

## Known Limitations
- Temperature shows device sensor reading, not ambient weather
- Strava API doesn't expose weather data shown in their UI
- Will revisit when Garmin Business Development partnership is approved

## Testing
- All 1274 tests pass
- Manual verification on production confirmed fixes working
