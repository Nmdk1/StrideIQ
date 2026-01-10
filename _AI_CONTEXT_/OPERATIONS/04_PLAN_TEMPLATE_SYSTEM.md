# Plan Template System

**Purpose:** Enable plan generation WITHOUT AI assistance. A human following these rules, or simple code implementing them, should produce quality training plans.

**Last Updated:** January 10, 2026

---

## Core Philosophy

1. **Easy must be EASY** - 80% of volume at conversational pace
2. **One quality session per week** is enough for most athletes
3. **Long run is The Engine** - builds race-specific endurance
4. **Threshold before intervals** - safer, nearly as effective
5. **Consistency > heroic workouts** - frequency builds durability
6. **Recovery is training** - adaptation happens during rest

---

## Plan Parameters

Every plan requires these inputs:

| Parameter | Description | Example |
|-----------|-------------|---------|
| `distance` | Race distance | marathon, half, 10k, 5k |
| `weeks_available` | Time until race | 8, 12, 14, 16, 18, 20 |
| `current_weekly_miles` | Athlete's current volume | 25, 35, 45, 55 |
| `days_per_week` | Available running days | 4, 5, 6, 7 |
| `goal_time` | Target finish (optional) | 3:30:00 |
| `recent_race` | For pace calculation | 5K in 22:00 |

---

## Phase Allocation Rules

### Phase Definitions

| Phase | Purpose | Key Workouts |
|-------|---------|--------------|
| **Base** | Aerobic foundation, durability | Easy runs, strides, hill sprints (8-10s) |
| **Build** | Introduce quality, threshold focus | T-work progression, easy long runs |
| **Peak** | Race-specific, MP work | MP in long runs, maintain T |
| **Taper** | Reduce fatigue, maintain sharpness | Short T, strides, reduced volume |

### Phase Distribution by Duration

| Total Weeks | Base | Build | Peak | Taper |
|-------------|------|-------|------|-------|
| 8 | 2 | 3 | 2 | 1 |
| 10 | 2 | 4 | 2 | 2 |
| 12 | 3 | 5 | 2 | 2 |
| 14 | 3 | 6 | 3 | 2 |
| 16 | 4 | 7 | 3 | 2 |
| 18 | 3 | 8 | 5 | 2 |
| 20 | 4 | 9 | 5 | 2 |

**Rule:** Taper is always 2 weeks (10-14 days) regardless of plan length.

### Cutback Week Placement

**Rule:** Every 4th week is a cutback week (reduce volume 20-25%).

For athletes who need more recovery (older, injury-prone, high stress):
- Option: Every 3rd week cutback

**Cutback weeks count toward their phase.** A cutback in Build phase is still Build, just lighter.

---

## Volume Progression Rules

### Starting Volume

**Rule:** Plan starting volume = athlete's current weekly miles × 0.9

Never start a plan higher than what they're currently running.

### Peak Volume by Distance

| Distance | Peak Volume Range |
|----------|-------------------|
| 5K | Current + 10-20% |
| 10K | Current + 15-25% |
| Half Marathon | Current + 20-30% |
| Marathon | Current + 30-50% |

**Maximum peaks by experience:**

| Current Volume | Marathon Peak Max |
|----------------|-------------------|
| 25-30 mpw | 40-45 mpw |
| 35-40 mpw | 50-55 mpw |
| 45-50 mpw | 60-70 mpw |
| 55-60 mpw | 70-85 mpw |
| 65+ mpw | 85-100+ mpw |

### Weekly Progression Rate

**Rule:** Increase volume by 5-10% per week during Build phase.

**Rule:** Never increase volume AND intensity in the same week.

### Volume by Phase

| Phase | Volume (% of Peak) |
|-------|-------------------|
| Base Week 1 | 70-75% |
| Base End | 80-85% |
| Build Start | 85% |
| Build End | 95-100% |
| Peak | 95-100% |
| Taper Week 1 | 70-75% |
| Taper Week 2 | 50-60% |
| Race Week | 30-40% |

---

## Weekly Structure Templates

### 6 Days Per Week (Recommended for Marathon)

| Day | Role | Notes |
|-----|------|-------|
| Monday | REST / Gym | No running. Strength + mobility. |
| Tuesday | Medium-Long | 20-25% of weekly volume. MP work in Peak. |
| Wednesday | Easy | Recovery from Tuesday, prep for Thursday |
| Thursday | QUALITY | The one quality session. T-work in Build, strides in Base. |
| Friday | Easy | Recovery |
| Saturday | Easy + Strides | Pre-long run. Keep short. |
| Sunday | LONG RUN | The Engine. 30-35% of weekly volume. |

### 5 Days Per Week

| Day | Role | Notes |
|-----|------|-------|
| Monday | REST | Full rest |
| Tuesday | Easy | |
| Wednesday | QUALITY | T-work or workout |
| Thursday | Easy | |
| Friday | REST | |
| Saturday | Easy + Strides | Pre-long run |
| Sunday | LONG RUN | |

