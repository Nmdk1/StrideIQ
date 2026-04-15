# Phase 2 Build Instructions — Say Something Worth Hearing

**Date:** April 12, 2026
**From:** Advisor
**To:** Opus builder (continuing from Phase 1)
**Status:** Phase 1 deployed and verified. This is Phase 2.

---

## Phase 1 Recap (DONE — do not re-implement)

Phase 1 shipped in commit `3ec6a95`. Changes:
- `workout_classifier.py`: Added `PACING` type, keyword detection before race keywords
- `run_analysis_engine.py`: Wired stored `workout_type` as primary classification source
- `run_attribution.py`: Cardiac decoupling for controlled-steady runs, suppressed Tier 3/4 fallback
- `activity_workout_type.py`: Added "pacing" to frontend selector

Verified on production: Hattiesburg run now returns "Well Coupled — HR stayed stable relative to pace (+1.2% drift). Aerobically controlled." instead of "Efficiency 7.2% worse. Check for fatigue or illness."

---

## Phase 2: Three Changes

Build order: 2A → 2B → 2C. Each is independently deployable.

---

### 2A. Longitudinal Comparison on Decoupling Attribution

**File:** `apps/api/services/run_attribution.py`
**Function:** `_get_decoupling_attribution()`

**What exists now:** Returns a single-point insight: "HR stayed stable relative to pace (+1.2% drift)."

**What to add:** Query `CachedStreamAnalysis` for historical drift on similar-effort runs. Add trend data to the attribution.

**Implementation:**

1. Add a function `_get_drift_history(athlete_id, activity, db) -> List[dict]`:
   - Query `CachedStreamAnalysis` joined to `Activity` where:
     - Same `athlete_id`
     - `Activity.workout_type` is in `CONTROLLED_STEADY_TYPES` (imported from `run_analysis_engine.py`)
     - `Activity.start_time` within last 90 days, before current activity
     - `Activity.id != activity.id`
   - Extract `result_json["drift"]["cardiac_pct"]` from each row
   - Return list of `{"date": activity.start_time.date(), "drift_pct": cardiac_pct, "distance_m": activity.distance_m}` sorted by date ascending
   - Minimum 3 entries to compute trend. If fewer, return empty list.

2. Modify `_get_decoupling_attribution()`:
   - Call `_get_drift_history()`
   - If history exists (≥3 points):
     - Compute simple trend: compare today's drift to the average of the oldest 3 entries
     - Add longitudinal context to the `insight` string
     - Add `trend` and `history` to the `data` dict
   - Example output when improving:
     ```
     title: "Well Coupled"
     insight: "HR stayed stable relative to pace (+1.2% drift). Your last 5 similar efforts averaged 4.8% — trending down."
     data: {
       "cardiac_decoupling_pct": 1.2,
       "method": "cardiac_decoupling",
       "trend": "improving",
       "trend_avg_pct": 4.8,
       "trend_sample_size": 5,
       "trend_oldest_date": "2026-01-15"
     }
     ```
   - Example when stable: "...Your similar efforts have been stable around 1-2% drift." (trend: "stable")
   - Example when insufficient history: keep current behavior, no trend fields in data.

**Athlete Trust Safety Contract note:** Cardiac decoupling is NOT in `OUTPUT_METRIC_REGISTRY` because it's not a correlation engine output. It's a direct physiological metric where lower IS better (less drift = more stable). Directional language ("trending down", "improving") is safe here because the polarity is unambiguous — unlike efficiency (speed/HR) which is ambiguous per the contract. But use "trending down" as the primary phrasing rather than "improving" to stay close to the data.

**Test:** Run against the Hattiesburg activity on production. Verify historical drift data is pulled and trend is computed. If there aren't 3+ controlled-steady runs with cached drift in the last 90 days, the output should be identical to Phase 1 (no trend, no crash).

---

### 2B. Activity-Relevant Finding Filter

**File:** `apps/api/routers/activities.py`
**Function:** `get_activity_findings()` (line 885)

**What exists now:** Returns global top-3 active findings by `times_confirmed`. Same 3 findings on every activity.

**What to change:** Filter findings to those whose `input_name` is relevant to THIS activity's actual pre-state.

**Implementation:**

1. Build a map of this activity's pre-state values. Use the existing `_CHECKIN_FIELD_MAP` pattern from `services/operating_manual.py` (line 722):

   ```python
   _INPUT_TO_PRESTATE = {
       "sleep_hours": ("checkin", "sleep_h"),
       "sleep_quality_1_5": ("checkin", "sleep_quality_1_5"),
       "hrv_rmssd": ("checkin", "hrv_rmssd"),
       "stress_1_5": ("checkin", "stress_1_5"),
       "readiness_1_5": ("checkin", "readiness_1_5"),
       "soreness_1_5": ("checkin", "soreness_1_5"),
       "motivation_1_5": ("checkin", "motivation_1_5"),
       "resting_hr": ("checkin", "resting_hr"),
   }
   ```

