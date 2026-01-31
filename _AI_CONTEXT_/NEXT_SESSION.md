# Next Session Instructions

**Last Updated:** 2026-01-31
**Previous Session:** Workout Classification & Data Sync Fixes

---

## Session Summary

This session fixed critical trust-breaking issues with workout classification:

1. **Workout Classification Overhaul** — HR as primary signal, athlete-relative thresholds
2. **Data Sync Fixes** — avg_hr and temperature now properly backfilled from Strava
3. **Confidence Threshold** — Low-confidence classifications show generic "Run" instead of guessing

---

## Current State

### Branch
`phase8-s2-hardening`

### Docker Status
Running. Production deployed. All containers healthy.

### All Tests Passing
- 1274 passed, 2 skipped
- Classification tests: 45 passed

---

## Fixes Implemented This Session

### 1. Athlete-Relative Thresholds
`apps/api/services/run_analysis_engine.py`:
- Added `_get_athlete_run_thresholds()` — calculates from athlete's 90-day history
- Long run = 90th percentile duration (top 10% of runs)
- No more hardcoded "60 min = long run" nonsense

### 2. HR as Primary Classification Signal
- Reordered classification: HR checked FIRST when available
- Duration only used to upgrade easy-effort runs to "Long Run"
- Fallback to duration-only when no HR data

### 3. Confidence Display Threshold
- `MIN_DISPLAY_CONFIDENCE = 0.65`
- Below threshold → shows "Run" instead of specific type
- Frontend updated in `RunContextAnalysis.tsx`

### 4. avg_hr Backfill
`apps/api/tasks/strava_tasks.py`:
- Strava list endpoint often omits `average_heartrate`
- Now backfills from detailed activity response

### 5. Temperature Sync
- Added temperature capture from Strava (`average_temp` → Fahrenheit)
- Frontend displays in °F
- Note: This is device sensor temp, not ambient weather

---

## Commits (This Session)
- `6924e1c` - fix(classification): use athlete-relative thresholds
- `5f1064b` - fix(classification): HR data is primary signal
- `d362bd3` - fix(strava): backfill avg_hr from activity details
- `441c542` - feat(strava): sync temperature, display as °F
- `86df231` - fix(types): add temperature_f to Activity interface

---

## Known Limitations

### Temperature
- Shows device sensor reading (Garmin), not ambient weather
- Strava API doesn't expose weather data
- Will revisit when Garmin Business Development partnership approved

### Classification
- Requires athlete's max_hr to be set for HR-based classification
- Michael's profile has max_hr=180, threshold_hr=165, resting_hr=50

---

## Pending Integrations

### Garmin API
- Applied to Garmin Business Development Program
- Awaiting approval
- May provide better weather data

### COROS API
- Application prepared: `docs/COROS_API_APPLICATION.md`
- Form responses: `docs/COROS_APPLICATION_FORM_RESPONSES.md`

---

## Key Files

| File | Purpose |
|------|---------|
| `apps/api/services/run_analysis_engine.py` | Run classification logic |
| `apps/api/services/workout_classifier.py` | Detailed workout classification |
| `apps/api/tasks/strava_tasks.py` | Strava sync with backfill logic |
| `_AI_CONTEXT_/SESSION_SUMMARY_2026_01_31_CLASSIFICATION_FIX.md` | This session's details |

---

## Commands to Resume

```bash
# Local test
docker compose -f docker-compose.test.yml run --rm api_test pytest tests/ -v

# Deploy to production
ssh root@strideiq.run
cd /opt/strideiq/repo && git pull origin phase8-s2-hardening && docker compose -f docker-compose.prod.yml up -d --build
```

---

## User Preferences

- **Full rigor** on all features
- **Test before deploy** — no blind deployments
- **Ask before making changes** — get approval first
- **Temperature in °F** for US users
- **Garmin/COROS integrations** — waiting on business partnerships

---

*Session ended: 2026-01-31*
