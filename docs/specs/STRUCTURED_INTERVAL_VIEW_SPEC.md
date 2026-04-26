# Structured Interval View — Spec

**Date:** April 9, 2026
**Status:** Scoped — ready to build
**Estimated effort:** 1 session (backend + frontend)
**Priority:** Athlete retention — athletes leave to Garmin for interval analysis

---

## Problem

After an interval workout, runners immediately want to see their splits
structured by workout segment: warm up, work intervals (numbered), rest
intervals, cool down. Garmin's "Intervals" tab does this perfectly —
type labels, interval numbering, clean table.

StrideIQ shows a flat `SplitsTable` — Split 1, Split 2, Split 3... with
no type distinction. Every lap looks the same. Runners go to Garmin
instead. This is a trust and engagement loss on one of the most
important activity types for serious runners.

---

## What Exists Today

1. **`ActivitySplit` rows** per activity — split_number, distance,
   elapsed_time, moving_time, average_heartrate, max_heartrate,
   average_cadence, gap_seconds_per_mile. No `type` field.

2. **`adapt_activity_detail_laps()`** in `garmin_adapter.py` — processes
   Garmin's raw `laps` array but drops any type metadata. Only stores
   numbered splits.

3. **`_detect_intervals()`** in `workout_classifier.py` — already
   identifies alternating fast/slow patterns using pace variance
   (CV > 15%) and counts work segments (≥3 to classify as intervals).
   Returns `(is_intervals, num_work_segments, avg_work_duration)`.

4. **`SplitsTable`** component — renders flat numbered rows. Highlights
   fastest split. No type labels, no grouping.

5. **`GET /v1/activities/{id}/splits`** — returns `ActivitySplit` rows
   ordered by split_number.

---

## Solution

### Backend

#### 1. Check Garmin raw laps for type metadata

Before building derivation logic, check whether Garmin's raw `laps`
array includes a `messageType`, `lapTrigger`, or similar field that
distinguishes workout laps from auto-laps. If present:

- `adapt_activity_detail_laps()` should extract and store it
- Add `lap_type` column to `ActivitySplit` (see below)

If Garmin does NOT send type metadata in the Health API push
(likely — the FIT protocol has it but the JSON API may not), proceed
with derivation.

#### 2. Add `lap_type` column to `ActivitySplit`

```python
lap_type = Column(Text, nullable=True)
# Values: 'warm_up', 'work', 'rest', 'cool_down', None (unclassified)
```

Migration: add column, nullable, no backfill required (derivation
happens at query time for existing data, persisted on new ingestion).

#### 3. Derive interval structure from splits

Create `apps/api/services/interval_detector.py`:

```python
def detect_interval_structure(splits: List[ActivitySplit]) -> IntervalAnalysis:
    """
    Analyze splits to detect and label workout structure.

    Returns IntervalAnalysis with:
    - labeled_splits: each split with lap_type assigned
    - workout_summary: "5×4:00 at 7:09 avg, 3:00 rest" or None
    - is_structured: True if interval pattern detected
    """
```

**Detection algorithm** (adapted from `_detect_intervals`):

1. Compute pace for each split (moving_time / distance)
2. Calculate mean pace and coefficient of variation
3. If CV < 12%: not structured → return all splits as unclassified
4. If CV ≥ 12%: classify each split:
   - Splits faster than `mean_pace * 0.93` → candidate `work`
   - Splits slower than `mean_pace * 1.07` → candidate `rest`
   - First split if slow + short → `warm_up`
   - Last split if slow + ≥ 0.5 mi → `cool_down`
   - Remaining fast splits → `work` (numbered sequentially)
   - Remaining slow splits between work segments → `rest`
5. Generate summary string:
   - Count work segments, compute avg work time, avg work pace
   - Count rest segments, compute avg rest time
   - Format: "5×4:00 at 7:09/mi avg, 3:00 rest"

**Edge cases:**
- Tempo runs (1 fast segment between warm up and cool down) →
  label as warm_up / work / cool_down, summary: "20:00 at 6:45/mi"
- Progression runs (each split faster) → don't force interval structure
- Fartlek (irregular fast/slow) → label work/rest but note irregular
  duration in summary

#### 4. Extend splits API response

Modify `GET /v1/activities/{id}/splits` to include:

