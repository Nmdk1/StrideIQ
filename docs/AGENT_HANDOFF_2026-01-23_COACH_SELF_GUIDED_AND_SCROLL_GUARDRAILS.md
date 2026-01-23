## Agent Handoff: Coach Self-Guided Engine + Scroll Guardrails

**Date:** 2026-01-23  
**Branch:** `stable-diagnostic-report-2026-01-14`  
**Owner intent:** Coach must feel N=1, evidence-backed, non-gaslighting; UI must be durable and not regress.

---

## Executive Summary

This work adds a **self-guided coaching backbone** (persistent intent + deterministic training prescription window) and stabilizes the Coach UI so it behaves like a real chat app:

- **Coach can “remember” intent** (within a collaborative, athlete-led window) via `CoachIntentSnapshot`.
- **Coach can generate up to a week of exact prescriptions** using bounded tools (not generic LLM output), while explicitly handling “plan vs reality” mismatches.
- **Coach page scroll is fixed**: the page does not scroll; **only the transcript** (middle pane) scrolls, with `min-h-0` guardrails to prevent regressions.

---

## What changed (high signal)

### 1) Coach memory: intent snapshot (athlete-led, non-repetitive)

- Added `CoachIntentSnapshot` (one per athlete) to persist:
  - `training_intent`, `pain_flag`, `time_available_min`, `weekly_mileage_target`, etc.
- AI coach updates the snapshot opportunistically from natural language to avoid repetitive questioning.

Key files:
- `apps/api/models.py`
- `apps/api/alembic/versions/c2d3e4f5a6b7_add_coach_intent_snapshot.py`
- `apps/api/services/coach_tools.py`
- `apps/api/services/ai_coach.py`

### 2) Deterministic prescriptions: “up to a week” window

- Added `get_training_prescription_window` tool to generate exact day plans using established plan primitives (paces/baseline + plan generator).
- **Crucial correctness rule**: if an activity exists for a day, show/analyze the **actual completed activity first**, then compare to plan (avoid athlete gaslighting).

Key file:
- `apps/api/services/coach_tools.py`

### 3) Coach chat UX: persisted history + transcript-only scroll

- Coach UI loads persisted thread history on mount.
- **Golden layout rule** (do not break):
  - outer coach shell: fixed height under sticky nav + `overflow-hidden`
  - nested flex/grid ancestors: **must include `min-h-0`**
  - transcript pane: `flex-1 min-h-0 overflow-y-auto` (the ONLY scroll container)

Key file:
- `apps/web/app/coach/page.tsx`

Regression safeguard:
- Added Jest test asserting the required scroll container structure/classes:
  - `apps/web/__tests__/coach-scroll-layout.test.tsx`

---

## How to verify quickly

### Web

- `docker compose up -d --build web`
- Visit `/coach` and validate:
  - Page itself does **not** scroll
  - Transcript scrolls between header and input
  - Input stays reachable/anchored
  - Works at common zoom levels (e.g. 67%) and narrow heights

### Web unit test

- From `apps/web`:
  - `npm test -- __tests__/coach-scroll-layout.test.tsx`

### API

- `docker compose exec -T api pytest -q`

---

## Notes / watch-outs

- PowerShell may not support `&&` depending on shell mode; run commands separately when needed.
- The e2e coach script requires `E2E_EMAIL` and `E2E_PASSWORD`; it is not a good regression gate unless CI provides creds.

