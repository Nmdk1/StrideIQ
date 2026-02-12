# Session Handoff — February 11, 2026

## Read First: `docs/SESSION_HANDOFF_2026-02-08.md`
That file has full project context, founder principles, architecture, and deploy procedures. This note covers only what happened today and what's next.

---

## Session Summary

Stabilization session. Fixed Strava sync UI stuck at 100%, insight engine generating duplicates on wrong days, and deployed security fixes. Then conducted deep research on training plan improvements — the founder's identified highest-impact work.

---

## Current State

- **HEAD:** `a9a4967` on `main`
- **Droplet:** deployed and healthy, all 9 containers up
- **Repo:** private
- **CI:** Green through `935254d`. Three newer commits (`693f2c5`, `9f05d8d`, `a9a4967`) need CI verification — set repo public temporarily, confirm green, set private.

---

## Commits This Session (all on `main`, all deployed)

| Commit | What | Files |
|--------|------|-------|
| `bdec399` | Security: redact JWT from logs, pin deps, strip task result | `auth.py`, `requirements.txt`, `v1.py` |
| `e1d41f6` | CI: restore ai_coach helper, fix DayDetailPanel click | `ai_coach.py`, `DayDetailPanel.tsx` |
| `2447b90` | Strava: interval-driven timeout, remove dead result block | `StravaConnection.tsx` |
| `935254d` | Insights: stamp date from activity, clamp percentile title | `insight_aggregator.py` |
| `693f2c5` | Strava: post-processing progress phase (superseded by a9a4967) | `strava_tasks.py` |
| `9f05d8d` | Insights: dedup by type+date, update existing rows | `insight_aggregator.py` |
| `a9a4967` | Strava: split post-processing into separate background task | `strava_tasks.py` |

---

## What Was Fixed (Details Matter)

### Strava Sync

The sync UI showed "Syncing 2 of 2... 100%" and never cleared. Three layered causes:

1. **Frontend timeout was effect-driven** — `useEffect` only ran when `syncStatus?.status` changed. If the backend kept returning the same `progress` status, the 2-minute timeout never re-evaluated. Fixed with `setInterval` every 10s in `StravaConnection.tsx`.

2. **Task reported 100% at the START of the last activity**, not the end. Then ~37 seconds of post-processing (PB sync across 200 activities, derived signals, insights) ran while `PROGRESS` state persisted. The UI correctly showed "syncing" because the task WAS still running — but the user saw 100% and thought it was stuck.

3. **Real fix**: Split the Celery task. `sync_strava_activities_task` returns SUCCESS immediately after activity processing + `last_strava_sync` update. Heavy work runs in a new `post_sync_processing_task` (fire-and-forget). Spinner clears in seconds.

Key files: `apps/api/tasks/strava_tasks.py` (new `post_sync_processing_task`), `apps/web/components/integrations/StravaConnection.tsx`

### Insight Engine

Calendar day detail panel showed wrong insights on wrong days with duplicates piling up. Three bugs:

1. **Wrong day**: `GeneratedInsight.insight_date` defaulted to `date.today()`. Activity from Feb 10 synced on Feb 11 → insight landed on Feb 11. Fixed: defaults to `None`, stamped from `activity.start_time.date()`.

2. **Percentile inversion**: `100 - 100 = 0` → "Top 0% efficiency." Fixed: `max(1, round(100 - percentile))`.

3. **Duplicate accumulation**: `persist_insights` deduped by exact title. `"30-day volume: 201.5 miles"` != `"209.5 miles"` → both persisted. Fixed: dedup by `(athlete_id, insight_date, insight_type)` for rolling stats, `+ activity_id` for activity-linked. Existing rows UPDATE instead of inserting new ones. In-memory dedup key strips digits.

Key file: `apps/api/services/insight_aggregator.py`

### Docker Caching Gotcha

`docker compose up -d --build` can use cached layers even after `git pull`. Always verify build output shows actual steps, not `CACHED`. Use `docker compose build --no-cache <service>` when in doubt.

