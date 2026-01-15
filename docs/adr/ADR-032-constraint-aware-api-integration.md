# ADR-032: Constraint-Aware Plan API Integration

**Status:** Accepted (Implemented)  
**Date:** 2026-01-15  
**Author:** Engineering Team  
**Depends On:** ADR-030 (Fitness Bank), ADR-031 (Constraint-Aware Planning)  
**Implementation:**  
- Backend: `apps/api/routers/plan_generation.py` (`/v2/plans/constraint-aware`)  
- Frontend: `apps/web/app/plans/create/page.tsx`  
- Service: `apps/web/lib/api/services/plans.ts`

---

## Context

ADR-030 and ADR-031 define the Fitness Bank Framework and Constraint-Aware Planning layer. This ADR defines the API contract and frontend integration for exposing this functionality to athletes.

Key requirements:
1. **Elite-tier gating** — Only subscribers get access
2. **Rate limiting** — Prevent abuse (5 plans/day)
3. **Tune-up race support** — Multiple races in single plan
4. **Database persistence** — Plans saved as TrainingPlan + PlannedWorkout
5. **Calendar integration** — Apply to calendar immediately

---

## Decision

### API Endpoint

```
POST /v2/plans/constraint-aware
GET  /v2/plans/constraint-aware/preview
```

### Request Schema

```typescript
interface ConstraintAwarePlanRequest {
  race_date: string;              // ISO date: "2026-03-15"
  race_distance: string;          // "5k", "10k", "10_mile", "half_marathon", "marathon"
  goal_time_seconds?: number;     // Optional goal time
  tune_up_races?: TuneUpRace[];   // Optional secondary races
  race_name?: string;             // e.g., "Boston Marathon"
}

interface TuneUpRace {
  date: string;                   // Must be before race_date
  distance: string;               // "5k", "10k", "10_mile", "half_marathon"
  name?: string;                  // Optional race name
  purpose: "threshold" | "sharpening" | "tune_up" | "fitness_check";
}
```

### Response Schema

```typescript
interface ConstraintAwarePlanResponse {
  success: boolean;
  plan_id: string;                // UUID for saved plan
  
  race: {
    date: string;
    distance: string;
    name?: string;
  };
  
  fitness_bank: {
    peak: {
      weekly_miles: number;       // Proven peak capability
      monthly_miles: number;
      long_run: number;
      mp_long_run: number;
      ctl: number;
    };
    current: {
      weekly_miles: number;
      ctl: number;
      atl: number;
    };
    best_vdot: number;
    races: RacePerformance[];
    tau1: number;
    tau2: number;
    experience: string;           // "beginner" | "intermediate" | "experienced" | "elite"
    constraint: {
      type: string;               // "none" | "injury" | "time" | "detrained"
      details: string | null;
      returning: boolean;
    };
  };
  
  model: {
    confidence: string;           // "high" | "medium" | "low"
    tau1: number;
    tau2: number;
    insights: string[];           // Personal insights from τ values
  };
  
  prediction: {
    time: string;                 // "3:01:09"
    confidence_interval: string;  // "±5-8 min"
  };
  
  personalization: {
    notes: string[];              // Counter-conventional insights
    tune_up_races: TuneUpRace[];
  };
  
  summary: {
    total_weeks: number;
    total_miles: number;
    peak_miles: number;
  };
  
  weeks: WeekPlan[];
  generated_at: string;
}

interface WeekPlan {
  week: number;
  theme: string;                  // "rebuild_easy", "build_t", "peak", etc.
  start_date: string;
  days: DayPlan[];
  total_miles: number;
  notes: string[];
}

interface DayPlan {
  day_of_week: number;            // 0=Mon, 6=Sun
  workout_type: string;           // "easy", "threshold", "long_mp", "race", etc.
  name: string;                   // "2x4mi @ T"
  description: string;            // Full description with paces
  target_miles: number;
  intensity: string;              // "easy", "moderate", "hard", "race"
  paces: Record<string, string>;  // { "threshold": "6:25", "easy": "8:04" }
  notes: string[];
  tss: number;                    // Training stress score
}
```

---

## Access Control

### Tier Gating

```python
# Backend enforcement
if athlete.subscription_tier not in ("elite", "premium", "guided"):
    raise HTTPException(403, "Constraint-aware plans require Elite subscription")
```

### Feature Flag

```python
flags = FeatureFlagService(db)
if not flags.is_enabled("plan.model_driven_generation", athlete):
    raise HTTPException(403, "Feature not enabled")
```

### Rate Limiting

```python
MODEL_PLAN_RATE_LIMIT = 5  # 5 per day per athlete

if not _check_rate_limit(str(athlete.id)):
    raise HTTPException(429, "Rate limit exceeded")
```

---

## Database Persistence

### TrainingPlan Fields

```python
db_plan = TrainingPlan(
    athlete_id=athlete.id,
    name="Constraint-Aware Marathon Plan",
    status="active",
    goal_race_date=plan.race_date,
    goal_race_distance_m=42195,
    plan_start_date=plan.weeks[0].start_date,
    plan_end_date=plan.race_date,
    total_weeks=plan.total_weeks,
    baseline_vdot=fb.best_vdot,
    baseline_weekly_volume_km=fb.peak_weekly_miles * 1.609,
    plan_type="marathon",
    generation_method="constraint_aware",  # NEW: Distinguishes from template
)
```

