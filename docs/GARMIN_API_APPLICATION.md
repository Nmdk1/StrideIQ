# Garmin Activity API Application Preparation

**Status:** SUBMITTED  
**Submitted:** 2026-01-30  
**Expected Response:** ~Feb 3, 2026 (2 business days)  
**Priority:** High (parallel with Strava approval process)

---

## Application Overview

### Program Details
- **Program**: Garmin Connect Developer Program (Activity API)
- **Cost**: Free for approved business developers
- **Turnaround**: ~2 business days for confirmation
- **Integration Timeline**: 1-4 weeks after approval
- **Application URL**: https://www.garmin.com/en-US/forms/GarminConnectDeveloperAccess/

### What's Included Upon Approval
- API documentation
- Secure development access to production environment
- Sample integration code
- Direct support from Developer Program team
- Garmin Connect branding materials
- Evaluation environment for testing
- **Full FIT file access** (complete activity details)

---

## Pre-Application Checklist

### Compliance Pages (COMPLETE)
- [x] **Privacy Policy**: https://strideiq.run/privacy
  - Updated: January 29, 2026
  - Includes Garmin Connect data handling section
  - Specifies data types collected (activities, health metrics, sleep, HRV)
  - Clear "We do NOT" section (no selling, sharing, AI training)
  - GDPR compliant with deletion/export rights

- [x] **Terms of Service**: https://strideiq.run/terms
  - Updated: January 29, 2026
  - Section 5.2 specifically covers Garmin Connect integration
  - Links to Garmin's Terms of Service
  - Clear user authorization language

- [x] **Support Page**: https://strideiq.run/support
  - Contact form/email available
  - FAQ section

### Technical Readiness (COMPLETE)
- [x] **Provider abstraction architecture** (ADR-057)
  - Unified data model supports multiple providers
  - `Activity` model has `provider` + `external_activity_id` uniqueness
  - Deduplication logic for cross-provider activities

- [x] **OAuth infrastructure ready**
  - Token encryption service exists (`services/token_encryption.py`)
  - Strava OAuth pattern can be replicated for Garmin

- [x] **File import fallback** (Phase 7 complete)
  - Garmin DI_CONNECT import already works
  - Users can import manually while API approval pending

### Business Information (REQUIRED FOR APPLICATION)

The application form requires:

| Field | Value | Status |
|-------|-------|--------|
| Company Name | StrideIQ | Ready |
| Business Type | Software/SaaS | Ready |
| Business Address | [OWNER: Add registered address] | NEEDED |
| Contact Email | [OWNER: Primary contact email] | NEEDED |
| Contact Phone | [OWNER: Contact phone] | NEEDED |
| Primary Sales Region | United States | Ready |
| Website URL | https://strideiq.run | Ready |
| Privacy Policy URL | https://strideiq.run/privacy | Ready |
| Terms of Service URL | https://strideiq.run/terms | Ready |

---

## Application Form Responses (Draft)

### Company Description
> StrideIQ is an AI-powered running analytics platform that provides personalized coaching insights based on individual athlete data. We use efficiency trend analysis (pace at heart rate), age-graded performance metrics, and correlation discovery to help runners of all ages optimize their training.

### Intended Use of Activity API
> We will use the Activity API to sync running activities from users' Garmin devices. This includes activity details (distance, duration, pace, elevation), heart rate data, power metrics, and splits. This data powers our N=1 (individual-only) analysis engine that calculates efficiency trends (pace at heart rate), age-graded performance, and personal records. No population modeling or data aggregation occurs.

### Target Market/Users
> Recreational and competitive runners of all ages who want data-driven insights about their training. Our platform specifically serves masters athletes (40+) and rejects age-based assumptions in favor of individual pattern discovery.

### Data Usage Statement
> User data is used exclusively to provide personalized insights to that individual user. We do not sell, share, or aggregate user data. We do not use user data to train AI models. Users can delete or export their data at any time per GDPR requirements.

### Expected User Volume
> Initial launch: 50-300 users  
> 12-month target: 1,000-5,000 users

