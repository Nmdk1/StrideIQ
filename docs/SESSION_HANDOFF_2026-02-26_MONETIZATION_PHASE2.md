# Session Handoff — Monetization Phase 2: Feature Gating

**Date:** 2026-02-26  
**Commit:** `84529f5`  
**Status:** SHIPPED — all 44 Phase 2 tests passing, deployed to production  

---

## What Was Built

Phase 2 implements the hybrid gating model decided at the top of this session:

1. **Output-layer pace gating** — Plan endpoints always return the plan structure. If the athlete is free with no `PlanPurchase` for this plan, pace target fields (`coach_notes`, `pace_description`) are set to `null`. The frontend blurs them and shows a "$5 to unlock" CTA.

2. **Endpoint-level 403 for intelligence/adaptation** — All intelligence endpoints now require Guided+ tier. Workout narratives require Premium+ tier.

3. **Canonical tier consolidation** — `FeatureFlagService._tier_satisfies()` now delegates to `core.tier_utils` (single source of truth). `require_tier()` trial-elevation bug fixed.

---

## Decisions Made This Session

| Decision | Detail |
|----------|--------|
| Paces gated behind $5 | Supersedes Resolved Decision #1 in TRAINING_PLAN_REBUILD_PLAN.md |
| Hybrid gating | Output-layer for plan data; endpoint 403 for intelligence |
| PlanTier ≠ monetization tier | `standard/semi_custom/custom/model_driven` is generation quality — do not conflate |

---

## Files Changed

| File | Change |
|------|--------|
| `apps/api/core/pace_access.py` | **NEW** — `can_access_plan_paces(athlete, plan_id, db)` utility |
| `apps/api/core/auth.py` | Fixed `require_tier()`: trial elevation only for free-tier athletes, not paid subscribers |
| `apps/api/routers/plan_generation.py` | `get_plan()` + `get_week_workouts()` null `coach_notes` for unauthorized. `_plan_to_preview(show_paces=False)` defaults to blurred |
| `apps/api/routers/daily_intelligence.py` | All endpoints → `require_tier(["guided"])`. Workout-narrative → `require_tier(["premium"])` |
| `apps/api/routers/insights.py` | `/intelligence` → `require_tier(["guided"])` (replaced manual tier check) |
| `apps/api/services/plan_framework/feature_flags.py` | `_tier_satisfies()` delegates to `tier_utils`. `_has_purchased()` checks `PlanPurchase` first |
| `apps/api/tests/test_monetization_phase2.py` | **NEW** — 44 tests covering the full matrix |
| `docs/TRAINING_PLAN_REBUILD_PLAN.md` | Updated Resolved Decision #1 and Monetization Mapping table |

---

## Test Evidence

```
44 passed in tests/test_monetization_phase2.py

Categories:
  Category 1: can_access_plan_paces() utility           8/8 pass
  Category 2: GET /v2/plans/{plan_id} pace gating       5/5 pass
  Category 3: GET /v2/plans/{plan_id}/week pace gating  3/3 pass
  Category 4: Preview pace gating                       2/2 pass
  Category 5: Intelligence 403 gating (guided+)        11/11 pass
  Category 6: Workout narrative 403 (premium+)          3/3 pass
  Category 7: Intelligence bank 403 (guided+)           3/3 pass
  Category 8: FeatureFlagService consolidation          8/8 pass

Pre-existing suite: 2832 passed, 7 skipped, 119 xfailed
Pre-existing failures (NOT caused by Phase 2): 2 Stripe webhook tests
  (verified: same failures on clean main before any changes)
```

---

## Bug Found and Fixed During Implementation

**`require_tier()` trial-elevation was too broad.**

The original code:
```python
if getattr(current_user, "has_active_subscription", False):
    actual_level = max(actual_level, tier_level("premium"))
```

Problem: `has_active_subscription` is `True` for ALL active Stripe subscribers — including Guided ($15/mo). This incorrectly elevated Guided subscribers to Premium-level access, bypassing the workout-narrative gate.

Fix: Trial elevation only applies when the base tier is free (i.e., no paid subscription yet):
```python
athlete_tier_is_free = tier_level(getattr(current_user, "subscription_tier", "free")) == 0
if athlete_tier_is_free and getattr(current_user, "has_active_subscription", False):
    actual_level = max(actual_level, tier_level("premium"))
```

This correctly handles:
- Free + active trial → premium-level access ✓
- Guided subscriber → guided-level only ✓
- Premium subscriber → premium-level ✓

---

## Production Status

```
Deployed: 2026-02-26
Commit: 84529f5 on main

Container health:
  strideiq_api     Up (healthy)
  strideiq_web     Up
  strideiq_worker  Up
  strideiq_postgres Up (healthy)
  strideiq_redis   Up (healthy)
  strideiq_caddy   Up

Smoke checks:
  GET /ping                          → {"status":"alive"}
  GET /v1/intelligence/today (unauth) → 401 (correct)
  GET /v2/plans/options              → 200 (public endpoint works)
```

---

## Frontend Work Needed (Not Part of Phase 2 Backend Scope)

The following frontend changes are needed to complete the user-facing feature:

1. **Plan view** — When `paces_locked: true` in the plan response (now returned alongside the plan), blur `coach_notes` with a "$5 to unlock" CTA that links to the Stripe checkout for this `plan_id` (which becomes the `plan_snapshot_id` for the `PlanPurchase`).

2. **Preview** — When `pace_description` is null in a preview response, show a blurred pace slot with the same CTA.

3. **After purchase** — After Stripe webhook fires and `PlanPurchase` is created, the plan re-fetch will return full paces. Frontend should re-fetch the plan after payment confirmation.

4. **Intelligence/adaptation endpoints** — Show upgrade prompts when 403 is returned from intelligence endpoints for free users.

---

## Open Items for Phase 3 (Monetization)

Per the Monetization Mapping in `TRAINING_PLAN_REBUILD_PLAN.md`:

- **Monetization contract tests** — 29 xfail tests in the existing suite covering the full tier mapping. These need to become real tests (currently xfail).
- **Guided/Premium plan generation access** — Custom plan generation still gated through `EntitlementsService`. Should be verified that `EntitlementsService` uses `tier_utils` (not the old binary free/pro model).
- **`_check_paid_tier()` in plan_generation.py** — This inline helper still uses a hand-rolled tier check. Should be replaced with `tier_utils.tier_satisfies()`.
- **Frontend UI** — The full "$5 to unlock" conversion funnel needs implementation.

---

## Read Order for Next Session

1. `docs/FOUNDER_OPERATING_CONTRACT.md`
2. `docs/TRAINING_PLAN_REBUILD_PLAN.md` (updated Monetization Mapping)
3. This handoff
