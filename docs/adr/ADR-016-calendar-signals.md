# ADR-016: Calendar Signals - Day Badges + Week Trajectory

## Status
Accepted

## Date
2026-01-14

## Context

### The Problem

The calendar is purely historical — showing completed workouts and planned sessions. Athletes glance at calendar weekly but get no intelligence about:
- Which days had significant training signals (efficiency spikes, decay, PR pattern match)
- Weekly trajectory (on track vs. fatigue building)
- How their patterns are evolving

### The Opportunity

We have 5 implemented analytics methods that can surface day-level and week-level signals:
1. **Efficiency Factor Trending** - Was a day's efficiency notably better/worse?
2. **Pace Decay Analysis** - Did a long run or race have significant fade?
3. **TSB/ATL/CTL** - Form status each day
4. **Pre-Race State Fingerprinting** - Pre-race state match
5. **Critical Speed Model** - Effort relative to capacity

### Design Principles

- **Scannable badges**: Quick visual on day cells, not clutter
- **Week trajectory**: One sentence summary per week
- **Confidence filtering**: Only show high/moderate signals
- **Mobile-first**: Badges compact but tappable
- **Sparse tone**: Non-prescriptive

## Decision

### 1. Backend: Calendar Signals API

New endpoint: `GET /v1/calendar/signals`

Query params:
- `start_date`: ISO date (required)
- `end_date`: ISO date (required)

Response:
```json
{
  "day_signals": {
    "2026-01-14": [
      {
        "type": "efficiency_spike",
        "badge": "Eff +5%",
        "color": "emerald",
        "icon": "trending_up",
        "confidence": "high",
        "tooltip": "Efficiency 5% above your 28-day average"
      }
    ],
    "2026-01-12": [
      {
        "type": "decay_risk",
        "badge": "Fade",
        "color": "orange", 
        "icon": "trending_down",
        "confidence": "moderate",
        "tooltip": "Pace decayed 12% — more than your typical pattern"
      }
    ]
  },
  "week_trajectories": {
    "2026-W03": {
      "summary": "On track — consistency strong this week.",
      "trend": "positive",
      "details": {
        "efficiency_trend": "+3.2%",
        "tsb_zone": "race_ready",
        "quality_completion": "3/3"
      }
    },
    "2026-W02": {
      "summary": "Watch fatigue — decoupling up 6% last 3 runs.",
      "trend": "caution",
      "details": {
        "efficiency_trend": "-1.5%",
        "tsb_zone": "overreaching"
      }
    }
  }
}
```

### 2. Day Badge Types

| Type | Badge | Color | When |
|------|-------|-------|------|
| efficiency_spike | "Eff ↑" | emerald | Efficiency >5% above average |
| efficiency_drop | "Eff ↓" | orange | Efficiency >5% below average |
| decay_risk | "Fade" | orange | Pace decay >8% (worse than pattern) |
| even_pacing | "Even" | green | Negative split or <3% decay |
| pr_match | "PR ✓" | purple | Pre-state matches PR fingerprint |
| fresh_form | "Fresh" | blue | TSB in race-ready zone |
| fatigued | "Load" | yellow | TSB in overreaching zone |
| at_cs | "@CS" | blue | Effort at Critical Speed |

### 3. Week Trajectory Sentences

Generated from:
- Efficiency trend (rolling 7-day slope)
- TSB zone and direction
- Quality session completion
- Pace decay patterns

Examples:
- "On track — efficiency trending up 4% this week."
- "Watch fatigue — 3 consecutive hard days without recovery."
- "Fresh and fit — good window for quality."
- "Building load — expect fatigue to peak mid-week."

### 4. Frontend Integration

**DayCell.tsx**:
- Add optional `signals` prop (array of badges)
- Render badges at bottom of cell (max 2 shown)
- Tooltip on hover shows full insight

**WeekSummaryRow.tsx**:
- Add `trajectory` prop with summary sentence
- Display below volume/quality stats
- Color-coded by trend (positive=green, caution=yellow, neutral=gray)

### 5. Confidence Filtering

Only show badges with:
- `confidence` in [HIGH, MODERATE]
- `priority` <= 3 (most important only)

Suppress Low confidence to avoid noise.

## Implementation

### Backend

`apps/api/services/calendar_signals.py`:
- `get_calendar_signals(athlete_id, start_date, end_date, db)`
- `get_day_badges(athlete_id, date, db)` - badges for one day
- `get_week_trajectory(athlete_id, week_start, db)` - summary for week

`apps/api/routers/calendar.py`:
- `GET /v1/calendar/signals`

### Frontend

`apps/web/components/calendar/DayBadge.tsx`:
- Small badge component with icon + text

`apps/web/components/calendar/DayCell.tsx`:
- Integrate optional signals array

`apps/web/components/calendar/WeekSummaryRow.tsx`:
- Add trajectory sentence display

### Feature Flag

`signals.calendar_badges` — Enable for rollout

## Consequences

### Positive
- Calendar becomes intelligent, not just historical
- Quick visual scan shows meaningful patterns
- Week trajectory reinforces weekly review habit

### Negative
- Requires API call for signals (cached)
- More visual elements on already-busy calendar
- Must avoid overwhelming with too many badges

## Test Plan

1. Unit tests for badge generation from each method
2. Unit tests for week trajectory generation
3. Unit tests for confidence filtering
4. Integration test: API returns valid signals
5. Frontend: badges render correctly, mobile responsive

## Security

- Signals only for authenticated user's activities
- Read-only access
- Rate limited via existing middleware
