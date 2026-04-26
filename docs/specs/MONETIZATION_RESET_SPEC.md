# Monetization Reset Spec

**Author:** Top Advisor (March 2026)
**Status:** ✅ IMPLEMENTED (2026-03-19) — shipped as 2-tier only (Free + StrideIQ Subscriber). The $5 one-time plan unlock described below was NOT implemented — paces are included for all tiers. See `TRAINING_PLAN_REBUILD_PLAN.md` Monetization Mapping for the canonical production state.
**Priority:** Revenue-critical

## Executive Summary

Collapse the current 4-tier monetization structure (Free / $5 one-time / Guided $15 / Premium $25) into a 2-tier model with a 30-day auto-trial. Gate the coach behind the paid tier. This is the single highest-leverage change for converting free users to paying athletes.

## The Problem

1. **The coach — the product's strongest feature — is completely free.** No `require_tier` on any coach endpoint. A free user gets the same model, context, tools, and fact memory as a paying user.
2. **Paid features are invisible.** Daily intelligence, readiness, adaptation — these are backend capabilities that the athlete cannot see or feel on current surfaces.
3. **Two paid tiers fragment a small user base.** Guided vs. Premium distinction creates decision fatigue and the Premium tier has almost no additional value (workout narratives only).
4. **No auto-trial.** Trial requires a manual POST to `/v1/billing/trial/start`. New athletes start on free with no taste of the full product.
5. **Net result:** No compelling reason for a free athlete to convert.

## Target State

| Tier | Price | Access |
|------|-------|--------|
| **Free** (post-trial) | $0 | Pace calculators, WMA age-grading, heat adjustment, race equivalency, plan preview (paces blurred), calendar view, activity list |
| **$5 Plan Unlock** | $5 one-time | Everything in Free + full plan paces for one plan (kept as micro-transaction entry point) |
| **StrideIQ** | $24.99/mo or $199/yr | Everything: Coach, morning briefing, daily intelligence, readiness, adaptation engine, plan generation, plan modification, runtoon, analytics, workout narratives, full fingerprint |

Every new athlete gets a **30-day full trial** on signup. During the trial, they have complete access to the StrideIQ tier. After 30 days, the coach and intelligence lock. The free tools remain.

## Why 30 Days

The product's value proposition is compounding personal knowledge. The correlation engine needs ~15 activities and ~20 days of data to surface meaningful N=1 findings. The coach needs conversations to build fact memory. A 7-day trial produces a demo. A 30-day trial produces an experience the athlete can't replace.

By day 30, the switching cost is real: the system has learned things about the athlete that took 30 days to accumulate. The decision to subscribe isn't "should I pay for an app?" — it's "can I afford to lose everything it learned about me?"

LLM cost of a 30-day trial: ~$3-5 per athlete. This is the customer acquisition cost. Significantly cheaper than paid advertising.

## Changes Required

### 1. Auto-Trial on Registration

**File:** `apps/api/routers/auth.py` → `register()` (line ~171-188)

Currently, trial is only started for athletes with a valid `race_promo_code`. Change to: **always start a 30-day trial on registration**, with race promo codes able to extend beyond 30 days.

```python
# After creating the athlete object (line ~171)
now = datetime.now(timezone.utc)

# Always start 30-day trial
default_trial_days = 30
athlete.trial_started_at = now
athlete.trial_source = "signup"

# Race promo can extend beyond default
if race_promo and trial_days and trial_days > default_trial_days:
    athlete.trial_ends_at = now + timedelta(days=trial_days)
    athlete.trial_source = f"race:{race_promo.code}"
else:
    athlete.trial_ends_at = now + timedelta(days=default_trial_days)
```

**No schema change needed.** The `trial_started_at`, `trial_ends_at`, and `trial_source` columns already exist on the Athlete model.

### 2. Gate the Coach Behind Paid Tier

**File:** `apps/api/routers/ai_coach.py`

Add `require_tier(["guided"])` to ALL coach endpoints:

