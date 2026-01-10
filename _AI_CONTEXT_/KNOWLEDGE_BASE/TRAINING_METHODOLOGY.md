# StrideIQ Training Methodology

**Version:** 1.0  
**Date:** January 10, 2026  
**Purpose:** Convertible knowledge for plan generation, coaching, and GPT interaction  
**Status:** DEFAULTS - Always overridden by athlete data when available

---

## How This Document Works

This is NOT a rulebook. It is a **knowledge base of defaults** combined with **coaching expertise**.

```
HIERARCHY OF TRUTH:
1. Athlete's actual data (objective truth - highest priority)
2. Our analysis of that data (coaching expertise applied)
3. Athlete's stated preferences (trust but verify)
4. Athlete's demographic patterns (age, experience)
5. These defaults (lowest priority)
```

### The Coaching Relationship

We are the coach. The athlete came to us because they need guidance.

- **Trust but verify:** An athlete may THINK something works, but their data may tell a different story
- **Data over perception:** When what they believe conflicts with what the data shows, we show them the data
- **We guide, not just execute:** If they knew already, they wouldn't be asking us
- **Explain the why:** We don't just override — we coach them through the discrepancy

```
WHEN PERCEPTION ≠ DATA:
1. Acknowledge what they believe
2. Show them what the data shows
3. Explain the discrepancy
4. Recommend based on evidence
5. They make the final call, but we've coached them
```

Every value below has an implicit prefix: **"Unless athlete data shows otherwise..."**

---

## Section 1: Core Principles

These principles guide decision-making when athlete data is ambiguous or unavailable.

### 1.1 The Governing Question

Before any prescription, ask:
> "What does THIS athlete's data show?"

If data exists: Use it.  
If data is incomplete: Use defaults + flag for observation.  
If data contradicts defaults: Data wins.

### 1.2 Principle Hierarchy

| Priority | Principle | Application |
|----------|-----------|-------------|
| 1 | Keep them running | Never prescribe what causes injury/burnout |
| 2 | Consistency over intensity | Sustainable beats heroic |
| 3 | Purpose over volume | Every workout needs a reason |
| 4 | Recovery enables adaptation | Rest is not optional |
| 5 | Individual over population | Their data > research averages |

---

## Section 2: Default Parameters

### 2.1 Intensity Distribution

```yaml
default:
  easy_percentage: 80
  moderate_to_hard_percentage: 20
  
override_triggers:
  - athlete_responds_better_to_higher_intensity: adjust_ratio
  - athlete_injury_prone: increase_easy_percentage
  - athlete_in_base_phase: may_increase_easy_to_85
```

### 2.2 Weekly Structure Templates

```yaml
# Template A: Quality During Week
intensity_week:
  sunday: long_run_easy
  monday: rest_or_cross_train
  tuesday: easy_or_medium_long
  wednesday: easy
  thursday: quality_session  # T-work, hills, etc.
  friday: easy
  saturday: easy
  
# Template B: Quality In Long Run
workout_long_week:
  sunday: long_run_with_workout  # MP blocks, fast finish
  monday: rest_or_cross_train
  tuesday: easy_recovery
  wednesday: easy
  thursday: easy_with_strides
  friday: easy
  saturday: easy

selection_logic:
  if weekly_quality_sessions >= 2: use intensity_week with easy_long
  if weekly_quality_sessions == 1: can use workout_long_week
  never: 3+ quality sessions in single week
```

### 2.3 Phase Definitions

