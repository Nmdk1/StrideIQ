# Effort Classification — Architectural Spec

**Date:** March 3, 2026
**Status:** Approved by founder
**Priority:** Critical — currently blocking 6 of 9 correlation metrics,
Recovery Fingerprint, and degrading workout classification, TSS, and insights

---

## The Problem

The system uses `athlete.max_hr` as a hard gate in 7 services across 12
code paths. If the profile field is null, those paths return None or empty
arrays. The founder's max_hr is null. The result:

- 6 of 9 correlation sweep metrics silently produce nothing
- Recovery Fingerprint returns None
- Workout classification falls back to pace/duration heuristics
- hrTSS (most accurate training stress) is skipped
- Insight aggregator uses hardcoded `185` as a guess

Max HR is a population metric. It requires a lab test or a race effort
brutal enough to surface the true ceiling. Most athletes never produce it
in normal training. Using it as a gate contradicts the N=1 philosophy
and silently cripples the system for every athlete who hasn't set it.

---

## The Design Decision

**Replace all max_hr-gated effort classification with a single shared
function that uses the athlete's own HR distribution.**

### `classify_effort(activity, athlete_id, db) → "hard" | "moderate" | "easy"`

One function. One place to improve. Used everywhere.

### Tier 1 (primary): HR Percentile Distribution

Compute the athlete's personal HR distribution from all activities with
`avg_hr`. Classify by percentile position:

| Percentile | Classification |
|-----------|----------------|
| >= P80 | hard |
| P40 - P79 | moderate |
| < P40 | easy |

**Properties:**
- Always available if the athlete has any activity history with HR
- Makes no claim about a ceiling the data doesn't contain
- Self-calibrating — as fitness changes, the distribution shifts
- What was P60 two years ago becomes P40 today without anyone telling
  the system the athlete improved
- The statement "this session was in the top 20% of effort" is always
  true from the data that exists

**Why not HRR as primary:** HRR requires an observed peak HR. If the
athlete's true ceiling never appeared in training data (because it only
surfaces in a sufficiently brutal race), the observed peak is
systematically low. Every HRR calculation is compressed — a run at 90%
of actual range looks like 97% of observed range. Hard sessions get
overclassified as maximal. The distribution is skewed from day one and
never self-corrects because the true ceiling never appears.

### Tier 2 (secondary): HRR with Observed Peak

Heart Rate Reserve using resting HR (from Garmin daily data or check-in)
and observed peak HR (`MAX(Activity.max_hr)` from history).

**Eligibility gate:** Only used when the system has:
- 20+ activities with HR data, AND
- At least 3 activities classified as "hard" by Tier 1

This ensures the observed peak is meaningfully close to the real ceiling.
Below this threshold, the observed peak is unreliable and HRR introduces
silent systematic error.

**Formula:** `HRR = (avg_hr - resting_hr) / (observed_peak_hr - resting_hr)`

| HRR | Classification |
|-----|----------------|
| >= 0.75 | hard |
| 0.45 - 0.74 | moderate |
| < 0.45 | easy |

When Tier 2 is eligible, it can be used alongside Tier 1 for higher
confidence (both agree = high confidence, they disagree = flag for review).

### RPE Disagreement Signal

When Tier 1 classification and the athlete's RPE (from DailyCheckin)
disagree by more than one tier, log the disagreement event for future
correlation analysis. Not blocking, not alerting — just captured as a
timestamped record with both values. Over time, these disagreement events
become their own correlation input: "On days when RPE was 2+ tiers above
HR classification, your next 48 hours showed..."

### Tier 3 (tertiary): Workout Type + RPE

When HR data is sparse (fewer than 10 activities with avg_hr):

| Signal | Classification |
|--------|----------------|
| `workout_type` in (race, interval, tempo_run, threshold_run) | hard |
| `workout_type` in (easy_run, recovery) | easy |
| `rpe_1_10 >= 7` (from DailyCheckin) | hard |
| `rpe_1_10 <= 4` | easy |
| Everything else | moderate |

### Never

- `220 - age` formula
- Hardcoded `185` or any other guess
- `athlete.max_hr` as a gate that returns None/empty when null
- Any classification that requires a number the data doesn't contain

---

## Implementation

### New file: `services/effort_classification.py`

