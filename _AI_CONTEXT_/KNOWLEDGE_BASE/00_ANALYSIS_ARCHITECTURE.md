# Analysis Architecture Requirements

## Core Principle
**The system must work with runs only.** Everything else is optional enhancement.

Athletes are notoriously bad at logging anything that doesn't happen automatically. The system cannot depend on manual input for core functionality.

---

## Multi-Scale Analysis Framework

### Scale 1: Individual Run
**Question:** How did this run go relative to similar runs?

Compare against:
- Previous run of same type (tempo vs last tempo)
- Same run type in same week position (Tuesday tempo vs Tuesday tempos)
- Same workout at different points in build (week 2 tempo vs week 5 tempo)
- What preceded it (yesterday's run, 3-day load, 7-day load)

Metrics:
- Pace at HR (efficiency)
- HR drift during run
- Splits pattern (even, positive, negative)
- Perceived effort (if logged)

### Scale 2: Training Block (Microcycle)
**Question:** Is this block producing expected adaptations?

A block is typically 1-3 weeks with a specific focus.

Analyze:
- Component mix (% easy, tempo, interval, long)
- Total load (volume × intensity)
- Recovery adequacy (are easy days easy enough?)
- Trend within block (improving, stable, declining)

Compare against:
- Previous block of same type
- Same block position in previous builds

### Scale 3: Training Build (Mesocycle)
**Question:** Is this build on track for the goal race?

A build is typically 8-20 weeks targeting a specific race/goal.

Detect phases within build:
- Base (high volume, low intensity)
- Build (moderate volume, increasing intensity)
- Peak (key workouts, race-specific)
- Taper (reduced volume, maintained intensity)
- Race
- Recovery

Analyze:
- Volume progression (is it following plan?)
- Intensity progression (are key workouts improving?)
- Key workout trends (long run pace, tempo pace, interval times)
- Fatigue accumulation vs performance output

### Scale 4: Season/Year (Macrocycle)
**Question:** Is this year better than last year?

Analyze:
- Build-over-build improvement
- Annual volume trends
- Injury frequency and duration
- PR progression
- Consistency (weeks with 0-1 runs)

### Scale 5: Career (Multi-Year)
**Question:** What's the long-term trajectory?

Track:
- Year-over-year improvement rates
- Volume capacity growth
- Injury resilience changes
- Race time progressions by distance

---

## Correlation Framework

### Time-Lag Analysis
Don't just correlate same-day. Correlate:
- This run's inputs → this run's outputs (immediate)
- This week's training → next week's performance (short-term)
- This block's load → next block's fitness (medium-term)
- This build's consistency → race outcome (long-term)

### Within-Type Comparison
Compare like to like:
- Tempo runs to tempo runs
- Long runs to long runs
- Easy runs to easy runs (are they truly easy?)
- Intervals to intervals (same rep scheme only)

### Combination Effects
Track how combinations affect outcomes:
- Long run Saturday + easy Sunday → Monday quality session
- Two hard days back-to-back → mid-week fatigue
- Three consecutive high-volume weeks → performance dip vs adaptation

---

## Phase Detection Algorithm (To Build)

Automatically detect phases based on:
1. Volume trend (increasing = build, decreasing = taper)
2. Intensity distribution (more threshold work = build, more easy = base)
3. Long run frequency and length
4. Key workout presence and spacing
5. Race detection (flagged activities or inferred from effort)

---

## Race Detection (To Build)

Infer race from:
- Activity name contains "race", "marathon", "5k", etc.
- All-out effort (HR at max, pace at threshold or faster)
- Unusual distance (exactly 5k, 10k, 21.1k, 42.2k)
- Weekend timing
- Followed by rest or very easy running

Allow manual flagging to override.

---

## Injury Tracking (To Build)

Capture:
- Injury date (onset)
- Injury type (bone, muscle, tendon, etc.)
- Affected body part
- Return-to-run date
- Activities during injury (diagnostic runs, cross-training)

Flag all activities in injury window as "injury-affected."
Exclude from normal trending unless specifically analyzing injury patterns.

---

## Optional Enhancement Inputs

### Nutrition
- Pre-run fuel (timing, type, quantity)
- During-run fuel (for long runs)
- Post-run recovery (protein timing, hydration)
- Daily nutrition (if logged)

Correlate:
- Fuel timing → long run performance
- Hydration → heat performance
- Protein timing → recovery quality

### Sleep
- Duration
- Quality (1-5)
- Wake time relative to run

Correlate:
- Sleep → same-day performance
- Sleep patterns → weekly trends

### Life Stress
- Work stress (1-5)
- Life events (travel, illness, family)
- Mental fatigue

Correlate:
- Stress → performance
- Accumulated stress → injury risk

### Lab Work
- Blood panels (ferritin, vitamin D, thyroid, etc.)
- Track over time
- Correlate to performance periods

### Pre-Session Readiness
- Wahoo-style alertness tests
- HRV readings
- Resting HR trend

---

## Output: Insights and Prescriptions

The system should produce:

### Descriptive (What happened)
- "Your tempo runs have improved 15 sec/km over this build"
- "Your long runs are consistently 10% slower than goal pace"
- "Week 4 showed signs of overreaching"

### Diagnostic (Why it happened)
- "The improvement correlates with increased threshold volume"
- "The fatigue spike followed three consecutive 100km weeks"
- "Performance dipped when sleep averaged under 6 hours"

### Prescriptive (What to do next)
- "Based on your pattern, reduce volume by 20% next week"
- "Your tempo runs respond best to 10-14 days rest between"
- "Similar athletes see best results with 2 quality sessions per week, not 3"

---

## Example: Michael's Nov 29 Half Marathon PR

Correct analysis would show:

**Build Phase (Oct-Nov 24):**
- Volume: 100-115km/week
- Key workouts: Improving tempo paces
- Long runs: Building to 30km+
- Efficiency trend: Stable or improving

**Taper Phase (Nov 24-29):**
- Volume: Reduced 40-50%
- Intensity: Maintained
- Freshness: Increasing

**Race (Nov 29):**
- Distance: 21.1km
- Result: 7-minute PR
- Outcome: Massive success

**Recovery Phase (Nov 30 - Dec 13):**
- Note: Bone injury Nov 25 (ran race injured!)
- Volume: Minimal
- Intensity: Easy only
- Purpose: Recovery + diagnostic

**Race #2 (Dec 13):**
- Distance: 10km
- Result: 3-minute PR (while injured!)
- Context: Exceptional performance despite injury

**Post-Race Recovery (Dec 14-31):**
- All runs: Diagnostic/recovery
- Purpose: Heal bone injury
- Expected efficiency: Low (intentional)

**System should NOT report:**
- "Efficiency declined 5.5%"

**System SHOULD report:**
- "Successful build → 7min half PR"
- "Exceptional 10k PR despite injury"
- "Currently in recovery phase - low efficiency expected"
- "Ready to resume: [when injury cleared]"


