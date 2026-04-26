# Advisor Note — Portal Verification Complete

**Date:** February 22, 2026
**Author:** Builder/Advisor session
**Advisor review:** February 22, 2026 — NO-GO on initial draft, 8 must-fix items issued. AC revised. **GO on revision.**
**Status:** Gate 0D resolved except implementation-time D4 unknowns (completion-gated). AC approved. Builder unblocked for D2-D8.
**Branch:** `feature/garmin-oauth`

---

## Context

The founder walked through the entire Garmin Connect Developer Portal on Feb 22, 2026
and captured official documentation. All artifacts are preserved in `docs/garmin-portal/`.
The builder completed D0 and D1 previously and is blocked on D2 pending these results.

**Read these files first (in order):**
1. `docs/FOUNDER_OPERATING_CONTRACT.md`
2. `docs/PHASE2_GARMIN_INTEGRATION_AC.md` (current spec — needs updates below)
3. `docs/garmin-portal/README.md` (index of captured portal docs)
4. `docs/garmin-portal/OAUTH_CONFIG.md` (OAuth 2.0 PKCE flow details)
5. `docs/garmin-portal/PARTNER_API.md` (token exchange, permissions, deregistration)
6. `docs/garmin-portal/HEALTH_API.md` (all endpoint schemas + field mappings)
7. `docs/garmin-portal/ENDPOINT_CONFIGURATION.md` (webhook URL setup, delivery modes)
8. `docs/garmin-portal/API_CONFIGURATION.md` (enabled APIs and permission status)
9. This document

---

## Gate 0D Resolution — All 7 Items VERIFIED

| # | Item | Result | Evidence |
|---|------|--------|----------|
| 1 | OAuth flow version | **OAuth 2.0 PKCE (S256)** | `OAUTH_CONFIG.md` — portal OAuth2 Tools wizard, 4-step flow |
| 2 | OAuth scope names | **ACTIVITY_EXPORT, HEALTH_EXPORT, MCT_EXPORT** | `PARTNER_API.md` — `GET /rest/user/permissions` response; consent screen shows Activities, Women's Health, Daily Health Stats, Historical Data |
| 3 | Token refresh behavior | Refresh requires **refresh_token + client_secret**. Expired refresh = full re-auth required. | `OAUTH_CONFIG.md` — Refresh Token portal page. `PARTNER_API.md` — `OAuthTokenExchangeResp` has `refresh_token_expires_in` |
| 4 | Webhook auth mechanism | **No HMAC/signing secret.** No signature configuration exists in portal. | `ENDPOINT_CONFIGURATION.md` — no signing secret field anywhere on page |
| 5 | Webhook payload format | **Per-type URLs** — each data type has its own URL field. NOT a single multiplexed endpoint. | `ENDPOINT_CONFIGURATION.md` — 22 separate URL fields, each with own delivery mode |
| 6 | Running dynamics in JSON | **NOT present.** Official `Sample` schema has no stride length, GCT, vertical oscillation, vertical ratio. Only `powerInWatts` in stream data. | `HEALTH_API.md` — official `ClientActivityDetail` and `Sample` schemas |
| 7 | Deregistration endpoint | **`DELETE /rest/user/registration`** returns `204 No Content` | `PARTNER_API.md` — confirmed endpoint and response |

---

## AC Corrections Required (advisor must validate these before AC update)

### CORRECTION 1: OAuth — PKCE confirmed, remove 1.0a contingency

**Current AC says:** "If Garmin uses OAuth 1.0a instead... update routers/garmin.py accordingly" (D2.1, G5-M7)

**Portal confirms:** OAuth 2.0 with PKCE. Authorization URL is `https://connect.garmin.com/oauth2Confirm`.

**Required change:** Remove OAuth 1.0a contingency. Add PKCE implementation details:
- `code_verifier`: 43-128 chars, A-Z a-z 0-9 `-.~_`
- `code_challenge`: `base64url(sha256(code_verifier))`
- `code_challenge_method`: `S256`
- `state` parameter: recommended, used to look up `code_verifier` and bind to StrideIQ user session

