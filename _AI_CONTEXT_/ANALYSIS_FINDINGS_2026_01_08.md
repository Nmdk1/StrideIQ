# Analysis Findings - Michael Shaffer

**Date:** 2026-01-08
**Data:** 322 runs, 505 days wellness, 113 days HRV

---

## Key Finding: HRV Does NOT Predict Performance

### Overall Correlations (All Runs)

| Factor | r-value | n | Interpretation |
|--------|---------|---|----------------|
| HRV → Efficiency | -0.069 | 95 | No effect |
| Resting HR → Efficiency | +0.046 | 95 | No effect |
| Sleep Duration → Efficiency | +0.086 | 319 | No effect |
| Yesterday's Sleep → Today's Eff | -0.110 | 318 | Slight negative |

**Conclusion:** At the aggregate level, HRV/RHR/Sleep don't predict efficiency.

---

## By Run Type

| Run Type | HRV → Efficiency | n | Impact |
|----------|------------------|---|--------|
| Easy | +0.444 | 5 | HIGH (small sample) |
| Medium-Long | -0.346 | 17 | HIGH (unexpected direction) |
| Recovery | -0.018 | 49 | None |
| Long Run | -0.128 | 20 | None |

**Interpretation:**
- Easy runs: High HRV = better efficiency (expected)
- Medium-long runs: High HRV = WORSE efficiency (unexpected - possibly runs harder when feeling good)

---

## High vs Low HRV Days

| Condition | n | Avg Efficiency |
|-----------|---|----------------|
| High HRV (≥29) | 64 | 0.0868 |
| Low HRV (<29) | 31 | 0.0869 |
| **Difference** | | **0.1%** (nothing) |

---

## Good vs Poor Sleep

| Condition | n | Avg Efficiency |
|-----------|---|----------------|
| Good sleep (≥6.9h) | 161 | 0.0861 |
| Poor sleep (<6.9h) | 158 | 0.0839 |
| **Difference** | | **+2.6%** (small signal) |

---

## Best vs Worst Efficiency Runs

### TOP 10 Runs (Highest Efficiency)

| Date | Efficiency | HRV | Sleep | Distance | Type |
|------|------------|-----|-------|----------|------|
| 2025-11-30 | 0.1030 | 22 | 6.3h | 24.9km | long_run |
| 2025-10-31 | 0.0995 | 31 | 8.1h | 1.6km | easy |
| 2025-11-12 | 0.0994 | 26 | 6.9h | 6.3km | recovery |
| 2025-10-12 | 0.0990 | 29 | 4.8h | 29.0km | long_run |
| **2025-12-13** | **0.0968** | **19** | **5.4h** | **10.1km** | **tempo (10K PR!)** |
| **2025-11-29** | **0.0962** | **30** | **4.7h** | **21.2km** | **long_run (HM PR!)** |

**TOP 10 AVERAGES:** HRV=28.2, Sleep=6.7h

### BOTTOM 10 Runs (Lowest Efficiency)

| Date | Efficiency | HRV | Sleep | Distance | Type |
|------|------------|-----|-------|----------|------|
| 2025-11-02 | 0.0792 | 28 | 6.5h | 33.8km | long_run |
| 2025-10-05 | 0.0745 | 29 | 6.2h | 24.3km | long_run |

**BOTTOM 10 AVERAGES:** HRV=30.4, Sleep=6.8h

### Comparison

| Metric | TOP 10 | BOTTOM 10 | Diff |
|--------|--------|-----------|------|
| HRV | 28.2 | 30.4 | **-2.2** (lower HRV = better!) |
| Sleep | 6.7h | 6.8h | -0.1h (no difference) |

**Critical insight:** PRs came on LOW HRV and SHORT sleep.

---

## Monthly Progression

| Month | Runs | Volume | Avg Eff | Avg HR | HRV |
|-------|------|--------|---------|--------|-----|
| Oct 24 | 34 | 319km | 0.0813 | 147 | - |
| Nov 24 | 32 | 300km | 0.0844 | 143 | - |
| Dec 24 | 28 | 311km | 0.0834 | 137 | - |
| Jan 25 | 27 | 287km | 0.0835 | 134 | - |
| Feb 25 | 19 | 187km | 0.0844 | 138 | - |
| Mar 25 | 26 | 230km | 0.0846 | 142 | - |
| Jul 25 | 20 | 274km | 0.0891 | 131 | - |
| Aug 25 | 23 | 285km | 0.0829 | 139 | - |
| Sep 25 | 29 | 344km | 0.0865 | 136 | 32 |
| Oct 25 | 34 | 415km | 0.0879 | 136 | 29 |
| **Nov 25** | **34** | **442km** | **0.0874** | **132** | 30 |
| Dec 25 | 16 | 160km | 0.0858 | 132 | 27 |