2. Get the `DailyCheckin` for activity date. Build `actual_values: Dict[str, float]` from the checkin fields.

3. Query active findings (same as now: `is_active`, `times_confirmed >= 3`, not suppressed).

4. For each finding, check relevance:
   - If `finding.input_name` is not in `actual_values` → skip (no data for this input on this day)
   - If `finding.threshold_value` is not None:
     - Check if the actual value crossed the threshold in the relevant direction
     - `finding.threshold_direction == "above"`: relevant if `actual_value > threshold_value`
     - `finding.threshold_direction == "below"`: relevant if `actual_value < threshold_value`
     - If the actual value did NOT cross → skip (the finding's condition wasn't triggered today)
   - If no `threshold_value` on the finding: include it if the input has data (Layer 1 threshold detection hasn't run for this finding yet — still worth showing if the input was present)

5. Return up to 3 relevant findings, ordered by `times_confirmed` desc.

6. If zero findings are relevant → return empty list. **Zero is a valid answer.**

**Important:** The existing `FindingAnnotation` response schema stays the same. Only the filtering logic changes. No new endpoint, no schema change.

**Edge case:** Activity pre-state might come from `Activity.pre_sleep_h` and `Activity.pre_recovery_hrv` directly (populated at sync time from the closest checkin). If `DailyCheckin` for the exact activity date doesn't exist, fall back to these `Activity`-level fields:
- `activity.pre_sleep_h` → maps to input_name `"sleep_hours"`
- `activity.pre_recovery_hrv` → maps to input_name `"hrv_rmssd"`

**Test:** Find an activity where the founder slept < 6 hours. If there's an active finding with `input_name="sleep_hours"` and `threshold_value` around 6-7, that finding should appear. On a day with 8 hours of sleep, the same finding should NOT appear (threshold not crossed).

---

### 2C. Longitudinal Comparison on Non-Decoupling Attributions

**File:** `apps/api/services/run_attribution.py`

This extends the longitudinal pattern from 2A to the speed/HR efficiency path (non-controlled-steady runs).

**What to add to `get_efficiency_attribution()` for structured/quality/race runs:**

When the function already has `similar_activities` (Tier 1 or Tier 2 peers) and has computed `diff_pct`, add trend context:

1. If `len(similar_activities) >= 5`:
   - Sort peers by `start_time`
   - Compare current efficiency to oldest-3 average and newest-3 average
   - If trending direction is consistent, add to insight: "Efficiency trending {up/down} over your last {N} {workout_type}s."
2. Add trend data to `data` dict: `"trend": "improving"|"stable"|"declining"`, `"trend_sample_size": N`

**Athlete Trust Safety Contract note:** Efficiency (speed/HR) IS polarity-ambiguous per the contract. DO NOT use "improving" or "declining" in athlete-facing text for this metric. Use neutral language: "Efficiency trending higher over your last 6 tempo runs" (factual direction without value judgment). The contract in `.cursor/rules/athlete-trust-efficiency-contract.mdc` is binding.

---

## Files You Will Modify

| File | Change |
|------|--------|
| `apps/api/services/run_attribution.py` | 2A: Add `_get_drift_history()`, modify `_get_decoupling_attribution()` for longitudinal context. 2C: Add trend to speed/HR efficiency path. |
| `apps/api/routers/activities.py` | 2B: Rewrite `get_activity_findings()` filtering logic. |

## Files You Will Read (not modify)

| File | Why |
|------|-----|
| `apps/api/services/operating_manual.py` lines 722-740 | `_CHECKIN_FIELD_MAP` pattern for input_name → field mapping |
| `apps/api/models.py` | `CachedStreamAnalysis` schema, `CorrelationFinding.threshold_value/threshold_direction`, `Activity.pre_sleep_h/pre_recovery_hrv`, `DailyCheckin` fields |
| `apps/api/services/stream_analysis_cache.py` | `CURRENT_ANALYSIS_VERSION` constant for cache queries |
| `apps/api/services/run_analysis_engine.py` | `CONTROLLED_STEADY_TYPES` (already imported in run_attribution.py) |

## Evidence Required

For each change (2A, 2B, 2C):
1. Show the diff
2. Run against a real activity on production (copy script to server, run inside container)
3. Paste the JSON output showing the new fields/filtering working
4. CI green before deploy

## What NOT to Do

- Do NOT modify the `INTELLIGENCE_VOICE_SPEC.md` or any builder instruction docs
- Do NOT create new API endpoints — modify existing response content only
- Do NOT touch frontend files
- Do NOT modify `workout_classifier.py` or `run_analysis_engine.py` — Phase 1 is done
- Do NOT add LLM calls — all Phase 2 insights are deterministic
- Do NOT use "improving" or "declining" for efficiency (speed/HR) metrics — Athlete Trust Safety Contract
