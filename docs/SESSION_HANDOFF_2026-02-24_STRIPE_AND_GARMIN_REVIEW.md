# Session Handoff — Stripe Setup & Garmin Partner Review

**Date:** February 24, 2026
**Status:** Stripe live in production. Garmin disconnect bug fixed. Garmin partner review in progress.
**Branch:** `main` (commit `9b11504`)
**Prior handoff:** `docs/SESSION_HANDOFF_2026-02-22_GARMIN_LIVE.md`

---

## Read order before first tool call

1. `docs/FOUNDER_OPERATING_CONTRACT.md`
2. `docs/PRODUCT_MANIFESTO.md`
3. `docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md`
4. `docs/TRAINING_PLAN_REBUILD_PLAN.md`
5. `docs/SESSION_HANDOFF_2026-02-22_GARMIN_LIVE.md` (prior Garmin state)
6. This document

---

## What happened this session

### 1. Stripe plugin installed and MCP server connected

Stripe Cursor plugin installed with full MCP toolset. Server authenticated and available for live API calls within the IDE.

Available tools: `create_product`, `create_price`, `list_products`, `list_prices`, `list_customers`, `list_subscriptions`, `create_checkout_session`, `create_payment_link`, `list_invoices`, `create_refund`, `list_disputes`, `stripe_integration_recommender`, `search_stripe_documentation`, and more.

---

### 2. Stripe fully set up in production (live mode)

**Stripe account:** `acct_1T4SGOLRj4KBJxHa`

**Product created:**

| Field | Value |
|---|---|
| Name | StrideIQ Pro |
| Product ID | `prod_U2XZC71b1B6nxX` |
| Description | N=1 training intelligence. Daily adaptation. Your plan learns you. |

**Prices created:**

| Billing | Price ID | Amount |
|---|---|---|
| Monthly | `price_1T4SUtLRj4KBJxHa4sq8e35A` | $14.99/mo |
| Annual | `price_1T4SUuLRj4KBJxHat0sHVdrw` | $149.00/yr |

**Customer Portal:** Configured in Stripe Dashboard (live mode).

**Webhook:** `strideiq-production` registered in Stripe Workbench.

| Field | Value |
|---|---|
| Destination ID | `we_1T4StVLRj4KBJxHaMH3qURqm` |
| Endpoint URL | `https://strideiq.run/v1/billing/webhooks/stripe` |
| Events | `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted` |
| Status | Active |

**Production `.env` additions (already on droplet):**
```
STRIPE_PRICE_PRO_MONTHLY_ID=price_1T4SUtLRj4KBJxHa4sq8e35A
STRIPE_PRICE_PRO_ANNUAL_ID=price_1T4SUuLRj4KBJxHat0sHVdrw
STRIPE_WEBHOOK_SECRET=whsec_d14No78S0mZ8AAYubytWQS7tlBJFihvq
```

**`.env.example` updated** with real price IDs as documented defaults.

**The full billing flow is production-ready:**
- Checkout session creation → Stripe hosted checkout
- Customer Portal for self-service subscription management
- Webhook-driven subscription mirroring: `Subscription` table + `athlete.subscription_tier` flips to `pro` on `checkout.session.completed`

---

### 3. Garmin disconnect bug fixed (commit `9b11504`)

**Bug:** `POST /v1/garmin/disconnect` returned 500 for accounts with Garmin activity data.

**Root cause:** `activity_split` table has a FK constraint on `activity.id`. The disconnect handler deleted `ActivityStream` rows and then `Activity` rows, but did not delete `ActivitySplit` rows first — causing `ForeignKeyViolation`.

**Fix:** Added `ActivitySplit` deletion between `ActivityStream` and `Activity` deletions in `apps/api/routers/garmin.py`.

```python
# Step 5 — delete order now:
db.query(ActivityStream).filter(...).delete()
db.query(ActivitySplit).filter(...).delete()   # ← added
db.query(Activity).filter(...).delete()
```

**Files changed:**
- `apps/api/routers/garmin.py` — import `ActivitySplit`, delete before `Activity`

**Tested:** Founder disconnected and reconnected successfully in production.

---

### 4. Garmin partner review — Elena Kononova

Elena Kononova (Garmin Connect Partner Services) requested a screenshot of the authorization page.

- Founder disconnected temporarily to expose the connect button
- Screenshots sent: pre-connection (connect button visible) + post-connection (connected state)
- Email reply sent with screenshots and URL (`https://strideiq.run/settings`)
- Garmin review status: **awaiting response**

---

### 5. Host migration deferred

Decision: do not migrate to larger droplet yet.

Reasons:
- Garmin backfill is actively running post-reconnect
- Stripe is brand new — want 24-48h stability before touching infrastructure
- No current performance emergency (p95 home briefing at 1.98s, SLO met)

**Revisit after:** Garmin approval received + backfill stable for 24h+

---

## Current production state

| Item | Status |
|---|---|
| Droplet | `main` at `9b11504` |
| Stripe | Live — product, prices, webhook, portal all configured |
| Garmin | Founder reconnected, webhooks flowing, backfill running |
| Feature flag `garmin_connect_enabled` | rollout 0%, allowlist: founder + father |
| Home briefing p95 | 1.98s (SLO: < 2s) ✅ |

---

## Open items (priority order per build plan)

### Immediate
1. **Garmin backfill fix** (from prior handoff — still open)
   - Add `resp.text` logging for non-202 responses in `garmin_backfill.py`
   - Use 30-day range for activities/activityDetails, 90 days for health endpoints
   - Add 429 retry logic
   - File: `apps/api/services/garmin_backfill.py`

2. **Garmin partner approval** — awaiting Elena's response

### Next build priority (per `docs/TRAINING_PLAN_REBUILD_PLAN.md`)
1. **Monetization tier mapping** — Stripe infrastructure is live; now build the tier gating logic (29 xfail contract tests)
2. **Phase 4 (50K Ultra)** — 37 xfail contract tests, ready to build
3. **Phase 3B** — gate: narration accuracy > 90% for 4 weeks (monitor `/v1/intelligence/narration/quality`)
4. **Phase 3C** — gate: 3+ months data + significant correlations

### Compliance (Garmin)
- 30-day display notice screenshots — send to Garmin
- ToS review for Garmin-protective liability language
- Document breach notification procedure

---

## What NOT to touch

- Do not change Stripe price IDs or product without founder sign-off
- Do not modify feature flag allowlist without founder instruction
- Do not touch Strava sync, home briefing, or AI coach code
- Do not re-propose anything in `docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md` rejected decisions
- Scoped commits only — never `git add -A`
