# ADR-008: Training Pace Calculator Integration

## Status
Accepted

## Date
2026-01-11

## Context

Athletes need personalized training paces calculated from their race performance. The Training Pace Calculator (based on RPI methodology) exists but is not properly integrated into the plan generation workflow:

1. **Standard tier**: Effort descriptions only (no paces) - working as designed
2. **Semi-custom tier**: Should use user-entered race time - broken (format mismatch)
3. **Custom tier (Elite)**: Should use user input OR Strava data - broken (ignores user input)

The athlete should be able to:
- Enter a recent race time for accurate paces
- Enter an aspirational race time for goal-based training
- Fall back to Strava data if no manual entry

## Decision

### Pace Source Priority (Custom/Elite tier)

1. **User-provided race time** (highest priority) - from plan creation form
2. **Strava race activities** - races tagged in Strava within last 6 months
3. **Strava training estimate** - conservative estimate from best training runs (RPI * 0.95)

### Pace Display Format

All pace prescriptions will include both the pace AND effort context:

| Workout Type | Format |
|--------------|--------|
| Easy/Recovery | `9:30-10:00/mi (conversational, relaxed)` |
| Long Run | `9:30-10:00/mi (easy, sustainable)` |
| Marathon Pace | `8:15/mi (goal race pace)` |
| Threshold/Tempo | `7:30/mi (comfortably hard)` |
| Interval | `6:45/mi (hard effort)` |
| Strides/Reps | `6:00/mi (quick, controlled)` |

### Data Flow

```
Frontend Form (H:MM:SS)
    ↓ parseTimeToSeconds()
Frontend Service (seconds)
    ↓ POST /v2/plans/custom
API Endpoint
    ↓ recent_race_time_seconds
PlanGenerator.generate_custom()
    ↓ (user input OR Strava fallback)
PaceEngine.calculate_from_race()
    ↓ TrainingPaces dataclass
_generate_workouts()
    ↓ paces.get_pace_description()
PlannedWorkout.coach_notes
```

### Tier Behavior

| Tier | Pace Source | Cost | Entitlement |
|------|-------------|------|-------------|
| Standard | None (effort only) | Free | All users |
| Semi-Custom | User input required | $5 one-time | Payment or paid tier |
| Custom | User input or Strava | Subscription | Elite/Pro tier |

## Constraints

1. **Time format conversion**: Frontend sends "H:MM:SS", API expects integer seconds
2. **RPI calculation requires distance + time**: Both must be provided for pace calculation
3. **Strava race detection**: Relies on `workout_type == 'Race'` tag from Strava
4. **Backward compatibility**: Existing plans retain their current coach_notes

## Security Considerations

1. **Input validation**: Race time seconds bounded (600-86400 seconds = 10min to 24hr)
2. **IDOR protection**: Generator receives athlete_id from auth, not request
3. **Rate limiting**: Plan creation already rate-limited per-user

## Testing Requirements

### Unit Tests
- `parseTimeToSeconds("4:30:15")` → `16215`
- `parseTimeToSeconds("30:00")` → `1800`
- `PaceEngine.calculate_from_race("5k", 1200)` → valid TrainingPaces
- `TrainingPaces.get_pace_description("easy")` → includes effort context

### Integration Tests
- Standard plan: no paces, effort descriptions only
- Semi-custom plan with race time: personalized paces
- Custom plan with user race time: uses user input
- Custom plan without race time: falls back to Strava

## Consequences

### Positive
- Athletes get accurate, personalized training paces
- Elite users can use aspirational race times for goal-based training
- Consistent pace + effort format improves workout clarity
- System degrades gracefully (Strava fallback, effort-only fallback)

### Negative
- Increased complexity in plan generation flow
- Frontend must handle time format conversion
- Migration: existing plans won't retroactively get new format

### Mitigation
- Time conversion utility is simple and well-tested
- Format changes only affect newly generated plans
- Clear error messages when pace calculation fails
