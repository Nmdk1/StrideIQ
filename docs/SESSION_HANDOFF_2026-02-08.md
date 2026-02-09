# Session Handoff - February 8, 2026

## Session Summary

Major session covering efficiency attribution fixes, AI coach tone overhaul, complete VDOT trademark purge, and identification of the next priority work. All tests green (1428 backend, 116 frontend). Git tree clean. Production deployed.

---

## CRITICAL: Founder Principles (Violate These and You Lose Trust)

The founder (Michael Shaffer) is a physicist, former 4:07 miler, college XC runner, and has been running for decades. He knows running science better than most coaches. Key non-negotiable principles:

1. **NEVER use the term VDOT anywhere user-facing or in code.** It is trademarked by Jack Daniels / VDOT O2. The internal term is **RPI** (Running Performance Index). This was a massive refactor this session (158 files). The only place "vdot" remains is in 2 database column names (`athlete.vdot`, `training_plan.baseline_vdot`) — the Python attributes are `athlete.rpi` and `plan.baseline_rpi` via `Column('vdot', Float)`.

2. **NEVER dump raw metrics on the athlete.** Numbers like "TSB: -16.2" or "CTL: 35.3" or "Form: -23.9" mean nothing to athletes. The LLM must translate data into coaching language. Raw data stays in internal briefs tagged `(INTERNAL — translate for athlete, never quote raw numbers)`.

3. **NEVER contradict how the athlete says they feel.** If they report feeling fine but load numbers are high, validate them and suggest recovery actions. Don't say "actually you're fatigued." That's a self-fulfilling prophecy.

4. **Coach-led, not dashboard-led.** The product is an AI coach, not a metrics dashboard. Every piece of data shown should have context, meaning, and actionability. Static cards with unexplained numbers break trust.

5. **N=1 data, not templates.** Insights must come from the athlete's own data, not generic training advice.

6. **Higher EF (Efficiency Factor) is BETTER.** EF = speed/HR. More ground per heartbeat = more efficient. This was incorrectly inverted before this session.

---

## What Was Done This Session (Chronological)

### 1. Coach Suggestion Prompts Rewritten
- **File:** `apps/api/services/ai_coach.py`
- Rewrote all suggestion chip prompts to trigger coaching insight instead of data readback
- Suggestions now ask questions like "What should I focus on?" instead of "Show me my CTL"

