# Builder Note — Garmin Production Feature Flag (Founder + Father Only)

**Date:** February 22, 2026  
**Assignment:** Ship Garmin rollout gate for production with strict 2-athlete allowlist  
**Branch:** `feature/garmin-oauth`  
**Founder sign-off:** Required before merge

---

## Before your first tool call

Read these documents in this exact order:

1. `docs/FOUNDER_OPERATING_CONTRACT.md`
2. `docs/PRODUCT_MANIFESTO.md`
3. `docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md`
4. `docs/PHASE2_GARMIN_INTEGRATION_AC.md`
5. `docs/TRAINING_PLAN_REBUILD_PLAN.md`
6. This document

---

## Objective

Deploy Garmin safely in production without staging by gating connect flow to exactly two athletes during Garmin's 30-day notice window:

- Founder: `mbshaf@gmail.com`
- Father: `wlsrangertug@gmail.com`

Nobody else should be able to start Garmin OAuth or see Garmin connect UI.

---

## Critical flag semantics (must follow)

Use existing feature-flag plumbing via `is_feature_enabled("garmin_connect_enabled", athlete_id, db)`.

Because current flag logic checks allowlist first, then rollout:

- `allowed_athlete_ids` alone is **not** restrictive if `rollout_percentage=100`.
- To enforce "only these two users", configure:
  - `enabled = true`
  - `rollout_percentage = 0`
  - `allowed_athlete_ids = [founder_uuid, father_uuid]`

This is non-negotiable for correct access control.

---

## Build scope (strict)

### 1) Backend gating

File: `apps/api/routers/garmin.py`

Required:
1. Gate `GET /v1/garmin/auth-url`
   - If flag disabled for caller: return `403`.
   - Return stable, non-sensitive error payload.

2. Gate `GET /v1/garmin/callback` (defense in depth)
   - After OAuth state validation and athlete resolution, check same flag.
   - If disabled: do not exchange/store tokens, do not enqueue backfill.
   - Return safe redirect with error status (do not hard-fail server).

Do not change:
- D4 webhook routes
- D7 backfill behavior for enabled athletes

### 2) Frontend gating

Files:
- `apps/web/components/integrations/GarminConnection.tsx`
- `apps/web/app/settings/page.tsx`
- `apps/web/app/onboarding/page.tsx`

Required:
1. Settings: hide Garmin connect CTA when flag is off.
2. Onboarding connect stage: hide Garmin option when flag is off.
3. If athlete is already connected, still show connected/disconnect state even when new connects are disabled.
4. Strava UX must remain unchanged.

Implementation note:
- Drive UI from backend truth (no env-only client toggle).

---

## Acceptance Criteria

1. **Access control**
   - Founder + father can access `/v1/garmin/auth-url` successfully.
   - Any other athlete gets `403` from `/v1/garmin/auth-url`.

2. **Callback protection**
   - Non-allowlisted callback does not persist tokens and does not enqueue backfill.
   - Allowlisted callback flow remains unchanged.

3. **UI exposure**
   - Non-allowlisted athletes do not see Garmin connect option in settings/onboarding.
   - Allowlisted athletes see Garmin connect UX.
   - Connected state still visible for already connected athletes.

4. **Regression safety**
   - Strava connect/disconnect/onboarding flows unchanged.
   - Existing Garmin webhook auth behavior unchanged.

---

## Required tests

### Backend
- Add/extend router tests for:
  - `/v1/garmin/auth-url`: allowlisted `200`, non-allowlisted `403`
  - `/v1/garmin/callback`: blocked path has no token write / no backfill enqueue
  - `/v1/garmin/callback`: allowlisted path behaves as before

### Frontend
- Settings test: Garmin connect hidden when flag off
- Onboarding test: Garmin option hidden when flag off
- Connected-state rendering test remains valid

### Regression
- Run affected Strava test slices to prove no cross-regression.

---

## Production rollout steps

1. Merge `feature/garmin-oauth` to `main`
2. Deploy production
3. Configure flag row `garmin_connect_enabled`:
   - `enabled=true`
   - `rollout_percentage=0`
   - `allowed_athlete_ids=[founder_uuid,father_uuid]`
4. Verify founder and father can connect Garmin
5. Verify non-allowlisted account cannot connect (403 + hidden UI)
6. Complete D4.3 live webhook capture and screenshots
7. Send Garmin 30-day notice
8. After window, widen rollout (or remove gate)

---

## Evidence required in handoff (no exceptions)

Builder must paste:

1. Files changed
2. Exact test commands run
3. Raw test output (pass/fail counts)
4. Proof founder auth-url success
5. Proof father auth-url success
6. Proof non-allowlisted athlete gets `403`
7. UI proof:
   - Founder/father see Garmin connect
   - Non-allowlisted user does not
8. Confirmation Strava flows still pass

No claims without concrete output/log evidence.
