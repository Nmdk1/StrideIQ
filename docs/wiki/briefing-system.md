# Morning Briefing System

## Current State

The morning briefing is the daily touchpoint — the athlete opens the app and sees an AI-generated briefing about their current state, today's plan, and what the system has noticed. It is the most complex prompt in the system and has been the source of repeated regressions.

## How It Works

### Architecture: Lane 2A

The briefing uses a two-lane architecture:

- **Lane 1 (Request path):** When the athlete opens the home page, `GET /v1/home` checks Redis for a cached briefing (`home_briefing:{athlete_id}`). If found, returns it immediately. The home endpoint **never blocks on LLM** — this is a hard infrastructure rule.

- **Lane 2A (Worker path):** A Celery task (`home_briefing_tasks.py`) generates the briefing asynchronously. It builds the full context, calls the LLM, and writes the result to Redis. The Lane 2A worker always passes `skip_cache=True` to bypass stale legacy cache keys.

- **Primary model (default):** **`claude-sonnet-4-6`** — `BRIEFING_PRIMARY_MODEL` in `apps/api/core/config.py`, selected by `resolve_briefing_model()` in `apps/api/core/llm_client.py` when Kimi canary routing does not apply.
- **Kimi canary cohort:** When `KIMI_CANARY_ENABLED` is true **and** the athlete UUID is listed in `KIMI_CANARY_ATHLETE_IDS`, briefings use **`KIMI_CANARY_MODEL`** (default **`kimi-k2.6`**).
- **Provider failures:** `call_llm` / `call_llm_with_json_parse` implement a fallback chain — **Anthropic → Gemini 2.5 Flash** for Sonnet-shaped primaries; **Kimi → Sonnet → Gemini** when the primary is Kimi (see `_FALLBACK_CHAIN` in `llm_client.py`).
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

**Honest workout-structure prompt (Apr 18, 2026):** Workout-structure prompt logic lives in `_render_workout_structure_block(c)` in `routers/home.py` and has three branches driven by `c["workout_structure"]` and the new `c["splits_available"]` flag:

1. **Structure found** — prompt names the structure and cross-checks against `run_shape.summary.workout_classification`. If they agree (track_intervals, threshold_intervals, hill_repeats, fartlek, tempo, over_under, progression, strides, anomaly), the LLM is told the average pace blends warmup/work/rest and to coach from the split breakdown. If they disagree, the LLM is told to trust the run_shape and treat the structure as secondary context.
2. **Splits available, no structure** — prompt says "NO STRUCTURED WORKOUT PATTERN — split-level analysis ran and found no interval/rep structure." Forbids inventing split-level data (fastest rep, slowest rep, rep count). Requires describing the run from overall metrics only.
3. **Splits not yet processed** — prompt says "SPLIT-LEVEL ANALYSIS NOT YET AVAILABLE — describe it using overall metrics only." Forbids inventing split-level data and forbids making claims about whether the run was structured. Replaces the older false claim that "the analysis system examined the splits and determined this was a CONTINUOUS run" — that wording lied when splits hadn't landed yet.

The `splits_available` flag is computed in both the request path (`routers/home.py`) and the worker path (`tasks/home_briefing_tasks.py`) by checking `ActivitySplit` rows for `today_actual.id`. The flag also feeds `_build_data_fingerprint`, so the brief regenerates when splits land asynchronously.

### Guardrails

- **Environmental comparison discipline:** Prompt explicitly forbids comparing runs across seasons without accounting for heat/humidity. Uses `heat_adjustment_pct` and dew point data.
- **Sleep source contract:** Only cite Garmin-measured sleep
- **Date labels:** All activity dates include pre-computed relative labels — LLM never computes relative time
- **Deterministic path:** `compute_coach_noticed` provides deterministic signals separate from LLM generation
- **No prescriptive claims:** Briefing acknowledges cross-training load but does not predict how the athlete will feel
- **Morning-voice content gates (Apr 18, 2026):** `validate_voice_output` enforces four content gates on the `morning_voice` and `coach_noticed` fields. Failures trigger `_strip_disallowed_sentences`, which removes only the offending sentences and re-validates the remainder; only when nothing usable remains do we publish the deterministic fallback. Preserves the ~80% of good content in a partially-bad briefing instead of nuking it.

  | Gate | Trigger | Why |
  |------|---------|-----|
  | `interrogative` | any `?` in the field | morning_voice is one-way; questions belong to the chat coach |
  | `multi_topic` | "Separately,", "Additionally,", "Also,", "Meanwhile,", "On another note,", "Beyond that," | morning_voice should land one specific point, not a digest |
  | `meta_preamble` | "Your data shows", "worth discussing/noting", "I've noticed a pattern", "Looking at your data", "The data suggests" | the athlete already knows we looked at their data |
  | `sentence_cap` | >3 sentences in `morning_voice` | enforces the 2-3 sentence contract |

  **Source-side fix (paired):** `build_fingerprint_prompt_section` gains `include_emerging_question` kwarg. The morning_voice lane in `generate_coach_home_briefing` and `_build_rich_intelligence_context` passes `False`, which rewrites the EMERGING PATTERN block as a low-confidence observation with explicit "do not lead, do not ask a question" guidance. The chat coach (`coach_tools/brief.py`) keeps the question.

### Scheduling

- **Morning intelligence task** (`run_morning_intelligence`): Fires at ~5 AM local time
- **Beat startup dispatch** (`beat_startup_dispatch.py`): On container start, checks if daily tasks have run in the last 20 hours. If not, dispatches immediately. This makes the pipeline deployment-proof — previously, daily tasks never fired because the beat container was recreated on every deploy before 4 AM.

