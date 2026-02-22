# Garmin Connect Developer Program — API Discovery

**Date:** February 19, 2026
**Author:** Builder (Phase 2A research)
**Status:** DRAFT — Awaiting supervisor review and founder sign-off
**Sources:** Garmin developer portal public docs, MyDataHelps field-level documentation (derived from the same Garmin developer program API spec), existing StrideIQ codebase

---

## Research method

The detailed API endpoint specification lives behind the developer portal login (`apis.garmin.com/tools/endpoints`). What is publicly available:
- High-level API descriptions at `developer.garmin.com/gc-developer-program/`
- Field-level documentation inferred from MyDataHelps, which integrates the same Garmin Connect developer program APIs and publishes field schemas publicly

Items marked **[PORTAL VERIFY]** require the founder to confirm in the portal before the AC document is written.

---

## 1. API Inventory

The Garmin Connect Developer Program provides five APIs, grouped by direction:

### 1A. Receive APIs (Garmin → StrideIQ)

| API | Description | Relevant to StrideIQ |
|-----|-------------|----------------------|
| **Activity API** | Full activity data for 30+ activity types | Yes — primary running data |
| **Health API** | All-day health metrics: sleep, stress, body battery, HRV, steps, HR | Yes — wellness correlation data |
| **Women's Health API** | Menstrual cycle tracking and pregnancy | No |

### 1B. Push APIs (StrideIQ → Garmin)

| API | Description | Relevant to StrideIQ |
|-----|-------------|----------------------|
| **Training API** | Publish structured workouts and training plans to user devices | Compliance question — see §5 |
| **Courses API** | Publish GPS courses to compatible devices | No — out of scope |

### Integration architecture (applies to all receive APIs)

