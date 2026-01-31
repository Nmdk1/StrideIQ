# COROS API Application Preparation

**Status:** PLANNING  
**Priority:** Medium (after Garmin Activity API approval)  
**Application URL:** https://support.coros.com/hc/en-us/articles/17085887816340-Submit-an-API-Application

---

## Overview

COROS offers a free API integration program for third-party applications. Unlike Garmin, there is **no fee** for API access. The integration supports OAuth-based authentication and push-based workout data sync.

---

## Application Requirements

### Company Information

| Field | Value | Status |
|-------|-------|--------|
| Primary Email | michael@strideiq.run | Ready |
| Secondary Email | support@strideiq.run | Ready |
| Product Owner Name/Title | Michael Shaffer, Founder | Ready |
| Company Name | StrideIQ (Sole Proprietor) | Ready |
| Company URL | https://strideiq.run | Ready |

**Available Email Aliases:**
- michael@strideiq.run (primary)
- support@strideiq.run
- legal@strideiq.run
- info@strideiq.run
- privacy@strideiq.run

### Application Details

| Field | Value | Status |
|-------|-------|--------|
| Application Name | StrideIQ | Ready |
| Application Description (100 chars) | AI running coach with personalized analytics. Sync workouts to unlock insights. | Ready |
| Number of Active Users | 0-150 | Ready |
| Primary Region | United States | Ready |

### API Functions Needed

| Function | Needed | Reason |
|----------|--------|--------|
| Activity/Workout Data Sync | ✅ Yes | Core feature - sync running activities |
| Structured Workouts and Training Plans Sync | ❌ No (future) | Not in current scope |
| GPX Route Import/Export | ❌ No | Not needed |
| Bluetooth Connectivity | ❌ No | Not applicable |
| ANT+ Connectivity | ❌ No | Not applicable |

### Technical Requirements

| Field | Value | Status |
|-------|-------|--------|
| Authorized Callback Domain | https://strideiq.run | Ready |
| OAuth Redirect URI | https://strideiq.run/auth/coros/callback | Ready |
| Workout Data Receiving Endpoint | https://api.strideiq.run/v1/webhooks/coros | To Build |
| Service Status Check URL | https://api.strideiq.run/health | Ready |

### Compliance Requirements (Already Met)

| Requirement | URL | Status |
|-------------|-----|--------|
| Login Portal | https://strideiq.run/login | ✅ Ready |
| Support Page | https://strideiq.run/support | ✅ Ready |
| Privacy Policy | https://strideiq.run/privacy | ✅ Ready (needs COROS section) |
| Terms of Service | https://strideiq.run/terms | ✅ Ready (needs COROS section) |

### App Images Required

| Size | Purpose | Status |
|------|---------|--------|
| 144px × 144px | Partner page display | NEEDED |
| 102px × 102px | Partner page display | NEEDED |
| 120px × 120px | Structured workouts (optional) | Not needed for v1 |
| 300px × 300px | Structured workouts (optional) | Not needed for v1 |

**Submit images to:** api@coros.com  
**Subject line:** StrideIQ - API Images

---

## Application Form Responses (Draft)

### Personal or Public Use?
> Public use - available to all StrideIQ users who have COROS devices.

### Commercial or Non-Commercial Use?
> Commercial use - StrideIQ is a subscription-based running analytics platform.

### Intended Use of Data?
> We will use the Activity API to sync running activities from users' COROS devices. This includes activity details (distance, duration, pace, elevation), heart rate data, and GPS data. This data powers our N=1 (individual-only) analysis engine that calculates efficiency trends, age-graded performance, and personal records. No population modeling or data aggregation occurs. User data is never sold, shared, or used for AI model training.

---

## Technical Integration Plan

### Architecture

```
COROS Cloud
    ↓ (Push: workout data every 5 min)
StrideIQ Webhook Endpoint (/v1/webhooks/coros)
    ↓ (verify client/secret header)
Celery Worker (download FIT, parse, normalize)
    ↓
Canonical Activity Model
    ↓
Analytics Engine
```

### Environments

| Environment | Domain | Purpose |
|-------------|--------|---------|
| Test | opentest.coros.com | Development/testing |
| Production | open.coros.com | Live users |

---

## OAuth 2.0 Flow (Section 3)

### Step 1: Authorization Request
```
GET https://open.coros.com/oauth2/authorize
  ?client_id={clientId}
  &redirect_uri={urlencode(https://strideiq.run/auth/coros/callback)}
  &response_type=code
  &state={csrf_token}
```

### Step 2: User Authorizes → Redirect with Code
```
https://strideiq.run/auth/coros/callback?code={CODE}&state={STATE}
```
- Code valid for 30 minutes, single use

### Step 3: Exchange Code for Token
```
POST https://open.coros.com/oauth2/accesstoken
Content-Type: application/x-www-form-urlencoded

client_id={clientId}
&redirect_uri={redirect_uri}
&code={code}
&client_secret={clientSecret}
&grant_type=authorization_code
```

