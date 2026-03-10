# Complete System Handoff: StrideIQ (Coach + N=1 Insight Engine)

**Date:** 2026-01-19
**From:** Previous Agent (context exhausted)
**To:** New Agent
**Goal:** Full system audit, fix all issues, verify with real athlete data, leave system fully functional

---

## Update (2026-01-22): UI consistency work + next-agent context

This repo has additional uncommitted work beyond this handoff’s original scope (notably **web UI consistency** attempts and admin/diagnostics routing changes).

- **Canonical UX goal**: the logged-in product must feel like one cohesive app (consistent backgrounds, card surfaces, spacing).
- **What changed**: global background drift (`bg-[#0a0a0f]`) was removed across many web pages/components in favor of `bg-slate-900`.
- **What’s still wrong (per owner feedback)**: Home still reads as a different theme due to translucent card surfaces (e.g. `bg-slate-800/50`, nested `bg-slate-900/30`) vs Analytics/Calendar using solid `bg-slate-800 border-slate-700`.
- **Next step**: standardize Home card surfaces to match Analytics/Calendar, and introduce a shared page wrapper component so styling can’t drift again.

See the session handoff for the next agent: `docs/AGENT_HANDOFF_2026-01-22_UI_UNIFICATION_AND_VERSION_CONTROL.md`.

---

## CRITICAL: Plan Generator BROKEN (Fix First)

**Status:** RESOLVED (was a 500 surfaced as “CORS” in browser)
**Page:** `localhost:3000/plans/create`

**What it looked like in browser:**
```
Access to fetch at 'http://localhost:8000/v2/plans/constraint-aware' from origin 'http://localhost:3000' 
has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header is present.
[Plan Create] Error creating constraint-aware plan: TypeError: Failed to fetch
```

**Root causes (fixed):**
- `feature_flag` schema mismatch (missing `requires_subscription` etc.) caused `POST /v2/plans/constraint-aware` to 500.
- `feature_flag` table was empty (no `plan.model_driven_generation` row), so even after schema fix, flags needed seeding.
- `services/fitness_bank.py` caught DB exceptions (e.g. missing `athlete_calibrated_model`) without rolling back, leaving the SQLAlchemy session “aborted” and breaking subsequent queries.

**Fix steps applied:**
```bash
# 1) Apply migration to align feature_flag schema
docker-compose exec -T api alembic upgrade head

# 2) Seed feature flags (creates plan.model_driven_generation, etc.)
docker-compose exec -T api python scripts/seed_feature_flags.py

# 3) Ensure services/fitness_bank.py rolls back on DB exceptions (prevents aborted tx)
#    (code change; already in repo)

# 4) Verify endpoint (must return 200 + Allow-Origin)
# NOTE: Do not hardcode real credentials in this repo. Use environment variables.
docker-compose exec -T api python -c "import os,requests; base='http://localhost:8000'; email=os.environ['STRIDEIQ_TEST_EMAIL']; pwd=os.environ['STRIDEIQ_TEST_PASSWORD']; r=requests.post(base+'/v1/auth/login', json={'email':email,'password':pwd}); r.raise_for_status(); tok=r.json()['access_token']; h={'Authorization':'Bearer '+tok,'Origin':'http://localhost:3000'}; payload={'race_date':'2026-03-15','race_distance':'marathon','race_name':'Test','tune_up_races':[]}; resp=requests.post(base+'/v2/plans/constraint-aware', headers=h, json=payload, timeout=180); print(resp.status_code, resp.headers.get('access-control-allow-origin'))"
```

**Key files:**
- `apps/api/routers/plan_generation.py` - endpoint definition
- `apps/api/main.py` - CORS middleware
- `apps/api/services/constraint_aware_planner.py` - plan generation logic
- `apps/api/services/fitness_bank.py` - **must rollback() on caught DB exceptions**

**Verification:** `POST /v2/plans/constraint-aware` now returns **200** and includes `Access-Control-Allow-Origin: http://localhost:3000`.

