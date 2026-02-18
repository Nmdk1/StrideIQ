# Garmin Connect Developer Program — API Reference

**Source documents:** Start Guide v1.2, Activity API v1.2.4, Health API v1.2.3, OAuth2 PKCE Spec, OAuth Migration Guide, License Agreement Rev C.
**Status:** Evaluation key. Production key requires technical + UX review.
**Support:** connect-support@developer.garmin.com

---

## 1. Architecture Overview

Garmin uses a **webhook-based, server-to-server** architecture. No client-side API calls allowed.

Two delivery modes (choose one per summary type):
- **Push** — Garmin POSTs full JSON data directly to your endpoint
- **Ping/Pull** — Garmin POSTs a notification with a `callbackURL`; you fetch data from that URL

**Push is recommended for StrideIQ.** Simpler, no callback round-trip, same data.

Critical rule: respond with HTTP 200 within 30 seconds. Do NOT hold the connection open while processing. Accept the webhook, queue processing, return 200 immediately.

Failed notifications retry with exponential backoff. Queue depth maintained for 7 days. Activity Files callbacks expire after 24 hours.

---

## 2. OAuth2 PKCE Flow

Garmin uses OAuth2 with PKCE (Proof Key for Code Exchange). OAuth1 is being retired on **12/31/2026**.

### Authorization (Step 1)
```
GET https://connect.garmin.com/oauth2Confirm
  ?response_type=code
  &client_id={client_id}
  &code_challenge={base64url(sha256(code_verifier))}
  &code_challenge_method=S256
  &redirect_uri={redirect_uri}
  &state={state}
```
User logs in, consents, redirected to `redirect_uri?code={code}&state={state}`.

### Token Exchange (Step 2)
```
POST https://diauth.garmin.com/di-oauth2-service/oauth/token
  Content-Type: application/x-www-form-urlencoded

  grant_type=authorization_code
  client_id={client_id}
  client_secret={client_secret}
  code={authorization_code}
  code_verifier={code_verifier}
  redirect_uri={redirect_uri}
```

Response:
```json
{
  "access_token": "...",
  "expires_in": 86400,
  "token_type": "bearer",
  "refresh_token": "...",
  "refresh_token_expires_in": 7775998
}
```

- Access token: 24h TTL. Subtract 600s for safety margin.
- Refresh token: 90-day TTL. New refresh token issued with each access token refresh.
- CORS preflight (OPTIONS) NOT supported.

### Refresh Token
```
POST https://diauth.garmin.com/di-oauth2-service/oauth/token
  grant_type=refresh_token
  client_id={client_id}
  client_secret={client_secret}
  refresh_token={refresh_token}
```

### API Calls
```
Authorization: Bearer {access_token}
```

### User ID
```
GET https://apis.garmin.com/wellness-api/rest/user/id
→ {"userId": "d3315b1072421d0dd7c8f6b8e1de4df8"}
```
User ID is persistent across token regeneration and multiple programs. Use as primary identifier.

### Delete Registration (required for account deletion / disconnect)
```
DELETE https://apis.garmin.com/wellness-api/rest/user/registration
→ HTTP 204
```

### User Permissions
```
GET https://apis.garmin.com/wellness-api/rest/user/permissions
→ ["HISTORICAL_DATA_EXPORT", "ACTIVITY_EXPORT", "HEALTH_EXPORT", ...]
```

---

## 3. Activity API

### 3.1 Activity Summaries

High-level activity data. Key fields for running:

| Field | Type | Notes |
|-------|------|-------|
| summaryId | string | Unique identifier |
| activityId | string | Garmin Connect activity ID |
| activityType | string | "RUNNING", "TRAIL_RUNNING", etc. (see Appendix) |
| activityName | string | User-set name |
| startTimeInSeconds | int | Unix timestamp UTC |
| startTimeOffsetInSeconds | int | Local time offset |
| durationInSeconds | int | Total duration |
| distanceInMeters | float | |
| averageSpeedInMetersPerSecond | float | |
| averagePaceInMinutesPerKilometer | float | |
| averageHeartRateInBeatsPerMinute | int | |
| maxHeartRateInBeatsPerMinute | int | |
| averageRunCadenceInStepsPerMinute | float | |
| maxRunCadenceInStepsPerMinute | float | |
| totalElevationGainInMeters | float | |
| totalElevationLossInMeters | float | |
| activeKilocalories | int | Includes BMR |
| steps | int | |
| deviceName | string | e.g. "Garmin fenix 8" |
| manual | bool | True if not from device |
| startingLatitudeInDegree | float | |
| startingLongitudeInDegree | float | |

