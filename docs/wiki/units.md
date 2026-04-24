# Units System

## Current State

Every number on every screen, in every export, in every sentence the product speaks — distance, pace, elevation — matches the athlete's chosen unit preference. The canonical units migration (Apr 2026) eliminated all hardcoded imperial fields from the API and moved unit conversion to the rendering layer.

## How It Works

### Canonical API Contract

All API endpoints return values in canonical SI-adjacent units:

| Metric | Canonical Unit | API Field Pattern |
|--------|---------------|-------------------|
| Distance | meters (int) | `distance_m`, `total_distance_m`, `completed_m`, `planned_m` |
| Pace | seconds per km (float) | `pace_s_per_km`, `avg_pace_s_per_km` |
| Duration | seconds (int) | `duration_s`, `total_duration_s` |
| Elevation | meters (float) | `elevation`, `total_ascent`, `total_descent_m` |

The API never ships miles, feet, or min/mi. Conversion to athlete-preferred units happens at the render boundary only.

### Athlete Preference

Source of truth: `Athlete.preferred_units` (values: `"metric"` or `"imperial"`).

**Country-aware defaults:** When a new athlete signs up, `derive_default_units()` in `services/timezone_utils.py` infers their country from IANA timezone:
- US → `imperial` (miles, ft, °F, min/mi)
- Everywhere else → `metric` (km, m, °C, min/km)

**Explicit override:** Athletes can change their preference in settings. When they do, `athlete.preferred_units_set_explicitly = True` is set, and the country-aware default no longer applies. The coach can also detect a unit preference expressed in chat via `_maybe_update_units_preference` in `services/coaching/_guardrails.py`.

### Frontend: `useUnits()` Hook

`apps/web/lib/context/UnitsContext.tsx` provides the `useUnits()` React hook:

```typescript
const {
  formatDistance,   // (meters) => "5.2 mi" or "8.4 km"
  formatPace,       // (secondsPerKm) => "7:42/mi" or "4:47/km"
  formatElevation,  // (meters) => "330 ft" or "101 m"
  convertDistance,   // (meters) => miles or km (raw number)
  convertPace,       // (secondsPerKm) => secondsPerMi or secondsPerKm
  convertElevation,  // (meters) => feet or meters
  distanceUnit,      // "miles" or "kilometers"
  distanceUnitShort, // "mi" or "km"
  paceUnit,          // "min/mi" or "min/km"
  elevationUnit,     // "ft" or "m"
} = useUnits();
```

Every page and component that displays distance, pace, or elevation must use this hook. There are no exceptions.

### Backend: `CoachUnits` Helper

`apps/api/services/coach_units.py` provides unit-aware formatters for LLM prompts and deterministic text:

| Method | Input | Output |
|--------|-------|--------|
| `format_distance(meters)` | `20921` | `"13.0 mi"` or `"20.9 km"` |
| `format_pace_from_distance_duration(meters, seconds)` | `20921, 5400` | `"6:54/mi"` or `"4:17/km"` |
| `format_elevation(meters)` | `330` | `"+1083 ft"` or `"+330 m"` |
| `format_temperature_from_f(fahrenheit)` | `72.0` | `"72.0°F"` or `"22.2°C"` |

The briefing pipeline (`tasks/home_briefing_tasks.py`) and home router (`routers/home.py`) pass unit-aware text fields (`distance_text`, `pace`, `elevation_text`) into LLM context via `CoachUnits`. The LLM system prompt includes the athlete's `preferred_units` so narrative text matches.

### CSV Exports

`routers/reports.py` CSV export respects `Athlete.preferred_units`. Imperial athletes see miles, lbs, °F, min/mi; metric athletes see km, kg, °C, min/km.

## Key Decisions

- **Canonical units at the API boundary.** The API ships meters and seconds-per-km. No consumer should ever see `distance_mi` or `pace_per_mile` in an API response.
- **Frontend owns display conversion.** The `useUnits()` hook is the single conversion point. No manual `* 0.621371` anywhere in component code.
- **Backend LLM text is unit-aware.** `CoachUnits` ensures narrative text matches the athlete's preference. The LLM never receives hardcoded imperial instructions.
- **Country-aware defaults, not US-first defaults.** New athletes outside the US default to metric. US athletes default to imperial. Either can be overridden.
- **`preferred_units_set_explicitly` flag.** Distinguishes between inferred defaults and explicit athlete choices. Country-aware re-derivation only applies when `False`.

## What Was Eliminated

The Apr 2026 migration replaced these patterns across ~50 files:

| Old pattern | New pattern |
|-------------|-------------|
| `distance_mi` (API field) | `distance_m` |
| `pace_per_mile` (API field) | `pace_s_per_km` |
| `duration_min` (API field) | `duration_s` |
| `total_distance_miles` | `total_distance_m` |
| `average_pace_per_mile` | `avg_pace_s_per_km` |
| `elevation_gain_ft` | `elevation` (meters) |
| `formatMiles(mi)` (frontend) | `formatDistance(meters)` via `useUnits()` |
| `rewriteImperialToMetric()` (regex hack) | Eliminated — no longer needed |
| Hardcoded `"min/mi"` labels | Dynamic via `paceUnit` from `useUnits()` |

## Sources

- `apps/web/lib/context/UnitsContext.tsx` — `useUnits()` hook, conversion utilities
- `apps/api/services/coach_units.py` — `CoachUnits` helper for LLM text
- `apps/api/services/timezone_utils.py` — `derive_default_units()`, country inference
- `apps/api/services/coaching/_guardrails.py` — `_maybe_update_units_preference()`
- `apps/api/routers/home.py` — unit-aware briefing context
- `apps/api/tasks/home_briefing_tasks.py` — unit-aware briefing data dicts
- `apps/api/routers/reports.py` — unit-aware CSV export
