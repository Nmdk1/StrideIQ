# ADR-008: Efficiency Factor Trending Enhancement

## Status
Accepted

## Date
2026-01-14

## Context

StrideIQ has existing efficiency calculation infrastructure:
- `efficiency_calculation.py`: EF from NGP with cardio lag filter and decoupling
- `efficiency_analytics.py`: Trends, stability metrics, load-response
- `/v1/analytics/efficiency-trends` endpoint

However, the current implementation lacks:
1. **Statistical significance testing** - trend detection uses simple averaging
2. **Confidence levels** - no communication of uncertainty
3. **Actionable insight surfacing** - no detection of when trends become meaningful
4. **Individual calibration** - uses fixed thresholds, not personalized

## Decision

Enhance efficiency trending with:

### 1. Statistical Trend Detection
Replace simple average comparison with proper regression:
- Linear regression slope with p-value
- Only surface "improving" or "declining" when p < 0.05
- Report confidence level based on sample size and variance

### 2. Trend Confidence Classification
| Confidence | Criteria |
|------------|----------|
| High | p < 0.01, n >= 20, R² > 0.5 |
| Moderate | p < 0.05, n >= 10 |
| Low | p < 0.10, n >= 5 |
| Insufficient | p >= 0.10 or n < 5 |

### 3. Insight Surfacing Rules
Surface efficiency insights when:
- Trend is statistically significant (p < 0.05)
- Effect size is meaningful (>3% change over period)
- Athlete can take action (not mid-race, not injured)

### 4. New Metrics
- `trend_slope`: EF change per week (negative = improving)
- `trend_p_value`: Statistical significance
- `trend_confidence`: High/Moderate/Low/Insufficient
- `efficiency_percentile`: Where this athlete sits vs. their own history
- `days_to_pr_pace`: At current trend, when could they match PR efficiency?

## Consequences

### Positive
- More accurate trend detection (fewer false positives)
- Clear communication of uncertainty
- Actionable insights with timing context
- Foundation for Pre-Race Fingerprinting (Priority 2)

### Negative
- Requires more data points before surfacing insights
- Slightly more complex calculation

## Implementation

### Files Modified
- `apps/api/services/efficiency_analytics.py` - Add statistical methods
- `apps/api/services/efficiency_trending.py` - New file for trending logic
- `apps/api/routers/analytics.py` - Enhanced response
- `apps/api/tests/test_efficiency_trending.py` - New tests

### Feature Flag
- `EFFICIENCY_TRENDING_V2` - Enables enhanced trending

### Dependencies
- `scipy.stats` for linear regression (already available)

## Test Plan
1. Unit tests for statistical calculations
2. Test with known data patterns (improving, declining, stable, noisy)
3. Verify no regressions in existing efficiency endpoint
4. Integration test for insight surfacing
