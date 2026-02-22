# Session Handoff — Phase 2 Garmin Build (Updated)

**Date:** February 22, 2026 (updated)
**Status:** D0–D4 implementation-complete. D4 completion gate (live webhook capture) pending founder portal action. Builder resumes at D5.
**Branch:** `feature/garmin-oauth`

---

## Builder Assignment

**Resume build at D5.** D0–D4 are complete (6 commits on branch). D4 is implementation-complete but completion-gated on D4.3 (live webhook capture — founder action required). D5 (activity sync) is unblocked and can proceed in parallel while D4.3 is pending.

---

## Read order before first tool call

1. `docs/FOUNDER_OPERATING_CONTRACT.md`
2. `docs/PRODUCT_MANIFESTO.md`
3. `docs/GARMIN_CONNECT_DEVELOPER_COMPLIANCE.md`
4. `docs/PHASE2_GARMIN_INTEGRATION_AC.md` ← **the spec (REVISED Feb 22, 2026 — read the "What Changed" section first)**
5. `docs/garmin-portal/README.md` ← index of official Garmin portal documentation
6. `docs/garmin-portal/OAUTH_CONFIG.md` ← OAuth 2.0 PKCE flow details (critical for D2)
7. `docs/garmin-portal/PARTNER_API.md` ← permissions, token exchange, deregistration
8. `docs/garmin-portal/HEALTH_API.md` ← all endpoint schemas and field mappings (critical for D3)
9. `docs/garmin-portal/ENDPOINT_CONFIGURATION.md` ← webhook URL setup and delivery modes (critical for D4)
10. `docs/ADVISOR_NOTE_2026-02-22_PORTAL_VERIFICATION.md` ← advisor review with decisions
11. This document

---

## What happened since last handoff

1. **Founder captured official Garmin developer portal documentation** — 6 files in `docs/garmin-portal/`
2. **All 7 `[PORTAL VERIFY]` items resolved** — no more stop-gates
3. **AC revised with 8 must-fix items from advisor review** — see "What Changed from Prior AC" section at top of AC
4. **Advisor GO cleared** on revised AC

---

## Gate status at handoff

| Gate | Status |
|---|---|
| 1. Discovery | COMPLETE |
| 2. Advisor review of discovery | COMPLETE — GO |
| 3. Founder approval of discovery | APPROVED |
| 4. AC specification | COMPLETE |
| 5. Advisor review of AC | COMPLETE — GO (Gate 5 + portal verification revision) |
| 6. Founder approval of AC | APPROVED |
| 0D. Portal verification | **ALL VERIFIED** (D4 completion-gate unknowns pending live capture) |
| 7. Implementation | **D0–D4 COMPLETE (D4 impl done, D4.3 pending) — resume at D5** |

---

## Completed deliverables

| Deliverable | Commit | Tests |
|---|---|---|
| D0 — Dedup service refactor | `96d21bc` | 26 tests (10 contract + 16 runtime) |
| D1 — Data model + migrations | `df4213d` | 24 tests (schema + constraints + contract) |
| D2 — OAuth 2.0 PKCE flow + disconnect + GDPR fix | (D2 commit) | 35 tests (PKCE, token refresh, router contract, GDPR contract) |
| D3 — Adapter layer + garmin_004 migration | `96950ef` | 46 tests (all adapters, source contracts, dedup contract, schema) |
| D3 post-review fixes | `9e7ceb8` | 6 must-fix items from founder + Codex advisor review |
| D4 — Webhook endpoints, security, task stubs | `27d63d8` | 22 tests (auth unit, rate limiter, endpoint integration, source contracts) |

**Total on branch:** 149 passed, 6 skipped (runtime DB — need live DB), 0 failed.

---

## Build order — remaining

```
D4 → D5 → D6 → D7 → D8
```

