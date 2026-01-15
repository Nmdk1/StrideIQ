# ADR-026: A/B Testing Model vs Template Plans

**Status:** ACCEPTED  
**Date:** 2026-01-15  
**Author:** AI Assistant  
**Reviewers:** Michael Shaffer

---

## Context

With the Individual Performance Model (ADR-022) ready for beta, we need to validate that model-driven plans outperform template-based plans before full rollout.

## Decision

**Implement A/B testing infrastructure for plan generation.**

### Split Strategy

| Approach | Decision |
|----------|----------|
| User-based split | Yes (consistent experience per user) |
| Random per request | No (confusing for user) |
| Time-based | No (external factors confound) |

**Implementation:** `athlete_id % 2` for 50/50 split among elite users.

### Metrics Tracked

| Metric | Source | What It Tells Us |
|--------|--------|------------------|
| Plan adoption rate | DB: plans generated | User trust |
| Plan completion rate | DB: workouts completed | User engagement |
| Prediction accuracy | Races after plan | Model validity |
| User satisfaction | Feedback endpoint | Subjective quality |

### Validation Approach

1. **Simulated A/B on historical data** (Step 1 validation)
   - Use developer + figshare proxies
   - Generate both plan types
   - Compare predicted vs actual outcomes
   
2. **Live A/B for beta users** (Step 5 rollout)
   - 50/50 split for elite tier
   - Track real outcomes over 12+ weeks
   - Decision point: Model must beat template on 2+ metrics

## Trade-offs

| Trade-off | Decision |
|-----------|----------|
| User confusion | Mitigate with clear labeling ("Personalized" vs "Standard") |
| Sample size | Beta users only—sufficient for signal |
| Metric lag | Plan completion takes 12+ weeks—start early |

## Implementation

### A/B Test Service

`apps/api/services/ab_test_plans.py`

```python
class PlanABTest:
    def get_variant(self, athlete_id: UUID) -> str:
        """Return 'model' or 'template' based on split."""
        
    def generate_with_tracking(self, athlete_id, race_date, distance) -> Plan:
        """Generate plan and track variant assignment."""
        
    def track_outcome(self, plan_id, outcome_type, value):
        """Track outcome for later analysis."""
        
    def get_report(self) -> ABTestReport:
        """Generate comparison report."""
```

### Database Schema

```sql
CREATE TABLE ab_test_assignment (
    id UUID PRIMARY KEY,
    athlete_id UUID NOT NULL,
    test_name TEXT NOT NULL,  -- 'model_vs_template_2026Q1'
    variant TEXT NOT NULL,    -- 'model' or 'template'
    assigned_at TIMESTAMP WITH TIME ZONE NOT NULL,
    plan_id UUID,             -- If plan generated
    UNIQUE(athlete_id, test_name)
);

CREATE TABLE ab_test_outcome (
    id UUID PRIMARY KEY,
    assignment_id UUID REFERENCES ab_test_assignment(id),
    outcome_type TEXT NOT NULL,  -- 'completion_rate', 'prediction_error', 'satisfaction'
    value NUMERIC,
    recorded_at TIMESTAMP WITH TIME ZONE NOT NULL
);
```

## Security

- Anonymized metrics only—no PII in reports
- Opt-out flag: `athlete.ab_test_opt_out` 
- User can request their variant info

## Feature Flag

```python
"ab.model_vs_template": {
    "enabled": False,  # Start disabled
    "rollout_percentage": 10,  # Ramp up gradually
    "description": "A/B test model-driven vs template plans"
}
```

## Test Plan

### Unit Tests
- Variant assignment consistency
- Split distribution (within 5% of 50/50)
- Outcome tracking

### Integration Tests
- Full flow with tracking
- Report generation

## Success Criteria

For model-driven to "win":
1. Prediction MAE < template MAE by 10%+
2. Completion rate >= template
3. Satisfaction >= template

If model loses, roll back to template default.

---

*ADR-026: A/B Testing Model vs Template Plans*
