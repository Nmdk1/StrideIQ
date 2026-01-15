# ADR-015: Why This Run? Activity Attribution

## Status
Accepted

## Date
2026-01-14

## Context

### The Problem

After completing a run, athletes see metrics (pace, HR, splits, decoupling) but have no way to understand **why** the run went well or poorly. Without post-run attribution:
- Missed learning opportunities from each session
- Pattern blindness (can't see recurring success/failure factors)
- No feedback loop for pre-run behaviors

### The Opportunity

We have 5 implemented analytics methods that can attribute run quality:
1. **Pace Decay Analysis** - How did pacing compare to historical patterns?
2. **Pre-Race State Fingerprinting** - Does pre-run state match success patterns?
3. **TSB/ATL/CTL** - Was form optimal for this workout?
4. **Efficiency Factor Trending** - Was efficiency better/worse than trend?
5. **Critical Speed Model** - How did effort compare to predicted capacity?

### Design Principles

- **Post-run focus**: Show after the run is done, for learning
- **Pace Decay priority**: For race-like activities, pacing is the story
- **N=1 patterns**: Link to YOUR historical patterns, not generic advice
- **Sparse tone**: "Data hints X. Test it." — not prescriptive

## Decision

### 1. Backend: Run Attribution API

New endpoint: `GET /v1/activities/{activity_id}/attribution`

Response:
```json
{
  "activity_id": "uuid",
  "activity_name": "Morning Run",
  "attributions": [
    {
      "source": "pace_decay",
      "priority": 1,
      "confidence": "high",
      "title": "Even Pacing",
      "insight": "Decay 3% in final 5k — matches your best race patterns.",
      "data": {
        "decay_percent": 3.2,
        "pattern_match": "best_races",
        "sample_compared": 12
      }
    },
    {
      "source": "tsb",
      "priority": 2,
      "confidence": "moderate",
      "title": "Fresh Form",
      "insight": "TSB +15 suggests good freshness. Performance matched expectation.",
      "data": {
        "tsb": 15,
        "zone": "race_ready"
      }
    },
    {
      "source": "pre_state",
      "priority": 3,
      "confidence": "moderate",
      "title": "Pre-Run State Match",
      "insight": "Sleep 7.5h, HRV 48 — 80% match to your PR fingerprint.",
      "data": {
        "match_percent": 80,
        "matching_factors": ["sleep", "hrv"]
      }
    }
  ],
  "summary": "Strong execution with good pacing. Form and pre-run state aligned.",
  "generated_at": "2026-01-14T10:30:00Z"
}
```

### 2. Attribution Sources

| Source | Priority | When Shown |
|--------|----------|------------|
| Pace Decay | 1 | Race or long run with splits |
| TSB Status | 2 | Always (if sufficient data) |
| Pre-State Match | 3 | If check-in logged pre-run |
| Efficiency vs Trend | 4 | If efficiency calculable |
| Critical Speed Compare | 5 | If CS model available |

### 3. Frontend: WhyThisRun Component

Location: Activity Detail page, after metrics section.

Design:
- Collapsible section (expanded by default)
- Attribution cards with icons and confidence badges
- Summary sentence at top
- Tone: Sparse, data-driven

### 4. Confidence Thresholds

| Level | Display |
|-------|---------|
| High | Green badge, show first |
| Moderate | Yellow badge, show if space |
| Low | Gray badge, collapse by default |

## Implementation

### Backend

`apps/api/services/run_attribution.py`:
- `get_run_attribution(activity_id, athlete_id, db)` - main function
- `get_pace_decay_attribution(activity)` - pacing analysis
- `get_tsb_attribution(athlete_id, activity_date)` - form status
- `get_pre_state_attribution(athlete_id, activity_date)` - pre-run match
- `get_efficiency_attribution(activity)` - efficiency vs trend
- `get_cs_attribution(activity)` - critical speed comparison

`apps/api/routers/activities.py`:
- `GET /v1/activities/{activity_id}/attribution`

### Frontend

`apps/web/components/activities/WhyThisRun.tsx`:
- Fetches attribution on load
- Renders ranked cards
- Handles empty states gracefully

### Feature Flag

`analytics.run_attribution` — Enable for rollout

## Consequences

### Positive
- Every run becomes a learning opportunity
- Reinforces pattern awareness
- Creates feedback loop for pre-run behaviors

### Negative
- Requires multiple service calls (performance consideration)
- May show "insufficient data" for new users
- Attribution is correlational (must be clear)

## Test Plan

1. Unit tests for each attribution source
2. Unit tests for ranking and filtering
3. Integration test: API returns valid attributions
4. Frontend: cards render correctly
5. Edge cases: no splits, no check-in, new user

## Security

- Activity must belong to authenticated user
- Read-only from existing data
- Rate limited via existing middleware
