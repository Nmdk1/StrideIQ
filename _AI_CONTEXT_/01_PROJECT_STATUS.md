# StrideIQ Project Status

**Last Updated:** February 1, 2026  
**Version:** 0.9.1  
**Git Branch:** main

---

## Current State: STABLE BETA

All core features implemented and tested. AI Coach upgraded with 90/10 model split for better reasoning.

---

## Recent Updates (February 1, 2026)

### AI Coach Improvements (90/10 Split)
- **Expanded complexity classifier**: Causal questions, ambiguity, multi-factor queries now route to Opus
- **Tool validation**: Logs when mini skips tool calls on data questions
- **Data prefetch**: Injects last 7 days of runs into context for mini
- **Simplified instructions**: Mini gets shorter, clearer instructions
- **Cost impact**: $0.96 → $1.60/athlete/month (still 12.9% of revenue)

### Integrations
- **COROS API Application Submitted**: Awaiting Client ID and API Keys
  - See `_AI_CONTEXT_/16_COROS_INTEGRATION.md` for details

### Security
- Session invalidation capability (SECRET_KEY rotation)
- Password reset via database

---

## API Health Check

| Endpoint | Status | Notes |
|----------|--------|-------|
| `/health` | ✅ PASS | |
| `/v1/auth/me` | ✅ PASS | |
| `/v1/athletes/me` | ✅ PASS | |
| `/v1/activities` | ✅ PASS | |
| `/v1/activities/{id}` | ✅ PASS | |
| `/v1/activities/{id}/splits` | ✅ PASS | |
| `/v1/activities/{id}/analysis` | ✅ PASS | |
| `/v1/compare/auto-similar/{id}` | ✅ PASS | |
| `/v1/causal/simple-patterns` | ✅ PASS | |
| `/v1/causal/analyze` | ✅ PASS | |
| `/v1/athlete-profile/summary` | ✅ PASS | |
| `/v1/training-load/current` | ✅ PASS | |
| `/v1/correlations/what-works` | ✅ PASS | |
| `/v1/recovery-metrics/me` | ✅ PASS | |
| `/v1/data-export/my-anonymized-profile` | ✅ PASS | |

**Result: 15/15 PASSED**

---

## Recent Changes (Jan 10, 2026)

### Features Added
1. **Tiered Confidence System** for causal attribution
   - STATISTICAL → PATTERN → TREND → EARLY_SIGNAL
   - Graceful degradation with limited data
   
2. **Simple Pattern Matching**
   - `GET /v1/causal/simple-patterns`
   - Compares best 20% vs worst 20% runs
   - No Granger testing required (works with 10+ runs)

### Bugs Fixed
1. `recovery_metrics.py`: Timezone-aware datetime comparison
2. `activity_analysis.py`: Replaced property access with column access in SQLAlchemy queries
3. `v1.py`: Fixed `/athletes/me` route ordering
4. `body_composition.py`: Made `athlete_id` optional (defaults to current user)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend                              │
│                   Next.js 14 + TypeScript                    │
│                   React Query + Tailwind                     │
└─────────────────────────┬───────────────────────────────────┘
                          │ HTTPS
┌─────────────────────────▼───────────────────────────────────┐
│                         API                                  │
│                   FastAPI + Python 3.11                      │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │   Routers    │  │   Services   │  │    Models    │       │
│  │   (40+)      │  │   (50+)      │  │  (SQLAlchemy)│       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└─────────────────────────┬───────────────────────────────────┘
                          │
     ┌────────────────────┼────────────────────┐
     │                    │                    │
┌────▼────┐         ┌─────▼─────┐        ┌─────▼─────┐
│PostgreSQL│         │   Redis   │        │  Celery   │
│TimescaleDB│         │   Cache   │        │  Workers  │
└──────────┘         └───────────┘        └───────────┘
```

---

## Key Services

| Service | File | Purpose |
|---------|------|---------|
| Causal Attribution | `causal_attribution.py` | Leading indicator detection |
| Contextual Comparison | `contextual_comparison.py` | Ghost averaging, similarity |
| Pattern Recognition | `pattern_recognition.py` | Per-run trailing analysis |
| Athlete Context | `athlete_context.py` | Intelligence dossier |
| Activity Analysis | `activity_analysis.py` | Efficiency, baselines |
| Workout Classifier | `workout_classifier.py` | Auto-detect run types |
| Correlation Engine | `correlation_engine.py` | Input/output correlations |
| VDOT Calculator | `vdot_calculator.py` | Pace predictions |

---

## Environment

### Docker Containers
- `running_app_api` - FastAPI backend
- `running_app_db` - PostgreSQL + TimescaleDB
- `running_app_redis` - Redis cache
- `running_app_web` - Next.js frontend
- `running_app_worker` - Celery worker

### Commands
```bash
# Start all services
docker-compose up -d

# Restart API after code changes
docker-compose restart api

# View logs
docker-compose logs -f api

# Run tests
docker-compose exec api pytest
```

---

## Test Credentials

```
Email: athlete@example.com
Password: <set via environment / password manager>
```

---

## Files Modified Today

```
apps/api/services/causal_attribution.py   # Tiered confidence
apps/api/routers/causal.py                # Simple patterns endpoint
apps/api/routers/recovery_metrics.py      # Datetime fix
apps/api/services/activity_analysis.py    # Property/column fix
apps/api/routers/v1.py                    # Route ordering fix
apps/api/routers/body_composition.py      # Optional athlete_id
```

---

## Next Session Priorities

1. Frontend testing of new comparison features
2. Polish UI/UX based on user feedback
3. Onboarding flow implementation
4. Landing page refinement
