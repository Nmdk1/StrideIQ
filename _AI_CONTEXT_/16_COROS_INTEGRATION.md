# COROS API Integration

## Overview

COROS integration enables syncing workout data and pushing structured training plans to COROS watches.

**Status:** 🟡 **API Application Submitted** (February 1, 2026)

## Application Details

| Field | Value |
|-------|-------|
| Application Date | February 1, 2026 |
| Company | StrideIQ |
| Contact Email | michael@strideiq.run |
| Backup Email | mbshaf@gmail.com |
| Application Name | StrideIQ |

## Requested API Functions

- ✅ Activity/Workout Data Sync
- ✅ Structured Workouts and Training Plans Sync

## Technical Configuration

| Endpoint | URL |
|----------|-----|
| Callback Domain | https://strideiq.run |
| Webhook Endpoint | https://strideiq.run/v1/webhooks/coros |
| Health Check | https://strideiq.run/health |

## Application Description (Submitted)

> AI running coach that analyzes your training data to optimize performance and prevent injury.

## Data Usage Statement (Submitted)

> User workout data (runs, GPS, heart rate, pace) is synced to provide AI-powered coaching insights, training load analysis, race predictions, and personalized training plan recommendations. Data is stored securely and only accessible to the authenticated user. We do not sell or share user data with third parties.

## Required Assets

### Logo Images (Required)

| Size | Purpose | Status |
|------|---------|--------|
| 144px × 144px | Partner page | ⏳ Pending |
| 102px × 102px | Partner page | ⏳ Pending |
| 120px × 120px | Workout sync (if applicable) | ⏳ Pending |
| 300px × 300px | Workout sync (if applicable) | ⏳ Pending |

**Email to:** api@coros.com  
**Subject:** StrideIQ - API Images

## Next Steps

1. ⏳ Wait for COROS to issue Client ID and API Keys
2. ⏳ Send logo images to api@coros.com
3. ⏳ Implement OAuth flow when credentials received
4. ⏳ Build webhook endpoint for workout data push
5. ⏳ Test integration with COROS watch
6. ⏳ Notify COROS 1 week before go-live

## Implementation Plan (Post-Approval)

### Phase 1: OAuth Flow
- Implement COROS OAuth 2.0 authentication
- Add COROS connection to Settings page
- Store tokens securely (encrypted)

### Phase 2: Activity Sync
- Implement webhook receiver for workout data push
- Parse COROS activity format
- Deduplicate with existing Strava/Garmin activities

### Phase 3: Training Plan Push
- Build structured workout format for COROS
- Push training plans to COROS servers
- Sync workout completion status back

## API Reference

COROS API Reference Guide: [Link provided in application email]

## Press Release Materials (Submitted)

### Quote from Founder

> "Runners deserve coaching that actually understands them. By integrating with COROS, we're giving athletes access to AI-powered insights built on the precise data that COROS watches capture. This partnership means runners can finally see what's actually driving their performance—and what's holding them back."
>
> — Michael Shaffer, Founder, StrideIQ

### About StrideIQ

> StrideIQ is an AI-powered running intelligence platform that transforms training data into actionable coaching insights. Unlike generic training apps, StrideIQ uses advanced algorithms to analyze the correlations between sleep, nutrition, training load, and performance—showing runners exactly what works for their unique physiology. The platform features personalized training plans, real-time coaching conversations, race predictions, and performance analytics trusted by runners from first-timers to Boston qualifiers. Founded by a lifelong runner who wanted coaching that adapts to real life, StrideIQ is built on the belief that every runner deserves the insights that elite athletes take for granted.

## Files to Create (When Approved)

- `apps/api/routers/coros.py` - API endpoints
- `apps/api/services/coros_service.py` - COROS API service
- `apps/api/routers/coros_webhook.py` - Webhook receiver
- `apps/web/app/settings/coros/page.tsx` - Settings UI

## Notes

- No fee for API integration
- COROS may provide test unit for Bluetooth/ANT+ (not needed for API-only)
- Must notify COROS 1 week before launch
- Must add Login Portal and Support Page for users
