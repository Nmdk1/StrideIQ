# Builder Note — Sleep Data Prompt Grounding Fix (V2)

**Date:** February 24, 2026  
**Priority:** High (athlete trust — incorrect sleep number in coach voice)  
**Status:** Ready to implement  
**Owner:** Builder agent  
**Scope:** Backend only (prompt grounding + validator + tests)

---

## Read order (mandatory)

1. `docs/FOUNDER_OPERATING_CONTRACT.md`
2. `docs/SESSION_HANDOFF_2026-02-24_STRIPE_AND_GARMIN_REVIEW.md`
3. `apps/api/routers/home.py` — `generate_coach_home_briefing`, `_build_rich_intelligence_context`, output validator
4. `apps/api/tasks/home_briefing_tasks.py` — `_build_briefing_prompt`
5. `apps/api/services/coach_tools.py` — `get_wellness_trends`, `build_athlete_brief`
6. `apps/api/models.py` — `DailyCheckin`, `GarminDay`
7. This document

---

## Problem statement (verified)

Home morning briefing cited a wrong sleep value ("7.5h last night") while athlete-reported and device reality were different.

Data integrity is not the core issue; prompt grounding is.  
The system currently allows the LLM to blend historical and current sleep context without strict temporal/source rules.

---

## Root causes

### Failure mode 1 — Today's numeric sleep (`sleep_h`) is missing from `checkin_data_dict`
`checkin_data_dict` currently carries labels (`sleep_label`) but not the explicit numeric `sleep_h`, so the model lacks a hard "today" sleep number.

### Failure mode 2 — Wellness narrative lacks temporal anchoring
`get_wellness_trends` provides aggregate narrative (e.g., avg/trend) without strong recency grounding in the prompt, enabling misattribution.

### Failure mode 3 — Garmin device sleep is not integrated into home briefing context
`GarminDay.sleep_total_s` is not used in home briefing prompt assembly, even though it is higher fidelity than slider input.

### Failure mode 4 — Post-generation validator does not enforce sleep-number grounding
Current validators enforce tone/format but not factual alignment for sleep claims.

---

## Sleep source contract (new, required)

When constructing sleep context for home briefing, enforce deterministic precedence:

1. **Garmin device sleep** (`GarminDay.sleep_total_s`) for last night if available and date-valid.
2. **Manual check-in `sleep_h`** for today if entered.
3. **Sleep label only** if no numeric source is available.
4. If no numeric source exists, **numeric sleep claims are forbidden** in generated text.

Conflict handling:
- If Garmin and check-in differ, prompt must present both as separate sources (device vs self-report), not collapse into one value.
- LLM should not invent a third value.

---

## Timezone contract (new, required)

"Last night" must use **athlete-local date**, not server-local `date.today()`.

- Determine athlete local date (from athlete timezone setting if available; fallback policy must be explicit).
- Use local wakeup-day semantics for Garmin sleep lookup:
  - `calendar_date = local_today` first
  - fallback to `local_today - 1 day` for delayed sync.
- Do not use raw server UTC date to label "last night."

---

## Implementation plan

### 1) Include `sleep_h` in `checkin_data_dict` in both call paths
Files:
- `apps/api/routers/home.py`
- `apps/api/tasks/home_briefing_tasks.py`

Add `sleep_h` from latest check-in row into prompt input dict.

---

### 2) Harden prompt assembly with explicit source labels
File:
- `apps/api/routers/home.py` (`generate_coach_home_briefing`)

Add explicit section with source-grounded fields, e.g.:
- `TODAY_CHECKIN_SLEEP_HOURS` (if present)
- `GARMIN_LAST_NIGHT_SLEEP_HOURS` (if present)
- `SLEEP_SOURCE_PRIORITY` instruction
- "Do not synthesize or average these values into a new number."

---

### 3) Add Garmin Source 0 in rich context with timezone-safe date lookup
File:
- `apps/api/routers/home.py` (`_build_rich_intelligence_context`)

Insert highest-priority sleep context block before other intelligence sections:
- Device sleep hours
- calendar_date used
- sleep score / HRV / resting HR when present
- clear label: **device-measured**

---

### 4) Improve wellness narrative recency anchoring
File:
- `apps/api/services/coach_tools.py` (`get_wellness_trends`)

Add explicit "most recent entry (date, value)" prefix before aggregates.  
Keep aggregate stats, but separate clearly from "last night" facts.

---

### 5) Add sleep-claim grounding validator
File:
- `apps/api/routers/home.py` (post-generation validation)

Rules:
- If output includes sleep-like numeric claim in sleep context, value must match one known source within tolerance.
- Tolerance: `<= 0.5h` (to allow slider rounding).
- Restrict detection to sleep-context phrases near numeric claims (avoid false hits on workout durations).
- If invalid: suppress that field (or replace with non-numeric fallback).

---

## Acceptance criteria (must all pass)

1. If check-in has `sleep_h=7.0`, generated text never claims 7.5 as "last night" unless a valid source supports it.
2. If Garmin shows `6.75` and check-in shows `7.0`, output either:
   - cites one source correctly with label, or
   - cites both with clear distinction.
3. If neither source has numeric sleep, output contains no numeric sleep claim.
4. "Last night" lookup uses athlete-local date logic (verified by tests).
5. Validator suppresses out-of-contract sleep numbers.
6. No frontend changes required; no API contract break.

---

## Test contracts

Add/update tests in `apps/api/tests/`:

1. `test_checkin_data_dict_includes_sleep_h_request_path`
2. `test_checkin_data_dict_includes_sleep_h_worker_path`
3. `test_prompt_contains_source_labeled_sleep_fields`
4. `test_wellness_trends_includes_most_recent_date_prefix`
5. `test_garmin_sleep_context_uses_local_today_then_local_yesterday`
6. `test_validator_rejects_sleep_number_not_in_sources`
7. `test_validator_accepts_sleep_number_within_rounding_tolerance`
8. `test_no_numeric_sleep_claim_when_no_numeric_sleep_sources`
9. `test_conflict_case_garmin_vs_checkin_does_not_invent_third_value`

---

## Observability requirements (new)

Add structured log fields during prompt build and validation:

- athlete_id
- local_date_used
- garmin_sleep_h (if present)
- checkin_sleep_h (if present)
- selected_primary_sleep_source
- validator_sleep_claim_value
- validator_result (pass/suppressed)

PR must include sample log lines from one real request.

---

## Rollout and cache plan

After deploy:
1. Clear/expire home briefing cache for test athlete(s) or wait for TTL.
2. Trigger one fresh home load + one check-in flow.
3. Verify output and logs match source contract.
4. Confirm no regression in response times beyond expected LLM latency.

---

## Post-deploy smoke checklist

1. Case A: Garmin 6.75, check-in 7.0 → output cites valid value(s), no invented number.
2. Case B: check-in only (no Garmin) → output uses check-in sleep or no numeric claim.
3. Case C: Garmin only (no check-in sleep_h) → output uses Garmin device value.
4. Case D: no numeric sources → no numeric sleep statement.
5. Confirm stale → fresh briefing transition still works.

---

## Do not touch

- Frontend code
- Check-in endpoint behavior
- Data models (`DailyCheckin`, `GarminDay`) schema
- Non-home-briefing pipelines

---

## Commit guidance

Suggested commit message:

`fix(home): ground sleep claims to dated device/check-in sources`

---

## Rollback plan

If validator is over-suppressing:
- keep source-grounding prompt changes,
- temporarily disable strict sleep numeric enforcement and fall back to non-numeric sleep phrasing,
- preserve logs to tune thresholds safely.
