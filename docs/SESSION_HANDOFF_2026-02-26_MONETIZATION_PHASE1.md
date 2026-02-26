# Session Handoff — Monetization Phase 1
**Date:** 2026-02-26  
**Status:** Phase 1 Close Gate: PASS (advisor confirmed)  
**Next:** Phase 2 — Feature Gating

---

## What Was Built This Session

### Phase 1A — Canonical Tier Engine
**`apps/api/core/tier_utils.py`** (new)  
Single source of truth for all tier logic. Every tier comparison in the codebase routes through here.

- `normalize_tier(tier)` — maps any string including legacy (`pro`/`elite`/`subscription` → `premium`) to canonical. Fail-closed: unknown/None → `"free"`.
- `tier_level(tier)` — numeric level: `free=0`, `guided=1`, `premium=2`.
- `tier_satisfies(actual, required)` — hierarchy check. `tier_satisfies("pro", "guided")` → `True`.

**`apps/api/core/auth.py`** — updated  
- `require_tier(["guided"])` → allows guided and premium (and all legacy premium-mapped tiers). Uses `tier_level` min-comparison instead of flat `in` membership.
- `require_query_access` → checks `tier_satisfies(tier, "guided")` instead of removed `TOP_TIERS` set.
- Active trial still grants premium-level entitlement.

**`apps/api/routers/athlete_insights.py`** — updated  
Migrated off removed `TOP_TIERS` import → now uses `tier_satisfies`.

### Phase 1B — Stripe Service Hardening
**`apps/api/core/config.py`** — 5 new env vars added:
```
STRIPE_PRICE_PLAN_ONETIME_ID      = price_1T59I4LRj4KBJxHa4dNcbzmd
STRIPE_PRICE_GUIDED_MONTHLY_ID    = price_1T59IULRj4KBJxHawLGlSTRH
STRIPE_PRICE_GUIDED_ANNUAL_ID     = price_1T59IULRj4KBJxHax7vyoVhG
STRIPE_PRICE_PREMIUM_MONTHLY_ID   = price_1T59HxLRj4KBJxHa5mKssgx1
STRIPE_PRICE_PREMIUM_ANNUAL_ID    = price_1T59HxLRj4KBJxHaLGNjwlD3
```
Legacy `STRIPE_PRICE_PRO_MONTHLY_ID` retained for existing subscriber backward-compat.

**`apps/api/services/stripe_service.py`** — redesigned:
- `build_price_to_tier(cfg)` — explicit `price_id → canonical_tier` dict. One-time price excluded (separate entitlement path).
- `tier_for_price_and_status(price_id, status, price_to_tier)` — only place Stripe state becomes a StrideIQ tier. Unknown price → `"free"` + warning log. Non-active/trialing → `"free"`. No auto-promotion.
- `create_checkout_session(tier, billing_period)` — supports `guided`/`premium`. Backward-compat default is `premium`.
- `create_one_time_checkout_session(plan_snapshot_id)` — `mode=payment`, stable artifact key in metadata.
- Webhook `process_stripe_event` — handles subscription and payment modes; uses `tier_for_price_and_status` throughout; replay-safe idempotency guard unchanged.

### Phase 1C — Billing Router
**`apps/api/routers/billing.py`** — updated:
- `CheckoutRequest` — old shape `{"billing_period": "annual"}` still accepted (backward compat). New shape adds `tier`.
- `POST /v1/billing/checkout` — dispatches to guided or premium checkout via canonical tier.
- `POST /v1/billing/checkout/plan` — one-time plan unlock. Ownership verification (`TrainingPlan.athlete_id == current_user.id`) returns 403 on mismatch.

### Phase 1D — Migration
**`apps/api/alembic/versions/monetization_001_tier_migration_and_plan_purchase.py`**:
- Creates `monetization_migration_ledger` — records `(athlete_id, original_tier)` before migrating. Rollback only touches ledger-tracked rows.
- Creates `plan_purchases` — one-time unlock records. `(athlete_id, plan_snapshot_id)` unique constraint. `stripe_payment_intent_id` unique for idempotency.
- Forward: 7 athletes migrated `pro → premium`. Ledger populated.
- Rollback: confirmed safe — only ledger rows reverted, `elite`/`free` untouched.