**Advisor question:** Is this a straightforward AC update or does it need re-review?

---

### CORRECTION 2: Webhook security — no HMAC exists

**Current AC says:** "If Garmin provides HMAC-SHA256 signature: verify using shared secret... If neither: IP allowlisting" (D4.1)

**Portal confirms:** No HMAC. No signing secret. No signature configuration anywhere.

**Required change:** Remove HMAC as primary option. Replace D4.1 with:
1. **Primary:** Verify `garmin-client-id` header matches `GARMIN_CLIENT_ID` env var
2. **Secondary:** IP allowlisting (if Garmin publishes source IP ranges — research during D4)
3. **Tertiary:** Strict schema validation on all payloads
4. **Policy:** Unknown `userId` values: return `200` (avoid retry storms), log and skip processing
5. **Policy:** Auth failure (wrong/missing header): return `401`, no processing

**Replace `GARMIN_WEBHOOK_SECRET` references** throughout AC and test plan with `GARMIN_CLIENT_ID` header check.

**Advisor question:** The `garmin-client-id` header is trivially spoofable. Is this acceptable with compensating controls (IP allowlist + schema validation + userId verification against known athletes), or does the advisor want to add additional hardening requirements?

---

### CORRECTION 3: Webhook topology — per-type URLs, not multiplexed

**Current AC says:** "Single multiplexed endpoint POST /v1/garmin/webhook... Garmin's push architecture sends all subscribed event types to a single registered callback URL per application" (D4, G5-H2)

**Portal confirms:** This is WRONG. Each data type has its own URL field. Garmin does NOT require a single URL.

**Two options:**

**Option A — Single endpoint (minimal code change to AC):**
Point all 22 portal URL fields to `https://strideiq.run/v1/garmin/webhook`. Discriminate incoming payloads by schema shape (each data type has distinct fields). AC rationale section updated to reflect this is our choice, not Garmin's constraint.

**Option B — Per-type routes:**
Create separate endpoints: `/v1/garmin/webhook/activities`, `/v1/garmin/webhook/sleeps`, `/v1/garmin/webhook/dailies`, etc. Cleaner routing — the URL itself is the discriminator. ~8-10 routes for Tier 1 data types.

**Founder deferred this to advisor.** Please evaluate and recommend with rationale.

**Factors to consider:**
- Option A: simpler code, single auth check, but requires robust payload discrimination
- Option B: explicit routing, no ambiguity, but more boilerplate and 22 portal URL registrations
- Hybrid: single endpoint for push types, separate for ping-only types (Deregistrations, Permissions Change)

---

### CORRECTION 4: Running dynamics — NOT in JSON API

**Current AC says:** Fields like `AverageStrideLength`, `AverageGroundContactTime`, etc. are mapped in D3.1 adapter table and new columns in D1.2 migration (D1.2 lines 194-198, 201)

**Portal confirms:** Official `ClientActivity` summary and `Sample` stream schemas do NOT contain:
- Stride length
- Ground contact time / balance
- Vertical oscillation / ratio
- Grade adjusted pace (GAP)
- Training Effect (aerobic/anaerobic)
- Self-evaluation (feel/perceived effort)
- Body Battery impact (at activity level)
- Moving time

**Present in official schema:**
- `averageRunCadenceInStepsPerMinute` / `maxRunCadenceInStepsPerMinute`
- `averageSpeedInMetersPerSecond` / `maxSpeedInMetersPerSecond`
- `averagePaceInMinutesPerKilometer` / `maxPaceInMinutesPerKilometer`
- `averageHeartRateInBeatsPerMinute` / `maxHeartRateInBeatsPerMinute`
- `distanceInMeters`
- `totalElevationGainInMeters` / `totalElevationLossInMeters`
- `activeKilocalories`
- `steps`
- `deviceName`
- `manual` / `isWebUpload`
- `activityId` (int64)
- Stream samples: `powerInWatts`, `heartRate`, `speedMetersPerSecond`, `stepsPerMinute`, `elevationInMeters`, `latitudeInDegree`, `longitudeInDegree`, `totalDistanceInMeters`, `airTemperatureCelcius`