```json
{
    "splits": [
        {
            "split_number": 1,
            "lap_type": "warm_up",
            "interval_number": null,
            "distance": 628,
            "elapsed_time": 231,
            "moving_time": 231,
            "average_heartrate": 120,
            "max_heartrate": 135,
            "average_cadence": 164,
            "gap_seconds_per_mile": 590
        },
        {
            "split_number": 2,
            "lap_type": "work",
            "interval_number": 1,
            "distance": 885,
            "elapsed_time": 240,
            "moving_time": 240,
            "average_heartrate": 165,
            ...
        },
        {
            "split_number": 3,
            "lap_type": "rest",
            "interval_number": null,
            "distance": 563,
            "elapsed_time": 180,
            "moving_time": 180,
            ...
        }
    ],
    "interval_summary": {
        "is_structured": true,
        "workout_description": "5×4:00 at 7:09/mi avg, 3:00 rest",
        "num_work_intervals": 5,
        "avg_work_pace_sec_per_km": 268,
        "avg_work_hr": 168,
        "avg_rest_duration_s": 180,
        "avg_rest_hr": 138,
        "fastest_interval": 4,
        "slowest_interval": 2
    }
}
```

If the activity is not classified as intervals (or not a run),
`interval_summary` is null and all `lap_type` values are null.

#### 5. Persist on ingestion

When `adapt_activity_detail_laps()` creates new `ActivitySplit` rows,
run `detect_interval_structure()` and persist the `lap_type` on each
row. This avoids re-computing on every API call.

For tempo and threshold workouts (1 sustained work segment):
still label warm_up / work / cool_down. The structure is relevant
even when there's only one work segment.

---

### Frontend

#### 1. Structured Intervals View

Add an "Intervals" tab or view within the activity detail page for
runs classified as intervals, tempo, or threshold.

**Layout (matching Garmin's structure):**

```
┌──────────────────────────────────────────────┐
│  5×4:00 at 7:09/mi avg · 3:00 rest          │  ← Summary header
├──────────────────────────────────────────────┤
│     Warm Up    3:51    0.39mi    9:58/mi     │  ← Muted text
├──────────────────────────────────────────────┤
│  1  Run        4:00    0.55mi    7:14/mi     │  ← Bold/white
│     Rest       3:00    0.35mi    8:28/mi     │  ← Muted
│  2  Run        4:00    0.55mi    7:19/mi     │
│     Rest       3:00    0.35mi    8:36/mi     │
│  3  Run        4:00    0.55mi    7:14/mi     │
│     Rest       3:00    0.37mi    8:04/mi     │
│  4  Run        4:00    0.58mi    6:53/mi  ★  │  ← Fastest marked
│     Rest       3:00    0.34mi    8:44/mi     │
│  5  Run        4:00    0.55mi    7:19/mi     │
├──────────────────────────────────────────────┤
│     Cool Down  8:28    1.03mi    8:12/mi     │  ← Muted
├──────────────────────────────────────────────┤
│     Total      44:21   5.62mi    7:53/mi     │
└──────────────────────────────────────────────┘
```

**Visual rules:**
- Work intervals: white text, bold, interval number on left
- Rest intervals: slate-400 text, indented, no number
- Warm up / cool down: slate-400 text, labeled, no number
- Fastest work interval: star or highlight marker
- Summary line at top: large text, the headline takeaway
- Columns: Type, Time, Distance, Pace (minimum). HR optional column.

#### 2. Tab or toggle integration

**Option A — Replace SplitsTable for structured workouts:**
When `interval_summary.is_structured` is true, show the Intervals
view by default. Add a "Mile Splits" toggle to see the flat view.

**Option B — Add Intervals tab alongside Splits:**
Two tabs: "Intervals" (structured) | "Splits" (flat per-mile).
Intervals tab only visible when `is_structured` is true.

Recommendation: **Option A.** The structured view is strictly better
for interval workouts. The flat view is a fallback for easy/steady runs
that have no structure.

#### 3. Mobile-first

390px viewport. The table must not horizontally scroll for the core
columns (Type, Time, Dist, Pace). HR and Cadence can be hidden on
mobile or shown on expand.

44px row height for touch targets.

---

## What NOT to Build

- Workout builder / structured workout creation
- Comparison across interval sessions (future feature)
- Integration with training plan workout structure
- Auto-detection from stream data (use splits/laps, not raw HR/pace streams)

---

## Testing

1. Activity with 5+ laps, high pace variance → detected as intervals,
   warm up/work/rest/cool down correctly labeled
2. Activity with 2 laps → not detected as intervals, flat view shown
3. Tempo run (1 sustained fast segment) → warm_up/work/cool_down labeled
4. Easy run (low pace variance) → no structure detected, flat splits
5. Summary string correctly formats rep count, avg pace, rest duration
6. Fastest interval correctly identified
7. Mobile: table renders without horizontal scroll at 390px

---

## Success Criteria

1. After an interval workout, the athlete opens StrideIQ and sees
   "5×4:00 at 7:09/mi avg, 3:00 rest" with structured type labels —
   without going to Garmin
2. Work intervals are visually distinct from rest intervals
3. Fastest interval is immediately visible
4. The view works at 390px viewport width