**What drove improvement:**
1. Volume: 300km → 442km (+47%)
2. Avg HR dropped: 147 → 132 (-10%)
3. Efficiency improved: 0.0813 → 0.0874 (+7.5%)
4. HRV actually dropped as fitness improved (32 → 27)

---

## Conclusions for Michael

1. **HRV is noise for you** - your PRs came on low HRV days
2. **Sleep duration has minimal effect** - 4.7h sleep = HM PR
3. **What matters is the training** - progressive volume, HR adaptation
4. **Training load suppresses HRV** - but builds fitness
5. **This validates your philosophy** - "HRV has no reproducible science"

---

## Implications for the Product

1. Don't over-index on HRV as a readiness metric
2. Track it as a correlate, not a prescription
3. Focus on training progression metrics:
   - Volume trends
   - HR at given pace (efficiency)
   - Workout type distribution
4. Individual variation matters - what doesn't work for Michael may work for others
5. Build athlete-specific models over time

---

---

## Part 2: What ACTUALLY Drives Improvement

### Ranked Correlations (Strongest First)

| Factor | r-value | n | Strength |
|--------|---------|---|----------|
| **Time → Average HR** | **-0.582** | 54 | **STRONG** |
| **Consistency Streak → Efficiency** | **+0.398** | 54 | **MODERATE** |
| **Cumulative Volume → Efficiency** | **+0.308** | 54 | **MODERATE** |
| Long Run Distance → Next Week Eff | +0.347 | 53 | MODERATE |
| Runs Per Week → Efficiency | +0.318 | 54 | MODERATE |
| Rolling 4-Week Volume → Efficiency | +0.243 | 50 | WEAK |
| Previous Week Volume → Efficiency | +0.273 | 53 | WEAK |
| 20km+ Long Runs (4 weeks) → Efficiency | +0.139 | 50 | WEAK |

### What Does NOT Matter

| Factor | r-value | Interpretation |
|--------|---------|----------------|
| High Intensity Runs/Week | -0.084 | No effect |
| High Intensity Ratio | -0.120 | No effect (maybe negative?) |
| Previous Week High Intensity | -0.166 | Slight negative |

---

## Breakthrough Periods

**Top 5 Efficiency Jumps:**
1. 2025-07-05: +10.7% (return from break)
2. 2025-03-27: +10.0%
3. 2025-07-03: +9.8%
4. 2025-07-02: +9.3%
5. 2025-07-06: +9.2%

**Top 5 Efficiency Drops:**
1. 2025-08-11: -9.5%
2. 2025-07-26: -8.4%
3. 2025-08-10: -8.1%
4. 2025-08-03: -8.0%
5. 2025-08-05: -7.7%

---

## Key Metrics Over Time

| Period | Avg HR | Avg Efficiency |
|--------|--------|----------------|
| First 10 Weeks | 144 bpm | 0.0829 |
| Last 10 Weeks | 132 bpm | 0.0864 |
| **Change** | **-12 bpm** | **+4.2%** |

---

## Actionable Insights for Michael

### 1. Keep Running (Volume Matters)
- Cumulative volume correlates with efficiency (r=0.308)
- More total running = better efficiency

### 2. Stay Consistent (Streaks Compound)
- Consistency streak → Efficiency (r=0.398)
- Consecutive weeks of 4+ runs build on each other
- Breaking consistency costs more than a single missed run

### 3. Long Runs Pay Off
- Long run distance → Next week efficiency (r=0.347)
- The benefit appears the following week

### 4. HR is Dropping (Fitness Building)
- Strongest signal: Time → HR (r=-0.582)
- HR dropped 12 bpm from start to now
- Same effort = faster pace

### 5. High Intensity ≠ Better Efficiency
- High intensity runs show negative correlation
- Suggests recovery/easy runs are where efficiency is measured
- Hard runs fatigue, but build fitness for later

---

## The Story in Numbers

From Oct 2024 to Nov 2025:
- Volume: 300km/month → 442km/month (+47%)
- Runs: 32/month → 34/month (+6%)
- HR: 147 → 132 (-10%)
- Efficiency: 0.0813 → 0.0874 (+7.5%)

**Result: Couch to 1:27 Half Marathon in 2 years at age 57.**

---

## Product Implications

This type of report should be offered as:
1. **One-time deep analysis** - $50-100 for comprehensive review
2. **Monthly subscription add-on** - automated monthly insights
3. **Investor demo** - shows the depth of analysis possible

Key differentiator: We find what matters for THIS athlete, not generic advice.

---

*Analysis completed: 2026-01-08*

