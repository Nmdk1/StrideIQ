# Session Handoff — Monetization v1 Complete

**Date:** 2026-02-26  
**Status:** MONETIZATION v1 COMPLETE — all revenue surfaces shipped and verified

---

## What "Monetization v1 Complete" Means

All features required for a new visitor to find, evaluate, purchase, and receive a paid tier are live:

| Capability | Status |
|---|---|
| 4-tier pricing page (Free / One-time / Guided / Premium) | ✅ Shipped |
| Monthly/annual toggle with savings callout | ✅ Shipped |
| Stripe checkout for all paid tiers | ✅ Shipped |
| Settings tier display + upgrade panel | ✅ Shipped |
| Plan-page locked-pace CTA + $5 one-time unlock | ✅ Shipped |
| PDF plan export (entitlement-gated via `can_access_plan_paces`) | ✅ Shipped |
| Register intent carry-through (`?tier=&period=` → post-signup settings redirect) | ✅ Shipped |
| Backend tier mapping + `tier_satisfies()` utility | ✅ Shipped |
| PDF generation guardrails (scope cap, byte cap, timeout) | ✅ Shipped |

---

## Stream 1 — Register Intent Carry-Through (this session)

**Problem:** A user clicking "Start Guided" on the Pricing page landed on `/register?tier=guided&period=annual`. After registering, the `?tier=` and `?period=` params were silently dropped. The user landed on `/onboarding` with no path to the upgrade panel.

**Fix — `apps/web/app/register/page.tsx`:**
- `parseTierIntent(tier, period)` validates params — only `guided` | `premium` are accepted; everything else (including `free`, `elite`, empty) falls back to `/onboarding`
- `period` defaults to `annual` if absent or invalid
- Post-registration redirect: if intent present → `/settings?upgrade=<tier>&period=<period>`; otherwise → `/onboarding`
- Contextual hint rendered on the form when intent is present: "You're signing up for the Guided ($15/mo) plan — you'll be redirected to subscribe right after."

**Loop prevention:** The Settings page reads `?upgrade=` and `?period=` once in a `useEffect` to pre-seed the upgrade panel state. It never re-routes back to `/register`. No loop is possible.

**Tests — `apps/web/__tests__/register-intent-carry.test.tsx` (10 tests, 10 passed):**
- No intent → routes to `/onboarding`; no hint shown
- `?tier=guided&period=annual` → hint shown, routes to `/settings?upgrade=guided&period=annual`
- `?tier=guided&period=monthly` → routes to `/settings?upgrade=guided&period=monthly`
- `?tier=premium&period=annual` → hint shows "Premium", routes correctly
- Invalid tier (`elite`, `free`) → falls back to `/onboarding`, no hint
- Missing period → defaults to `annual`

---

## Stream 2 — xfail Audit (this session)

**File:** `apps/api/tests/test_monetization_tier_mapping.py`

All 12 Group B xfails were reviewed against the full shipped feature set. **Zero represent shipped behavior.** Every xfail is blocked by a genuine unbuilt gate:

| Test | Gate blocking promotion |
|---|---|
| `test_guided_gets_n1_plan_parameters` | Needs Strava fixture + plan-generation integration |
| `test_guided_gets_readiness_score` | Needs DailyReadiness activity data fixtures |
| `test_guided_gets_completion_tracking` | Needs full workout state-machine integration |
| `test_guided_no_advisory_mode` | `/v1/coach/chat` not yet tier-gated |
| `test_premium_gets_coach_advisory_mode` | Advisory mode not yet built |
| `test_premium_gets_multi_race_planning` | Phase 4 infrastructure not yet built |
| `test_premium_gets_intelligence_bank_dashboard` | Dashboard endpoint does not yet exist |
| `test_premium_gets_conversational_coach` | Coach endpoint not yet tier-gated |
| `TestTierTransitions` (4 tests) | Stripe webhook simulation fixtures not in test infra |

An audit comment block was added to the file documenting this conclusion and providing promotion rules for future builders.

**Test result: 46 passed, 12 xfailed, 0 failed** — identical to pre-session state.

---

## Test Evidence

### Backend monetization tests
```
python -m pytest tests/test_monetization_tier_mapping.py tests/test_stripe_service_unit.py -v
46 passed, 12 xfailed, 0 failed
```

### Frontend intent carry-through tests
```
npx jest --testPathPattern="register-intent-carry" --watchAll=false
10 passed, 0 failed
```

---

## Monetization v1 — Explicitly Deferred Items

These are intentionally deferred and known. They are NOT gaps.

1. **403 upgrade prompts** — when free users hit intelligence endpoints they see a raw 403. A future UX improvement would show an inline "Get Guided — $15/mo" CTA instead of an error. Not blocking.

2. **Group B xfails (12 tests)** — will become real tests as features are built: advisory mode, N=1 fixtures, tier-transition webhook simulation, multi-race, etc.

3. **Post-unlock re-fetch** — confirmed via architecture review: React Query cache busts on mount after `/plans/{id}?unlocked=1`. No additional work needed.

4. **Onboarding skip for paid intent** — users with tier intent bypass onboarding to reach Settings faster. Onboarding remains accessible via `/onboarding` if needed later. This is intentional product behavior.

---

## Build Priority (Updated)

Per `docs/TRAINING_PLAN_REBUILD_PLAN.md`:

1. ~~Monetization tier mapping~~ **COMPLETE**  
2. ~~PDF plan export~~ **COMPLETE**  
3. ~~Register intent carry-through~~ **COMPLETE**  
4. **Phase 4 (50K Ultra)** — next buildable; 37 contract tests waiting  
5. Phase 3B — gate accruing (narration accuracy > 90% for 4 weeks)  
6. Phase 3C — gate accruing (3+ months data)

---

## Read Order for Next Session

1. `docs/FOUNDER_OPERATING_CONTRACT.md`
2. `docs/TRAINING_PLAN_REBUILD_PLAN.md`
3. This handoff (`SESSION_HANDOFF_2026-02-26_MONETIZATION_V1_COMPLETE.md`)
