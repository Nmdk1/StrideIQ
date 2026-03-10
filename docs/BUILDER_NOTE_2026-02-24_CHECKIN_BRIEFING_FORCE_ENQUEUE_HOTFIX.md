# Builder Note — Check-in Briefing Force-Enqueue Hotfix

**Date:** February 24, 2026  
**Priority:** SEV-1 follow-up (prevent check-in refresh suppression by cooldown)  
**Branch target:** `main`  
**Required outcome:** commit and push to `origin/main`

---

## Why this hotfix is required

The current check-in flow now marks briefing cache dirty and calls `enqueue_briefing_refresh`, but enqueue can still be skipped by cooldown. That creates a failure mode:

1. check-in marks cache dirty,
2. enqueue is blocked by cooldown,
3. no task runs until cooldown expires,
4. athlete sees prolonged pending/fallback state.

Check-in must be deterministic: it should force one refresh enqueue while still respecting lock/circuit protections.

---

## Read order

1. `docs/FOUNDER_OPERATING_CONTRACT.md`
2. `apps/api/routers/daily_checkin.py`
3. `apps/api/tasks/home_briefing_tasks.py`
4. `apps/api/services/home_briefing_cache.py`
5. `apps/api/tests/test_daily_checkin_briefing_refresh.py`
6. `apps/api/tests/test_home_briefing_cache.py`
7. This document

---

## Scope (minimal)

### 1) Add force-enqueue support

**File:** `apps/api/tasks/home_briefing_tasks.py`

Update function signature:

- from: `enqueue_briefing_refresh(athlete_id: str) -> bool`
- to: `enqueue_briefing_refresh(athlete_id: str, force: bool = False) -> bool`

Behavior:
- `force=False` (default): current behavior unchanged.
- `force=True`:
  - bypass cooldown check,
  - still honor circuit breaker,
  - still set cooldown after enqueue,
  - still rely on task lock to prevent duplicate concurrent execution.

Implementation guidance:
- add a small helper in `home_briefing_cache.py` if needed (e.g., `is_circuit_open_for_athlete`) rather than duplicating key logic in task file.
- keep existing logging style; include `force=true` in enqueue log for auditability.

### 2) Use force path for check-in trigger only

**File:** `apps/api/routers/daily_checkin.py`

In `_trigger_briefing_refresh`, call:

`enqueue_briefing_refresh(athlete_id, force=True)`

Do not change non-check-in callers; they should continue with normal cooldown behavior.

---

## What NOT to change

- Do not alter polling UI or frontend code in this hotfix.
- Do not change lock TTL, cooldown duration, or circuit thresholds.
- Do not add dependencies.
- Do not touch unrelated queues/tasks.

---

## Acceptance criteria

1. Check-in path (`/v1/daily-checkin`) always attempts enqueue even if cooldown key exists.
2. Force path still blocks enqueue when circuit is open.
3. Non-force callers keep existing cooldown behavior.
4. Existing tests remain green; new force-specific tests pass.

---

## Required tests

### Update/add backend tests

**File:** `apps/api/tests/test_daily_checkin_briefing_refresh.py`

Add tests:

1. `_trigger_briefing_refresh` calls `enqueue_briefing_refresh(..., force=True)`.
2. If cooldown exists, force enqueue path still proceeds.

**File:** `apps/api/tests/test_home_briefing_cache.py` or new focused task test file

Add tests around enqueue behavior:

3. `force=False` + cooldown present => enqueue skipped.
4. `force=True` + cooldown present + circuit closed => enqueue allowed.
5. `force=True` + circuit open => enqueue blocked.

---

## Verification evidence required

- Paste targeted pytest output for updated files.
- Paste `git diff --name-only` (scoped files only).
- Paste commit SHA and confirmation that branch is `main`.
- Paste push confirmation to `origin/main`.

---

## Git instructions (explicit)

This hotfix must land directly on `main` and be pushed.

1. Ensure branch:
   - `git checkout main`
   - `git pull origin main`
2. Make scoped edits and run tests.
3. Stage only relevant files (no `git add -A`).
4. Commit:
   - `fix(home): force enqueue briefing refresh on check-in`
5. Push:
   - `git push origin main`

---

## Post-push smoke checks (required)

1. Submit check-in.
2. Confirm backend log indicates forced enqueue.
3. Confirm no cooldown-skip log for that check-in event.
4. Confirm briefing transitions to fresh without repeated manual refresh.

