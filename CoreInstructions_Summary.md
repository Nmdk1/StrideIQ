# StrideIQ Core Instructions Summary
**Last Updated:** 2026-01-17 00:30 UTC
**Version:** 2.1

## What is StrideIQ?
AI-powered running coach that creates personalized training plans based on an athlete's actual physiological response to training - not population averages. The "Biological Digital Twin" concept.

## Core Philosophy: N=1
**The athlete is the sole sample.** Every metric, threshold, and recommendation should be calibrated to THIS athlete's data, not population norms.

Recent example: TSB zones are now personalized. An athlete who routinely trains at TSB -20 won't be incorrectly labeled "overreaching" just because population thresholds say so.

## Tech Stack
- **Backend:** FastAPI, Python 3.11, SQLAlchemy, PostgreSQL (TimescaleDB)
- **Frontend:** Next.js 14, React, TypeScript, Tailwind CSS, shadcn/ui
- **Infrastructure:** Docker Compose, Redis, Celery
- **Data:** Strava integration for activity sync

## Key Services Running
```
docker-compose up -d --build
```
- API: http://localhost:8000
- Web: http://localhost:3000
- PostgreSQL: localhost:5432
- Redis: localhost:6379

## Current State (as of 2026-01-17)

### Recently Completed
1. **N=1 TSB Zones (ADR-035)** - Personal thresholds based on athlete's historical mean/SD
2. **Training Load Page** - Accessible at /training-load with Personal Zones card
3. **Calendar Signals** - PB badges, removed noisy load badges
4. **Workout Classification** - Nuanced progression run detection with quality indicators
5. **Home Page Fixes** - Correct "remaining miles" calculation, past missed workouts handled

### All Tests Passing
```bash
docker-compose exec api python -m pytest tests/ -v
```

---

## PRIORITY: Phase 2 Training Plan Implementation

### Background
Phase 1 training plans are functional but have issues identified by the athlete:

1. **Zero strides or hill work/sprints** despite high volume (75 mpw)
2. **Tempo and Threshold runs treated as same** (need distinction)
3. **Too long taper** (3 weeks vs physiological 2 weeks)
4. **Little variation** in distances and run types

### What Exists
- `apps/api/services/model_driven_plan_generator.py` - Current plan generator
- `apps/api/services/constraint_aware_planner.py` - Handles athlete constraints
- `apps/api/services/fitness_bank.py` - Fitness/fatigue modeling
- `docs/adr/ADR-034-training-plan-variation.md` - Variation engine design

### Phase 2 Requirements (from user conversations)

#### 1. Workout Variety Engine
Add strides, hill sprints, and drills to plans:
- **Strides:** 4-6x20sec after easy runs, 2x/week during base/build
- **Hill sprints:** 6-10x10sec max effort, 1x/week during build
- **Drills:** Dynamic warmup progressions

#### 2. Distinguish Tempo vs Threshold
- **Tempo:** Comfortably hard, ~15-20 min sustained, ~85% max HR
- **Threshold:** Lactate threshold pace, 20-40 min, ~88-90% max HR
- Plans should prescribe each appropriately, not interchangeably

#### 3. Evidence-Based Taper
- Marathon: 2-3 weeks (currently 3, user prefers 2)
- Half Marathon: 10-14 days
- Shorter races: 7-10 days
- Make taper length configurable or data-driven

#### 4. Distance/Type Variation
- Avoid same distance easy runs every day
- Mix: 4mi easy, 6mi easy, 5mi with strides, etc.
- Psychological freshness matters

#### 5. Manual Plan Adjustments
User wants ability to:
- Swap workout days easily
- Mark workouts as missed (not just delete)
- Adjust individual workout distances

### Key Files to Read
1. `_AI_CONTEXT_/TRAINING_PHILOSOPHY.md` - Core training principles
2. `_AI_CONTEXT_/PLAN_GENERATION_FRAMEWORK.md` - Current generation logic
3. `docs/adr/ADR-034-training-plan-variation.md` - Variation engine spec
4. `apps/api/services/model_driven_plan_generator.py` - Main generator
5. User's Grok conversation about plan quality (referenced in session history)

### Implementation Approach
1. **Create ADR first** - Document the Phase 2 design
2. **Add unit tests** - TDD for new workout types
3. **Extend generator** - Add variety without breaking existing logic
4. **Verify with real plan** - Generate plan and validate manually
5. **Frontend support** - Ensure calendar displays new workout types correctly

---

## Development Standards

### Rigor Requirements
- **ADR for significant features** - Design first, code second
- **Verification before commit** - Run tests, check manually
- **Logging for observability** - Log key calculations
- **Handle edge cases** - Cold start, missing data, outliers

### Testing
```bash
# Run all API tests
docker-compose exec api python -m pytest tests/ -v

# Run specific test file
docker-compose exec api python -m pytest tests/test_training_load.py -v

# Verify N=1 TSB zones
docker-compose exec api python scripts/verify_n1_tsb.py
```

### Rebuilding
```bash
# Full rebuild
docker-compose down
docker-compose up -d --build

# API only
docker-compose up -d --build api
```

---

## Key ADRs to Know
- **ADR-010:** Training Stress Balance (TSB/ATL/CTL)
- **ADR-022:** Individual Performance Model (Banister τ1/τ2)
- **ADR-033:** Narrative Translation Layer
- **ADR-034:** Training Plan Variation Engine
- **ADR-035:** N=1 Individualized TSB Zones (NEW)

## Tone/Style
- **No fluff** - Technical accuracy over validation
- **Disagree when necessary** - User values honest feedback
- **Full rigor** - Don't cut corners on significant features
- **Verify before claiming done** - Tests pass, manual check complete

## User Context
- **Name:** Michael (mbshaf@gmail.com)
- **Age:** 57
- **Training:** High volume (~75 mpw), experienced marathoner
- **Goal:** Training for specific races with data-driven plans
- **Personality:** Values precision, calls out sloppiness, wants N=1 personalization

---

## Quick Start for Next Agent

1. Read this file and `_AI_CONTEXT_/ChatSession_2026-01-17_0030.md`
2. Run `docker-compose ps` to verify services
3. Check git status for any uncommitted changes
4. Review `docs/adr/ADR-034-training-plan-variation.md` for Phase 2 context
5. Ask user what they want to prioritize

**Primary pending work:** Phase 2 Training Plan Implementation (variety, tempo/threshold distinction, taper length, manual adjustments)
