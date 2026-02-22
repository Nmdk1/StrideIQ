# Phase 2: Garmin Connect Integration — Acceptance Criteria

**Date:** February 22, 2026
**Revised:** February 22, 2026 — Portal verification revision (8 must-fix items from advisor review of portal evidence)
**Status:** APPROVED — Portal verification revision GO cleared by advisor Feb 22, 2026
**Branch:** `feature/garmin-oauth` (all implementation work — never `main`)
**Input documents:**
- `docs/GARMIN_API_DISCOVERY.md` (field mappings, architecture decisions)
- `docs/GARMIN_CONNECT_DEVELOPER_COMPLIANCE.md` (contractual obligations)
- `docs/ADVISOR_HANDOFF_GARMIN_REVIEW.md` (10 must-fix items from Gate 2)
- `docs/SESSION_HANDOFF_2026-02-19_GARMIN_BUILDER_NOTE.md`
- `docs/garmin-portal/` (official Garmin developer portal documentation — captured Feb 22, 2026)
- `docs/ADVISOR_NOTE_2026-02-22_PORTAL_VERIFICATION.md` (advisor review with 8 must-fix items)

**Gate 2 must-fix items addressed:** All 10. Traceability markers: [H1]–[H4], [M1]–[M5], [L1]–[L3], [F1]–[F2].
**Gate 5 must-fix items addressed:** All 10 (5 from Advisor 1, 5 from Advisor 2). Traceability markers: [G5-H5], [G5-H6], [G5-M1]–[G5-M3], [G5-M6]–[G5-M8].
**Portal verification must-fix items addressed:** All 8. Traceability markers: [PV-1]–[PV-8].

---

## What Changed from Prior AC (Portal Verification Revision)

On February 22, 2026, the founder captured official documentation from the Garmin Connect Developer Portal (preserved in `docs/garmin-portal/`). The advisor reviewed the findings and issued 8 must-fix items. All 8 are applied in this revision:

1. **[PV-1]** Gate 0D language corrected — "resolved except implementation-time D4 unknowns" (webhook headers and payload envelope shape remain unknown until first live capture)
2. **[PV-2]** Webhook topology locked to **per-type routes** (`/v1/garmin/webhook/activities`, `/v1/garmin/webhook/sleeps`, etc.) — portal confirms per-type URL registration
3. **[PV-3]** D4 security updated to **mandatory layered controls** — `garmin-client-id` header check + strict schema validation + unknown `userId` handling + replay/rate limiting + IP allowlist if obtainable. No HMAC exists.
4. **[PV-4]** Added **first-live-webhook-capture** as D4 completion gate — D4 cannot be marked done until actual Garmin webhook headers and payload envelope are captured and documented
5. **[PV-5]** Women's Health moved from "not applicable" to **Tier 2 with separate future model** (`GarminCycle` or similar) — cycle data is multi-day, does not fit `GarminDay` grain
6. **[PV-6]** Undocumented fields (Training Effect, self-evaluation, body battery impact) **deferred from Tier 1 adapter** — columns kept nullable but not mapped until real payload proof
7. **[PV-7]** Explicit **retirement requirement for `apps/api/tasks/garmin_tasks.py`** added — must be retired or replaced before production rollout
8. **[PV-8]** D4 **completion-gated** (not start-gated) until Data Generator payload confirms parser/auth assumptions — implementation may begin, but D4 cannot be marked DONE until live capture

---

## 0. Pre-Build Gates

### Gate 0A: 30-Day Display Format Notice [M5] — MERGE GATE ONLY [G5-H1]

**Hard rollout gate. Not a blocker on implementation commits — a blocker on merging to `main`.**

Implementation and testing on `feature/garmin-oauth` may proceed before this gate clears. Merging to `main` and deploying to production are blocked until this gate is verified.

The Garmin developer agreement requires 30 days notice to `connect-support@developer.garmin.com` before any screen displaying Garmin-sourced data goes live. This notice must include mockups of:
- Any activity display screen where `provider="garmin"` data is shown
- Any wellness/health data display (sleep, HRV, stress, body battery)
- Any attribution placement for Garmin-sourced data

**Gate cleared when:** Garmin acknowledges receipt of notice AND 30 calendar days have elapsed.

Responsibility: Founder sends notice. Builder provides mockups for notice package during Phase 2 build.

### Gate 0B: AI Consent Infrastructure Verified — BEFORE FIRST COMMIT

Phase 1 shipped. `has_ai_consent()` gates all 8 LLM call sites. Before writing any Garmin sync task code, verify that `has_ai_consent()` is evaluated against the same athlete record that owns the Garmin connection. No Garmin data may reach an LLM for athletes who have not granted consent.

**Gate cleared when:** Builder confirms `has_ai_consent()` is called before any Garmin-triggered LLM processing. No new code required — confirm existing gating covers the new Garmin task path.

### Gate 0C: Feature Branch Isolation — BEFORE FIRST COMMIT

All Garmin code lives on `feature/garmin-oauth`. No commits to `main`. CI runs on `main` and `develop` — Garmin work must not trigger CI failures on those branches during development.

### Gate 0D: [PORTAL VERIFY] Dependency Resolution — VERIFIED [G5-M2, PV-1]

Founder captured official Garmin developer portal documentation on February 22, 2026. All artifacts preserved in `docs/garmin-portal/`. Gate 0D items are resolved except implementation-time D4 unknowns (webhook HTTP headers and payload envelope shape), which are addressed by the D4 completion gate below.

| [PORTAL VERIFY] item | Status | Result | Evidence |
|---|---|---|---|
| OAuth flow version (2.0 or 1.0a?) | **VERIFIED** | OAuth 2.0 PKCE (S256) | `docs/garmin-portal/OAUTH_CONFIG.md` |
| OAuth scope names | **VERIFIED** | `ACTIVITY_EXPORT`, `HEALTH_EXPORT`, `MCT_EXPORT` | `docs/garmin-portal/PARTNER_API.md`, consent screen |
| OAuth token refresh behavior | **VERIFIED** | Refresh requires refresh_token + client_secret. Expired refresh = re-auth. | `docs/garmin-portal/OAUTH_CONFIG.md` |
| Webhook auth mechanism | **VERIFIED** | No HMAC/signing secret. No signature config in portal. | `docs/garmin-portal/ENDPOINT_CONFIGURATION.md` |
| Webhook payload format and envelope | **PARTIALLY VERIFIED** | Per-type URL registration confirmed. Actual HTTP headers and payload wrapping unknown until first live webhook. | `docs/garmin-portal/ENDPOINT_CONFIGURATION.md` |
| Activity Details JSON — running dynamics | **VERIFIED** | NOT present in JSON API. Stride length, GCT, VO, VR absent from official `Sample` schema. Only `powerInWatts` in streams. | `docs/garmin-portal/HEALTH_API.md` |
| Garmin deregistration endpoint | **VERIFIED** | `DELETE /rest/user/registration` returns `204 No Content` | `docs/garmin-portal/PARTNER_API.md` |

**D4 completion gate [PV-4, PV-8]:** D4 implementation may begin, but D4 cannot be marked DONE until:
1. First live webhook is captured (via Data Generator or real device sync) documenting actual HTTP headers and payload envelope shape
2. Parser and auth assumptions are confirmed against the live payload

This does not block D2 or D3.

---

## 1. Scope

### In scope (Phase 2 — Tier 1)

| Deliverable | What it ships |
|---|---|
| D0 | Deduplication service refactor (internal field names only — prerequisite for all sync) |
| D1 | Data model changes (Athlete OAuth fields + `GarminDay` + Activity new columns) |
| D2 | OAuth 2.0 flow (connect, callback, token refresh, disconnect + data purge) |
| D3 | Adapter layer (`garmin_adapter.py` — all field translations) |
| D4 | Webhook endpoint (security validation + dispatch) |
| D5 | Activity sync (ingest, dedup, provider precedence) |
| D6 | Health/wellness sync (Sleep, HRV, Daily wellness → `GarminDay`) |
| D7 | Initial backfill (90-day on connect) |
| D8 | Attribution (`GarminBadge` component) |

### Out of scope (permanent)

- **Training API:** Out of scope. The Garmin developer agreement (Section 4.6) grants Garmin unlimited rights to any data pushed to their platform — StrideIQ-generated training plans pushed to Garmin would become Garmin's property. Treated as permanent until three conditions are met: (a) full legal review, (b) client base that supports the exploration, (c) concrete use case. No code written for it until then.
- **Courses API:** Not applicable.
- **Beat-to-beat HRV:** Requires commercial license. Evaluate cost in eval environment. Defer unless cost is reasonable and product need is confirmed.

