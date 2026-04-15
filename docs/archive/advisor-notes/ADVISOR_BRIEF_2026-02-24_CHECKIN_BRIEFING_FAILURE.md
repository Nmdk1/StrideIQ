# Advisor Brief: Home Page Coaching Insights Not Appearing After Check-in

**Date:** February 24, 2026  
**For:** External advisor review  
**Author:** Current advisor (acknowledging 4 failed attempts to fix this)  
**Severity:** Critical UX failure — athlete-facing, trust-destroying

---

## The Problem (Athlete's Experience)

The athlete opens the home page, completes their morning check-in (feel, sleep, soreness), saves it. They expect to immediately see coaching insights — morning voice, check-in reaction, workout context. Instead they see nothing new. They refresh. Nothing. Refresh again. Nothing. After 8 manual refreshes, the insights finally appear.

No athlete will do this. This has been "fixed" 4 times. It keeps failing.

---

## Architecture (How It Currently Works)

```
Athlete submits check-in
    ↓
POST /v1/daily-checkin
    ↓
1. Check-in saved to DB (synchronous, instant)
2. enqueue_briefing_refresh(athlete_id) fired (fire-and-forget to Celery)
3. HTTP 201 returned to frontend immediately
    ↓
Frontend receives 201:
    - Optimistic update: swaps QuickCheckin → CheckinSummary widget
    - queryClient.invalidateQueries(['home']) — triggers background refetch of /v1/home
    - toast.success('Check-in saved')
    ↓
Meanwhile, in background:
    - Celery worker picks up generate_home_briefing task
    - Task calls Claude Opus (10-15 seconds)
    - Briefing written to Redis cache
    ↓
/v1/home endpoint:
    - Reads briefing from Redis cache
    - If cache is STALE or MISSING, returns whatever was there before (or nothing)
    - If cache is FRESH, returns the new briefing
    ↓
Problem:
    - The invalidateQueries refetch of /v1/home fires IMMEDIATELY after check-in save
    - The Celery task hasn't even started yet (worker queue, prefetch, task startup)
    - So /v1/home returns the OLD briefing (pre-check-in) or no briefing
    - The frontend caches this stale response in React Query
    - The athlete sees no change
    - No auto-retry. No polling. No loading indicator.
    - Athlete must manually refresh the page to get the new briefing
```

---

## Why Previous Fixes Failed

### Fix 1-3: Various backend adjustments
Multiple attempts at ensuring the briefing task fires correctly, cache invalidation, etc. The backend IS firing the task correctly. The task IS generating the briefing. The briefing IS landing in the cache. **The problem was never that the briefing doesn't get generated. The problem is timing.**

### Fix 4 (most recent): Progress page pre-warm on login
Added a Celery pre-warm task on login. This helps with cold-start on the progress page but does nothing for the check-in → briefing flow because:
- The briefing needs to incorporate the CHECK-IN DATA that was just submitted
- Pre-warming stale caches doesn't help when the content must be regenerated with new input

---

## Root Cause (Honest Assessment)

**The frontend has no awareness that the briefing is being regenerated.**

After check-in:
1. `invalidateQueries(['home'])` fires ONE refetch immediately
2. That refetch hits the API while the briefing is still being generated (~10-15s away)
3. React Query caches the stale result
4. No further automatic refetches happen
5. The athlete is stuck with stale content until they manually refresh

The `briefing_state` field IS returned by the API (`fresh`, `stale`, `missing`, `refreshing`) but the frontend **completely ignores it**. There is no code in `home/page.tsx` that reads `briefing_state`. No polling. No "Coach is thinking..." state. No automatic retry when the state is `stale` or `refreshing`.

---

## Key Files

| File | Role |
|------|------|
| `apps/web/lib/hooks/queries/home.ts` | `useQuickCheckin()` — mutation that saves check-in, does optimistic update, fires ONE invalidateQueries |
| `apps/web/app/home/page.tsx` | Home page component — renders coach_briefing fields but ignores briefing_state |
| `apps/api/routers/v1.py:1002-1023` | Check-in endpoint — saves to DB, fires enqueue_briefing_refresh |
| `apps/api/routers/home.py:1928-2076` | /v1/home endpoint — reads briefing from Redis cache, returns briefing_state |
| `apps/api/tasks/home_briefing_tasks.py:508-524` | enqueue_briefing_refresh — Celery task dispatch with cooldown |
| `apps/api/services/home_briefing_cache.py` | Redis cache service with read/write/cooldown/circuit-breaker |

---

## What the API Already Provides (But Frontend Ignores)

The `/v1/home` response includes `briefing_state` with these possible values:

| State | Meaning |
|-------|---------|
| `fresh` | Briefing was generated recently, content is current |
| `stale` | Briefing exists but is old (>15 min) — a refresh was triggered |
| `missing` | No briefing has ever been generated |
| `refreshing` | A briefing task is currently running |
| `consent_required` | AI consent not granted |

The frontend renders `coach_briefing.morning_voice`, `coach_briefing.coach_noticed`, `coach_briefing.checkin_reaction`, etc. when present — but never checks `briefing_state` to decide whether to poll, show a loading state, or wait.

---

## What Needs to Happen

The frontend must use `briefing_state` to provide a seamless post-check-in experience. Specifically:

1. After check-in submission, the frontend should know that the briefing is being regenerated
2. When `briefing_state` is `stale`, `missing`, or `refreshing`, the frontend should show a loading/thinking indicator where the coaching insights will appear
3. The frontend should auto-poll `/v1/home` every 2-3 seconds while the briefing is not `fresh`
4. When `briefing_state` transitions to `fresh`, swap in the coaching content and stop polling
5. Add a timeout (30 seconds) — if briefing still isn't fresh, show a graceful fallback ("Your coach is taking a moment — check back shortly")

The backend already supports this. The `briefing_state` field exists. The cache infrastructure works. The Celery task works. This is purely a frontend integration gap.

---

## Constraints

- Single Celery worker with `--pool=solo` (one task at a time)
- Briefing generation calls Claude Opus (~10-15 seconds)
- Other tasks (Garmin webhooks, Strava sync, intelligence) compete for the same worker
- Migration to more powerful hardware (8 CPU, 32 GB RAM) is planned but not yet executed
- The architectural pattern (async briefing via Celery + Redis cache) is sound for scale; the problem is that the frontend never implemented the polling/waiting UX

---

## Question for Advisor

Given this architecture, is the proposed fix (frontend polling on `briefing_state`) the right approach? Or should we consider:

- A WebSocket/SSE push when the briefing is ready?
- Synchronous briefing generation inline with the check-in response (blocking but guaranteed)?
- A different caching/invalidation strategy?

The founder has spent significant money on 4 failed attempts. The next fix must be the last.
