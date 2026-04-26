# BUILDER INSTRUCTIONS — P4 Load Context (Scope+Tech Locked, Builder Go)

**Owner:** Builder  
**Reviewer:** Northstar  
**Priority:** P0 reliability (history-aware load context)  
**Status:** Approved to implement  
**Date:** 2026-03-22

Canonical specs: `docs/specs/P4_LOAD_CONTEXT_TECHNICAL_SPEC.md`, `docs/specs/P4_LOAD_CONTEXT_SCOPE_AND_PROCESS.md`.

## Decision lock

- `C_upper = 1.15`
- `D4_N = 8`
- `D4_M = 120` days
- Slice **4b:** **YES** — enable history for authenticated standard create/preview after 4a + CI green

## Slices

`0 → 1 → 2 → 3 → 4a → 4b` as in technical spec.

## CI / commit gate

Commits touching `plan_framework/**` or `plan_generation.py`:

- `P0-GATE: GREEN`
- `P0-GATE-NOTES: <what was verified>`

## Completion evidence

Files changed, constants lock, test output, CI run id, prod verification, known risks.

## Non-goals

P5 adaptation, fluency P4, LLM narrative, broad `AthletePlanProfileService` refactor.
