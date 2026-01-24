# ADR-055: Stripe MVP (Hosted Checkout + Portal + Webhooks)

## Status
**Accepted (Implemented)**

## Date
2026-01-24

## Context
StrideIQ needs to monetize the existing Strava-based product immediately without building a custom billing system.

Constraints:
- **Monthly only** for MVP (reduce refund/proration complexity).
- Single paid tier: **Pro** (`pro`) vs **Free** (`free`).
- Prefer Stripe-hosted experiences (Checkout + Customer Portal) to minimize UI surface area and security risk.

## Decision
Use Stripe as the billing source of truth and implement a minimal, robust integration:

1) **Checkout**: Stripe Checkout Session in `mode="subscription"` for upgrades to Pro.  
2) **Portal**: Stripe Customer Portal Session for manage/cancel/update payment method.  
3) **Webhooks**: Signature-verified webhook endpoint with **idempotency** to update a DB mirror and entitlements.

### DB mirror tables
- `subscriptions`: subscription mirror for queries + entitlements
- `stripe_events`: processed event ids for webhook idempotency

### Entitlement policy (MVP)
- `active` / `trialing` → `pro`
- everything else → `free`

## Configuration (required)
This integration is designed to be Stripe-hosted (no custom payment UI).

**Required environment variables (API):**
- `STRIPE_SECRET_KEY` (Stripe secret key; test in dev, live in prod)
- `STRIPE_PRICE_PRO_MONTHLY_ID` (Price id for Pro monthly subscription)

**Required for webhooks:**
- `STRIPE_WEBHOOK_SECRET` (signing secret for the configured webhook endpoint)

**Optional (defaults to `WEB_APP_BASE_URL`):**
- `STRIPE_CHECKOUT_SUCCESS_URL` (defaults to `.../settings?stripe=success`)
- `STRIPE_CHECKOUT_CANCEL_URL` (defaults to `.../settings?stripe=cancel`)
- `STRIPE_PORTAL_RETURN_URL` (defaults to `.../settings`)

**Webhook endpoint (API):**
- `POST /v1/billing/webhooks/stripe`

## Local dev notes
- Checkout/portal can work without configuring webhooks (useful for early UI testing).
- For webhook testing in local dev, use the Stripe CLI (or equivalent) to forward events to your API:
  - Forward to `http://localhost:8000/v1/billing/webhooks/stripe`
  - Set `STRIPE_WEBHOOK_SECRET` to the signing secret provided by your local forwarding tool.

## Considered Options (Rejected)
- **Custom billing UI** (too much surface area; reinvents Stripe; higher risk).
- **Annual plans** in MVP (more proration/refund complexity; not needed to test willingness to pay).

## Consequences
### Positive
- Fast path to revenue with minimal custom code.
- Stripe-hosted surfaces reduce PCI/security scope.
- Webhook idempotency prevents double-processing and state corruption.

### Negative
- Requires correct webhook signature verification (raw body).
- Requires careful mapping from Stripe customer/subscription ids to athletes.

## Security / Privacy Considerations
- Verify webhook signatures using `Stripe-Signature` header and the **raw request body**.
- Do not log secrets; treat Stripe customer/subscription ids as sensitive operational identifiers.

## Test Strategy
- Backend tests cover:
  - webhook idempotency (same event id twice → one DB event record)
  - subscription update → athlete tier flips to `pro`
  - checkout/portal endpoints return URLs (Stripe SDK mocked)

## Related
- Phase plan: `docs/PHASED_WORK_PLAN.md`
- Admin RBAC seam: `docs/adr/ADR-053-admin-rbac-audit-and-impersonation-hardening.md`
- Viral-safe ops: `docs/adr/ADR-054-viral-safe-ingestion-resilience-and-emergency-brake.md`