**Required changes:**
- D1.2: Keep all columns in migration (nullable, no harm). Annotate running dynamics columns as "FIT-file-only — deferred to Tier 2 FIT parsing"
- D3.1: Remove absent fields from adapter mapping table. Add present fields that were missing (`averagePaceInMinutesPerKilometer`, `activityId`, `totalElevationLossInMeters`, `steps`, `deviceName`, `isWebUpload`)
- D5.3: Mark as **RESOLVED** — no eval checkpoint needed. Running dynamics confirmed absent from JSON API.

**Advisor question:** Should Training Effect, self-evaluation, and body battery impact fields also be annotated as "not in official schema — source unknown" in the migration? They appear in the discovery doc but not in the portal's official schema. They may exist in actual payloads but aren't documented.

---

### CORRECTION 5: Women's Health is in scope

**Current AC says:** "Women's Health API: Not applicable" (Out of scope, line 82)

**Portal confirms:** Women's Health (`MCT_EXPORT`) is enabled, approved, and appears on the user consent screen as a default-ON toggle. The founder explicitly stated this is wanted for female athlete training intelligence.

**Required change:** Move from "Out of scope (permanent)" to either:
- Add to D6 scope (process MCT data into `GarminDay` or new model)
- Or add as Tier 2 deferred (capture via webhook but defer processing)

**Advisor question:** Does MCT data belong in `GarminDay` (add columns) or does it warrant its own model? The data is cycle-level (multi-day spans), not daily. See `HEALTH_API.md` for the `ClientSummarizedMenstrualCycle` schema.

---

### CORRECTION 6: Backfill is async — D4 before D7

**Current AC says:** D7 backfill triggers after OAuth connect.

**Portal confirms:** Backfill endpoints return `202 Accepted`. Data is delivered asynchronously via webhook push. This means D4 (webhook endpoint) MUST be deployed and configured in the portal before D7 backfill can receive any data.

**Required change:** Add explicit dependency note to D7: "Prerequisite: D4 webhook endpoint must be deployed and registered in portal before backfill can be triggered."

**Build order remains `D0 → D1 → D2 → D3 → D4 → D5 → D6 → D7 → D8`** — this already has D4 before D7, so no reorder needed. Just make the dependency explicit.

---

### CORRECTION 7: OAuth token field names confirmed

**Current AC says:** "[PORTAL VERIFY] Confirm exact field names returned in OAuth token response before migration is written." (D1.1, line 160)

**Portal confirms (from `OAuthTokenExchangeResp` schema):**
- `access_token` (string)
- `token_type` (string)
- `refresh_token` (string)
- `expires_in` (int32 — seconds)
- `scope` (string)
- `refresh_token_expires_in` (int32 — seconds)

D1.1 migration fields (`garmin_oauth_access_token`, `garmin_oauth_refresh_token`, `garmin_oauth_token_expires_at`, `garmin_user_id`) are correct. Mark VERIFIED.

---

### CORRECTION 8: Endpoint delivery modes

**New information for AC:** Garmin supports three delivery modes per endpoint:
- `on hold` — paused
- `enabled` — ping mode (notification only, pull data)
- `push` — full data delivery

Three endpoint types are **ping-only** (no push):
- Activity Files (FIT/TCX/GPX — must pull via `GET /rest/activityFile`)
- Deregistrations
- User Permissions Change

All others support push. Add this to D4 documentation.

---

## Advisor Deliverables

After reviewing this note and the portal docs, the advisor should:

1. **Validate or challenge** each correction above
2. **Decide** webhook topology (Option A single / Option B per-type / Hybrid)
3. **Decide** Women's Health scope (D6 expansion / Tier 2 / separate model)
4. **Decide** whether undocumented fields (Training Effect, self-eval, body battery impact) should be kept in adapter with "may not be present" annotation or removed entirely
5. **Produce** a must-fix checklist (same format as Gates 2 and 5)
6. **Clear or block** the AC update

Once the advisor clears, the AC gets updated, and then a builder handoff note is written.

---