### Deferred (Tier 2, post-stable Tier 1)

- **Women's Health / Menstrual Cycle Tracking [PV-5]:** In scope for Tier 2. MCT data (`MCT_EXPORT`) is enabled and approved in portal. Cycle data is multi-day and semantically distinct from `GarminDay` (which is daily grain). Will use a **separate future model** (`GarminCycle` or similar) — NOT added to `GarminDay`. Webhook endpoint `POST /v1/garmin/webhook/mct` is defined in D4.0 Tier 2 table. Register in portal when Tier 2 begins.
- Stress Detail + Body Battery intraday samples (stored as raw JSONB in Tier 1, computed fields in Tier 2)
- User Metrics / VO2 max trend tracking
- Epoch summaries (15-minute granularity)
- Body composition, blood pressure, pulse ox
- Running dynamics from FIT file parsing (`GET /rest/activityFile`)
- Undocumented activity fields (Training Effect, self-evaluation, body battery impact) — populate after real payload proof

---

## 2. Retired Code

Before any new code is written:

| File | Action | Reason |
|---|---|---|
| `apps/api/services/garmin_service.py` | **Delete entirely** | Uses `python-garminconnect` (unofficial library, username/password auth). Active compliance violation — violates §5.2(i) and §5.2(j) of the developer agreement. |
| `apps/api/routers/garmin.py` | **Audit and replace** | Likely references retired service. Rebuild from scratch to official OAuth pattern. |
| `apps/api/tasks/garmin_tasks.py` | **Delete and replace [PV-7]** | References `garmin_username`, `garmin_password_encrypted`, and `services.garmin_service`. Contains deprecated auth fields that could be accidentally invoked. Must be retired before production rollout — not left as dead code. New tasks are defined in D5/D6/D7. |
| `apps/api/services/provider_import/garmin_di_connect.py` | **Keep as-is** | Handles takeout/file import — separate use case, no compliance issue. Does not use unofficial library. |

The `garmin_username` and `garmin_password_encrypted` fields on the Athlete model must be removed via Alembic migration (D1 migration scope below).

---

## 3. Deliverables and Acceptance Criteria

---

### D0: Deduplication Service Refactor [G5-H6]

**Prerequisite for all sync deliverables. Must pass before D3 adapter work begins.**

`apps/api/services/activity_deduplication.py` currently uses a mix of provider-specific field names from different ingestion paths:

- `startTimeLocal`, `startTime`, `start_date_local` (Strava field names + unofficial Garmin library names)
- `distance`, `distanceInMeters` (unofficial Garmin field name)
- `averageHeartRate`, `avgHeartRate` (unofficial Garmin field names)

These must be removed. The deduplication service must operate exclusively on internal field names (`start_time`, `distance_m`, `avg_hr`). All callers must pass already-adapted dicts. This is not a new constraint — it is cleaning up existing violations before Phase 2 adds a new caller that would depend on the broken contract.

**Required changes to `activity_deduplication.py`:**
- Replace all `activity.get("startTimeLocal") or activity.get("startTime") or activity.get("start_date_local")` → `activity.get("start_time")`
- Replace all `activity.get("distance") or activity.get("distanceInMeters") or activity.get("distance_m")` → `activity.get("distance_m")`
- Replace all `activity.get("averageHeartRate") or activity.get("avgHeartRate") or activity.get("avg_hr")` → `activity.get("avg_hr")`

**Caller audit:** Find all callers of deduplication service. Confirm each passes an already-adapted dict with internal field names. Fix any callers that pass raw provider payloads directly.

**AC:**
- `activity_deduplication.py` contains no strings: `startTimeLocal`, `startTime`, `start_date_local`, `distanceInMeters`, `averageHeartRate`, `avgHeartRate` (verified by test — see contract tests)
- All existing callers pass internal field names
- Existing deduplication tests still pass after refactor (no behavior change — only field name cleanup)
- Runtime integration test: create an activity via Strava adapter → pass to deduplication → confirm match found correctly (not a grep test — actual execution)

---

### D1: Data Model Changes

#### D1.1: Athlete model — OAuth token fields

**Remove (via Alembic migration):**
- `garmin_username` (Text)
- `garmin_password_encrypted` (Text)

**Add (via Alembic migration):**
- `garmin_oauth_access_token` (Text, nullable, encrypted at rest — same pattern as Strava)
- `garmin_oauth_refresh_token` (Text, nullable, encrypted at rest)
- `garmin_oauth_token_expires_at` (DateTime with timezone, nullable)
- `garmin_user_id` (Text, nullable) — Garmin's user identifier from OAuth response

**Existing fields confirmed present (no migration needed):**
- `garmin_connected` (Boolean)
- `last_garmin_sync` (DateTime)
- `garmin_sync_enabled` (Boolean)

**VERIFIED:** Token response fields confirmed via `docs/garmin-portal/PARTNER_API.md`: `access_token`, `refresh_token`, `expires_in`, `scope`, `token_type`, `refresh_token_expires_in`.

**Alembic `EXPECTED_HEADS` strategy [G5-M1]:** Phase 2 introduced four migrations committed in sequence. The CI head-check must be updated once — after all migrations are committed — not after each one. The final pre-merge value is `EXPECTED_HEADS = {"garmin_004"}` (updated from the original `garmin_003_garmin_day` — D3 added `garmin_004_activity_official_fields` for the 7 Activity columns confirmed by portal verification). The CI head-check linear chain is: `consent_001 → garmin_001 → garmin_002 → garmin_003 → garmin_004`.

**AC:**
- Migration `garmin_001_oauth_fields.py` applies cleanly on a fresh schema
- Migration downgrades cleanly
- `garmin_username` and `garmin_password_encrypted` absent after upgrade
- OAuth token fields present and nullable after upgrade
- `EXPECTED_HEADS` updated to `{"garmin_004"}` in the final pre-merge commit (D3 added garmin_004; updated from original garmin_003_garmin_day)

#### D1.2: Activity model — new columns [H1]

**Existing columns that Garmin populates (no migration needed — fields already exist):**

| Garmin field | Activity column |
|---|---|
| `SummaryId` | `external_activity_id` |
| `StartTimeInSeconds` | `start_time` |
| `DurationInSeconds` | `duration_s` |
| `ActivityType` (mapped) | `sport` |
| `ActivityName` | `name` |
| `AverageHeartRateInBeatsPerMinute` | `avg_hr` |
| `MaxHeartRateInBeatsPerMinute` | `max_hr` |
| `AverageSpeedInMetersPerSecond` | `average_speed` |
| `DistanceInMeters` | `distance_m` |
| `TotalElevationGainInMeters` | `total_elevation_gain` |

**New columns (require Alembic migration — `garmin_002_activity_new_fields.py`):**

**Columns with official schema backing (populate in Tier 1 adapter):**

| Garmin field (official `ClientActivity` schema) | New Activity column | Type | Notes |
|---|---|---|---|
| `averageRunCadenceInStepsPerMinute` | `avg_cadence` | Integer, nullable | — |
| `maxRunCadenceInStepsPerMinute` | `max_cadence` | Integer, nullable | — |
| `averagePaceInMinutesPerKilometer` | `avg_pace_min_per_km` | Float, nullable | — |
| `maxPaceInMinutesPerKilometer` | `max_pace_min_per_km` | Float, nullable | — |
| `maxSpeedInMetersPerSecond` | `max_speed` | Float, nullable | — |
| `totalElevationLossInMeters` | `total_descent_m` | Float, nullable | — |
| `activeKilocalories` | `active_kcal` | Integer, nullable | Active only, not BMR |
| `steps` | `steps` | Integer, nullable | — |
| `deviceName` | `device_name` | Text, nullable | — |

**Columns with stream-level backing only (populate from Activity Details samples):**

| Garmin field (official `Sample` schema) | New Activity column | Type | Notes |
|---|---|---|---|
| `powerInWatts` (per-sample) | `avg_power_w` | Integer, nullable | Compute average from stream samples |
| `powerInWatts` (per-sample max) | `max_power_w` | Integer, nullable | Compute max from stream samples |

**Columns deferred — FIT-file-only, not in official JSON API [PV-6]:**

