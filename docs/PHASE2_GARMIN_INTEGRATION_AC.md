# Phase 2: Garmin Connect Integration — Acceptance Criteria

**Date:** February 22, 2026
**Status:** DRAFT — awaiting Gate 5 advisor review and Gate 6 founder approval
**Branch:** `feature/garmin-oauth` (all implementation work — never `main`)
**Input documents:**
- `docs/GARMIN_API_DISCOVERY.md` (field mappings, architecture decisions)
- `docs/GARMIN_CONNECT_DEVELOPER_COMPLIANCE.md` (contractual obligations)
- `docs/ADVISOR_HANDOFF_GARMIN_REVIEW.md` (10 must-fix items from Gate 2)
- `docs/SESSION_HANDOFF_2026-02-19_GARMIN_BUILDER_NOTE.md`

**Must-fix items addressed:** All 10 from Gate 2 review. Traceability markers: [H1]–[H4], [M1]–[M5], [L1]–[L3], [F1]–[F2].

---

## 0. Pre-Build Gates (non-negotiable — all must clear before first commit)

### Gate 0A: 30-Day Display Format Notice [M5]

**Hard rollout gate. Not a checklist item — a calendar dependency.**

The Garmin developer agreement requires 30 days notice to `connect-support@developer.garmin.com` before any screen displaying Garmin-sourced data goes live. This notice must include mockups of:
- Any activity display screen where `provider="garmin"` data is shown
- Any wellness/health data display (sleep, HRV, stress, body battery)
- Any attribution placement for Garmin-sourced data

**Gate cleared when:** Garmin acknowledges receipt of notice AND 30 calendar days have elapsed. The `feature/garmin-oauth` branch may be built and tested on feature branch only until this gate clears. Merging to `main` is blocked until this gate is verified.

Responsibility: Founder sends notice. Builder provides mockups for notice package during Phase 2 build.

### Gate 0B: AI Consent Infrastructure Verified

Phase 1 shipped. `has_ai_consent()` gates all 8 LLM call sites. Before any Garmin-sourced data enters an LLM pipeline, verify that `has_ai_consent()` is evaluated against the same athlete record that owns the Garmin connection. No Garmin data reaches an LLM for athletes who have not granted consent.

**Gate cleared when:** Builder confirms `has_ai_consent()` is called before any Garmin-triggered LLM processing. No new code required — confirm existing gating covers the new Garmin task path.

### Gate 0C: Feature Branch Isolation

All Garmin code lives on `feature/garmin-oauth`. No commits to `main`. CI runs on `main` and `develop` — Garmin work must not trigger CI failures on those branches during development.

---

## 1. Scope

### In scope (Phase 2 — Tier 1)

| Deliverable | What it ships |
|---|---|
| D1 | Data model changes (Athlete OAuth fields + `GarminDay` + Activity new columns) |
| D2 | OAuth 2.0 flow (connect, callback, token refresh, disconnect + data purge) |
| D3 | Adapter layer (`garmin_adapter.py` — all field translations) |
| D4 | Webhook endpoint (security validation + dispatch) |
| D5 | Activity sync (ingest, dedup, provider precedence) |
| D6 | Health/wellness sync (Sleep, HRV, Daily wellness → `GarminDay`) |
| D7 | Initial backfill (90-day on connect) |
| D8 | Attribution (`GarminBadge` component) |

### Out of scope (permanent)

- **Training API:** Permanently out of scope. The Garmin developer agreement (Section 4.6) grants Garmin unlimited rights to any data pushed to their platform — StrideIQ-generated training plans pushed to Garmin would become Garmin's property. Hard boundary, not a deferral.
- **Women's Health API:** Not applicable.
- **Courses API:** Not applicable.
- **Beat-to-beat HRV:** Requires commercial license. Evaluate cost in eval environment. Defer unless cost is reasonable and product need is confirmed.

### Deferred (Tier 2, post-stable Tier 1)

- Stress Detail + Body Battery intraday samples (stored as raw JSONB in Tier 1, computed fields in Tier 2)
- User Metrics / VO2 max trend tracking
- Epoch summaries (15-minute granularity)
- Body composition, blood pressure, pulse ox

