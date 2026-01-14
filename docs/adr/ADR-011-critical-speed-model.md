# ADR-011: Critical Speed + D' Model

## Status
**ARCHIVED** — Removed from main branch as of 2026-01-14

### Archive Note

The Critical Speed + D' model has been **archived** and removed from the main codebase.

**Reason**: Redundant with Training Pace Calculator (VDOT-based), which:
- Predicts race times more simply and accurately from a single race input
- Uses well-understood paces (Easy, Tempo, Interval) that athletes recognize
- Doesn't require explaining D' (anaerobic reserve) to users

**User feedback**: CS predictions were confusing (two different predictions for same race), less accurate than VDOT, and provided low perceived value.

**Preserved in**: Branch `archive/cs-model-2026-01` for potential future pivot to insight-only mode (speed/endurance profile, trend analysis, race pacing strategy).

**Files removed**:
- `apps/api/services/critical_speed.py`
- `apps/web/components/tools/CriticalSpeedPredictor.tsx`
- `apps/api/tests/test_critical_speed.py`
- `apps/api/tests/test_cs_prediction.py`
- `/v1/analytics/cs-prediction` endpoint

---

## Original Decision (for reference)

## Date
2026-01-14

## Context

### The Problem

Athletes need to understand:
1. What is my sustainable aerobic ceiling (Critical Speed)?
2. How much anaerobic capacity do I have for surges (D')?
3. What pace can I realistically hold for any race distance?

Current tools either:
- Use simplified VDOT tables (assume fixed relationships)
- Require expensive lab testing
- Provide no confidence intervals

### Scientific Basis

The Critical Power/Speed model (Monod & Scherrer 1965, Hill 1993) describes a hyperbolic relationship between time and speed:

```
Time = D' / (Speed - CS) + (Distance / CS)

Rearranged:
Distance = CS * Time + D'
```

Where:
- **CS (Critical Speed)**: Speed theoretically maintainable indefinitely (aerobic ceiling)
- **D' (D-prime)**: Finite anaerobic distance reserve above CS

### Existing Data

StrideIQ has PersonalBest records with:
- `distance_category`: '400m', '800m', 'mile', '5k', '10k', 'half_marathon', 'marathon'
- `distance_meters`: Actual distance
- `time_seconds`: Fastest time
- `is_race`: Whether it was a race (more reliable)

## Decision

Implement Critical Speed + D' model:

### 1. Data Requirements

Minimum 3 PRs at different distances spanning:
- At least one short (≤2 miles)
- At least one medium (2-10 miles)
- At least one long (≥10 miles)

Prefer race PRs over training PRs (more maximal effort).

### 2. Model Fitting

Use linear regression on transformed data:
```
Distance = CS * Time + D'
```

This is a linear relationship: y = mx + b where:
- y = distance
- x = time
- m = CS (slope)
- b = D' (intercept)

### 3. Validation

- R² > 0.95 required for reliable model
- Residual analysis to detect outliers
- Confidence intervals on CS and D'

### 4. Pace Prediction

For any target distance:
```
Predicted Time = D' / (Target_Speed - CS) + Target_Distance / CS

Solving for speed:
Speed = CS + D' / Time
```

Provide predictions with confidence levels:
- High confidence: 3+ PRs, R² > 0.98
- Moderate confidence: 3+ PRs, R² > 0.95
- Low confidence: R² < 0.95 or <3 PRs

### 5. Cautious Insights

Output example:
> "Critical Speed: 4.8 m/s (4:52/km). D': 120m. Suggests 5K pace ~4:55/km at 95% confidence."

Never prescribe, only inform.

## Implementation

### New Service

`apps/api/services/critical_speed.py`:
- `fit_critical_speed_model(prs: List[PR]) -> CSModel`
- `predict_race_time(model: CSModel, distance_m: float) -> Prediction`
- `get_athlete_cs_profile(athlete_id: str, db: Session) -> CSProfile`

### API Endpoint

`GET /v1/analytics/critical-speed`:
- Returns CS, D', confidence level
- Includes predictions for standard distances
- Lists PRs used in calculation

### Edge Cases

1. **Insufficient data**: Return None with explanation
2. **Outlier detection**: Exclude PRs that deviate >20% from model
3. **Stale PRs**: Warn if oldest PR >2 years old
4. **Poor fit**: If R² < 0.90, suggest model may not apply

## Consequences

### Positive
- Provides personalized pacing predictions
- No lab testing required
- Clear confidence levels
- Based on established sports science

### Negative
- Requires 3+ PRs at different distances
- Assumes maximal efforts (training PRs may underestimate)
- Model breaks down at very short (<400m) or very long (>marathon) distances

## Test Plan

1. Unit tests for regression math
2. Unit tests for pace prediction
3. Test with known data (verified CS/D' values)
4. Test edge cases (2 PRs, all same distance, outliers)
5. Test confidence interval calculation

## Feature Flag

`analytics.critical_speed` - Enable after implementation

---

## Update: N=1 Model Tuning (2026-01-14)

### Problem

User feedback: Critical Speed model under-predicted 5K performance. Actual 5K PR was 19:01 but model predicted 19:33 (~2.8% error).

Root cause: Model was fitting equally to all distances, allowing long-distance PRs to pull CS lower than actual short-distance performance indicated.

### Fixes Applied

1. **Tighter outlier detection**
   - Changed threshold from 15% to 10% residual
   - More aggressively excludes non-representative PRs

2. **Stale PR exclusion**
   - PRs older than 2 years excluded from model fitting
   - Falls back to including if insufficient fresh data
   - Warning shown when stale data used

3. **Weighted regression for short distances**
   - PRs ≤10K get 1.5× weight in regression
   - This pulls CS higher for runners with strong shorter races
   - Addresses systematic under-prediction at short distances

4. **Distance clustering warnings**
   - If all PRs are >10K: "Model may under-predict short distances"
   - If all PRs are ≤10K: "Model may under-predict long distances"
   - Helps users understand model limitations

### Constants

```python
OUTLIER_THRESHOLD_PCT = 10.0  # Tightened from 15%
STALE_PR_DAYS = 730           # 2 years
SHORT_DISTANCE_WEIGHT = 1.5   # Weight for ≤10K PRs
SHORT_DISTANCE_THRESHOLD_M = 10000
```

### Trade-offs

- Weighted regression may slightly reduce accuracy for ultra-marathon predictions
- Excluding stale PRs means fewer data points for new users
- 10% outlier threshold may exclude more PRs than before

### Verification

- Added unit tests for weighted regression
- Added tests for stale PR filtering
- Added tests for distance clustering detection
- Manual verification with N=1 user data
