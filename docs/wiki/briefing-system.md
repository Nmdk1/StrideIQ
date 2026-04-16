# Morning Briefing System

## Current State

The morning briefing is the daily touchpoint — the athlete opens the app and sees an AI-generated briefing about their current state, today's plan, and what the system has noticed. It is the most complex prompt in the system and has been the source of repeated regressions.

## How It Works

### Architecture: Lane 2A

The briefing uses a two-lane architecture:

- **Lane 1 (Request path):** When the athlete opens the home page, `GET /v1/home` checks Redis for a cached briefing (`home_briefing:{athlete_id}`). If found, returns it immediately. The home endpoint **never blocks on LLM** — this is a hard infrastructure rule.

- **Lane 2A (Worker path):** A Celery task (`home_briefing_tasks.py`) generates the briefing asynchronously. It builds the full context, calls the LLM, and writes the result to Redis. The Lane 2A worker always passes `skip_cache=True` to bypass stale legacy cache keys.

- **Primary model:** Claude Opus 4.6 (highest reasoning quality)
- **Fallback:** Gemini 2.5 Flash (if Opus unavailable)
- **Cache key:** `home_briefing:{athlete_id}` (written by Lane 2A)
- **Legacy key:** `coach_home_briefing:{athlete_id}:{data_hash}` (request path only, being phased out)

### Prompt Assembly

The briefing prompt is assembled in `generate_coach_home_briefing()` in `routers/home.py` (line ~1938). It gathers **8+ intelligence sources:**

1. **Athlete brief** — full context from `build_athlete_brief()` in `services/coach_tools/brief.py`
2. **Today's completed activity** — if the athlete ran today, includes distance, pace, HR, elevation, temperature, humidity, heat adjustment
3. **Workout structure** — from `_summarize_workout_structure()` if detected (5-gate architecture)
4. **Planned workout** — from `PlannedWorkout` if one exists for today
5. **Check-in data** — readiness, sleep, soreness from `DailyCheckin`
6. **Wellness trends** — 28-day check-in trends via `get_wellness_trends()`
7. **Recent runs** — last 5 runs within 10 days (date-bounded, not unbounded `.limit(5)`)
8. **Personal fingerprint** — confirmed correlation findings with layer data via `build_fingerprint_prompt_section()`
9. **Race countdown** — days to race if one exists
10. **Cross-training context** — recent non-run activities (last 48 hours)

### Workout Structure Detection

`_summarize_workout_structure()` in `routers/home.py` (line ~1722) detects structured workouts from mile split data. Rebuilt Apr 7, 2026 with a 5-gate architecture:

1. **Shape-extractor veto:** If `activity.run_shape` classifies as `easy_run`/`long_run`/`medium_long_run`/`gray_zone_run`, return None immediately
2. **Elevation gate:** If hilly terrain (>50ft/mi gain) and GAP is steady (CV < 0.08), return None
3. **Alternating pattern:** Require ≥2 W/R transitions, work:rest ratio ≤ 3:1
4. **Work rep consistency:** CV < 0.50 on rep distances
5. **Pace gap:** ≥45s/mi differential between avg work and avg rest

Threshold: `median * 0.92` (must be ≥8% faster than median to qualify as "work").

**Prompt authority:** When `shape_classification` disagrees with structure detection, the prompt tells the LLM to trust `run_shape` and treat structure as secondary context.

**Explicit null-structure guardrail:** When `_summarize_workout_structure` returns `None`, the prompt injects: "NO WORKOUT STRUCTURE DETECTED — the analysis system examined the splits and determined this was a CONTINUOUS run, NOT intervals or repeats. Do NOT describe this run as intervals, reps, repeats, or any structured workout. Do NOT invent split-level data." This `else` branch (line ~2273 in `home.py`) was added to kill the interval hallucination bug at the prompt level — the LLM was inventing structure even when the detection system found none.

### Guardrails

- **Environmental comparison discipline:** Prompt explicitly forbids comparing runs across seasons without accounting for heat/humidity. Uses `heat_adjustment_pct` and dew point data.
- **Sleep source contract:** Only cite Garmin-measured sleep
- **Date labels:** All activity dates include pre-computed relative labels — LLM never computes relative time
- **Deterministic path:** `compute_coach_noticed` provides deterministic signals separate from LLM generation
- **No prescriptive claims:** Briefing acknowledges cross-training load but does not predict how the athlete will feel

### Scheduling

- **Morning intelligence task** (`run_morning_intelligence`): Fires at ~5 AM local time
- **Beat startup dispatch** (`beat_startup_dispatch.py`): On container start, checks if daily tasks have run in the last 20 hours. If not, dispatches immediately. This makes the pipeline deployment-proof — previously, daily tasks never fired because the beat container was recreated on every deploy before 4 AM.

## Key Decisions

- **Lane 2A architecture** — briefing is always pre-generated, never blocks the request path
- **Deterministic + LLM hybrid** — `compute_coach_noticed` provides structural signals, LLM provides natural language
- **10-day activity window** (Apr 8, 2026) — previously unbounded `.limit(5)` allowed 16-day-old runs to appear under "This Week's Training"
- **5-gate workout structure** (Apr 7, 2026) — prevents false interval detection on easy runs with natural pace variation

## Known Issues

- **Briefing regressions** — this is the most fragile surface. Changes to the prompt assembly or intelligence sources have caused repeated regressions. The advisor has had to make significant fixes after builder changes. **Approach with extreme caution.**
- **Cache invalidation:** The Lane 2A worker writes to `home_briefing:{athlete_id}` but the request path also checks the legacy `coach_home_briefing:{hash}` key. Stale legacy keys can silently block Lane 2A writes if `skip_cache=True` is not passed.
- **Briefing questions are rhetorical:** Emerging pattern questions in the briefing have no response mechanism. The briefing-to-coach flow (approved design, not yet built) would make them tappable.

## What's Next

- **Briefing-to-coach response loop:** Tappable emerging patterns → coach chat with `finding_id` pre-loaded → athlete responds → fact extraction → lifecycle classifier
- **Specificity fix:** Translate findings into athlete's training units (pace/mi, miles, hours, counts), not vague descriptions
- **Environmental comparison fix:** Pre-filter comparisons for similar conditions or explicitly instruct LLM

## Sources

- `apps/api/routers/home.py` — prompt assembly, workout structure detection
- `apps/api/tasks/home_briefing_tasks.py` — Lane 2A worker
- `apps/api/services/coach_tools/brief.py` — `build_athlete_brief`
- `apps/api/services/coach_tools/wellness.py` — wellness trends
- `apps/api/services/fingerprint_context.py` — fingerprint prompt section
- `apps/api/tasks/beat_startup_dispatch.py` — deployment-proof scheduling
- `docs/BUILD_SPEC_HOME_AND_ACTIVITY.md` — home page spec
- `docs/BUILDER_INSTRUCTIONS_2026-03-09_HOME_PAGE_INTELLIGENCE.md` — intelligence lanes