---

## 2. Retired Code

Before any new code is written:

| File | Action | Reason |
|---|---|---|
| `apps/api/services/garmin_service.py` | **Delete entirely** | Uses `python-garminconnect` (unofficial library, username/password auth). Active compliance violation — violates §5.2(i) and §5.2(j) of the developer agreement. |
| `apps/api/routers/garmin.py` | **Audit and replace** | Likely references retired service. Rebuild from scratch to official OAuth pattern. |
| `apps/api/tasks/garmin_tasks.py` | **Audit and replace** | May reference retired service. Review, keep any reusable task scaffolding. |
| `apps/api/services/provider_import/garmin_di_connect.py` | **Keep as-is** | Handles takeout/file import — separate use case, no compliance issue. Does not use unofficial library. |

The `garmin_username` and `garmin_password_encrypted` fields on the Athlete model must be removed via Alembic migration (D1 migration scope below).

---

## 3. Deliverables and Acceptance Criteria

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

**[PORTAL VERIFY]** Confirm exact field names returned in OAuth token response before migration is written.

**AC:**
- Migration `garmin_001_oauth_fields.py` applies cleanly on a fresh schema
- Migration downgrades cleanly
- `garmin_username` and `garmin_password_encrypted` absent after upgrade
- OAuth token fields present and nullable after upgrade
- `EXPECTED_HEADS` in `.github/scripts/ci_alembic_heads_check.py` updated to `{"garmin_001_oauth_fields"}`

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

| Garmin field | New Activity column | Type | Notes |
|---|---|---|---|
| `AverageRunCadenceInStepsPerMinute` | `avg_cadence` | Integer, nullable | — |
| `MaxRunCadenceInStepsPerMinute` | `max_cadence` | Integer, nullable | — |
| `AverageStrideLength` | `avg_stride_length_m` | Float, nullable | Meters |
| `AverageGroundContactTime` | `avg_ground_contact_ms` | Float, nullable | Milliseconds |
| `AverageGroundContactTimeBalance` | `avg_ground_contact_balance_pct` | Float, nullable | Left/right % |
| `AverageVerticalOscillation` | `avg_vertical_oscillation_cm` | Float, nullable | Centimeters |
| `AverageVerticalRatio` | `avg_vertical_ratio_pct` | Float, nullable | % |
| `AveragePowerInWatts` | `avg_power_w` | Integer, nullable | — |
| `MaxPowerInWatts` | `max_power_w` | Integer, nullable | — |
| `AverageGradeAdjustedPaceInMinutesPerMile` | `avg_gap_min_per_mile` | Float, nullable | GAP |
| `TotalDescentInMeters` | `total_descent_m` | Float, nullable | — |
| `AerobicTrainingEffect` | `garmin_aerobic_te` | Float, nullable | **Informational only** — never used in StrideIQ load calculations |
| `AnaerobicTrainingEffect` | `garmin_anaerobic_te` | Float, nullable | **Informational only** |
| `TrainingEffectLabel` | `garmin_te_label` | Text, nullable | **Informational only** |
| `SelfEvaluationFeel` | `garmin_feel` | Text, nullable | Low-fidelity — import only |
| `SelfEvaluationPerceivedEffort` | `garmin_perceived_effort` | Integer, nullable | Low-fidelity — import only |
| `BodyBatteryImpact` | `garmin_body_battery_impact` | Integer, nullable | Net body battery drain |
| `MovingTimeInSeconds` | `moving_time_s` | Integer, nullable | Separate from elapsed |
| `MaxSpeedInMetersPerSecond` | `max_speed` | Float, nullable | — |
| `ActiveKilocalories` | `active_kcal` | Integer, nullable | Active only, not BMR |

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

### D2: OAuth 2.0 Flow

Following the Strava pattern in `routers/strava.py`. All endpoints in `routers/garmin.py`.

#### D2.1: Connect flow

