# Phase 1 — Activities-list filters: design

## Principle

Filtering is a visualization, not a form. The athlete sees the distribution of
their data in each filterable dimension and brushes the range they care about
directly on that distribution. They never type a number. They never open a
dropdown for a numeric range. They see "where my data lives" before they
filter it.

This applies the design philosophy: visual catches the eye → athlete interacts →
narrative below. The histogram IS the visual. The filtered count is the
narrative.

## Layout

The filter strip lives above the activities list, replacing the current
4-column grid of dropdowns. It is a single horizontal row of five compact
panels, scrollable on narrow viewports.

```
┌─────────────────┬──────────────┬──────────────┬──────────────┬──────────────┐
│ Workout type    │ Distance     │ Dew point    │ Temp         │ Elev gain    │
│ chip strip      │ histogram    │ histogram    │ histogram    │ histogram    │
│ ▣Easy 89        │ ▁▂▆█▆▃▁      │ ▁▃▆█▇▅▂      │ ▁▂▄█▇▅▂      │ █▇▄▂▁        │
│ ▢Long 47        │ [brush band] │ [brush band] │ [brush band] │ [brush band] │
│ ▢Thresh 23      │ 6—14 mi      │ 50—75 °F     │ 55—80 °F     │ 0—800 ft     │
└─────────────────┴──────────────┴──────────────┴──────────────┴──────────────┘
```

Below the strip, an active-filter chip row when any filter is active:

```
Filtered: [Long Run ×] [Dew 60–75 °F ×] [3 mi–18 mi ×]                Clear all
```

Below that, the filtered count: "47 activities match" — narrative-line.
Below that, the activity list (unchanged).

## Histogram component

Each numeric histogram (distance, dew point, temp, elevation gain):

- 16-bucket histogram of the athlete's actual values for that dimension across
  all their activities (no time window — full lifetime, this is filter context).
- Bar height log-scaled for distribution visibility (long-run distance has a
  long tail; without log, the bulk is squashed).
- Subtle overlay band shows the active brushed range; bars outside the brush
  rendered at reduced opacity.
- Drag the band edges to adjust min/max. Click on a bar to brush to that bucket.
- Double-click anywhere on the histogram to clear that filter.
- Below the histogram: dynamic range label (e.g., "8.2 — 13.4 mi") respecting
  unit preference.
- Tooltip on hover shows bucket count.

Color scheme: bars in `slate-600` for inactive, `orange-500` for the active
brush range. Matches existing design system.

## Workout-type chip strip

- One chip per workout_type the athlete has at least one of.
- Each chip shows label + count: "Long Run · 47".
- Tap to toggle inclusion (multi-select). Default: all on (no filter active).
- When all are on, no `workout_type` parameter is sent.
- Suppressed: workout types with zero activities don't render.

## Suppression rules

- A histogram dimension where every activity has NULL is not rendered at all.
- A histogram dimension where the athlete has fewer than 5 activities with
  values is not rendered (insufficient distribution to be meaningful).
- The workout-type chip strip is hidden if the athlete has fewer than 2
  distinct workout types.
- Active-filter chip row is invisible when no filters are active.
- "X activities match" line appears only when filters are active (otherwise
  the existing "N activities in last 30 days" line shows).

## URL state

All active filters serialize to URL query params:

```
/activities?workout_type=long_run,threshold&dew_min=60&dew_max=75&distance_min=8000&distance_max=20000
```

Deep-link-restorable. Shareable.

## Backend contract

Endpoint: `GET /v1/activities` (existing).

New query params (all optional, all individually nullable):
- `workout_type`: comma-separated list (e.g., `long_run,threshold`)
- `temp_min` / `temp_max`: float, °F
- `dew_min` / `dew_max`: float, °F
- `elev_gain_min` / `elev_gain_max`: float, meters
  (the existing `min_distance_m` / `max_distance_m` are kept; UI sends these)

New endpoint: `GET /v1/activities/filter-distributions`

Returns histogram data per dimension for the filter UI:

```json
{
  "workout_types": [
    {"value": "long_run", "count": 47},
    {"value": "easy_run", "count": 89},
    ...
  ],
  "distance_m": {
    "min": 1500,
    "max": 32000,
    "buckets": [{"lo": 1500, "hi": 3406, "count": 12}, ...],
    "available": true
  },
  "dew_point_f": {"min": ..., "max": ..., "buckets": [...], "available": true},
  "temp_f": {"min": ..., "max": ..., "buckets": [...], "available": true},
  "elevation_gain_m": {"min": ..., "max": ..., "buckets": [...], "available": false}
}
```

`available: false` when fewer than 5 activities have a value in that
dimension. Frontend uses this to suppress the histogram entirely.

## Behavioral smoke (post-deploy)

1. On prod against my data: open `/activities`, brush dew range to 60–75 °F,
   brush distance to 8–20 mi. Verify list is long runs in summer-like conditions.
2. Add `workout_type=threshold` chip → verify list narrows to threshold sessions
   in those conditions.
3. Copy URL, open in incognito tab → identical filtered view restored.
4. Find a dimension I have no data for (e.g., if I have no elevation data on
   any activity) and verify that histogram doesn't render.
5. Clear all → list returns to default chronological view.

## What I will NOT do in Phase 1

- Date range filter — already have `start_date` / `end_date` params, leaving
  the existing date-range UX (currently absent in the list page) for future.
- Saved filter presets — defer.
- Sort options change — keep existing sort dropdown.
- Pace/HR filtering — out of scope for Phase 1, can add later.
