# ADR-025: Model-Driven Plan API Endpoint

**Status:** ACCEPTED  
**Date:** 2026-01-15  
**Author:** AI Assistant  
**Reviewers:** Michael Shaffer

---

## Context

The Individual Performance Model (ADR-022) needs a public API endpoint for frontend integration. This enables:

1. Elite subscribers to generate personalized plans
2. UI to display predictions and personalization notes
3. Future mobile app integration

## Decision

**Endpoint:** `POST /v1/plans/model-driven`

### Request

```json
{
    "race_date": "2026-05-01",
    "race_distance": "marathon",
    "goal_time_seconds": 12600,  // Optional
    "force_recalibrate": false    // Optional
}
```

### Response

```json
{
    "plan_id": "uuid",
    "race": {
        "date": "2026-05-01",
        "distance": "marathon",
        "distance_m": 42195
    },
    "prediction": {
        "time_seconds": 12480,
        "time_formatted": "3:28:00",
        "confidence": "moderate",
        "confidence_interval": "±3:00"
    },
    "model": {
        "confidence": "moderate",
        "tau1": 38.2,
        "tau2": 6.8,
        "insights": [
            "You adapt faster than average (τ1=38 vs typical 42)"
        ]
    },
    "personalization": {
        "taper_days": 12,
        "notes": [
            "Your τ2=6.8 suggests faster recovery—add sharpening workouts in taper"
        ]
    },
    "weeks": [...],  // Full plan structure
    "generated_at": "2026-01-15T10:30:00Z"
}
```

## Trade-offs

| Trade-off | Decision |
|-----------|----------|
| Sync vs async | Sync—generation takes <5s with caching |
| Full plan vs summary | Full plan—frontend needs complete structure |
| Model details exposed | Yes—transparency builds trust |

## Security

### Authentication
- JWT required
- User must match athlete_id in token

### Authorization
- Elite tier required (feature flag: `api.model_driven_plans`)
- IDOR check: Can only generate plans for self

### Input Validation
- `race_date`: ISO date, must be future (within 52 weeks)
- `race_distance`: Enum (5k, 10k, half_marathon, marathon)
- `goal_time_seconds`: Optional, positive integer, reasonable range

### Rate Limiting
- 5 requests per day per user
- Prevents abuse of compute-intensive generation

## Implementation

### Endpoint Location
`apps/api/routers/plans.py`

### Flow
1. Validate JWT, extract athlete_id
2. Check feature flag (`api.model_driven_plans`)
3. Check rate limit
4. Validate input
5. Fetch/calibrate model (via cache)
6. Calculate trajectory, taper, prediction
7. Generate plan
8. Return response

### Error Responses

| Code | Reason |
|------|--------|
| 400 | Invalid input (bad date, unknown distance) |
| 401 | Missing/invalid JWT |
| 403 | Not elite tier / rate limit exceeded |
| 422 | Insufficient data for model |
| 500 | Generation failed |

## Feature Flag

```python
"api.model_driven_plans": {
    "enabled": False,  # Default disabled
    "requires_tier": "elite",
    "description": "Model-driven plan generation endpoint"
}
```

## Test Plan

### Unit Tests
- Input validation (dates, distances)
- Auth/tier checks

### Integration Tests
- Full generation flow (mock DB)
- Rate limit enforcement

### E2E Tests (manual)
- Curl test with valid JWT
- UI integration

---

*ADR-025: Model-Driven Plan API Endpoint*
