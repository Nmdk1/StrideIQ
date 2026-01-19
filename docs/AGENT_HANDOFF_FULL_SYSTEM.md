# Complete System Handoff: StrideIQ (Coach + N=1 Insight Engine)

**Date:** 2026-01-19
**From:** Previous Agent (context exhausted)
**To:** New Agent
**Goal:** Full system audit, fix all issues, verify with real athlete data, leave system fully functional

## Current State (Verified)

**As of 2026-01-19, the AI Coach is validated end-to-end with real athlete data:**
- Tool outputs contain **citable evidence** (date + UUID + human-readable value)
- Dynamic suggestions work end-to-end: **click suggestion → tool calls → cited answer**
- Browser flow verified at `localhost:3000/coach` (including a headless browser check)

---

## Project Overview

StrideIQ is an AI-powered running coach platform. It ingests data from Strava, calculates training metrics (ATL/CTL/TSB, efficiency, correlations), and provides personalized coaching through an AI interface.

### Tech Stack
- **Backend:** FastAPI (Python 3.11) in Docker
- **Database:** PostgreSQL in Docker
- **Frontend:** Next.js (React)
- **AI:** OpenAI Assistants API (gpt-4o-mini for queries)
- **Data Source:** Strava API

### Key Directories
```
apps/
  api/                    # FastAPI backend
    services/             # Core business logic
    routers/              # API endpoints
    models.py             # SQLAlchemy models
    tests/                # Pytest tests
  web/                    # Next.js frontend
docs/
  adr/                    # Architecture Decision Records
  manifesto.md            # Product vision
```

---

## The Athlete (Your Test User)

**CRITICAL:** There is ONE real athlete in the system. All testing must use their data.

```
Name: Michael Shaffer
Email: mbshaf@gmail.com
Athlete ID: 4368ec7f-c30d-45ff-a6ee-58db7716be24
Activities: 370
Personal Bests: 6
```

**Data Quality Settings (fixed this session):**
```sql
Max HR: 180
Resting HR: 50
Threshold HR: 165
Threshold Pace: 3.92 min/km
```

---

## The 5 Phases of N=1 Insight Engine

These phases were built to transform StrideIQ from "code that runs" to "code that thinks." Each has an ADR in `docs/adr/`.

### Phase 1: ADR-045 - Complete Correlation Wiring
**Purpose:** Correlation engine to find relationships between inputs and outputs.
**Key File:** `apps/api/services/correlation_engine.py`
**Functions:**
- `analyze_correlations()` - Main correlation analysis
- `aggregate_pb_events()` - PB event aggregation
- `aggregate_pre_pb_state()` - Training state before PBs
- `aggregate_efficiency_by_effort_zone()` - Efficiency by HR zone
- Time-shifted correlations for lagged effects

**Status:** Implemented. Core outputs verified with real athlete data.

### Phase 2: ADR-046 - Expose Hidden Analytics to Coach
**Purpose:** Give the AI coach access to analytical tools.
**Key File:** `apps/api/services/coach_tools.py`
**5 New Tools Added:**
1. `get_race_predictions` - Predict race times
2. `get_recovery_status` - Recovery state analysis
3. `get_active_insights` - Prioritized insights
4. `get_pb_patterns` - PB training patterns (FIXED this session)
5. `get_efficiency_by_zone` - Efficiency by effort zone

**Status:** Tools audited against real athlete data; evidence contract enforced.

### Phase 3: ADR-047 - Coach Architecture Refactor
**Purpose:** Dynamic model selection for cost optimization.
**Key File:** `apps/api/services/ai_coach.py`
**Changes:**
- Query classification (simple vs standard)
- Model selection (gpt-3.5-turbo for simple, gpt-4o-mini for standard)
- 11 tools registered with OpenAI Assistant

**Status:** Architecture is in place. Tool dispatch in `chat()` method handles all 11 tools.

### Phase 4: ADR-048 - Dynamic Insight Suggestions
**Purpose:** Replace static suggestions with data-driven ones.
**Key File:** `apps/api/services/ai_coach.py`
**Function:** `get_dynamic_suggestions()`
**Sources:**
- Active insights
- PB patterns
- TSB state
- Efficiency trends
- Recent activity

**Status:** Verified end-to-end. Suggestions are “citation-forcing” to ensure the coach responds with receipts.