**Response:**
```json
{
  "expiresIn": 2592000,
  "refreshToken": "xxx",
  "accessToken": "xxx",
  "openId": "user_unique_id"
}
```
- accessToken valid for 30 days
- refreshToken NEVER expires

### Step 4: Refresh Token (when approaching 30-day expiry)
```
POST https://open.coros.com/oauth2/refresh
Content-Type: application/x-www-form-urlencoded

client_id={clientId}
&refresh_token={refreshToken}
&client_secret={clientSecret}
&grant_type=refresh_token
```

### Deauthorization
```
POST https://open.coros.com/coros/open/unbind
Header: token={accessToken}
```

### Check Binding Status
```
GET https://open.coros.com/coros/open/bind/status
  ?token={accessToken}
  &openId={openId}
```

---

## Data Endpoints (Section 4)

### Get User Info
```
GET https://open.coros.com/coros/open/user/info
  ?token={accessToken}
  &openId={openId}
```
Returns: nick, profilePhoto, runCalorie, runDistance, runTotalTime

### Get Workout Records (by date range)
```
GET https://open.coros.com/coros/open/sport/data
  ?token={accessToken}
  &openId={openId}
  &startDate=20260101
  &endDate=20260131
```
**Limits:**
- Max 30 days per query
- Query date must be within 3 months of current date

**Response includes:**
- labelId (workout ID)
- mode/subMode (workout type)
- distance (meters), calorie, avgSpeed (sec/km), avgFrequency (steps/min)
- step, startTime, endTime, startTimezone, endTimezone
- **fitUrl** (direct download link for FIT file)
- triathlonItemList (for multisport)

### Get Daily Data (sleep, HRV, RHR)
```
GET https://open.coros.com/coros/open/daily/data
  ?token={accessToken}
  &openId={openId}
  &startDate=20260101
  &endDate=20260131
```
**Response includes:**
- sleepStartTime, sleepEndTime
- calorie, step
- rhr (resting heart rate)
- hrvList (hrv, timestamp, hr)
- ppgHrv (overnight HRV)
- sleepAvgHr

### Get FIT File Details
```
GET https://open.coros.com/coros/open/fit/download
  ?token={accessToken}
  &openId={openId}
  &labelId={workoutId}
  &mode={parentType}
  &subMode={childType}
```

---

## Webhook Push (Section 5.3)

COROS pushes workout data to partner every 5 minutes.

### Requirements
| Item | Value |
|------|-------|
| Endpoint URL | https://api.strideiq.run/v1/webhooks/coros |
| Status Check URL | https://api.strideiq.run/health |
| Must handle duplicates | Yes (idempotent) |
| Retry policy | 2 retries, then marks failed |
| Failed data retention | 24 hours, then stops pushing |

### Webhook Request Format
```
POST https://api.strideiq.run/v1/webhooks/coros
Header: client={clientId}
Header: secret={clientSecret}
Content-Type: application/json

{
  "sportDataList": [
    {
      "openId": "user_id",
      "labelId": "workout_id",
      "mode": 8,
      "subMode": 1,
      "distance": 10000,
      "calorie": 500,
      "avgSpeed": 300,
      "avgFrequency": 180,
      "startTime": 1234567890,
      "endTime": 1234571490,
      "fitUrl": "https://oss.coros.com/fit/xxx.fit",
      ...
    }
  ]
}
```

### Required Response
```json
{
  "result": "0000",
  "message": "OK"
}
```
- `result: "0000"` = success
- Any other code = failure (will retry)

---

## Workout Type Mapping

| COROS mode | COROS subMode | Type | StrideIQ activity_type |
|------------|---------------|------|------------------------|
| 8 | 1 | Outdoor Run | run |
| 8 | 2 | Indoor Run | run |
| 15 | 1 | Trail Run | trail_run |
| 20 | 1 | Track Run | run |
| 16 | 1 | Hike | hike |
| 31 | 1 | Walk | walk |
| 9 | 1 | Outdoor Bike | bike |
| 9 | 2 | Indoor Bike | bike |
| 10 | 1 | Open Water | swim |
| 10 | 2 | Pool Swim | swim |
| 13 | 1 | Triathlon | triathlon |
| 13 | 2 | Multisport | multisport |

---

## Data Mapping (COROS → StrideIQ)

| COROS Field | Type | StrideIQ Activity Field |
|-------------|------|------------------------|
| labelId | String | external_activity_id |
| mode + subMode | int | activity_type (mapped) |
| startTime | timestamp (sec) | start_time |
| endTime - startTime | int | elapsed_time_seconds |
| distance | float (meters) | distance_meters |
| calorie | float | calories |
| avgSpeed | int (sec/km) | avg_pace_seconds_per_km |
| avgFrequency | int (steps/min) | avg_cadence |
| step | int | total_steps |
| fitUrl | string | Parse FIT for HR, GPS, splits |

### Daily Data Mapping (for recovery features)

| COROS Field | StrideIQ Field |
|-------------|----------------|
| rhr | resting_heart_rate |
| ppgHrv | overnight_hrv |
| sleepStartTime/EndTime | sleep_duration |
| sleepAvgHr | sleep_avg_hr |