| Deliverable | What it is | Key constraint | Blocker status |
|---|---|---|---|
| ~~D2~~ | OAuth 2.0 PKCE flow | DONE | — |
| ~~D3~~ | Adapter layer | DONE | — |
| ~~D4~~ | Webhook endpoints (per-type routes) | Implementation complete. Completion-gated on D4.3 (live capture). Founder registers URLs in portal. | **IMPLEMENTATION DONE, D4.3 pending** |
| **D5** | Activity sync | Garmin primary, Strava secondary. 7 provider precedence tests. | UNBLOCKED (after D3+D4) |
| **D6** | Health/wellness sync | `GarminDay` upsert. Women's Health is Tier 2 (separate model, not D6). | UNBLOCKED (after D4) |
| **D7** | Initial backfill | 90 days. Async: backfill API returns 202, data pushed to webhook. **D4 must be deployed first.** | UNBLOCKED (after D4) |
| **D8** | Attribution | `GarminBadge` component. | UNBLOCKED (parallel with D7) |

---

## Critical changes from prior AC version (builder must read)

These are the most important differences from what you read before D0/D1:

### 1. OAuth is PKCE, not contingent
- OAuth 2.0 PKCE (S256) confirmed. No OAuth 1.0a contingency.
- Auth URL: `https://connect.garmin.com/oauth2Confirm`
- Must generate `code_verifier` (43-128 chars), compute `code_challenge = base64url(sha256(code_verifier))`, store verifier keyed by `state`
- Token refresh requires `refresh_token` + `GARMIN_CLIENT_SECRET`
- Expired refresh token = full re-auth required

### 2. Webhook is per-type routes, not multiplexed
- Each data type gets its own endpoint: `/v1/garmin/webhook/activities`, `/v1/garmin/webhook/sleeps`, etc.
- See D4.0 route table in AC for full list (9 Tier 1 + 4 Tier 2)
- All routes share common `verify_garmin_webhook` auth middleware

### 3. No HMAC — layered security instead
- No `GARMIN_WEBHOOK_SECRET`. That env var is gone.
- Auth: `garmin-client-id` header check against `GARMIN_CLIENT_ID`
- Plus: strict schema validation, unknown userId skip-and-log, rate limiting, IP allowlist if obtainable

### 4. Running dynamics NOT in JSON API
- Stride length, GCT, vertical oscillation, vertical ratio, GAP — FIT-file-only
- Training Effect, self-eval, body battery impact — not in official schema, not mapped in Tier 1 adapter
- `powerInWatts` IS in stream samples
- Columns stay in migration (nullable) but adapter does NOT populate them

### 5. Field names are camelCase, not PascalCase
- Official schema uses `averageHeartRateInBeatsPerMinute`, `distanceInMeters`, `startTimeInSeconds`
- Not `AverageHeartRateInBeatsPerMinute` etc. as discovery doc assumed
- D3 adapter mapping table in AC is corrected to official names

### 6. Backfill is async
- `GET /rest/backfill/activities` returns `202 Accepted`
- Data arrives via webhook endpoints, not in the API response
- D4 webhook must be deployed and registered in portal before backfill works

### 7. `garmin_tasks.py` must be deleted
- Not just "audit and replace" — delete. It references deprecated auth fields.
- New tasks defined in D5/D6/D7.

---

## Hard rules (unchanged)

1. **All Garmin code on `feature/garmin-oauth` only.** Never commit to `main`.
2. **Tests-first.** Write failing tests before implementation.
3. **`garmin_service.py` is retired.** Delete if not already deleted.
4. **`garmin_tasks.py` must be retired.** Delete and replace with new task definitions.
5. **Training API is permanently out of scope.** Do not build it.
6. **Women's Health (MCT) is Tier 2.** Do not add to `GarminDay`. Separate model later.
7. **Undocumented fields are deferred.** Do not map TE/self-eval/body-battery in Tier 1 adapter.
8. **Merge to `main` is blocked** until Gate 0A (30-day notice) clears.

---

## Key architectural decisions (do not re-open)

- `GarminDay` is the single wellness model — no separate `GarminSleep`, `GarminHRV`
- Garmin is primary source; Strava is secondary — Garmin wins dedup conflicts
- Training API permanently out of scope (compliance §4.6 IP exposure)
- Per-type webhook routes (portal is per-type, we match it)
- Push delivery mode for all health/wellness endpoints; ping-only for Activity Files, Deregistrations, Permissions Change
- 90-day backfill depth (async via webhook)
- Dedup operates post-adapter on internal field names only
- `consent_audit_log` reuses existing schema — no new migration
- Women's Health deferred to Tier 2 with separate `GarminCycle` model
- Undocumented fields deferred until real payload proof

