# ADR-035: N=1 Individualized TSB Zones

## Status
Accepted - Verified with Real Data

## Date
2026-01-15

## Context

### The Problem

ADR-010 established TSB zones using **population-based thresholds**:

| TSB Range | Zone |
|-----------|------|
| +15 to +25 | Race Ready |
| +5 to +15 | Recovering |
| -10 to +5 | Optimal Training |
| -30 to -10 | Overreaching |
| < -30 | Overtraining Risk |

**This is NOT N=1.** These thresholds assume all athletes respond the same way.

Reality:
- A high-volume marathoner may routinely train at TSB -20 and thrive
- A casual runner at TSB -10 might be deeply fatigued
- Generic thresholds label normal training as "overreaching" for some athletes

### The N=1 Philosophy

The athlete is the sole sample. What matters is:
- What is **normal for THIS athlete**?
- Is THIS athlete more or less fatigued than **their** typical state?
- Zones should be defined relative to **personal distribution**, not population norms

## Decision

Replace population-based TSB zones with **individualized zones** based on each athlete's historical TSB distribution.

### Personal Zone Calculation

1. **Collect historical TSB data** - Last 180 days of daily TSB values
2. **Calculate personal statistics**:
   - Mean TSB (μ): The athlete's typical training state
   - Standard Deviation (σ): How much their TSB varies
3. **Define zones relative to personal distribution**:

| Zone | Threshold | Meaning |
|------|-----------|---------|
| Race Ready | > μ + 1.5σ | Unusually fresh for this athlete |
| Recovering | μ + 0.75σ to μ + 1.5σ | Fresher than their normal |
| Normal Training | μ - 1σ to μ + 0.75σ | Their typical training range |
| Overreaching | μ - 2σ to μ - 1σ | More fatigued than usual for them |
| Overtraining Risk | < μ - 2σ | Unusually fatigued - investigate |

### Example: Two Athletes

| Metric | Casual Runner | Marathon Athlete |
|--------|---------------|------------------|
| Mean TSB | +5 | -20 |
| SD | 8 | 12 |
| "Race Ready" threshold | > +17 | > -2 |
| "Overreaching" threshold | < -11 | < -44 |
| TSB of -15 | **Overreaching** | **Normal Training** |

The same TSB value means completely different things for different athletes.

### Fallback for New Athletes

Athletes with < 56 days (8 weeks) of data:
- Use population defaults (legacy behavior)
- `is_sufficient_data` flag indicates when personal zones are active
- As data accumulates, zones automatically become personalized

### Minimum Standard Deviation

Enforce minimum SD of 8 to prevent overly narrow zones for very consistent athletes.

## Implementation

### Data Structure

```python
@dataclass
class PersonalTSBProfile:
    athlete_id: UUID
    mean_tsb: float
    std_tsb: float
    min_tsb: float
    max_tsb: float
    sample_days: int
    
    # Personalized thresholds
    threshold_fresh: float      # μ + 1.5σ
    threshold_recovering: float # μ + 0.75σ
    threshold_normal_low: float # μ - 1σ
    threshold_danger: float     # μ - 2σ
    
    is_sufficient_data: bool    # >= 56 days
```

### Method Changes

```python
# Old (population-based)
def get_tsb_zone(tsb: float) -> TSBZoneInfo

# New (N=1)
def get_tsb_zone(tsb: float, athlete_id: Optional[UUID] = None) -> TSBZoneInfo
def get_personal_tsb_profile(athlete_id: UUID) -> PersonalTSBProfile
```

### Zone Descriptions

Descriptions now include personal context:
- *"TSB -15 — within your typical training range (-30 to -12)"*
- *"TSB +5 is unusually fresh for you (>-2 is your race-ready zone)"*

## Edge Cases

### 1. Cold Start / New Athletes
- **Problem**: No historical data to calculate personal stats
- **Solution**: Fall back to population defaults, flag as `is_sufficient_data=False`

### 2. Gaps in Data
- **Problem**: Missing days affect mean/SD calculation
- **Solution**: Use only days with calculated TSB values (EMAs handle gaps gracefully)

### 3. Outliers
- **Problem**: Extreme TSB values (injury recovery, extended rest) skew statistics
- **Solution**: Consider trimmed mean/SD (exclude top/bottom 5%), or use median instead of mean
- **Current**: Not implemented - flagged for future enhancement

### 4. Inconsistent Athletes
- **Problem**: Very consistent athletes have tiny SD, leading to narrow zones
- **Solution**: Enforce minimum SD of 8

### 5. Seasonal Variation
- **Problem**: Off-season vs peak training have different TSB norms
- **Solution**: Use 180-day window (6 months) to capture natural variation
- **Future**: Consider seasonal weighting or rolling windows

## Verification Checklist

- [x] Unit tests for PersonalTSBProfile creation (46 tests passing)
- [x] Unit tests for zone classification with personal thresholds
- [x] Integration test: API returns personalized zones for real athlete
- [x] Manual verification: Check calculated thresholds for test athlete
    - Verified with athlete@example.com (198 activities, 180 days history)
    - Personal mean TSB: -3.2, SD: 13.9 (trimmed)
    - Thresholds: fresh>+17.6, recovering>+7.2, normal>-17.1, danger>-31.0
- [x] Logging: Log personal thresholds when calculated
- [x] Edge case: New athlete with <56 days data falls back correctly
- [x] Edge case: Athlete with consistent TSB gets minimum SD of 8
- [x] Outlier handling: Uses trimmed mean/SD (excludes top/bottom 5%)

## Test Plan

### Unit Tests
1. Profile creation from insufficient data → population defaults
2. Profile creation from sufficient data → calculated stats
3. Zone classification uses personal thresholds
4. Minimum SD enforcement
5. Zone descriptions include personal context

### Integration Tests
1. API endpoint returns personalized zone info
2. get_load_history returns 180 days of data
3. Calendar signals use personalized zones
4. Home page uses personalized zones

### Manual Verification
1. Query real athlete's profile, verify thresholds are sensible
2. Check UI displays personalized zone labels
3. Verify population fallback for new account

## Consequences

### Positive
- True N=1: Zones reflect individual, not population
- Eliminates false "overreaching" labels for high-volume athletes
- More actionable insights (fresh/fatigued *for you*)
- Self-calibrating as more data accumulates

### Negative
- Requires 8+ weeks of data for personalization
- Additional DB query to calculate profile
- More complex than fixed thresholds
- Outliers can skew statistics (future work)

### Performance Considerations
- Personal profile calculation requires loading 180 days of TSB history
- Consider caching profile with TTL (recalculate daily, not per request)
- Profile is ~O(180) TSB values - lightweight

## Future Enhancements

1. **Outlier handling**: Trimmed mean/SD to reduce sensitivity to extreme values
2. **Seasonal adjustment**: Weight recent data more heavily
3. **Confidence intervals**: Show uncertainty in zone thresholds
4. **Profile caching**: Cache PersonalTSBProfile with daily refresh
5. **Visual display**: Show personal distribution on Training Load chart

## Related ADRs

- ADR-010: Training Stress Balance (original implementation)
- ADR-022: Individual Performance Model (N=1 philosophy)