### 3.2 Activity Details

Full per-second sensor data. Same summary fields plus:

**Samples array** (up to 1 sample/second):

| Field | Type |
|-------|------|
| startTimeInSeconds | int |
| latitudeInDegree | float |
| longitudeInDegree | float |
| elevationInMeters | float |
| heartRate | int |
| speedMetersPerSecond | float |
| stepsPerMinute | float |
| totalDistanceInMeters | float |
| timerDurationInSeconds | int |
| clockDurationInSeconds | int |
| movingDurationInSeconds | int |
| powerInWatts | float |
| airTemperatureCelcius | float |

**Laps array**: `[{startTimeInSeconds: int}]`

Duration limit: Activities >24 hours are NOT available through Activity Details. Use Activity Files instead.

Historical Activity Details available only via Push (not Ping/Pull).

Time relationships: `movingDuration <= timerDuration <= clockDuration`

### 3.3 Activity Files

Raw FIT/TCX/GPX files from the device. Only available via Ping (not Push).
- Callback URL valid for 24 hours only, single download
- Contains device-specific data not in Activity Details
- FIT SDK: https://developer.garmin.com/fit/overview/

### 3.4 Move IQ

Auto-detected activities (not user-initiated). Minimal data: type, subtype, duration. Already included in Daily/Epoch summaries.

---

## 4. Health API

### 4.1 Daily Summaries

One per day per user. Key fields:

| Field | Type | Notes |
|-------|------|-------|
| calendarDate | string | "yyyy-mm-dd" |
| steps | int | |
| distanceInMeters | float | |
| activeTimeInSeconds | int | |
| activeKilocalories | int | Activity only, excludes BMR |
| bmrKilocalories | int | Basal metabolic rate |
| floorsClimbed | int | |
| minHeartRateInBeatsPerMinute | int | |
| averageHeartRateInBeatsPerMinute | int | 7-day rolling average |
| maxHeartRateInBeatsPerMinute | int | |
| restingHeartRateInBeatsPerMinute | int | |
| timeOffsetHeartRateSamples | map | Offset→HR, 15s intervals |
| averageStressLevel | int | 1-100, -1 if insufficient data |
| maxStressLevel | int | |
| stressDurationInSeconds | int | Stress range (26-100) |
| restStressDurationInSeconds | int | Rest range (1-25) |
| stressQualifier | string | calm, balanced, stressful, very_stressful + _awake variants |
| bodyBatteryChargedValue | int | Amount charged during day |
| bodyBatteryDrainedValue | int | Amount drained during day |
| moderateIntensityDurationInSeconds | int | MET 3-6 |
| vigorousIntensityDurationInSeconds | int | MET >6 |

### 4.2 Epoch Summaries

15-minute time slices. Same fields as Daily but at granular level. Multiple records per epoch if multiple activity types (e.g. WALKING + RUNNING in same 15 min).

Duration <900s means mid-epoch sync; replace with updated record on next sync.

### 4.3 Sleep Summaries

Per-sleep-event (not per-day). Key fields:

| Field | Type | Notes |
|-------|------|-------|
| calendarDate | string | |
| durationInSeconds | int | Excludes awake/unmeasurable |
| deepSleepDurationInSeconds | int | |
| lightSleepDurationInSeconds | int | |
| remSleepInSeconds | int | Requires REM-capable device |
| awakeDurationInSeconds | int | |
| sleepLevelsMap | map | deep/light/rem/awake time ranges |
| validation | string | AUTO_FINAL, ENHANCED_FINAL, AUTO_TENTATIVE, etc. |
| overallSleepScore | map | {value: int, qualifierKey: EXCELLENT/GOOD/FAIR/POOR} |
| sleepScores | map | Per-category scores (duration, stress, awakeCount, rem%, light%, deep%) |
| timeOffsetSleepRespiration | map | Offset→breaths/min |
| timeOffsetSleepSpo2 | map | Offset→SpO2 |
| naps | list | Nap entries with duration, start time, validation |

