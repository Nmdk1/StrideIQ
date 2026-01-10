# External Integration Requirements

**Purpose:** Document the requirements for obtaining API access to each platform so you know exactly what's needed when you're ready to apply.

**Current Status:** Only Strava is integrated. Other platforms require a live production website, privacy policy, and/or business registration before granting API access.

---

## Currently Integrated

### ✅ Strava
- **Status:** Fully integrated
- **Data Type:** Activities, laps/splits, GAP
- **Auth:** OAuth 2.0
- **Webhooks:** Supported
- **Files:** `apps/api/services/strava_service.py`, `apps/api/routers/strava.py`

---

## Pending Integrations (Post-Launch)

### 🟡 Garmin Connect

**Application Status:** Rejected (requires live website + company)

**Requirements for API Access:**
1. ✅ Registered business entity (LLC, Corp, etc.)
2. ✅ Live production website with:
   - Homepage explaining the product
   - Privacy policy
   - Terms of service
   - Contact information
3. ✅ App description explaining how Garmin data will be used
4. ✅ Screenshots of the integration (if available)

**API Details:**
- **Portal:** https://developer.garmin.com/
- **Auth:** OAuth 2.0 (official) or username/password (python-garminconnect, blocked)
- **Data Available:**
  - Activities (running, cycling, swimming)
  - Daily summaries
  - Sleep data
  - HRV status
  - Body composition
  - Stress data
  - Training load
  - Training readiness

**Application Process:**
1. Create developer account at https://developer.garmin.com/
2. Submit application with business details
3. Wait for approval (typically 1-4 weeks)
4. Receive client_id and client_secret
5. Implement OAuth flow

**Code Ready:** `apps/api/services/garmin_service.py` (using python-garminconnect, will need updating for official OAuth)

**Data Mapping:**
```
Garmin Field            → Our Field
activityType           → Activity.sport
duration               → Activity.duration_s
distance               → Activity.distance_m
averageHR              → Activity.avg_hr
maxHR                  → Activity.max_hr
averageSpeed           → Activity.average_speed
splits[]               → ActivitySplit[]
sleepTimeSeconds       → DailyCheckin.sleep_h
hrvStatus              → DailyCheckin.hrv_rmssd
restingHeartRate       → DailyCheckin.resting_hr
bodyBatteryChargedValue → DailyCheckin (new field)
stressLevelValue       → DailyCheckin.stress_1_5
```

---

### 🟡 Coros

**Application Status:** Not yet applied

**Requirements for API Access:**
1. ✅ Registered business entity
2. ✅ Live production website with privacy policy
3. ✅ Business development partnership (more restrictive than Garmin)

**API Details:**
- **Portal:** https://developer.coros.com/ (requires partnership application)
- **Auth:** OAuth 2.0
- **Data Available:**
  - Activities
  - Training load
  - Sleep data
  - HRV

**Application Process:**
1. Contact COROS business development
2. Submit partnership application
3. Demonstrate live product
4. Sign partnership agreement
5. Receive API credentials

**Priority:** Medium (after Garmin)

---

### 🟡 Whoop

**Application Status:** Not yet applied

**Requirements for API Access:**
1. ✅ Business entity
2. ✅ Live website
3. ✅ Partnership agreement (Whoop has stricter requirements)

**API Details:**
- **Portal:** https://developer.whoop.com/
- **Auth:** OAuth 2.0
- **Data Available:**
  - Recovery score
  - Strain score
  - Sleep data
  - HRV
  - Resting HR
  - Respiratory rate

**Data Mapping:**
```
Whoop Field            → Our Field
recovery.score         → DailyCheckin.recovery_score (new)
strain.score           → DailyCheckin.strain_score (new)
sleep.hours            → DailyCheckin.sleep_h
sleep.quality          → DailyCheckin (new field)
hrv.rmssd              → DailyCheckin.hrv_rmssd
resting_heart_rate     → DailyCheckin.resting_hr
```

**Priority:** Medium-High (valuable recovery data)

---

### 🟡 Apple Health (via HealthKit)

**Application Status:** Not applicable (different approach)

**Requirements:**
1. ✅ Apple Developer Program membership ($99/year)
2. ✅ iOS app (React Native or native Swift)
3. ✅ Privacy policy explaining data use
4. ✅ HealthKit entitlement approval