**`apps/api/models.py`** — `PlanPurchase` ORM model added.

### Tests
**`apps/api/tests/test_tier_engine.py`** — 36 tests, 36 pass  
**`apps/api/tests/test_stripe_service_unit.py`** — 29 tests, 29 pass  
Total: **65/65 pass** in production container.

---

## Gate Check Results (all 6 confirmed PASS)

| Check | Result |
|---|---|
| 1) Checkout matrix (5 calls) | PASS — 5× HTTP 200, `cs_live_...` Stripe URLs |
| 2) Unknown price fail-closed | PASS — all resolve to `free`, warnings logged |
| 3) Webhook idempotency replay | PASS — 2nd delivery `idempotent: True`, 1 event row |
| 4) One-time idempotency | PASS — 2 calls → 1 `plan_purchases` row |
| 5) Migration safety | PASS — ledger-scoped rollback, non-migrated users untouched |
| 6) Regression smoke | PASS — 65/65 in production container |

---

## Commit Log (this session)

```
375ad8d monetization: add Phase 1 close-gate check script
12bb370 monetization: Phase 1 unit tests - tier engine and price-to-tier mapping (65/65 pass)
1f10bfc monetization: Phase 1D - pro-to-premium migration with ledger and PlanPurchase model
7b4ca44 monetization: Phase 1C - billing router with backward-compat checkout and /checkout/plan
849cc02 monetization: Phase 1B - Stripe service hardening with price-to-tier map
445aa7c monetization: Phase 1A - canonical tier engine and auth adoption
```

---

## Production State

- **Server:** `root@187.124.67.153`
- **Containers:** all healthy (`strideiq_api`, `strideiq_worker`, `strideiq_web`, `strideiq_postgres`, `strideiq_redis`, `strideiq_caddy`)
- **DB migration:** `monetization_001` applied (both heads: `garmin_004`, `monetization_001`)
- **Stripe mode:** Live (`sk_live_...`)
- **Stripe prices:** All 5 IDs loaded in container env

### Known state: `mbshaf@gmail.com` stripe_customer_id
Cleared to `NULL` during gate check testing (test-mode customer ID was incompatible with live Stripe key). Will repopulate automatically on first real checkout completion via webhook. No action needed unless the founder actively uses this account for a real checkout before that.

---

## Open Items for Phase 2

### Phase 2 — Feature Gating (next build)

Per builder note:

**Feature Access Contract to implement:**
- `free` → public tools + basic plan structure (no pace targets)
- `one-time` → full paces for purchased artifact only (static, no adaptation)
- `guided` → full paces + adaptation/intelligence/tracking
- `premium` → guided + narratives/advisory/multi-race/dashboard

**Output contract (must define):**
- Locked pace fields: always `null` OR always omitted — pick one, enforce in tests.

**Required negative tests:**
- Free blocked from guided/premium endpoints.
- One-time cannot access guided-only endpoints.
- Guided blocked from premium-only endpoints.
- Cross-athlete plan unlock impossible.

### Deferred to Phase 2: Purchase model question
`PlanPurchase` (new, Phase 1) vs `Purchase` (existing, line 1666 models.py). Decision: keep `PlanPurchase` — it has proper idempotency key (`stripe_payment_intent_id` unique) and per-athlete artifact constraint. Old `Purchase` model is a candidate for deprecation when feature flag system aligns to new tier model. Not blocking.

### xfail contract tests
29 tests in `test_monetization_tier_mapping.py` remain xfail — these are Phase 5 work (after Phase 2 gating and Phase 3 frontend are built).

---

## Read Order for Next Builder

1. `docs/FOUNDER_OPERATING_CONTRACT.md`
2. `docs/PRODUCT_MANIFESTO.md`
3. `docs/TRAINING_PLAN_REBUILD_PLAN.md`
4. `apps/api/tests/test_monetization_tier_mapping.py` (29 xfail contracts)
5. `apps/api/core/tier_utils.py` (canonical tier engine — read before touching any access control)
6. `apps/api/services/stripe_service.py` (price→tier mapping, one-time flow)
7. This handoff doc
