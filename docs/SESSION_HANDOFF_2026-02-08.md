# Session Handoff - February 8, 2026

## Session Summary

This session fixed critical issues with the Efficiency Factor (EF) attribution system, workout classification pipeline, and the AI coach's tone/framing on the Home page. All changes driven by real-world athlete feedback from a 20-mile breakthrough long run.

---

## 1. Efficiency Factor (EF) Formula Correction

**Problem:** EF was calculated as `pace / HR` (lower = better), which is mathematically inverted. The correct definition is `speed / HR` (higher = better). This caused breakthrough runs to be flagged as "Low Efficiency."

**Solution:**
- Rewrote `_compute_gap_efficiency()` to compute EF as `speed_mps / avg_hr`
- Uses distance-weighted GAP (Grade Adjusted Pace) from `ActivitySplit` records when available, falling back to raw speed
- GAP normalizes for elevation so hilly runs aren't penalized
- Flipped all comparison thresholds (`diff_pct > 5` = "Very Efficient", etc.)
- Added `method` field ("gap" or "raw_pace") to attribution data

**Files Changed:**
- `apps/api/services/run_attribution.py` — `_compute_gap_efficiency()`, `get_efficiency_attribution()`

---

## 2. Tiered Comparison Logic for Efficiency

**Problem:** Efficiency was compared against ALL recent runs regardless of type. A 20-mile long run was being compared to 5K tempos and easy recovery runs, producing misleading results.

**Solution:**
- Implemented 4-tier comparison fallback:
  1. Same workout type + similar distance (+-30%, 90 days, min 2 runs)
  2. Same workout type, any distance (90 days, min 2 runs)
  3. Similar distance only (+-30%, 90 days, min 3 runs, lower confidence)
  4. All recent runs (28 days, min 5 runs, lowest confidence)
- Extended lookback from 28 to 90 days for type-specific comparisons (athletes do 1-2 long runs/month)

**Files Changed:**
- `apps/api/services/run_attribution.py` — `get_efficiency_attribution()`

---

## 3. Workout Classification on Strava Sync

**Problem:** `WorkoutClassifierService` was never called during Strava activity ingestion. All recent runs had `workout_type: N/A`, preventing type-based efficiency comparisons.

**Solution:**
- Integrated `WorkoutClassifierService.classify_activity()` into the Strava sync task
- Runs after activity creation, performance metrics, and PB updates
- Sets `workout_type`, `workout_zone`, `workout_confidence`, `intensity_score`
- Reclassified all 346 existing activities on production

**Files Changed:**
- `apps/api/tasks/strava_tasks.py` — added classification call in sync loop

---

## 4. Long Run Classification Fix

**Problem:** `_classify_steady_state()` classified long, low-intensity runs (e.g., 20 miles at 122 HR) as `recovery_run` instead of `long_run` because it checked intensity before distance.

**Solution:**
- Reordered classification logic to check distance/duration thresholds first
- Runs over 90min or 20km are classified as `long_run` regardless of intensity
- Runs over 60min or 15km are classified as `medium_long_run`
- Only shorter runs at very low intensity get `recovery_run`

**Files Changed:**
- `apps/api/services/workout_classifier.py` — `_classify_steady_state()`

---

## 5. Splits Table Cumulative Time

**Problem:** The "Time" column in the activity splits table showed per-split duration instead of cumulative elapsed time.

**Solution:**
- Added `cumulativeTime` accumulator in the splits mapping logic
- Table renders cumulative time for each row

**Files Changed:**
- `apps/web/components/activities/SplitsTable.tsx`

---

## 6. Coach Tone Guardrails (LLM Prompt Engineering)

**Problem:** The AI coach on the Home page was:
1. Quoting raw metrics verbatim ("your current form of -16.2")
2. Contradicting how the athlete reported feeling ("you say fine but you're actually fatigued")
3. Leading with warnings and injury risk language after positive experiences
4. Acting as a liability disclaimer instead of a motivating coach

**Solution:**

### Gemini System Prompt (home.py)
Added explicit COACHING TONE RULES:
- Always lead with what went well before raising concerns
- Frame load concerns as forward-looking actions, not warnings/diagnoses
- Never contradict athlete's self-reported feelings
- Never quote raw metrics (TSB, CTL, form scores) — translate to coaching language
- Be a motivator and strategist, not a liability disclaimer

### Field Descriptions
- `coach_noticed`: "Lead with progress or positive trends"
- `today_context`: "Celebrate the effort first, then frame next steps"
- `checkin_reaction`: "Acknowledge how they feel FIRST, then guide next steps. Never contradict their self-report."

### Athlete Brief Data Labels (coach_tools.py)
- Tagged Training State and Recovery sections with `(INTERNAL — use to reason but NEVER quote raw numbers to the athlete)`
- Raw CTL/ATL/TSB data stays in the brief so the LLM can reason correctly
- LLM translates dynamically based on full context instead of hardcoded if/elif

**Files Changed:**
- `apps/api/routers/home.py` — system prompt, field descriptions
- `apps/api/services/coach_tools.py` — `build_athlete_brief()`, `get_training_load()` narrative

---

## 7. Test Fix: Timezone-Aware Datetime Comparison

**Problem:** `test_strava_token_refresh.py` had a pre-existing `TypeError: can't subtract offset-naive and offset-aware datetimes`.

**Solution:**
- Ensured both sides of the comparison are timezone-aware before subtraction
- Added defensive `replace(tzinfo=timezone.utc)` for DB values that may be naive

**Files Changed:**
- `apps/api/tests/test_strava_token_refresh.py`

---

## 8. Cleanup

- Stripped trailing whitespace from all modified files
- Deleted temporary diagnostic scripts (`scripts/prod_check_ef.py`, `scripts/check_long_runs.py`)
- Flushed Redis coach briefing cache on production

---

## Test Results

- **Backend:** 1428 passed, 7 skipped
- **Frontend:** 116 passed (20 suites)

---

## Commits (chronological)

1. `2080244` — fix: splits table Time column shows cumulative elapsed time
2. `5bb7729` — fix: efficiency attribution compares against similar runs
3. `939a597` — fix: strava token refresh test timezone comparison
4. `4482914` — fix: efficiency attribution uses GAP from splits + same workout type
5. `8e1b5e1` — fix: auto-classify workout type on Strava sync
6. `bf3d3ab` — fix: long runs at low intensity classified as long_run
7. `bb94030` — fix: EF formula corrected to speed/HR (higher=better)
8. `2bd9572` — Coach tone: add LLM guardrails for raw metric parroting and negative framing
9. (pending) — chore: strip trailing whitespace, cleanup temp scripts, session docs

---

## Key Design Decisions

1. **EF = speed/HR, not pace/HR.** Higher EF means more ground covered per heartbeat. This is the standard definition used in exercise physiology.

2. **LLM translates metrics, code doesn't.** Raw data stays in the athlete brief for the LLM to reason from. The prompt instructs the LLM to never quote raw numbers. This handles infinite context variety without hardcoded string mappings.

3. **90-day lookback for type comparisons.** Long runs happen 1-2x/month. A 28-day window often yields 0-1 comparisons, forcing fallback to dissimilar run types.

4. **GAP from splits, not activity-level.** GAP data lives on `ActivitySplit.gap_seconds_per_mile`. Distance-weighted average across splits gives the most accurate EF for hilly routes.

---

## Production State

- All changes deployed to droplet
- Redis cache flushed to force new coach briefing generation
- 346 activities reclassified with correct workout types
