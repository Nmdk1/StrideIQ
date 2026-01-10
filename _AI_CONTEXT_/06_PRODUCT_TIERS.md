# PRODUCT TIERS & MONETIZATION STRATEGY

**Last Updated:** Jan 4, 2026  
**Status:** Product Strategy Defined

## Overview

The Performance Physics Engine operates as a freemium multi-tiered service, designed to convert free users through demonstrated value into paying subscribers.

## Tier Structure

### Tier 1: Free Landing Page & Tools
**Monetization:** Free  
**Purpose:** Acquisition funnel and value demonstration

**Features:**
- **VDOT Pace Calculator** - Free tool for runners to calculate training paces based on recent race times
- Age-grading calculator (free tool)
- Pace converter (free tool)
- Public content and resources
- Lead generation forms

**Conversion Goal:** Free tools → Fixed plans or subscription

---

### Tier 2: Fixed Training Plans
**Monetization:** One-time purchase per plan  
**Purpose:** Low-barrier entry point and conversion hook

**Features:**
- Pre-built training plans for specific race distances/goals
- Plans are "fixed" (not dynamically adjusted) but tailored to user's current fitness
- Race preparation focus (5K, 10K, Half Marathon, Marathon)
- Entry-level coaching guidance
- Basic progress tracking

**Pricing:** $X per plan (TBD)

**Conversion Goal:** Fixed plans → Guided self-coaching subscription

**Strategy:** 
- Demonstrate coaching quality and value
- Show users what personalized coaching can do
- Use as proof point for subscription value

---

### Tier 3: Guided Self-Coaching Subscription
**Monetization:** Monthly/annual subscription ($15/month)  
**Purpose:** Core subscription revenue

**Features:**
- **Full Diagnostic Engine Access:**
  - Efficiency Trend Signal (Master Signal)
  - Performance Stability metrics
  - Load → Response Mapping
  - PB Probability Modeling
- **Activity-Based Insights:**
  - Pace @ HR trends
  - HR @ Pace trends
  - Age-graded performance tracking
  - Race detection and analysis
- **Policy-Based Coaching:**
  - Performance Maximal, Durability First, Re-Entry policies
  - Continuous feedback loop (Observe-Hypothesize-Intervene-Validate)
- **Activity-Based Correlation Engine:**
  - Intensity distribution vs PB probability
  - Volume patterns vs efficiency
  - Training load vs adaptation
- **All Tier 2 Features:**
  - Access to fixed plans (included or discounted)

**Data Access:** Strava integration + activity data only

**Pricing:** $15/month or annual (TBD)

**Conversion Goal:** Guided self-coaching → Premium guided self-coaching

---

### Tier 4: Premium Guided Self-Coaching Subscription
**Monetization:** Premium monthly/annual subscription ($25/month)  
**Purpose:** Premium insights and advanced recovery analytics

**Features:**
- **ALL Tier 3 Features PLUS:**
- **Advanced Recovery Insights:**
  - Sleep vs next-day efficiency correlations
  - HRV vs recovery slope correlations
  - Resting heart rate trends vs performance
  - Stress vs recovery correlations
- **Garmin/Coros Integration:**
  - Full access to wearable data
  - Automatic data sync
  - Multi-device support
- **Recovery-Based Correlation Engine:**
  - Time-shifted correlations (sleep → efficiency, HRV → recovery)
  - Personal recovery curves learned from individual data
  - Recovery elasticity with recovery metrics
- **Advanced Negative Signal Detection:**
  - False fitness detection using recovery metrics
  - Masked fatigue detection with HRV/HR data
- **Premium Visualizations:**
  - Recovery trend charts
  - Sleep-performance correlation graphs
  - HRV analysis dashboards

**Data Access:** Full Garmin/Coros integration + all recovery metrics

**Pricing:** $25/month or annual (TBD)

**Paywall Strategy:**
- Garmin/Coros data collected for all users (when available) to improve models
- Advanced insights derived from recovery data are **paywalled** - only Tier 4 sees them
- Lower tiers benefit from improved models but don't see recovery-specific insights

---

## Data Collection vs. Data Access

**Critical Distinction:**

1. **Data Collection (All Tiers):**
   - System collects Garmin/Coros data when available (post-launch)
   - Data used internally to improve models and insights
   - Benefits all tiers through better algorithms

2. **Data Access (Tier-Specific):**
   - Tier 3: Activity data only (Strava)
   - Tier 4: Full recovery data access + insights

**Implementation:**
- Collect recovery data for all users (when Garmin/Coros available)
- Use data to improve internal models
- Only serve recovery-specific insights to Tier 4
- Lower tiers see improved activity-based insights but not recovery correlations

---

## Conversion Funnel

```
Free Tools (VDOT Calculator)
    ↓
Fixed Training Plans (One-Time Purchase)
    ↓
Guided Self-Coaching Subscription (Tier 3)
    ↓
Premium Guided Self-Coaching Subscription (Tier 4)
```

**Conversion Points:**
1. **Free → Fixed Plans:** Demonstrate value through free tools
2. **Fixed Plans → Subscription:** Show coaching quality, convert to recurring revenue
3. **Tier 3 → Tier 4:** Upsell advanced recovery insights

---

## Technical Implementation Requirements

### Database Schema
- `subscription_tier` field on `Athlete` model (already exists: 'free', 'guided', 'premium')
- `plan_purchases` table (one-time purchases)
- `subscriptions` table (recurring subscriptions)
- `payment_history` table

### Feature Gating
- Middleware/decoration for tier-based access control
- API endpoints check subscription tier
- Frontend conditionally renders features based on tier

### Payment Processing
- Stripe or PayPal integration
- One-time purchases (fixed plans)
- Recurring subscriptions (Tier 3 & 4)
- Subscription management (upgrade/downgrade/cancel)

### Free Tools
- VDOT Pace Calculator (standalone, no auth required)
- Age-grading calculator (standalone)
- Pace converter (standalone)

---

## Launch Strategy

**Pre-Launch (Phase 2-3):**
- Build landing page with VDOT calculator
- Create fixed training plans
- Set up subscription system
- Implement tier-based feature gating

**Launch (March 15, 2026):**
- Free tier: Landing page + VDOT calculator
- Fixed plans: Available for purchase
- Tier 3: Guided coaching subscription (Strava-based)
- Tier 4: Premium coaching (when Garmin/Coros API access granted)

**Post-Launch:**
- Apply for Garmin/Coros API access
- Integrate recovery data collection
- Build recovery correlation engine
- Enable Tier 4 premium features

---

## Pricing Strategy (To Be Determined)

**Fixed Plans:** $X per plan
- Consider: $19.99, $29.99, $39.99 per plan
- Bundle discounts (e.g., 3 plans for $X)

**Tier 3 - Guided Self-Coaching:** $15/month or annual
- Annual discount: ~15-20%

**Tier 4 - Premium Guided Self-Coaching:** $25/month or annual
- Annual discount: ~15-20%
- Premium over Tier 3: ~2x pricing

**Market Research Needed:**
- Competitive analysis (TrainingPeaks, Final Surge, etc.)
- Value proposition testing
- Willingness to pay research

---

## Success Metrics

**Acquisition:**
- Free tool usage (VDOT calculator)
- Landing page conversion rate
- Fixed plan purchase rate

**Conversion:**
- Fixed plan → Subscription conversion rate
- Tier 3 → Tier 4 upgrade rate
- Monthly recurring revenue (MRR)
- Customer lifetime value (LTV)

**Retention:**
- Monthly churn rate
- Annual subscription retention
- Feature usage by tier