### Phase 5: ADR-049 - Activity-Linked Nutrition Correlation
**Purpose:** Correlate nutrition with performance/recovery.
**Key File:** `apps/api/services/correlation_engine.py`
**Function:** `aggregate_activity_nutrition()`
**Tool:** `get_nutrition_correlations` in coach_tools.py

**Status:** Implemented; may show “insufficient data” if the athlete has no nutrition entries.

---

## The 11 Coach Tools - Complete Audit Required

Each tool MUST return:
```python
{
    "ok": True,
    "tool": "tool_name",
    "generated_at": "ISO timestamp",
    "data": { ... useful structured data ... },
    "evidence": [
        {
            "type": "activity|personal_best|derived",
            "id": "unique_id",
            "date": "2025-01-15",
            "value": "Human readable citation the coach can quote"
        }
    ]
}
```

**The `evidence` array is critical.** The AI coach uses this to cite facts. Evidence may be empty only when the tool truly has no data (and `data` must explain why).

| # | Tool | Location | Audit Status |
|---|------|----------|--------------|
| 1 | `get_recent_runs` | coach_tools.py | VERIFIED |
| 2 | `get_efficiency_trend` | coach_tools.py | VERIFIED |
| 3 | `get_plan_week` | coach_tools.py | VERIFIED |
| 4 | `get_training_load` | coach_tools.py | VERIFIED |
| 5 | `get_correlations` | coach_tools.py | VERIFIED |
| 6 | `get_race_predictions` | coach_tools.py | VERIFIED (PB/VDOT fallback if model table missing) |
| 7 | `get_recovery_status` | coach_tools.py | VERIFIED |
| 8 | `get_active_insights` | coach_tools.py | VERIFIED (may legitimately be empty if no insights exist) |
| 9 | `get_pb_patterns` | coach_tools.py | VERIFIED (includes PB activity IDs) |
| 10 | `get_efficiency_by_zone` | coach_tools.py | VERIFIED (includes citable activity evidence) |
| 11 | `get_nutrition_correlations` | coach_tools.py | VERIFIED (may be “insufficient data” if no nutrition entries) |

---

## Known Issues to Fix

### 1. Evidence Quality Regressions
If any tool returns results without citable evidence for a data-backed claim, treat it as a regression. The system’s trust depends on receipts.

### 2. End-to-End Flow Must Stay Verified
When a user clicks a suggestion:
1. Suggestion text becomes a chat message
2. Coach calls appropriate tool(s)
3. Coach responds with **at least one date + UUID citation** when data exists

### 3. OpenAI Assistant May Have Stale Tools
The assistant is created/updated with tool definitions. If tools changed, assistant may not have latest definitions.

**Check:** `apps/api/services/ai_coach.py` method `_get_or_create_assistant()`

### 4. Coach Thread Caching
The athlete has a `coach_thread_id` that persists conversation. Old threads may have stale context.

**Fix:** Clear before testing:
```sql
UPDATE athlete SET coach_thread_id = NULL WHERE email = 'mbshaf@gmail.com';
```

### 5. Database Migration Gap
Calendar tables were created manually because migration was broken. Check `alembic_version` table and ensure schema is consistent.

---

## System Components to Validate

### Core Services
| Service | File | Purpose |
|---------|------|---------|
| AICoach | `services/ai_coach.py` | Main coach logic |
| CoachTools | `services/coach_tools.py` | Tool functions |
| CorrelationEngine | `services/correlation_engine.py` | Analytics |
| TrainingLoadCalculator | `services/training_load.py` | ATL/CTL/TSB |
| EfficiencyAnalytics | `services/efficiency_analytics.py` | Efficiency trends |
| InsightAggregator | `services/insight_aggregator.py` | Prioritized insights |

### API Endpoints
| Endpoint | Router | Purpose |
|----------|--------|---------|
| POST /v1/coach/chat | routers/ai_coach.py | Chat with coach |
| GET /v1/coach/suggestions | routers/ai_coach.py | Get suggestions |
| POST /v1/coach/new-conversation | routers/ai_coach.py | Clear thread |

### Frontend Pages
| Page | File | Purpose |
|------|------|---------|
| /coach | apps/web/... | Coach chat UI |
| /calendar | apps/web/... | Calendar view |
| /analytics | apps/web/... | Analytics dashboard |

---

## How to Test

### 1. Audit All 11 Tools (fast)
Inside the API container:

```bash
docker-compose exec -T api python scripts/audit_coach_tools.py 4368ec7f-c30d-45ff-a6ee-58db7716be24
```

