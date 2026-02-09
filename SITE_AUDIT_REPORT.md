# Site Audit Report: Performance Focused Coaching System

**Date:** January 7, 2026  
**Auditor:** Lead Engineer  
**Site:** localhost:3000 (pre-production)

---

## Executive Summary

The foundation is **solid**. The codebase is well-architected, the correlation engine is genuinely innovative, and the free tools provide real value. However, several gaps need addressing before inviting beta users. The good news: **most fixes are quick and don't require expensive infrastructure.**

**Launch Recommendation:** **Launch now for closed beta.** Don't wait for perfection. You have enough to validate the product with real users. The correlation engine needs real data to prove itself, and beta users will provide that.

---

## 1. UX Audit

### ✅ What's Working
- **Morning Check-in** (`/checkin`) - Ultra-fast, friction-free design. Perfect.
- **Free Tools** - RPI, WMA, Running Economy, Heat-Adjusted Pace. Real value, no signup required.
- **Navigation** - Clean, responsive, auth-aware

### ⚠️ Issues to Fix

#### A. Navigation Overload (Logged In)
**Problem:** 10+ nav items when logged in. Overwhelming.

**Fix:**
```
Primary Nav: Check-in | Dashboard | Discovery | Activities
Dropdown Menu: Settings, Nutrition, Availability, Profile
Admin: Only for admin/owner roles (already correct)
```

**Priority:** Medium | **Effort:** 1-2 hours

#### B. Empty State Experience
**Problem:** New users see "Insufficient data" on Dashboard/Discovery. Feels broken.

**Fix:** Create welcoming empty states that:
- Explain what they'll see once data is collected
- Show sample/demo data (grayed out)
- Link to Strava connection
- Maintain tone: "No activities yet. Connect Strava. Data flows. Insights follow."

**Priority:** HIGH | **Effort:** 2-3 hours

#### C. Onboarding Flow
**Current:** Multi-step wizard at `/onboarding`
**Issue:** Users might skip Strava connection, which is critical

**Fix:** 
- Make Strava connection the hero action (step 2, right after name)
- Show clear value: "Connect Strava → We analyze your history → Insights in minutes"
- Add progress indicator persistence

**Priority:** HIGH | **Effort:** 1-2 hours

#### D. First-Run Experience
**Problem:** After registration, users land on Activities (empty). Confusing.

**Fix:** 
1. Registration → Onboarding → Dashboard (not Activities)
2. Dashboard shows "Getting started" card if no activities

**Priority:** Medium | **Effort:** 1 hour

---

## 2. Performance Audit

### ✅ What's Working
- Next.js 14 with `standalone` output - Good for containerization
- React Query for caching
- Redis caching layer implemented
- N+1 queries fixed

### ⚠️ Issues to Fix

#### A. Image Optimization
**Problem:** Hero background uses external Unsplash URL. No optimization.

**Fix:**
```tsx
// Use next/image with blur placeholder
import Image from 'next/image'
// Or host locally and optimize
```

**Priority:** Low | **Effort:** 30 min

#### B. Bundle Size
**Problem:** Recharts is heavy (~500KB). Loaded on pages that may not need charts.

**Fix:** Dynamic imports:
```tsx
const EfficiencyChart = dynamic(
  () => import('@/components/dashboard/EfficiencyChart'),
  { loading: () => <ChartSkeleton /> }
)
```

**Priority:** Low | **Effort:** 1 hour

#### C. API Response Time
**Current:** No compression, no edge caching

**Fix for Production:**
- Enable gzip/brotli compression
- Add CDN (Cloudflare free tier)
- API cache headers for static-ish endpoints

**Priority:** Medium (for production) | **Effort:** 1-2 hours

---

## 3. Mobile Responsiveness Audit

### ✅ What's Working
- Tailwind responsive classes used throughout
- Mobile nav hamburger menu
- Grid layouts adapt

### ⚠️ Issues to Fix

#### A. Free Tools Cards
**Problem:** 4-column grid on large screens → 1 column on mobile. Cards get very long.

**Fix:** 
- `lg:grid-cols-4` → `md:grid-cols-2 lg:grid-cols-4`
- Consider accordion or tabs on mobile

**Priority:** Medium | **Effort:** 1 hour

#### B. Dashboard Charts
**Problem:** Recharts ResponsiveContainer is good, but legends may overflow on small screens.

**Fix:** Hide legend on mobile, show summary below chart instead

**Priority:** Low | **Effort:** 30 min

#### C. Check-in Page
**Status:** ✅ Already mobile-optimized (sliders work well on touch)

#### D. Navigation Scroll
**Problem:** Mobile nav dropdown may not scroll on very small screens if many items

**Fix:** Add `max-h-[calc(100vh-4rem)] overflow-y-auto` to mobile menu

**Priority:** Low | **Effort:** 15 min

---

## 4. Tone Consistency Audit

### ✅ Compliant
- Morning Check-in page - Good
- Nutrition page - Verified compliant
- Discovery sections - "What's Working" / "What Doesn't Work" - Perfect tone

