# Plan Generation System

**Last Updated:** January 10, 2026  
**Status:** Foundation Complete - Ready for Implementation

---

## Product Tiers for Plans

| Tier | Price | Personalization | How It Works |
|------|-------|-----------------|--------------|
| **Free** | $0 | None | Fixed plan with effort descriptions (no paces) |
| **Fixed Plan** | $5 | Paces only | User enters race time in Training Pace Calculator → Plan populates with their specific paces |
| **Custom** | TBD | Full | Questionnaire + data → AI-generated plan |
| **Guided Self-Coaching** | TBD | Dynamic | Ongoing adjustments based on data |

**Current Focus: Free + $5 Fixed Plans**

---

## Plan Matrix

### Distances
- 5K
- 10K
- Half Marathon
- Full Marathon

### Mileage Tiers

| Tier | 5K/10K Range | Half/Full Range | Description |
|------|--------------|-----------------|-------------|
| **Low** | <30 mi/wk | <40 mi/wk | Beginners, time-constrained |
| **Mid** | 30-50 mi/wk | 40-65 mi/wk | Experienced recreational |
| **High** | 50-70 mi/wk | 65-85 mi/wk | Competitive amateurs |
| **Monster** | 70+ mi/wk | 85+ mi/wk | Elite amateurs, semi-pro |

### Days Per Week
- 4 days (Low/Mid only)
- 5 days (All tiers)
- 6 days (Mid/High/Monster)
- 7 days (High/Monster only)

### Durations

| Distance | Standard | Extended |
|----------|----------|----------|
| 5K | 8 weeks | 12 weeks |
| 10K | 8 weeks | 12 weeks |
| Half Marathon | 12 weeks | 16 weeks |
| Full Marathon | 12 weeks | 18 weeks |

---

## Volume Progression Rules

### Building Phase Pattern
```
Week 1: Starting volume
Week 2: +5-10%
Week 3: +5-10%
Week 4: CUT-BACK (-25%)
Week 5: Resume at Week 3 level
Week 6: +5%
Week 7: +5%
Week 8: CUT-BACK (-25%)
...continue to peak...
```

### Peak and Hold
- Peak mileage should HOLD for 2-3 weeks before taper
- This allows fitness to consolidate
- Not every week should be a new high

### Taper Pattern

| Race Distance | Taper Length | Volume Reduction |
|---------------|--------------|------------------|
| 5K | 4-7 days | 30-40% |
| 10K | 7-10 days | 40-50% |
| Half Marathon | 10-14 days | 50-60% |
| Marathon | 14-21 days | 50-60% |

### Cut-back Week Rules
- Default: Every 4th week
- Option: Every 3rd week (for those who need more recovery)
- Volume reduction: 20-30%
- Intensity: Reduced but not eliminated (short T session OK)
- Long run: Shortened, very easy effort

---

## Phase Definitions

### 1. BASE Phase
**Duration:** 3-4 weeks (marathon), 2-3 weeks (shorter races)
**Purpose:** Build aerobic foundation, establish volume

**What happens:**
- 80-90% easy running
- Strides after easy runs (6-8 × 20s)
- Short hill sprints (4-8 × 8s) for neuromuscular
- Long runs building to moderate distance (14-16 mi for marathon)
- NO threshold work yet
- NO MP work yet

**Weekly pattern (5-day example):**
| Day | Workout |
|-----|---------|
| Sun | Long run (easy) |
| Mon | Gym + rest |
| Tue | Easy + strides |
| Wed | Easy |
| Thu | Gym |
| Fri | Easy |
| Sat | Easy + hill sprints |

### 2. BUILD 1 Phase (Threshold Introduction)
**Duration:** 3-4 weeks
**Purpose:** Introduce threshold work, continue volume build

**What happens:**
- T-work introduced (starts with intervals, progresses toward continuous)
- Long runs continue building
- Strides/hills maintained
- NO MP work yet

**T-Block Progression Example:**
- Week 1: 6 × 5 min @ T, 2 min jog
- Week 2: 5 × 6 min @ T, 2 min jog
- Week 3: 4 × 8 min @ T, 2 min jog
- (cut-back week)
- Week 5: 3 × 10 min @ T, 2 min jog

