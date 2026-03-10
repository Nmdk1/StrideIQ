# Garmin Health API — Official Portal Documentation

**Source:** `https://apis.garmin.com/tools/apiDocs/wellness-api`
**Captured:** February 22, 2026
**Server:** `https://apis.garmin.com/wellness-api` (Prod)

---

## Summary Endpoints

### GET /rest/activities

Activity summaries — high-level info from discrete fitness activities started by the user.

**Parameters:** `uploadStartTimeInSeconds`, `uploadEndTimeInSeconds`, `token` (OAuth2)

**Response schema (`ClientActivity`):**

```json
{
  "userId": "4aacafe82427c251df9c9592d0c06768",
  "summaryId": "x153a9f3-5a9478d4-6",
  "activityId": 5001968355,
  "activityName": "string",
  "activityDescription": "string",
  "isParent": true,
  "parentSummaryId": "string",
  "durationInSeconds": 1789,
  "startTimeInSeconds": 1512234126,
  "startTimeOffsetInSeconds": -25200,
  "activityType": "RUNNING",
  "averageBikeCadenceInRoundsPerMinute": 0,
  "averageHeartRateInBeatsPerMinute": 144,
  "averageRunCadenceInStepsPerMinute": 84,
  "averagePushCadenceInPushesPerMinute": 80,
  "averageSpeedInMetersPerSecond": 2.781,
  "averageSwimCadenceInStrokesPerMinute": 0,
  "averagePaceInMinutesPerKilometer": 15.521924,
  "activeKilocalories": 367,
  "deviceName": "forerunner935",
  "distanceInMeters": 1976.83,
  "maxBikeCadenceInRoundsPerMinute": 0,
  "maxHeartRateInBeatsPerMinute": 159,
  "maxPaceInMinutesPerKilometer": 10.396549,
  "maxRunCadenceInStepsPerMinute": 106,
  "maxPushCadenceInPushesPerMinute": 75,
  "maxSpeedInMetersPerSecond": 4.152,
  "numberOfActiveLengths": 0,
  "startingLatitudeInDegree": 51.053232522681355,
  "startingLongitudeInDegree": -114.06880217604339,
  "steps": 5022,
  "pushes": 1000,
  "totalElevationGainInMeters": 16,
  "totalElevationLossInMeters": 22,
  "manual": true,
  "isWebUpload": true
}
```

**Notable absent fields vs discovery doc assumptions:**
- No `AverageStrideLength`
- No `AverageGroundContactTime`
- No `AverageGroundContactTimeBalance`
- No `AverageVerticalOscillation`
- No `AverageVerticalRatio`
- No `AveragePowerInWatts` / `MaxPowerInWatts` (at summary level)
- No `AverageGradeAdjustedPaceInMinutesPerMile` (GAP)
- No `AerobicTrainingEffect` / `AnaerobicTrainingEffect`
- No `TrainingEffectLabel`
- No `SelfEvaluationFeel` / `SelfEvaluationPerceivedEffort`
- No `BodyBatteryImpact` (at activity summary level)
- No `MovingTimeInSeconds`

**Present fields not in discovery doc:**
- `averagePushCadenceInPushesPerMinute` (wheelchair)
- `averageBikeCadenceInRoundsPerMinute`
- `averageSwimCadenceInStrokesPerMinute`
- `averagePaceInMinutesPerKilometer`
- `isWebUpload`

---

### GET /rest/activityDetails

Detailed activity info including GPS, sensor data, laps.

**Response schema (`ClientActivityDetail`):**

```json
{
  "userId": "4aacafe82427c251df9c9592d0c06768",
  "summaryId": "x153a9f3-5a9478d4-6",
  "activityId": 5001968355,
  "summary": { /* same as ClientActivity above */ },
  "samples": [
    {
      "startTimeInSeconds": 1512234126,
      "latitudeInDegree": 51.053232522681355,
      "longitudeInDegree": -114.06880217604339,
      "elevationInMeters": 1049.4000244140625,
      "airTemperatureCelcius": 28,
      "heartRate": 83,
      "speedMetersPerSecond": 0,
      "stepsPerMinute": 57,
      "totalDistanceInMeters": 0.17000000178813934,
      "powerInWatts": 0,
      "bikeCadenceInRPM": 0,
      "swimCadenceInStrokesPerMinute": 0,
      "wheelChairCadenceInPushesPerMinute": 0,
      "timerDurationInSeconds": 0,
      "clockDurationInSeconds": 0,
      "movingDurationInSeconds": 0
    }
  ],
  "laps": [
    {
      "startTimeInSeconds": 1512234126
    }
  ]
}
```

**Sample schema fields (official `Sample` model):**
- `startTimeInSeconds` (int32)
- `latitudeInDegree` (double)
- `longitudeInDegree` (double)
- `elevationInMeters` (double)
- `airTemperatureCelcius` (double)
- `heartRate` (int32)
- `speedMetersPerSecond` (double)
- `stepsPerMinute` (double) — cadence
- `totalDistanceInMeters` (double)
- `powerInWatts` (double) — running power IS in stream data
- `bikeCadenceInRPM` (double)
- `swimCadenceInStrokesPerMinute` (double)
- `wheelChairCadenceInPushesPerMinute` (double)
- `timerDurationInSeconds` (int32)
- `clockDurationInSeconds` (int32)
- `movingDurationInSeconds` (int32)