| Endpoint | Method | Auth required | Description |
|---|---|---|---|
| `/v1/garmin/auth-url` | GET | Athlete | Returns Garmin OAuth authorization URL |
| `/v1/garmin/callback` | GET | None (Garmin callback) | Exchanges code for tokens, stores encrypted |
| `/v1/garmin/status` | GET | Athlete | Returns `{connected: bool, last_sync: datetime|null}` |

**AC:**
- `GET /v1/garmin/auth-url` returns 200 with `{auth_url: "https://connect.garmin.com/oauthConfirm?..."}` for authenticated athlete
- `GET /v1/garmin/callback?code=X&state=Y` exchanges code, stores encrypted tokens, sets `garmin_connected=True`, returns redirect to frontend
- `GET /v1/garmin/status` returns `{connected: false}` for unconnected athlete
- `GET /v1/garmin/status` returns `{connected: true, last_sync: "..."}` for connected athlete
- OAuth state parameter verified on callback (CSRF protection)
- Tokens stored encrypted — `garmin_oauth_access_token` and `garmin_oauth_refresh_token` are never stored in plaintext

#### D2.2: Token refresh [M3]

Mirror `ensure_fresh_token` pattern from Strava.

**Logic:**
1. Before any Garmin API call, check `garmin_oauth_token_expires_at`
2. If expired (or within 5 minutes of expiry), call Garmin refresh endpoint
3. On successful refresh: update `garmin_oauth_access_token`, `garmin_oauth_refresh_token`, `garmin_oauth_token_expires_at`
4. On refresh failure: set `garmin_connected=False`, log the failure, do NOT throw to the caller — return a structured error so the task can skip gracefully

**[PORTAL VERIFY]** Confirm Garmin uses standard OAuth 2.0 refresh grant and refresh token rotation behavior.

**AC:**
- `ensure_fresh_garmin_token(athlete_id, db)` exists in `services/garmin_oauth.py`
- Expired token triggers refresh before API call
- Refresh failure sets `garmin_connected=False` — athlete must reconnect
- No API calls are made with an expired token
- Test: mock expired token → verify refresh is called before the actual API request

#### D2.3: Disconnect + data purge [F1]

| Endpoint | Method | Auth required | Description |
|---|---|---|---|
| `/v1/garmin/disconnect` | POST | Athlete | Disconnects Garmin, purges data, calls deregistration |

**Disconnect behavior (ordered):**

1. Call Garmin deregistration endpoint to notify Garmin to stop sending data for this user. **[PORTAL VERIFY]** exact endpoint URL and payload during eval environment work.
2. Clear OAuth tokens immediately: `garmin_oauth_access_token=None`, `garmin_oauth_refresh_token=None`, `garmin_oauth_token_expires_at=None`, `garmin_user_id=None`, `garmin_connected=False`
3. Delete all `GarminDay` rows for this athlete (wellness data is sourced entirely from Garmin — no other provider)
4. Delete Activities with `provider="garmin"` **on explicit disconnect only**. On token expiry/auth failure (soft disconnect), retain activities — they still represent real training data. On explicit athlete-initiated disconnect, delete.
5. The existing GDPR deletion route (`DELETE /v1/gdpr/delete`) must be extended to include `GarminDay` deletion and Garmin-provider activity deletion for the targeted athlete.

**Idempotency:** Calling disconnect multiple times is safe. If tokens are already null, skip the deregistration call. If `GarminDay` rows don't exist, skip. Return 200 in all cases.

**AC:**
- `POST /v1/garmin/disconnect` returns 200
- After disconnect: `garmin_connected=False`, all four token fields are null
- After disconnect: `GarminDay` rows for the athlete are absent from the database
- After disconnect: Activities with `provider="garmin"` are absent for the athlete
- After disconnect: calling disconnect again returns 200 (idempotent)
- `DELETE /v1/gdpr/delete` includes `GarminDay` and Garmin-provider activities in purge scope
- Test: connect athlete → create `GarminDay` rows → disconnect → verify rows absent → disconnect again → verify 200

---

### D3: Adapter Layer

