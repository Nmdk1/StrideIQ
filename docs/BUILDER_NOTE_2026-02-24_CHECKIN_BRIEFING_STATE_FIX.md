# Builder Note — Check-in Briefing State Contract Fix

**Date:** February 24, 2026  
**Priority:** SEV-1 (athlete trust issue on core daily flow)  
**Status:** Ready to implement  
**Owner:** Builder agent  
**Advisor stance:** Proceed with state-driven polling, but fix backend contract first

---

## Read order (mandatory)

1. `docs/FOUNDER_OPERATING_CONTRACT.md`
2. `docs/ADVISOR_BRIEF_2026-02-24_CHECKIN_BRIEFING_FAILURE.md`
3. `apps/web/lib/hooks/queries/home.ts`
4. `apps/web/lib/api/services/home.ts`
5. `apps/web/app/home/page.tsx`
6. `apps/api/routers/daily_checkin.py`
7. `apps/api/routers/v1.py` (checkins endpoint behavior reference)
8. `apps/api/routers/home.py` (`briefing_state` production contract)
9. `apps/api/services/home_briefing_cache.py`
10. `apps/api/tasks/home_briefing_tasks.py`
11. This document

---

## Problem statement (verified)

The check-in UX fails for two reasons at once:

1. The web check-in mutation posts to `/v1/daily-checkin`, but that endpoint does not enqueue briefing refresh.
2. Frontend ignores `briefing_state` and does only one immediate refetch, so it misses the async generation window.

Result: athlete submits check-in, sees stale/no coaching insights, and must manually refresh repeatedly.

---

## Root cause contract

This is not just "frontend forgot polling." The actual contract failure is cross-layer:

- Trigger mismatch: UI route and enqueue route diverged.
- State mismatch: cached `fresh` can still represent pre-check-in content unless marked dirty.
- UX mismatch: frontend does not honor `briefing_state` state machine.

All three must be fixed together in one scoped change.

---

## Implementation plan

### A) Backend: make check-in trigger deterministic on the route the UI actually calls

**File:** `apps/api/routers/daily_checkin.py`

After successful create/update commit in `create_or_update_checkin`:

- Import and call `enqueue_briefing_refresh(str(current_user.id))` in a non-blocking `try/except`.
- Log warning on exception; never fail check-in response.

Expected behavior:
- Any successful `/v1/daily-checkin` save attempts to enqueue briefing refresh.
- Endpoint remains fast and resilient.

### B) Backend: force "not fresh" after new check-in input

**File:** `apps/api/services/home_briefing_cache.py`

Add helper:
- `mark_briefing_dirty(athlete_id: str) -> None`
- Deletes `home_briefing:{athlete_id}` key (cache payload only; do not delete lock/circuit/cooldown keys).
- Swallow Redis exceptions with warning log (non-blocking).

**File:** `apps/api/routers/daily_checkin.py`

After successful save and before enqueue call:
- Call `mark_briefing_dirty(str(current_user.id))` in its own guarded `try/except`.

Why:
- Prevents stale pre-check-in payload from being treated as `fresh`.
- Guarantees next `/v1/home` read returns `missing` or `refreshing`, which the frontend can react to.

### C) Frontend: consume `briefing_state` and poll until fresh

**File:** `apps/web/lib/api/services/home.ts`

- Add `briefing_state?: 'fresh' | 'stale' | 'missing' | 'refreshing' | 'consent_required' | null;` to `HomeData`.

**File:** `apps/web/lib/hooks/queries/home.ts`

Update `useHomeData()`:
- Keep existing query key and query fn.
- Add `refetchInterval` function:
  - if `briefing_state` in `['stale', 'missing', 'refreshing']` => `2000`
  - else => `false`
- Keep `refetchOnWindowFocus: true`.

Update `useQuickCheckin()` onSuccess:
- Keep optimistic check-in summary update and toast.
- Keep invalidate call.
- Add a "poll window" marker in cache (local-only) if needed for timeout handling in page component (see D).

### D) Frontend: add visible loading/thinking state + timeout fallback

**File:** `apps/web/app/home/page.tsx`

Add logic:
- Determine `isBriefingPending = briefing_state === 'stale' || briefing_state === 'missing' || briefing_state === 'refreshing'`.
- Show a lightweight "Coach is thinking..." placeholder in the same visual area where `morning_voice`/`coach_noticed` appears when pending and no fresh content.
- Start a 30s timer when pending starts; if still pending after 30s, show fallback:
  - "Your coach is taking a moment - check back shortly."
  - Include small "Retry now" action (invalidates `['home']` once).
- Stop timer and remove fallback once `briefing_state` becomes `fresh` (or `consent_required`).

Do not block the rest of home page rendering.

---

## Explicit non-goals (do NOT do in this change)

- Do not add WebSocket/SSE.
- Do not move briefing generation inline into check-in response.
- Do not change Celery worker topology in this task.
- Do not redesign cache TTL/circuit-breaker/cooldown policy.
- Do not touch unrelated home/progress performance code.

---

## Acceptance criteria

1. Submitting check-in via `/v1/daily-checkin` causes refresh enqueue attempt every time.
2. Immediately after check-in save, `/v1/home` does not report stale pre-check-in payload as `fresh`.
3. Home UI renders pending state while `briefing_state` is non-fresh.
4. Home UI polls automatically every ~2 seconds until `briefing_state === 'fresh'`.
5. Polling stops once fresh.
6. If still non-fresh after 30s, graceful fallback appears with one-click retry.
7. Existing optimistic check-in summary behavior remains intact.

---

## Required tests (must be written before merge)

### Backend tests

**File:** `apps/api/tests/test_daily_checkin_briefing_refresh.py` (new)

1. `POST /v1/daily-checkin` create path calls `mark_briefing_dirty` and `enqueue_briefing_refresh`.
2. `POST /v1/daily-checkin` update path calls both helpers.
3. If dirty/enqueue helpers throw, endpoint still returns success (non-blocking behavior).

**File:** `apps/api/tests/test_home_briefing_cache.py` (extend)

4. `mark_briefing_dirty` removes payload key when present.
5. `mark_briefing_dirty` no-ops safely when Redis unavailable/errors.

### Frontend tests

**File:** `apps/web/__tests__/home-briefing-state.test.tsx` (new or extend existing home tests)

6. With `briefing_state='refreshing'`, page shows thinking placeholder and no infinite spinner.
7. While `briefing_state` non-fresh, query refetch interval is active (2s).
8. When state transitions to `fresh`, placeholder disappears and briefing content renders.
9. After 30s still non-fresh, fallback message appears and Retry triggers one refetch invalidate.

Use fake timers for deterministic timeout assertions.

---

## Verification evidence required in PR description

- Test outputs for all new/updated backend and frontend test files.
- Short screenshot or log snippet showing:
  - check-in save,
  - temporary pending state,
  - automatic swap to fresh briefing without manual refresh.
- `git diff --name-only` showing only scoped files.

---

## Suggested commit message

`fix(home): honor briefing_state after check-in with dirty-mark + polling`

---

## Rollout notes

- This is safe behind existing architecture; no migration needed.
- Deploy normally.
- Post-deploy smoke:
  1. submit check-in
  2. confirm pending state appears
  3. confirm coaching insights auto-appear without browser refresh
  4. confirm no check-in API latency regression

