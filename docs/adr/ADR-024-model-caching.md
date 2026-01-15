# ADR-024: Individual Performance Model Caching

**Status:** ACCEPTED  
**Date:** 2026-01-15  
**Author:** AI Assistant  
**Reviewers:** Michael Shaffer

---

## Context

Model calibration (ADR-022) involves grid search optimization that takes 1-3 seconds. Running this on every plan generation or prediction request would degrade UX.

## Decision

**Cache calibrated model parameters in database** with intelligent invalidation.

### Storage: PostgreSQL (not Redis)

| Factor | PostgreSQL | Redis |
|--------|------------|-------|
| Persistence | Durable | Volatile |
| Schema | Structured (jsonb) | Key-value |
| Queries | Rich (by user, age) | Simple |
| Infrastructure | Already have | Would add |

**Decision:** PostgreSQL with `individual_models` table.

### Cache Key Strategy

- Primary: `user_id`
- Invalidation trigger: New activity sync OR manual recalibrate
- TTL: 7 days (recalibrate weekly even without new data for freshness)

### Expiration Policy

| Condition | Action |
|-----------|--------|
| Cache age < 7 days | Return cached |
| Cache age >= 7 days | Recalibrate |
| New race added | Invalidate + recalibrate |
| Manual recalibrate | Force recalibrate |
| >10 new activities | Invalidate |

## Implementation

### Database Schema

```sql
CREATE TABLE individual_model (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    athlete_id UUID NOT NULL UNIQUE REFERENCES athlete(id) ON DELETE CASCADE,
    
    -- Calibrated parameters
    tau1 NUMERIC NOT NULL,
    tau2 NUMERIC NOT NULL,
    k1 NUMERIC NOT NULL,
    k2 NUMERIC NOT NULL,
    p0 NUMERIC NOT NULL,
    
    -- Fit quality
    fit_error NUMERIC,
    r_squared NUMERIC,
    n_performance_markers INTEGER,
    n_training_days INTEGER,
    
    -- Confidence
    confidence TEXT NOT NULL,  -- 'high', 'moderate', 'low', 'uncalibrated'
    confidence_notes JSONB DEFAULT '[]',
    
    -- Cache metadata
    input_data_hash TEXT,  -- Hash of input window for cache key
    last_activity_date DATE,
    calibrated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    
    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX ix_individual_model_athlete_id ON individual_model(athlete_id);
CREATE INDEX ix_individual_model_expires_at ON individual_model(expires_at);
```

### Service Interface

```python
class ModelCache:
    def get(self, athlete_id: UUID) -> Optional[BanisterModel]:
        """Get cached model if valid."""
        
    def set(self, athlete_id: UUID, model: BanisterModel) -> None:
        """Cache calibrated model."""
        
    def invalidate(self, athlete_id: UUID) -> None:
        """Invalidate cached model."""
        
    def get_or_calibrate(self, athlete_id: UUID) -> BanisterModel:
        """Get cached or calibrate fresh."""
```

### Integration

1. Hook into `individual_performance_model.py`
2. Replace `get_or_calibrate_model()` to check cache first
3. Invalidate on Strava webhook (new activity)
4. Expose manual recalibrate via API

## Trade-offs

| Trade-off | Decision |
|-----------|----------|
| Staleness vs speed | 7-day TTL balances freshness with performance |
| Storage cost | Minimal (1 row per user, <1KB) |
| Consistency | Eventual (acceptable for predictions) |

## Security

- User-scoped: Each user only sees their model
- Auth required: JWT validation on all endpoints
- No PII in model params (just numbers)

## Feature Flag

```python
"cache.model_params": {
    "enabled": True,  # Default enabled
    "description": "Cache individual model parameters"
}
```

## Test Plan

### Unit Tests
- Cache hit returns model
- Cache miss triggers calibration
- Invalidation clears cache
- Expiration triggers recalibration

### Integration Tests
- Full flow: calibrate → cache → retrieve
- Invalidation on new activity

---

*ADR-024: Individual Performance Model Caching*
