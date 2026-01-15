# ADR-010: Training Stress Balance (TSB/ATL/CTL)

## Status
Accepted

## Date
2026-01-14

## Context

### The Problem

Athletes need to understand:
1. Are they building fitness (CTL rising)?
2. Are they accumulating too much fatigue (ATL high)?
3. Are they fresh enough to race well (TSB positive)?

Traditional tools (TrainingPeaks) provide these metrics but:
- Require power meter data (not common for runners)
- Use fixed constants (7-day ATL, 42-day CTL) that don't fit all athletes
- Don't integrate with other insights (HRV, efficiency, race fingerprinting)

### Existing Implementation

StrideIQ already has `services/training_load.py`:
- TSS calculation (hrTSS, rTSS, estimated)
- ATL/CTL/TSB with exponential moving averages
- Training phase detection
- Basic recommendations

### Current Gap

What's missing:
1. **Unit tests** - No test coverage
2. **Feature flag** - Not controlled
3. **Actionable zones** - No "race window" detection
4. **Personal calibration** - Fixed decay constants, not personalized
5. **Integration** - Not connected to Pre-Race Fingerprinting

## Decision

Enhance TSB implementation with:

### 1. Actionable TSB Zones

| TSB Range | State | Insight |
|-----------|-------|---------|
| +15 to +25 | Fresh & fit | "Race window - fitness high, fatigue low" |
| +5 to +15 | Recovering | "Final taper zone - ready soon" |
| -10 to +5 | Optimal training | "Building phase - productive overload" |
| -30 to -10 | Overreaching | "High fatigue - monitor recovery" |
| < -30 | Overtraining risk | "Red zone - consider rest" |

### 2. Race Readiness Score

Combine TSB with:
- TSB value (weighted)
- TSB trend (rising = better)
- Days since last hard workout
- Recent sleep quality (if available)

Output: 0-100 "Race Readiness" score

### 3. Personal Decay Constants

Future enhancement: Discover optimal τ1 (CTL decay) and τ2 (ATL decay) from athlete's data by correlating training patterns with performance outcomes.

### 4. Integration Points

- Pre-Race Fingerprinting: Include TSB as a feature in readiness analysis
- Efficiency Trending: Correlate TSB with efficiency changes
- Home Page: Surface TSB in daily insights

## Implementation

### Enhanced Service

Add to `services/training_load.py`:
- `get_tsb_zone(tsb: float) -> TSBZone`
- `calculate_race_readiness(athlete_id, target_date) -> RaceReadiness`
- `project_tsb(athlete_id, days_ahead) -> List[float]`

### Unit Tests

New file `tests/test_training_load.py`:
- Test TSS calculations for all methods
- Test ATL/CTL/TSB accuracy
- Test zone classification
- Test edge cases (no data, single workout)

### Feature Flag

`analytics.training_stress_balance` - Enable/disable TSB features

## Consequences

### Positive
- Actionable race window detection
- Clear fatigue warnings
- Foundation for personal calibration
- Integration with other analytics

### Negative
- TSS estimation without power/HR data is less accurate
- Fixed decay constants may not fit all athletes
- Requires ~42 days of data for accurate CTL

## Test Plan

1. Unit tests for TSS calculations
2. Unit tests for ATL/CTL/TSB math
3. Unit tests for zone classification
4. Integration tests for API endpoints
5. Edge cases: no data, sparse data, single workout

## Feature Flag

`analytics.training_stress_balance` - Currently enabled, controls TSB features
