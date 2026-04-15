# Builder Note — Sleep Data Prompt Grounding Fix

**Date:** February 24, 2026
**Priority:** High (athlete trust — coach cited wrong sleep number in morning briefing)
**Status:** SHIPPED — commit `494b9e9`
**Owner:** Builder agent

---

## Read order (mandatory)

1. `docs/FOUNDER_OPERATING_CONTRACT.md`
2. `docs/SESSION_HANDOFF_2026-02-24_STRIPE_AND_GARMIN_REVIEW.md`
3. `apps/api/routers/home.py` — `generate_coach_home_briefing`, `_build_rich_intelligence_context`, validator
4. `apps/api/tasks/home_briefing_tasks.py` — `_build_briefing_prompt`
5. `apps/api/services/coach_tools.py` — `get_wellness_trends`, `build_athlete_brief`
6. `apps/api/models.py` — `DailyCheckin`, `GarminDay` (calendar_date semantics)
7. This document

---

## Problem statement (verified, now fixed)

The home morning briefing cited "7.5h sleep last night" when:
- Athlete slept 6h45 (Garmin device measurement)
- Athlete entered 7.0h on the check-in slider

This was not corrupted stored data. Three layered prompt construction failures caused the LLM to cite the wrong number.

---

## What shipped (commit `494b9e9`)

### Fix 1 — Today's sleep_h numeric added to prompt

**Root cause:** `checkin_data_dict` was built with only `sleep_label` ("Great"/"OK"), not the numeric `sleep_h`. The LLM got "Sleep Great" but no hours, then borrowed whatever numeric it found in historical context.

**Files changed:**
- `apps/api/routers/home.py` — new `_build_checkin_data_dict()` helper, single source of truth for both the request path and the Celery worker path. Now includes `sleep_h` numeric.
- `apps/api/tasks/home_briefing_tasks.py` — uses the same helper.
- Prompt line updated to: `"TODAY_CHECKIN_SLEEP_HOURS: {sleep_h}h"` with explicit grounding label.

### Fix 2 — Wellness trends recency prefix

**Root cause:** `get_wellness_trends` narrative was `"Sleep avg 7.2h (trend: improving)"` — no date attribution. Historical values were indistinguishable from last night.

**File changed:** `apps/api/services/coach_tools.py` — `get_wellness_trends` now prepends:
```
Most recent entry (2026-02-24): sleep=7.0h | stress=2/5 | soreness=2/5…
28-day avg: 6.9h (trend: stable).
```

### Fix 3 — Garmin device sleep added as ground truth source

**Root cause:** `GarminDay.sleep_total_s` was never queried for the home briefing. Device-measured sleep (highest fidelity, no rounding) was completely absent from the prompt.

**File changed:** `apps/api/routers/home.py` — `_build_rich_intelligence_context` now adds Source 0 before all other sources:
```
--- Last Night (Garmin device — use as ground truth for sleep) ---
Device-measured sleep last night: 6.75h (Garmin, calendar_date=2026-02-25)
Sleep score: 78/100 (GOOD)
Overnight HRV: 52ms
Resting HR: 48bpm
```

**Calendar date semantics (critical):** `calendar_date` is the wakeup day (Garmin's convention). Monday night's sleep → `calendar_date = Tuesday`. Query `today` first; fall back to `yesterday` if not yet pushed (common before Garmin syncs in the morning).

### Fix 4 — Sleep validator

**File changed:** `apps/api/routers/home.py` — new `validate_sleep_claims()` function. Scoped to sleep-context sentences only (false-positive safe on workout durations). 0.5h tolerance. Suppresses `morning_voice` to fallback text if the cited value deviates > 0.5h from both device and manual sources.

Both request path and Celery task wired to validator.

### Fix 5 — SLEEP SOURCE CONTRACT in prompt

Prompt now includes explicit contract:
```
SLEEP SOURCE CONTRACT:
- TODAY_CHECKIN_SLEEP_HOURS: {sleep_h}h (athlete-reported, from slider)
- GARMIN_LAST_NIGHT_SLEEP_HOURS: {garmin_h}h (device-measured, highest fidelity)
- When citing last night's sleep, use GARMIN value if available, else TODAY_CHECKIN value.
- Do NOT synthesize or average these values. Do NOT cite historical wellness averages as "last night."
```

---

## Tests (22 new, all passing)

File: `apps/api/tests/test_sleep_prompt_grounding.py`

Covers:
- `test_today_sleep_h_in_checkin_data_dict`
- `test_wellness_trends_recency_label`
- `test_garmin_sleep_in_rich_context`
- `test_garmin_sleep_calendar_date_fallback` (yesterday fallback)
- `test_validator_suppresses_wrong_sleep_number`
- `test_validator_false_positive_safe_on_workout_durations` (P0.2 gate)
- All 9 AC contracts

**Test result: 95 passed, 13 skipped (DB-only), 0 failed.**

---

## Files changed

| File | Change |
|---|---|
| `apps/api/routers/home.py` | `_build_checkin_data_dict()` helper, `_get_garmin_sleep_h_for_last_night()`, SLEEP SOURCE CONTRACT in prompt, `validate_sleep_claims()`, Source 0 in `_build_rich_intelligence_context` |
| `apps/api/tasks/home_briefing_tasks.py` | Uses shared `_build_checkin_data_dict()`, wired to validator |
| `apps/api/services/coach_tools.py` | `get_wellness_trends` recency prefix |
| `apps/api/tests/test_sleep_prompt_grounding.py` | 22 new regression tests |
