# Coach Output Contract v1

**Status:** Accepted (implementation baseline)  
**Date:** 2026-02-09  
**Scope:** Athlete-facing coach output quality for Calendar day coach, Home briefing, and Progress cards.

## Product Intention

StrideIQ coach output must feel like high-trust, N=1 coaching:
- Interpretive, not watch-like metric narration.
- Positive-first, never dismissive.
- Fact-grounded and non-speculative.
- Actionable every time.

## Canonical A->I->A Shape

Every athlete-facing output must include:

1. **Assessment**  
   Interpretive judgment of what happened (not raw metric replay).

2. **Implication**  
   Why the assessment matters for near-term training direction.

3. **Action**  
   At least one concrete next step.

## Surface Contracts

### Calendar Day Coach (`POST /v1/calendar/coach`, `context_type=day`)

- **Fact source:** `get_calendar_day_context` is canonical for date/weekday/pace relation.
- **Fail-closed preflight:** if day context is incomplete, do not run model response path.
- **Prompt contract:** model is instructed to return JSON keys:
  - `assessment`
  - `implication`
  - `action` (array)
  - `athlete_alignment_note`
  - `evidence` (array)
  - `safety_status`
- **Formatter contract:** router renders athlete-facing prose from contract payload.
- **Leak prevention:** internal labels (for example fact capsule labels) must never be shown to athlete.
- **Deterministic fallback:** if model output fails contract checks, render from day facts.

### Home Briefing (`GET /v1/home`)

- Existing structured fields remain:
  - `coach_noticed` (Assessment)
  - `week_assessment` (Implication)
  - `today_context` / `checkin_reaction` / `race_assessment` (Action present in at least one)
- Validation enforces:
  - interpretive assessment language
  - at least one concrete action
  - optional sections required when relevant context exists
- Invalid model output is rejected (fallback path).

### Progress Cards (`GET /v1/progress/summary`)

- Existing structured card fields remain:
  - `summary` (Assessment)
  - `trend_context` (Implication)
  - `next_step` (Action)
- Validation enforces per-card A->I->A quality and blocks internal label leakage.
- Invalid model output falls back to deterministic card generation.

## Explicit Failure Examples (Anti-patterns)

1. **Watch-parrot response (fails Assessment)**
   - "You ran 10 miles at 7:06/mi, HR 152."
   - Why fail: numeric replay only, no interpretation.

2. **Internal contract leakage (fails UX trust)**
   - "Date: 2026-02-10. Recorded pace vs marathon pace: slower by 0:09/mi."
   - Why fail: echoes internal fact capsule labels to athlete.

3. **No actionable next step (fails Action)**
   - "Your trend is stable this week."
   - Why fail: no concrete recommendation.

4. **Speculative contradiction (fails trust)**
   - "You seem fatigued" when athlete reports feeling good and no conflicting evidence is present.
   - Why fail: violates athlete alignment and evidence-first contract.

## Verification Baseline

- `apps/api/tests/test_calendar_coach_trust_contract.py`
- `apps/api/tests/test_coach_output_contract_structured.py`
- `apps/api/tests/test_coach_output_contract_chat.py`

These tests ensure contract coverage for:
- day fact integrity and fail-closed behavior,
- structured surface quality gates,
- and internal-label leakage suppression in coach chat normalization.