```yaml
phases:
  base:
    duration_weeks: 3-4
    focus: "aerobic foundation, volume building"
    quality_sessions_per_week: 0
    allowed_intensity: [strides, hill_sprints_short]
    long_run_type: easy_only
    
  build_1:
    duration_weeks: 3
    focus: "threshold introduction"
    quality_sessions_per_week: 1
    allowed_intensity: [threshold, strides, hills]
    long_run_type: easy_or_progressive
    
  build_2:
    duration_weeks: 3
    focus: "race-specific integration"
    quality_sessions_per_week: 1
    allowed_intensity: [threshold, marathon_pace, strides]
    long_run_type: may_include_mp_blocks
    
  peak:
    duration_weeks: 3
    focus: "hold volume, sharpen"
    quality_sessions_per_week: 1
    allowed_intensity: [threshold, marathon_pace]
    long_run_type: race_simulation
    volume: hold_at_peak
    
  taper:
    duration_weeks: 1.5-2
    focus: "reduce fatigue, maintain fitness"
    quality_sessions_per_week: 1
    allowed_intensity: [short_threshold, strides]
    volume_reduction: 40-60%

override_triggers:
  - athlete_needs_longer_base: extend_base_phase
  - athlete_recovers_slowly: add_cutback_weeks
  - athlete_responds_to_shorter_taper: reduce_taper
```

### 2.4 Cut-back Rhythm

```yaml
default:
  frequency: every_4th_week
  volume_reduction: 25%
  intensity_reduction: maintenance_or_zero
  
alternatives:
  every_3rd_week:
    when: [older_athlete, high_life_stress, injury_prone, slower_recovery]
  every_5th_week:
    when: [young_athlete, low_life_stress, fast_recovery, low_volume]

override_triggers:
  - athlete_shows_fatigue_accumulation: insert_cutback
  - athlete_performance_declining: insert_cutback
  - athlete_feeling_strong_at_week_4: may_delay_cutback
```

---

## Section 3: Workout Definitions

### 3.1 Workout Types

```yaml
easy:
  feel: "conversational, can speak in complete sentences"
  hr_ceiling: 75% max
  purpose: "aerobic base, recovery"
  default_percentage_of_training: 70-80%
  
  # NOT derived from race pace - this is critical
  pace_derivation: perceived_effort_only
  
threshold:
  feel: "comfortably hard, short phrases only"
  hr_range: 83-90% max
  purpose: "raise lactate threshold"
  duration_range: 20-40min continuous OR intervals
  volume_limit: 10% of weekly mileage
  
  pace_derivation: training_pace_calculator
  pace_description: "~10-15 sec/mi slower than 10K race pace"
  
marathon_pace:
  feel: "sustainable but focused"
  hr_range: 81-88% max
  purpose: "race-specific fitness, fueling practice"
  placement: inside_long_runs_preferred
  never: standalone_2_days_before_long_run
  
  pace_derivation: training_pace_calculator OR goal_time
  
long_run:
  purpose: "endurance, fat oxidation, mental toughness"
  default_day: sunday
  pace: 10-20% slower than MP when easy
  progression:
    start: 14 miles (marathon)
    peak: 22-24 miles
    hold_peak_for: 3 weeks before taper
    
intervals:
  purpose: "raise VO2max ceiling"
  structure: 3-5min repeats at 5K pace
  volume_limit: 8% of weekly mileage
  
  # CRITICAL TIMING RULE
  safe_phases: [base, pre_build]
  risky_phases: [mid_build, peak]
  reason: "cumulative fatigue increases injury risk"
  
  override_triggers:
    - athlete_handles_intervals_well_in_build: may_include
    - athlete_history_of_interval_injury: avoid_entirely
    
strides:
  structure: "4-8 x 15-30s, fast but relaxed"
  recovery: full (walk back)
  purpose: "neuromuscular activation, economy"
  injury_risk: very_low
  when: end_of_easy_runs, 2-3x_per_week
  
hill_sprints:
  structure: "6-12 x 8-12s max effort uphill"
  grade: 6-10%
  recovery: full (2-3min walk down)
  purpose: "power, economy, force production"
  injury_risk: low
  when: end_of_easy_runs_in_base_phase
```

### 3.2 T-Block Progression (Default)

```yaml
t_block_example:
  week_1: "6 x 5min @ T, 2min jog"
  week_2: "5 x 6min @ T, 2min jog"
  week_3: "4 x 8min @ T, 2min jog"
  week_4: "3 x 10min @ T, 3min jog"
  week_5: "2 x 15min @ T, 3min jog"
  week_6: "30-40min continuous @ T"
  
volume_scaling:
  low_mileage_runner: start_at "4 x 3min"
  high_mileage_runner: can_handle "2 x 20min or 40min continuous"
  
override_triggers:
  - athlete_struggles_with_progression: slow_down
  - athlete_crushing_workouts: may_accelerate
```

