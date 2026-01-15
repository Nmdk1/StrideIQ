# ADR-013: Home Glance Signals Integration

## Status
Accepted

## Date
2026-01-14

## Context

### The Problem

Five analytics methods are now implemented in the backend:
1. Efficiency Factor Trending (ADR-008)
2. Pre-Race State Fingerprinting (ADR-009)
3. TSB/ATL/CTL Training Stress Balance (ADR-010)
4. Critical Speed + D' Model (ADR-011)
5. Pace Decay Analysis (ADR-012)

These provide valuable insights but are not yet visible to users.

### The Opportunity

The Home page is the "Glance Layer" — designed for 2-second value. Users should see:
- Their current training status at a glance
- High-confidence signals without digging
- Actionable insights without noise

### Design Principles

- **Only show high-confidence signals** (p < 0.05, sample > 10, R² > 0.95)
- **Tone: Sparse/irreverent** — no prescriptiveness
- **N=1 philosophy** — athlete's data first, not generic advice
- **No clutter** — max 3-4 signals visible at once

## Decision

### 1. Backend: Signals Aggregation API

New endpoint: `GET /v1/analytics/home-signals`

Returns prioritized, filtered signals from all 5 methods:

```json
{
  "signals": [
    {
      "id": "efficiency_trend",
      "type": "efficiency",
      "priority": 1,
      "confidence": "high",
      "icon": "trending_up",
      "color": "emerald",
      "title": "Efficiency up 4.2%",
      "subtitle": "Last 4 weeks trend",
      "detail": "p=0.02, R²=0.89"
    },
    {
      "id": "tsb_status",
      "type": "tsb",
      "priority": 2,
      "confidence": "high",
      "icon": "battery_full",
      "color": "green",
      "title": "Fresh but fit",
      "subtitle": "Good race window (TSB +18)",
      "detail": null
    }
  ],
  "suppressed_count": 2,
  "last_updated": "2026-01-14T10:30:00Z"
}
```

### 2. Signal Priority Rules

| Priority | Signal Type | Threshold |
|----------|-------------|-----------|
| 1 | TSB Race Ready | TSB 15-25, CTL > 30 |
| 2 | Pre-Race Fingerprint Match | >80% match to PR pattern |
| 3 | Efficiency Trending | p < 0.05, change > 2% |
| 4 | Critical Speed Update | R² > 0.95, new PR included |
| 5 | Pace Decay Pattern | Confidence high, deviation from norm |

### 3. Frontend: Signals Banner Component

Location: Between Header and Today section on Home page.

Design:
- Horizontal scrollable cards on mobile
- Grid on desktop (2 columns)
- Subtle animation on load (fade-in)
- Tap to see detail (future: modal with attribution)

### 4. Suppression Rules

Don't show signal if:
- Confidence < moderate
- Sample size < 5 for statistical methods
- Data older than 30 days
- Already shown in last 24 hours (staleness check)

## Implementation

### Backend

`apps/api/services/home_signals.py`:
- `aggregate_signals(athlete_id, db) -> List[Signal]`
- `filter_by_confidence(signals) -> List[Signal]`
- `prioritize_signals(signals) -> List[Signal]`

`apps/api/routers/analytics.py`:
- `GET /v1/analytics/home-signals`

### Frontend

`apps/web/components/home/SignalsBanner.tsx`:
- Fetches from API
- Renders signal cards
- Handles empty state gracefully

### Feature Flag

`signals.home_banner` — Enable for rollout

## Consequences

### Positive
- High-value insights surface without user effort
- Motivates engagement with analytics
- Demonstrates N=1 value proposition

### Negative
- Requires maintaining signal priority logic
- Must handle cold-start (new users with no data)
- API adds latency to home page load

## Test Plan

1. Unit tests for signal aggregation
2. Unit tests for filtering/prioritization
3. Integration test: API returns valid signals
4. Frontend: renders signals correctly
5. Edge cases: no signals, low confidence, stale data

## Security

- No new user inputs
- Signals are read-only from existing data
- Rate limited via existing middleware
