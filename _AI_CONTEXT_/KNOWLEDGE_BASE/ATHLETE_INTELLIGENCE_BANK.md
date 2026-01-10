# Athlete Intelligence Bank

**Version:** 1.0  
**Date:** January 10, 2026  
**Status:** CORE ARCHITECTURE - Every athlete has this profile  
**Purpose:** Continuous learning, banked insights, compounding intelligence

---

## Overview

Every athlete has a growing intelligence profile. This is not a static record — it evolves with every workout, every build, every race. The longer an athlete is with StrideIQ, the smarter their coaching becomes.

```
Year 1: Learning phase — observation, pattern detection, defaults with flags
Year 2: Pattern recognition — "this athlete responds to X"
Year 3+: Precision coaching — system knows them better than they know themselves
```

---

## Schema

```yaml
athlete_intelligence:
  athlete_id: uuid
  created_at: timestamp
  last_updated: timestamp
  
  # ═══════════════════════════════════════════════════════════════════
  # SECTION 1: REAL-TIME SIGNALS (Updated continuously)
  # ═══════════════════════════════════════════════════════════════════
  
  current_state:
    efficiency_trend: improving | stable | declining
    fatigue_level: low | moderate | high | critical
    readiness_score: 0-100
    days_since_quality_session: int
    current_phase: base | build | peak | taper | off_season | recovery
    injury_risk: low | elevated | high
    
  recent_patterns:
    last_7_days:
      total_miles: float
      quality_sessions: int
      avg_easy_hr: int
      sleep_avg_hours: float
    last_28_days:
      total_miles: float
      trend_vs_prior_28: up | down | stable
      efficiency_delta: float
      
  # ═══════════════════════════════════════════════════════════════════
  # SECTION 2: BANKED INSIGHTS (Permanent, grows over time)
  # ═══════════════════════════════════════════════════════════════════
  
  what_works:
    workouts:
      - insight: "T-blocks produce breakthroughs"
        confidence: high
        evidence_count: 3
        last_confirmed: date
      - insight: "Long runs with MP finish > pure easy long runs"
        confidence: high
        evidence_count: 5
        last_confirmed: date
      - insight: "Responds well to high frequency (6-7 days/wk)"
        confidence: medium
        evidence_count: 2
        last_confirmed: date
        
    recovery:
      - insight: "Needs cutback every 3rd week (not 4th)"
        confidence: high
        evidence_count: 4
        last_confirmed: date
      - insight: "Sleep under 6hrs impacts performance 48hrs later"
        confidence: medium
        evidence_count: 3
        last_confirmed: date
        
    nutrition:
      - insight: "Caffeine 45min pre-race improves performance"
        confidence: medium
        evidence_count: 2
        last_confirmed: date
        
  what_doesnt_work:
    - insight: "Intervals when cumulative fatigue is high"
      severity: injury_risk
      evidence_count: 2
      last_occurrence: date
    - insight: "Long runs over 22mi (diminishing returns, high cost)"
      severity: diminishing_returns
      evidence_count: 3
      last_occurrence: date
    - insight: "Aggressive easy paces (runs them too hard)"
      severity: recovery_impact
      evidence_count: ongoing
      
  injury_triggers:
    - pattern: "Intervals introduced mid-build at 65+ mpw"
      occurrences: 2
      severity: bone_stress
      prevention: "Speed work in base only; T-work in build"
    - pattern: "Volume spike >15% week-over-week"
      occurrences: 1
      severity: soft_tissue
      prevention: "Cap weekly increase at 10%"
      
  # ═══════════════════════════════════════════════════════════════════
  # SECTION 3: KEY PERFORMANCE INDICATORS (Tracked over time)
  # ═══════════════════════════════════════════════════════════════════
  
  kpi_history:
    threshold_pace:
      - date: 2025-06-15
        value: "4:15/km"
        context: "post-base block"
      - date: 2025-09-20
        value: "4:08/km"
        context: "mid-build"
      - date: 2025-11-15
        value: "4:03/km"
        context: "peak fitness"
      current: "4:03/km"
      trend: improving
      
    efficiency_factor:
      - date: 2025-06-15
        value: 1.42
      - date: 2025-11-15
        value: 1.58
      current: 1.58
      trend: improving
      
    easy_pace_hr:
      - date: 2025-06-15
        pace: "5:30/km"
        hr: 138
      - date: 2025-11-15
        pace: "5:30/km"
        hr: 128
      trend: improving  # Same pace, lower HR
      
    long_run_durability:
      max_without_fade: 18  # miles
      fade_trigger: underfueling
      mp_capability: "Can hold MP for 16mi in training"
      
  # ═══════════════════════════════════════════════════════════════════
  # SECTION 4: BUILD HISTORY (Every completed training cycle)
  # ═══════════════════════════════════════════════════════════════════
  
  build_history:
    - build_id: fall_2025_half_marathon
      start_date: 2025-10-04
      end_date: 2025-11-29
      duration_weeks: 8
      
      training_summary:
        avg_weekly_volume: 99km
        peak_weekly_volume: 108km
        runs_per_week_avg: 8.1
        long_runs_total: 19
        tempo_sessions: 4
        interval_sessions: 0
        
      race_outcome:
        distance: half_marathon
        goal_time: "1:34:00"
        actual_time: "1:27:40"
        result: PR
        improvement: "7 minutes"
        pacing: slightly_positive_but_controlled
        
      analysis:
        what_worked:
          - "High volume (99 km/wk avg) built aerobic base"
          - "Long runs with MP blocks (4 total) made race pace familiar"
          - "No intervals mid-build prevented injury"
        what_didnt:
          - "Tempo sessions were sporadic (only 4)"
          - "Speed work missing entirely"
          - "Threshold could have been higher"
          
      athlete_feedback:
        felt_strong: "miles 1-10"
        struggled: "miles 11-13 (legs heavy)"
        mental: confident
        fueling: good
        
      weaknesses_identified:
        - "Late-race leg fatigue"
        - "Undertrained threshold"
        - "No speed maintenance"
        
      learnings_banked:
        - "High volume works for this athlete"
        - "MP long runs produce race-day confidence"
        - "Need more structured T-block next time"
        
    - build_id: summer_2025_5k
      # ... previous build
      
  # ═══════════════════════════════════════════════════════════════════
  # SECTION 5: ATHLETE PROFILE (Demographics & Preferences)
  # ═══════════════════════════════════════════════════════════════════
  
  profile:
    age: 57
    years_running: 2  # Current stint
    lifetime_running: true  # Ran before, returned
    work_status: full_time
    life_stress: moderate
    
    training_preferences:
      preferred_long_run_day: sunday
      preferred_quality_day: thursday
      available_days: 6
      max_weekly_hours: 10
      gym_days: [monday, thursday]
      
    response_patterns:
      volume_responder: high  # Responds well to volume
      intensity_responder: moderate
      speed_responder: high_in_base_only
      recovery_speed: moderate
      
    constraints:
      injury_history: [bone_stress_2025]
      avoid: [intervals_mid_build]
      require: [cutback_every_3_weeks]
      
  # ═══════════════════════════════════════════════════════════════════
  # SECTION 6: NEXT PHASE PRESCRIPTION
  # ═══════════════════════════════════════════════════════════════════
  
  next_phase:
    recommended_type: pre_training
    recommended_duration_weeks: 8
    target_weaknesses:
      - "Leg speed maintenance (add strides 3x/week)"
      - "Threshold development (structured T-block)"
      - "Hill strength (heavy legs late = strength deficit)"
    prepares_for: spring_marathon_build
    start_date: 2026-01-15
    
    prescribed_focus:
      - "Strides after every easy run (6x20s)"
      - "Hill sprints 2x/week (8x10s)"
      - "Introduce T-work week 4"
      - "Build volume from 50 to 70 km/wk"
```