- **Auth:** OAuth 2.0
- **Format:** REST + JSON
- **Integration model:** Ping/pull OR push (developer's choice)
  - Push: Garmin sends data to StrideIQ webhook on each sync
  - Ping/pull: Garmin sends a ping notification, StrideIQ pulls data
- **Onboarding tools:** Evaluation environment, sample data, backfill capability
- **Scopes:** [PORTAL VERIFY] — exact scope names not in public docs

---

## 2. Data Field Mapping

### 2A. Activity API

**Model: Activity Summary** (one record per activity)

| Garmin field | Type | Maps to | Notes |
|---|---|---|---|
| `SummaryId` | String | `external_activity_id` | Unique per summary |
| `ActivityId` | String | (secondary ref) | Garmin Connect activity ID |
| `StartTimeInSeconds` | Unix timestamp | `start_time` | UTC; combine with `StartTimeOffsetInSeconds` for local |
| `StartTimeOffsetInSeconds` | Integer (seconds) | (timezone offset) | Add to start time for local time |
| `DurationInSeconds` | Integer | `duration_s` | Elapsed time |
| `ActivityType` | String enum | `sport` (mapped) | RUNNING, TRAIL_RUNNING, TREADMILL_RUNNING, CYCLING, etc. |
| `ActivityName` | String | `name` | User-assigned name |
| `AverageHeartRateInBeatsPerMinute` | Integer | `avg_hr` | — |
| `MaxHeartRateInBeatsPerMinute` | Integer | `max_hr` | — |
| `AverageRunCadenceInStepsPerMinute` | Integer | — | **New field** — not currently in Activity model |
| `MaxRunCadenceInStepsPerMinute` | Integer | — | **New field** |
| `AverageStrideLength` | Float (m) | — | **New field** — native, confirmed 1.03 m format |
| `AverageGroundContactTime` | Float (ms) | — | **New field** — confirmed 237 ms format |
| `AverageGroundContactTimeBalance` | Float (%) | — | **New field** — left/right GCT balance |
| `AverageVerticalOscillation` | Float (cm) | — | **New field** — confirmed 7.7 cm format |
| `AverageVerticalRatio` | Float (%) | — | **New field** — confirmed 7.8% format |
| `AveragePowerInWatts` | Integer | — | **New field** — confirmed 299 W avg |
| `MaxPowerInWatts` | Integer | — | **New field** — confirmed 415 W max |
| `AerobicTrainingEffect` | Float | `garmin_aerobic_te` | Store informational only — never used in StrideIQ load calculations. Garmin TE is poorly calibrated for individual athletes. StrideIQ computes its own training effect. |
| `AnaerobicTrainingEffect` | Float | `garmin_anaerobic_te` | Same — informational only |
| `TrainingEffectLabel` | String | `garmin_te_label` | Same — informational only |
| `AverageGradeAdjustedPaceInMinutesPerMile` | Float | — | **New field** — GAP |
| `MovingTimeInSeconds` | Integer | `duration_s` candidate | Separate from elapsed time |
| `TotalDescentInMeters` | Float | — | **New field** |
| `MinElevationInMeters` | Float | — | **New field** |
| `MaxElevationInMeters` | Float | — | **New field** |
| `BodyBatteryImpact` | Integer | — | **New field** — net body battery drain from this activity (e.g. -14) |
| `AverageSweatLossInMilliliters` | Float | — | **New field** — estimated sweat loss |
| `IntensityMinutesModerate` | Integer | — | **New field** — WHO intensity minutes |
| `IntensityMinutesVigorous` | Integer | — | **New field** |
| `SelfEvaluationFeel` | String | `garmin_feel` | Import as athlete-recorded data. **Product note:** Garmin does not surface this data back to the athlete in any useful way, so athletes often click through it without genuine engagement. Import if present, but do not treat as high-fidelity signal. StrideIQ should build its own RPE/feel capture if this data is important to the coaching model — one that closes the loop by showing the athlete how their ratings correlate with outcomes. |
| `SelfEvaluationPerceivedEffort` | Integer | `garmin_perceived_effort` | Same caveat — import if present, low trust as a reliable input. |
| `AverageSpeedInMetersPerSecond` | Float | `average_speed` | Same units as Strava |
| `MaxSpeedInMetersPerSecond` | Float | — | **New field** |
| `AveragePaceInMinutesPerKilometer` | Float | (derived from speed) | Redundant if speed stored |
| `ActiveKilocalories` | Integer | — | **New field** (active only, not BMR) |
| `DeviceName` | String | — | Good for attribution |
| `DistanceInMeters` | Float | `distance_m` | Same units as existing model |
| `TotalElevationGainInMeters` | Float | `total_elevation_gain` | Same units as existing model |
| `TotalElevationLossInMeters` | Float | — | **New field** |
| `StartingLatitudeInDegree` | Float | — | Start GPS (existing model has no GPS) |
| `StartingLongitudeInDegree` | Float | — | Start GPS |
| `Steps` | Integer | — | Total steps for activity |
| `IsParent` / `ParentSummaryId` | Bool/String | — | Multi-sport handling |
| `Manual` | Bool | `source` | If true, `source="garmin_manual"` |
| `DeviceName` | String | — | For attribution display |

**Activity type mapping (Garmin → StrideIQ `sport`):**

| Garmin `ActivityType` | StrideIQ `sport` |
|---|---|
| `RUNNING` | `run` |
| `TRAIL_RUNNING` | `run` (subtype TBD) |
| `TREADMILL_RUNNING` | `run` |
| `INDOOR_RUNNING` | `run` |
| All others | skip (or store separately) |

**Model: Activity Details Summary** (second-by-second, one record per activity)

This is the stream data equivalent — maps to StrideIQ's existing stream storage (ADR-063).

| Garmin field | Type | Maps to |
|---|---|---|
| `StartTimeInSeconds` | Unix timestamp | stream timestamp |
| `LatitudeInDegree` | Float | GPS lat stream |
| `LongitudeInDegree` | Float | GPS lng stream |
| `ElevationInMeters` | Float | altitude stream |
| `AirTemperatureCelcius` | Float | `temperature_f` (convert) |
| `HeartRate` | Integer | HR stream |
| `SpeedMetersPerSecond` | Float | velocity stream |
| `StepsPerMinute` | Integer | cadence stream |
| `StrideLength` | Float (m) | stride length stream — native, confirmed meters |
| `GroundContactTime` | Float (ms) | GCT stream — running dynamics, in JSON (not FIT-only) |
| `GroundContactBalance` | Float (%) | left/right GCT balance stream |
| `VerticalOscillation` | Float (cm) | vertical oscillation stream — confirmed cm units |
| `VerticalRatio` | Float (%) | vertical ratio stream — confirmed 7.5% format |
| `TotalDistanceInMeters` | Float | distance stream |
| `PowerInWatts` | Integer | power stream — confirmed 278 W format |

**Model: Activity Laps** — lap splits, maps to `ActivitySplit` model

**FIT file access:** Raw FIT binary also available for each activity. **Not needed for Phase 2** — JSON stream data covers all current StrideIQ use cases including full running dynamics (stride length, ground contact time, vertical oscillation, vertical ratio — all confirmed native in JSON from portal). FIT file is lower priority; defer unless a specific metric emerges that isn't in JSON. **[PORTAL VERIFY]** whether FIT access requires a separate scope.

---

### 2B. Health API

#### Daily Summary (one record per day)

| Garmin field | Type | StrideIQ mapping |
|---|---|---|
| `CalendarDate` | `yyyy-mm-dd` | New `GarminDay.calendar_date` |
| `RestingHeartRateInBeatsPerMinute` | Integer | `GarminDay.resting_hr` |
| `AverageStressLevel` | Integer (1-100, or -1) | `GarminDay.avg_stress` |
| `MaxStressLevel` | Integer | `GarminDay.max_stress` |
| `StressQualifier` | String enum | `GarminDay.stress_qualifier` |
| `Steps` | Integer | `GarminDay.steps` |
| `ActiveTimeInSeconds` | Integer | `GarminDay.active_time_s` |
| `ActiveKilocalories` | Integer | `GarminDay.active_kcal` |
| `ModerateIntensityDurationInSeconds` | Integer | `GarminDay.moderate_intensity_s` |
| `VigorousIntensityDurationInSeconds` | Integer | `GarminDay.vigorous_intensity_s` |
| `MinHeartRateInBeatsPerMinute` | Integer | `GarminDay.min_hr` |
| `MaxHeartRateInBeatsPerMinute` | Integer | `GarminDay.max_hr` |
| `timeOffsetHeartRateSamples` | Map[offset→bpm] | (raw JSONB, not parsed in Phase 2) |

**What's new vs Strava:** Strava provides none of this. Every field above is net-new data for the correlation engine.

#### Sleep Summary (one record per sleep event)

| Garmin field | Type | StrideIQ mapping |
|---|---|---|
| `CalendarDate` | `yyyy-mm-dd` | `GarminSleep.calendar_date` |
| `StartTimeInSeconds` | Unix timestamp | `GarminSleep.start_time` |
| `DurationInSeconds` | Integer | `GarminSleep.total_sleep_s` |
| `DeepSleepDurationInSeconds` | Integer | `GarminSleep.deep_s` |
| `LightSleepDurationInSeconds` | Integer | `GarminSleep.light_s` |
| `RemSleepInSeconds` | Integer | `GarminSleep.rem_s` |
| `AwakeDurationInSeconds` | Integer | `GarminSleep.awake_s` |
| `OverallSleepScoreValue` | Integer (0-100) | `GarminSleep.score` |
| `OverallSleepScoreQualifierKey` | EXCELLENT/GOOD/FAIR/POOR | `GarminSleep.score_qualifier` |
| `Validation` | String enum | `GarminSleep.validation` |
| `SleepScores` | Map of per-dimension scores | (JSONB) |
| `sleepLevelsMap` | Map of stage→time ranges | (JSONB — for future visualisation) |
| `TimeOffsetSleepRespiration` | Map[offset→breaths/min] | (raw JSONB) |
| `TimeOffsetSleepSpo2` | Map[offset→SpO2%] | (raw JSONB, device-dependent) |

**Sleep `CalendarDate` edge case:** Garmin assigns `CalendarDate` to the morning of the wake-up day, not the night the athlete went to sleep. A run on Saturday that follows sleep on Friday night will have `CalendarDate = Saturday`. When joining sleep data to activity data, join on `GarminDay.calendar_date = activity.start_time::date` (the wakeup/activity day), not the night the athlete went to bed. This must be reflected in the data model and any correlation queries.

**What's new vs Strava:** Strava has no sleep data. Sleep staging is entirely new. The existing correlation engine already references sleep duration (was empty for Strava-only users); Garmin fills this.

#### HRV Summary (one record per night)

| Garmin field | Type | StrideIQ mapping |
|---|---|---|
| `CalendarDate` | `yyyy-mm-dd` | `GarminHRV.calendar_date` |
| `LastNightAvg` | Integer (ms) | `GarminHRV.avg_hrv_ms` |
| `LastNight5MinHigh` | Integer (ms) | `GarminHRV.five_min_high_hrv_ms` |
| `HrvValues` | Map[offset→ms] | (raw JSONB — for future trend visualisation) |

**Note:** This is the **overnight summary HRV** (rMSSD equivalent), not beat-to-beat. The enhanced beat-to-beat interval data requires a commercial license fee. **[PORTAL VERIFY]** cost and applicability. For Phase 2, overnight summary is sufficient for the correlation engine.

**What's new vs Strava:** Strava has no HRV. The existing unofficial Garmin code was pulling `rmssd` and `sdnn` — the official API provides `LastNightAvg` which is Garmin's overnight HRV metric (methodology: proprietary, likely rMSSD-based). Field name differs.

#### Stress Detail Summary (one record per day)

| Garmin field | Type | StrideIQ mapping |
|---|---|---|
| `CalendarDate` | `yyyy-mm-dd` | `GarminDay.calendar_date` (augments Daily Summary) |
| `TimeOffsetStressLevelValues` | Map[offset→1-100] | `GarminDay.stress_samples` (JSONB) |
| `TimeOffsetBodyBatteryValues` | Map[offset→level] | `GarminDay.body_battery_samples` (JSONB) |
| `BodyBatteryDynamicFeedbackEvent.BodyBatteryLevel` | VERY_LOW/LOW/MODERATE/HIGH | `GarminDay.body_battery_current` |
| `BodyBatteryActivityEvents` | Array of {type, impact} | `GarminDay.body_battery_events` (JSONB) |

**Stress value encoding:**
- 1-100: actual stress score (1-25=rest, 26-50=low, 51-75=moderate, 76-100=high)
- -1: off wrist
- -2: large motion
- -3: not enough data
- -4: recovering from exercise
- -5: unidentified

**Body Battery events:** `SLEEP`, `RECOVERY`, `NAP`, `ACTIVITY`, `STRESS` — positive impact = charge, negative = drain.

**Phase 2 decision:** Intraday stress + body battery are valuable for the correlation engine but increase storage significantly. Recommend storing raw JSONB in Phase 2 and adding computed fields (daily avg, end-of-day body battery) in Phase 3. See §4 priority recommendation.

#### User Metrics (per-user daily calculations)

| Garmin field | Type | StrideIQ mapping |
|---|---|---|
| `CalendarDate` | `yyyy-mm-dd` | `GarminDay.calendar_date` |
| `Vo2Max` | Float | `GarminDay.vo2max` (running) |
| `Vo2MaxCycling` | Float | `GarminDay.vo2max_cycling` |
| `FitnessAge` | Integer | `GarminDay.fitness_age` |

**VO2 max note:** Garmin's VO2 max estimate is derived from outdoor running activities with GPS + HR. It updates infrequently (after qualifying runs). More reliable than generic formulas but still an estimate. Relevant for the correlation engine — can track how VO2 max trend responds to training load.

#### Epoch Summary (15-minute granularity)

Not in scope for Phase 2. Daily summaries are sufficient for the correlation engine. Epochs would be useful for identifying intraday load patterns but add significant volume.

#### Other Health API models (lower priority)

| Model | Fields | Phase 2 scope |
|---|---|---|
| Body Composition | Weight, BMI, body fat % | Deferred |
| Pulse Ox | SpO2 readings | Deferred (also available in sleep SpO2 field) |
| Blood Pressure | Systolic/diastolic | Deferred |
| Respiration | Breathing rate | Sleep respiration already in Sleep Summary |
| Skin Temp | Skin temperature variation during sleep | Deferred |
| Health Snapshot | 2-minute health session | Deferred |
| MoveIQ | Auto-detected activity (not user-initiated) | Deferred |

---

## 3. Architecture Decisions Needed

### 3A. Push vs ping/pull

**Options:**
- **Push:** Garmin sends POST to our webhook after each device sync. Near-realtime. Simpler — no polling required. Requires a publicly accessible HTTPS endpoint.
- **Ping/pull:** Garmin sends a lightweight ping, we GET the data from Garmin's endpoint. One extra round trip but same latency in practice.

**Recommendation: Push.** Simpler operational model. Strava also uses webhooks for activity updates. Consistent architecture. The droplet is already running HTTPS behind Caddy, so the webhook endpoint is trivially deployable.

**[PORTAL VERIFY]** — Confirm exact webhook payload format and whether both Activity and Health APIs support push, or only ping/pull.

### 3B. Sync frequency and latency

Data is available after the user syncs their device to Garmin Connect (via Garmin Connect mobile or USB). There is no always-on streaming — data availability depends on user sync behavior. Typical: users sync daily or on phone proximity.

**Recommendation:** Process webhooks on receipt. No polling required in push mode.

### 3C. Strava + Garmin overlap handling

When both providers are connected, the same run will appear in both:

| Scenario | Action |
|---|---|
| Same activity in Strava + Garmin | `services/activity_deduplication.py` matches on: time within **1 hour** + distance within **5%** + HR within **5 bpm** (if both present). Garmin kept as primary. |
| Garmin has activity that Strava doesn't | Ingest as `provider="garmin"` |
| Strava has activity that Garmin doesn't | Ingest as `provider="strava"` |
| User prefers one source | [Future: user preference setting] |

**Dedup thresholds (from `services/activity_deduplication.py`):** 1 hour time window, 5% distance tolerance, 5 bpm HR tolerance. Note: the file-import path (`garmin_di_connect.py`) uses tighter thresholds (120s / 1.5%) — those apply only to the takeout import, not live sync.

**Garmin-as-primary assumption:** The existing dedup service hardcodes "Garmin is primary source; Strava is fallback" — Garmin wins on conflict. **The AC document must explicitly decide whether this assumption holds**, or whether both providers are treated as equal peers with the athlete choosing a preferred source. The assumption is reasonable (Garmin is native device data) but should be a named decision, not an inherited default.

**Display attribution:** Activities sourced from Garmin display Garmin attribution. Activities from Strava display Strava attribution. The `provider` field already exists on the Activity model.

**Garmin-native advantage:** Cadence from Garmin's footpod is more accurate than Strava's estimate. Elevation from barometric altimeter (more accurate than GPS-derived). These may differ slightly from Strava values for the same activity — display the data from the sourcing provider.

### 3D. New data storage: `GarminDay` model

The wellness data (sleep, HRV, stress, body battery, daily metrics) has no current home in the StrideIQ data model. Options:

**Option A:** Extend existing `DailySummary` or similar model.
**Option B:** New `GarminDay` table — one row per (athlete, calendar_date), containing all Garmin wellness fields.
**Option C:** Separate tables per data type (GarminSleep, GarminHRV, GarminStress).

**Recommendation: Option B** — single `GarminDay` table for Phase 2. Simpler join patterns, lower query complexity, easier to add columns as more Garmin APIs are enabled. If data volume becomes a concern (intraday samples), move samples to a separate `GarminDaySamples` table with JSONB columns.

**Proposed `GarminDay` fields (Phase 2 scope):**
```
calendar_date       DATE        — primary key component
athlete_id          UUID FK     — primary key component
resting_hr          INTEGER     — from Daily Summary
avg_stress          INTEGER     — from Daily Summary (-1 if insufficient)
max_stress          INTEGER     — from Daily Summary
stress_qualifier    TEXT        — calm/balanced/stressful/very_stressful
steps               INTEGER     — from Daily Summary
active_time_s       INTEGER     — from Daily Summary
active_kcal         INTEGER     — from Daily Summary
moderate_intensity_s INTEGER    — from Daily Summary
vigorous_intensity_s INTEGER    — from Daily Summary
sleep_total_s       INTEGER     — from Sleep Summary
sleep_deep_s        INTEGER     — from Sleep Summary
sleep_light_s       INTEGER     — from Sleep Summary
sleep_rem_s         INTEGER     — from Sleep Summary
sleep_awake_s       INTEGER     — from Sleep Summary
sleep_score         INTEGER     — from Sleep Summary (0-100)
sleep_score_qualifier TEXT      — from Sleep Summary
sleep_validation    TEXT        — from Sleep Summary
hrv_overnight_avg   INTEGER     — from HRV Summary (ms)
hrv_5min_high       INTEGER     — from HRV Summary (ms)
vo2max              FLOAT       — from User Metrics (nullable; updates infrequently)
body_battery_end    INTEGER     — end-of-day body battery from Stress Detail
stress_samples      JSONB       — TimeOffsetStressLevelValues (raw)
body_battery_samples JSONB      — TimeOffsetBodyBatteryValues (raw)
garmin_summary_id   TEXT        — SummaryId for dedup
inserted_at         TIMESTAMPTZ
updated_at          TIMESTAMPTZ
```

Unique constraint: `(athlete_id, calendar_date)`

### 3E. Athlete model changes

Replace existing unofficial Garmin fields with OAuth 2.0 fields:

**Remove (unofficial library fields):**
- `garmin_username`
- `garmin_password_encrypted`

**Add:**
- `garmin_oauth_access_token` (Text, encrypted) — short-lived access token
- `garmin_oauth_refresh_token` (Text, encrypted) — long-lived refresh token
- `garmin_oauth_token_expires_at` (DateTime)
- `garmin_user_id` (Text) — Garmin's user ID from OAuth
- `garmin_connected` (Boolean) — already exists
- `last_garmin_sync` (DateTime) — already exists
- `garmin_sync_enabled` (Boolean) — already exists

**[PORTAL VERIFY]** — Confirm token field names and whether Garmin uses standard OAuth2 refresh flow.

### 3F. Abstraction layer (compliance requirement — Section 7)

The compliance doc requires an adapter pattern so API changes don't propagate through the codebase.

**Proposed structure (follows Strava pattern):**
```
routers/garmin.py           — OAuth endpoints (auth-url, callback, disconnect, status)
services/garmin_adapter.py  — Maps Garmin API response fields → internal models
tasks/garmin_tasks.py       — Celery tasks (webhook processing, backfill)
services/garmin_webhooks.py — Webhook signature verification + dispatch
```

All field translations go through `garmin_adapter.py`. If Garmin renames a field, one file changes.

### 3G. Token security

OAuth tokens are encrypted at rest (same pattern as Strava). Tokens stored in `garmin_oauth_access_token` and `garmin_oauth_refresh_token` on the Athlete model, encrypted with the application secret key. Not committed to code or `.env` files.

### 3H. Training API — out of scope

The Training API allows pushing workout plans to Garmin devices.

**Compliance doc Section 4.6:** Anything pushed to Garmin becomes Garmin's property — they can copy, modify, distribute, sublicense, and use it for any purpose with no obligation to StrideIQ. Pushing StrideIQ-generated training plans or coaching insights to Garmin means giving Garmin unlimited rights to that data.

**Decision (founder):** Training API is permanently out of scope. StrideIQ receives data from Garmin; it does not push data to Garmin. This is not a deferral — it is a hard boundary based on the compliance agreement.

---

## 4. Priority Recommendation

### Tier 1 — Phase 2 ship target (MVP Garmin integration)

These deliver the highest product value and unblock the correlation engine for Garmin users.

| Component | What it enables |
|---|---|
| OAuth 2.0 flow | Replaces unsafe username/password auth |
| Activity API sync | Running data from Garmin device without Strava |
| Sleep Summary | Sleep staging — net-new for correlation engine |
| HRV Summary | Overnight HRV — net-new for correlation engine |
| Daily Summary | Resting HR, stress, steps — net-new for correlation engine |

**Data payload for correlation engine after Tier 1:**
- Activities: same as today (from Garmin instead of or in addition to Strava)
- Sleep: total duration + staging (deep/light/REM) + quality score
- HRV: overnight average + 5-min high
- Daily wellness: resting HR, stress level, steps, active calories

**This fills the single largest gap in StrideIQ's correlation engine:** Strava-only users have activities but no wellness context. Every Garmin user provides daily wellness data that immediately feeds the correlation engine.

### Tier 2 — After Tier 1 is stable

| Component | What it enables |
|---|---|
| Stress Detail + Body Battery | Intraday stress and recovery context |
| User Metrics (VO2 max) | VO2 max trend tracking |
| Epoch summaries | 15-minute activity granularity |

### Deferred

| Component | Why deferred |
|---|---|
| Training API | Out of scope permanently — compliance Section 4.6 IP exposure |
| Women's Health API | Out of scope |
| Courses API | Out of scope |
| Beat-to-beat HRV | Commercial license required — verify cost |
| Body composition, Blood pressure, Pulse Ox | Low product value relative to implementation cost |

---

## 5. Compliance Mapping

| Compliance item | Status |
|---|---|
| AI consent (Section 15.10) | Cleared — Phase 1 shipped |
| Attribution on Garmin data screens | Required — build `GarminBadge` component |
| 30-day display format notice | Required before any new visualisation goes live |
| No write-back to Garmin | Training API out of scope permanently — compliance Section 4.6 |
| Abstraction layer (Section 3.2) | Designed — `garmin_adapter.py` |
| Tokens encrypted at rest | Plan confirmed — same as Strava |
| No reverse engineering | Official API only — existing unofficial code retired |

**30-day notice requirement:** Before Phase 2 ships to production, send notice to `connect-support@developer.garmin.com` with mockups of:
- Any screen displaying Garmin-sourced activities
- Any screen displaying Garmin wellness data (if new UI components added)

Existing visualisations (Run Shape Canvas, MiniPaceChart, Training Load) may need retroactive notice if Garmin data feeds them — **[FOUNDER: flag this for the pre-launch checklist]**.

---

## 6. Open Items

Items that affect architecture decisions are true AC blockers. Items discoverable during evaluation environment implementation are not blockers — they get resolved while building.

### 6A. Architecture blockers

None. Both candidates resolve cleanly:
- **Health API push vs ping/pull:** AC written as "push preferred, ping/pull fallback." Adapter pattern absorbs the difference. One implementation path adds a polling task; architecture unchanged.
- **Beat-to-beat HRV cost:** Overnight summary HRV is Phase 2 scope. Beat-to-beat is Tier 2 or later. If cost is prohibitive, it's never built. AC does not promise it.

### 6B. Implementation details (resolve during eval environment work)

These are standard OAuth/webhook implementation questions. They don't change the architecture — they're discovered and handled while building against the evaluation environment.

| # | Item |
|---|---|
| 1 | Exact OAuth 2.0 scope names |
| 2 | Webhook payload format and envelope structure |
| 3 | Webhook authentication mechanism (HMAC / shared secret) |
| 4 | Rate limits per user per day |
| 5 | Backfill depth limit |
| 6 | Data latency post-device-sync |
| 7 | FIT file access — separate scope required? |

### 6C. Disconnect / data deletion flow (must be in AC)

The discovery document covers OAuth connect but not the reverse. The AC document must specify:

1. **Garmin deregistration endpoint:** The developer agreement likely requires calling a Garmin-provided deregistration endpoint when an athlete disconnects StrideIQ from their Garmin account. This notifies Garmin to stop sending data for that user. **[PORTAL VERIFY]** exact endpoint and required payload during eval environment work.

2. **StrideIQ data purge on disconnect:** When an athlete disconnects Garmin, StrideIQ must decide what to delete:
   - `GarminDay` records (wellness data) — sourced entirely from Garmin, no other provider — purge on disconnect
   - Activities with `provider="garmin"` — purge or retain? If the athlete reconnects, activities would be re-synced. Recommend purge on explicit disconnect; retain on token expiry/error (soft disconnect).
   - OAuth tokens — always purge immediately on disconnect

3. **GDPR "right to erasure" interaction:** If an athlete requests full data deletion (`DELETE /v1/gdpr/delete`), all Garmin-sourced data must be included. The existing GDPR deletion flow must be extended to cover `GarminDay` and Garmin-provider activities.

4. **Strava pattern reference:** `POST /v1/strava/disconnect` clears tokens but does not currently purge activity data. The Garmin disconnect flow should make an explicit decision about activity data — and that decision should be documented in the AC, not left as an implementation default.

---

## 7. Existing Code Assessment

### `services/garmin_service.py` — retire

Uses `python-garminconnect` (unofficial library, username/password auth). This library:
- Scrapes the Garmin Connect web app
- Violates Section 5.2(j) of the developer agreement (no scraping)
- Violates Section 5.2(i) (no reverse engineering)
- Is technically a compliance violation that Phase 2 must correct

**Action:** Delete `garmin_service.py` and all references. Replace with official OAuth flow. Retire `garmin_username` and `garmin_password_encrypted` fields from Athlete model (via Alembic migration — remove columns, replace with OAuth token fields).

### `services/provider_import/garmin_di_connect.py` — keep, archive

This handles the Garmin takeout export format (JSON file import). It's a different use case (historical data import, not live sync) and does not use the unofficial library. It can coexist with the OAuth integration.

**Action:** Keep as-is. Route to `source="garmin_import"` on Activity. No compliance issue.

---

## 8. What Strava Does That Garmin Does Not

| Strava-only capability | StrideIQ impact |
|---|---|
| Segment efforts (KOM, CR, PR) | Not used by StrideIQ |
| Best efforts (automatic from Strava DB) | Not used by StrideIQ |
| Social features (kudos, comments) | Not used by StrideIQ |
| Gear tracking (shoe mileage) | Not used by StrideIQ |

StrideIQ does not use any Strava-exclusive features. The integration value from Strava is purely activity data — and Garmin provides equivalent (or superior) activity data natively.

**Implication:** A Garmin-only user loses nothing important in StrideIQ. A Strava-only user continues to work as today.

---

## Summary for supervisor review

**What we know (from public docs + portal screenshots):**
- 5 APIs: Activity, Health, Women's Health, Training, Courses
- Full field schema for Activity summary, Activity Details streams (second-by-second), Sleep, HRV, Daily, Stress/Body Battery, User Metrics
- Running dynamics (stride length, GCT, vertical oscillation, vertical ratio, power) confirmed native in JSON — no FIT parsing needed
- Units confirmed from portal screenshots: stride length in meters, vertical oscillation in cm, GCT in ms
- Dedup thresholds: `activity_deduplication.py` uses 1 hour / 5% / 5 bpm; Garmin-as-primary is an existing assumption the AC must explicitly confirm
- Sleep `CalendarDate` is wakeup day (morning), not the night before — join logic must account for this
- Training Effect: store informational-only, never used in StrideIQ load calculations (founder decision)
- Self evaluation (feel/RPE): import if present, low fidelity — athlete disengagement documented
- Training API: out of scope permanently — compliance Section 4.6 IP exposure (founder decision)
- Push architecture preferred; `GarminDay` model is the right home for wellness data
- Existing unofficial `garmin_service.py` must be retired — active compliance violation

**Architecture blockers before AC:** None. Both candidates resolved — see §6A.

**Implementation details (resolve during eval environment work):**
OAuth scope names, webhook payload format, auth mechanism, rate limits, backfill depth, data latency, beat-to-beat HRV cost.

**Recommended Phase 2 scope:** OAuth 2.0 + Activity API + Sleep + HRV + Daily wellness (Tier 1). Everything else deferred.