## Open Items NOT Resolved by Portal

| Item | Status | Path to resolution |
|------|--------|-------------------|
| Refresh token rotation (does token change on each refresh?) | Unknown — requires live token | Code defensively: always store returned refresh token |
| Exact webhook HTTP headers Garmin sends | **Blocks D4 completion** — requires configured endpoint | First live webhook capture validation step before D4 is marked done |
| Garmin source IP ranges for allowlisting | Unknown — not in portal | Research during D4, or contact Garmin support |
| Webhook payload wrapping (are items in an array? top-level object?) | **Blocks D4 completion** — schemas show response format, not push format | First live Data Generator payload must confirm parser assumptions |

Items marked "Blocks D4 completion" are not build-start blockers but are completion gates — D4 cannot be marked DONE until these are captured and documented.

---

## Advisor Review — February 22, 2026

### Findings by severity

#### HIGH

1. **"All 7 Gate 0D items resolved" is overstated.**
   - Open items include unknowns directly relevant to D4: exact webhook headers and payload wrapping shape.
   - These affect auth checks and parser contract.
   - **Resolution:** Language corrected to "resolved except implementation-time D4 unknowns."

2. **Webhook auth remains weak unless AC adds compensating controls as hard requirements.**
   - No HMAC/signature means `garmin-client-id` alone is not strong auth.
   - AC must require layered controls (header check + strict schema + user validation + rate controls; IP allowlist if obtainable).

3. **Current codebase still contains legacy Garmin task paths using retired auth fields/services.**
   - `apps/api/tasks/garmin_tasks.py` still references `garmin_username`, `garmin_password_encrypted`, and `services.garmin_service`.
   - AC/build handoff must explicitly retire/replace this path before production Garmin sync.

#### MEDIUM

4. **Undocumented fields conflict (TE/self-eval/body battery impact) needs explicit policy in AC.**
   - Keep nullable columns if desired, but mark as "not in official schema / best-effort only" and do not assume presence.

5. **Women's Health scope decision is missing and blocks clean modeling choices.**
   - Cycle-level data does not fit neatly into daily grain.

### Decisions on the 4 advisor decision points

1. **Webhook topology:** **Option B (per-type routes)**
   Rationale: portal is per-type; per-type routes reduce ambiguity, simplify handlers, and avoid brittle discriminator parsing.

2. **Women's Health scope:** **Tier 2, separate model**
   Rationale: cycle objects are multi-day and semantically distinct from `GarminDay`.
   Recommendation: ingest later into a dedicated `GarminCycle` (or similar) model.

3. **Undocumented fields handling (TE/self-eval/body battery impact):**
   **Do not map in Tier 1 adapter.**
   Keep columns nullable if already planned, but mark "deferred / not guaranteed by official schema." Populate only after real payload proof.

4. **Webhook security adequacy:**
   **Header-only is insufficient by itself.**
   Acceptable only with compensating controls made mandatory in AC/tests.

### Go / No-Go

**NO-GO for AC clear yet.**

One AC revision pass needed to lock the decisions and unresolved D4 unknown handling.

### Must-fix checklist (for AC update)

1. Replace "Gate 0D fully resolved" language with "resolved except implementation-time D4 unknowns."
2. Lock webhook topology to **per-type routes** and update endpoint list/tests accordingly.
3. Update D4 security contract to mandatory layered controls:
   - `garmin-client-id` header check
   - strict schema validation
   - unknown `userId` handling policy (return 200, log, skip)
   - replay/rate limiting
   - IP allowlist if Garmin ranges are obtainable
4. Add explicit "first live webhook capture" validation step before marking D4 done (headers + payload envelope recorded).
5. Move Women's Health out of Tier 1 into Tier 2 and specify separate future model (not `GarminDay`).
6. Mark TE/self-eval/body-battery-impact adapter mapping as deferred until payload proof; no hard dependency in Tier 1 tests.
7. Add explicit retirement requirement for legacy task path (`apps/api/tasks/garmin_tasks.py`) before production rollout.
8. Keep D4 blocked until first real Data Generator payload confirms parser/auth assumptions.
