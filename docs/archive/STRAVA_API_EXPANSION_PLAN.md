# Strava API Expansion Plan

## Executive Summary

StrideIQ currently operates in Strava's "Single Player Mode" (1 athlete capacity). To onboard additional users, we must apply for production API access through Strava's Developer Program. This document outlines the requirements, timeline, common pitfalls, and action plan based on deep research of official documentation and developer community experiences.

---

## Current State

| Metric | Current Value |
|--------|---------------|
| Athlete Capacity | 1 (owner only) |
| Rate Limit (15-min) | 200 requests |
| Rate Limit (daily) | 2,000 requests |
| App Status | Development/Personal |

---

## Strava's Official Process

### Timeline
- **Official estimate**: 7-10 business days
- **Real-world experience**: Highly variable (1 week to 3+ months)
- Developer forum reports show significant delays and lack of communication from Strava

### Submission Requirements

The [Developer Program Form](https://share.hsforms.com/1VXSwPUYqSH6IxK0y51FjHwcnkd8) requires:

1. **Basic Info**
   - First/Last Name
   - Email Address
   - Company Name
   - API Application Name
   - Strava Client ID

2. **Application Details**
   - Number of Users (currently authenticated)
   - Intended Audience (personal vs. other users)
   - Support URL
   - Application Description (how you use/display Strava data)

3. **Compliance Checkboxes**
   - ✅ API Brand Guidelines compliance
   - ✅ API Agreement (Terms of Service) compliance

4. **Screenshots** (CRITICAL)
   - All places Strava data is shown
   - "Connect with Strava" button
   - "Powered by Strava" or "Compatible with Strava" logos

---

## What Strava Evaluates

Based on the API Agreement (updated October 9, 2025) and developer experiences:

### Must-Have ✅

| Requirement | StrideIQ Status | Action Needed |
|-------------|-----------------|---------------|
| **Usefulness to athletes** | ✅ Yes - AI coaching, training insights | Document in application |
| **Non-competitive** | ⚠️ Review needed | Ensure we don't replicate core Strava features |
| **Privacy Policy** | ✅ Exists | Verify GDPR/UK GDPR compliance statements |
| **Terms of Service** | ✅ Exists | Verify Strava data handling terms |
| **Support URL** | ✅ Available | Link to /contact or support page |
| **Connect with Strava button** | ⚠️ Check | Must use official assets (orange or white, 48px) |
| **"Powered by Strava" logo** | ⚠️ Check | Must appear where Strava data is displayed |
| **HTTPS encryption** | ✅ Yes | Strava data encrypted in transit |
| **User-only data display** | ✅ Yes | Each user sees only their own data |
| **OAuth authentication** | ✅ Yes | Proper OAuth 2.0 flow implemented |

### Critical API Agreement Provisions

1. **No AI/ML Training**: Cannot use Strava data for model training
2. **No Data Sharing**: Cannot share user data with third parties without explicit consent
3. **No Selling Data**: Cannot sell, license, or monetize Strava data
4. **7-Day Cache Limit**: No Strava data can remain cached longer than 7 days
5. **48-Hour Deletion**: Must delete data within 48 hours of user deletion on Strava
6. **Respect Privacy Settings**: Must honor user's Strava privacy choices
7. **User Deauthorization**: Must delete all user data when they disconnect

### Red Flags That Cause Rejection

From developer forums:
- Replicating Strava functionality (activity feed, social features)
- Displaying other users' data (even if public on Strava)
- Missing or improper branding
- Vague application descriptions
- No clear value proposition for athletes
- Security concerns (credentials storage, unencrypted data)

---

## Developer Community Insights

### Common Frustrations

1. **Poor Communication**
   - Many developers report waiting weeks/months without any response
   - No automated status updates or tracking

2. **Hidden Process**
   - Link to apply not prominently displayed
   - Documentation scattered across multiple sites

3. **Inconsistent Timelines**
   - Some approved in 1 week, others wait 3+ months
   - No explanation for delays

### Success Factors (From Approved Developers)

1. **Complete Application**
   - All fields filled out thoroughly
   - Clear, specific application description

2. **Proper Branding**
   - Using official Strava assets correctly
   - "Powered by Strava" visible where data appears

3. **Webhooks Implementation**
   - Strava prefers apps that use webhooks over polling
   - Demonstrates efficient API usage

4. **Clear Value Proposition**
   - Explain exactly how the app benefits athletes
   - Show what makes it unique (not competing with Strava)

5. **Follow-Up**
   - Email developers@strava.com if no response in 10+ business days
   - Include Client ID in subject line

---

## StrideIQ Preparation Checklist

### Phase 1: Compliance Audit (Before Applying)

- [ ] **Privacy Policy Review**
  - Add Strava-specific data handling section
  - Include GDPR/UK GDPR compliance statements
  - Add statement about Strava monitoring/collecting usage data
  - State 7-day cache limit and 48-hour deletion policy

- [ ] **Terms of Service Review**
  - Disclaim warranties on behalf of third-party providers
  - Exclude third parties from consequential damages liability

- [ ] **Branding Compliance**
  - Download official [Connect with Strava buttons](https://developers.strava.com/downloads/1.1-Connect-with-Strava-Buttons.zip)
  - Download official [Strava API Logos](https://developers.strava.com/downloads/1.2-Strava-API-Logos.zip)
  - Replace any custom Strava buttons with official assets
  - Add "Powered by Strava" logo on:
    - Activity detail pages
    - Calendar view (where Strava activities appear)
    - Training load charts
    - Any page displaying Strava data

- [ ] **Technical Compliance**
  - Verify webhooks are implemented (not just polling)
  - Verify HTTPS on all endpoints
  - Verify token encryption
  - Verify user data isolation (no cross-user data leakage)
  - Verify deletion flow when user disconnects

### Phase 2: Screenshot Preparation

Prepare high-quality screenshots showing:

1. **Settings/Integrations Page**
   - "Connect with Strava" button (official asset)
   - Connected state with disconnect option

2. **Calendar Page**
   - Strava activities displayed
   - "Powered by Strava" or "View on Strava" attribution

3. **Activity Detail Page**
   - Individual activity data from Strava
   - Attribution link/logo

4. **Training Load/Analytics**
   - Charts derived from Strava data
   - Attribution visible

5. **AI Coach**
   - If discussing Strava activities, note data source

### Phase 3: Application Submission

**Recommended Application Description Template:**

```
StrideIQ is an AI-powered running coach that helps endurance athletes 
optimize their training through personalized insights and evidence-based 
coaching.

How we use Strava API:
- Sync running/cycling activities via OAuth and webhooks
- Display activity data (distance, pace, heart rate, elevation) to the 
  authenticated user only
- Calculate training load metrics (CTL/ATL/TSB) from activity data
- Provide AI coaching insights based on the user's own training patterns

Value to Strava Athletes:
- Personalized training insights beyond what Strava provides
- AI coaching that adapts to individual fitness levels
- Training load monitoring with evidence-based guidance
- Race prediction and goal planning

We do NOT:
- Share user data with third parties
- Display other users' data
- Compete with or replicate Strava core features
- Use data for AI/ML model training

All Strava data is encrypted, displayed only to the authenticated user, 
and deleted within 48 hours of user request or Strava deauthorization.
```

### Phase 4: Follow-Up Protocol

| Day | Action |
|-----|--------|
| 0 | Submit application |
| 10 | If no response, email developers@strava.com |
| 20 | Second follow-up email |
| 30 | Post on Developer Forum for visibility |
| 45+ | Consider direct outreach via LinkedIn to Strava developer relations |

**Follow-Up Email Template:**

```
Subject: API Production Access Request - Client ID: [YOUR_CLIENT_ID]

Hi Strava Developer Team,

I submitted our application "StrideIQ" for production API access on 
[DATE] but haven't received a response yet.

Client ID: [YOUR_CLIENT_ID]
Application: StrideIQ (AI Running Coach)
Submitted: [DATE]

Could you please provide an update on the review status?

We're an AI-powered running coach that helps athletes optimize their 
training. We've implemented webhooks, proper branding, and full GDPR 
compliance.

Thank you for your time,
[Your Name]
```

---

## Risk Mitigation

### If Approval is Delayed/Denied

1. **File Import Fallback** (Already Implemented)
   - ADR-057 established Garmin file import as a first-class integration
   - Users can export from Strava and import to StrideIQ manually
   - Less convenient but provides immediate value

2. **Garmin Direct Integration**
   - Separate priority: Garmin Health API reapplication
   - Provides alternative data source if Strava blocked

3. **Multi-Provider Strategy**
   - Coros, Polar, Suunto file import seams ready
   - Reduces single-provider dependency

### Potential Rejection Reasons & Responses

| Concern | StrideIQ Response |
|---------|-------------------|
| "Competes with Strava" | We complement Strava with AI coaching; we don't replicate social features, activity feed, or segments |
| "Data privacy concerns" | Full GDPR compliance, user-only data display, encryption, 48-hour deletion |
| "Insufficient value" | AI coaching, training load science, race prediction - features Strava doesn't offer |
| "Branding issues" | Will update to use official assets exactly as specified |

---

## Timeline Estimate

| Phase | Duration | Owner Action |
|-------|----------|--------------|
| Compliance Audit | 2-3 hours | Review privacy policy, ToS, branding |
| Screenshot Preparation | 1 hour | Capture required screens |
| Application Submission | 30 min | Complete form |
| Initial Response | 7-10 business days | Wait |
| Follow-Up (if needed) | Every 10 days | Email developers@strava.com |
| **Total (optimistic)** | 2-3 weeks | |
| **Total (realistic)** | 4-8 weeks | |

---

## Immediate Next Steps

1. **Today**: Review current Privacy Policy and Terms of Service
2. **Today**: Check all Strava-related UI for proper branding
3. **Tomorrow**: Prepare screenshots
4. **Tomorrow**: Submit application
5. **Day 10**: Follow up if no response

---

## Related Documents

- [Strava API Agreement](https://www.strava.com/legal/api) (Updated October 9, 2025)
- [Strava Brand Guidelines](https://developers.strava.com/guidelines) (Updated September 29, 2025)
- [Developer FAQs](https://partners.strava.com/developers/developers-faqs)
- [Rate Limits Documentation](https://developers.strava.com/docs/rate-limits/)
- [Developer Forum](https://communityhub.strava.com/t5/developer-discussions/bd-p/developer-discussions)
- ADR-057: Provider Expansion via File Import (local fallback strategy)

---

## Contacts

- **Strava Developer Support**: developers@strava.com
- **Developer Forum**: https://communityhub.strava.com/t5/developer-discussions/bd-p/developer-discussions

---

*Last Updated: January 29, 2026*
