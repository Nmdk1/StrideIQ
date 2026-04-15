# Builder Note — Phase 2: Garmin Connect Integration

**Date:** February 19, 2026
**Assignment:** Scope and build Garmin Connect integration
**Builder model:** Sonnet 4.6
**Supervisor:** Opus (reviews every output)
**Founder sign-off:** Required before build starts

---

## Before your first tool call

Read these documents in this exact order:

1. `docs/FOUNDER_OPERATING_CONTRACT.md`
2. `docs/PRODUCT_MANIFESTO.md`
3. `docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md`
4. `docs/GARMIN_CONNECT_DEVELOPER_COMPLIANCE.md` — Garmin contractual obligations
5. This document

---

## Context

StrideIQ has been accepted into the Garmin Connect Developer Program (February 2026). We have evaluation environment access to the developer portal at `https://developerportal.garmin.com/`. Credentials are under `michael@strideiq.run`.

**Blocker 0 (AI consent infrastructure) is cleared.** Phase 1 shipped to production. Privacy policy updated, consent flow live, all 8 LLM call sites gated, audit trail operational.

**There is existing Garmin code in the codebase** (`services/garmin_service.py`, `services/provider_import/garmin_di_connect.py`) that uses the unofficial `python-garminconnect` library with username/password auth. This is NOT the official API. The official Garmin Connect developer program uses OAuth 2.0 and has four distinct APIs. The existing code may be useful as reference for data models but the auth and API layer must be replaced.

**The existing Strava integration** is the reference pattern for architecture:
- OAuth: `routers/strava.py` (auth-url, callback endpoints)
- Token storage: encrypted fields on `Athlete` model
- Data sync: Celery tasks in `tasks/strava_tasks.py`
- Activity mapping: direct field mapping with `provider="strava"`, `source="strava"`
- Deduplication: unique constraint on `(provider, external_activity_id)`
- State tracking: `AthleteIngestionState` model
- Rate limiting: Redis-based budget

---

## Phase 2A: API Discovery (DO THIS FIRST — NO CODE)

The founder has confirmed we don't yet know exactly what data the four Garmin APIs provide. Before writing any acceptance criteria or code, you must research and document what's available.

### Step 1: Read the Garmin developer documentation

Go to `https://developerportal.garmin.com/` and read the documentation for all available APIs. Garmin's developer program typically provides these API categories (names may vary — use whatever they actually call them):

- Activity/Fitness API (workouts, activities)
- Health API (daily summaries, steps, calories)
- Sleep API (sleep stages, duration, quality)
- Wellness/Body Battery/Stress API (stress scores, Body Battery, HRV)

For each API, document:
- Endpoint URLs and methods
- What data fields are returned (exact field names and types)
- Push (webhook/ping) vs pull (polling) model
- Rate limits
- OAuth scopes required
- Any data that overlaps with what Strava already provides

### Step 2: Produce the discovery document

Create `docs/GARMIN_API_DISCOVERY.md` with:

1. **API inventory** — every API endpoint available to us, grouped by category
2. **Data field mapping** — for each endpoint, what fields map to existing StrideIQ models and what's new
3. **Architecture decisions needed** — push vs pull, sync frequency, overlap handling with Strava
4. **Priority recommendation** — which APIs to integrate first based on product value

**DO NOT write acceptance criteria yet.** The discovery document is the input to the AC document.

### Step 3: Submit for supervisor review

The supervisor (Opus) will review the discovery document against:
- The compliance doc (`GARMIN_CONNECT_DEVELOPER_COMPLIANCE.md`)
- The existing Strava integration patterns
- Product priorities from `TRAINING_PLAN_REBUILD_PLAN.md`

After supervisor review, the founder approves, and then we write the AC document.

---

## Phase 2B: Integration Spec (AFTER discovery is approved)

Once the discovery document is approved, produce `docs/PHASE2_GARMIN_INTEGRATION_AC.md` with:

1. Deliverables in build order
2. Acceptance criteria for each deliverable
3. Test design (test-first, same pattern as Phase 1)
4. Rollout plan

Expected deliverables (subject to discovery findings):
- OAuth 2.0 flow (Garmin-specific)
- Activity sync adapter
- Health/wellness data sync (sleep, HRV, stress, Body Battery)
- Attribution components (Garmin branding on data display)
- Data source tracking and dedup across Strava + Garmin

**All Garmin code lives on `feature/garmin-oauth` branch.** Not `main`.

---

## Rules

1. **Discovery before code.** Do not write implementation code until the AC document is founder-approved.
2. **Show evidence, not claims.** Paste API response examples from docs.
3. **Do not access the developer portal yourself.** You cannot log in. Research the documentation by reading the Garmin developer docs that are publicly available, and note where portal-only docs need founder verification.
4. **Follow the existing Strava pattern** for architecture unless there's a specific reason to deviate (document the reason).
5. **Compliance doc is law.** Every deliverable must map to a compliance checklist item.
6. **No write-back to Garmin** without explicit founder approval.
7. **Feature branch only.** `git checkout -b feature/garmin-oauth` before any code.

---

## Start with Phase 2A Step 1. Go.