Sleep score ranges: Excellent 90-100, Good 80-89, Fair 60-79, Poor <60.

Validation types to accept: ENHANCED_FINAL > AUTO_FINAL > ENHANCED_TENTATIVE > AUTO_TENTATIVE > DEVICE > AUTO_MANUAL > MANUAL > OFF_WRIST

### 4.4 Stress Details

3-minute averaged stress scores throughout the day plus Body Battery.

| Stress Value | Meaning |
|-------------|---------|
| 1-25 | Rest |
| 26-50 | Low stress |
| 51-75 | Medium stress |
| 76-100 | High stress |
| -1 | Off wrist |
| -2 | Large motion |
| -3 | Not enough data |
| -4 | Recovering from exercise |
| -5 | Unidentified |

Body Battery: `timeOffsetBodyBatteryValues` map + `bodyBatteryActivityEvents` list.

### 4.5 User Metrics

Per-date calculations (not time-bound):

| Field | Type |
|-------|------|
| vo2Max | float |
| vo2MaxCycling | float |
| fitnessAge | int |
| enhanced | bool |

### 4.6 HRV Summaries

Overnight sleep window only:

| Field | Type |
|-------|------|
| lastNightAvg | int |
| lastNight5MinHigh | int |
| hrvValues | map | Offset→RMSSD, 5-min intervals |

### 4.7 Other Health Summaries

- **Pulse Ox** — SpO2 measurements (all-day or on-demand)
- **Respiration** — Breaths/min throughout day
- **Health Snapshot** — 2-min session: HR, HRV (RMSSD+SDRR), stress, SpO2, respiration
- **Body Composition** — Weight, BMI, body fat%, muscle mass, bone mass (Index scale)
- **Blood Pressure** — Systolic, diastolic, pulse (Index BPM or manual)
- **Skin Temperature** — Sleep-window skin temp deviation

---

## 5. Backfill (Historical Data)

Request historical data for a user. Async — returns 202 immediately, data delivered via Push/Ping later.

| API | URL | Max Range |
|-----|-----|-----------|
| Activities | `/wellness-api/rest/backfill/activities` | 30 days |
| Activity Details | `/wellness-api/rest/backfill/activityDetails` | 30 days (Push only) |
| Dailies | `/wellness-api/rest/backfill/dailies` | 90 days |
| Sleep | `/wellness-api/rest/backfill/sleeps` | 90 days |
| Epochs | `/wellness-api/rest/backfill/epochs` | 90 days |
| Stress | `/wellness-api/rest/backfill/stressDetails` | 90 days |
| HRV | `/wellness-api/rest/backfill/hrv` | 90 days |
| All others | See Health API doc | 90 days |

Rate limits:
- Evaluation: 100 days/min
- Production: 10,000 days/min
- Per user: 1 month since first connection

Duplicate requests rejected with HTTP 409.

---

## 6. Webhook Endpoints (StrideIQ must implement)

| Endpoint | Purpose | Required |
|----------|---------|----------|
| Deregistration | User disconnected from Garmin or your app called DELETE /registration | Yes |
| User Permission | User changed data sharing permissions | Yes |
| Activity Summaries | New activity synced | If using Activity API |
| Activity Details | New activity details (Push only) | If using Activity API |
| Activity Files | New activity file available (Ping only) | If using Activity API |
| Move IQ | Auto-detected activity | Optional |
| Dailies | Daily summary updated | If using Health API |
| Epochs | 15-min epoch updated | Optional |
| Sleeps | Sleep data updated | If using Health API |
| Stress Details | Stress/Body Battery updated | If using Health API |
| User Metrics | VO2max/fitness age updated | If using Health API |
| HRV | Overnight HRV updated | If using Health API |
| Pulse Ox | SpO2 data | Optional |
| Respiration | Breathing rate data | Optional |
| Health Snapshot | 2-min health reading | Optional |
| Body Composition | Weight/BMI data | Optional |
| Blood Pressure | BP readings | Optional |
| Skin Temperature | Sleep skin temp | Optional |