### PlannedWorkout Fields

```python
db_workout = PlannedWorkout(
    plan_id=db_plan.id,
    athlete_id=athlete.id,
    scheduled_date=workout_date,
    week_number=week.week_number,
    day_of_week=day.day_of_week,
    workout_type=day.workout_type,
    title=day.name,                        # "2x4mi @ T"
    description=day.description,           # Full with paces
    phase=phase,                           # "build", "peak", "taper", "race"
    target_distance_km=day.target_miles * 1.609,
    coach_notes=f"Paces: {paces} | {notes}",  # Personalized
)
```

---

## Frontend Integration

### Plan Creation Flow

```
1. /plans/create → Select "Fitness Bank Plan"
2. Enter race date, distance, name
3. Add tune-up races (optional)
4. Generate → Preview shows:
   - Fitness Bank (peak 71mpw, 22mi long, 18@MP)
   - Prediction (3:01:09 ±5min)
   - Model (τ1=25d, τ2=18d)
   - Week themes
   - Personalized insights
5. Apply to Calendar → Plan active
```

### UI Components

```tsx
// Plan type selection
<button onClick={() => setFormData({ planType: 'constraint-aware' })}>
  🏦 Fitness Bank Plan
  <span className="badge">Elite</span>
  <span className="badge">Recommended</span>
</button>

// Fitness Bank display
<div className="fitness-bank">
  <div className="metric">{peak.weekly_miles} mpw peak</div>
  <div className="metric">{peak.long_run}mi longest</div>
  <div className="metric">{peak.mp_long_run}@MP proven</div>
</div>

// Constraint warning
{constraint.returning && (
  <div className="warning">
    ⚠️ Detected: {constraint.type} - plan protects first weeks
  </div>
)}
```

---

## Validation

### Input Validation

| Field | Rule |
|-------|------|
| race_date | Must be 4-52 weeks in future |
| race_distance | Must be valid enum |
| tune_up_races[].date | Must be before race_date |
| goal_time_seconds | Must be ≥ 600 (10 minutes) |

### Output Validation

| Check | Rule |
|-------|------|
| Peak week | Within 10% of proven peak |
| MP long run | ≤ proven peak MP miles |
| Race week at end | themes[-1] == "race" |
| Theme alternation | No consecutive T/MP |

---

## Error Handling

```python
try:
    plan = generate_constraint_aware_plan(...)
except InsufficientDataError:
    raise HTTPException(400, "Need at least 90 days of training history")
except NoRaceDataError:
    # Fall back to lower confidence prediction
    plan = generate_with_defaults(...)
except Exception as e:
    logger.error(f"Plan generation failed: {e}")
    raise HTTPException(500, f"Plan generation failed: {str(e)}")
```

---

## Testing Requirements

### Backend Tests

| Test | File | Coverage |
|------|------|----------|
| Elite tier check | `test_constraint_aware_endpoint.py` | Access control |
| Rate limiting | `test_constraint_aware_endpoint.py` | Rate limit |
| Input validation | `test_constraint_aware_endpoint.py` | Edge cases |
| Plan save | `test_constraint_aware_endpoint.py` | DB persistence |
| Tune-up races | `test_constraint_aware_endpoint.py` | Multi-race |

### Frontend Tests

| Test | File | Coverage |
|------|------|----------|
| Plan type toggle | `plans-create.test.tsx` | UI state |
| Tune-up add/remove | `plans-create.test.tsx` | Form handling |
| Preview display | `plans-create.test.tsx` | Data rendering |
| Apply to calendar | `plans-create.test.tsx` | Integration |

### Integration Tests

| Test | File | Coverage |
|------|------|----------|
| Full flow | `test_full_integration.py` | End-to-end |
| Real data | `test_constraint_aware_real_data.py` | Validation |

---

## Security Review

### Threat Model

| Threat | Mitigation |
|--------|------------|
| Unauthorized access | Elite tier check + JWT validation |
| Rate limit bypass | Per-athlete tracking with 24h window |
| SQL injection | SQLAlchemy ORM parameterized queries |
| Data leakage | Only return own athlete data |
| Excessive computation | 10-minute timeout on generation |

### Audit Trail

```python
logger.info(f"Constraint-aware plan generated for {athlete.id} in {gen_time:.2f}s, saved as {saved_plan.id}")
```

---

## Monitoring

### Metrics

| Metric | Purpose |
|--------|---------|
| `plan.constraint_aware.generated` | Success count |
| `plan.constraint_aware.failed` | Failure count |
| `plan.constraint_aware.latency_ms` | Generation time |
| `plan.constraint_aware.rate_limited` | Rate limit hits |

### Alerts

- Generation time > 5s: P2
- Failure rate > 5%: P1
- Rate limit > 10 athletes/hour: Review abuse

---

## Rollout Plan

1. **Feature flag**: `plan.model_driven_generation` (existing)
2. **Initial**: Elite subscribers only
3. **Monitor**: 1 week of usage data
4. **Expand**: Premium tier if stable
5. **Promote**: Marketing for Fitness Bank differentiation

---

*API contract for world-class N=1 training plans.*