### 2. Dual-Layer "What's Working" with N=1 Correlation Progress
- **Files:** `apps/api/routers/progress.py`, `apps/web/app/progress/page.tsx`, `apps/web/lib/hooks/queries/progress.ts`
- Added a new "What's Working" section to the Progress page
- Shows N=1 correlation-driven insights (what patterns correlate with the athlete's best performances)
- Created `_AI_CONTEXT_/OPERATIONS/V3_HOME_REDESIGN_NOTES.md` — a design document for the V3 coach-first home page vision (deferred for later)

### 3. Splits Table Cumulative Time
- **File:** `apps/web/components/activities/SplitsTable.tsx`
- "Time" column now shows cumulative elapsed time, not per-split duration

### 2. Efficiency Factor (EF) Complete Overhaul
- **Files:** `apps/api/services/run_attribution.py`
- Formula corrected: `speed_mps / avg_hr` (higher = better), NOT `pace / HR`
- Uses GAP (Grade Adjusted Pace) from `ActivitySplit.gap_seconds_per_mile` when available
- Distance-weighted average across splits for hilly routes
- 4-tier comparison fallback:
  1. Same workout type + similar distance (+-30%, 90 days, min 2)
  2. Same workout type, any distance (90 days, min 2)
  3. Similar distance only (+-30%, 90 days, min 3, lower confidence)
  4. All recent runs (28 days, min 5, lowest confidence)

### 3. Workout Classification Pipeline
- **File:** `apps/api/tasks/strava_tasks.py` — auto-classifies on Strava sync
- **File:** `apps/api/services/workout_classifier.py` — fixed `_classify_steady_state()` to prioritize distance/duration over intensity (20-miler at low HR = long_run, not recovery_run)
- 346 activities reclassified on production

### 4. Coach Tone Guardrails
- **File:** `apps/api/routers/home.py` — Added COACHING TONE RULES to Gemini system prompt:
  - Lead with positives
  - Frame concerns as forward-looking actions
  - Never contradict self-report
  - Never quote raw metrics
  - Be motivator, not liability disclaimer
- **File:** `apps/api/services/coach_tools.py` — Tagged internal data sections with `(INTERNAL — translate for athlete)` so LLM has data to reason from but knows not to quote it

### 5. Test Fixes
- `test_strava_token_refresh.py` — timezone-naive vs timezone-aware comparison
- `test_email_verification.py` — mocked `send_email` in `complete_email_change` tests (was sending real emails to `emailchange_test@example.com` on every test run)

### 6. VDOT Trademark Purge (158 files)
- **Every** instance of "vdot" renamed to "rpi" across the entire codebase
- File renames: `vdot_calculator.py` → `rpi_calculator.py`, `vdot.py` router → `rpi.py`, 18 total
- Function renames: `calculate_vdot_from_race_time` → `calculate_rpi_from_race_time`, etc.
- Variable renames: `vdot` → `rpi`, `fallback_vdot` → `fallback_rpi`, etc.
- API route: `/v1/vdot` → `/v1/rpi`
- DB columns: Python attributes renamed, physical column names preserved via `Column('vdot', Float)`
- All docs, ADRs, AI context files updated
- 3366 insertions, 3366 deletions — pure rename, no logic changes

### 7. Cleanup
- Trailing whitespace stripped from all modified files
- Temp diagnostic scripts deleted
- Redis cache flushed on production

---

## Test Results

- **Backend:** 1428 passed, 7 skipped, 0 failed
- **Frontend:** 116 passed (20 suites), 0 failed
- Git tree: clean
- Production: deployed and verified

---

## Commits (chronological, 14 total)

1. `9e544b9` — fix: rewrite suggestion prompts to trigger coaching insight, not data readback
2. `0294918` — feat: dual-layer What's Working with N=1 correlation progress indicator
3. `2080244` — fix: splits table Time column shows cumulative elapsed time
4. `5bb7729` — fix: efficiency attribution compares against similar runs
5. `939a597` — fix: strava token refresh test timezone comparison
6. `4482914` — fix: efficiency attribution uses GAP from splits + same workout type
7. `8e1b5e1` — fix: auto-classify workout type on Strava sync
8. `bf3d3ab` — fix: long runs at low intensity classified as long_run
9. `bb94030` — fix: EF formula corrected to speed/HR (higher=better)
10. `2bd9572` — Coach tone: add LLM guardrails for raw metric parroting and negative framing
11. `a69614b` — chore: strip trailing whitespace, remove temp scripts, add session handoff docs
12. `93a31b5` — fix: mock send_email in complete_email_change tests
13. `51baf57` — fix: remove trademarked VDOT term from user-facing labels and API responses
14. `534bef2` — refactor: purge trademarked VDOT term from entire codebase, replace with RPI

---

## IMMEDIATE NEXT PRIORITY: Progress Page "Dumb Cards"

### The Problem

The Progress page (`apps/web/app/progress/page.tsx`) has static metric cards that violate the coach-led principle:

```
Fitness: 35.3 (rising)
Form: -23.9
Volume (28d): 191.5mi (+188.8%)
Consistency: 100%
```

These cards:
- Show raw numbers with no explanation ("What is Form? What does -23.9 mean?")
- Have no drill-down capability
- Leave the athlete with more questions than answers
- Break trust because they look like a generic dashboard, not a coach
- Are the same pattern we just fixed on the Home page (raw TSB/CTL dumping)

### The Solution Direction

These cards should be **coach-interpreted, interactive, and contextual**:

1. **Replace raw numbers with coaching language.** Instead of "Form: -23.9", show something like "Absorbing load — recovery days this week will let fitness lock in." The LLM should generate these interpretations.

2. **Add drill-down.** Tapping a card should expand to show trend context, what's driving the number, and what the athlete should do about it.

3. **Make them dynamic.** The cards should adapt based on training phase, injury history, and goals. A "Form: -23.9" during a build phase means something completely different from the same number during a taper.

### Key Files

- **Frontend:** `apps/web/app/progress/page.tsx` — renders the cards
- **Backend data:** `apps/api/routers/progress.py` — the `/v1/progress/summary` endpoint that feeds the page
- **Training load:** `apps/api/services/coach_tools.py` — `get_training_load()` computes CTL/ATL/TSB
- **LLM briefing pattern:** `apps/api/routers/home.py` — `generate_coach_home_briefing()` is the existing pattern for LLM-interpreted cards (reusable)
- **Athlete brief:** `apps/api/services/coach_tools.py` — `build_athlete_brief()` has the data sections already tagged as INTERNAL

### Architecture Hint

The Home page already has a working pattern: raw data → LLM prompt with tone rules → structured JSON response → frontend renders coaching language. The Progress page cards should follow the same pattern rather than rendering raw numbers from the API.

---

## Key Architecture Notes

### How the Coach Home Page Works
1. `apps/api/routers/home.py` → `generate_coach_home_briefing()` calls Gemini
2. Athlete brief built by `build_athlete_brief()` in `coach_tools.py`
3. Brief contains raw data tagged `(INTERNAL — translate for athlete)`
4. Gemini prompt has COACHING TONE RULES enforcing positive-first framing
5. Response is structured JSON with fields: `coach_noticed`, `today_context`, `week_assessment`, `checkin_reaction`, `race_assessment`
6. Cached in Redis for 30 minutes keyed by data fingerprint

### How the Progress Page Works
1. `apps/api/routers/progress.py` → `GET /v1/progress/summary`
2. Aggregates: training load, recovery, race predictions, runner profile, volume trajectory, efficiency, PBs
3. Frontend renders raw numbers directly — NO LLM interpretation layer
4. This is the gap that needs to be filled

### Database Column Aliasing
- `Athlete.rpi` maps to DB column `vdot`: `rpi = Column('vdot', Float, nullable=True)`
- `TrainingPlan.baseline_rpi` maps to DB column `baseline_vdot`: `baseline_rpi = Column('baseline_vdot', Float, nullable=True)`
- No migration needed, no downtime risk

### Coach Tone Rules (in home.py prompt)
```
COACHING TONE RULES (non-negotiable):
- ALWAYS lead with what went well before raising concerns
- Frame load/fatigue concerns as FORWARD-LOOKING actions, not warnings
- NEVER contradict how the athlete says they feel
- NEVER quote raw metrics like TSB numbers, form scores, or load ratios
- You are a motivator and strategist, not a liability disclaimer
```

---

## Production Environment

- **Droplet:** `root@ubuntu-s-1vcpu-2gb-sfo2-01:/opt/strideiq/repo`
- **Deploy:** `cd /opt/strideiq/repo && git pull && docker compose -f docker-compose.prod.yml up -d --build --remove-orphans`
- **Flush Redis:** `docker compose -f docker-compose.prod.yml exec redis redis-cli FLUSHALL`
- **Run backend tests:** `docker compose run --rm api python -m pytest tests/ -x -q`
- **Run frontend tests:** `cd apps/web && npm test -- --watchAll=false`
- **Reclassify activities:** `docker compose -f docker-compose.prod.yml exec api python -c "from core.database import SessionLocal; from services.workout_classifier import WorkoutClassifierService; db=SessionLocal(); svc=WorkoutClassifierService(db); ..."`

---

## Codebase Stats

- **Total:** ~192K lines of code across 721 source files (Python + TypeScript + JavaScript)
- **Backend:** 149K lines Python (515 files)
- **Frontend:** 41K lines TypeScript/TSX (195 files)
- **Docs:** 107K lines markdown (281 files)
