# Diagnostic Report for Michael Shaffer
**Generated:** January 8, 2026  
**Analysis Period:** October 16, 2025 - December 31, 2025 (11 weeks)  
**Data Source:** 69 runs with valid pace + heart rate data

---

## Executive Summary

Your running efficiency declined **5.5%** over the analysis period. However, this coincided with a **85% drop in weekly volume** (115km → 17km). The most actionable finding is that **shorter, faster runs show higher efficiency** — but this is likely because quality workouts are naturally shorter, not because long runs are "bad."

**The biggest gap in this analysis:** No sleep, stress, soreness, or nutrition data exists. This means we cannot test the most likely explanations for the efficiency decline.

---

## Question 1: What factors have the strongest statistical correlation with IMPROVEMENTS in efficiency?

| Factor | Correlation (r) | Effect Size | Interpretation |
|--------|-----------------|-------------|----------------|
| **Day of Week** | +0.311 | Medium | Later in week → higher efficiency |
| **Hour of Day** | +0.235 | Small | Later runs → slightly higher efficiency |
| **Previous Week Volume** | +0.087 | Negligible | Higher volume → *slightly* better, but NOT significant |

**Plain English:**
- Your best efficiency runs tend to happen **Thursday-Saturday** (correlation is real, p<0.05)
- Afternoon/evening runs are slightly more efficient than morning runs (may be warmth or body readiness)
- Previous week's volume shows a tiny positive effect, but it's not statistically reliable

**What this means:** There's no single "do more of this" factor that stands out. Your efficiency improvements are not strongly predicted by any single input we can measure.

---

## Question 2: What factors have the strongest correlation with DECREASES in efficiency?

| Factor | Correlation (r) | Effect Size | Interpretation |
|--------|-----------------|-------------|----------------|
| **Run Duration** | -0.318 | Medium | Longer runs → lower efficiency |
| **Elevation Gain** | -0.276 | Small | More climbing → lower efficiency |
| **Run Distance** | -0.248 | Small | Longer distance → lower efficiency |

**Plain English:**
- Longer runs (by time or distance) have lower efficiency — **this is physiologically expected**
- Hills hurt efficiency — **also expected**
- These are NOT "problems to fix" — they're natural consequences of workout type

**Critical caveat:** This doesn't mean long runs are bad for you. It means:
- When you run longer, your pace-per-heartbeat gets worse (fatigue)
- Your tempo runs and shorter quality work will always "look" more efficient

---

## Question 3: How confident is the system in each finding?

| Finding | Sample Size | Statistical Significance | Effect Size | Confidence |
|---------|-------------|-------------------------|-------------|------------|
| Duration → lower efficiency | n=69 | p<0.05 | Medium | **HIGH** |
| Day of week → higher efficiency | n=69 | p<0.05 | Medium | **MEDIUM** |
| Elevation → lower efficiency | n=69 | p<0.05 | Small | **MEDIUM** |
| Distance → lower efficiency | n=69 | p<0.05 | Small | **MEDIUM** |
| Hour → higher efficiency | n=69 | p<0.05 | Small | **LOW** |
| Prior week volume → higher | n=56 | NOT significant | Negligible | **NONE** |
| Rest days → higher | n=68 | NOT significant | Negligible | **NONE** |

**Technical notes:**
- For n=69, correlations with |r| > 0.22 are statistically significant (p<0.05)
- I used Pearson correlation; effect sizes follow Cohen's conventions
- No proper p-value calculation was implemented — thresholds are approximations

---

## Question 4: What findings are weak, speculative, or inconclusive?

### Inconclusive (NOT statistically significant):

1. **Rest days before a run** (r=+0.002)
   - Zero correlation. More rest neither helps nor hurts your efficiency.
   - *This is surprising.* Common coaching wisdom suggests rest improves performance.
   - Possible explanation: You're running frequently enough that 1-2 day variations don't matter.

2. **Previous week's volume** (r=+0.087)
   - Tiny positive effect, but too weak to trust.
   - We cannot say "more volume last week = better efficiency this week" with any confidence.

### Speculative (statistically significant but may be confounded):

3. **Day of week correlation** (+0.311)
   - Real correlation, but *why*? Possible explanations:
     - Cumulative fatigue builds early in week
     - Quality workouts scheduled later in week
     - Weekend runs are more relaxed/enjoyable
   - Without knowing your training schedule, this is speculative.

4. **Hour of day correlation** (+0.235)
   - Real but weak. Likely explained by:
     - Body temperature higher later in day
     - Already eaten/hydrated
     - More awake/alert

---

## Question 5: What key data is MISSING that would materially change confidence?

### Critical Missing Data:

| Data Type | Entries | Impact |
|-----------|---------|--------|
| **Sleep duration/quality** | 0 | Cannot test if poor sleep causes bad runs |
| **Stress level** | 0 | Cannot test if life stress hurts performance |
| **Muscle soreness** | 0 | Cannot track recovery trajectory |
| **Nutrition** | 0 | Cannot test meal timing or fuel effects |
| **Body composition/weight** | 0 | Cannot correlate weight to efficiency |
| **HRV** | 0 | Cannot test readiness signals |

### Unanswerable Questions:

