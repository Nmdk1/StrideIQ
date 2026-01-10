# MIGRATION GUIDE: Legacy to Production Architecture

**Status:** In Progress  
**Last Updated:** Jan 4, 2026

## Overview

We're migrating from an ad-hoc codebase structure to a production-ready, scalable architecture. This guide documents the migration path.

## Architecture Changes

### New Structure
```
apps/api/
├── core/              # NEW: Core infrastructure
│   ├── config.py      # Centralized configuration
│   ├── logging.py     # Structured logging
│   ├── database.py    # Connection pooling
│   └── cache.py       # Redis caching (TODO)
├── routers/           # API endpoints (unchanged)
├── services/          # Business logic (unchanged)
├── tasks/             # NEW: Celery tasks (TODO)
├── models.py          # Database models (unchanged)
└── schemas.py         # Pydantic schemas (unchanged)
```

## Migration Steps

### Phase 1: Core Infrastructure ✅ COMPLETE
- [x] Created `core/config.py` - Centralized configuration
- [x] Created `core/database.py` - Connection pooling
- [x] Created `core/logging.py` - Structured logging
- [x] Updated `main.py` - Enhanced health checks, request logging
- [x] Updated `database.py` - Backward compatibility wrapper

### Phase 2: Import Migration (IN PROGRESS)
**Current State:** Legacy imports still work via backward compatibility

**Files to Migrate:**
- [ ] `routers/v1.py` - Update `from database import get_db` → `from core.database import get_db`
- [ ] `routers/strava.py` - Update database imports
- [ ] `routers/feedback.py` - Update database imports
- [ ] `models.py` - Update `from database import Base` → `from core.database import Base`
- [ ] `alembic/env.py` - Update database imports
- [ ] All scripts in `scripts/` - Update database imports

**Migration Pattern:**
```python
# OLD
from database import get_db, SessionLocal, Base

# NEW
from core.database import get_db, get_db_sync, Base
```

### Phase 3: Background Tasks (TODO)
**Goal:** Move long-running operations to Celery

**Tasks to Migrate:**
- [ ] Strava sync (`routers/strava.py::strava_sync`) → `tasks/strava_tasks.py`
- [ ] PB recalculation → Background task
- [ ] Age-grading recalculation → Background task

**Pattern:**
```python
# OLD: Synchronous in router
@router.post("/sync")
def sync():
    # Long-running sync...
    return {"status": "complete"}

# NEW: Async task
@router.post("/sync")
def sync():
    task = sync_strava_activities.delay(athlete_id)
    return {"task_id": task.id, "status": "queued"}

# In tasks/strava_tasks.py
@celery_app.task
def sync_strava_activities(athlete_id):
    # Long-running sync...
    pass
```

### Phase 4: Caching Layer (TODO)
**Goal:** Reduce database load with Redis caching

**Candidates for Caching:**
- [ ] Athlete data (10 min TTL)
- [ ] Age-grading calculations (5 min TTL)
- [ ] Activity lists (1 min TTL)
- [ ] Personal bests (5 min TTL)

### Phase 5: Rate Limiting (TODO)
**Goal:** Protect API from abuse

**Implementation:**
- [ ] Add rate limiting middleware
- [ ] Per-user limits
- [ ] Per-IP limits
- [ ] Exempt health checks

## Backward Compatibility

The legacy `database.py` module is maintained as a compatibility layer. It imports from `core.database` and issues a deprecation warning.

**Timeline:**
- **Week 1:** Legacy imports work, warnings issued
- **Week 2:** Migrate all imports
- **Week 3:** Remove legacy `database.py` wrapper

## Testing Strategy

1. **Unit Tests:** Test core modules independently
2. **Integration Tests:** Test API endpoints with new infrastructure
3. **Load Tests:** Verify connection pooling handles concurrency
4. **Migration Tests:** Verify backward compatibility

## Rollback Plan

If issues arise:
1. Revert `main.py` to previous version
2. Keep legacy `database.py` active
3. Disable new core modules via feature flags
4. Gradual re-enablement

## Notes

- All new code should use `core.*` modules
- Legacy code continues to work during migration
- No breaking changes until Phase 3 (background tasks)
- Database connection pooling is active immediately