For each tool, verify:
- `ok` is True
- `data` contains useful information
- `evidence` items (when present) have `type`, `id` (UUID), `date`, `value`

### 2. Test Dynamic Suggestions
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

### 3. Test End-to-End Chat (most important)
1. Clear the coach thread in database
2. Open browser to localhost:3000/coach
3. Click a suggestion
4. Verify coach responds with SPECIFIC CITED DATA, not generic advice

### 4. Headless Browser Proof (repeatable)
From `apps/web/` on the host:

```bash
node scripts/e2e_coach_suggestions.mjs
```

This test logs in, navigates to `/coach`, clicks a suggestion, and asserts the response contains a **date** and a **UUID**.

### 4. Verify in Browser
The ultimate test is the user experience. If it doesn't work in browser with real data, it doesn't work.

---

## Database Access

```bash
# PostgreSQL CLI
docker-compose exec -T postgres psql -U postgres -d running_app

# Check athlete
SELECT id, display_name, email, coach_thread_id FROM athlete;

# Check activities
SELECT COUNT(*) FROM activity WHERE athlete_id = '4368ec7f-c30d-45ff-a6ee-58db7716be24';

# Check PBs
SELECT distance_category, achieved_at FROM personal_best 
WHERE athlete_id = '4368ec7f-c30d-45ff-a6ee-58db7716be24';

# Clear coach thread
UPDATE athlete SET coach_thread_id = NULL WHERE email = 'mbshaf@gmail.com';

# Check for test athlete pollution
SELECT COUNT(*) FROM athlete;  -- Should be 1
```

---

## Commands Reference

```bash
# Start system
docker-compose up -d

# API container shell
docker-compose exec -T api bash

# Run Python in API container
docker-compose exec -T api python -c "..."

# View API logs
docker-compose logs -f api

# Run tests
docker-compose exec -T api python -m pytest tests/ -v

# Check lint
docker-compose exec -T api python -m flake8 services/ai_coach.py
```

---

## Success Criteria

When you are done:

1. **All 11 coach tools return useful data with evidence citations**
2. **Every dynamic suggestion produces a specific cited answer when clicked**
3. **No "I don't have enough data" responses when data exists**
4. **Coach can answer questions about:**
   - Recent runs (dates, distances, paces)
   - Training load (current TSB, fatigue state)
   - Efficiency trends (improving/declining)
   - Personal bests (what conditions led to them)
   - Correlations (what predicts good performance)
5. **System works end-to-end in browser with Michael Shaffer's real data**
6. **No test athletes in database (only Michael Shaffer)**
7. **All tests pass without polluting database**

---

## User Expectations

- **Zero tolerance for "it works" claims that fail in browser**
- **Test with REAL data, not synthetic**
- **If a suggestion promises insight, clicking it MUST deliver**
- **Production quality, not prototypes**
- **Cite specific evidence (dates, values, activity IDs)**

---

## What Was Fixed This Session (Don't Regress)

1. **Test isolation** - conftest.py uses transactional rollback
2. **Calendar tables** - created manually (calendar_note, calendar_insight)
3. **Test athletes cleaned** - deleted 38 fake athletes
4. **get_pb_patterns** - returns per-PB detail with TSB **and PB activity IDs**
5. **Dynamic suggestions** - citation-forcing prompts to ensure cited answers in UI
6. **Data quality** - resting HR, threshold HR, threshold pace set

---

## Recommended Approach

1. **Read this document completely**
2. **Audit all 11 coach tools** - test each, fix evidence arrays
3. **Test dynamic suggestions** - verify each leads to useful answer
4. **Test in browser** - actual user flow
5. **Fix any issues found**
6. **Re-test everything**
7. **Confirm with user**

Do NOT claim success until the user has verified in browser.

---

## Files to Read First

1. `apps/api/services/ai_coach.py` - Main coach service
2. `apps/api/services/coach_tools.py` - All 11 tools
3. `apps/api/routers/ai_coach.py` - API endpoints
4. `docs/adr/ADR-045-complete-correlation-wiring.md` through `ADR-049-*`

---

## Anti-Patterns to Avoid

- Testing that functions return `ok: true` without checking evidence
- Claiming "all phases pass" without testing user flows
- Adding test data without cleanup
- Making changes without testing with real athlete data
- Assuming tools work because they don't throw errors
- Ignoring the evidence array structure