### 3. BUILD 2 Phase (MP Introduction)
**Duration:** 3-4 weeks
**Purpose:** Introduce marathon-pace work, race-specific fitness

**What happens:**
- MP work introduced in long runs (start with 4 mi, build to 6 mi)
- T-work continues (progressing toward continuous)
- Volume approaching peak

**Intensity Rule:**
- If long run has MP work → No T that week (easy mid-week)
- If T mid-week → Long run stays pure easy

**Weekly pattern alternates:**
| Week Type | Tuesday | Long Run (Sunday) |
|-----------|---------|-------------------|
| A | Threshold | Easy |
| B | Easy | MP finish (4-6 mi) |

### 4. PEAK Phase
**Duration:** 2-3 weeks
**Purpose:** Hold peak volume, race-specific work, confidence

**What happens:**
- Volume holds steady (within 2-4 mi of peak)
- Longest runs (20-22 mi for marathon)
- MP work extends (6-8 mi segments)
- Dress rehearsal long run (~3 weeks out)
- T-work maintained but not progressing

**Key workouts:**
- 20 mi with 6 @ MP (mid-run)
- 22 mi easy (pure aerobic volume)
- 20 mi with 8 @ MP (dress rehearsal)

### 5. TAPER Phase
**Duration:** 2-3 weeks (marathon), 1-2 weeks (shorter)
**Purpose:** Reduce fatigue, maintain fitness, peak for race

**What happens:**
- Volume drops 40-60%
- Long run shortened significantly (12-14 mi last one)
- One short T session maintained (sharpening)
- Strides maintained
- Extra rest, sleep, nutrition focus

---

## Weekly Structure Templates

### 5 Days/Week
| Day | Base Phase | Build Phase | Peak Phase | Taper |
|-----|------------|-------------|------------|-------|
| Sun | Long (easy) | Long or Long+MP | Long+MP or Easy | Race/Short |
| Mon | Gym | Gym | Gym (light) | Rest |
| Tue | Easy+strides | Threshold | Easy or T | Short T |
| Wed | Easy | Easy | Easy | Easy |
| Thu | Gym | Gym | Gym (optional) | Rest |
| Fri | Easy | Easy | Easy or T | Easy+strides |
| Sat | Easy+hills | Easy+strides | Easy+strides | Easy |

### 6 Days/Week
Same as 5-day but add:
- Wednesday becomes easy run instead of potential rest
- Or add recovery run on Thursday

### 4 Days/Week
| Day | Base | Build | Peak |
|-----|------|-------|------|
| Sun | Long | Long or Long+MP | Long+MP |
| Mon | Rest | Rest | Rest |
| Tue | Easy+strides | Threshold | Threshold |
| Wed | Rest | Rest | Rest |
| Thu | Easy | Easy+strides | Easy |
| Fri | Rest | Rest | Rest |
| Sat | Easy+hills | Easy | Easy+strides |

---

## Workout Definitions (For Plan Display)

### Effort Descriptions (Free Plans)
Use these when paces aren't known:

| Workout Type | Effort Description |
|--------------|-------------------|
| Easy | Conversational pace, can talk in full sentences |
| Long Run | Same as easy, just longer |
| Recovery | Very easy, slower than normal easy |
| Threshold (T) | Comfortably hard, could hold for ~1 hour in a race |
| Marathon Pace | Goal marathon effort, controlled |
| Strides | Fast but relaxed, 20-30 seconds |
| Hill Sprints | 8-10 seconds, max effort |
| Hill Strides | 30 seconds, strong but controlled |

### Pace Descriptions ($5 Plans - After Training Pace Calculator)
User enters recent race time → system calculates:

| Workout Type | Pace Source |
|--------------|-------------|
| Easy | Easy pace from calculator |
| Threshold | T pace from calculator |
| Marathon Pace | MP from calculator |
| Interval (if used) | I pace from calculator |

---

## Long Run Progression by Tier

### Marathon - Mid Mileage (40-55 mi/wk peak)
```
Week 1:  14 mi
Week 2:  15 mi
Week 3:  16 mi
Week 4:  12 mi (cut-back)
Week 5:  16 mi
Week 6:  17 mi
Week 7:  18 mi
Week 8:  14 mi (cut-back)
Week 9:  18 mi
Week 10: 18 mi (+MP)
Week 11: 20 mi
Week 12: 14 mi (cut-back)
Week 13: 20 mi (+MP)
Week 14: 22 mi (peak)
Week 15: 20 mi (+MP dress rehearsal)
Week 16: 16 mi
Week 17: 12 mi
Week 18: RACE
```