| Endpoint | Current Auth | New Auth |
|----------|-------------|----------|
| `POST /v1/coach/chat` | `get_current_athlete` | `require_tier(["guided"])` |
| `POST /v1/coach/chat/stream` | `get_current_athlete` | `require_tier(["guided"])` |
| `POST /v1/coach/new-conversation` | `get_current_athlete` | `require_tier(["guided"])` |
| `GET /v1/coach/context` | `get_current_athlete` | `require_tier(["guided"])` |
| `GET /v1/coach/suggestions` | `get_current_athlete` | `require_tier(["guided"])` |
| `GET /v1/coach/history` | `get_current_athlete` | `require_tier(["guided"])` |

Using `require_tier(["guided"])` means any athlete at guided level OR above (including premium and trial-elevated) has access. This is the minimum paid tier gate. Trial users pass because `require_tier` already elevates free+active-trial to premium level (see `auth.py` lines 299-308).

### 3. Single Subscription Tier in Checkout

**File:** `apps/api/routers/billing.py` → `create_checkout()` (line ~92)

Remove the `guided` vs `premium` tier selection. All new subscriptions create a checkout for `premium` tier at the new price points.

**Stripe product and prices (CREATED — live in Stripe):**

| Resource | ID | Details |
|----------|-----|---------|
| Product: StrideIQ | `prod_UAo8wlJVm24lPF` | Single subscription product |
| Monthly Price | `price_1TCSWBLRj4KBJxHaZuwbWteL` | $24.99/mo recurring |
| Annual Price | `price_1TCSWCLRj4KBJxHapRzdPIVq` | $199/yr recurring |

**Env vars to add to production `.env`:**
```
STRIPE_PRICE_STRIDEIQ_MONTHLY_ID=price_1TCSWBLRj4KBJxHaZuwbWteL
STRIPE_PRICE_STRIDEIQ_ANNUAL_ID=price_1TCSWCLRj4KBJxHapRzdPIVq
```

**Checkout endpoint changes:**
- Remove `tier` parameter from checkout request body (or ignore it)
- Default to `premium` internally for all new subscriptions
- Use `STRIPE_PRICE_STRIDEIQ_MONTHLY_ID` and `STRIPE_PRICE_STRIDEIQ_ANNUAL_ID`
- Keep `STRIPE_PRICE_PLAN_ONETIME_ID` for $5 plan unlock (unchanged)

**No existing subscribers to migrate.** Old Guided/Premium/Pro products can be archived in Stripe once this ships.

### 4. Update Pricing Page

**File:** `apps/web/app/components/Pricing.tsx`

Replace the 4-tier layout with a 2-tier layout (+ plan unlock):

**Free column:**
- Training pace calculator
- WMA age-grading
- Heat-adjusted pace
- Race equivalency
- Plan preview (paces blurred)
- 30-day full trial included

**StrideIQ column ($24.99/mo or $199/yr):**
- Personal AI running coach
- Morning briefing with your data
- Daily intelligence & readiness
- Adaptive training plans
- Real-time plan modification
- Performance analytics
- Living Fingerprint (learns you over time)
- "Start 30-Day Free Trial" CTA (not "Subscribe")

The CTA should be trial-first. The athlete clicks "Start 30-Day Free Trial" → registers → gets full access. No credit card required for trial. Payment only when they convert at day 30.

### 5. Remove Premium-Only Distinction

**File:** `apps/api/routers/daily_intelligence.py` (line ~371)

Currently: `require_tier(["premium"])` on workout narrative endpoint.
Change to: `require_tier(["guided"])` — same as all other intelligence endpoints.

With a single paid tier, there's no reason to gate workout narratives separately. All paid athletes and trial users get everything.

### 6. Trial Expiry Nudge System

**New files needed:**

#### a. Trial status endpoint
**File:** `apps/api/routers/billing.py` — add endpoint

```
GET /v1/billing/trial/status
```

Returns:
```json
{
  "has_trial": true,
  "trial_days_remaining": 5,
  "trial_ends_at": "2026-04-15T00:00:00Z",
  "facts_learned": 47,
  "findings_discovered": 12,
  "activities_analyzed": 23
}
```

This powers the frontend nudge. The `facts_learned`, `findings_discovered`, and `activities_analyzed` counts make the loss tangible.

#### b. Frontend trial banner
**File:** `apps/web/app/components/TrialBanner.tsx` (new)

