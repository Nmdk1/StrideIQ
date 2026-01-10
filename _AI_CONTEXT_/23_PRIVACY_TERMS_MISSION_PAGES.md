# Privacy Policy, Terms of Service, and Mission Statement Pages

**Date:** January 5, 2026  
**Status:** ✅ Complete - Ready for Garmin API Application

## Overview

Built world-class Privacy Policy, Terms of Service, and Mission Statement pages to meet Garmin's requirements for official OAuth API access. These pages are critical for unlocking Garmin/Coros integration.

## Requirements Analysis

Based on research of Garmin's and Strava's privacy policy requirements:

### Garmin Requirements:
1. **Clear Privacy Policy** that complies with all applicable laws
2. **Data Attribution**: Must attribute Garmin when displaying Garmin-sourced data
3. **Data Retention**: Only as long as necessary unless user gives express consent
4. **Location Data**: Must not default to collecting, users must opt-in
5. **Clear Statement**: Data submitted is to YOUR application, not to Garmin
6. **Garmin Liability Disclaimer**: Must state Garmin has no responsibility/liability

### Strava Requirements:
- Similar transparency and compliance standards
- Clear data usage policies
- User rights (GDPR/CCPA compliance)

## Implementation

### 1. Privacy Policy Page (`/privacy`) ✅

**Key Sections:**
- **Introduction**: Clear statement that data goes to us, not Garmin/Strava
- **Data We Collect**: 
  - Activity data (distance, pace, HR, power, splits)
  - Recovery metrics (Premium tier: sleep, HRV, resting HR)
  - Profile information
  - Location data (opt-in only, clearly stated)
- **How We Use It**: Personalize training, analyze efficiency, never sell
- **Data Storage & Security**: Encrypted at rest/transit, secure providers
- **Data Retention**: Only as long as necessary (Garmin requirement)
- **User Rights**: Access, delete, export (GDPR/CCPA compliance)
- **Third Parties**: Stripe (payments), analytics (anonymous)
- **Data Attribution**: Garmin attribution statement (required)
- **Children's Privacy**: Not for users under 13
- **Changes to Policy**: How updates are communicated

**Tone**: Transparent, respectful, runner-focused
- "We only collect what's needed to make your training smarter"
- "We never sell your data"
- Clear, readable language (not dense legalese)

### 2. Terms of Service Page (`/terms`) ✅

**Key Sections:**
- **Agreement to Terms**: Clear acceptance language
- **Description of Service**: What we provide
- **Subscriptions & Payments**: 
  - Subscription tiers explained
  - Payment terms (Stripe)
  - Cancellation policy
- **Refund Policy**: 
  - Fixed plans: 7-day refund if not started
  - Subscriptions: Non-refundable (with exceptions)
- **No Guaranteed Results**: Standard disclaimer (honest and fair)
- **Acceptable Use**: What users can/cannot do
- **Intellectual Property**: 
  - Our content ownership
  - User data ownership
  - Garmin data attribution (required)
- **Third-Party Services**: Strava, Garmin, Coros, Stripe
- **Limitation of Liability**: Standard protections with training disclaimer
- **Termination**: Account suspension/termination terms
- **Changes to Terms**: How updates are communicated
- **Governing Law**: US jurisdiction

**Tone**: Honest, fair, professional

### 3. Mission Statement Page (`/mission`) ✅

**Content**: Full manifesto text formatted beautifully

**Design Features:**
- Hero section with subtle background image (dawn trail)
- Founder quote prominently displayed
- Generous spacing and elegant typography
- Dark mode consistent with site
- Sections:
  - Core Philosophy
  - Product Logic
  - Primary Trend Signals
  - Secondary Signals
  - Correlation Engines
  - PB Probability Modeling
  - Early Warnings
  - What This Enables
  - AI-Powered Coaching
  - Taxonomy (The New Masters)
  - Key Metrics
  - The Coaching Process

**Layout**: Clean, readable, professional

### 4. Footer Updates ✅

Updated Footer component to include:
- Quick Links section (existing)
- **New Legal section** with links to:
  - Privacy Policy (`/privacy`)
  - Terms of Service (`/terms`)
- Mission Statement link (existing)
- Contact section (existing)

Footer now appears on all pages (landing, privacy, terms, mission)

## Technical Implementation

### Files Created:
1. ✅ `apps/web/app/privacy/page.tsx` - Privacy Policy page
2. ✅ `apps/web/app/terms/page.tsx` - Terms of Service page
3. ✅ `apps/web/app/mission/page.tsx` - Mission Statement page
4. ✅ `apps/web/app/components/Footer.tsx` - Updated with Legal links

### Styling:
- Tailwind CSS (dark mode)
- Consistent with landing page aesthetic
- Mobile-responsive
- Accessible (semantic HTML, proper headings)
- Professional typography and spacing

### Garmin Compliance Checklist:

✅ **Privacy Policy Requirements:**
- ✅ Clear statement that data goes to us, not Garmin
- ✅ Garmin liability disclaimer included
- ✅ Data retention policy (only as long as necessary)
- ✅ Location data opt-in requirement stated
- ✅ Complies with applicable laws (GDPR/CCPA mentioned)
- ✅ User rights clearly stated
- ✅ Security measures described
- ✅ Third-party sharing transparent

✅ **Terms of Service Requirements:**
- ✅ Garmin data attribution statement included
- ✅ Compliance with Garmin's API terms acknowledged
- ✅ User responsibilities defined
- ✅ Intellectual property clarified
- ✅ Limitation of liability included
- ✅ Termination conditions stated

## Status

✅ **Complete** - All three pages built and deployed
- Privacy Policy: `/privacy` ✅
- Terms of Service: `/terms` ✅
- Mission Statement: `/mission` ✅
- Footer updated with Legal links ✅
- All pages mobile-responsive and accessible ✅
- Build successful, deployed to production ✅

## Next Steps

1. **Review**: User will review pages when back (~2 hours)
2. **Garmin Application**: Once approved, can apply for official Garmin OAuth API access
3. **Coros Application**: Similar process for Coros API access
4. **Legal Review**: Consider professional legal review before launch (recommended)

## Notes

- Privacy Policy specifically addresses Garmin's requirements
- Terms include Garmin data attribution as required
- Language is clear and readable (not dense legalese)
- Pages match site aesthetic (dark mode, professional)
- All pages accessible and mobile-friendly

---

**Ready for Garmin API Application** 🚀

