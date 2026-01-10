# NEXT STEPS & PRIORITIES (Updated: Jan 5, 2026)

## Current Status Summary

✅ **Phase 1 Complete (100%)**
- WMA 2023 age-grading with distance-specific tables
- PB calculation and tracking
- Race detection with confidence scoring
- Derived signals (Durability Index, Recovery Half-Life, Consistency Index)
- Frontend displays age-graded metrics and race detection
- CORS fixed - frontend loading successfully

🚧 **Phase 1.5 In Progress (~40%)**
- ✅ Core infrastructure (config, database, logging)
- ✅ Health checks
- 🚧 Background tasks (Celery) - NOT STARTED
- 🚧 Caching layer (Redis) - NOT STARTED
- 📋 Rate limiting - NOT STARTED

## Critical Gaps Per Manifesto Section 2

### Missing Primary Trend Signals:
1. **Efficiency Trend (Master Signal)** - NOT IMPLEMENTED
   - Pace improvement at constant HR
   - HR reduction at constant pace
   - Age-graded % slope over time
   
2. **Performance Stability** - NOT IMPLEMENTED
   - Variance of pace @ HR across similar sessions
   - Fade curves (first vs. second half efficiency)
   - Consistency of age-graded % across weeks

### Missing Secondary Signals:
3. **Load → Response Mapping** - NOT IMPLEMENTED
   - Acute vs chronic load deltas
   - Load efficiency (gain per unit load)
   - Load saturation (plateaus)

4. **Recovery Elasticity** - PARTIALLY IMPLEMENTED
   - ✅ Recovery half-life (exists but basic)
   - ❌ HR suppression/elevation on easy days
   - ❌ Pace degradation persistence

5. **Durability / Structural Risk** - PARTIALLY IMPLEMENTED
   - ✅ Durability Index (exists but basic)
   - ❌ Rising HR cost for easy pace
   - ❌ Increased variability after volume ramps
   - ❌ Micro-regressions after load spikes

### Missing Correlation Engines:
6. **Time-Shifted Correlations** - NOT IMPLEMENTED
   - Sleep vs next-day efficiency
   - Fueling vs long-run fade
   - Stress vs recovery slope
   - Intensity distribution vs PB probability
   - **No fixed windows - lags learned from data**

### Missing Advanced Features:
7. **PB Probability Modeling** - NOT IMPLEMENTED
   - Probability of PB in next 6-10 weeks
   - Based on efficiency slope, stability, recovery, load alignment

8. **Negative Signal Detection** - NOT IMPLEMENTED
   - False Fitness detection
   - Masked Fatigue detection

## Recommended Next Steps

### Option A: Complete Phase 1.5 First (Production Infrastructure)
**Priority:** High - Needed for scalability
**Timeline:** 1-2 weeks
**Tasks:**
1. Move Strava sync to Celery (prevents API blocking)
2. Implement Redis caching (reduce DB load)
3. Add rate limiting middleware (protect API)

**Pros:** 
- Makes system production-ready
- Enables horizontal scaling
- Prevents blocking issues

**Cons:**
- Delays diagnostic features
- Less visible user value

### Option B: Build Diagnostic Engine First (Manifesto Section 2)
**Priority:** High - Core product value
**Timeline:** 2-3 weeks
**Tasks:**
1. Efficiency Trend Signal (Master Signal)
2. Performance Stability metrics
3. Load → Response Mapping
4. Correlation Engine (time-shifted)
5. PB Probability Modeling

**Pros:**
- Delivers core manifesto value
- Makes product unique and valuable
- Enables world-class diagnostics

**Cons:**
- System may hit scaling issues later
- More complex to implement

### Option C: Build World-Class Website First (Phase 2 Requirement)
**Priority:** Medium-High - Unlocks Garmin/Coros
**Timeline:** 2-3 weeks
**Tasks:**
1. Multi-page architecture (home, dashboard, diagnostics, policy, leaderboards)
2. High-performance visualizations (charts, trends, heatmaps)
3. Premium UI/UX (typography, spacing, motion)
4. Dark/light mode, accessibility
5. Company website + privacy policy

**Pros:**
- Required for Garmin/Coros API access
- Proves product is serious
- Better user experience

**Cons:**
- Less backend functionality
- May need to rebuild if data model changes

## Recommendation: Hybrid Approach

**Week 1-2: Complete Critical Phase 1.5**
- Move Strava sync to Celery (prevents blocking)
- Add Redis caching for activities/athletes (immediate performance gain)
- This enables system to handle load while building features