---

## How This Is Used

### 1. Plan Generation

```python
def generate_plan(athlete_id, goal_race, timeline):
    # Load athlete intelligence
    intel = load_athlete_intelligence(athlete_id)
    
    # Apply banked insights
    if "needs cutback every 3rd week" in intel.what_works:
        plan.cutback_frequency = 3
        
    if "intervals mid-build → injury" in intel.injury_triggers:
        plan.exclude_intervals_after_week(6)
        
    if intel.kpi_history.threshold_pace.current:
        plan.set_training_paces(intel.kpi_history)
        
    # Address weaknesses from last build
    for weakness in intel.build_history[-1].weaknesses_identified:
        plan.add_focus(weakness)
```

### 2. Coaching Decisions

```python
def coaching_response(athlete_id, question):
    intel = load_athlete_intelligence(athlete_id)
    
    # Check if athlete belief contradicts banked data
    if athlete_says("intervals work for me"):
        if "intervals mid-build → injury" in intel.injury_triggers:
            return coach_through_discrepancy(
                belief="You feel intervals work",
                data="Your data shows 2 injuries from mid-build intervals",
                recommendation="Speed work in base phase instead"
            )
```

### 3. Post-Race Analysis

```python
def analyze_build(athlete_id, race_result):
    intel = load_athlete_intelligence(athlete_id)
    training = get_training_data(intel.current_build)
    
    # Compare predicted vs actual
    analysis = compare_outcome(training, race_result)
    
    # Identify what worked
    analysis.what_worked = identify_positive_correlations(training, race_result)
    
    # Identify weaknesses
    analysis.weaknesses = identify_weaknesses(race_result, athlete_feedback)
    
    # Bank learnings
    intel.build_history.append(analysis)
    intel.what_works.extend(analysis.what_worked)
    intel.weaknesses_identified = analysis.weaknesses
    
    # Prescribe next phase
    intel.next_phase = prescribe_next_phase(analysis.weaknesses, athlete_schedule)
    
    save_athlete_intelligence(intel)
```

