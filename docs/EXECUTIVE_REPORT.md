# StrideIQ Executive Report

**Version:** 3.13.0+  
**Branch:** stable-diagnostic-report-2026-01-14  
**Date:** 2026-01-15

---

## 1. Executive Summary

StrideIQ is an algorithmic training platform that treats each athlete as a sample size of one. No population averages. No generic plans. No motivational fluff.

**The Problem:** Every running app on the market builds plans from population data — "most runners respond well to X." But you're not most runners. Your τ1 might be 25 days, not 42. Your body might need more recovery after threshold work, not less. Generic plans leave performance on the table.

**The Solution:** StrideIQ calibrates individual physiological models from your Strava data, detects what actually works for YOU, and generates plans that respect your proven capabilities — not theoretical ones.

**Core Differentiators:**
- **N=1 philosophy**: External research informs questions, not answers. Your data calls the shots.
- **Calibrated models**: Individual τ1/τ2 time constants, not fixed 42/7 defaults.
- **Counter-conventional insights**: "Your data shows you respond better to shorter tapers" — even when textbooks disagree.
- **Fitness Bank**: Plans built from YOUR peak (71mpw, 22mi long, 18@MP) — not generic "Week 1: 30mi."
- **No BS engagement**: No streaks, no badges, no "Great job!" when you had a shit run.

**Current State:** Production-ready core with Fitness Bank Framework deployed. 17 unit tests, 9 integration checks passing. Ready for elite tier rollout.

---

## 2. What It Is

### Architecture

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Frontend** | Next.js 14, React 18, shadcn/ui, Tailwind | Sparse UI, value-first displays |
| **API** | Python 3.11, FastAPI, Pydantic | Algorithmic services, no LLM at generation time |
| **Database** | PostgreSQL 15, SQLAlchemy | Activities, metrics, plans, workouts |
| **Cache** | Redis | Model parameters, session data |
| **Containers** | Docker Compose | Local dev + deployment |

### Data Flow

```
Strava OAuth → Webhooks → Activities → TSS/VDOT Computation
                              ↓
                    Individual Performance Model
                    (τ1, τ2, k1, k2 calibration)
                              ↓
                    Fitness Bank (peaks, patterns, constraints)
                              ↓
                    Plan Generation (themes → workouts → calendar)
                              ↓
                    Athlete UI (Home, Plans, Calendar, Analytics)
```

**Critical constraint:** No aggregated population data enters the core loop. External datasets (Figshare 10M+, WMA factors) inform validation questions, not individual prescriptions.

### Core Components

| Component | File | Purpose |
|-----------|------|---------|
| **FitnessBankCalculator** | `services/fitness_bank.py` | Analyzes full history for peak capabilities |
| **WeekThemeGenerator** | `services/week_theme_generator.py` | T/MP alternation, injury protection |
| **WorkoutPrescriptionGenerator** | `services/workout_prescription.py` | Specific structures ("2x3mi @ 6:25") |
| **ConstraintAwarePlanner** | `services/constraint_aware_planner.py` | Orchestrates plan generation |
| **IndividualPerformanceModel** | `services/individual_performance_model.py` | τ1/τ2 calibration from race data |
| **EfficiencyTrending** | `services/efficiency_trending.py` | Pace:HR ratio analysis |
| **PreRaceFingerprinting** | `services/pre_race_fingerprinting.py` | Optimal pre-race state detection |
| **CorrelationEngine** | `services/insight_aggregator.py` | Lagged/multi-factor correlations |

---

## 3. What It Does

### Data Ingestion

| Step | Mechanism | Output |
|------|-----------|--------|
| **OAuth** | Strava OAuth 2.0 | Access token, athlete profile |
| **Webhooks** | Activity create/update events | Real-time sync |
| **Processing** | Distance, duration, HR, splits, best efforts | TSS, VDOT, efficiency metrics |
| **Enrichment** | Workout classification, heat adjustment | Contextual metadata |

Activities are stored with full split data. Best efforts (5K, 10K, half, marathon) are extracted for race performance tracking.

### Analysis Layer

| Method | Algorithm | Insight |
|--------|-----------|---------|
| **Efficiency Trending** | 28-day rolling pace:HR ratio | "Your efficiency is up 4.2% — aerobic gains landing" |
| **Pre-Race Fingerprinting** | Pattern match: TSB, sleep, mileage before PRs | "Your best races happen with TSB +15 to +20" |
| **Training Load (TSB/CTL/ATL)** | Banister impulse-response, individual τ | "CTL 72, ATL 85, TSB -13: heavy but sustainable" |
| **Pace Decay** | Second-half vs first-half pace analysis | "You fade 8% in long runs — MP portions too ambitious?" |
| **VDOT Calculation** | Daniels' formula from race times | "Current VDOT: 53.2 → MP 6:46, T 6:25" |