### Marathon - Low Mileage (<40 mi/wk peak)
- Start: 10-12 mi
- Peak: 18-20 mi
- MP segments: 3-4 mi max

### Marathon - High Mileage (65-85 mi/wk peak)
- Start: 16-18 mi
- Peak: 22-24 mi
- MP segments: 8-10 mi

---

## Gym/Strength Placement

**Standard:** Monday + Thursday
**Spacing:** At least 2 days between gym sessions
**Peak adjustment:** Second session (Thursday) becomes optional when cumulative fatigue is high
**Taper:** Light strength only, no new stress

---

## Training Pace Calculator Integration

### For $5 Fixed Plans

**User Flow:**
1. User purchases plan
2. Directed to Training Pace Calculator
3. Enters recent race distance and time
4. System calculates all training paces
5. Plan is populated with specific paces

**Paces Calculated:**
- Easy pace range
- Marathon pace
- Threshold (T) pace
- Interval (I) pace (if plan includes)
- Repetition (R) pace (if plan includes)

**Display Format:**
Instead of: "10 mi w/ 30 min T"
Show: "10 mi w/ 30 min @ 6:45/mi"

---

## File Structure for Plans

```
plans/
├── archetypes/
│   ├── marathon_low.json
│   ├── marathon_mid.json
│   ├── marathon_high.json
│   ├── marathon_monster.json
│   ├── half_low.json
│   ├── half_mid.json
│   ├── half_high.json
│   ├── 10k_low.json
│   ├── 10k_mid.json
│   ├── 10k_high.json
│   ├── 5k_low.json
│   ├── 5k_mid.json
│   └── 5k_high.json
├── workouts/
│   ├── easy.json
│   ├── long_run.json
│   ├── threshold.json
│   ├── marathon_pace.json
│   ├── strides.json
│   ├── hills.json
│   └── recovery.json
├── generated/
│   └── (preview files for review)
└── templates/
    ├── 4_day.json
    ├── 5_day.json
    ├── 6_day.json
    └── 7_day.json
```

---

## Plan Generation Process

### Step 1: Select Parameters
- Distance (5K, 10K, Half, Full)
- Mileage tier (Low, Mid, High, Monster)
- Days per week (4, 5, 6, 7)
- Duration (8, 12, 16, 18 weeks)

### Step 2: Load Archetype
- Get phase boundaries
- Get volume progression
- Get long run progression
- Get cut-back week placement

### Step 3: Apply Weekly Template
- Based on days/week
- Slot workouts into days
- Apply phase-specific content

### Step 4: Generate Workouts
- Use T-block progression for threshold weeks
- Apply intensity rules
- Insert strides/hills appropriately

### Step 5: Output
- **Free:** HTML/PDF with effort descriptions
- **$5:** Same but with pace integration hooks

---

## Quality Checklist for Each Plan

Before publishing any plan, verify:

- [ ] Volume starts appropriately for tier
- [ ] Volume builds 5-10%/week (not more)
- [ ] Cut-back every 4th week
- [ ] Peak mileage holds for 2-3 weeks
- [ ] Taper length appropriate for distance
- [ ] Long runs start at appropriate distance for tier
- [ ] Long runs peak at appropriate distance
- [ ] T-work progresses properly (intervals → continuous)
- [ ] MP work appears in Build 2, not earlier
- [ ] Intensity rule followed (no T + MP long run same week)
- [ ] Gym on Monday + Thursday with proper spacing
- [ ] Second gym becomes optional in peak
- [ ] Effort descriptions are clear (free) or paces populated ($5)
- [ ] Weekly mileage totals displayed
- [ ] Phase labels visible

---

## Next Steps

1. **Build complete Marathon/Mid/5d/18w archetype** (in progress)
2. **Create plan generator script** that reads archetypes and outputs plans
3. **Build remaining archetypes** for other distances/tiers
4. **Integrate with Training Pace Calculator** for $5 plans
5. **Create delivery system** (how user receives plan after purchase)

---

*This document governs all fixed plan generation. Update as learnings accumulate.*