---

## Rate Limits

| Limit | Value |
|-------|-------|
| Max calls per minute | 1000 |
| Max days per query | 30 |
| Historical data limit | 3 months before current date |
| HTTP 429 | Too Many Requests |

---

## Implementation Phases

### Phase 1: Application Submission
1. Update Privacy Policy with COROS section
2. Update Terms of Service with COROS section
3. Create app logo images (144×144, 102×102)
4. Submit application form
5. Wait for approval and receive Client ID/Secret

### Phase 2: OAuth Implementation (Post-Approval)
1. Add COROS OAuth credentials to environment
2. Create `/v1/coros/auth-url` endpoint
3. Create `/v1/coros/callback` endpoint
4. Create `/v1/coros/disconnect` endpoint
5. Add connect/disconnect UI in settings

### Phase 3: Webhook Integration
1. Create `/v1/webhooks/coros` endpoint
2. Implement COROS data parser
3. Map to canonical Activity model
4. Test with real COROS account

### Phase 4: UI Integration
1. Add COROS to integrations settings page
2. Add COROS icon/branding
3. Show sync status

---

## Comparison: COROS vs Garmin vs Strava

| Aspect | Strava | Garmin | COROS |
|--------|--------|--------|-------|
| API Fee | Free | Free | Free |
| Auth Type | OAuth 2.0 | OAuth 2.0 | OAuth 2.0 |
| Token Validity | 6 hours | Unknown | 30 days |
| Refresh Token | Expires | Unknown | Never expires |
| Data Push | Webhooks | Ping/Pull | Push every 5 min |
| FIT File Access | No | Yes | Yes (via URL) |
| Daily Data (Sleep/HRV/RHR) | No | Health API (separate) | Yes (same API) |
| Historical Limit | None? | Unknown | 3 months |
| Rate Limit | 100/15min, 1000/day | Unknown | 1000/min |
| Approval Time | 7-10 days | ~2 business days | TBD |
| Current Status | **APPROVED** | Submitted | Not Applied |

### COROS Advantages
1. **Daily data included** - Sleep, HRV, RHR in same API (no separate Health API needed)
2. **Push-based** - COROS pushes to us every 5 min (less polling)
3. **Long token life** - 30 days vs Strava's 6 hours
4. **RefreshToken never expires** - Simpler token management
5. **FIT files via URL** - Direct download, no extra API call

### COROS Limitations
1. **3-month historical limit** - Can only query last 3 months
2. **No real-time** - Push is every 5 min, not instant
3. **Smaller user base** - Fewer athletes use COROS vs Garmin

---

## Action Items

### Owner Actions (Pre-Application)
- [x] ~~Provide secondary email address~~ - support@strideiq.run
- [ ] Create/provide app logo images (144×144 and 102×102 PNG)
- [ ] Email images to api@coros.com with subject "StrideIQ - API Images"
- [ ] Review application form responses in this document
- [ ] Submit application when ready

### Technical Actions (Pre-Application)
- [ ] Add COROS section to Privacy Policy (similar to Garmin section)
- [ ] Add COROS section to Terms of Service (similar to Garmin section)

### Technical Actions (Post-Approval)
- [ ] Store clientId and clientSecret in `.env`
- [ ] Implement OAuth flow (`/v1/coros/auth-url`, `/v1/coros/callback`, `/v1/coros/disconnect`)
- [ ] Implement webhook endpoint (`/v1/webhooks/coros`) with client/secret verification
- [ ] Implement FIT file download and parsing
- [ ] Implement daily data sync (sleep, HRV, RHR)
- [ ] Map COROS workout types to StrideIQ activity_type
- [ ] Add UI for connect/disconnect in settings
- [ ] Add feature flag: `integrations.coros_oauth_v1`

---

## Resources

- **API Application Form:** https://docs.google.com/forms/d/e/1FAIpQLSe2i_nIRV62yCeld8J9UR41I_vC34Z2_S82CodxurHHjFEo9Q/viewform
- **API Reference Guide (Dropbox):** https://www.dropbox.com/scl/fo/6ps1297tn9pfo7qmcb0o8/AItfHWAW8t-jZ0NIrAaT0hg?rlkey=kbq4zmu47j9c3c6qu7b96z39f&st=wi864yvy&dl=0
- **Support Page:** https://support.coros.com/hc/en-us/articles/17085887816340-Submit-an-API-Application
- **OAuth Authorize URL:** https://open.coros.com/oauth2/authorize
- **Submit Images To:** api@coros.com (Subject: "StrideIQ - API Images")

### API Reference PDF

**Status:** REVIEWED ✅ (V2.0.6, April 2025)

Full technical documentation extracted and integrated into this document.

---

## Notes

- COROS requires 1-week notice before going live for marketing coordination
- COROS may provide loaner devices for Bluetooth/ANT+ testing (not applicable for API-only)
- No credential-based access - OAuth only (matches our security policy)
- Existing file import seam (ADR-057) can be leveraged for data normalization

---

**Last Updated:** 2026-01-31 (API Reference V2.0.6 integrated)
