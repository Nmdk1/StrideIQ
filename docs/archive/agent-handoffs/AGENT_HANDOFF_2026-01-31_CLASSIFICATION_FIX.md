# Agent Handoff: 2026-01-31 Classification & Data Sync Fixes

## Session Context
User (Michael) reported that an 8-mile regular training run was classified as "Long Run" at 50% confidence. This was identified as trust-breaking behavior.

## What Was Done

### 1. Workout Classification Overhaul
**Problem:** Hardcoded 60-minute threshold classified any run over an hour as "Long Run"
**Fix:** 
- Added athlete-relative thresholds based on 90-day training history
- Long run = 90th percentile duration (top 10% of athlete's runs)
- HR data is now PRIMARY classification signal (not duration)

### 2. Confidence Display Threshold
**Problem:** 50% confidence displayed as specific workout type (coin flip = trust killer)
**Fix:**
- Added `MIN_DISPLAY_CONFIDENCE = 0.65`
- Below threshold → shows generic "Run" badge
- Only displays specific type when confident

### 3. avg_hr Backfill
**Problem:** Strava's list endpoint often omits `average_heartrate`
**Fix:**
- Now backfills from detailed activity response
- Both new activities and existing activities get backfill

### 4. Temperature Sync
**Problem:** Temperature wasn't being synced from Strava
**Fix:**
- Added temperature capture (converts Strava's Celsius to Fahrenheit)
- Frontend displays in °F

## Files Modified
1. `apps/api/services/run_analysis_engine.py` - Classification logic
2. `apps/api/tasks/strava_tasks.py` - Data sync with backfill
3. `apps/web/components/activities/RunContextAnalysis.tsx` - Display logic
4. `apps/web/app/activities/[id]/page.tsx` - Temperature display

## Branch
`phase8-s2-hardening`

## Deployment Status
Production deployed and verified working.

## Known Issues
- Temperature shows device sensor reading (Garmin), not ambient weather
- Strava API doesn't expose weather data
- Will revisit when Garmin partnership approved

## Athlete Profile (Michael)
- max_hr: 180
- resting_hr: 50
- threshold_hr: 165
- Long runs: 2+ hours
- Medium-long: 1:40-2:00

## Next Steps
1. Wait for Garmin Business Development approval
2. Wait for COROS API approval
3. Revisit weather data when integrations available

## Tests
All 1274 tests passing.
