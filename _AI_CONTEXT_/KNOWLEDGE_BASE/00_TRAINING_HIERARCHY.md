# Training Hierarchy Model

## The Complete Structure

```
CAREER (multi-year)
│
├── SEASON (annual cycle)
│   │
│   ├── BUILD (macrocycle, 8-24 weeks)
│   │   │
│   │   ├── BLOCK/PERIOD (mesocycle, 2-6 weeks)
│   │   │   │
│   │   │   ├── WEEK (microcycle, 7 days)
│   │   │   │   │
│   │   │   │   ├── WORKOUT (single session)
│   │   │   │   │   │
│   │   │   │   │   ├── TYPE (category)
│   │   │   │   │   │   │
│   │   │   │   │   │   └── VARIATION (specific execution)
```

---

## Level Definitions

### CAREER
- All training history for the athlete
- Multi-year trajectory
- Used for: Long-term trends, injury patterns, volume capacity changes

### SEASON
- Annual training cycle (may have 2-3 builds per season)
- Typically follows racing calendar
- Used for: Year-over-year comparison, annual planning

### BUILD (Macrocycle)
- Training block targeting a specific goal race
- Typically 8-24 weeks
- Has distinct phases: Base → Build → Peak → Taper → Race → Recovery
- Used for: Assessing training cycle effectiveness, predicting race outcome

### BLOCK/PERIOD (Mesocycle)
- Focus period within a build
- Typically 2-6 weeks
- Examples: "Base Phase", "Speed Development", "Race Specific", "Taper"
- Used for: Tracking adaptation within a training focus

### WEEK (Microcycle)
- 7-day training unit
- Repeating pattern of workouts
- Examples: "Recovery week", "Build week", "Key week"
- Used for: Fatigue/freshness tracking, weekly load balance

### WORKOUT
- Single training session
- Has duration, distance, intensity
- Used for: Immediate performance assessment

### TYPE
- Category of workout by purpose
- Examples: Easy, Long, Tempo, Interval, Recovery, Race
- Used for: Comparing like-to-like

### VARIATION
- Specific execution of a workout type
- Examples within "Tempo":
  - Steady tempo (continuous)
  - Cruise intervals (broken tempo with short rest)
  - Progression tempo (start slower, finish at tempo)
  - Cutdown (each rep faster)
- Used for: Fine-grained comparison, prescription specificity

---

## Example: Michael's Nov 29 Half Marathon PR

```
CAREER
└── 2025 SEASON
    └── BUILD: Fall Half Marathon Prep (Sept - Nov 29)
        │
        ├── BLOCK 1: Base (Sept)
        │   ├── Week 1: Introduction
        │   ├── Week 2: Volume build
        │   ├── Week 3: Volume build
        │   └── Week 4: Recovery/adaptation
        │
        ├── BLOCK 2: Build (Oct)
        │   ├── Week 5: Tempo introduction
        │   │   ├── Mon: Easy (recovery)
        │   │   ├── Tue: Tempo (cruise intervals, 3x10min)
        │   │   ├── Wed: Easy (aerobic)
        │   │   ├── Thu: Intervals (VO2max, 5x1000m)
        │   │   ├── Fri: Easy (recovery)
        │   │   ├── Sat: Long (progressive)
        │   │   └── Sun: Easy (recovery)
        │   ├── Week 6: ...
        │   ├── Week 7: ...
        │   └── Week 8: Recovery
        │
        ├── BLOCK 3: Peak/Race Specific (Nov 1-24)
        │   ├── Week 9: Race pace focus
        │   ├── Week 10: Key workout week
        │   ├── Week 11: Sharpening
        │   └── Week 12: Pre-taper
        │
        ├── BLOCK 4: Taper (Nov 24-28)
        │   └── Week 13: Taper
        │
        └── RACE: Nov 29 - Half Marathon (7-min PR!)
```

---

## Analysis at Each Level

### At WORKOUT Level
- Compare this tempo to last tempo
- Was this harder/easier than expected?
- How does HR compare at same pace?

### At TYPE Level
- Are tempo runs improving week over week?
- Is easy running truly easy (HR in zone)?
- Are long runs getting more efficient?

### At VARIATION Level
- Do cruise intervals produce better race results than steady tempos?
- Does this athlete respond better to progression runs or even-paced?

### At WEEK Level
- Is this week's load appropriate for this point in the block?
- Is recovery adequate between quality sessions?
- Is the hard/easy balance correct?

### At BLOCK Level
- Is this phase producing expected adaptations?
- How does this base phase compare to previous base phases?
- Are key workouts improving across the block?

### At BUILD Level
- Is this build on track for goal race?
- How does volume/intensity compare to previous successful builds?
- What's the predicted race outcome based on key workouts?

### At SEASON Level
- Is this year better than last year at same point?
- What's the injury trend this year?
- How many races, what results?

### At CAREER Level
- What's the 3-year PR trajectory?
- Has injury frequency decreased as training matured?
- What's the sustainable weekly volume?

---

## Comparison Rules

### Same Level Only
- Compare tempo to tempo, not tempo to easy
- Compare base block to base block, not base to taper
- Compare first week of build to first week of previous build

### Same Context
- Week 3 of base phase in Build A → Week 3 of base phase in Build B
- Not week 3 of base → week 3 of taper

### Appropriate Lag
- This week's training → next week's key workout
- This block's load → next block's adaptation
- This build's training → race day result

---

## Automatic Detection (To Build)

The system should automatically detect:

1. **Workout Type** - from pace, HR, duration, pattern (✓ have classifier)
2. **Variation** - from interval structure, progression pattern
3. **Week Type** - from total load vs recent average
4. **Block Transitions** - from volume/intensity trend changes
5. **Build Phases** - from multi-week patterns
6. **Race Days** - from all-out effort + specific distances

Manual override always available for corrections.