Shown when `trial_days_remaining <= 7`:
- **Day 7-3:** Subtle banner: "Your trial ends in X days. Your coach has learned {N} things about you."
- **Day 2-1:** Prominent banner: "Tomorrow your personal coach locks. Subscribe to keep everything it's learned."
- **Day 0 (expired):** Full-width: "Your coaching trial has ended. {N} facts, {N} findings, {N} activities — all waiting for you. Subscribe to unlock."

#### c. Trial expiry email (optional, Phase 2)
Celery task that sends an email at day 25 and day 30. Not required for initial launch — the in-app banner is sufficient.

### 7. Coach Lockout UX

When a post-trial free user taps the coach:

**Do NOT show a 403 error.** Show a dedicated screen:

> "Your personal coach is waiting. During your trial, it learned {N} things about you — your patterns, your goals, your body. Subscribe to pick up where you left off."
>
> [Subscribe — $24.99/mo] [View Annual ($199/yr — save $100)]

The frontend should call `GET /v1/billing/trial/status` to populate the counts, then show this screen instead of the chat UI when the user lacks access.

## Stripe Configuration (DONE)

Product and prices are live in Stripe:
- Product: `prod_UAo8wlJVm24lPF` (StrideIQ)
- Monthly: `price_1TCSWBLRj4KBJxHaZuwbWteL` ($24.99/mo)
- Annual: `price_1TCSWCLRj4KBJxHapRzdPIVq` ($199/yr)

**No existing subscribers.** No migration needed. Old products (Guided, Premium, Pro) can be archived after deploy.

### Existing Beta Users

All current beta users have `admin_tier_override` or direct tier assignments from the founder. These are unaffected — `admin_tier_override` bypasses all tier checks.

## Files Changed Summary

| File | Change |
|------|--------|
| `apps/api/routers/auth.py` | Auto-start 30-day trial on registration |
| `apps/api/routers/ai_coach.py` | Add `require_tier(["guided"])` to all 6 endpoints |
| `apps/api/routers/billing.py` | Single-tier checkout, trial status endpoint |
| `apps/api/routers/daily_intelligence.py` | Relax workout-narrative from premium to guided |
| `apps/api/core/config.py` | Add `STRIPE_PRICE_STRIDEIQ_MONTHLY_ID`, `STRIPE_PRICE_STRIDEIQ_ANNUAL_ID` |
| `apps/web/app/components/Pricing.tsx` | 2-tier layout, trial-first CTA |
| `apps/web/app/components/TrialBanner.tsx` | New — trial countdown with loss-tangibility counts |
| `apps/web/app/components/CoachLockout.tsx` | New — subscribe screen when coach is locked |

## Success Metrics

| Metric | Target |
|--------|--------|
| Trial-to-paid conversion | >15% (industry avg for fitness apps: 5-10%) |
| Coach engagement during trial | >3 conversations in first 7 days |
| Time to first "wow" moment | <5 days (measured by first finding surfaced) |
| Monthly churn (paid) | <5% |
| Target: 700 paying athletes | = $17,493 MRR / $209,916 ARR |

## What This Does NOT Change

- $5 one-time plan purchase (stays as micro-transaction entry point)
- Free pace calculators, heat adjustment, race equivalency (stay free forever)
- Backend tier levels (`free=0, guided=1, premium=2`) — kept for backwards compatibility
- Admin comp override system
- Invite allowlist system
- Race promo code system (promo codes can still extend trial beyond 30 days)

## Sequencing

1. ~~**Create Stripe product and prices**~~ — **DONE** (product `prod_UAo8wlJVm24lPF`, monthly `price_1TCSWBLRj4KBJxHaZuwbWteL`, annual `price_1TCSWCLRj4KBJxHapRzdPIVq`)
2. **Add env vars to production `.env`** on server (2 lines)
3. **Backend: coach gating + auto-trial + trial status endpoint** (one PR)
4. **Frontend: pricing page + trial banner + coach lockout** (one PR)
5. **Deploy and verify** on founder account first
6. **Archive old Stripe products** (Guided, Premium, Pro) after confirmed working
7. **Monitor** trial-to-paid conversion for first 30 days

## Release Gates (Required)

No deploy until all gates are satisfied:

### Gate A - Config readiness
1. `STRIPE_PRICE_STRIDEIQ_MONTHLY_ID` present in API runtime.
2. `STRIPE_PRICE_STRIDEIQ_ANNUAL_ID` present in API runtime.
3. Checkout endpoint returns these exact Stripe price IDs for monthly/annual requests.

### Gate B - Entitlement correctness
1. Fresh signup receives 30-day trial automatically.
2. Trial user can access all 6 coach endpoints.
3. Expired-trial free user is blocked from all 6 coach endpoints.
4. Guided/premium/admin-comp users retain coach access.
5. Workout-narrative endpoint accepts guided tier (not premium-only).

### Gate C - UX correctness
1. Pricing page shows 2-tier + plan unlock model exactly.
2. Trial banner appears at the intended windows (`<= 7 days`).
3. Coach lockout screen replaces generic 403 experience.

### Gate D - Post-deploy health
1. Founder smoke path passes end-to-end.
2. No spike in 4xx/5xx on billing and coach endpoints.
3. No unexpected downgrade of existing admin-comp or Stripe-linked users.

## Builder Test Plan (Minimum)

### Backend tests
1. Registration trial auto-start:
   - signup without promo -> `trial_started_at` set, `trial_ends_at = now + 30d`, `trial_source="signup"`.
   - signup with promo >30d -> extended end date and `trial_source="race:<code>"`.
2. Coach endpoint gating:
   - free no-trial -> 403 on all 6 endpoints.
   - free active-trial -> 200 on all 6 endpoints.
   - guided/premium/admin override -> 200 on all 6 endpoints.
3. Checkout:
   - monthly path uses `STRIPE_PRICE_STRIDEIQ_MONTHLY_ID`.
   - annual path uses `STRIPE_PRICE_STRIDEIQ_ANNUAL_ID`.
   - plan unlock path still uses `STRIPE_PRICE_PLAN_ONETIME_ID`.
4. Trial status endpoint:
   - returns expected shape and non-negative counts.
5. Daily intelligence narrative endpoint:
   - guided now allowed.

### Frontend tests
1. Pricing renders correct copy, tier count, and trial-first CTA.
2. Coach route renders lockout state (not raw 403) for blocked users.
3. Trial banner visibility windows:
   - hidden when >7 days
   - subtle for 7-3
   - prominent for 2-1
   - expired state for 0

## Production Verification Commands (Copy/Paste)

Run on server after env and deploy:

```bash
cd /opt/strideiq/repo
docker compose -f docker-compose.prod.yml restart api worker
sleep 8
echo "from core.config import settings; print('MONTHLY_SET', bool(settings.STRIPE_PRICE_STRIDEIQ_MONTHLY_ID)); print('ANNUAL_SET', bool(settings.STRIPE_PRICE_STRIDEIQ_ANNUAL_ID))" | docker exec -i strideiq_api python
```

Expected:
- `MONTHLY_SET True`
- `ANNUAL_SET True`

Founder smoke:
1. Register fresh test athlete.
2. Confirm trial fields and coach access.
3. Manually simulate expired trial on test athlete.
4. Confirm coach lockout and trial status payload.
5. Start checkout monthly and annual; verify Stripe session uses:
   - `price_1TCSWBLRj4KBJxHaZuwbWteL`
   - `price_1TCSWCLRj4KBJxHapRzdPIVq`

## Rollback Plan

If deploy regresses billing/coach access:
1. Revert backend/frontend to previous release commit.
2. Restart `api` and `worker`.
3. Keep Stripe product IDs unchanged (safe to retain).
4. Temporarily remove coach tier gate only if needed for incident mitigation, then re-apply after fix.

## Required Delivery Format (Every Builder Handoff)

Must include:
1. Exact files changed.
2. Migration revision (expected: none for this spec).
3. Test output pasted (backend + frontend).
4. CI run ID and status.
5. Production verification command output.
6. Explicit known risks remaining.

## Recommended Operational Guardrails

1. Use a dedicated test athlete for monetization smoke (never founder chat thread).
2. Tag logs with release marker `monetization_reset_release` for first 48h.
3. Track hourly:
   - registrations,
   - trial starts,
   - coach 403 rate,
   - checkout session creation success,
   - paid conversion attempts.