**Running dynamics fields NOT present in official Sample schema:**
- No `strideLength`
- No `groundContactTime`
- No `groundContactBalance`
- No `verticalOscillation`
- No `verticalRatio`

**Conclusion [M2]:** Running dynamics (stride length, GCT, vertical oscillation, vertical ratio) are NOT available in the JSON API. They exist only in FIT files (`GET /rest/activityFile`). Power (`powerInWatts`) IS available in stream samples.

---

### GET /rest/activityFile

Raw FIT, TCX, or GPX files.

**Important note from docs:** "Unlike normal Summaries, Activity Files are not available as a Push integration. Files are only available in response to a Ping by calling the specified callbackURL."

**Parameters:** `id`, `token`
**Response:** `application/octet-stream`

---

### GET /rest/dailies

Daily summaries — high-level view of user's entire day (midnight-to-midnight).

**Response schema (`ClientDaily`):**

```json
{
  "userId": "4aacafe82427c251df9c9592d0c06768",
  "summaryId": "x153a9f3-5a9478d4-6",
  "calendarDate": "2022-01-11",
  "activityType": "WALKING",
  "activeKilocalories": 321,
  "bmrKilocalories": 1731,
  "steps": 4210,
  "pushes": 3088,
  "distanceInMeters": 3146.5,
  "pushDistanceInMeters": 2095.2,
  "durationInSeconds": 86400,
  "activeTimeInSeconds": 12240,
  "startTimeInSeconds": 1452470400,
  "startTimeOffsetInSeconds": 3600,
  "moderateIntensityDurationInSeconds": 81870,
  "vigorousIntensityDurationInSeconds": 4530,
  "floorsClimbed": 8,
  "minHeartRateInBeatsPerMinute": 59,
  "maxHeartRateInBeatsPerMinute": 112,
  "averageHeartRateInBeatsPerMinute": 64,
  "restingHeartRateInBeatsPerMinute": 64,
  "timeOffsetHeartRateSamples": "{15: 75, 30: 75, ...}",
  "source": "string",
  "stepsGoal": 4500,
  "pushesGoal": 3100,
  "intensityDurationGoalInSeconds": 1500,
  "floorsClimbedGoal": 18,
  "averageStressLevel": 43,
  "maxStressLevel": 87,
  "stressDurationInSeconds": 13620,
  "restStressDurationInSeconds": 7600,
  "activityStressDurationInSeconds": 3450,
  "lowStressDurationInSeconds": 6700,
  "mediumStressDurationInSeconds": 4350,
  "highStressDurationInSeconds": 108000,
  "stressQualifier": "stressful_awake",
  "bodyBatteryChargedValue": 6,
  "bodyBatteryDrainedValue": 18
}
```

---

### GET /rest/sleeps

Sleep summaries — duration, staging, quality.

**Important note from docs:** "Many Garmin devices attempt to auto-sync data during the night while the user is asleep and the smartphone is charging. This may result in an incomplete Sleep summary record. It is important to update sleep data with the most recent data provided on subsequent ping notifications to get an accurate and full representation of the sleep window."

**Response schema (`ClientSleep`):**

```json
{
  "userId": "4aacafe82427c251df9c9592d0c06768",
  "summaryId": "x153a9f3-5a9478d4-6",
  "calendarDate": "2022-01-10",
  "durationInSeconds": 15264,
  "totalNapDurationInSeconds": 300,
  "startTimeInSeconds": 1452419581,
  "startTimeOffsetInSeconds": 7200,
  "unmeasurableSleepInSeconds": 0,
  "deepSleepDurationInSeconds": 11231,
  "lightSleepDurationInSeconds": 3541,
  "remSleepInSeconds": 0,
  "awakeDurationInSeconds": 492,
  "sleepLevelsMap": "deep: [{...}], light: [{...}], rem: [{...}]",
  "validation": "DEVICE",
  "timeOffsetSleepSpo2": "0: 95, 60: 96, ...",
  "timeOffsetSleepRespiration": "60: 15.31, 120: 14.58, ...",
  "overallSleepScore": {
    "value": 87,
    "qualifierKey": "GOOD"
  },
  "sleepScores": { "additionalProp1": { "value": 87, "qualifierKey": "GOOD" } },
  "naps": [
    {
      "napStartTimeInSeconds": 1692116877,
      "napOffsetInSeconds": -18000,
      "napDurationInSeconds": 300,
      "napValidation": "device"
    }
  ]
}
```

**Sleep field name differences vs discovery doc:**
- Discovery: `OverallSleepScoreValue` → Actual: nested `overallSleepScore.value`
- Discovery: `OverallSleepScoreQualifierKey` → Actual: nested `overallSleepScore.qualifierKey`