**Implementation Approach:**
- Requires iOS companion app
- App reads HealthKit data locally
- Syncs to our backend via API
- Can access: workouts, sleep, HRV, resting HR, steps

**Priority:** High (large user base, valuable data)

**Alternative:** Terra API (https://tryterra.co/) - aggregates health data from multiple sources including Apple Health

---

### 🟡 MyFitnessPal

**Application Status:** Not yet applied

**Requirements for API Access:**
1. ✅ Business entity
2. ✅ Partnership application
3. ⚠️ MyFitnessPal has significantly restricted API access in recent years

**API Details:**
- **Status:** Limited availability (partnership only)
- **Alternative:** Users can manually export data or use CSV import

**Implementation Approach:**
- Consider implementing CSV import for nutrition data
- Users export from MFP → upload to our app
- Parse and store in NutritionEntry table

**Priority:** Medium (nutrition data valuable, but manual logging also works)

**Alternative:** 
- Cronometer API (more open)
- Manual nutrition entry (already implemented)

---

### 🟡 Intervals.icu

**Application Status:** Not yet applied

**Requirements:**
- More open API (simpler approval process)
- Developer API key

**API Details:**
- **Portal:** https://intervals.icu/api/v1/docs
- **Auth:** API key
- **Data Available:**
  - Activities
  - Wellness data (weight, sleep, HRV)
  - Training load
  - Fitness/fatigue calculations

**Priority:** Medium (overlaps with Strava, but adds wellness data)

---

### 🟡 Oura Ring

**Application Status:** Not yet applied

**Requirements:**
1. ✅ Developer account
2. ✅ App submission with data use explanation

**API Details:**
- **Portal:** https://cloud.ouraring.com/
- **Auth:** OAuth 2.0
- **Data Available:**
  - Readiness score
  - Sleep score
  - Sleep stages
  - HRV
  - Resting HR
  - Body temperature

**Priority:** Low-Medium (smaller user base, but high-quality data)

---

## Integration Priority Order

Based on user value and API accessibility:

1. **Garmin** - Large user base, comprehensive data (activities + recovery)
2. **Whoop** - Excellent recovery data, popular among serious athletes
3. **Apple Health** - Largest potential user base (requires iOS app)
4. **Coros** - Growing user base, good activity data
5. **Intervals.icu** - Easy API access, good training data
6. **MyFitnessPal/Cronometer** - Nutrition data (consider CSV import first)
7. **Oura** - Niche but high-quality recovery data

---

## Launch Checklist for Integration Applications

Before applying for APIs, ensure you have:

- [ ] **Business Entity:** LLC or Corporation registered
- [ ] **Live Website:** Production deployment at performancefocused.com (or similar)
- [ ] **Privacy Policy Page:** `/privacy` with comprehensive data handling explanation
- [ ] **Terms of Service Page:** `/terms` with legal terms
- [ ] **Contact Information:** Support email, business address
- [ ] **Product Description:** Clear explanation of how data is used
- [ ] **Screenshots:** UI showing where integration data appears

---

## Architecture Notes

The `apps/api/services/data_streams/` module is already prepared for new integrations:

1. **Create adapter class** in `data_streams/adapters/{platform}.py`
2. **Implement base interface** (sync, get_auth_url, exchange_code, etc.)
3. **Map to unified models** (UnifiedActivityData, UnifiedRecoveryData, etc.)
4. **Register in DataStreamRegistry**
5. **Add OAuth routes** in `routers/{platform}.py`
6. **Add webhook handler** (if supported)

No changes needed to:
- Correlation engine
- Efficiency calculations
- Frontend dashboards
- Activity analysis

The unified data models normalize all sources automatically.

---

## Current Workarounds (Pre-Launch)

While waiting for API access:

1. **Activities:** Strava provides all activity data needed
2. **Sleep/HRV:** Use DailyCheckin manual entry
3. **Nutrition:** Use Nutrition page manual entry
4. **Body Comp:** Use Body Composition manual entry
5. **Work Patterns:** Use WorkPattern manual entry

The correlation engine works with manual data. Automated sync just reduces friction.

---

**Last Updated:** January 2026


