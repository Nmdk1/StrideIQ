# Session Handoff — Monetization Complete (Frontend Last Mile added)

**Date:** 2026-02-26  
**Backend Commits:** `48ac179`, `46c7c72`, `c89f35d`  
**Frontend Last Mile Commits:** `2917e73`, `7d8ac2a`, `4f80f64`, `e906d7b`  
**Status:** SHIPPED — all monetization surfaces live, production healthy

---

## Frontend Last Mile (4 additional commits)

### Stream A — Pricing.tsx (`2917e73`)

Replaced 2-tier Free/Elite view with canonical 4-tier model:

| Tier | Price | CTA |
|------|-------|-----|
| Free | $0 | `/register` |
| Race Plan Unlock | $5 one-time | `/register` |
| Guided | $15/mo or $150/yr | `/settings?upgrade=guided&period=<period>` (authed) or `/register?tier=guided` |
| Premium | $25/mo or $250/yr | `/settings?upgrade=premium&period=<period>` (authed) or `/register?tier=premium` |

- Monthly/annual toggle — annual selected by default; savings callout per tier ("Save $30/yr", "Save $50/yr")
- Authenticated users deep-linked directly to Settings upgrade panel; unauthenticated users go to `/register`
- Guided card has "Most Popular" badge and orange border highlight

### Stream B — Settings tier display + checkout UI (`7d8ac2a`, fixes `4f80f64`, `e906d7b`)

Replaced binary `hasPaidAccess ? 'pro' : 'free'` with canonical 3-tier display:

- **`canonicalizeTier(rawTier, hasActiveSub)`** — normalises all legacy values (pro, elite, subscription) to `free | guided | premium`
- Membership card shows: "Free Plan", "Guided Plan", or "Premium Plan" — no more "PRO PLAN"
- Tier-aware upgrade panel:
  - **Free users**: period toggle (Monthly/Annual) + two checkout cards (Guided / Premium) — both show tier features and CTA
  - **Guided users**: period toggle + one card (Premium upgrade)
  - **Premium users**: "Manage subscription" only (Stripe portal)
- Each CTA calls `POST /v1/billing/checkout` with `{tier, billing_period}` — matches the existing backend contract exactly
- `?upgrade=guided&period=annual` URL params pre-seed the panel (from Pricing page deep link); uses `window.location.search` instead of `useSearchParams()` to avoid Next.js Suspense boundary requirement
- Build fix: removed `<Suspense>` wrapper from default export after dropping `useSearchParams`

### Production smoke check (post-deploy)

```
GET https://strideiq.run/       → 200
GET https://strideiq.run/settings → 200
GET https://strideiq.run/ping   → 200
docker ps: all 6 containers Up and healthy
```

### Tests (no regressions)

```
python -m pytest tests/test_monetization_tier_mapping.py tests/test_stripe_service_unit.py -v
46 passed, 12 xfailed, 0 failed
```

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
```

### Alembic Dual-Head Incident — Ops Runbook

**What happened:**  
After deploy, `strideiq_api` entered a restart loop. Logs showed:
```
ERROR: Alembic upgrade failed: Requested revision monetization_001 overlaps with other requested revisions garmin_004
```

**Root cause:**  
The production `alembic_version` table had two rows:
```
 version_num
------------------
 monetization_001
 garmin_004
```
This occurred because `monetization_001` was deployed to production in a prior session with `down_revision = "sleep_quality_001"` (wrong parent), making Alembic think both `garmin_004` and `monetization_001` were independent heads. The `down_revision` was subsequently corrected to `"garmin_004"` in the migration file and in `ci_alembic_heads_check.py`, but the production tracking row was never cleaned up — it was still carrying both entries.

**Why the fix was safe:**  
`garmin_004`'s DDL (all Garmin columns, ActivityStream, etc.) was already physically applied to the database — the tables and columns exist. The `alembic_version` row for `garmin_004` was purely a tracking artifact incorrectly indicating it was still a "head." Removing it simply corrected the bookkeeping to match reality: `monetization_001` is the single head, chained from `garmin_004`.

**Exact commands run on production:**

```bash
# BEFORE — confirmed dual-head state
docker exec strideiq_postgres psql -U postgres -d running_app \
  -c "SELECT version_num FROM alembic_version;"
#  version_num
# ------------------
#  monetization_001
#  garmin_004
# (2 rows)

# FIX — remove stale tracking row
docker exec strideiq_postgres psql -U postgres -d running_app \
  -c "DELETE FROM alembic_version WHERE version_num = 'garmin_004';"
# DELETE 1

# Restart API
docker restart strideiq_api

# AFTER — verify single clean head (inside API container)
docker exec strideiq_api alembic -c /app/alembic.ini current
# monetization_001 (head)
```

**CI is unaffected:** CI spins up a fresh Postgres for every run. It applies migrations from scratch in chain order. The dual-head issue only surfaces on a persistent DB that carried the stale row from a prior deployment.

**Recurrence prevention:** `ci_alembic_heads_check.py` already enforces `EXPECTED_HEADS = {"monetization_001"}`. Any future migration that doesn't chain correctly will fail CI before reaching production.

```
Containers after fix:
  strideiq_api     Up (healthy)  ← confirmed with alembic current = monetization_001 (head)
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

Frontend last mile is now also shipped. Remaining deferred items:

1. **Upgrade prompts for 403 responses** — when free users hit intelligence endpoints, they see 403. The frontend should show an upgrade CTA ("Get Guided — $15/mo") instead of a blank error. Not yet built.

2. **Deep-link from `/register` → Settings upgrade** — currently, a new user clicking a paid tier on the Pricing page goes to `/register?tier=guided&period=annual`. After registration the flow lands on onboarding/home, not the Settings upgrade panel. A future improvement: the register page reads `?tier=` and `?period=` and redirects post-registration to `/settings?upgrade=<tier>&period=<period>`. This is a UX polish item, not a blocking gap.

3. **Group B tests** — will become real tests as features are built (advisory mode gating, tier transition webhooks, etc.)

4. **Post-unlock re-fetch** — after Stripe returns to `/plans/{id}?unlocked=1`, the plan data re-fetches automatically (React Query cache busts on mount). Confirmed via architecture review.

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
