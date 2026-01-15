# ADR-012: Pace Decay Analysis

## Status
Accepted

## Date
2026-01-14

## Context

### The Problem

Athletes often experience pace fade in races, especially in longer distances. Understanding:
1. How much did I slow down in the final segments?
2. Is this my pattern, or was this race different?
3. What conditions correlate with more/less decay?

This helps athletes:
- Adjust pacing strategy
- Identify fueling issues
- Recognize fitness limiters

### Scientific Basis

Pace decay is the reduction in running speed during a race, typically quantified as:
- Percentage drop from average pace in early segments
- Comparison of first half to second half (positive/negative split)
- Rate of decay in final 20-30% of race

Research shows:
- Elite marathoners aim for <2% pace decay
- Recreational runners often see 5-15% decay
- Decay correlates with glycogen depletion, heat, and inadequate fitness

### Existing Data

StrideIQ has:
- `ActivitySplit`: Per-mile/km splits with `elapsed_time`, `distance`, `average_heartrate`
- `Activity`: Race flag, total distance, total time
- `NutritionEntry`: Pre/during/post activity nutrition
- `DailyNote`: Post-workout notes including fueling details

## Decision

Implement Pace Decay Analysis:

### 1. Core Metrics

**Decay Percentage**: Drop from early pace to late pace
```
decay_pct = ((late_pace - early_pace) / early_pace) * 100
```

**Split Classification**:
- NEGATIVE: Late faster than early (rare, excellent execution)
- EVEN: ±2% difference
- MILD_POSITIVE: 2-5% slower
- MODERATE_POSITIVE: 5-10% slower
- SEVERE_POSITIVE: >10% slower

**Segment Analysis**:
- First third vs last third
- First half vs second half
- Peak pace vs final 20%

### 2. Pattern Detection

Compare current race to athlete's history:
- "Typical decay for you at this distance"
- "More decay than usual — 8% vs your average 4%"
- "Less decay than usual — pacing improved"

### 3. Correlation Analysis (Future)

When nutrition/checkin data available:
- Pre-run carbs vs decay
- Sleep quality vs decay
- Training load leading up to race

### 4. Insight Generation

Examples:
- "Pace decayed 8% in last 5K — higher than your typical 4% at this distance."
- "Strong negative split — finished 3% faster than you started."
- "Decay matches your pattern when you skip pre-race fueling."

Always cautious, never prescriptive.

## Implementation

### New Service

`apps/api/services/pace_decay.py`:
- `calculate_split_paces(splits: List[Split]) -> List[float]`
- `calculate_decay_metrics(splits: List[Split]) -> DecayMetrics`
- `classify_split_pattern(decay_pct: float) -> SplitPattern`
- `compare_to_history(current: DecayMetrics, history: List[DecayMetrics]) -> Comparison`
- `get_activity_pace_decay(activity_id: str, db: Session) -> DecayAnalysis`
- `get_athlete_decay_profile(athlete_id: str, db: Session) -> DecayProfile`

### API Endpoint

`GET /v1/analytics/pace-decay/{activity_id}`:
- Returns decay metrics for specific activity
- Includes historical comparison

`GET /v1/analytics/pace-decay/profile`:
- Returns athlete's typical decay patterns by distance

### Edge Cases

1. **Short races (<3 splits)**: Cannot calculate meaningful decay
2. **Missing splits**: Interpolate or mark as incomplete
3. **Non-race activities**: Calculate but flag as "training run"
4. **Outlier splits**: Detect and optionally exclude (e.g., bathroom break)
5. **Ultra-marathons**: Decay is expected; adjust thresholds

## Consequences

### Positive
- Provides actionable pacing feedback
- Identifies fueling/fitness issues
- Tracks improvement over time
- No additional data collection required

### Negative
- Requires split data (not all activities have it)
- Short races have limited analysis
- Cannot prove causation with correlations

## Test Plan

1. Unit tests for pace calculation from splits
2. Unit tests for decay percentage calculation
3. Test split pattern classification
4. Test historical comparison
5. Test edge cases (short races, missing splits, outliers)
6. Test insight generation

## Feature Flag

`analytics.pace_decay` - Enable after implementation