| New Activity column | Type | Notes |
|---|---|---|
| `avg_stride_length_m` | Float, nullable | **FIT-file-only — deferred to Tier 2 FIT parsing** |
| `avg_ground_contact_ms` | Float, nullable | **FIT-file-only — deferred to Tier 2 FIT parsing** |
| `avg_ground_contact_balance_pct` | Float, nullable | **FIT-file-only — deferred to Tier 2 FIT parsing** |
| `avg_vertical_oscillation_cm` | Float, nullable | **FIT-file-only — deferred to Tier 2 FIT parsing** |
| `avg_vertical_ratio_pct` | Float, nullable | **FIT-file-only — deferred to Tier 2 FIT parsing** |
| `avg_gap_min_per_mile` | Float, nullable | **FIT-file-only — deferred to Tier 2 FIT parsing** |
| `moving_time_s` | Integer, nullable | **Not in official schema — deferred until payload proof** |

**Columns deferred — not in official schema, not guaranteed by portal docs [PV-6]:**

| New Activity column | Type | Notes |
|---|---|---|
| `garmin_aerobic_te` | Float, nullable | **Not in official schema — deferred until real payload proof.** INFORMATIONAL ONLY if ever populated. |
| `garmin_anaerobic_te` | Float, nullable | **Not in official schema — deferred until real payload proof.** INFORMATIONAL ONLY if ever populated. |
| `garmin_te_label` | Text, nullable | **Not in official schema — deferred until real payload proof.** INFORMATIONAL ONLY if ever populated. |
| `garmin_feel` | Text, nullable | **Not in official schema — deferred until real payload proof.** Low-fidelity. |
| `garmin_perceived_effort` | Integer, nullable | **Not in official schema — deferred until real payload proof.** Low-fidelity. |
| `garmin_body_battery_impact` | Integer, nullable | **Not in official schema — deferred until real payload proof.** |

All deferred columns remain in the migration (nullable, no harm). They are NOT mapped in the Tier 1 adapter and NOT tested for presence. They will be populated only after a real Garmin webhook payload confirms these fields exist in the push format.

**[L2] Training Effect code-level guard:** `garmin_aerobic_te`, `garmin_anaerobic_te`, `garmin_te_label` must be annotated in the model with `# INFORMATIONAL ONLY — never use in training load calculations`. The correlation engine and load service must not read these fields. If either service touches them, the test suite must catch it.

**[L3] Self-evaluation data quality annotation:** `garmin_feel` and `garmin_perceived_effort` imported if present. These are low-fidelity — athletes frequently click through Garmin's post-activity rating without genuine engagement. Code comments and any future UI that displays these fields must reflect this caveat.

**AC:**
- `garmin_002_activity_new_fields.py` applies cleanly, downgrades cleanly
- All new columns are nullable (Strava activities unaffected — no backfill required)
- `garmin_aerobic_te`, `garmin_anaerobic_te`, `garmin_te_label` have `# INFORMATIONAL ONLY` annotation in model definition
- Running dynamics columns absent from any correlation engine query (test: grep for these column names in `services/n1_insight_generator.py`, `services/daily_intelligence.py`, `services/correlation_*`)

#### D1.3: `GarminDay` model [H3]

New table: `garmin_day`. One row per `(athlete_id, calendar_date)`.

**All field mappings in this document use `GarminDay` consistently.** Field names `GarminSleep.*` and `GarminHRV.*` from the discovery document are merged into `GarminDay` per architecture decision 3D. No separate `GarminSleep` or `GarminHRV` tables.

```
GarminDay:
  id                       UUID PK, default gen_random_uuid()
  athlete_id               UUID FK → athlete.id, NOT NULL
  calendar_date            DATE NOT NULL
  -- Daily Summary fields
  resting_hr               INTEGER nullable
  avg_stress               INTEGER nullable  -- -1 means insufficient data
  max_stress               INTEGER nullable
  stress_qualifier         TEXT nullable     -- calm/balanced/stressful/very_stressful
  steps                    INTEGER nullable
  active_time_s            INTEGER nullable
  active_kcal              INTEGER nullable
  moderate_intensity_s     INTEGER nullable
  vigorous_intensity_s     INTEGER nullable
  min_hr                   INTEGER nullable
  max_hr                   INTEGER nullable
  -- Sleep Summary fields
  sleep_total_s            INTEGER nullable
  sleep_deep_s             INTEGER nullable
  sleep_light_s            INTEGER nullable
  sleep_rem_s              INTEGER nullable
  sleep_awake_s            INTEGER nullable
  sleep_score              INTEGER nullable  -- 0-100
  sleep_score_qualifier    TEXT nullable     -- EXCELLENT/GOOD/FAIR/POOR
  sleep_validation         TEXT nullable
  -- HRV Summary fields
  hrv_overnight_avg        INTEGER nullable  -- ms
  hrv_5min_high            INTEGER nullable  -- ms
  -- User Metrics fields
  vo2max                   FLOAT nullable    -- updates infrequently
  -- Body Battery (from Stress Detail)
  body_battery_end         INTEGER nullable  -- end-of-day value
  -- Raw JSONB (Phase 2 — computed fields deferred to Tier 2)
  stress_samples           JSONB nullable    -- TimeOffsetStressLevelValues
  body_battery_samples     JSONB nullable    -- TimeOffsetBodyBatteryValues
  -- Dedup
  garmin_daily_summary_id  TEXT nullable     -- SummaryId for daily dedup
  garmin_sleep_summary_id  TEXT nullable     -- SummaryId for sleep dedup
  garmin_hrv_summary_id    TEXT nullable     -- SummaryId for HRV dedup
  -- Audit
  inserted_at              TIMESTAMPTZ NOT NULL default now()
  updated_at               TIMESTAMPTZ NOT NULL default now()
```

Unique constraint: `(athlete_id, calendar_date)` — upsert on conflict.

**Sleep CalendarDate join rule [L1]:** `GarminDay.calendar_date` is the wakeup day (morning), not the night before. When joining sleep data to activity data, use `garmin_day.calendar_date = activity.start_time::date`. A run on Saturday that follows Friday night sleep will have `calendar_date = Saturday`. All correlation queries must use this join logic.

**AC:**
- `garmin_003_garmin_day.py` migration applies cleanly, downgrades cleanly
- `(athlete_id, calendar_date)` unique constraint enforced
- Upsert (`INSERT ... ON CONFLICT (athlete_id, calendar_date) DO UPDATE`) works correctly
- Existing `daily_readiness` table is NOT modified (different model, different use)
- `GarminSleep`, `GarminHRV` do not appear as separate models anywhere in the codebase after this deliverable

---

### D2: OAuth 2.0 PKCE Flow

Following the Strava pattern in `routers/strava.py`. All endpoints in `routers/garmin.py`.

**OAuth version: CONFIRMED OAuth 2.0 with PKCE (S256).** Portal verification on Feb 22, 2026 confirmed the 4-step PKCE flow. OAuth 1.0a contingency is retired — Garmin's token-exchange endpoint in the Partner API is a legacy migration path only.

#### D2.1: Connect flow

| Endpoint | Method | Auth required | Description |
|---|---|---|---|
| `/v1/garmin/auth-url` | GET | Athlete | Returns Garmin OAuth 2.0 PKCE authorization URL |
| `/v1/garmin/callback` | GET | None (Garmin callback) | Exchanges code + code_verifier for tokens, stores encrypted |
| `/v1/garmin/status` | GET | Athlete | Returns `{connected: bool, last_sync: datetime|null}` |

**PKCE flow implementation:**

1. **`GET /v1/garmin/auth-url`:**
   - Generate `code_verifier`: cryptographically random string, 43-128 chars, charset A-Z a-z 0-9 `-.~_`
   - Compute `code_challenge`: `base64url(sha256(code_verifier))`
   - Generate `state`: random string bound to the authenticated StrideIQ athlete session (used to look up `code_verifier` and athlete on callback)
   - Store `code_verifier` and `athlete_id` keyed by `state` (Redis or DB, TTL 10 minutes)
   - Return authorization URL: `https://connect.garmin.com/oauth2Confirm?client_id={GARMIN_CLIENT_ID}&response_type=code&state={state}&redirect_uri={GARMIN_REDIRECT_URI}&code_challenge={code_challenge}&code_challenge_method=S256`

2. **`GET /v1/garmin/callback?code=X&state=Y`:**
   - Verify `state` matches a stored pending authorization (CSRF protection)
   - Retrieve `code_verifier` and `athlete_id` from stored state
   - Exchange `code` + `code_verifier` for tokens at Garmin token endpoint
   - Store encrypted tokens on Athlete model
   - Fetch user ID via `GET /rest/user/id` → store as `garmin_user_id`
   - Fetch permissions via `GET /rest/user/permissions` → verify required permissions granted
   - Set `garmin_connected=True`
   - Enqueue `garmin_initial_backfill_task` (D7)
   - Redirect to frontend