**`services/garmin_adapter.py`** — single file responsible for all Garmin API field translations. If Garmin renames a field, only this file changes.

#### D3.1: Activity adapter

`adapt_activity_summary(raw: dict) -> dict` — maps Garmin Activity Summary payload to internal `Activity` model field names.

**Field translations:**

| Garmin field | Internal field | Transform |
|---|---|---|
| `SummaryId` | `external_activity_id` | string as-is |
| `StartTimeInSeconds` | `start_time` | Unix → `datetime` UTC |
| `StartTimeOffsetInSeconds` | (used for local time only) | Add to `start_time` for local |
| `DurationInSeconds` | `duration_s` | int |
| `ActivityType` | `sport` | mapping: RUNNING/TRAIL_RUNNING/TREADMILL_RUNNING/INDOOR_RUNNING → `"run"`, all others → `None` (skip) |
| `ActivityName` | `name` | string |
| `AverageHeartRateInBeatsPerMinute` | `avg_hr` | int |
| `MaxHeartRateInBeatsPerMinute` | `max_hr` | int |
| `AverageSpeedInMetersPerSecond` | `average_speed` | float |
| `DistanceInMeters` | `distance_m` | float |
| `TotalElevationGainInMeters` | `total_elevation_gain` | float |
| `AverageRunCadenceInStepsPerMinute` | `avg_cadence` | int |
| `MaxRunCadenceInStepsPerMinute` | `max_cadence` | int |
| `AverageStrideLength` | `avg_stride_length_m` | float (meters) |
| `AverageGroundContactTime` | `avg_ground_contact_ms` | float (ms) |
| `AverageGroundContactTimeBalance` | `avg_ground_contact_balance_pct` | float |
| `AverageVerticalOscillation` | `avg_vertical_oscillation_cm` | float (cm) |
| `AverageVerticalRatio` | `avg_vertical_ratio_pct` | float |
| `AveragePowerInWatts` | `avg_power_w` | int |
| `MaxPowerInWatts` | `max_power_w` | int |
| `AverageGradeAdjustedPaceInMinutesPerMile` | `avg_gap_min_per_mile` | float |
| `TotalDescentInMeters` | `total_descent_m` | float |
| `AerobicTrainingEffect` | `garmin_aerobic_te` | float |
| `AnaerobicTrainingEffect` | `garmin_anaerobic_te` | float |
| `TrainingEffectLabel` | `garmin_te_label` | string |
| `SelfEvaluationFeel` | `garmin_feel` | string |
| `SelfEvaluationPerceivedEffort` | `garmin_perceived_effort` | int |
| `BodyBatteryImpact` | `garmin_body_battery_impact` | int |
| `MovingTimeInSeconds` | `moving_time_s` | int |
| `MaxSpeedInMetersPerSecond` | `max_speed` | float |
| `ActiveKilocalories` | `active_kcal` | int |
| `Manual` | `source` | `True → "garmin_manual"`, `False → "garmin"` |
| — | `provider` | hardcoded `"garmin"` |

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

### D4: Webhook Endpoint [H4]

`POST /v1/garmin/webhook` — receives push notifications from Garmin.

#### D4.1: Webhook security

**Requirement:** Every incoming webhook request must be authenticated before any data is processed.

**Implementation (in order of preference):**

1. **[PORTAL VERIFY first]** If Garmin provides HMAC-SHA256 signature: verify signature using the shared secret stored in environment variable `GARMIN_WEBHOOK_SECRET`. Mirror the pattern in `apps/api/services/strava_webhook.py` (`verify_webhook_signature`).
2. **If Garmin provides a shared secret header:** Verify the header value matches `GARMIN_WEBHOOK_SECRET`.
3. **If Garmin provides neither:** Implement IP allowlisting — accept requests only from Garmin's documented IP ranges. **[PORTAL VERIFY]** IP range list.

Any request that fails authentication returns `401` immediately. No data is processed. No task is enqueued. This is fail-closed.