## Key Decisions

- **Lane 2A architecture** — briefing is always pre-generated, never blocks the request path
- **Deterministic + LLM hybrid** — `compute_coach_noticed` provides structural signals, LLM provides natural language
- **10-day activity window** (Apr 8, 2026) — previously unbounded `.limit(5)` allowed 16-day-old runs to appear under "This Week's Training"
- **5-gate workout structure** (Apr 7, 2026) — prevents false interval detection on easy runs with natural pace variation

## Timezone: Home vs. Current (Two-Timezone Model)

The briefing uses two distinct timezone concepts — **do not conflate them:**

| Concept | Source | Used for |
|---|---|---|
| **Home timezone** (`Athlete.timezone`) | GPS mode over 30 activities/90 days, or first Strava OAuth | Training day/week windows, plan schedule, streak accounting |
| **Effective timezone** (`get_athlete_effective_timezone()`) | Most recent GPS activity within 72 hours | `local_now` passed to prompt — determines time-of-day period ("morning" / "afternoon" / "evening") for natural-language phrasing |

**How it works:** `get_athlete_effective_timezone()` queries the most recent GPS activity within the last 72 hours. If it's in a different timezone than the athlete's home, that travel timezone is returned. When the athlete runs at home again, the effective timezone automatically reverts to home. Nothing is ever written to `Athlete.timezone` — it is read-only from this function.

**Fingerprint:** The briefing fingerprint includes `tz:{effective_timezone}` so that traveling to a new timezone triggers a fresh LLM generation with the correct local-time period, and returning home triggers another fresh generation.

**Root cause fixed (Apr 24, 2026):** The NC trip bug — where a single run in Cary, NC set `home = America/New_York` for a Mississippi athlete permanently — was caused by `infer_and_persist_athlete_timezone` picking the most-recent GPS activity (which happened to be an Eastern-timezone trip) rather than the mode. Fixed by using modal GPS timezone across last 30 activities.

## Clock Time Removed from Briefing (Apr 24, 2026)

The LLM system prompt previously included `The athlete's current local time is {HH:MM AM/PM}`. This caused two problems:

1. **Immediately stale**: the briefing is pre-generated (Lane 2A), so by the time the athlete reads it the stated time can be 30–60 minutes old.
2. **Zero information value**: the athlete has a clock on their device at all times.

**Fix:** `_call_opus_briefing_sync` in `routers/home.py` now passes only the time-of-day *period* (`morning` / `afternoon` / `evening`) to the system prompt, with an explicit instruction: *"Do NOT state or repeat the clock time — the athlete already has a clock."* Natural relative phrasing ("this morning", "tonight") is still enabled via the period label. The `_time_str` computation is removed entirely.

## Timezone History Bug Fixed

Previous (broken): `Athlete.timezone` was set from a single "most recent" GPS activity → one trip to Eastern time zone during a NC race poisoned home timezone permanently.

Current (correct): `infer_and_persist_athlete_timezone` samples last 30 GPS activities in 90 days, uses mode → single trips don't affect home timezone.



- **Briefing regressions** — this is the most fragile surface. Changes to the prompt assembly or intelligence sources have caused repeated regressions. The advisor has had to make significant fixes after builder changes. **Approach with extreme caution.**
- **Cache invalidation:** The Lane 2A worker writes to `home_briefing:{athlete_id}` but the request path also checks the legacy `coach_home_briefing:{hash}` key. Stale legacy keys can silently block Lane 2A writes if `skip_cache=True` is not passed.
- **Briefing questions are rhetorical:** Emerging pattern questions in the briefing have no response mechanism. The briefing-to-coach flow (approved design, not yet built) would make them tappable.

## What's Next

- **Briefing-to-coach response loop:** Tappable emerging patterns → coach chat with `finding_id` pre-loaded → athlete responds → fact extraction → lifecycle classifier
- **Specificity fix:** ✅ SHIPPED (Apr 2026). Findings translate into athlete's preferred units via `CoachUnits` helper. Backend passes unit-aware `distance_text`, `pace`, `elevation_text` in LLM context. LLM system prompt includes `preferred_units` directive.
- **Environmental comparison fix:** Pre-filter comparisons for similar conditions or explicitly instruct LLM (SEASONAL COMPARISON DISCIPLINE shipped in the briefing prompt)

## Sources

- `apps/api/core/llm_client.py` — `resolve_briefing_model`, `call_llm`, `call_llm_with_json_parse`, provider fallback chain
- `apps/api/core/config.py` — `BRIEFING_PRIMARY_MODEL`, `KIMI_CANARY_*`, `KIMI_CANARY_MODEL`
- `apps/api/routers/home.py` — prompt assembly, workout structure detection, `_call_opus_briefing_sync`
- `apps/api/tasks/home_briefing_tasks.py` — Lane 2A worker
- `apps/api/services/coach_tools/brief.py` — `build_athlete_brief`
- `apps/api/services/coach_tools/wellness.py` — wellness trends
- `apps/api/services/fingerprint_context.py` — fingerprint prompt section
- `apps/api/tasks/beat_startup_dispatch.py` — deployment-proof scheduling
- `docs/BUILD_SPEC_HOME_AND_ACTIVITY.md` — home page spec
- `docs/BUILDER_INSTRUCTIONS_2026-03-09_HOME_PAGE_INTELLIGENCE.md` — intelligence lanes