**Week 2-4: Build Core Diagnostic Signals**
- Efficiency Trend Signal (Master Signal) - **CRITICAL**
- Performance Stability metrics
- Basic correlation engine (start with sleep→efficiency if we have sleep data)

**Week 4-6: World-Class Website**
- Multi-page architecture
- Diagnostic visualizations
- Company site + privacy policy
- Apply for Garmin/Coros access

**Week 6-8: Advanced Diagnostics**
- PB Probability Modeling
- Load → Response Mapping
- Negative Signal Detection
- Full correlation engine

## Data Source Constraints (CLARIFIED)

**Current Data Available:**
- ✅ Strava activity data (pace, HR, distance, time, splits)
- ✅ Age-graded performance metrics
- ✅ Race detection flags
- ✅ Derived signals (Durability, Recovery Half-Life, Consistency)

**Data NOT Available Until Post-Launch:**
- ❌ Sleep data (requires Garmin/Coros API)
- ❌ Stress data (requires Garmin/Coros API)
- ❌ Recovery metrics (HRV, etc. - requires Garmin/Coros API)
- ❌ Fueling data (not available from Strava)

**Implication:**
- Correlation engine for sleep/stress/recovery must be deferred until after Garmin/Coros integration
- Can build correlation engine for activity-based correlations (intensity distribution, volume patterns, etc.)
- Must build company website + privacy policy BEFORE launch to enable Garmin/Coros API access

## Revised Priority Plan

### Phase 1.5 Completion (Weeks 1-2) - CRITICAL
**Why:** System must be production-ready before launch
1. ✅ Move Strava sync to Celery (prevents API blocking)
2. ✅ Implement Redis caching (reduce DB load, improve performance)
3. ✅ Add rate limiting middleware (protect API)

### Phase 2A: Activity-Based Diagnostics (Weeks 2-4)
**Why:** Core manifesto value using available data
1. **Efficiency Trend Signal (Master Signal)** - CRITICAL
   - Pace improvement at constant HR
   - HR reduction at constant pace
   - Age-graded % slope over time
   - Uses only activity data (we have this!)

2. **Performance Stability Metrics**
   - Variance of pace @ HR across similar sessions
   - Fade curves (first vs. second half efficiency)
   - Consistency of age-graded % across weeks

3. **Load → Response Mapping**
   - Acute vs chronic load deltas
   - Load efficiency (gain per unit load)
   - Load saturation detection
   - Uses activity volume/intensity (we have this!)

4. **PB Probability Modeling**
   - Probability of PB in next 6-10 weeks
   - Based on efficiency slope, stability, recovery elasticity
   - Uses activity trends (we have this!)

### Phase 2B: World-Class Website + Privacy Policy (Weeks 4-6)
**Why:** Required for Garmin/Coros API access post-launch
**Status:** ✅ Landing Page Complete (Jan 5, 2026)
1. ✅ Company website landing page (Hero, Free Tools, How It Works, Pricing, Footer)
2. 📋 Privacy policy (GDPR-compliant, clear data usage) - NEXT
3. 📋 Terms of service - NEXT
4. Multi-page architecture:
   - ✅ Home/Landing page - COMPLETE
   - ✅ Dashboard (enhanced current) - EXISTS
   - 📋 Diagnostics page (new - show efficiency trends, stability, PB probability) - NEXT
   - ✅ Personal Bests (existing) - EXISTS
   - ✅ Profile/Settings (existing) - EXISTS
   - 📋 Leaderboards (future - age-graded rankings) - FUTURE

### Phase 2C: Advanced Activity-Based Features (Weeks 6-8)
1. Negative Signal Detection (False Fitness, Masked Fatigue)
2. Activity-based correlation engine (intensity distribution vs PB probability)
3. Enhanced visualizations (charts, trends, heatmaps)

### Post-Launch: Garmin/Coros Integration
1. Apply for API access (with live website)
2. Integrate Garmin/Coros data sources
3. Build sleep/stress/recovery correlation engine
4. Add recovery-based diagnostics

## Recommended Immediate Next Steps

**Week 1-2: Complete Phase 1.5**
- Move Strava sync to Celery
- Implement Redis caching
- Add rate limiting

**Week 2-4: Build Efficiency Trend Signal**
- This is the "Master Signal" from manifesto
- Uses only activity data (pace, HR, age-graded %)
- Core diagnostic value

**Week 4-6: Build Website + Privacy Policy**
- Required for Garmin/Coros access
- Can be done in parallel with diagnostics

**Week 6-8: Complete Activity-Based Diagnostics**
- Performance Stability
- Load → Response Mapping
- PB Probability Modeling

**Post-Launch: Garmin/Coros + Sleep/Stress Correlations**
- After website is live and API access granted