**AC:**
- `POST /v1/garmin/webhook` with invalid/missing signature returns `401`
- `POST /v1/garmin/webhook` with valid signature returns `200` and enqueues processing task
- Test: send request with correct HMAC → 200; send with wrong HMAC → 401; send with no signature → 401
- `GARMIN_WEBHOOK_SECRET` is in `.env.example` with a placeholder value — never hardcoded

#### D4.2: Webhook dispatch

On authenticated webhook receipt:
1. Return `200` immediately (Garmin expects fast acknowledgement)
2. Enqueue Celery task `process_garmin_webhook_task` with payload
3. Task processes activity or health data asynchronously

**AC:**
- Webhook endpoint returns `200` within 500ms regardless of payload size
- All processing happens in Celery worker, not in the webhook handler
- Failed task processing is logged with full payload for debugging
- Duplicate webhook deliveries (same `SummaryId`) are deduplicated — task checks if record exists before processing

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

#### D5.3: Running dynamics eval verification [M2]

The discovery document states that running dynamics (stride length, GCT, vertical oscillation, vertical ratio, power) are "confirmed native in JSON." This was inferred from portal screenshots, not a live API call.

**Before running dynamics columns are populated in production:**

In the eval environment, call the Activity Details endpoint for a real Garmin activity and confirm the response JSON contains: `StrideLength`, `GroundContactTime`, `GroundContactBalance`, `VerticalOscillation`, `VerticalRatio`, `PowerInWatts`.

**If confirmed:** Populate the Activity model columns as specified in D1.2. Mark M2 resolved.

**If not present in JSON (only in FIT binary):** Defer running dynamics columns to Tier 2. Set columns nullable, leave unpopulated. Document the finding. Do not block Phase 2 ship.

**AC:**
- Eval verification step is documented in a comment at the top of `garmin_adapter.adapt_activity_stream()`
- Result of verification (confirmed / deferred) is noted before Phase 2 merges to main

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

`garmin_initial_backfill_task(athlete_id)` — triggered automatically after successful OAuth connect (callback success).

**Backfill depth: 90 days [M4]**

Rationale: 90 days is the correlation engine's analysis window. Data older than 90 days does not contribute to current correlation findings. This is consistent across all data sources.

**Backfill scope:**
- Activities: last 90 days of running activities from Activity API
- Health/wellness: last 90 days of `GarminDay` records (daily summary, sleep, HRV)

**Backfill behavior:**
- Runs as background Celery task after connect — does not block OAuth callback
- Uses same deduplication logic as live sync (D5.2)
- Rate-limit aware: backs off if Garmin returns 429
- Idempotent: safe to re-run (upsert on `GarminDay`, dedup on Activities)

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
| `test_no_duplicate_created_on_garmin_strava_overlap` | Same as above. | `Activity.objects.count()` unchanged after Garmin ingest |
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
- `test_webhook_invalid_signature_returns_401` — wrong HMAC → 401
- `test_webhook_valid_signature_returns_200` — correct HMAC → 200
- `test_token_refresh_on_expiry` — expired token triggers refresh before API call
- `test_token_refresh_failure_sets_disconnected` — refresh fails → `garmin_connected=False`

### Category 2: Integration Tests

- `test_garmin_oauth_connect_flow` — full OAuth: auth-url → callback → status connected
- `test_garmin_disconnect_clears_tokens` — disconnect → tokens null, `garmin_connected=False`
- `test_garmin_disconnect_purges_garmin_day_rows` — disconnect → `GarminDay` rows absent
- `test_garmin_disconnect_purges_provider_garmin_activities` — explicit disconnect → Garmin activities absent
- `test_garmin_disconnect_idempotent` — disconnect twice → 200 both times
- `test_gdpr_delete_includes_garmin_day` — GDPR delete → `GarminDay` rows absent
- `test_garmin_day_upsert` — insert daily summary → insert sleep for same date → single row with merged fields
- `test_garmin_day_unique_constraint` — cannot insert two rows for same (athlete_id, calendar_date)
- `test_sleep_calendar_date_join_wakeup_day` — sleep on Friday night (`calendar_date=Saturday`) joins correctly to Saturday activity [L1]
- `test_backfill_idempotent` — run twice → same row count [D7]
- `test_dedup_two_thresholds_live_vs_takeout` — takeout import then live webhook for same activity → single row [M1]