---

## D4 completion gate (builder: read carefully)

D4 implementation can START immediately. But D4 cannot be marked DONE until:

1. Deploy webhook endpoints to eval/staging
2. Register URLs in Garmin portal Endpoint Configuration
3. Use Data Generator (or real device sync) to trigger at least one webhook per Tier 1 data type
4. Capture and document: actual HTTP headers, payload envelope shape, confirm `garmin-client-id` header presence
5. Save samples to `docs/garmin-portal/WEBHOOK_PAYLOAD_SAMPLES.md`
6. If live payload contradicts any assumption → update handler before marking D4 complete

**The founder will help with portal URL registration when D4 endpoints are deployed.**

---

## Founder action items (during build)

1. **30-day display format notice:** Send to `connect-support@developer.garmin.com` when builder provides mockups. Clock starts on send.
2. **Portal URL registration:** When D4 endpoints are deployed, founder registers them in Endpoint Configuration page.
3. **Privacy Policy link:** Must point to real policy before any user goes through OAuth consent flow.

---

## Production state at handoff

- Production is healthy and on `main`
- Phase 1 (AI consent) is live and gated
- All backend and frontend tests green
- No open regressions
- `feature/garmin-oauth` branch has 6 commits (D0–D4), 149 passing tests

---

## What the next session looks like

Builder resumes at D5 (activity sync). D4 endpoints are deployed-ready — founder registers webhook URLs in the Garmin developer portal Endpoint Configuration when a staging/eval environment is available, then triggers test payloads for D4.3 live capture. D5, D6, D7, D8 can all proceed in parallel with D4.3 pending. D4.3 must be captured before merge to main.

---

## Production flag rollout (post-merge) — IDEMPOTENT SQL

After merging `feature/garmin-oauth` to `main` and deploying, seed the
`garmin_connect_enabled` feature flag with this **upsert** (safe to re-run):

```sql
INSERT INTO feature_flag (
  id, key, name, description, enabled,
  requires_subscription, requires_tier, requires_payment,
  rollout_percentage, allowed_athlete_ids, created_at, updated_at
)
VALUES (
  gen_random_uuid(),
  'garmin_connect_enabled',
  'Garmin Connect',
  'Gate Garmin OAuth to founder + father only during notice window',
  true,
  false, NULL, NULL,
  0,
  jsonb_build_array('<founder_uuid>', '<father_uuid>'),
  now(), now()
)
ON CONFLICT (key) DO UPDATE SET
  enabled             = EXCLUDED.enabled,
  rollout_percentage  = EXCLUDED.rollout_percentage,
  allowed_athlete_ids = EXCLUDED.allowed_athlete_ids,
  updated_at          = now();
```

Replace `<founder_uuid>` and `<father_uuid>` with the actual UUIDs from the
`athlete` table (look up by `email`):

```sql
-- Look up UUIDs
SELECT id, email
FROM athlete
WHERE email IN ('mbshaf@gmail.com', 'wlsrangertug@gmail.com');
```

**Verify immediately after upsert:**

```sql
SELECT key, enabled, rollout_percentage, allowed_athlete_ids
FROM feature_flag
WHERE key = 'garmin_connect_enabled';
```

Expected result:

| key | enabled | rollout_percentage | allowed_athlete_ids |
|---|---|---|---|
| garmin_connect_enabled | true | 0 | ["<founder_uuid>", "<father_uuid>"] |

**Flag semantics enforced:**
- `enabled = true` — flag exists and is active
- `rollout_percentage = 0` — zero-percent population rollout (no one passes by hash)
- `allowed_athlete_ids = [...]` — allowlist is checked first; listed athletes pass regardless of rollout

Result: only the two listed athletes can reach `GET /v1/garmin/auth-url` or complete
the callback. Everyone else receives `403`. UI hides the Garmin connect option for
non-listed athletes (driven by `garmin_connect_available: false` in `/v1/garmin/status`).