All calculations use **your data only**. No "runners like you" nonsense.

### Insight Generation

**Correlation Engine:**
- Lagged correlations: Does mileage 3 weeks ago predict today's efficiency?
- Multi-factor: Sleep + easy day ratio → race performance
- Directional: "More recovery = faster long runs" or opposite?

**Diagnostic Report (`/diagnostic`):**
- Full athlete profile with constraint analysis
- Historical patterns (peak weeks, MP progressions, race timeline)
- Fitness Bank summary
- Personalized recommendations

### Planning System

Three tiers, one philosophy:

| Tier | Method | Personalization |
|------|--------|-----------------|
| **Template** | Pre-built structures | Distance/weeks only |
| **Model-Driven** | τ1/τ2 calibration + optimal load | Individual response characteristics |
| **Fitness Bank (Elite)** | Full constraint-aware planning | Peak targeting + injury protection + dual races |

**Fitness Bank Planning Flow:**

1. **FitnessBank** → Analyze 12+ months of history
   - Peak weekly: 71 miles
   - Peak long run: 22 miles
   - Peak MP long run: 18 miles
   - Best VDOT: 53.2
   - τ1: 25 days (fast adapter)
   - Constraint: Injury (sharp volume drop)

2. **WeekThemeGenerator** → Periodization
   - Rebuild phases for injury return
   - T/MP alternation (never consecutive same)
   - Recovery every 3-4 weeks based on τ1
   - Tune-up race coordination

3. **WorkoutPrescriptionGenerator** → Specific prescriptions
   - "2x4mi @ 6:25 w/ 3min jog" not "threshold work"
   - Personal paces from VDOT
   - Experience-appropriate structures

4. **ConstraintAwarePlanner** → Final assembly
   - Counter-conventional notes
   - Race predictions with confidence intervals
   - Calendar-ready output

**Sample Output (Elite athlete, injury return, March marathon + 10-mile tune-up):**

```
Week 1: rebuild_easy     28mi    (Easy only, leg healing)
Week 2: rebuild_strides  36mi    (Add strides)
Week 3: rebuild_strides  39mi    (Building back)
Week 4: build_t          58mi    (2x4mi @ 6:25)
Week 5: build_mp         69mi    (18mi w/ 10@MP)
Week 6: peak             73mi    (23mi w/ 14@MP — race simulation)
Week 7: taper_1          55mi    (Reduce volume, maintain intensity)
Week 8: tune_up          32mi    (10-MILE RACE — go hard)
Week 9: race             43mi    (MARATHON)

Prediction: 3:01:09 ±5-8min
```

### UI Surfaces

| Surface | Features |
|---------|----------|
| **Home** | TSB gauge, "Why" cards (3-5 insights), signals banner |
| **Plans** | Create (template/model/Fitness Bank), preview, apply to calendar |
| **Calendar** | Weekly view, day detail panel, workout edits/swaps/variants |
| **Analytics** | Efficiency chart, load response, age-graded trends, "Why This Trend" |
| **Activities** | Splits, efficiency comparison, "Why This Run" analysis |

### Flexibility

User modifications preserve personalization:

| Action | System Response |
|--------|-----------------|
| **Swap days** | Reschedule workout, no overlap, model params intact |
| **Override pace** | Flag as user-modified, optional TSB recalc |
| **Substitute workout** | Match approximate TSS, note substitution reason |
| **Skip workout** | Record skip reason, adjust downstream if needed |

---

## 4. Why It Matters

### The Problem with Generic Apps

| App | Approach | Failure Mode |
|-----|----------|--------------|
| **Strava** | Social features, basic summaries | "Relative effort" is population-based |
| **Garmin** | Template plans, HRV tracking | Same plan for 25mpw and 70mpw runners |
| **TrainingPeaks** | Coach-dependent, manual TSS | Expensive, requires expert interpretation |
| **Runna** | Generic AI plans | "Runners like you" means nobody like you |

### StrideIQ Differentiators

| Feature | Others | StrideIQ |
|---------|--------|----------|
| **τ time constants** | Fixed 42/7 | Calibrated from YOUR race data |
| **Training paces** | Generic VDOT tables | From YOUR proven race performances |
| **Injury return** | "Start over at Week 1" | Respect banked fitness, progressive rebuild |
| **Dual races** | Manual coordination | Automatic tune-up + goal race sequencing |
| **Counter-conventional** | "Follow the science" | "Your data says otherwise" |
| **Volume targeting** | Generic build | Target YOUR peak (71mpw, not 40) |