Configure at: https://apis.garmin.com/tools/endpoints

---

## 7. Running Activity Types (Garmin → StrideIQ mapping needed)

| Garmin API Value | Description |
|-----------------|-------------|
| RUNNING | General running |
| INDOOR_RUNNING | Indoor/treadmill |
| TREADMILL_RUNNING | Treadmill specific |
| TRAIL_RUNNING | Trail |
| TRACK_RUNNING | Track |
| STREET_RUNNING | Street/road |
| VIRTUAL_RUN | Virtual (Zwift etc.) |
| ULTRA_RUN | Ultra distance |
| OBSTACLE_RUN | OCR |

---

## 8. Production Key Requirements

Before going live, need technical + UX review from Garmin:

### Technical (use Partner Verification tool)
- 2+ Garmin Connect users authorized
- Deregistration + User Permission endpoints enabled
- Push/Ping processing working (pull-only NOT allowed)
- HTTP 200 within 30s for all data (min 10MB payload, Activity Details 100MB)
- Data from physical Garmin devices (not just Data Generator)

### UX/Brand
- Screenshots of all Garmin branding usage
- Attribution per brand guidelines
- Complete UX flow showing Garmin representation
- All instances of Garmin marks in the app

### Account
- All team members added to developer portal
- Signed up for API Blog notifications

---

## 9. Key Differences: Garmin vs Strava

| Aspect | Strava | Garmin |
|--------|--------|--------|
| Data delivery | Polling + webhooks | Webhooks only (Push or Ping) |
| Auth | OAuth2 standard | OAuth2 PKCE |
| Activity streams | Separate API call per stream | Embedded in Activity Details as samples array |
| Health data | None | Daily, Sleep, Stress, HRV, Body Battery, SpO2, etc. |
| Historical data | Paginated API calls | Backfill endpoint (async, 30-90 day windows) |
| Rate limits | Per-app, 15-min windows | Per-key, evaluation vs production tiers |
| File access | Not available | FIT/TCX/GPX files via Activity Files |
| Token refresh | Refresh token, no expiry | Refresh token, 90-day expiry |
| Client restrictions | Client-side OK | Server-to-server only |

---

## 10. Implementation Notes for StrideIQ

### Data StrideIQ should consume (priority order)
1. **Activity Details (Push)** — per-second HR, pace, cadence, GPS, elevation. Maps to ActivityStream model.
2. **Activity Summaries (Push)** — high-level metrics. Maps to Activity model.
3. **Sleep Summaries (Push)** — sleep duration, stages, scores. Maps to check-in correlation data.
4. **HRV Summaries (Push)** — overnight HRV for readiness. Maps to check-in/readiness model.
5. **Daily Summaries (Push)** — resting HR, stress, Body Battery. Maps to daily wellness context.
6. **Stress Details (Push)** — granular stress/Body Battery. Future: pre-race stress analysis.

### Data mapping at ingestion boundary
Garmin samples use different field names than Strava streams:
- `speedMetersPerSecond` → convert to pace (min/km or min/mi)
- `heartRate` → same concept, different key name
- `stepsPerMinute` → maps to cadence (Strava uses `cadence` as steps/min ÷ 2)
- `elevationInMeters` → same as Strava `altitude`
- `latitudeInDegree`/`longitudeInDegree` → same as Strava `latlng`

### Webhook endpoint design
- Accept POST, return 200 immediately
- Queue data processing via Celery (same pattern as Strava webhook)
- Store raw webhook payload for debugging
- Validate `garmin-client-id` header matches our client ID

### Time handling
- All timestamps are Unix seconds UTC
- `startTimeOffsetInSeconds` is NOT a timezone — it's whatever the user set on their device
- Use UTC internally, apply offset only for display
