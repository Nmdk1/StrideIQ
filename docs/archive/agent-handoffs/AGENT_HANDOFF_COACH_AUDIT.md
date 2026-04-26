# Agent Handoff: Coach System Audit (Resolved + Verified)

**Date:** 2026-01-19
**From:** Previous Agent (context exhausted)
**To:** New Agent
**Priority:** HIGH - Production system with paying user

---

## Executive Summary

The StrideIQ AI Coach is now operating as a **forensic, N=1 coaching system**:
- **All 11 tools** are callable and return structured data with an evidence contract.
- Dynamic suggestions are **end-to-end verified**: click → tool calls → answer contains receipts (date + UUID).
- The coach can highlight outliers as exceptions (not normalize them), matching “human coach” nuance.

---

## System Architecture

### Key Files
- `apps/api/services/ai_coach.py` - Main AI Coach service (OpenAI Assistants API)
- `apps/api/services/coach_tools.py` - 11 tool functions the coach can call
- `apps/api/services/correlation_engine.py` - Analytics engine for correlations
- `apps/api/services/training_load.py` - ATL/CTL/TSB calculations

### Database
- PostgreSQL in Docker: `docker-compose exec -T postgres psql -U postgres -d running_app`
- Single athlete: (redacted) (`athlete@example.com`)
- Athlete ID: `4368ec7f-c30d-45ff-a6ee-58db7716be24`
- 370 activities, 6 personal bests

### Data Quality (FIXED this session)
```sql
-- Values now set correctly
Max HR: 180
Resting HR: 50
Threshold HR: 165
Threshold Pace: 3.92 min/km
```

---

## The 11 Coach Tools - Audit Status

| # | Tool | Status | Notes |
|---|------|--------|-------|
| 1 | `get_recent_runs` | VERIFIED | Evidence cites activity IDs + date + distance/pace/HR |
| 2 | `get_efficiency_trend` | VERIFIED | Evidence cites activity IDs + EF points |
| 3 | `get_plan_week` | VERIFIED | Evidence cites planned workout IDs + dates |
| 4 | `get_training_load` | VERIFIED | Evidence cites derived ATL/CTL/TSB snapshot |
| 5 | `get_correlations` | VERIFIED | Evidence cites derived analysis summary (may be “none found”) |
| 6 | `get_race_predictions` | VERIFIED | PB/RPI fallback when calibrated model table is absent |
| 7 | `get_recovery_status` | VERIFIED | Evidence cites derived recovery half-life |
| 8 | `get_active_insights` | VERIFIED | May legitimately be empty if no insights exist |
| 9 | `get_pb_patterns` | VERIFIED | Evidence includes PB **activity UUIDs** for receipts |
| 10 | `get_efficiency_by_zone` | VERIFIED | Evidence includes concrete matching activity UUIDs |
| 11 | `get_nutrition_correlations` | VERIFIED | May show “insufficient data” if no nutrition entries exist |

---

## What Was Fixed This Session

### 1. Test Isolation (conftest.py)
- Implemented transactional rollback for all tests
- Tests can no longer pollute production database
- File: `apps/api/tests/conftest.py`

### 2. EPOCH Documentation Removed
- User requested removal of multi-agent workflow
- Deleted 16 handoff/EPOCH documentation files
- Working directly with user now (no Planner/Builder/Tester)

### 3. Calendar Tables Created
- `calendar_note` and `calendar_insight` were missing
- Created manually via SQL (migration was broken)

### 4. Test Athletes Cleaned
- Deleted 38 test athletes that were polluting database
- Only Michael Shaffer remains

### 5. get_pb_patterns Fixed
- Was returning only aggregates (min/max/mean TSB)
- Now returns per-PB detail array with date, category, distance, time, TSB
- Coach can now cite specific PBs

### 6. Dynamic Suggestions Fixed
- Updated to use new get_pb_patterns data structure
- Now includes specific PB callouts like "Your 2mile PR on 2025-07-10 was at TSB -32"

### 7. Data Quality Fixed
- Set resting HR, threshold HR, threshold pace from athlete's actual data
- TSB calculations are now accurate (was artifact before)

---

## What To Watch For (Regression Risks)

### 1. Evidence regressions
Any answer that includes numbers/trends without receipts is a regression.

### 2. Insight emptiness vs “broken”
`get_active_insights` can return zero items if no insights exist; that is not a bug. The bug condition is “tool had data but returned non-citable evidence.”

---

## How to Test Properly

### 1. Audit all 11 tools (fast)
```bash
docker-compose exec -T api python scripts/audit_coach_tools.py 4368ec7f-c30d-45ff-a6ee-58db7716be24
```

### 2. Verify Evidence Is Populated
For each tool, check that `result['evidence']` is a non-empty list with citable facts.

### 3. Test Dynamic Suggestions
```bash
docker-compose exec -T api python -c "
from core.database import SessionLocal
from uuid import UUID
from services.ai_coach import AICoach

db = SessionLocal()
coach = AICoach(db)
athlete_id = UUID('4368ec7f-c30d-45ff-a6ee-58db7716be24')

for s in coach.get_dynamic_suggestions(athlete_id):
    print(s)
db.close()
"
```

### 4. Clear Coach Thread Before Testing
```sql
UPDATE athlete SET coach_thread_id = NULL WHERE email = '<ATHLETE_EMAIL>';
```

### 5. Headless browser proof (repeatable)
From `apps/web/` on the host:

```bash
node scripts/e2e_coach_suggestions.mjs
```

---

## User Context

- User is the product owner and sole athlete in the system
- Very low tolerance for "it works" claims that don't hold up in browser
- Has spent significant money on this session
- Expects production-quality, not "ok: true" theater
- Test with THEIR data, not synthetic data
- If a suggestion promises insight, clicking it MUST deliver that insight

---

## Commands Reference

```bash
# Enter API container
docker-compose exec -T api bash

# PostgreSQL access
docker-compose exec -T postgres psql -U postgres -d running_app

# Run Python in container
docker-compose exec -T api python -c "..."

# Check athlete count
docker-compose exec -T postgres psql -U postgres -d running_app -c "SELECT COUNT(*) FROM athlete;"

# View coach thread
docker-compose exec -T postgres psql -U postgres -d running_app -c "SELECT coach_thread_id FROM athlete WHERE email = '<ATHLETE_EMAIL>';"
```

---

## Success Criteria

1. All 11 coach tools return useful data with evidence citations
2. Every dynamic suggestion, when clicked, produces a specific cited answer
3. No "I don't have enough data" responses when data exists
4. User can ask about their training and get answers grounded in their actual runs

---

## Do Not

- Claim things work without testing the full user journey
- Test only that functions return `ok: true`
- Add test athletes without cleaning them up
- Make changes without verifying with real athlete data
- Ignore evidence arrays - they are how the coach cites facts
