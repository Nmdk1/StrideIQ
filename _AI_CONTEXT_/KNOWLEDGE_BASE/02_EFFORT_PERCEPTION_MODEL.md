# RPE (Rate of Perceived Exertion) Model

## The Key Insight

**The same pace/HR produces different RPE based on workout structure.**

| Workout | Pace | Duration | Expected RPE |
|---------|------|----------|--------------|
| 40 min continuous threshold | T-pace | 40 min | 8-9 (race-like) |
| 6 × 5 min threshold intervals | T-pace | 30 min work | 6-7 (manageable) |
| 20 min tempo | T-pace | 20 min | 6-7 |
| 8 × 1 min VO2max | I-pace | 8 min work | 7-8 |
| 20 × 400m | R-pace | 8 min work | 6-7 |

The **recovery structure** dramatically changes the subjective experience.

---

## Three Separate Metrics

We track three distinct concepts:

### 1. Workout Type (Structure)
**Auto-detected from GPS/lap data**

What was the STRUCTURE of the workout?
- Continuous vs. Intervals
- Duration of work segments
- Recovery length and intensity
- Progression pattern

Examples: `tempo_continuous`, `tempo_intervals_5x5`, `progression_long_run`

### 2. Intensity Score (Objective, 0-100)
**Calculated from pace/HR data**

What was the physiological LOAD?
- Based on pace relative to thresholds
- Based on HR relative to max
- Continuous spectrum, not zones

This is what the DATA shows, not what it felt like.

### 3. RPE - Rate of Perceived Exertion (Subjective, 1-10)
**Reported by athlete post-run**

What did it FEEL like?
- Standard RPE 1-10 scale (Borg CR-10)
- Captured via ActivityFeedback
- Separate from objective intensity

---

## Expected RPE Model

For each workout type + duration, we model expected RPE:

### Continuous Threshold Efforts

| Duration | Expected RPE | Notes |
|----------|--------------|-------|
| 15-20 min | 6-7 | Comfortably hard |
| 25-30 min | 7-8 | Hard |
| 35-40 min | 8-9 | Very hard, race-like |
| 45+ min | 9-10 | Near maximal |

### Threshold Intervals (with recovery)

| Structure | Expected RPE | Notes |
|-----------|--------------|-------|
| 4-6 × 3-5 min, 2+ min recovery | 6-7 | Manageable |
| 6-8 × 5 min, 1 min recovery | 7-8 | Hard |
| 3 × 10 min, 2 min recovery | 7-8 | Hard |
| 2 × 20 min, 2 min recovery | 8-9 | Very hard |

### VO2max Intervals

| Structure | Expected RPE | Notes |
|-----------|--------------|-------|
| 6-8 × 2-3 min, equal recovery | 7-8 | Standard |
| 10-12 × 1 min, 1 min recovery | 6-7 | Shorter feels easier |
| 4-5 × 4-5 min, 3 min recovery | 8-9 | Long VO2 is brutal |

### Easy/Recovery

| Duration | Expected RPE | Notes |
|----------|--------------|-------|
| Any | 2-4 | Should feel easy |
| If RPE > 5 | Flag it | Not actually easy |

### Long Runs

| Duration | Expected RPE | Notes |
|----------|--------------|-------|
| 90-120 min easy | 4-6 | Moderately tiring |
| 120+ min easy | 6-7 | Fatiguing |
| With fast finish | 7-8 | Hard by end |

---

## RPE Gap Analysis

The difference between Expected RPE and Actual RPE is a training signal:

### Actual RPE > Expected RPE (Felt Harder)
Possible causes:
- **Accumulated fatigue** - need more recovery
- **Life stress** - work, sleep, emotional
- **Under-fueled** - glycogen depleted
- **Illness coming** - early warning
- **Heat/humidity** - environmental stress
- **Altitude** - if traveling

**Action:** Flag for coach/system attention

### Actual RPE < Expected RPE (Felt Easier)
Possible causes:
- **Fitness improvement** - they've adapted
- **Fresh legs** - well recovered
- **Favorable conditions** - cool, downhill, tailwind
- **Pace was conservative** - sandbagged

**Action:** Consider increasing load or pace

### RPE Gap Thresholds

| Gap | Meaning |
|-----|---------|
| ±1 | Normal variation |
| ±2 | Worth noting |
| ±3+ | Significant signal |

---

## Simple Athlete Override

Athletes shouldn't pick from 50 workout variants. The system should:

### Auto-Detect from Data
1. Continuous vs. Intervals (from pace variance)
2. Duration/structure (from lap data)
3. Progression pattern (from split analysis)
4. Recovery segments (from pace drops)

### Simple Override Options
If auto-detection is wrong, athlete picks from SIMPLE categories:

| Category | Description |
|----------|-------------|
| **Easy** | Recovery, easy run, shakeout |
| **Long** | Long run (easy or with workout) |
| **Tempo** | Sustained threshold effort |
| **Intervals** | Repeated hard efforts with recovery |
| **Race** | Competition or time trial |
| **Other** | Something else (add note) |

### System Figures Out Details
Based on simple category + data:
- "Intervals" + 5 distinct fast segments = "5 × something"
- "Tempo" + 40 min sustained = "continuous threshold"
- "Long" + last 3 mi faster = "fast finish long run"

---

## Implementation Notes

### Interval Detection Algorithm
```
1. Get lap/split data (km splits or manual laps)
2. Calculate pace variance
3. If high variance (CV > 20%):
   - Look for alternating fast/slow pattern
   - Count distinct "work" segments (pace < threshold + 10%)
   - Count "recovery" segments (pace > easy pace)
4. If pattern detected:
   - Classify as intervals
   - Record structure: N × duration, recovery duration
```

### Duration Factor
```
same_intensity_longer_duration = higher_expected_RPE

For threshold (T-pace):
- 20 min continuous → expected RPE 6-7
- Each additional 5 min → +0.5 expected RPE
- 40 min continuous → expected RPE 8-9

For intervals:
- Longer work segments → higher expected RPE
- Shorter recovery → higher expected RPE
- More reps → higher expected RPE (fatigue accumulation)
```

### Athlete RPE Calibration
Over time, learn THIS athlete's RPE patterns:
- "Michael typically rates easy runs RPE 3"
- "Michael's threshold intervals average RPE 6.5"
- If his RPE 8 on intervals → something unusual

---

## UI Implications

### Post-Run Flow
1. Auto-classification shown: "Looks like Tempo Intervals (5 × 5 min)"
2. Simple confirm/override: "Is this right? [Yes] [Change]"
3. RPE prompt: "How hard did that feel? [1-10]"
4. If RPE gap > 2: "That felt harder/easier than expected. Anything unusual today?"

### Activity Display
Show all three metrics:
- **Type:** Tempo Intervals (5 × 5 min @ T)
- **Intensity:** 72/100 (calculated)
- **RPE:** 7/10 (reported)
- **Expected RPE:** 6-7 ✓ (or ⚠️ if gap)

---

## Connection to Comparison Engine

When comparing workouts:
- Compare same TYPE (tempo vs tempo, not tempo vs easy)
- Note RPE differences: "Last month this workout felt RPE 6, now RPE 5 - improvement?"
- Track RPE trends over time: "Your average RPE for threshold work is declining - good sign"

---

*This model allows us to capture the full picture: what the workout WAS, what it COST physiologically, and how it FELT - all as separate, meaningful metrics.*