```python
def classify_effort(
    activity: Activity,
    athlete_id: str,
    db: Session,
) -> str:
    """
    Returns "hard", "moderate", or "easy".

    Tier 1: HR percentile from athlete's own distribution.
    Tier 2: HRR with observed peak (when eligible).
    Tier 3: Workout type + RPE (when HR data sparse).
    """

def get_effort_thresholds(
    athlete_id: str,
    db: Session,
) -> dict:
    """
    Returns the athlete's current effort thresholds:
    - p80_hr, p40_hr (Tier 1 boundaries)
    - tier: which classification tier is active
    - observed_peak_hr (if available)
    - resting_hr (if available)
    - activity_count: how many activities with HR data
    - hard_count: how many classified as hard

    Cached in Redis, recalculated when new activities arrive.
    """

def classify_effort_bulk(
    activities: List[Activity],
    athlete_id: str,
    db: Session,
) -> Dict[UUID, str]:
    """
    Classify multiple activities at once (for aggregation functions).
    Computes thresholds once, applies to all.
    """
```

### Caching

The percentile distribution should be cached in Redis:
`effort_thresholds:{athlete_id}`, recalculated when new activities sync.
The distribution doesn't change per-request — it changes when new data
arrives.

### Migration Path

Every service that currently uses `athlete.max_hr` for effort
classification must be migrated to use `classify_effort()` or
`get_effort_thresholds()`. The migration is mechanical — replace the
max_hr gate with a call to the shared function.

---

## Files to Migrate

| File | Lines | Current behavior | Migration |
|------|-------|-----------------|-----------|
| `services/recovery_metrics.py` | 26-27, 380-384 | `HARD_SESSION_HR_THRESHOLD = 0.85 * max_hr` → None if null | Use `classify_effort_bulk()` for hard/easy session lists |
| `services/correlation_engine.py` | 791-798 | `aggregate_pace_at_effort()` → empty if no max_hr | Use `get_effort_thresholds()` for HR boundaries |
| `services/correlation_engine.py` | 932-938 | `aggregate_efficiency_by_effort_zone()` → empty if no max_hr | Same |
| `services/correlation_engine.py` | 1051-1056 | `aggregate_race_pace()` → empty if no max_hr | Same |
| `services/workout_classifier.py` | 533-536, 568-569 | `_calculate_hr_zone()` and `_calculate_intensity()` → None/skip | Use thresholds from `get_effort_thresholds()` |
| `services/workout_classifier.py` | 808-813 | Progressive run hard finish detection → skip | Same |
| `services/run_analysis_engine.py` | 338-339 | HR-based workout classification → skip | Use `classify_effort()` |
| `services/run_analysis_engine.py` | 1109-1110 | Red flag detection → skip | Use thresholds |
| `services/training_load.py` | 314, 340-344 | hrTSS → falls back to rTSS | Use observed peak or percentile-derived peak |
| `services/coach_tools.py` | 1506-1510, 1909-1913 | Effort zone evidence → empty | Use `get_effort_thresholds()` |
| `services/coach_tools.py` | 2488-2505 | HR zones display → skip | Derive from percentile thresholds |
| `services/insight_aggregator.py` | 419, 957 | Hardcoded `185` fallback | Use `get_effort_thresholds()` |
| `services/activity_analysis.py` | 179-183 | `220 - age` formula | Use `classify_effort()` |

---

## Acceptance Criteria

- [ ] AC1: `classify_effort()` returns valid classification for athletes with no `max_hr` set
- [ ] AC2: Recovery Fingerprint renders real data for the founder
- [ ] AC3: All 9 correlation sweep metrics produce non-empty output for the founder
- [ ] AC4: No code path uses `220 - age` or hardcoded `185`
- [ ] AC5: No code path returns None/empty solely because `athlete.max_hr` is null
- [ ] AC6: Percentile thresholds are cached and recalculated on new activity
- [ ] AC7: Tier selection is logged (which tier was used for each classification)
- [ ] AC8: All existing tests pass (with updated expectations where needed)
- [ ] AC9: New tests cover all three tiers and the eligibility gate for Tier 2
- [ ] AC10: RPE disagreement events (>1 tier gap) are logged for future correlation input

---

## What This Unlocks

When this ships, for the founder alone:
- Recovery Fingerprint renders with real data (dozens of hard sessions now classifiable)
- Correlation sweep produces findings across all 9 metrics (not just 3)
- Workout classification uses HR data instead of pace/duration fallbacks
- hrTSS becomes available for more accurate training load
- Insight aggregator stops using made-up numbers
- The Progress page fills with real, confirmed patterns from 2 years of data

For every future user:
- No profile field needs to be set before the system works at full capability
- Connect Garmin → history imports → effort classification works immediately
- The system improves its understanding of the athlete as more data arrives
- No population metric ever gates N=1 intelligence