### ⚠️ Violations Found

#### A. Hero Section
**Current:** "Personal bests. Running faster at lower heart rates."
**Status:** ✅ Good - Direct, sparse

#### B. Pricing Section  
**Current:** "Start free. Upgrade when you're ready for more."
**Status:** ✅ Acceptable

#### C. Error Messages (verify all)
**Ensure:** No "Oops!" or "We're sorry!" - Use direct language

**Action:** Audit all error states against TONE_GUIDE.md

**Priority:** Low | **Effort:** 1 hour

---

## 5. SEO Audit

### 🔴 Critical Missing Items

#### A. robots.txt - MISSING
**Create:** `apps/web/public/robots.txt`
```
User-agent: *
Allow: /
Disallow: /api/
Disallow: /admin/
Disallow: /dashboard/
Disallow: /activities/
Disallow: /checkin/
Disallow: /settings/
Disallow: /profile/

Sitemap: https://yourdomain.com/sitemap.xml
```

**Priority:** HIGH | **Effort:** 5 min

#### B. sitemap.xml - MISSING
**Create:** `apps/web/app/sitemap.ts`
```typescript
import { MetadataRoute } from 'next'

export default function sitemap(): MetadataRoute.Sitemap {
  const baseUrl = process.env.NEXT_PUBLIC_BASE_URL || 'https://yourdomain.com'
  
  return [
    { url: baseUrl, lastModified: new Date(), changeFrequency: 'weekly', priority: 1 },
    { url: `${baseUrl}/mission`, lastModified: new Date(), changeFrequency: 'monthly', priority: 0.8 },
    { url: `${baseUrl}/#tools`, lastModified: new Date(), changeFrequency: 'monthly', priority: 0.9 },
    { url: `${baseUrl}/#pricing`, lastModified: new Date(), changeFrequency: 'monthly', priority: 0.7 },
  ]
}
```

**Priority:** HIGH | **Effort:** 15 min

#### C. Meta Tags - INSUFFICIENT
**Current:**
```tsx
title: 'Performance Focused Coaching System'
description: 'Complete health and fitness management...'
```

**Improved:**
```tsx
export const metadata: Metadata = {
  title: {
    default: 'Performance Focused Coaching System | Running Efficiency Analytics',
    template: '%s | Performance Focused Coaching'
  },
  description: 'Discover what actually improves your running. Track efficiency correlations between sleep, nutrition, and performance. Free RPI calculator, age-grading tools, and AI-powered coaching.',
  keywords: [
    'running efficiency',
    'runner performance analytics',
    'running correlation analysis',
    'personal running insights',
    'RPI calculator',
    'age graded running',
    
    'heat adjusted pace',
    'masters running',
    'efficiency factor running',
    'running coach app',
    'Strava analytics'
  ],
  authors: [{ name: 'Michael Shaffer' }],
  creator: 'Performance Focused Coaching',
  openGraph: {
    type: 'website',
    locale: 'en_US',
    url: 'https://yourdomain.com',
    siteName: 'Performance Focused Coaching',
    title: 'Running Efficiency Analytics | Performance Focused Coaching',
    description: 'Discover what actually improves your running. Correlate sleep, nutrition, and training with performance outcomes.',
    images: [{ url: '/og-image.png', width: 1200, height: 630 }]
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Running Efficiency Analytics',
    description: 'Discover what actually improves your running.',
    images: ['/og-image.png']
  },
  robots: {
    index: true,
    follow: true
  }
}
```

**Priority:** HIGH | **Effort:** 30 min

#### D. Page-Specific Meta Tags
Each page needs its own metadata. Currently missing:
- `/mission` - needs meta
- Tool pages (if separate routes exist)

**Priority:** Medium | **Effort:** 1 hour

#### E. Structured Data (Schema.org) - MISSING
Add JSON-LD for:
- Organization
- SoftwareApplication
- FAQ (on landing page)

**Priority:** Medium | **Effort:** 1 hour

---

## 6. Keyword Optimization

### Target Keywords (by intent)

#### High-Intent (Bottom Funnel):
- "running coach app"
- "running analytics app"  
- "Strava analytics alternative"

#### Discovery (Top Funnel):
- "personal running insights"
- "runner efficiency correlations" ← Your unique differentiator

- "RPI calculator" ← You have this!
- "age graded running calculator" ← You have this!
- "heat adjusted pace calculator" ← You have this!

#### Long-Tail (Blog Content for later):
- "how to improve running efficiency"
- "what affects running performance"
- "running pace at heart rate zones"
- "masters runner training"

### Content Gaps
**You have great tools but no explanatory content around them.**

Consider adding (POST-LAUNCH):
- `/tools/rpi-calculator` with full SEO page explaining RPI
- `/tools/age-grading` with explanation of WMA standards
- `/blog` with articles targeting long-tail keywords

**Priority:** Low (post-launch) | **Effort:** Ongoing

---

## 7. Manifesto Alignment Check

| Feature | Aligned? | Notes |
|---------|----------|-------|
| Free Tools | ✅ | Value-first, no signup |
| Age-Grading | ✅ | WMA standards, no decline narrative |
| Efficiency Focus | ✅ | Pace @ HR as core metric |
| Correlation Engine | ✅ | Personal curves, no global averages |
| Tone | ✅ | Sparse, direct, irreverent when earned |
| No Prescriptive Language | ✅ | "Patterns" not "You should" |
| Optional Inputs | ✅ | Nutrition/check-in clearly optional |
| Policy-Based | ⚠️ | Not yet implemented in UI |

**Overall:** Strong alignment. The product reflects the manifesto well.

---

## 8. Launch Strategy: Bootstrapping Edition

### The Reality
You're broke. The product is 85% ready. Waiting for perfection costs opportunity.

### Recommendation: **Launch Closed Beta NOW**

#### Phase 1: Immediate (This Week)
**Cost: $0-20/month**

1. **Deploy Backend:**
   - Railway.app or Render.com (free tier: 500 hours/month)
   - PostgreSQL: Railway or Supabase free tier
   - Redis: Upstash free tier (10k commands/day)

2. **Deploy Frontend:**
   - Vercel free tier (perfect for Next.js)
   - Automatic HTTPS, CDN included

3. **Domain:**
   - Get a domain ($10-15/year)
   - Namecheap or Cloudflare Registrar

4. **Email:**
   - Resend.com free tier (100 emails/day) for transactional
   - Your personal email for support initially

#### Phase 2: Invite Beta Users (Week 2)
**Target: 10-25 serious runners**

- Post in running communities (Reddit r/running, r/AdvancedRunning)
- Reach out to local running clubs
- Masters running Facebook groups (your target demographic)
- Offer lifetime free tier to first 25 users

**Pitch:**
> "Building a running analytics tool that finds what actually improves YOUR efficiency. Free tools available now. Looking for 25 beta testers who track with Strava and want to find their personal performance patterns. Free for life for early testers."

#### Phase 3: Iterate (Weeks 3-8)
- Collect feedback
- Fix critical bugs
- Let correlation engine gather data
- Build testimonials

#### Phase 4: Apply for Garmin/Coros (Week 4+)
- You now have a live production site
- Privacy policy (generate with Termly.io free)
- Real users demonstrating the product

### Free Tier Deployment Stack

| Service | Free Tier Limits | Good For |
|---------|------------------|----------|
| **Vercel** | 100GB bandwidth, serverless | Frontend |
| **Railway** | 500 hours/month | API + Worker |
| **Supabase** | 500MB DB, 50k requests | PostgreSQL |
| **Upstash** | 10k commands/day | Redis |
| **Resend** | 100 emails/day | Email |
| **Cloudflare** | Unlimited | DNS + CDN |

**Total Cost: $10-15/year (domain only)**

### What to Fix Before Beta Launch

**MUST DO (blocking):**
1. ☐ Add robots.txt (5 min)
2. ☐ Add sitemap.ts (15 min)
3. ☐ Fix meta tags (30 min)
4. ☐ Create empty state for Dashboard (1 hour)
5. ☐ Add privacy policy page (use generator, 30 min)
6. ☐ Add terms of service page (use generator, 30 min)

**SHOULD DO (nice-to-have):**
7. ☐ Simplify navigation for logged-in users
8. ☐ Fix mobile nav scroll
9. ☐ Dynamic import for charts

**DEFER (post-beta):**
- SEO content pages
- Structured data
- Payment integration
- Advanced features

---

## 9. Action Items Summary

### Immediate (Before Beta - 4-6 hours total)

| Item | Priority | Effort | Impact |
|------|----------|--------|--------|
| robots.txt | HIGH | 5 min | SEO |
| sitemap.ts | HIGH | 15 min | SEO |
| Meta tags update | HIGH | 30 min | SEO |
| Empty state for Dashboard | HIGH | 1 hr | UX |
| Privacy policy page | HIGH | 30 min | Legal/API access |
| Terms of service page | HIGH | 30 min | Legal |
| Deploy to free tier | HIGH | 2 hrs | Launch |

### Post-Beta (Ongoing)

| Item | Priority | Effort | Impact |
|------|----------|--------|--------|
| Navigation simplification | Medium | 2 hrs | UX |
| Dynamic imports | Low | 1 hr | Performance |
| Structured data | Low | 1 hr | SEO |
| Blog/content | Low | Ongoing | SEO |
| OG image creation | Low | 30 min | Social |

---

## 10. Final Thoughts

**You're closer than you think.**

The correlation engine is your moat. Nobody else is doing "personal running insights through correlation analysis" in this way. The free tools drive traffic. The manifesto keeps the product honest.

Stop polishing. Start shipping.

> "Nobody cares. Work harder." — Cameron Hanes

Your beta users will tell you what to fix. The correlation engine needs data to prove itself. Every day without users is a day without learning.

**Recommended Launch Date: This Weekend**

---

**Document Version:** 1.0  
**Generated:** January 7, 2026


