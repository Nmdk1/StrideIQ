# Runner Road Magic Alternation - Integration Complete

**Date:** January 5, 2026  
**Status:** ✅ Complete

## Overview

Integrated the "Runner Road (or Trail) Magic Alternation" principle into the knowledge base and plan generator. This is a custom principle derived from real-world athlete data (founder: 57 years old, full-time work, 70 mpw sustained).

## Principle Details

### Core Concept
Alternate training focus to achieve deeper adaptation, prevent staleness, and sustain high mileage with lower overreach risk.

### Key Components
1. **Monthly or weekly alternation**: Cycle between threshold-focused blocks (lactate clearance, tempo/threshold work) and interval-focused blocks (VO2max/speed, 5K/10K pace intervals).

2. **Long run restraint**: Avoid marathon-pace or faster segments in long runs during quality-heavy weeks. Reserve MP+ longs for every 3rd week (or less) to protect recovery and allow full effort in weekly quality sessions.

### Benefits (from real-world data)
- Greater sustainability at high mileage (70+ mpw with full-time work)
- Deeper adaptation per stimulus type (threshold vs. intervals)
- Reduced chronic stress and injury risk
- Consistent efficiency gains and enjoyment

## Implementation

### 1. Knowledge Base Entry ✅

**File:** `apps/api/scripts/add_runner_road_magic_principle.py`

Added principle to knowledge base with:
- **Methodology**: "Runner Road Magic"
- **Principle Type**: "periodization_principle"
- **Tags**: `alternation`, `periodization`, `long_run`, `threshold`, `intervals`, `sustainability`, `high_mileage`, `masters`, `work_life_balance`
- **Structured Data**: Alternation pattern details, application rules, benefits

**Entry ID**: `3803b550-eb32-4244-8d83-f0c2bdf914a3`

### 2. Blending Heuristics ✅

**File:** `apps/api/services/blending_heuristics.py`

Updated `determine_methodology_blend()` to apply alternation pattern with higher weight for:
- **High volume** (60+ mpw): +0.3 weight
- **Masters athletes** (50+): +0.2 weight
- **Work constraints**: +0.15 weight
- **Conservative/balanced risk tolerance**: +0.1 weight
- **Historical data support**: +0.25 weight (if alternation shows superior efficiency gains)

Alternation weight is applied proportionally, reducing other methodologies to maintain 100% total blend.

### 3. Plan Generator ✅

**File:** `apps/api/services/principle_plan_generator.py`

Updated plan generation to apply alternation pattern:

#### Alternation Cycle (3-week rotation)
- **Week 1 (threshold focus)**: Threshold/tempo workouts, easy long run
- **Week 2 (interval focus)**: VO2max/speed intervals, easy long run
- **Week 3 (MP long)**: Reduced quality session intensity, marathon-pace long run with segments

#### Implementation Details
- `generate_principle_based_plan()`: Checks if alternation should be applied (weight > 0.15)
- `synthesize_workout_from_principles()`: Updated to accept `alternation_focus` parameter
- Quality sessions: Alternates between threshold and interval focus based on week
- Long runs: MP+ segments only every 3rd week, easy pace otherwise
- Week metadata: Includes `alternation_focus` field when applied

### 4. Explanation Layer ✅

**File:** `apps/api/services/ai_coaching_engine.py`

Updated `translate_recommendation_for_client()` to add alternation explanation for Tier 3/4 subscription clients:

```
"Alternating focus pattern: [rationale]. Your plan alternates between threshold-focused weeks (lactate clearance) and interval-focused weeks (VO2max/speed), with marathon-pace long runs every 3rd week. This pattern supports deeper adaptation and sustainability at high mileage."
```

## Application Rules

### Tier 2 Fixed Plans
- Apply as default "sustainable rotation" template when:
  - User volume is high (60+ mpw)
  - Risk tolerance is conservative/balanced
- Example cycle: Week 1 threshold, Week 2 interval, Week 3 MP long
- Scale frequency based on user input (runs/week, mileage history)

### Tier 3/4 Subscription Coaching
- Analyze Strava history for response to threshold vs. interval weeks
- If alternation shows superior efficiency gains, bias plan toward this pattern
- Provide explanation: "Your data shows alternating threshold and interval focus drives stronger efficiency gains — we've structured this cycle accordingly, with MP long runs every 3 weeks."

## Testing

To test alternation pattern application:

```python
athlete_profile = {
    "current_base_mileage": 70,  # High volume
    "age": 57,  # Masters athlete
    "work_constraints": True,  # Full-time work
    "risk_tolerance": "conservative"
}

diagnostic_signals = {
    "current_weekly_mileage": 70
}

# Generate plan - should apply alternation pattern
plan = generate_principle_based_plan(
    athlete_id="...",
    goal_distance="Marathon",
    current_fitness={"vdot": 50.0},
    diagnostic_signals=diagnostic_signals,
    athlete_profile=athlete_profile,
    weeks_to_race=12
)

# Check alternation applied
assert plan["plan"]["alternation_applied"] == True
assert plan["plan"]["alternation_rationale"] is not None

# Check week alternation focus
for week in plan["plan"]["weeks"]:
    if week.get("alternation_focus"):
        print(f"Week {week['week_number']}: {week['alternation_focus']}")
```

## Files Modified

1. ✅ `apps/api/scripts/add_runner_road_magic_principle.py` - Script to add principle to KB
2. ✅ `apps/api/services/blending_heuristics.py` - Added alternation weighting logic
3. ✅ `apps/api/services/principle_plan_generator.py` - Applied alternation pattern to plan generation
4. ✅ `apps/api/services/ai_coaching_engine.py` - Added alternation explanation for clients

## Status

✅ **Complete** - Runner Road Magic Alternation principle fully integrated
- Knowledge base entry created
- Blending heuristics updated
- Plan generator applies alternation pattern
- Explanation layer references alternation when applied
- Ready for testing with high-volume/masters athletes

## Next Steps

1. Test with real athlete profiles (high volume, masters, work constraints)
2. Monitor efficiency gains from alternation vs. non-alternation plans
3. Refine alternation frequency based on athlete response
4. Consider adding alternation pattern visualization in UI

---

**Integration Complete** 🚀