### Category 3: Provider Precedence Tests [F2]

All 7 tests listed in Section 4.

### Category 4: Contract Tests (regression locks)

- `test_garmin_adapter_is_only_file_with_garmin_field_names` — source inspection: Garmin field names (`StartTimeInSeconds`, `SummaryId`, etc.) appear ONLY in `garmin_adapter.py`, nowhere else in the codebase
- `test_activity_dedup_has_no_garmin_field_names` — source inspection of `activity_deduplication.py` [H2]
- `test_garmin_day_model_exists_no_garmin_sleep_or_hrv` — `GarminDay` model exists; no `GarminSleep`, `GarminHRV` models [H3]
- `test_training_api_never_called` — no import of Training API client anywhere in codebase
- `test_webhook_secret_not_hardcoded` — `GARMIN_WEBHOOK_SECRET` read from env, never hardcoded

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
D1 → D2 → D3 → D4 → D5 → D6 → D7 → D8
```

Rationale: D1 (models) unblocks everything. D2 (OAuth) unblocks sync. D3 (adapter) unblocks D4+D5+D6. D7 (backfill) depends on D5+D6. D8 (attribution) can run in parallel with D7.

### Step 3: Eval environment verification

Before any production code is written:
- Verify Activity Details endpoint returns running dynamics fields in JSON [M2]
- Verify Garmin webhook authentication mechanism [H4]
- Verify OAuth token field names and refresh flow [M3]
- Verify Garmin deregistration endpoint URL and payload [F1]
- Confirm exact OAuth scope names

Document all findings in a brief eval verification note. Update the adapter and AC if anything diverges from discovery assumptions.

### Step 4: 30-day notice

Founder sends display format notice to `connect-support@developer.garmin.com`. Builder provides mockup package. 30-day clock starts. Development continues on feature branch.

### Step 5: Merge gate

`feature/garmin-oauth` may only merge to `main` when:

- [ ] All tests pass (full backend suite, no new failures)
- [ ] 30-day notice period elapsed and acknowledged [M5]
- [ ] Eval environment verification complete [M2]
- [ ] Attribution component reviewed against Garmin brand guidelines [D8]
- [ ] No references to `garmin_service.py` remain in codebase (retired)
- [ ] `garmin_username` and `garmin_password_encrypted` columns absent from production schema
- [ ] Garmin deregistration endpoint integrated and tested [F1]
- [ ] Production containers healthy on `feature/garmin-oauth` test deploy

---

## 7. Must-Fix Traceability (Gate 2 → AC)

| # | Gate 2 Item | Addressed In |
|---|---|---|
| 1 | Use `GarminDay` consistently [H3] | D1.3 — `GarminDay` is the sole model; no `GarminSleep`/`GarminHRV` |
| 2 | Separate existing vs new Activity columns [H1] | D1.2 — explicit table with "existing" vs "new" columns and migration name |
| 3 | Dedup post-adapter on internal field names [H2] | D3.3 — adapter contract + contract tests |
| 4 | Webhook security [H4] | D4.1 — HMAC preferred, IP allowlist fallback, fail-closed |
| 5 | Backfill depth 90 days [M4] | D7 — 90 days specified with rationale |
| 6 | 30-day notice as hard rollout gate [M5] | Gate 0A — calendar dependency, merge blocked until cleared |
| 7 | Running dynamics JSON verification [M2] | D5.3 — eval environment verification step required |
| 8 | Sleep CalendarDate wakeup-day join test [L1] | D6.2 — explicit test scenario specified |
| 9 | Disconnect endpoint + idempotent purge [F1] | D2.3 — disconnect behavior specified, idempotency required |
| 10 | Provider precedence contract tests [F2] | Section 4 — 7 named tests at dedup-time and read-time |

---

*This document is the input to Gate 5 advisor review. No code is written until Gate 5 and Gate 6 clear.*