**User consent screen:** After redirect, user sees Garmin consent screen with 4 toggles:
- Activities (default ON) → `ACTIVITY_EXPORT`
- Women's Health (default ON) → `MCT_EXPORT`
- Daily Health Stats (default ON) → `HEALTH_EXPORT`
- Historical Data (default OFF) → controls backfill access

**Required permissions:** `ACTIVITY_EXPORT` and `HEALTH_EXPORT` are required. If either is denied, set `garmin_connected=True` but log a warning and limit sync scope accordingly. `MCT_EXPORT` is optional (Tier 2).

**Consent audit log [G5-M8]:** Garmin connect is a material change to what data enters AI pipelines. Log to `consent_audit_log` using the existing schema — no migration needed:
- On successful connect: `consent_type="integration"`, `action="garmin_connected"`, `source="settings"`, `athlete_id`, `ip_address`
- This is an informational audit entry — not an AI consent grant. The AI consent gate (`has_ai_consent()`) is separate and already in place.
- `consent_type="integration"` is a new value alongside the existing `"ai_processing"` type. The model docstring notes that `consent_type` is extensible.

**AC:**
- `GET /v1/garmin/auth-url` returns 200 with `{auth_url: "https://connect.garmin.com/oauth2Confirm?..."}` for authenticated athlete
- Auth URL includes `code_challenge`, `code_challenge_method=S256`, `state`, `redirect_uri`
- `code_verifier` is stored server-side keyed by `state` (never sent to client)
- `GET /v1/garmin/callback?code=X&state=Y` exchanges code + code_verifier, stores encrypted tokens, sets `garmin_connected=True`, returns redirect to frontend
- `GET /v1/garmin/status` returns `{connected: false}` for unconnected athlete
- `GET /v1/garmin/status` returns `{connected: true, last_sync: "..."}` for connected athlete
- OAuth state parameter verified on callback (CSRF protection) — invalid/missing state returns 400
- Tokens stored encrypted — `garmin_oauth_access_token` and `garmin_oauth_refresh_token` are never stored in plaintext
- Successful connect creates a `consent_audit_log` entry with `consent_type="integration"`, `action="garmin_connected"`, `source="settings"`
- After connect, `garmin_user_id` is populated from `GET /rest/user/id`

#### D2.2: Token refresh [M3]

Mirror `ensure_fresh_token` pattern from Strava.

**VERIFIED:** Refresh requires `refresh_token` + `client_secret` (portal Refresh Token page). If the refresh token is invalid or expired, full re-authentication is required.

**Logic:**
1. Before any Garmin API call, check `garmin_oauth_token_expires_at`
2. If expired (or within 5 minutes of expiry), call Garmin refresh endpoint with `refresh_token` + `GARMIN_CLIENT_SECRET`
3. On successful refresh: update `garmin_oauth_access_token`, `garmin_oauth_refresh_token` (always store returned refresh token — rotation behavior unknown, code defensively), `garmin_oauth_token_expires_at`
4. On refresh failure (including expired refresh token): set `garmin_connected=False`, log the failure, do NOT throw to the caller — return a structured error so the task can skip gracefully. Athlete must go through full OAuth consent flow again to reconnect.

**Environment variables required:** `GARMIN_CLIENT_ID`, `GARMIN_CLIENT_SECRET`, `GARMIN_REDIRECT_URI` — all in `.env.example`.

**AC:**
- `ensure_fresh_garmin_token(athlete_id, db)` exists in `services/garmin_oauth.py`
- Refresh call includes `client_secret` from `GARMIN_CLIENT_SECRET` env var
- Expired token triggers refresh before API call
- Refresh failure sets `garmin_connected=False` — athlete must reconnect via full OAuth flow
- Returned refresh token is always stored (handles both rotation and non-rotation)
- No API calls are made with an expired token
- Test: mock expired token → verify refresh is called before the actual API request
- Test: mock expired refresh token (refresh returns 401) → verify `garmin_connected=False` is set

#### D2.3: Disconnect + data purge [F1]

| Endpoint | Method | Auth required | Description |
|---|---|---|---|
| `/v1/garmin/disconnect` | POST | Athlete | Disconnects Garmin, purges data, calls deregistration |

**Disconnect behavior (ordered):**

1. Call Garmin deregistration endpoint: `DELETE /rest/user/registration` (returns `204 No Content`). VERIFIED via `docs/garmin-portal/PARTNER_API.md`.
2. Clear OAuth tokens immediately: `garmin_oauth_access_token=None`, `garmin_oauth_refresh_token=None`, `garmin_oauth_token_expires_at=None`, `garmin_user_id=None`, `garmin_connected=False`
3. Reset `AthleteIngestionState` for Garmin sync (if the model tracks Garmin sync state separately from Strava). [G5-L4]
4. Delete all `GarminDay` rows for this athlete (wellness data is sourced entirely from Garmin — no other provider)
5. Delete Activities with `provider="garmin"` **on explicit disconnect only**. On token expiry/auth failure (soft disconnect), retain activities — they still represent real training data. On explicit athlete-initiated disconnect, delete.
6. Log to `consent_audit_log`: `consent_type="integration"`, `action="garmin_disconnected"`, `source="settings"`, `athlete_id`, `ip_address` [G5-M8]

**Soft disconnect (token failure, not user-initiated):** Sets `garmin_connected=False`, clears tokens, does NOT delete `GarminDay` or activities. The athlete's historical data is preserved. They reconnect to resume sync.

**Idempotency:** Calling disconnect multiple times is safe. If tokens are already null, skip the deregistration call. If `GarminDay` rows don't exist, skip. Return 200 in all cases.

**GDPR deletion scope [G5-H5, G5-M6]:** `DELETE /v1/gdpr/delete-account` (note: actual endpoint is `/delete-account`, not `/delete`) must be extended with two additions:
1. `db.query(GarminDay).filter(GarminDay.athlete_id == athlete_id).delete()` — new addition for Phase 2
2. `db.query(ActivityStream).filter(ActivityStream.activity_id.in_(activity_ids)).delete()` — pre-existing gap, fix now

Both deletions must happen before the parent `Activity` rows are deleted (FK constraint order). Import `GarminDay` into `routers/gdpr.py` alongside existing model imports.

**AC:**
- `POST /v1/garmin/disconnect` returns 200
- After disconnect: `garmin_connected=False`, all four token fields are null
- After disconnect: `GarminDay` rows for the athlete are absent from the database
- After disconnect: Activities with `provider="garmin"` are absent for the athlete
- After disconnect: calling disconnect again returns 200 (idempotent)
- Disconnect creates a `consent_audit_log` entry with `consent_type="integration"`, `action="garmin_disconnected"`, `source="settings"`
- `DELETE /v1/gdpr/delete-account` includes `GarminDay`, `ActivityStream`, and Garmin-provider activities in purge scope
- Integration test: connect athlete → create `GarminDay` rows → explicit disconnect → verify `GarminDay` rows absent → verify Garmin activities absent → disconnect again → verify 200
- Integration test: GDPR delete for athlete with Garmin data → `GarminDay` rows absent AND `ActivityStream` rows absent

---

### D3: Adapter Layer

**`services/garmin_adapter.py`** — single file responsible for all Garmin API field translations. If Garmin renames a field, only this file changes.

#### D3.1: Activity adapter

`adapt_activity_summary(raw: dict) -> dict` — maps Garmin Activity Summary payload to internal `Activity` model field names.

**Field translations (Tier 1 — official `ClientActivity` schema only):**