### 4. GPT Context Injection

```python
def build_gpt_context(athlete_id):
    intel = load_athlete_intelligence(athlete_id)
    
    return f"""
    ATHLETE INTELLIGENCE SUMMARY:
    
    Current State: {intel.current_state}
    
    What Works For This Athlete:
    {format_insights(intel.what_works)}
    
    What Doesn't Work (Avoid):
    {format_insights(intel.what_doesnt_work)}
    
    Injury Triggers:
    {format_triggers(intel.injury_triggers)}
    
    Last Build Outcome:
    {intel.build_history[-1].summary()}
    
    Weaknesses Being Addressed:
    {intel.next_phase.target_weaknesses}
    
    Use this context when responding. Reference specific data.
    Trust but verify athlete perceptions against this data.
    """
```

---

## Banking Events

The intelligence bank is updated on these events:

| Event | What Gets Banked |
|-------|------------------|
| **Every Workout** | EF trends, anomalies, patterns |
| **Weekly** | Volume trends, recovery patterns |
| **Quality Session** | Response to intensity, adaptation signals |
| **Cut-back Week** | Recovery response, rebound quality |
| **Race** | Full build analysis, outcome comparison |
| **Injury** | What preceded it, trigger pattern |
| **Athlete Feedback** | Subjective experience, preferences |

---

## The Compounding Effect

```
Month 1:   System knows: demographics, stated preferences
Month 3:   System knows: + response to volume, recovery speed
Month 6:   System knows: + what workouts produce gains, injury risks
Year 1:    System knows: + full build cycle, race outcome patterns
Year 2:    System knows: + seasonal patterns, multi-build progression
Year 3+:   System knows them better than they know themselves
```

---

## The Promise

> "The longer you're with StrideIQ, the better we know you. Every workout teaches us something. Every build makes the next one smarter. By year two, we'll know what works for YOU — not what works for the average runner. That's coaching."

---

*Core architecture for StrideIQ athlete intelligence*  
*This is the moat. This is the differentiator.*  
*Performance Focused Coaching*