---

### GET /rest/hrv

HRV summaries — overnight sleep window.

**Response schema (`ClientHRVSummary`):**

```json
{
  "userId": "4aacafe82427c251df9c9592d0c06768",
  "summaryId": "x153a9f3-5a9478d4-6",
  "calendarDate": "2022-05-31",
  "lastNightAvg": 44,
  "lastNight5MinHigh": 72,
  "startTimeOffsetInSeconds": -18000,
  "durationInSeconds": 3820,
  "startTimeInSeconds": 1653976004,
  "hrvValues": "{300: 32, 600: 24, ...}"
}
```

---

### GET /rest/stressDetails

Stress and Body Battery — 3-minute averages.

**Response schema (`ClientStress`):**

```json
{
  "userId": "4aacafe82427c251df9c9592d0c06768",
  "summaryId": "x153a9f3-5a9478d4-6",
  "startTimeInSeconds": 1490245200,
  "startTimeOffsetInSeconds": 0,
  "durationInSeconds": 540,
  "calendarDate": "2022-03-23",
  "maxStressLevel": 51,
  "averageStressLevel": 43,
  "timeOffsetStressLevelValues": "{0: 18, 180: 51, 360: 28, 540: 29}",
  "timeOffsetBodyBatteryValues": "{0: 55, 180: 56, 360: 59}",
  "bodyBatteryDynamicFeedbackEvent": {
    "eventStartTimeInSeconds": 1687291752,
    "bodyBatteryLevel": "LOW"
  },
  "bodyBatteryActivityEvents": [
    {
      "eventType": "activity",
      "eventStartTimeInSeconds": 1687291752,
      "eventStartTimeOffsetInSeconds": -18000,
      "durationInSeconds": 660000,
      "bodyBatteryImpact": -3,
      "activityName": "walking",
      "activityType": "Olathe Walking",
      "activityId": 5003836302
    }
  ]
}
```

---

### GET /rest/userMetrics

Per-user calculations (VO2 max, fitness age).

```json
{
  "userId": "4aacafe82427c251df9c9592d0c06768",
  "summaryId": "x153a9f3-5a9478d4-6",
  "calendarDate": "2022-03-23",
  "vo2Max": 48,
  "vo2MaxCycling": 45,
  "fitnessAge": 32,
  "enhanced": true
}
```

---

### GET /rest/epochs

15-minute granularity wellness data. One record per activity type per epoch.

```json
{
  "userId": "4aacafe82427c251df9c9592d0c06768",
  "summaryId": "x153a9f3-5a9478d4-6",
  "activityType": "WALKING",
  "activeKilocalories": 24,
  "steps": 93,
  "distanceInMeters": 49.11,
  "durationInSeconds": 840,
  "activeTimeInSeconds": 449,
  "startTimeInSeconds": 1519679700,
  "startTimeOffsetInSeconds": -21600,
  "met": 3.3020337,
  "intensity": "ACTIVE",
  "meanMotionIntensity": 4,
  "maxMotionIntensity": 7
}
```

---

### Other Endpoints (deferred — not in Phase 2 Tier 1)

- `GET /rest/bodyComps` — body composition (weight, BMI, body fat %)
- `GET /rest/bloodPressures` — blood pressure readings
- `GET /rest/pulseOx` — SpO2 readings
- `GET /rest/respiration` — breathing rate
- `GET /rest/skinTemp` — skin temperature deviation
- `GET /rest/healthSnapshot` — 2-minute health session
- `GET /rest/moveiq` — auto-detected activities (not user-initiated)
- `GET /rest/mct` — menstrual cycle tracking
- `GET /rest/solarIntensity` — solar intensity readings
- `GET /rest/manuallyUpdatedActivities` — manual/edited activities

---

## User Controller

- `GET /rest/user/permissions` — fetch user's granted permissions
- `GET /rest/user/id` — fetch API user ID
- `DELETE /rest/user/registration` — deregister user (disconnect)

---

## Backfill Endpoints

All return `202 Accepted`. Parameters: `summaryStartTimeInSeconds`, `summaryEndTimeInSeconds`.

- `GET /rest/backfill/activities`
- `GET /rest/backfill/activityDetails`
- `GET /rest/backfill/dailies`
- `GET /rest/backfill/sleeps`
- `GET /rest/backfill/hrv`
- `GET /rest/backfill/stressDetails`
- `GET /rest/backfill/epochs`
- `GET /rest/backfill/bodyComps`
- `GET /rest/backfill/bloodPressures`
- `GET /rest/backfill/pulseOx`
- `GET /rest/backfill/respiration`
- `GET /rest/backfill/skinTemp`
- `GET /rest/backfill/healthSnapshot`
- `GET /rest/backfill/moveiq`
- `GET /rest/backfill/mct`
- `GET /rest/backfill/userMetrics`

**Backfill returns 202 (async).** Garmin queues the backfill and pushes the data to the webhook endpoint when ready. This is not a synchronous pull — it's "request backfill, receive via webhook."