| Garmin field (official) | Internal field | Transform |
|---|---|---|
| `summaryId` | `external_activity_id` | string as-is |
| `activityId` | `garmin_activity_id` | int64 — Garmin's native activity ID |
| `startTimeInSeconds` | `start_time` | Unix → `datetime` UTC |
| `startTimeOffsetInSeconds` | (used for local time only) | Add to `start_time` for local |
| `durationInSeconds` | `duration_s` | int |
| `activityType` | `sport` | mapping: RUNNING/TRAIL_RUNNING/TREADMILL_RUNNING/INDOOR_RUNNING → `"run"`, all others → `None` (skip) |
| `activityName` | `name` | string |
| `averageHeartRateInBeatsPerMinute` | `avg_hr` | int |
| `maxHeartRateInBeatsPerMinute` | `max_hr` | int |
| `averageSpeedInMetersPerSecond` | `average_speed` | float |
| `distanceInMeters` | `distance_m` | float |
| `totalElevationGainInMeters` | `total_elevation_gain` | float |
| `totalElevationLossInMeters` | `total_descent_m` | float |
| `averageRunCadenceInStepsPerMinute` | `avg_cadence` | int |
| `maxRunCadenceInStepsPerMinute` | `max_cadence` | int |
| `averagePaceInMinutesPerKilometer` | `avg_pace_min_per_km` | float |
| `maxPaceInMinutesPerKilometer` | `max_pace_min_per_km` | float |
| `maxSpeedInMetersPerSecond` | `max_speed` | float |
| `activeKilocalories` | `active_kcal` | int |
| `steps` | `steps` | int |
| `deviceName` | `device_name` | string |
| `startingLatitudeInDegree` | `start_lat` | float |
| `startingLongitudeInDegree` | `start_lng` | float |
| `manual` | `source` | `True → "garmin_manual"`, `False → "garmin"` |
| `isWebUpload` | (informational) | Log only |
| — | `provider` | hardcoded `"garmin"` |

**Fields NOT mapped in Tier 1 adapter [PV-6]:**
- Running dynamics (stride length, GCT, GCT balance, vertical oscillation, vertical ratio, GAP) — FIT-file-only
- Training Effect (aerobic TE, anaerobic TE, TE label) — not in official schema
- Self-evaluation (feel, perceived effort) — not in official schema
- Body Battery impact — not in official schema
- Moving time — not in official schema
- Power at summary level — not in official `ClientActivity` schema (available in stream `Sample` only)

These fields may appear in actual webhook payloads (Garmin sometimes sends undocumented fields). If the D4.3 live webhook capture reveals their presence, add them to the adapter in a follow-up commit with test coverage. Do not assume they exist.

**Missing/null field handling:** All fields nullable in the model. If a Garmin field is absent or null in the payload, set the internal field to `None`. Never raise on a missing optional field.

#### D3.2: Health/wellness adapter

`adapt_daily_summary(raw: dict) -> dict` — maps Health API Daily Summary to `GarminDay` fields.

`adapt_sleep_summary(raw: dict) -> dict` — maps Sleep Summary fields to `GarminDay` sleep fields.

`adapt_hrv_summary(raw: dict) -> dict` — maps HRV Summary to `GarminDay` HRV fields.

`adapt_stress_detail(raw: dict) -> dict` — maps Stress Detail to `GarminDay` JSONB fields.

**Stress value encoding:** Negative values (`-1` through `-5`) indicate data quality issues (off-wrist, large motion, etc.) — store as-is, do not treat as actual stress scores. Any consumer of `avg_stress` or `stress_samples` must filter out negative values before computing statistics.

**Sleep CalendarDate [L1]:** The adapter preserves `CalendarDate` as-is from Garmin's payload. The `GarminDay.calendar_date` field is the wakeup day (morning), not the night before. Correlation queries must join on wakeup day. The adapter must NOT adjust the date — it is correct as Garmin provides it. A docstring in `adapt_sleep_summary` must document this.

#### D3.3: Deduplication contract [H2]

**Deduplication operates post-adapter on internal field names only.**

The `services/activity_deduplication.py` service must never receive a raw Garmin API payload. The call chain is:

```
raw Garmin payload → garmin_adapter.adapt_activity_summary() → internal dict → activity_deduplication.py
```

`activity_deduplication.py` already operates on internal field names (`start_time`, `distance_m`, `avg_hr`). If it currently references any provider-specific field names (`startTimeLocal`, `StartTimeInSeconds`, etc.), fix before Phase 2 ships.

**AC:**
- `adapt_activity_summary` is the only place Garmin field names appear in adapter-to-model path
- `activity_deduplication.py` contains no Garmin field name strings (verified by test — grep for `StartTime`, `startTime`, `SummaryId` in `activity_deduplication.py`)
- Running `adapt_activity_summary` on a sample Garmin activity payload produces a dict containing only internal field names

---

### D4: Webhook Endpoints [H4, PV-2, PV-3, PV-4, PV-8]

**Webhook topology: per-type routes [PV-2].** Portal verification confirmed each data type has its own URL field in the Garmin developer portal. The advisor locked this to per-type routes. Each data type gets a dedicated endpoint.

**Rationale:** Per-type routes reduce ambiguity, simplify per-handler logic, and avoid brittle payload discriminator parsing. The portal is already per-type — matching that structure eliminates a translation layer.

**Garmin delivery modes** (from `docs/garmin-portal/ENDPOINT_CONFIGURATION.md`):
- `on hold` — paused, no data sent
- `enabled` — ping mode (Garmin notifies, we pull via API)
- `push` — full data in webhook payload

Activity Files, Deregistrations, and User Permissions Change are **ping-only** (no push). All health/wellness types support push.

#### D4.0: Webhook route table

**Tier 1 endpoints (required for MVP):**

| Portal Data Type | Route | Delivery Mode | Celery Task |
|---|---|---|---|
| ACTIVITY - Activities | `POST /v1/garmin/webhook/activities` | push | `process_garmin_activity_task` |
| ACTIVITY - Activity Details | `POST /v1/garmin/webhook/activity-details` | push | `process_garmin_activity_detail_task` |
| HEALTH - Sleeps | `POST /v1/garmin/webhook/sleeps` | push | `process_garmin_health_task` |
| HEALTH - HRV Summary | `POST /v1/garmin/webhook/hrv` | push | `process_garmin_health_task` |
| HEALTH - Stress | `POST /v1/garmin/webhook/stress` | push | `process_garmin_health_task` |
| HEALTH - Dailies | `POST /v1/garmin/webhook/dailies` | push | `process_garmin_health_task` |
| HEALTH - User Metrics | `POST /v1/garmin/webhook/user-metrics` | push | `process_garmin_health_task` |
| COMMON - Deregistrations | `POST /v1/garmin/webhook/deregistrations` | enabled (ping) | `process_garmin_deregistration_task` |
| COMMON - User Permissions Change | `POST /v1/garmin/webhook/permissions` | enabled (ping) | `process_garmin_permissions_task` |

**Tier 2 endpoints (enable when ready):**

| Portal Data Type | Route | Notes |
|---|---|---|
| HEALTH - Respiration | `POST /v1/garmin/webhook/respiration` | Tier 2 |
| HEALTH - Body Compositions | `POST /v1/garmin/webhook/body-comps` | Tier 2 |
| HEALTH - Pulse Ox | `POST /v1/garmin/webhook/pulse-ox` | Tier 2 |
| WOMEN_HEALTH - MCT | `POST /v1/garmin/webhook/mct` | Tier 2 — separate `GarminCycle` model |

**Deferred endpoints (not registered in portal during Phase 2):**
- ACTIVITY - Activity Files (ping-only — FIT parsing is future work)
- ACTIVITY - Manually Updated Activities
- ACTIVITY - MoveIQ
- HEALTH - Epochs (high volume)
- HEALTH - Blood Pressure, Skin Temperature, Health Snapshot

All per-type routes share a common authentication middleware (D4.1).

#### D4.1: Webhook security [PV-3]

**Requirement:** Every incoming webhook request must be authenticated before any data is processed.

**VERIFIED: No HMAC/signing secret exists in Garmin's portal.** No signature configuration, no shared secret field. Security must use mandatory layered compensating controls.

**Mandatory layered controls (all required, not pick-one):**

1. **`garmin-client-id` header check:** Verify the `garmin-client-id` request header matches `GARMIN_CLIENT_ID` env var. Reject if missing or mismatched. This is the primary gate.
2. **Strict schema validation:** Validate incoming payload against expected schema for the endpoint's data type. Reject malformed payloads with `400`.
3. **Unknown `userId` handling:** If `userId` in payload does not match any athlete's `garmin_user_id`, return `200` (avoid Garmin retry storms) but log the event and skip all processing. Do not create data for unknown users.
4. **Rate limiting:** Apply per-IP rate limiting on webhook endpoints. Log and reject excessive request rates with `429`.
5. **IP allowlisting (best-effort):** If Garmin publishes source IP ranges (check during implementation or contact Garmin support), configure allowlist. If not obtainable, document the gap and rely on layers 1-4.

