# Monetization

## Current State

Two-tier model with a 30-day free trial. Stripe handles all billing. The original 4-tier model was explicitly superseded by the two-tier reset (Mar 19, 2026).

## Tiers

| Tier | Price | What you get |
|------|-------|-------------|
| **Free** | $0 | 30-day coach trial, basic activity tracking, training load |
| **StrideIQ Subscriber** | $24.99/mo or $199/yr | Full coach access, N=1 intelligence, daily insights, plan generation, Personal Operating Manual |

### Promo Codes

- **RUNTHEDIST** — promo code for the founder's upcoming 10K race

### What's NOT in the tier model

- `PlanTier` (`standard`/`semi_custom`/`custom`/`model_driven`) is a **generation axis**, not a monetization tier. It controls how the plan engine generates plans, not what the athlete pays.
- The 4-tier model (free/guided/premium/pro) was **explicitly superseded** by the two-tier reset.

## Implementation

### Stripe Integration

| File | Role |
|------|------|
| `services/stripe_service.py` | Stripe subscriptions, payments, customer management |
| `routers/billing.py` | Billing API endpoints |
| `core/tier_utils.py` | Tier/entitlement helpers |
| `core/pace_access.py` | Pace data access control by tier |

### Webhook

`POST https://strideiq.run/v1/billing/webhooks/stripe` — receives Stripe events.

### Key Environment Variables

- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `STRIPE_PRICE_SUBSCRIBER_MONTHLY`
- `STRIPE_PRICE_SUBSCRIBER_ANNUAL`

### Models

- `Subscription` — tracks active subscriptions
- `StripeEvent` — logs all Stripe webhook events
- `PlanPurchase` — plan purchase records
- `Purchase` — general purchase records
- `RacePromoCode` — promo code management

## Key Decisions

- **Two tiers only:** Complexity is the enemy. Free trial converts or doesn't.
- **30-day trial:** Enough time for the intelligence engine to discover patterns and demonstrate value
- **Coach access = paid differentiator:** The AI coach is the primary monetization lever
- **No pace-blurring:** Previously considered blurring pace data for free users — rejected

## Sources

- `docs/specs/MONETIZATION_RESET_SPEC.md` — two-tier reset decision
- `docs/TRAINING_PLAN_REBUILD_PLAN.md` — monetization mapping section
- `apps/api/services/stripe_service.py` — Stripe implementation
- `apps/api/routers/billing.py` — billing endpoints