---

## Section 4: Athlete Factors

### 4.1 Volume-Based Defaults

```yaml
volume_tiers:
  low:
    weekly_miles: "<30 (5K/10K) or <40 (HM/M)"
    days_per_week: 5-6
    quality_sessions: 0-1
    focus: "frequency, consistency, base building"
    long_run_cap: 12-14 miles
    
  mid:
    weekly_miles: "30-50 (5K/10K) or 40-65 (HM/M)"
    days_per_week: 6
    quality_sessions: 1
    focus: "durability, threshold development"
    long_run_cap: 18-20 miles
    
  high:
    weekly_miles: "50+ (5K/10K) or 65+ (HM/M)"
    days_per_week: 6-7
    quality_sessions: 1-2
    focus: "full periodization, race-specific"
    long_run_cap: 22-24 miles
    
  mileage_monster:
    weekly_miles: "85+"
    days_per_week: 7 (often doubles)
    quality_sessions: 2
    focus: "advanced periodization"
    long_run_cap: 24+ miles

override_triggers:
  - athlete_thrives_at_higher_volume: move_up_tier
  - athlete_breaks_down_at_tier_volume: move_down_tier
```

### 4.2 Age-Based Defaults

```yaml
age_factors:
  default_assumptions:
    recovery_time: increases_with_age
    injury_risk: increases_with_cumulative_fatigue
    speed_work_timing: earlier_in_cycle_for_older
    
  adjustments:
    masters_40_plus:
      prefer: [strides, hills, threshold]
      caution: [intervals_mid_build]
      recovery: may_need_extra_day
      
    masters_50_plus:
      prefer: [strides, hills, threshold]
      avoid: [intervals_under_cumulative_fatigue]
      recovery: often_needs_extra_day
      cutback_frequency: consider_every_3rd_week

# CRITICAL OVERRIDE
age_override:
  description: "Age is a variable, not a limiter"
  rule: "Individual data ALWAYS overrides age assumptions"
  example: "57-year-old PRing beats predictions - use their data"
```

### 4.3 Experience-Based Defaults

```yaml
experience_levels:
  beginner:
    running_years: "<2"
    priority: "consistency, injury prevention, habit building"
    intensity: minimal
    progression: conservative
    
  intermediate:
    running_years: "2-5"
    priority: "base building, introducing structure"
    intensity: threshold_focus
    progression: moderate
    
  advanced:
    running_years: "5+"
    priority: "optimization, race-specific"
    intensity: full_periodization
    progression: athlete_dependent

override_triggers:
  - athlete_progresses_faster_than_expected: move_up_level
  - athlete_has_athletic_background: may_start_higher
  - athlete_returning_after_break: assess_current_fitness
```

---

## Section 5: Decision Logic

### 5.1 Plan Generation Flow

```
INPUT: athlete_profile, goal_race, timeline

1. CHECK athlete data availability:
   - Full data (Strava/Garmin): Use actual patterns
   - Partial data (questionnaire): Use stated + defaults
   - No data: Use pure defaults + flag all assumptions

2. DETERMINE tier from current_volume or stated_volume

3. SELECT phase structure based on weeks_to_race

4. FOR each week:
   a. Determine phase
   b. Apply phase template
   c. Adjust for athlete factors
   d. Check against athlete history (if available)
   e. Flag any assumptions made

5. OUTPUT plan with:
   - Effort descriptions (if no pace data)
   - Training Pace Calculator link (for pace personalization)
   - Flagged assumptions for athlete review
```

### 5.2 Coaching Decision Flow

```
INPUT: athlete_question, athlete_profile, current_plan

1. RETRIEVE relevant methodology section

2. ANALYZE athlete data:
   - What does their actual performance data show?
   - What patterns exist in their history?
   - What has objectively worked/not worked?
   
3. COMPARE to athlete stated belief:
   - Do they think X works but data shows otherwise?
   - Trust but verify — perception is not evidence
   
4. IF data supports their belief:
   - Confirm and reinforce with evidence
   - "Your data backs this up..."
   
5. IF data contradicts their belief:
   - Acknowledge their perception
   - Show them the data
   - Coach through the discrepancy
   - Make a clear recommendation
   - "I hear you, but here's what I'm seeing..."
   
6. IF no data exists:
   - Use defaults
   - Explain as starting point
   - Flag for observation

7. WE ARE THE COACH:
   - Make clear recommendations
   - Don't be wishy-washy
   - They came to us for guidance
```

