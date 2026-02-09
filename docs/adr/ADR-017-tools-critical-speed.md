# ADR-017: Tools Page - Critical Speed Pace Predictor

## Status
**ARCHIVED** — Removed from codebase as of 2026-01-14

### Archive Reason

After implementation and user testing, the CS + D' Predictor was found to:

1. **Be redundant** with the Training Pace Calculator (RPI-based), which predicts race times more simply and accurately from a single race input.

2. **Provide low perceived value** — Users don't understand D' (421m) and CS (3.96 m/s) metrics. The predictions weren't meaningfully better than RPI.

3. **Create confusion** — Two tools showing different predictions for the same race distance. Users don't know which to trust.

4. **Require complex data** — Needs multiple PRs correctly synced, which proved error-prone.

### Files Removed

- `apps/api/services/critical_speed.py`
- `apps/web/components/tools/CriticalSpeedPredictor.tsx`
- `apps/api/tests/test_critical_speed.py`, `test_cs_prediction.py`
- `/v1/analytics/cs-prediction` endpoint
- CS signals from Home, Analytics, Activity Detail

### Preserved In

Branch: `archive/cs-model-2026-01`

See also: `DEFERRED_REFACTOR_BACKLOG.md`

### Future Consideration

The CS model could be revived in a **pivot to insight-only** mode:
- "Your D' is low — consider adding speed work"
- "CS trending up 2% over 8 weeks"
- Race pacing strategy based on D' depletion

This would provide unique value that RPI cannot offer.

---

## Original Decision (for reference)

## Date
2026-01-14

## Context

### The Problem

The Tools page has useful calculators (RPI, Age-Grading, Heat-Adjusted Pace) but doesn't leverage our Critical Speed + D' model. Athletes who have built a CS profile from their race history can't easily use it to predict race times for custom distances.

### The Opportunity

We already have a robust Critical Speed service (ADR-011) that:
- Fits hyperbolic power-duration curve to PR data
- Calculates CS (aerobic ceiling) and D' (anaerobic reserve)
- Predicts race times for standard distances
- Provides confidence intervals and insight text

### Design Principles

- **Personalized**: Uses YOUR race data, not population averages
- **Confidence-aware**: Shows prediction confidence based on model fit
- **Sparse tone**: "Data predicts this. Test it."
- **Mobile-first**: Clean input, clear output

## Decision

### 1. Backend: CS Prediction Endpoint

New endpoint: `GET /v1/analytics/cs-prediction`

Query params:
- `distance_m`: Custom distance in meters (optional, default shows all standard)

Response:
```json
{
  "has_model": true,
  "model": {
    "critical_speed_m_s": 4.52,
    "d_prime_m": 180,
    "r_squared": 0.97,
    "confidence": "high",
    "prs_used": 4
  },
  "predictions": [
    {
      "distance_m": 5000,
      "distance_label": "5K",
      "predicted_time_s": 1068,
      "predicted_time_formatted": "17:48",
      "predicted_pace_per_km_s": 213.6,
      "predicted_pace_formatted": "3:34",
      "confidence_low_formatted": "17:20",
      "confidence_high_formatted": "18:16"
    }
  ],
  "insight": "Critical Speed 4.52 m/s suggests 5K pace ~3:34/km (high confidence)."
}
```

### 2. Frontend: CriticalSpeedPredictor Component

New component on Tools page:
- Card with CS profile summary (if available)
- Distance input (dropdown for standard + custom input)
- "Predict" button
- Prediction cards: time, pace/km, pace/mile, confidence range
- Insight sentence below

For unauthenticated or no-data users:
- Explain what CS is
- CTA to connect Strava/log races

### 3. UI Design

```
┌─────────────────────────────────────────┐
│ 🎯 Critical Speed Predictor             │
│ Predict race times from YOUR PR data    │
├─────────────────────────────────────────┤
│ Your CS: 4.52 m/s (3:41/km) • D': 180m  │
│ Model confidence: HIGH (4 PRs)          │
├─────────────────────────────────────────┤
│ Distance: [5K ▼] or [Custom: ___ m]     │
│ [Predict Time]                          │
├─────────────────────────────────────────┤
│ ┌───────────────────────────────────┐   │
│ │ 5K Prediction                     │   │
│ │ Time: 17:48                       │   │
│ │ Pace: 3:34/km • 5:44/mi           │   │
│ │ Range: 17:20 - 18:16 (95% CI)     │   │
│ └───────────────────────────────────┘   │
│                                         │
│ "Data predicts this. Test it."          │
└─────────────────────────────────────────┘
```

### 4. No-Model State

For users without sufficient PR data:
```
┌─────────────────────────────────────────┐
│ 🎯 Critical Speed Predictor             │
├─────────────────────────────────────────┤
│ No CS model yet.                        │
│ Log 3+ race PRs at different distances  │
│ to unlock personalized predictions.     │
│                                         │
│ [Connect Strava] or [Log a Race]        │
└─────────────────────────────────────────┘
```

## Implementation

### Backend

`apps/api/routers/analytics.py`:
- Add `GET /v1/analytics/cs-prediction` endpoint
- Calls existing `get_athlete_cs_profile()` and `predict_race_time()`
- Formats predictions for frontend

### Frontend

`apps/web/components/tools/CriticalSpeedPredictor.tsx`:
- Fetches CS profile from API
- Distance selector (standard distances + custom)
- Displays prediction results
- Handles empty states

### Feature Flag

`tools.cs_predictor` — Enable for rollout

## Consequences

### Positive
- Leverages existing CS model for user-facing value
- Personalized predictions based on real race data
- Completes Tools page with advanced analytics

### Negative
- Requires authentication and race history
- May confuse users unfamiliar with CS concept

## Test Plan

1. Unit tests for prediction endpoint
2. Unit tests for formatted output
3. Frontend: renders correctly with/without model
4. Edge cases: custom distances, no data

## Security

- Predictions only for authenticated user
- Read-only from existing PR data
- Rate limited via existing middleware
