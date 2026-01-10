# StrideIQ Executive Summary

> *The only running app that answers "WHY did I run faster/slower?" using your data alone.*

**Version:** 0.9.0  
**Date:** January 10, 2026  
**Status:** Stable Beta

---

## What is StrideIQ?

StrideIQ is an **AI-powered running intelligence platform** that transforms raw workout data into actionable insights. Unlike Strava (social) or Garmin Connect (data logging), StrideIQ answers the question every serious runner asks:

> **"WHY did I run faster/slower today, and what should I do about it?"**

---

## Core Differentiators

### 1. N=1 Philosophy
We learn from **your data**, not population averages. Sleep studies say 8 hours is optimal, but if YOUR fastest runs came after 5 hours of sleep, we tell you that.

### 2. Contextual Comparison ("Ghost Runs")
Compare any run against a "ghost average" of your similar efforts. See exactly where you outperformed or underperformed, and understand why.

### 3. Causal Attribution Engine
We don't just correlate—we identify **leading indicators** that *precede* your performance changes. "Your weekly volume 3 weeks ago predicted today's race time."

### 4. Tiered Confidence System
Honest about what we know:
- **Statistical:** Granger-tested causal relationships
- **Pattern:** Clear correlations
- **Trend:** Directional signals
- **Early Signal:** Emerging patterns

---

## Technical Architecture

| Layer | Technology | Purpose |
|-------|------------|---------|
| **API** | FastAPI + Python 3.11 | 40+ REST endpoints, async |
| **Database** | PostgreSQL + TimescaleDB | Time-series optimized |
| **Frontend** | Next.js 14 + TypeScript | React Server Components |
| **Auth** | JWT + OAuth2 | Strava integration |
| **Cache** | Redis | Rate limiting, session |
| **Queue** | Celery | Background sync jobs |

---

## Feature Inventory (v0.9.0)

### Data Ingestion
- ✅ Strava OAuth integration
- ✅ Automatic activity sync
- ✅ Webhook real-time updates
- ✅ Manual data entry (daily check-ins, body composition)

### Analysis Engines
- ✅ **Contextual Comparison Engine** - Ghost averaging, similarity scoring
- ✅ **Causal Attribution Engine** - Leading indicator detection
- ✅ **Simple Pattern Matching** - Best vs worst run analysis
- ✅ **Training Load Monitoring** - ACWR, fatigue detection
- ✅ **Efficiency Analytics** - Pace/HR efficiency trends
- ✅ **Workout Classification** - Auto-detect run types

### Insights & Recommendations
- ✅ Athlete profile (runner type, consistency streaks)
- ✅ Personal bests tracking
- ✅ Correlation discovery ("what works for you")
- ✅ Recovery metrics
- ✅ VDOT calculator with age grading

### Data Privacy & Export
- ✅ GDPR-compliant data export
- ✅ Full data download (JSON)
- ✅ Anonymized profile export (for research)
- ✅ Account deletion workflow

---

## API Endpoint Summary

| Category | Count | Examples |
|----------|-------|----------|
| Auth | 4 | login, register, me, refresh |
| Athletes | 5 | profile, personal-bests, metrics |
| Activities | 8 | list, detail, splits, analysis |
| Comparison | 5 | auto-similar, quick-score, HR filters |
| Causal | 5 | analyze, simple-patterns, readiness |
| Insights | 6 | correlations, training-load, efficiency |
| Data | 4 | export, anonymized, delete |
| **Total** | **37+** | |

---

## Stability Metrics

### Test Results (v0.9.0)
```
=== FINAL VERIFICATION ===
[PASS] health
[PASS] auth/me
[PASS] athletes/me
[PASS] activities (list)
[PASS] activities/{id}
[PASS] activities/{id}/splits
[PASS] activities/{id}/analysis
[PASS] compare/auto-similar
[PASS] causal/simple-patterns
[PASS] causal/analyze
[PASS] athlete-profile/summary
[PASS] training-load/current
[PASS] correlations/what-works
[PASS] recovery-metrics/me
[PASS] data-export/anonymized

=== RESULTS: 15 PASSED, 0 FAILED ===
```

---

## Market Positioning

### Competitive Landscape

| Product | Focus | Gap StrideIQ Fills |
|---------|-------|-------------------|
| **Strava** | Social/logging | No "why" analysis |
| **Garmin Connect** | Device data | No cross-input correlation |
| **TrainingPeaks** | Coaching platforms | Expensive, coach-centric |
| **Runalyze** | Free analytics | Complex, not actionable |
| **Whoop** | Recovery focus | No training integration |

### StrideIQ Sweet Spot
**Self-coached runners** who want **coach-level insights** without the cost or dependency.

---

## Next Steps (Roadmap)

### Phase 1: Launch Prep (Q1 2026)
- [ ] Public beta launch
- [ ] Landing page with value proposition
- [ ] Onboarding flow
- [ ] Subscription tiers

### Phase 2: Intelligence (Q2 2026)
- [ ] AI Coach chat integration
- [ ] Race prediction
- [ ] Training plan generation
- [ ] Garmin API integration

### Phase 3: Scale (Q3 2026)
- [ ] Mobile app (React Native)
- [ ] Coach marketplace
- [ ] Team/club features
- [ ] Advanced periodization

---

## Investment Thesis

1. **Market Size:** 50M+ serious recreational runners globally
2. **Pain Point:** Overwhelming data, no actionable insights
3. **Moat:** Proprietary causal attribution engine + N=1 philosophy (athlete data overrides population research) — defensible IP with provisional patent in progress
4. **Monetization:** Freemium → Pro ($9.99/mo) → Elite ($19.99/mo)
5. **Traction:** Closed beta launched January 2026; early users reporting PR insights and fatigue detection
6. **Team:** Technical founder with running background

---

## Contact

For partnership, investment, or technical inquiries:
- **Email:** [founder email]
- **X:** @nomdk1
- **Demo:** Available upon request

---

*Confidential — For Potential Partners/Investors Only. Version 0.9.0 | January 10, 2026*
