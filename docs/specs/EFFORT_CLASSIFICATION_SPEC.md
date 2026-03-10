# Effort Classification — Shipped Spec

**Date:** March 3, 2026
**Status:** Shipped reality — Tiers 1-3 live
**Purpose:** Define the effort-classification system that is currently in
production after removing `athlete.max_hr` as a hard gate.

**Future work:** The pace-anchored Tier 0 / TPP concept has been split
out into `docs/specs/EFFORT_CLASSIFICATION_TIER0_PROPOSAL.md` so this
document stays honest about what is shipped.

---

## The Problem

The old system used `athlete.max_hr` as a hard gate in multiple services.
If the profile field was null, those paths returned `None` or empty
arrays. The founder's `max_hr` is null. The result was:

- correlation sweep metrics silently producing nothing
- Recovery Fingerprint returning `None`
- workout classification falling back inconsistently
- hrTSS being skipped
- hardcoded guesses like `185` leaking into downstream logic

Max HR is a population metric. Using it as a hard gate contradicts the
N=1 philosophy and silently cripples the system for athletes who have
never surfaced a trustworthy ceiling.

---

## Shipped Decision

**Replace all max_hr-gated effort classification with a single shared
function that always returns `hard`, `moderate`, or `easy` using the
athlete's own data.**

### `classify_effort(activity, athlete_id, db) -> "hard" | "moderate" | "easy"`

One function. One place to improve. Used everywhere.

---

## Shipped Tiers

### Tier 1 (primary): HR Percentile Distribution

Compute the athlete's personal HR distribution from all activities with
`avg_hr`. Classify by percentile position:

| Percentile | Classification |
|-----------|----------------|
| >= P80 | hard |
| P40 - P79 | moderate |
| < P40 | easy |

**Properties:**
- available whenever the athlete has HR history
- makes no claim about a ceiling the data doesn't contain
- self-calibrating as the athlete's HR distribution shifts over time
- "this session was in the top 20% of your effort history" is always
  true from the data that exists

### Tier 2 (secondary): HRR with Observed Peak

Heart Rate Reserve using resting HR (from Garmin daily data or check-in)
and observed peak HR (`MAX(Activity.max_hr)` from history).

**Eligibility gate:** Only used when the system has:
- 20+ activities with HR data, AND
- at least 3 activities classified as hard by Tier 1

This ensures the observed peak is meaningfully close to the real ceiling.

**Formula:** `HRR = (avg_hr - resting_hr) / (observed_peak_hr - resting_hr)`

| HRR | Classification |
|-----|----------------|
| >= 0.75 | hard |
| 0.45 - 0.74 | moderate |
| < 0.45 | easy |

When Tier 2 is eligible, it can be used alongside Tier 1 for higher
confidence. Agreement = high confidence. Disagreement = log for review.

### Disagreement Signals

When the active tier's classification and RPE (from `DailyCheckin`)
disagree by more than one tier, log the event. This is captured as a
timestamped disagreement record for future correlation input. It is not
blocking and not alerting.

### Tier 3 (tertiary): Workout Type + RPE

When HR data is sparse:

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

### File: `services/effort_classification.py`

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
    - tier: which classification tier is active ("percentile",
      "hrr", "workout_type")
    - p80_hr, p40_hr (Tier 1 boundaries)
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

The percentile thresholds are cached in Redis:
`effort_thresholds:{athlete_id}`, recalculated when new activities sync.

### Migration Path

The 8 services now call `classify_effort()` and `get_effort_thresholds()`.
The output domain remains `"hard"`, `"moderate"`, `"easy"` — unchanged
from what consumers already handle.

---

## Migrated Files

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

- [x] AC1: `classify_effort()` returns valid classification for athletes with no `max_hr` set
- [x] AC2: Recovery Fingerprint renders real data for the founder
- [x] AC3: All 9 correlation sweep metrics produce non-empty output for the founder
- [x] AC4: No code path uses `220 - age` or hardcoded `185`
- [x] AC5: No code path returns None/empty solely because `athlete.max_hr` is null
- [x] AC6: Percentile thresholds are cached and recalculated on new activity
- [x] AC7: Tier selection is logged (which tier was used for each classification)
- [x] AC8: All existing tests pass (with updated expectations where needed)
- [x] AC9: New tests cover all three tiers and the eligibility gate for Tier 2
- [x] AC10: RPE disagreement events (>1 tier gap) are logged for future correlation input

---

## What This Unlocks

- Recovery Fingerprint renders with real data
- Correlation sweep produces findings across all 9 metrics
- No population formulas, no max_hr gates

For every future user:
- No profile field needs to be set before the system works at full capability
- Connect Garmin → history imports → effort classification works immediately
- The system improves its understanding of the athlete as more data arrives
- No population metric ever gates N=1 intelligence

---

## Future Tier 0

The pace-anchored Tier 0 / TPP concept is intentionally not specified
here as shipped behavior. See:

- `docs/specs/EFFORT_CLASSIFICATION_TIER0_PROPOSAL.md`