### 4 Days Per Week

| Day | Role | Notes |
|-----|------|-------|
| Monday | REST | |
| Tuesday | Easy | |
| Wednesday | REST | |
| Thursday | QUALITY | |
| Friday | REST | |
| Saturday | Easy | Pre-long |
| Sunday | LONG RUN | |

**Rule:** With 4 days, quality session can include elements (e.g., tempo finish on long run) since there's only one quality opportunity.

---

## Workout Progression Rules

### Base Phase Workouts

**Quality Day Options:**
- Easy + 6×20s strides
- Easy + 6×8-10s hill sprints
- Easy + 4×20s strides + 4×8s hills

**Long Run:** Always easy. Building time on feet.

**NO threshold work in Base phase.**

### Build Phase: T-Block Progression

The threshold block progresses from intervals toward continuous:

| Week in Build | Workout |
|---------------|---------|
| 1 | 6 × 5 min @ T, 2 min jog |
| 2 | 5 × 6 min @ T, 2 min jog |
| 3 | 4 × 8 min @ T, 2 min jog |
| 4 (cutback) | 15 min continuous @ T |
| 5 | 3 × 10 min @ T, 2 min jog |
| 6 | 2 × 15 min @ T, 3 min jog |
| 7 | 25-30 min continuous @ T |
| 8 (cutback) | 15 min continuous @ T |

**Rule:** For shorter Build phases, compress but keep progression direction (intervals → continuous).

### Peak Phase: MP Introduction

**Intensity Rule:** If there's T-work on Thursday, long run is easy. If long run has MP work, Thursday is easy + strides.

**MP Long Run Progression (Marathon):**

| Week in Peak | Long Run MP Work |
|--------------|------------------|
| 1 | 20 mi with 8 @ MP (2×4mi MP, 1mi easy between) |
| 2 | Easy long run (T-work Thursday) |
| 3 | 22 mi with 12 @ MP (3×4mi, 1mi easy between) |
| 4 | Easy long run (T-work Thursday) |
| 5 (Dress Rehearsal) | 22 mi with 16 CONTINUOUS @ MP |

**Medium-Long MP Work (Build2/Peak):**
- 10 mi with 2×2mi @ MP
- 10 mi with 2×3mi @ MP

### Taper Phase

| Week | Volume | Quality |
|------|--------|---------|
| Taper 1 | 70% | 15 min @ T (sharpening) |
| Taper 2 | 50% | 10 min @ T (sharpening) |
| Race Week | 30% | Strides only |

**Rule:** Maintain some intensity (short T, strides) to stay sharp. Only volume drops.

---

## Long Run Progression Rules

### Starting Long Run

**Rule:** Starting long run = current long run OR 25-30% of starting weekly volume.

### Building Long Runs

**Rule:** Increase long run by 1-2 miles every 1-2 weeks.

**Rule:** Cutback weeks reduce long run by 25-30%.

### Peak Long Run by Distance

| Race Distance | Peak Long Run |
|---------------|---------------|
| 5K | 10-12 miles |
| 10K | 12-15 miles |
| Half Marathon | 14-16 miles |
| Marathon | 20-22 miles |

**Rule:** Marathon long runs cap at 22 miles. 20 miles is sufficient for most.

---

## Pace Calculation

### From Race Time to Training Paces

Use the Training Pace Calculator (VDOT-based):

| Zone | Description | Feel |
|------|-------------|------|
| Easy | Conversational | Can speak full sentences |
| Long | Slightly slower than easy | Relaxed, sustainable |
| Marathon (MP) | Goal race pace | Controlled, "I could do this for hours" |
| Threshold (T) | Comfortably hard | Short sentences only, ~60 min race effort |
| Interval (I) | Hard | 10-15 min race effort |

### Pace Relationship (Approximate)

If Easy pace = E min/mile:
- Long = E + 10-15 sec/mile
- Marathon = E - 45-60 sec/mile
- Threshold = E - 75-90 sec/mile
- Interval = E - 105-120 sec/mile

**Example:** Easy = 9:00/mile
- Long = 9:10-9:15/mile
- Marathon = 8:00-8:15/mile
- Threshold = 7:30-7:45/mile
- Interval = 7:00-7:15/mile

---

## Duration Fitting Algorithm

When athlete has non-standard time until race:

### More Time Than Needed (e.g., 22 weeks for marathon)

**Option A:** Extend Base phase (extra aerobic foundation)
**Option B:** Add "Pre-Base" easy running block
**Option C:** Start plan later

### Less Time Than Needed (e.g., 10 weeks for marathon)

**Compression Rules:**
1. Taper stays at 2 weeks (non-negotiable)
2. Compress Build and Peak proportionally
3. If < 8 weeks: Consider recommending different race

**10-Week Marathon Example:**
- Base: 2 weeks
- Build: 4 weeks  
- Peak: 2 weeks
- Taper: 2 weeks