### Real-World Impact

**Case: 55-year-old elite amateur, injury return**

Generic plan would prescribe: 30mpw → 40mpw → 50mpw over 12 weeks.

StrideIQ Fitness Bank knows:
- Peak: 71mpw (proven sustainable)
- 22-mile long runs (completed multiple times)
- 18 miles at MP (race simulation ready)
- τ1 = 25 days (fast adapter)
- Current constraint: Leg injury, 16mpw current

Prescription:
- 3 weeks rebuild (28 → 39mi), not 6
- Peak to 73mpw by week 6, not week 12
- 10-mile tune-up 8 days before marathon — race it HARD as final threshold
- Prediction: 3:01 ±5-8min (injury uncertainty factored)

**Difference:** Generic leaves 15-20 miles/week on the table. StrideIQ targets the proven peak.

---

## 5. Current State & Risks

### Stable Features

| Feature | Status | Tests |
|---------|--------|-------|
| Strava sync | ✅ Production | Webhook handlers tested |
| Activity analysis | ✅ Production | 15+ unit tests |
| Efficiency trending | ✅ Production | Rolling calculations validated |
| Training load (CTL/ATL/TSB) | ✅ Production | Impulse-response verified |
| Age grading (WMA 2025) | ✅ Production | All age groups validated |
| Template plans | ✅ Production | Standard flow working |
| Model-driven plans | ✅ Production | τ calibration + preview |
| Fitness Bank Framework | ✅ Production | 17 unit + 9 integration tests |
| Calendar integration | ✅ Production | Apply + edit flow working |

### Open Work

| Item | Status | Priority |
|------|--------|----------|
| A/B testing infrastructure | Scaffolded | Medium |
| Figshare dataset validation | Research phase | Low |
| Garmin integration | Pending API access | High |
| Sleep/nutrition tracking | UI exists, data sparse | Medium |
| Mobile app | Not started | Future |

### Pain Points Fixed

| Issue | Resolution |
|-------|------------|
| Agent drift (unsolicited refactors) | Atomic step pattern, rigor checklist |
| TuneUpRace Pydantic recursion | Renamed `date` → `race_date` with alias |
| Overly conservative injury ramps | Floor at 35% peak, steeper ramps for fast adapters |
| Missing race week | Week calculation now includes race week properly |
| PowerShell incompatibility | Avoid bash-specific syntax |

### Robustness

- **Unit tests:** 200+ across services
- **Integration tests:** API flow + DB verification
- **Feature flags:** All new features gated
- **Rate limiting:** 5 plans/day per athlete
- **Tier enforcement:** Elite-only for Fitness Bank
- **Startup validation:** Import checks before deploy

---

## 6. Future Outlook

### Immediate (Next Sprint)

| Task | Effort | Impact |
|------|--------|--------|
| Manual testing of Fitness Bank UI | 2h | Validate full flow |
| Elite tier beta rollout | 4h | Real athlete feedback |
| Garmin API integration | 8h | Broader data capture |

### Short-Term (Q1 2026)

| Task | Effort | Impact |
|------|--------|--------|
| A/B test model vs template plans | 2w | Quantify personalization value |
| Figshare validation study | 2w | External credibility |
| Sleep quality → performance correlation | 1w | Lifestyle factor integration |
| Export plans to .ics | 2d | Calendar interoperability |

### Long-Term Vision

| Milestone | Target |
|-----------|--------|
| 1000 elite tier subscribers | Q2 2026 |
| Mobile app (React Native) | Q3 2026 |
| Coach dashboard | Q4 2026 |
| Wearable integrations (Whoop, Oura) | Q4 2026 |

---

## Appendix: Key Files Reference

| Path | Purpose |
|------|---------|
| `apps/api/services/fitness_bank.py` | FitnessBank model + calculator |
| `apps/api/services/constraint_aware_planner.py` | Plan orchestration |
| `apps/api/services/week_theme_generator.py` | Periodization themes |
| `apps/api/services/workout_prescription.py` | Specific workout structures |
| `apps/api/routers/plan_generation.py` | `/v2/plans/*` endpoints |
| `apps/web/app/plans/create/page.tsx` | Plan creation UI |
| `docs/adr/ADR-030-fitness-bank-framework.md` | Architecture decision |
| `docs/adr/ADR-031-constraint-aware-planning.md` | Planning layer design |
| `docs/adr/ADR-032-constraint-aware-api-integration.md` | API contract |

---

*No population BS. Your data calls the shots.*
