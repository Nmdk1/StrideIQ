# Unified Reports

## Current State

Cross-domain reporting page at `/reports`. Combines health (Garmin wellness), activities, nutrition, and body composition into a single day-indexed view for any date range. Designed for athletes, coaches, dieticians, exercise physiologists, and primary care physicians. Deployed April 10, 2026.

## What It Does

A configurable report that shows everything about an athlete's health, training, and nutrition in one place. You pick the date range, toggle which data categories you want, and get a scannable daily log with drill-down detail.

## Architecture

### Backend

Single endpoint returns all data in one call:

| Endpoint | Purpose |
|----------|---------|
| `GET /v1/reports` | Unified report. Params: `start_date`, `end_date`, `categories` (comma-separated). |
| `GET /v1/reports/export/csv` | Same filters, CSV download. Imperial units (miles, lbs, °F, min/mi). |
| `GET /v1/reports/available-metrics` | Returns curated + extended metric lists. |

Router: `routers/reports.py`. Queries `GarminDay`, `Activity`, `NutritionEntry`, `BodyComposition` in a single pass, indexes by date, computes period averages.

### Data Sources

| Category | Source Table | What's Exposed |
|----------|-------------|---------------|
| Health | `GarminDay` | Sleep (score, duration, stages), HRV (overnight avg, 5min high), resting HR, min/max HR, stress, steps, active cal, VO2max, intensity minutes |
| Activities | `Activity` | Name, sport, workout type, duration, distance, pace, HR, elevation, cadence, stride, GCT, power, age-graded %, weather, shape sentence |
| Nutrition | `NutritionEntry` | Per-entry macros + daily totals (cal, protein, carbs, fat, fiber, caffeine, fluid) |
| Body Comp | `BodyComposition` | Weight, body fat %, muscle mass, BMI |

### Metric Tiers

**Health curated** (default on): sleep_score, sleep_total_s, hrv_overnight_avg, resting_hr, avg_stress, steps, active_kcal

**Health extended** (user-toggleable): sleep stages (deep/light/REM/awake), hrv_5min_high, min/max HR, max_stress, VO2max, active_time_s, intensity minutes

### Frontend

Page: `apps/web/app/reports/page.tsx`

Features:
- Date range presets: 7d, 14d, 30d, 90d, custom
- Category toggles: Health, Activities, Nutrition, Body Comp (minimum one)
- Health metric picker: curated defaults + selectable extended metrics
- Period averages card (computed across selected range)
- Trend sparklines: sleep score, HRV, resting HR, steps, calories, weight
- Day-by-day log (reverse chronological) with compact summary line per day
- Tap-to-expand daily detail: full health metrics grid, activity cards, nutrition entries, body comp
- CSV export button

Navigation: accessible from bottom nav More menu.

Service: `lib/api/services/reports.ts`
Hook: `lib/hooks/queries/reports.ts` → `useReport()`

## Key Decisions

- **GarminDay exposed to frontend for the first time.** Previously health data was only consumed server-side (home, progress, correlations). Reports surface it directly.
- **Curated + extended metric pattern.** Defaults show what matters; athletes can toggle on niche metrics (VO2max, intensity minutes, etc.).
- **One API call.** The backend assembles all four data categories in a single query pass rather than requiring 4 separate frontend calls.
- **CSV uses imperial units.** Miles, lbs, °F, min/mi pace — matches the primary athlete base.

## Sources

- `apps/api/routers/reports.py`
- `apps/web/app/reports/page.tsx`
- `apps/web/lib/api/services/reports.ts`
- `apps/web/lib/hooks/queries/reports.ts`
