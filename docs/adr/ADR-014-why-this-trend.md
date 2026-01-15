# ADR-014: Why This Trend? Attribution Integration

## Status
Accepted

## Date
2026-01-14

## Context

### The Problem

Users see trends on the Analytics page (efficiency improving, load increasing, etc.) but have no way to understand **why** the trend is happening. Without attribution:
- Users don't know what behaviors to continue
- Users can't identify what's driving improvement or decline
- Insights feel like "magic" rather than actionable intelligence

### The Opportunity

We have 5 implemented analytics methods that can contribute to attribution:
1. **Efficiency Factor Trending** - Is efficiency changing? How significant?
2. **Pre-Race State Fingerprinting** - Are current biometrics matching patterns?
3. **TSB/ATL/CTL Training Load** - Is load appropriate? Fresh or fatigued?
4. **Critical Speed Model** - Has aerobic capacity shifted?
5. **Pace Decay Analysis** - Is pacing improving or declining?

We also have correlation data linking inputs (sleep, nutrition, BMI, mileage, consistency) to outputs.

### Design Principles

- **N=1 First**: Attribution uses YOUR data patterns, not generic advice
- **Ranked by Contribution**: Show what matters most, not everything
- **Confidence Badges**: Be honest about certainty
- **Sparse Tone**: "Data hints X drove 35% of gains. Test it." — not prescriptive

## Decision

### 1. Backend: Trend Attribution API

New endpoint: `GET /v1/analytics/trend-attribution`

Query parameters:
- `metric`: Which metric to explain (efficiency, load, speed)
- `days`: Time window (default 28)

Response:
```json
{
  "trend_summary": {
    "metric": "efficiency",
    "direction": "improving",
    "change_percent": 4.2,
    "p_value": 0.02,
    "confidence": "high"
  },
  "attributions": [
    {
      "factor": "sleep_quality",
      "label": "Sleep Quality (1-day lag)",
      "contribution_pct": 35,
      "correlation": 0.72,
      "confidence": "moderate",
      "insight": "Higher sleep scores precede your best efficiency days.",
      "sample_size": 24
    },
    {
      "factor": "consistency",
      "label": "Training Consistency",
      "contribution_pct": 28,
      "correlation": 0.65,
      "confidence": "moderate",
      "insight": "Weeks with 4+ runs show better efficiency trends.",
      "sample_size": 18
    }
  ],
  "method_contributions": {
    "efficiency_trending": true,
    "tsb_analysis": true,
    "critical_speed": false,
    "fingerprinting": false,
    "pace_decay": true
  },
  "generated_at": "2026-01-14T10:30:00Z"
}
```

### 2. Attribution Factors

| Factor | Source | Lag Considered |
|--------|--------|----------------|
| sleep_quality | Daily check-in | 0-2 days |
| sleep_duration | Daily check-in | 0-2 days |
| hrv | Daily check-in | 0-1 days |
| resting_hr | Daily check-in | 0-1 days |
| stress | Daily check-in | 0-1 days |
| nutrition_quality | Nutrition entries | 0-1 days |
| hydration | Nutrition entries | 0 days |
| body_weight | Body composition | 7 days |
| bmi | Body composition | 7 days |
| weekly_mileage | Activities | 7 days |
| consistency | Activities | 7 days |
| long_run_pct | Activities | 14 days |
| easy_run_pct | Activities | 14 days |
| workout_intensity | Activities | 7 days |
| tsb | Training load | 0 days |
| atl | Training load | 0 days |
| ctl | Training load | 0 days |

### 3. Frontend: WhyThisTrend Component

Location: Analytics page, as a button on trend charts.

On click:
1. Fetch attribution data
2. Show modal with ranked attribution cards
3. Each card shows: factor, contribution %, confidence badge, insight

Design:
- Button: "Why This Trend?" with info icon
- Modal: Clean list of ranked attributions
- Cards: Colored by confidence (green=high, yellow=moderate)
- Tone: Sparse, non-prescriptive

### 4. Confidence Thresholds

| Level | Criteria |
|-------|----------|
| High | correlation > 0.7, sample > 20, p < 0.05 |
| Moderate | correlation > 0.4, sample > 10, p < 0.10 |
| Low | correlation > 0.2, sample > 5 |
| Insufficient | Otherwise (not shown) |

## Implementation

### Backend

`apps/api/services/trend_attribution.py`:
- `get_trend_summary(athlete_id, metric, days)` - summarize trend
- `calculate_factor_contributions(athlete_id, metric, days)` - rank factors
- `generate_attribution_insight(factor, correlation, direction)` - sparse text

`apps/api/routers/analytics.py`:
- `GET /v1/analytics/trend-attribution`

### Frontend

`apps/web/components/analytics/WhyThisTrend.tsx`:
- Button component
- Modal with attribution cards
- Responsive (full screen on mobile)

### Feature Flag

`analytics.trend_attribution` — Enable for rollout

## Consequences

### Positive
- Users understand what's driving their trends
- Reinforces N=1 value proposition
- Creates feedback loop for behavior change

### Negative
- Attribution is correlational, not causal (must be clear about this)
- Requires sufficient data for meaningful attribution
- Adds complexity to Analytics page

## Test Plan

1. Unit tests for attribution calculation
2. Unit tests for ranking and filtering
3. Integration test: API returns valid attributions
4. Frontend: modal opens, cards render correctly
5. Edge cases: no data, low confidence, single factor

## Security

- No new user inputs
- Read-only from existing data
- Rate limited via existing middleware
