# ADR-020: Home Experience Phase 1 Enhancement

## Status
Accepted

## Date
2026-01-15

## Context

### Current State

The Home page ("Glance Layer") exists with:
- Today's workout + basic "Why this workout" context
- Yesterday's insight (activity-based)
- Week progress with trajectory sentence
- SignalsBanner for analytics signals

### The Gap

The current implementation generates "Why this workout" from **plan position only** (week number, phase). This misses the core value proposition: tying today's workout to **what actually works for this athlete**.

Similarly, yesterday's insight is generated inline rather than pulling from the `InsightAggregator` service which has richer pattern detection.

### Vision

Phase 1: Home Experience should deliver 2-second value:
- **Today**: Workout + "Why" tied to athlete's actual correlations
- **Yesterday**: One key insight from `InsightAggregator`
- **Week**: Trajectory sentence with training load context

### Tone

Sparse, irreverent, non-prescriptive:
- "Data says this. Cool."
- No "you should" or "try to"
- Let data speak for itself

### UX Principles

1. **No dead elements** — If it looks interactive (badge, button, link), it MUST be interactive. Dead elements breach user trust.
2. **No jargon badges** — Technical terms like "TSB", "CTL", "Building" mean nothing to athletes. Use plain language or don't show.
3. **Context only when actionable** — Don't add noise. Only show context when it helps the athlete make a decision.

## Decision

### 1. Enhanced "Why This Workout" Generation

Update `generate_why_context()` in `routers/home.py` to:

1. **Check for relevant correlations** from athlete's data:
   - Sleep quality → performance correlation
   - TSB zone → efficiency correlation
   - Workout type → adaptation patterns

2. **Priority order for context**:
   - High: Correlation-based (if p < 0.10, effect > 0.5)
   - Medium: Training load context (TSB zone, CTL trend)
   - Low: Plan position (current behavior)

3. **Tone examples**:
   - "Your efficiency peaks after 2 rest days. Yesterday was rest. Cool."
   - "Week 8 of 12. Threshold phase. Builds lactate clearance."
   - "TSB +15. Good window for quality work."

### 2. Yesterday Insight from InsightAggregator

Update `get_home_data()` to:

1. **Query CalendarInsight** for yesterday's date
2. **Fallback** to `generate_yesterday_insight()` if no stored insight
3. **Priority**: Show highest-priority insight from aggregator

### 3. Week Trajectory with Load Context

Enhance `generate_trajectory_sentence()` to include:

1. **TSB context** when available (from training_load service)
2. **Efficiency trend** when statistically significant
3. **Simple fallback** when data insufficient

### 4. API Response Enhancement

Add optional fields to `HomeResponse`:

```python
class TodayWorkout(BaseModel):
    # ... existing fields ...
    why_context: Optional[str] = None
    why_source: Optional[str] = None  # "correlation" | "load" | "plan"
    correlation_data: Optional[dict] = None  # For frontend expansion

class WeekProgress(BaseModel):
    # ... existing fields ...
    tsb_context: Optional[str] = None  # "Fresh" | "Building" | "Fatigued"
    load_trend: Optional[str] = None  # "up" | "stable" | "down"
```

## Implementation

### Backend Changes

1. `apps/api/routers/home.py`:
   - Add `get_correlation_context()` helper
   - Update `generate_why_context()` to check correlations first
   - Update `get_home_data()` to query InsightAggregator

2. `apps/api/services/home_signals.py`:
   - Add `get_correlation_for_workout()` function
   - Returns relevant correlation if available

### Frontend Changes

None required for Phase 1 — frontend already renders `why_context` correctly.

### Feature Flag

`home.enhanced_context` — Enable for gradual rollout

## Test Plan

### Unit Tests

1. `test_get_correlation_context` — Returns correlation when available
2. `test_why_context_priority` — Correlation > Load > Plan
3. `test_yesterday_from_aggregator` — Pulls from CalendarInsight
4. `test_trajectory_with_tsb` — Includes TSB context

### Integration Tests

1. API returns enhanced why_context for user with correlations
2. API falls back gracefully when no correlations exist
3. Yesterday insight pulls from aggregator when available

## Security

- No new user inputs
- Read-only from existing data
- No PII in logs

## Consequences

### Positive
- Home page delivers correlation-based value (the moat)
- Athlete sees what actually works for them
- Builds trust through personalization

### Negative
- Slightly increased query complexity
- Need correlation data to show enhanced context
- Cold-start users see simpler context

### Mitigations
- Graceful fallback to plan-based context
- Cache correlation lookups
- Clear messaging for new users
