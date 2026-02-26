# Session Handoff — Monetization Complete

**Date:** 2026-02-26  
**Commits:** `48ac179`, `46c7c72`, `c89f35d`  
**Status:** SHIPPED — all 3 streams delivered, deployed, production healthy

---

## Hard Gate Result

All 5 Stripe price IDs confirmed present in `/opt/strideiq/repo/.env` before coding began:
- `STRIPE_PRICE_PLAN_ONETIME_ID` — $5 one-time plan unlock
- `STRIPE_PRICE_GUIDED_MONTHLY_ID` — $15/mo
- `STRIPE_PRICE_GUIDED_ANNUAL_ID` — $150/yr
- `STRIPE_PRICE_PREMIUM_MONTHLY_ID` — $25/mo
- `STRIPE_PRICE_PREMIUM_ANNUAL_ID` — $250/yr

---

## Stream 1 — `_check_paid_tier()` cleanup (`48ac179`)

**File:** `apps/api/routers/plan_generation.py`

Replaced hand-rolled tier string list with `core.tier_utils.tier_satisfies(athlete.subscription_tier, "guided")`. Legacy fallback for athletes with semi-custom/custom/framework_v2 plans preserved. Behavioral parity verified for all 8 tier values (pro, elite, premium, guided, subscription → True; free, None, unknown → False).

---

## Stream 2 — Monetization xfail test conversion (`46c7c72`)

**File:** `apps/api/tests/test_monetization_tier_mapping.py`

| Group | Tests | Outcome |
|-------|-------|---------|
| Group A — real tests | 17 | Passed |
| Group B — structured xfail | 12 | xfailed (correct) |
| Total | 29 | 17 passed, 12 xfailed, 0 failed |

**Group A tests (real, xfail removed):**
- Free tier (6): RPI public, plan structure with paces_locked, null paces, 403 on intel/narrative/bank
- One-time tier (4): PlanPurchase unlocks paces, still 403 on intelligence
- Guided tier (4): 200 on intelligence/bank, 403 on narratives
- Premium tier (3): 200 on intelligence, 200 on workout-narrative endpoint

**Group B remains xfail:**
- Features not yet built: N=1 plan param verification, readiness score fixtures, advisory mode, multi-race, conversational coach tier-gating, tier transition webhook simulation

---

## Stream 3 — Frontend locked pace CTA (`c89f35d`)

**Files:** `apps/web/app/plans/[id]/page.tsx`, `apps/api/routers/billing.py`, `apps/api/services/stripe_service.py`

**Frontend (`/plans/[id]`):**
1. `paces_locked: boolean` added to `PlanDetail` interface
2. Banner at top of plan page when `paces_locked=true` — "Unlock — $5" button
3. Per-workout inline lock button on quality workouts (`threshold`, `tempo`, `intervals`, `long_mp`) when `coach_notes` is null and `paces_locked=true`
4. `unlockPaces()` — calls `POST /v1/billing/checkout/plan` with `plan_snapshot_id: plan.id`, redirects to Stripe checkout URL
5. Post-payment: `?unlocked=1` param shows success banner, then cleaned from URL via `history.replaceState`

**Backend:**
- `create_one_time_checkout_session()` accepts optional `success_url` override
- Billing router passes `/plans/{id}?unlocked=1` as success URL so athlete lands back on their plan page post-payment (not settings)

---

## Production Deploy

```
git pull: 84529f5..c89f35d (3 new commits + prior session commits)
docker compose up -d --build: exit 0

Note: Production DB had stale dual-head alembic state (garmin_004 + monetization_001).
Fixed by: DELETE FROM alembic_version WHERE version_num = 'garmin_004'
This is the same fix applied to local test DB. CI uses a fresh DB so it's unaffected.

Containers after fix:
  strideiq_api     Up (healthy)
  strideiq_web     Up
  strideiq_worker  Up
  strideiq_postgres Up (healthy)
  strideiq_redis   Up (healthy)
  strideiq_caddy   Up

Smoke check:
  GET /ping → {"status":"alive"}
```

---

## What's Left in Monetization

Everything backend and the primary frontend CTA are done. The remaining items are either:

1. **Upgrade prompts for 403 responses** — when free users hit intelligence endpoints, they see 403. The frontend should show an upgrade CTA ("Get Guided — $15/mo") instead of a blank error. Not yet built.

2. **Group B tests** — will become real tests as features are built (advisory mode gating, tier transition webhooks, etc.)

3. **Post-unlock re-fetch** — after Stripe returns to `/plans/{id}?unlocked=1`, the plan data re-fetches automatically (React Query cache busts on mount). Confirmed via architecture review.

---

## Build Priority (Updated)

Per `TRAINING_PLAN_REBUILD_PLAN.md`:
1. ~~Monetization tier mapping~~ **COMPLETE**
2. Phase 4 (50K Ultra) — next buildable, 37 contract tests waiting
3. Phase 3B — gate accruing (narration accuracy > 90% for 4 weeks)
4. Phase 3C — gate accruing (3+ months data)

---

## Read Order for Next Session

1. `docs/FOUNDER_OPERATING_CONTRACT.md`
2. `docs/TRAINING_PLAN_REBUILD_PLAN.md`
3. This handoff
