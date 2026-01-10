# Deep Analysis Report - Product Specification

*A comprehensive personalized analysis of what drives an athlete's improvement*

---

## Product Overview

### What It Is
A one-time or periodic deep dive into an athlete's training data that identifies:
1. What factors correlate with their improvement
2. What doesn't matter (despite common belief)
3. Breakthrough periods and what caused them
4. Actionable insights specific to them

### Why It's Valuable
- Generic training advice is everywhere
- THIS report is about THEM
- Data-driven, not opinion-based
- Validates or challenges their assumptions
- Gives clear, actionable next steps

---

## Report Structure

### Section 1: Executive Summary
*1 page, 5 bullet points*

> "Based on 322 runs over 14 months, here's what actually matters for YOUR running:
> 1. Consistency (4+ runs/week) correlates strongly with efficiency (+0.40)
> 2. Volume accumulation pays off - more total miles = better performance
> 3. Your HR has dropped 12 bpm - your aerobic base is building
> 4. HRV does NOT predict your performance - your PRs came on low HRV days
> 5. Sleep duration has minimal effect on your running efficiency"

---

### Section 2: Wellness vs Performance
*The truth about HRV, RHR, Sleep*

**What We Tested:**
- Morning HRV → Same-day efficiency
- Resting HR → Same-day efficiency
- Sleep duration → Same-day efficiency
- Yesterday's wellness → Today's performance

**What We Found:**
| Factor | Correlation | Verdict |
|--------|-------------|---------|
| HRV → Efficiency | r = -0.069 | NO EFFECT |
| RHR → Efficiency | r = +0.046 | NO EFFECT |
| Sleep → Efficiency | r = +0.086 | NO EFFECT |

**Your PRs:**
- Half Marathon PR (1:27:40): HRV=30, Sleep=4.7h
- 10K PR: HRV=19, Sleep=5.4h

**Conclusion:** For you, wellness metrics don't predict performance. Focus on training, not morning readings.

---

### Section 3: What DOES Drive Improvement
*Ranked by statistical strength*

**Top 5 Factors:**

1. **HR Dropping Over Time** (r = -0.58)
   - Your HR has dropped 12 bpm from start to now
   - Same effort = faster pace
   - This IS fitness

2. **Consistency Streak** (r = +0.40)
   - Consecutive weeks of 4+ runs compound
   - Breaking consistency costs more than a single miss

3. **Long Run Distance** (r = +0.35)
   - Long runs → Better efficiency NEXT WEEK
   - The payoff is delayed

4. **Cumulative Volume** (r = +0.31)
   - More total lifetime running = better efficiency
   - Keep running. It adds up.

5. **Runs Per Week** (r = +0.32)
   - More runs = better efficiency
   - Frequency matters

---

### Section 4: Training Progression
*Monthly breakdown with trends*

| Month | Volume | Runs | Efficiency | Avg HR |
|-------|--------|------|------------|--------|
| Oct 24 | 319km | 34 | 0.0813 | 147 |
| ... | ... | ... | ... | ... |
| Nov 25 | 442km | 34 | 0.0874 | 132 |

**Key Trends:**
- Volume: +47% (300→442 km/month)
- Efficiency: +7.5%
- HR: -10% (147→132 bpm)

---

### Section 5: Breakthrough Analysis
*When did you make big jumps?*

**Biggest Efficiency Gains:**
1. July 5, 2025: +10.7% - Returned from break, fresh
2. March 27, 2025: +10.0%
3. July 2-6, 2025: Multiple jumps after summer training start

**Biggest Efficiency Drops:**
1. August 10-11, 2025: -9% - Heat? Fatigue? Investigate.

---

### Section 6: By Workout Type
*Which sessions affect you most?*

| Workout Type | HRV Effect | Notes |
|--------------|------------|-------|
| Easy runs | +0.44 | High HRV = better easy runs |
| Medium-long | -0.35 | High HRV = push harder = lower efficiency |
| Long runs | -0.13 | No effect |
| Recovery | -0.02 | No effect |

**Insight:** When you feel good (high HRV), you run your medium-long runs harder. This tanks efficiency but probably builds fitness.

---

### Section 7: Actionable Recommendations
*What to do next*

Based on YOUR data, not generic advice:

1. **Keep the consistency** - Your streaks strongly correlate with improvement
2. **Don't skip long runs** - The payoff appears next week
3. **Ignore morning HRV** - It doesn't predict your performance
4. **Trust the volume** - Cumulative miles are building your fitness
5. **Your HR drop is the signal** - That's real fitness, not a gadget score

---

### Section 8: What We Can't Answer Yet
*Data gaps*

- No nutrition data logged - can't correlate food to performance
- No strength training data - can't assess cross-training effects
- No race history beyond Strava - limited PR context
- Daily check-ins sparse - subjective data incomplete

**To unlock these insights:** Log check-ins, nutrition, strength work.

---

## Pricing Options

### Option A: One-Time Deep Dive
- **Price:** $49-99
- **Includes:** Full report, PDF export, 30-min video walkthrough
- **When:** After 3+ months of data

### Option B: Monthly Insights
- **Price:** $15/month add-on to Pro tier
- **Includes:** Automated monthly summary, trend tracking
- **When:** Ongoing

### Option C: Coach Package
- **Price:** $199/athlete
- **Includes:** Full analysis + coach debrief call
- **When:** For coached athletes

---

## Technical Requirements

### Data Needed
- 50+ activities with HR data
- 8+ weeks of training
- (Optional) Wellness data for correlation
- (Optional) Check-ins for subjective data

### Processing
1. Load activities from DB
2. Calculate weekly aggregates
3. Run correlation analysis
4. Identify breakthrough periods
5. Generate recommendations
6. Render report (PDF/HTML/In-app)

### AI Component
- Use OpenAI to generate narrative from data
- Personalize tone based on athlete preferences
- Highlight insights specific to them

---

## Competitive Advantage

| Feature | Us | TrainingPeaks | Strava |
|---------|----|--------------| -------|
| Personalized correlations | ✅ | ❌ | ❌ |
| What matters for YOU | ✅ | ❌ | ❌ |
| HRV/Sleep analysis | ✅ | ✅ | ❌ |
| Breakthrough detection | ✅ | Partial | ❌ |
| Plain language insights | ✅ | ❌ | ❌ |
| Coach-quality analysis | ✅ | ❌ | ❌ |

---

## Next Steps

1. Build report generation pipeline
2. Design PDF/HTML template
3. Integrate with OpenAI for narrative
4. Create in-app preview
5. Build purchase/subscription flow
6. Beta test with Michael's data

---

*Product Specification v1.0 - 2026-01-08*