Compress T-block: 4×8min → 2×12min → 20min continuous (faster progression)

---

## Quality Checklist

Before finalizing any plan, verify:

- [ ] Taper is 2 weeks
- [ ] Cutback every 3-4 weeks
- [ ] No threshold in Base phase (strides/hills only)
- [ ] Peak volume doesn't exceed athlete's capacity
- [ ] Volume increase ≤ 10% per week
- [ ] One quality session per week (not two)
- [ ] Long run on Sunday, rest/gym on Monday
- [ ] T-work progresses intervals → continuous
- [ ] MP work only in Peak phase (not before)
- [ ] Dress rehearsal 3 weeks before race (16+ continuous MP miles)
- [ ] Easy days are truly easy (no hidden intensity)

---

## Example: Building a 14-Week Marathon Plan for 40mpw Athlete

**Inputs:**
- Distance: Marathon
- Weeks: 14
- Current: 40 mpw
- Days: 6
- Goal: 3:45 (8:35/mile)

**Phase Allocation (from table):**
- Base: 3 weeks
- Build: 6 weeks
- Peak: 3 weeks
- Taper: 2 weeks

**Volume:**
- Start: 36 mpw (40 × 0.9)
- Peak: 52 mpw (40 × 1.3)
- Progression: ~2 mpw/week during Build

**Long Run:**
- Start: 12 miles
- Peak: 20-22 miles

**Cutback Weeks:** 4, 8, 12

**T-Block (compressed for 6-week Build):**
- Week 4 (cutback): Easy week
- Week 5: 5×5 min T
- Week 6: 4×6 min T
- Week 7: 3×8 min T
- Week 8 (cutback): 12 min continuous T
- Week 9: 2×12 min T

**Peak MP Work:**
- Week 10: 18mi with 6 @ MP
- Week 11: Easy long (T on Thursday)
- Week 12 (cutback): 14mi easy
- Wait - need to recalculate...

Actually:
- Week 10: T on Thursday, 20mi easy long
- Week 11: Easy week, 20mi with 10 @ MP
- Week 12: T on Thursday, 20mi easy long

No - let me apply rules correctly:

**Corrected Peak (weeks 10-12):**
- Week 10: 20mi with 8 @ MP (no T this week)
- Week 11: T on Thursday, 20mi easy
- Week 12: Dress rehearsal - 22mi with 14 continuous @ MP (no T)

**Taper (weeks 13-14):**
- Week 13: 15 min T sharpening, 14mi easy long
- Week 14: 10 min T sharpening, 10mi easy long, race on Sunday of week 15? 

No - race is END of week 14. Let me recalculate:

If race is Sunday of Week 14:
- Week 13: Taper week 1 (70% volume, short T)
- Week 14: Race week (30% volume, strides only, race Sunday)

---

## Implementation Notes

### For Code Implementation

```python
def generate_plan(distance, weeks, current_mpw, days_per_week, goal_time=None, recent_race=None):
    # 1. Calculate phase allocation from table
    phases = get_phase_allocation(weeks)
    
    # 2. Calculate volumes
    start_volume = current_mpw * 0.9
    peak_volume = calculate_peak(current_mpw, distance)
    
    # 3. Calculate paces from recent_race
    paces = calculate_training_paces(recent_race) if recent_race else None
    
    # 4. Get weekly template for days_per_week
    template = get_weekly_template(days_per_week)
    
    # 5. Generate each week
    weeks = []
    for week_num in range(1, weeks + 1):
        phase = get_phase_for_week(week_num, phases)
        is_cutback = week_num % 4 == 0
        volume = calculate_week_volume(week_num, start_volume, peak_volume, phase, is_cutback)
        workouts = generate_week_workouts(template, phase, volume, paces, week_num)
        weeks.append(workouts)
    
    return weeks
```

### For Human Execution

1. Determine phase allocation from table
2. Calculate start (current × 0.9) and peak volumes
3. Place cutbacks every 4th week
4. Fill in Base weeks: easy + strides/hills
5. Fill in Build weeks: T-block progression
6. Fill in Peak weeks: alternating T and MP long runs
7. Fill in Taper: reduced volume, sharp T
8. Verify with checklist

---

## Appendix: Distance-Specific Modifications

### 5K Plans
- More interval work (I pace) in Build/Peak
- Strides throughout (neuromuscular activation critical)
- Long runs shorter (10-12mi max)
- T-work still important (aerobic base)

### 10K Plans
- Balance of T and I work
- Long runs 12-15mi
- 10K pace practice in Peak (tempo efforts at goal pace)

### Half Marathon Plans
- Similar to marathon but compressed
- Peak long run 14-16mi
- HMP work instead of MP work
- Less total volume needed

### Marathon Plans
- T-work dominates Build
- MP work dominates Peak
- Long runs are primary race-specific stimulus
- Volume is king (for those who can handle it)

---

*This document enables plan generation without AI. Follow the rules, use the tables, verify with checklist.*