---

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
Name: (redacted)
Email: athlete@example.com
Athlete ID: 4368ec7f-c30d-45ff-a6ee-58db7716be24
Activities: 370
Personal Bests: 9 (Strava best-efforts derived; includes 1-mile race PB)
```

**Data Quality Settings (fixed this session):**
```sql
Max HR: 180
Resting HR: 50
Threshold HR: 165
Threshold Pace: 3.92 min/km
```

---

## NEW (2026-01-20): Strava Best-Effort Ingestion Hardening (Production Safety)

**Why this exists:** PBs, diagnostics, and parts of coaching depend on Strava’s authoritative `best_efforts` (fastest segments inside activities). If ingestion is incomplete, downstream metrics can look “wrong” even when logic is correct.

**Root regression fixed:** `run_migrations.py` used `create_all()` + manual `alembic_version` stamping, which could silently skip tables added later (ex: `best_effort`). This made PBs appear “reverted” even though best-effort code existed.

**Fixes applied:**
- `apps/api/run_migrations.py`: now runs `alembic upgrade head` (fail-fast). Only falls back to `create_all()` for an empty DB and then stamps `head`.
- Migration: `apps/api/alembic/versions/8c7b1b3c4d5e_add_best_effort_table_for_pbs.py` (creates `best_effort` if missing).
- Worker task registration: `apps/api/tasks/__init__.py` imports `best_effort_tasks`.

**New endpoints (no external calls unless explicitly queued):**
- `GET /v1/athletes/{id}/best-efforts/status`
- `POST /v1/athletes/{id}/sync-best-efforts/queue?limit=200`
- `POST /v1/athletes/{id}/strava/backfill-index/queue?pages=5`
- `POST /v1/athletes/{id}/strava/ingest-activity/{strava_activity_id}?mark_as_race=true`
- `GET /v1/tasks/{task_id}`

**NEW (ops visibility):**
- Table: `athlete_ingestion_state` (1 row per athlete/provider) stores:
  - last task ids
  - last run started/finished
  - last error (if any)
  - last run counters (pages fetched / activities checked / etc.)
- `GET /v1/athletes/{id}/best-efforts/status` now returns **both**:
  - computed progress (`best_efforts.*`)
  - durable run metadata (`ingestion_state.*`)

**Frontend behavior:**
- `apps/web/app/personal-bests/page.tsx` queues best-effort backfill and polls task completion (no long-running HTTP request / no sleeping in the browser request).

**Operational notes (for viral-safe scaling):**
- Use **index backfill** first (cheap): creates missing Activity rows from Strava summaries.
- Use **best-effort backfill** second (expensive): fetches per-activity details to extract `best_efforts` and regenerates PBs.
- If a specific race is missing and Strava shows best-efforts for it, use **single-activity ingest** with the Strava activity ID (authoritative link; no guessing).

**IMPORTANT NOTE (Strava semantics):**
- Many activities will legitimately return **no** `best_efforts` because Strava only includes them when the activity sets a PR.
- Therefore, “has BestEffort rows” is NOT a valid proxy for “processed.”
- The system now tracks a dedicated processing marker: `activity.best_efforts_extracted_at`.
- `GET /v1/athletes/{id}/best-efforts/status` reports `activities_processed` using that marker.

**Viral spike throttle (global):**
- `apps/api/services/strava_service.py:get_activity_details` is now guarded by a Redis-backed semaphore.
- Setting: `STRAVA_DETAIL_FETCH_CONCURRENCY` (default 4) caps concurrent Strava `/activities/{id}` detail fetches across *all* workers.
- If Redis is unavailable, throttle degrades gracefully (availability > strict throttling).

**Golden path check (automated):**
- Script: `apps/api/scripts/golden_path_check.py`
- Runs a minimal end-to-end validation against a running stack:
  - auth → best-efforts status → queue a tiny chunk → PBs → coach citations
  - optional plan generation check (can be skipped)
- Usage (inside API container):
```bash
docker-compose exec -T api python scripts/golden_path_check.py --skip-plan
```

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
| 6 | `get_race_predictions` | coach_tools.py | VERIFIED (PB/RPI fallback if model table missing) |
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
UPDATE athlete SET coach_thread_id = NULL WHERE email = '<ATHLETE_EMAIL>';
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
UPDATE athlete SET coach_thread_id = NULL WHERE email = '<ATHLETE_EMAIL>';

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
