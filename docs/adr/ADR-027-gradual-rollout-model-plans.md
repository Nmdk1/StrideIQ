# ADR-027: Gradual Rollout of Model-Driven Plans

**Status:** ACCEPTED  
**Date:** 2026-01-15  
**Author:** AI Assistant  
**Reviewers:** Michael Shaffer

---

## Context

The Individual Performance Model (ADR-022) has been validated (ADR-023), cached (ADR-024), exposed via API (ADR-025), and A/B tested (ADR-026). It's time for production rollout.

## Decision

**Gradual rollout to elite tier users with monitoring and rollback capability.**

### Rollout Strategy

| Phase | Percentage | Duration | Criteria to Advance |
|-------|------------|----------|---------------------|
| Beta | 100% elite | Immediate | Validation passed |
| Monitor | 100% elite | 2 weeks | <5% error rate |
| Expand | All subscribers | 2 weeks | Positive A/B results |
| GA | All users | Ongoing | Stable metrics |

### Feature Flag Configuration

```python
"plan.model_driven_generation": {
    "enabled": True,
    "requires_tier": "elite",
    "rollout_percentage": 100,
    "description": "Individual performance model for personalized plan generation"
}
```

### Monitoring

| Metric | Source | Alert Threshold |
|--------|--------|-----------------|
| Generation success rate | Logs | <95% |
| Generation time (p95) | Logs | >10s |
| API error rate | Logs | >5% |
| User satisfaction | Feedback | <3.5/5 |

### Rollback Plan

If >5% errors in 24h window:
1. Set `rollout_percentage: 0`
2. Existing plans unaffected
3. New requests fall back to template
4. Investigate, fix, re-validate

## Implementation

### Feature Flag Update

Update `seed_feature_flags.py`:
```python
{
    "key": "plan.model_driven_generation",
    "enabled": True,  # Enable for beta
    "requires_tier": "elite",
    "rollout_percentage": 100,  # Full rollout to elite
}
```

### Logging

Add structured logging to endpoint:
```python
logger.info("model_plan_generated", extra={
    "athlete_id": str(athlete.id),
    "race_distance": request.race_distance,
    "generation_time_ms": gen_time_ms,
    "model_confidence": plan.model_confidence,
    "tau1": plan.tau1,
    "tau2": plan.tau2
})
```

### Settings UI (Optional)

Add opt-in toggle in `/settings`:
- "Use personalized plan generation"
- Default: On for elite
- Allows user to revert to template

## Security

### Tier Verification

Middleware check:
```python
if athlete.subscription_tier not in ("elite", "premium", "guided"):
    raise HTTPException(403, "Requires elite subscription")
```

### Rate Limiting

5 requests/day/user to prevent abuse.

### Input Validation

- Race date: Future, within 52 weeks
- Distance: Enum validation
- Goal time: Reasonable range (if provided)

## Test Plan

### Integration Tests

1. Elite user can access endpoint
2. Basic user gets 403
3. Rate limit enforced
4. Invalid inputs rejected

### E2E Tests (Manual)

1. Generate plan via UI
2. View predictions
3. Complete plan generation flow

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Adoption | 50% of elite users try within 30 days | DB query |
| Completion | 80% of started plans have >50% workouts completed | DB query |
| Satisfaction | 4.0+ average rating | Feedback |
| Prediction accuracy | MAE <5% for users with calibrated models | Comparison |

---

*ADR-027: Gradual Rollout of Model-Driven Plans*