### Technical Integration Plan
> REST API integration using ping/pull architecture. We will subscribe to activity uploads and retrieve FIT files for complete activity details. OAuth 2.0 for user authorization with encrypted token storage. We have existing infrastructure for Strava OAuth that will be replicated for Garmin.

---

## Activity API Data Points We Need

### Core Data (Activity API)
| Metric | Use Case |
|--------|----------|
| **Activity Details** | Distance, duration, pace, elevation, activity type |
| **Heart Rate** | Avg/max HR, HR zones for efficiency analysis |
| **Splits/Laps** | Per-mile/km breakdown for pacing analysis |
| **Power** | Running power for advanced efficiency metrics |
| **Cadence** | Steps per minute for form analysis |
| **GPS/Route** | Elevation gain, terrain context |
| **FIT Files** | Complete raw data for detailed analysis |

### Activity Types Supported
- Running (primary focus)
- Trail running
- Treadmill
- Track running
- Walking (for cross-training context)

### Future Consideration (Separate Application)
| API | Use Case | When |
|-----|----------|------|
| **Health API** | Sleep, HRV, stress, body battery | Tier 4 premium features |
| **Training API** | Push workouts to device | If users request |

---

## Post-Approval Implementation Plan

### Phase 1: OAuth Setup (Days 1-3)
1. Register OAuth client in Garmin Developer Portal
2. Implement Garmin OAuth flow (mirror Strava pattern)
3. Add `garmin_access_token`, `garmin_refresh_token` to Athlete model
4. Create `/v1/garmin/connect` and `/v1/garmin/disconnect` endpoints

### Phase 2: Activity Sync (Days 4-10)
1. Implement activity notification handling (ping/pull)
2. Retrieve FIT files for complete activity data
3. Parse FIT files using existing FIT SDK patterns
4. Map Garmin activity data to canonical `Activity` model
5. Add deduplication against existing Strava activities
6. Test with owner's Garmin account

### Phase 3: Push Notifications (Days 11-14)
1. Set up push notification endpoints for real-time sync
2. Handle activity upload events
3. Reduce polling overhead

### Future: Health API (Separate Application)
- Apply for Health API when ready for Tier 4 premium features
- Sleep, HRV, stress, body battery for recovery correlation

---

## Risk Mitigation

### If Application Rejected
1. **File Import** (already works): Users can export from Garmin Connect and upload
2. **Reapply with more details**: Address any specific concerns
3. **Strava remains primary**: Core product works without Garmin API

### If Approval Delayed
1. Continue with Strava + file import
2. Communicate clearly to users about data source options
3. Prioritize other launch readiness tasks

---

## Related Documents
- `docs/adr/ADR-057-provider-expansion-file-import-garmin-coros.md`
- `_AI_CONTEXT_/15_GARMIN_INTEGRATION.md`
- `docs/SECURITY_SECRETS.md` (token handling)

---

## Action Items

### Owner Actions
- [x] ~~Confirm business registration details (address, entity name)~~
- [x] ~~Confirm primary contact information for application~~
- [x] ~~Review application form responses~~
- [x] ~~Submit application~~ - **DONE 2026-01-30**
- [ ] Wait for Garmin confirmation (~2 business days)
- [ ] If approved: Form Wyoming LLC before production launch

### Technical Actions (Post-Approval)
- [ ] Set up Garmin OAuth credentials in `.env`
- [ ] Implement OAuth flow following Strava pattern
- [ ] Add Garmin connect/disconnect UI to Settings
- [ ] Implement activity sync worker
- [ ] Implement health metrics sync
- [ ] Add feature flag: `integrations.garmin_oauth_v1`

---

## Timeline

| Milestone | Target Date | Status |
|-----------|-------------|--------|
| Submit application | Jan 30, 2026 | **DONE** |
| Garmin confirmation | ~Feb 3, 2026 | Waiting (~2 business days) |
| OAuth integration | Feb 10, 2026 | After approval |
| Activity sync complete | Feb 14, 2026 | Testing with owner account |
| Public beta release | March 15, 2026 | Launch target |