---

## NEXT SESSION: Training Plan Improvements

### The Decision

The founder will choose one of four options. **Do not start coding until they decide.** Present the options if they haven't read them yet.

### Option A: "Depth First"
Make marathon plans world-class before expanding distances. Complete all marathon archetypes, inject paces, add "why" narratives, implement weekly re-evaluation.

### Option B: "Breadth First"
Cover 5K/10K/half/marathon at minimum viable quality. Build 3-4 archetypes per distance.

### Option C: "Coach-Led Adaptive"
Generate 2-week rolling blocks. Coach explains and adjusts. Plans are emergent from coaching.

### Option D: "Hybrid" (Recommended)
Full-plan skeleton calendar for buy-in + coach adjusts weekly. Recommended execution:
1. Inject calculated paces + add "why" narratives (immediate)
2. Build half marathon and 10K archetypes (next)
3. Weekly re-evaluation by coach (following)
4. 2-week rolling blocks for full adaptive mode (later)

### Current Plan System (What Exists)

- **5 generators**: principle-based, model-driven, archetype-based, constraint-aware, hybrid
- **2 archetypes built**: `marathon_mid_6d_18w`, `marathon_mid_5d_18w` (in `plans/archetypes/`)
- **9 workout types**: easy, recovery, strides, long, tempo, threshold, intervals, hills, MP (in `plans/workouts/`)
- **Plan generation**: `apps/api/services/plan_generator.py`, `principle_plan_generator.py`, `model_driven_plan_generator.py`, `constraint_aware_planner.py`
- **Models**: `TrainingPlan`, `PlannedWorkout` in `apps/api/models.py`
- **Workout templates**: `WorkoutTemplate` model with `intensity_tier`, `phase_compatibility`, `progression_logic`
- **Coach modules**: `apps/api/services/coach_modules/` — routing, context, conversation

### Key Gaps
1. Only marathon — no 5K/10K/half
2. No calculated paces in workout cards (effort descriptions only)
3. No "why" explaining workout purpose
4. No weekly adaptation after missed/modified workouts
5. Plans are static, not living documents

### External Research Completed
- **Daniels**: VDOT/5-zone system, season periodization
- **Jon Green** (Verde Track Club): 2-week blocks, athlete education on "why", speed work for marathoners
- **McMillan**: Training Cycle Builder, 6-step system
- **TrainAsONE/Athletica.ai**: Daily AI adaptation, readiness scores, auto-rephasing
- **Academic**: LLM coaching case studies show gains but need persistent models and safety guardrails

---

## CRITICAL: Founder Principles (Violate These and You Lose Trust)

Read the full list in `docs/SESSION_HANDOFF_2026-02-08.md`. The non-negotiables:

1. **NEVER use VDOT** — trademarked. Internal term is **RPI**.
2. **NEVER dump raw metrics** — coach must translate TSB/CTL/form into coaching language.
3. **NEVER contradict how the athlete feels** — validate, then suggest.
4. **Coach-led, not dashboard-led** — every number needs context and actionability.
5. **N=1 data** — insights from the athlete's own data, not templates.

---

## Deploy Reference

```bash
# Standard deploy
cd /opt/strideiq/repo
git pull origin main
docker compose -f docker-compose.prod.yml up -d --build --remove-orphans
docker compose -f docker-compose.prod.yml ps

# Force rebuild (if caching issues)
docker compose -f docker-compose.prod.yml build --no-cache web
docker compose -f docker-compose.prod.yml build --no-cache api
docker compose -f docker-compose.prod.yml up -d

# CI: repo must be public for GitHub Actions (private repo has no free minutes)
# Set public → push → verify green → set private
```

---

## Untracked Files (not committed, intentional)
```
 M docs/SESSION_HANDOFF_2026-02-08.md
 M docs/SESSION_HANDOFF_2026-02-11.md
?? .github/scripts/
?? apps/api/coverage.xml
?? docs/P0_1_PRE_MERGE_PACKAGE.md
```
