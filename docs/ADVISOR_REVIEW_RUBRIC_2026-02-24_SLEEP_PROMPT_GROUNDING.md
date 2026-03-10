# Advisor Review Rubric — Sleep Prompt Grounding

**Date:** February 24, 2026  
**Purpose:** Pre-implementation and implementation quality gate for `BUILDER_NOTE_2026-02-24_SLEEP_PROMPT_GROUNDING_V2.md`  
**Use:** Advisor/founder pass-fail checklist before builder starts and before merge

---

## Required read order

1. `docs/FOUNDER_OPERATING_CONTRACT.md`
2. `docs/BUILDER_NOTE_2026-02-24_SLEEP_PROMPT_GROUNDING_V2.md`
3. `apps/api/models.py` (`Athlete`, `DailyCheckin`, `GarminDay`)
4. `apps/api/routers/home.py`
5. `apps/api/tasks/home_briefing_tasks.py`
6. `apps/api/services/coach_tools.py`

---

## Phase 0 — Preflight (must pass before coding)

### Gate P0.1 — Timezone field reality check (hard gate)

**Question:** Does athlete-local timezone exist on the model/config right now?

Builder must provide:
- Exact field name and type (or explicit statement that it does not exist)
- One code reference proving it
- Fallback policy if missing (must be explicit and documented)

**Pass criteria:**
- One of:
  - `Athlete` timezone source exists and is used, OR
  - Fallback policy is explicitly defined (`UTC` or server-local) and documented in-code/doc
- No silent default

**Fail conditions:**
- Assumes timezone exists without proof
- Adds "last night" logic without defined fallback

---

### Gate P0.2 — Validator false-positive inventory (hard gate)

**Question:** Will sleep-number detection accidentally trigger on workout duration text?

Builder must provide:
- Sample inventory of current home outputs (at least 10 lines total across `morning_voice`, `checkin_reaction`, `workout_why`)
- List of sleep-context phrases to match
- List of non-sleep phrases to exclude (e.g., "60-minute tempo", "90 minutes")
- Proposed detection rule boundaries

**Pass criteria:**
- Detection scoped to sleep context, not generic numeric+unit patterns
- At least one explicit negative test case planned for workout durations

**Fail conditions:**
- Regex/parser designed without phrase inventory
- Detection only based on `\d+(\.\d+)?h` style token with no context guard

---

## Phase 1 — Design contract review

### Gate D1 — Source precedence is deterministic

Builder must show explicit order:
1. Garmin device sleep
2. Check-in `sleep_h`
3. Label-only (no numeric claim)

**Pass criteria:**
- Conflict behavior specified (Garmin vs check-in mismatch)
- "No third synthesized value" rule present

---

### Gate D2 — Temporal grounding contract is explicit

**Pass criteria:**
- "Last night" date resolution described
- Garmin wakeup-day semantics acknowledged
- Today/Yesterday fallback behavior defined

---

### Gate D3 — Suppression policy is explicit

**Pass criteria:**
- If claim not grounded, output is suppressed or rewritten non-numerically
- Tolerance band justified (0.5h for slider rounding)

---

## Phase 2 — Test-plan adequacy review

Builder test plan must include all of:

1. `sleep_h` present in request-path checkin dict  
2. `sleep_h` present in worker-path checkin dict  
3. Prompt contains source-labeled sleep fields  
4. Wellness narrative includes most recent date/value recency anchor  
5. Garmin date fallback (today then yesterday)  
6. Validator rejects ungrounded sleep numeric  
7. Validator accepts value within tolerance  
8. No numeric sleep claim when no numeric source exists  
9. Negative test: workout-duration numeric should not trigger sleep validator

**Pass criteria:** 9/9 planned with concrete assertions  
**Fail criteria:** Any missing, or no negative false-positive test

---

## Phase 3 — Implementation review (pre-merge)

Advisor checks:
- Files touched match scoped list only
- No frontend changes
- No model schema changes unless explicitly approved
- No unrelated refactors

**Evidence required:**
- `git diff --name-only`
- Targeted pytest output for new/updated tests
- One sample prompt snapshot (redacted) showing grounded fields
- One sample validator decision log (pass or suppress)

---

## Phase 4 — Production readiness review

### Smoke scenarios (must be demonstrated)

1. Garmin 6.75 + check-in 7.0 -> output cites valid source(s), no invented number  
2. Check-in-only -> numeric may be used from check-in only  
3. Garmin-only -> numeric may be used from Garmin only  
4. No numeric source -> no numeric sleep claim  
5. Existing home briefing stale->fresh behavior still works

---

## Decision rubric

- **GO:** All P0 gates pass, design contract clear, 9/9 tests implemented and passing, smoke criteria met.
- **GO WITH CONDITIONS:** Non-critical gap with explicit follow-up issue and no athlete-facing trust risk.
- **NO-GO:** Any P0 gate fails, source precedence ambiguous, or validator false-positive risk untested.

---

## Reviewer sign-off template

- **Preflight:** PASS / FAIL  
- **Design contract:** PASS / FAIL  
- **Test plan:** PASS / FAIL  
- **Implementation scope:** PASS / FAIL  
- **Production smoke:** PASS / FAIL  
- **Final decision:** GO / GO WITH CONDITIONS / NO-GO  
- **Notes:** <required follow-ups, if any>