### 5.3 GPT Interaction Filter

```
WHEN responding to athlete:

WE ARE THE COACH:
- The athlete came to us for guidance, not validation
- We have expertise and can see patterns they can't
- We trust their experience but verify with data
- When perception conflicts with data, we show them the data

DO:
- Reference their specific data when available
- Explain the "why" behind recommendations
- When their belief conflicts with data: "I hear you, but your data shows..."
- Coach through discrepancies, don't just agree
- Make clear recommendations based on evidence

DO NOT:
- Present defaults as absolute rules
- Blindly accept athlete perception when data contradicts
- Be a yes-man — we're coaches, not order-takers
- Use zone numbers (use effort descriptions)
- Cite source names (use principles only)

LANGUAGE PATTERNS:
- "Your data shows..." > "The rule is..."
- "I notice that..." > "You should..."
- "What I see in your history is..." > "What do you think?"
- "Based on your runs, I'd recommend..." > "Whatever you prefer"

WHEN ATHLETE BELIEF ≠ DATA:
- "I understand you feel X works for you..."
- "But looking at your data, I'm seeing Y..."
- "For example, [specific evidence]..."
- "What I'd recommend is Z, because..."
- "What are your thoughts?"
```

---

## Section 6: Learning Loop

### 6.1 Capturing Athlete Feedback

```yaml
feedback_triggers:
  - workout_felt_wrong: flag for review
  - athlete_modified_plan: learn from modification
  - unexpected_performance: analyze cause
  - injury_occurred: analyze preceding load
  
storage:
  - athlete_profile.response_patterns
  - athlete_profile.effective_workouts
  - athlete_profile.injury_triggers
  - athlete_profile.preference_overrides
```

### 6.2 Updating Athlete Model

```
AFTER each training block:

1. Compare predicted vs actual performance
2. Identify patterns:
   - What workouts produced breakthroughs?
   - What preceded injuries or fatigue?
   - Where did athlete deviate from plan?
   
3. Update athlete profile:
   - response_to_threshold: [better/worse/neutral]
   - response_to_volume: [better/worse/neutral]
   - recovery_speed: [fast/average/slow]
   - injury_triggers: [list]
   
4. Next plan uses updated profile, NOT fresh defaults
```

---

## Section 7: Pace Handling

### 7.1 When Paces Are Known

```yaml
source: training_pace_calculator OR recent_race_time
application:
  threshold: use_calculated_T_pace
  marathon_pace: use_calculated_MP
  easy: use_effort_description (calculators often too fast)
  intervals: use_calculated_I_pace
```

### 7.2 When Paces Are Unknown

```yaml
approach: effort_descriptions_only
examples:
  easy: "Conversational. Can speak in full sentences."
  threshold: "Comfortably hard. Short phrases only."
  marathon_pace: "Sustainable focus. Could hold for 26.2."
  intervals: "Hard. 5K race effort."
  
call_to_action: "Use Training Pace Calculator for specific paces"
never: prescribe specific paces without data
```

---

## Section 8: The Meta-Rule

```
This entire document is a STARTING POINT.

The moment we have athlete data, it supersedes these defaults.
The moment outcomes contradict predictions, we update our model.

But we are the COACH:
- When athlete perception conflicts with data, we show them the data
- We trust but verify — belief is not evidence
- If they knew already, they wouldn't be asking us
- We guide based on what we see, not just what they think

We do not adapt athletes to plans.
We learn from athlete DATA and adapt plans to achieve better outcomes.
We are not order-takers. We are coaches.
```

---

*Convertible knowledge for StrideIQ systems*  
*All values are defaults unless overridden by athlete data*  
*Performance Focused Coaching*