- ❌ Does sleep duration affect your efficiency?
- ❌ Does perceived stress correlate with performance?
- ❌ Does muscle soreness predict performance decline?
- ❌ Does HRV trend with efficiency?
- ❌ Do certain foods improve your running?
- ❌ Does meal timing affect performance?
- ❌ Does hydration status correlate with efficiency?
- ❌ Does weight fluctuation affect performance?

### What would unlock these answers:
- **2-4 weeks of Morning Check-ins** → Sleep/stress/soreness correlations
- **2-4 weeks of nutrition logging** → Food/timing correlations
- **Weekly weigh-ins** → Weight fluctuation analysis

**Without this data, the diagnostic engine is operating at maybe 40% of its potential.**

---

## Question 6: What is the single highest-leverage experiment I could run next?

### Recommended Experiment: **Start Morning Check-ins for 4 weeks**

**Why this is highest-leverage:**
1. Takes 10 seconds per day
2. Unlocks 3 major correlation types (sleep, stress, soreness)
3. Will either:
   - Reveal a hidden cause of your efficiency decline, OR
   - Confirm that these factors don't matter for you

**Protocol:**
- Every morning, log:
  - Sleep quality (1-5)
  - Stress level (1-5)
  - Muscle soreness (1-5)
  - Optional: HRV if you have a device
  - Optional: Resting HR
- Continue for minimum 4 weeks (28+ data points)
- Re-run this analysis after 4 weeks

**Alternative Experiment (if you want to test training structure):**

Given that your efficiency declined during a period of volume reduction:
- **Hypothesis:** Efficiency decline is caused by loss of aerobic base
- **Test:** Return to 60-80km/week for 4 weeks, track efficiency
- **Caveat:** The volume correlation is NOT significant in current data, so this is speculative

---

## Question 7: What would be RECKLESS to change based on current evidence?

### Do NOT make these changes based on this data:

1. **Eliminating long runs**
   - Yes, they show lower efficiency, but that's physiologically normal
   - Long runs build aerobic capacity that enables quality work
   - The correlation is descriptive, not prescriptive

2. **Dramatically changing training schedule (morning vs. evening)**
   - The correlation is weak (r=0.235)
   - Could be confounded by many factors
   - No reason to disrupt your life

3. **Adding rest days**
   - Rest days show ZERO correlation with next-run efficiency
   - If you're already resting appropriately, more rest won't help

4. **Making nutrition changes**
   - There is NO DATA to support or refute any dietary intervention
   - Any change would be a guess

5. **Assuming the efficiency decline means you're getting slower**
   - Efficiency (pace/HR) declined, but we don't know:
     - Did your race times decline?
     - Was this a rest/recovery block?
     - Was there illness, travel, life stress?

---

## Appendix: Raw Observations

### Efficiency Trend by Week:
```
Week 41:  0.1152 (peak, but only 3 runs, likely recovery)
Week 42:  0.0828 (115km volume)
Week 43:  0.0775
Week 44:  0.0802
Week 45:  0.0770
Week 46:  0.0731 (lowest volume weeks begin)
Week 47:  0.0785
Week 48:  0.0753 (volume drops to 70km)
Week 49:  0.0807
Week 50:  0.0652 (29km volume)
Week 51:  0.0800 (only 1 run)
Week 52:  0.0595 (17km volume)
```

**Pattern:** Efficiency is unstable when volume drops below ~60km/week. This could indicate:
- Loss of aerobic fitness
- Different workout composition
- End-of-year recovery/holiday effect

### Best Efficiency Runs (Top 5):
1. 10/31 @ 4.0 min/km, HR 151 — short 1.6km
2. 11/29 @ 4.1 min/km, HR 151 — 21.2km long run (!)
3. 10/31 @ 4.0 min/km, HR 155 — 6.4km
4. 10/31 @ 4.0 min/km, HR 155 — 3.2km
5. 10/23 @ 4.0 min/km, HR 156 — 8.1km

**Note:** Run #2 is interesting — a 21km long run with top-5 efficiency. This suggests it's not just about run length.

### Worst Efficiency Runs (Bottom 5):
1. 11/02 — 33.8km @ 5.7 min/km, HR 134
2. 11/21 — 4.8km @ 5.6 min/km, HR 135
3. 10/31 — 3.2km @ 5.6 min/km, HR 132
4. 12/18 — 14.5km @ 5.9 min/km, HR 129
5. 11/16 — 22.5km @ 6.1 min/km, HR 129

**Note:** The 33.8km run on 11/02 was your longest and least efficient — expected for an ultra-distance effort.

---

## System Integrity Notes

### What this analysis got right:
- Used actual database queries on real data
- Calculated real correlation coefficients
- Applied appropriate significance thresholds
- Identified missing data honestly

### What this analysis could improve:
- True p-value calculation (currently approximated)
- Effect size confidence intervals
- Multivariate regression (controlling for multiple factors)
- Time-series analysis (accounting for autocorrelation)
- Weather data integration (temperature, humidity)

### Confidence in methodology:
- **Data integrity:** HIGH (direct database queries)
- **Statistical rigor:** MEDIUM (correlations are real, but no multivariate analysis)
- **Causal claims:** LOW (correlation ≠ causation)

---

*Report generated by the Diagnostic Engine v0.1*  
*This analysis is descriptive, not prescriptive. Consult your coaching philosophy before making changes.*