**Auth failure behavior:**
- Missing/wrong `garmin-client-id` header → `401`, no processing, no task enqueued
- Valid header but unknown `userId` → `200`, logged, skipped (not a security failure — may be a user who hasn't connected yet)
- Valid header but malformed payload → `400`, logged

**AC:**
- All webhook routes share a common `verify_garmin_webhook` dependency that checks the `garmin-client-id` header
- Request with missing `garmin-client-id` header → `401`
- Request with wrong `garmin-client-id` header → `401`
- Request with valid header → `200` and processing task enqueued
- Request with valid header but unknown `userId` → `200`, no task processing, event logged
- Request with valid header but malformed payload → `400`
- Rate limiting is applied per-IP on all webhook routes
- `GARMIN_CLIENT_ID` is read from env var — never hardcoded in source
- Test: correct header → 200; wrong header → 401; missing header → 401; unknown userId → 200 + skip; malformed body → 400

#### D4.2: Webhook dispatch

On authenticated webhook receipt:
1. Return `200` immediately (Garmin expects fast acknowledgement)
2. Enqueue appropriate Celery task with payload (task determined by route, not by payload inspection)
3. Task processes data asynchronously

**AC:**
- Each webhook endpoint returns `200` within 500ms regardless of payload size
- All processing happens in Celery worker, not in the webhook handler
- Failed task processing is logged with full payload for debugging
- Duplicate webhook deliveries (same `SummaryId`) are deduplicated — task checks if record exists before processing

#### D4.3: First-live-webhook completion gate [PV-4, PV-8]

**D4 cannot be marked DONE until the following are captured and documented:**

1. Actual HTTP headers sent by Garmin on a real webhook request (confirm `garmin-client-id` header presence and format)
2. Actual payload envelope shape (is it a single object? array of objects? wrapped in a container?)
3. Data Generator or real device sync used to trigger at least one webhook for each Tier 1 data type

**Process:** Deploy D4 endpoints to eval environment → configure URLs in portal Endpoint Configuration → use Data Generator to trigger test payloads → capture and document in `docs/garmin-portal/WEBHOOK_PAYLOAD_SAMPLES.md`.

If the live payload contradicts any assumption in D4.1 or D4.2, update the handler before marking D4 complete.

---

### D5: Activity Sync

#### D5.1: Activity ingestion

`process_garmin_activity_task(athlete_id, raw_payload)` Celery task:

1. Call `ensure_fresh_garmin_token(athlete_id, db)` — abort if token refresh fails
2. Call `garmin_adapter.adapt_activity_summary(raw_payload)` — get internal dict
3. Filter: only process `sport="run"` activities (skip cycling, etc.)
4. Call `activity_deduplication.check_duplicate(adapted, db)` — see D5.2
5. If not duplicate: create `Activity` row with `provider="garmin"`, `source="garmin"` or `"garmin_manual"`
6. Enqueue stream processing if Activity Details endpoint is available
7. Update `last_garmin_sync` on athlete

#### D5.2: Deduplication with Strava [H2, F2]

**Post-adapter deduplication — internal field names only.**

Deduplication thresholds (from `services/activity_deduplication.py`):
- Time window: 1 hour
- Distance tolerance: 5%
- HR tolerance: 5 bpm (if both present)

**Takeout import (garmin_di_connect.py) uses different thresholds (120s / 1.5%)** — this is intentional. The two-threshold design reflects different confidence levels: file import has exact timing; live sync has potential clock drift.

**Test [M1]:** Activity imported via takeout → same activity arrives via webhook → verify exactly one Activity row exists in the database after both ingestion paths complete.

**Provider precedence when Garmin and Strava both have the same activity [F2]:**

**Decision: Garmin is primary, Strava is secondary.** This is not an inherited default — it is an explicit architectural decision. Rationale: Garmin data comes directly from the device sensor (barometric altimeter, footpod cadence, native GPS). Strava data is often re-processed from the same source or estimated. Device-native data is authoritative.

Concretely: when deduplication finds a match between a new Garmin activity and an existing Strava activity, the Garmin activity wins — the existing `Activity` row is updated with Garmin fields and `provider` is set to `"garmin"`.

**Athlete override (future, Tier 2):** A future user preference setting may allow an athlete to choose Strava as primary. This is not built in Phase 2.

**AC:**
- Activity arrives from Garmin for athlete with Strava already connected
- Duplicate is detected (time + distance match)
- Existing Activity row: `provider` updated to `"garmin"`, Garmin-sourced fields populated
- No second Activity row created
- Test: create Strava Activity → ingest matching Garmin activity → assert single row with `provider="garmin"`

#### D5.3: Running dynamics — RESOLVED [M2]

**VERIFIED via portal documentation (Feb 22, 2026):** Running dynamics (stride length, GCT, GCT balance, vertical oscillation, vertical ratio) are **NOT present in the official JSON API**. The `ClientActivity` summary schema and `Sample` stream schema in `docs/garmin-portal/HEALTH_API.md` do not include these fields. They exist only in raw FIT files (`GET /rest/activityFile`).

**`powerInWatts` IS available** in Activity Detail stream samples. Average/max power can be computed from stream data.

**Decision:** Running dynamics columns remain in migration (nullable). They are not mapped in the Tier 1 adapter and not populated. FIT file parsing is deferred to Tier 2.

**AC:**
- Comment at top of `garmin_adapter.py` documents: "Running dynamics (stride length, GCT, VO, VR) not available in JSON API — FIT-file-only. Power available in stream samples."
- Running dynamics columns (`avg_stride_length_m`, `avg_ground_contact_ms`, `avg_ground_contact_balance_pct`, `avg_vertical_oscillation_cm`, `avg_vertical_ratio_pct`, `avg_gap_min_per_mile`) are present in schema but NOT populated by Tier 1 adapter
- No test asserts these fields are populated from JSON API data

---

### D6: Health/Wellness Sync

`process_garmin_health_task(athlete_id, data_type, raw_payload)` Celery task.

Processes daily summary, sleep, HRV, and stress detail payloads into `GarminDay` rows.

#### D6.1: Upsert logic

`GarminDay` uses upsert on `(athlete_id, calendar_date)`. Receiving a sleep update for a date that already has a daily summary row merges the new fields — it does not create a new row.

**Upsert strategy:** `INSERT INTO garmin_day (...) ON CONFLICT (athlete_id, calendar_date) DO UPDATE SET ...`

Only the fields present in the incoming payload are updated. Fields sourced from a different API endpoint (e.g., sleep fields when processing a daily summary update) are left unchanged.

#### D6.2: Sleep CalendarDate join test [L1]

A specific test must verify the join logic:

**Test scenario:**
1. Insert a `GarminDay` row with `calendar_date = 2026-02-21` (Saturday) containing sleep data from Friday night (athlete went to sleep Friday, woke up Saturday)
2. Insert an `Activity` row with `start_time` of Saturday Feb 21
3. Query correlation engine join: `garmin_day.calendar_date = activity.start_time::date`
4. Assert the sleep row joins correctly to the Saturday activity
5. Assert that querying for `calendar_date = 2026-02-20` (Friday) does NOT return this sleep row

**AC:**
- Test above passes
- No correlation query uses `calendar_date` as the night-before date

#### D6.3: Stress value filter

Any analytics query that computes `avg_stress` must exclude negative values (-1 through -5). Negative values mean "insufficient data" — not actual low stress scores. A stress score of -1 is not `1`.

**AC:**
- `GarminDay.avg_stress` is stored as-is (including negatives)
- Any analytics function that reads `avg_stress` filters: `WHERE avg_stress > 0`
- Test: insert `GarminDay` row with `avg_stress=-1` → analytics query → assert row excluded from average

---

### D7: Initial Backfill

**Prerequisite: D4 webhook endpoints must be deployed and registered in portal before backfill can be triggered.** Backfill endpoints return `202 Accepted` — data is delivered asynchronously via webhook push to the registered endpoints, NOT returned synchronously in the API response. See `docs/garmin-portal/HEALTH_API.md` (backfill section).

`garmin_initial_backfill_task(athlete_id)` — triggered automatically after successful OAuth connect (callback success).

**Backfill depth: 90 days [M4]**

Rationale: 90 days is the correlation engine's analysis window. Data older than 90 days does not contribute to current correlation findings. This is consistent across all data sources.

**Backfill scope:**
- Activities: last 90 days via `GET /rest/backfill/activities` (returns 202, data pushed to webhook)
- Activity Details: last 90 days via `GET /rest/backfill/activityDetails` (returns 202)
- Health/wellness: last 90 days of dailies, sleeps, HRV, stress via respective backfill endpoints (all return 202)

**Backfill behavior:**
- Runs as background Celery task after connect — does not block OAuth callback
- Calls Garmin backfill API endpoints which return `202 Accepted` immediately
- Garmin queues the backfill and pushes data to webhook endpoints when ready (may take minutes to hours)
- Uses same deduplication logic as live sync (D5.2) — data arrives via same webhook paths
- Rate-limit aware: backs off if Garmin returns 429
- Idempotent: safe to re-run (upsert on `GarminDay`, dedup on Activities)
- **Note:** Historical Data toggle on user consent screen defaults to OFF. If athlete has not enabled it, backfill may return limited or no data. Log this condition.

**AC:**
- After OAuth connect completes, `garmin_initial_backfill_task` is enqueued
- Task ingests up to 90 days of activities
- Task ingests up to 90 days of wellness data into `GarminDay`
- If athlete already has Strava activities for the same dates, deduplication runs normally (no bypass)
- Re-running backfill does not create duplicate rows
- Test: run backfill twice for same athlete → assert row counts unchanged after second run

---

### D8: Attribution (Garmin Badge)

Per compliance Section 6.1/6.2/6.4: any screen displaying Garmin-sourced data must include Garmin attribution per brand guidelines at `https://developer.garmin.com/brand-guidelines/overview/`.

#### D8.1: `GarminBadge` component

New React component: `apps/web/components/common/GarminBadge.tsx`

- Displays Garmin logo/wordmark per brand guidelines
- Used conditionally: rendered only when `provider="garmin"`
- Must not be stretched, recolored, or distorted
- Must not imply Garmin endorsement of StrideIQ

#### D8.2: Attribution placement

| Screen | Condition | Attribution |
|---|---|---|
| Activity detail page | `activity.provider === "garmin"` | `GarminBadge` near data source |
| Home page hero | If hero metrics sourced from Garmin activity | `GarminBadge` |
| Progress/training load | If data includes Garmin-sourced activities | `GarminBadge` or per-metric attribution |
| Sleep/HRV display (future) | All `GarminDay` data | `GarminBadge` always |

**AC:**
- `GarminBadge` renders correctly per Garmin brand guidelines
- Activity detail page renders `GarminBadge` when `provider="garmin"`
- Activity detail page does NOT render `GarminBadge` when `provider="strava"`
- Brand guideline review checklist item completed before Phase 2 merges to `main`

---

## 4. Provider Precedence Contract Tests [F2]

These tests must exist and pass before Phase 2 is implementation-complete.

### At dedup-time

| Test | Scenario | Expected |
|---|---|---|
| `test_garmin_wins_over_strava_on_dedup` | Existing Strava activity. Garmin activity arrives with matching time/distance. | Single Activity row, `provider="garmin"` |
| `test_no_duplicate_created_on_garmin_strava_overlap` | Same as above. | Single Activity row exists — row count unchanged after Garmin ingest |
| `test_strava_kept_when_garmin_not_match` | Existing Strava activity. Garmin activity with different time/distance. | Two separate Activity rows — different runs |
| `test_garmin_only_athlete` | Athlete with no Strava. Garmin activity arrives. | Activity row created with `provider="garmin"` |

### At read-time (query/retrieval behavior)

| Test | Scenario | Expected |
|---|---|---|
| `test_home_endpoint_uses_garmin_activity` | Athlete has both Strava and Garmin records for same run. | Home endpoint returns data from `provider="garmin"` row |
| `test_activity_list_deduped` | Athlete has Strava + Garmin for same run. | Activity list shows one run, not two |
| `test_garmin_fields_visible_in_strava_activity_slot` | Garmin wins dedup, populates running dynamics fields. | Activity detail includes `avg_cadence`, `avg_stride_length_m`, etc. |

---

## 5. Full Test Plan

### Category 1: Unit Tests

- `test_adapt_activity_summary_maps_all_fields` — feed a complete sample Garmin payload, assert every internal field is present and correctly typed
- `test_adapt_activity_summary_unknown_sport_returns_none` — CYCLING → `sport=None`
- `test_adapt_activity_summary_missing_optional_field` — payload missing `AverageRunCadenceInStepsPerMinute` → `avg_cadence=None` (no raise)
- `test_adapt_daily_summary_negative_stress_preserved` — `-1` stored as `-1` in `avg_stress`
- `test_adapt_sleep_summary_calendar_date_preserved` — `CalendarDate` stored as-is, docstring present
- `test_adapt_hrv_summary_maps_correct_fields` — `LastNightAvg` → `hrv_overnight_avg`, `LastNight5MinHigh` → `hrv_5min_high`
- `test_dedup_uses_internal_field_names` — `activity_deduplication.py` contains no Garmin field name strings
- `test_training_effect_fields_not_in_correlation_engine` — grep test: `garmin_aerobic_te` absent from all correlation service source files
- `test_webhook_missing_client_id_header_returns_401` — missing `garmin-client-id` header → 401
- `test_webhook_wrong_client_id_header_returns_401` — wrong `garmin-client-id` value → 401
- `test_webhook_valid_client_id_header_returns_200` — correct header → 200
- `test_webhook_unknown_user_id_returns_200_skips` — valid header, unknown `userId` → 200, no processing
- `test_webhook_malformed_payload_returns_400` — valid header, bad JSON schema → 400
- `test_token_refresh_on_expiry` — expired token triggers refresh before API call
- `test_token_refresh_failure_sets_disconnected` — refresh fails → `garmin_connected=False`
- `test_token_refresh_expired_refresh_token_sets_disconnected` — refresh token expired (401 from Garmin) → `garmin_connected=False`

### Category 2: Integration Tests

- `test_garmin_oauth_connect_flow` — full OAuth: auth-url → callback → status connected
- `test_garmin_connect_logs_audit_entry` — connect → `consent_audit_log` row with `consent_type="integration"`, `action="garmin_connected"` [G5-M8]
- `test_garmin_disconnect_clears_tokens` — disconnect → tokens null, `garmin_connected=False`
- `test_garmin_disconnect_purges_garmin_day_rows` — disconnect → `GarminDay` rows absent
- `test_garmin_disconnect_purges_provider_garmin_activities` — explicit disconnect → Garmin activities absent
- `test_garmin_disconnect_logs_audit_entry` — disconnect → `consent_audit_log` row with `consent_type="integration"`, `action="garmin_disconnected"` [G5-M8]
- `test_garmin_disconnect_idempotent` — disconnect twice → 200 both times
- `test_gdpr_delete_includes_garmin_day_and_activity_stream` — GDPR delete → `GarminDay` rows absent AND `ActivityStream` rows absent [G5-H5]
- `test_garmin_day_upsert` — insert daily summary → insert sleep for same date → single row with merged fields
- `test_garmin_day_unique_constraint` — cannot insert two rows for same (athlete_id, calendar_date)
- `test_sleep_calendar_date_join_wakeup_day` — sleep on Friday night (`calendar_date=Saturday`) joins correctly to Saturday activity [L1]
- `test_backfill_idempotent` — run twice → same row count [D7]
- `test_dedup_two_thresholds_live_vs_takeout` — takeout import then live webhook for same activity → single row [M1]
- `test_dedup_runtime_uses_internal_field_names` — runtime integration test: create Strava activity via adapter → pass to deduplication → confirm match found correctly (not a grep test — actual execution against test DB) [G5-M3, D0]

### Category 3: Provider Precedence Tests [F2]

All 7 tests listed in Section 4. Note: the read-time tests (`test_home_endpoint_uses_garmin_activity`, `test_activity_list_deduped`, `test_garmin_fields_visible_in_strava_activity_slot`) are runtime integration tests that hit the actual endpoints and query results from a test database — not source inspection. [G5-M3]

### Category 4: Contract Tests (regression locks) [G5-M3]

Each contract area has both a grep/source inspection test AND a runtime integration test. Grep tests detect the violation fast; runtime tests verify actual behavior.

**Grep/source inspection tests:**
- `test_garmin_adapter_is_only_file_with_garmin_field_names` — Garmin API field names (`StartTimeInSeconds`, `SummaryId`, etc.) appear ONLY in `garmin_adapter.py`, nowhere else
- `test_activity_dedup_has_no_provider_field_names` — `activity_deduplication.py` contains none of: `startTimeLocal`, `startTime`, `start_date_local`, `distanceInMeters`, `averageHeartRate`, `avgHeartRate` [D0, G5-H6]
- `test_garmin_day_model_exists_no_garmin_sleep_or_hrv` — `GarminDay` model exists; `GarminSleep`, `GarminHRV` do not
- `test_training_api_never_called` — no Training API client import anywhere in codebase
- `test_webhook_client_id_from_env` — `GARMIN_CLIENT_ID` read from env var for webhook auth, never hardcoded in source
- `test_legacy_garmin_tasks_retired` — `apps/api/tasks/garmin_tasks.py` does not exist or contains no references to `garmin_username`, `garmin_password_encrypted`, or `garmin_service` [PV-7]

**Runtime integration tests (behavior, not source inspection):**
- `test_dedup_accepts_only_internal_field_names_runtime` — call dedup service with a dict using internal field names → match found; call with Garmin API field names → no match (field name sensitivity test)
- `test_provider_precedence_at_read_time_runtime` — insert Strava activity + Garmin activity for same run in test DB → query home endpoint → response contains Garmin-sourced data [G5-M3]

---

## 6. Rollout Plan

### Step 1: Branch setup

```bash
git checkout -b feature/garmin-oauth
```

All commits to this branch until Gate 6 and Gate 0A clear.

### Step 2: Build order

Build in deliverable order. Each deliverable must have its tests passing before starting the next.

```
D0 → D1 → D2 → D3 → D4 → D5 → D6 → D7 → D8
```

Rationale: D0 (dedup refactor) is a prerequisite for all sync deliverables — clean it up first. D1 (models) unblocks everything else. D2 (OAuth) unblocks sync. D3 (adapter) unblocks D4+D5+D6. D7 (backfill) depends on D5+D6. D8 (attribution) can run in parallel with D7.

### Step 3: Eval environment verification — COMPLETE

All portal verification items resolved February 22, 2026 (see Gate 0D table). Key findings documented in `docs/garmin-portal/`:
- OAuth 2.0 PKCE confirmed [M2 RESOLVED]
- Running dynamics NOT in JSON API — FIT-file-only [M2 RESOLVED]
- No webhook HMAC — layered compensating controls required [H4 RESOLVED]
- Deregistration: `DELETE /rest/user/registration` → `204 No Content` [F1 RESOLVED]
- Scopes: `ACTIVITY_EXPORT`, `HEALTH_EXPORT`, `MCT_EXPORT` [RESOLVED]
- Token refresh requires `client_secret` [M3 RESOLVED]

**Remaining D4 implementation-time verification:** First live webhook capture required before D4 completion (D4.3).

### Step 4: 30-day notice

Founder sends display format notice to `connect-support@developer.garmin.com`. Builder provides mockup package. 30-day clock starts. Development continues on feature branch.

### Step 5: Merge gate

`feature/garmin-oauth` may only merge to `main` when ALL of the following are true:

- [ ] All tests pass (full backend suite, no new failures)
- [ ] 30-day notice period elapsed and acknowledged [M5] [Gate 0A]
- [ ] All Gate 0D items verified and documented (see verified table above)
- [ ] D4.3 first-live-webhook completion gate passed — actual headers and payload envelope documented [PV-4, PV-8]
- [ ] Running dynamics confirmed NOT in JSON API — columns present but unpopulated [M2, RESOLVED]
- [ ] Webhook topology: per-type routes deployed and registered in portal [PV-2]
- [ ] OAuth 2.0 PKCE confirmed and implemented [RESOLVED]
- [ ] Attribution component reviewed against Garmin brand guidelines [D8]
- [ ] No references to `garmin_service.py` remain in codebase (retired)
- [ ] `apps/api/tasks/garmin_tasks.py` retired — no references to deprecated auth fields [PV-7]
- [ ] `garmin_username` and `garmin_password_encrypted` columns absent from production schema
- [ ] Garmin deregistration endpoint integrated and tested [F1]
- [x] `EXPECTED_HEADS` updated to `{"garmin_004"}` in CI check [G5-M1] — done in D3 post-review fixes
- [ ] GDPR deletion covers `GarminDay` AND `ActivityStream` [G5-H5]
- [ ] Production containers healthy on `feature/garmin-oauth` test deploy

---

## 7. Must-Fix Traceability

### Gate 2 → AC (10 items)

| # | Gate 2 Item | Addressed In |
|---|---|---|
| 1 | Use `GarminDay` consistently [H3] | D1.3 — `GarminDay` is the sole model; no `GarminSleep`/`GarminHRV` |
| 2 | Separate existing vs new Activity columns [H1] | D1.2 — explicit table with "existing" vs "new" columns and migration name |
| 3 | Dedup post-adapter on internal field names [H2] | D0 + D3.3 — refactor deliverable + adapter contract + runtime integration tests |
| 4 | Webhook security [H4] | D4.1 — **UPDATED:** No HMAC exists. Mandatory layered controls: `garmin-client-id` header + schema validation + userId check + rate limiting + IP allowlist. See PV-3. |
| 5 | Backfill depth 90 days [M4] | D7 — 90 days specified with rationale |
| 6 | 30-day notice as hard rollout gate [M5] | Gate 0A — merge-only gate, build on branch allowed |
| 7 | Running dynamics JSON verification [M2] | D5.3 — eval checkpoint with defer path |
| 8 | Sleep CalendarDate wakeup-day join test [L1] | D6.2 — explicit test scenario specified |
| 9 | Disconnect endpoint + idempotent purge [F1] | D2.3 — ordered steps, idempotency required, deregistration endpoint |
| 10 | Provider precedence contract tests [F2] | Section 4 — 7 named tests; read-time tests are runtime, not grep |

### Gate 5 → AC (10 items)

| # | Gate 5 Item | Addressed In |
|---|---|---|
| G5-H5 | GDPR: add `GarminDay` AND `ActivityStream` deletion | D2.3 — both deletions specified with FK ordering; test added |
| G5-H6 | Dedup refactor: explicit deliverable for field name cleanup | D0 — new deliverable added; prerequisite for all sync work |
| G5-M6 | GDPR endpoint path: `/delete` → `/delete-account` | D2.3 — corrected |
| G5-M7 | OAuth 1.0a contingency note | D2.1 — **RETIRED:** OAuth 2.0 PKCE confirmed via portal verification. Contingency removed. |
| G5-M8 | `consent_audit_log` for connect/disconnect | D2.1 + D2.3 — log entries specified; tests added |
| G5-H1 | Gate 0A contradiction resolved | Section 0 — build on branch allowed; merge blocked; wording unified |
| G5-H2 | Webhook topology: binding decision + portal proof required | D4 — **UPDATED:** per-type routes locked (portal confirms per-type URL registration). See D4.0 route table. |
| G5-M1 | Alembic EXPECTED_HEADS across D1.1–D1.3 | D3 post-review — staged commit strategy; final head is `garmin_004` (D3 added garmin_004 beyond original plan) |
| G5-M2 | [PORTAL VERIFY] dependencies as hard stop-gates per deliverable | Gate 0D — **RESOLVED:** all items verified except D4 implementation-time unknowns (D4.3 completion gate) |
| G5-M3 | Runtime tests alongside grep tests for key contracts | Category 3 + Category 4 — runtime integration tests specified for dedup and read-time precedence |

### Portal Verification → AC (8 items)

| # | Must-Fix Item | Addressed In |
|---|---|---|
| PV-1 | Gate 0D language: "resolved except D4 unknowns" | Gate 0D table — corrected language, D4 completion gate added |
| PV-2 | Webhook topology: per-type routes | D4.0 — route table with 9 Tier 1 + 4 Tier 2 endpoints |
| PV-3 | D4 security: mandatory layered controls | D4.1 — 5 mandatory controls, no HMAC, fail-closed |
| PV-4 | First-live-webhook completion gate | D4.3 — must capture headers + envelope before D4 done |
| PV-5 | Women's Health: Tier 2, separate model | Scope section — moved to Tier 2 deferred, `GarminCycle` model |
| PV-6 | Undocumented fields deferred | D1.2 + D3.1 — TE/self-eval/body-battery not mapped until payload proof |
| PV-7 | Legacy `garmin_tasks.py` retirement | Retired Code table — explicit delete requirement + contract test |
| PV-8 | D4 blocked until Data Generator confirms | D4.3 — Data Generator payload must confirm before D4 done |

---

*Gate 6 approved by founder on February 16, 2026. Portal verification revision applied and advisor GO cleared February 22, 2026. Implementation proceeds on `feature/garmin-oauth`.*
