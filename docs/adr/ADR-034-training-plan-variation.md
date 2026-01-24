# ADR-034: Training Plan Workout Variation

## Status

Proposed (Phase 2 - Future Enhancement)

## Context

The current model-driven plan generator (`model_driven_plan_generator.py`) produces physiologically sound training plans but exhibits algorithmic monotony - workouts tend to repeat with similar structures week over week. User feedback identified this pattern:

> "There is little variation to the distances or types of runs in much of the program...I'm not sure that is good for either psychological or physical adaptations."

### Current Behavior

The plan generator uses fixed week structures per phase:

```python
# BUILD phase - same structure every week
{"day": 3, "type": "quality", "tss_pct": 0.14}  # Always Thursday
{"day": 6, "type": "long", "tss_pct": 0.30}     # Always Sunday, same TSS%
```

This produces plans where:
- Quality workouts always fall on the same day
- Easy run distances are nearly identical week to week
- Threshold work follows the same 3×10min pattern every time
- Long runs progress in distance but not structure

### Why This Happened

1. **TSS Optimization**: The algorithm maximizes physiological efficiency, and repeating proven patterns is "safe" from a load management perspective.

2. **Code Simplicity**: Deterministic structures are easier to implement, test, and debug than stochastic variation.

3. **Risk Aversion**: Variation introduces unpredictability; the algorithm errs toward consistent stimulus.

### Why Variation Matters

**Physiological Benefits:**
- **General Adaptation Syndrome**: The body adapts to specific stressors. Varied stimuli prevent accommodation and continue driving adaptation.
- **Muscle Fiber Recruitment**: Different paces recruit different fiber types. Variation ensures comprehensive development.
- **Injury Prevention**: Repetitive identical stresses increase overuse injury risk.

**Psychological Benefits:**
- **Engagement**: Monotonous training leads to mental fatigue and dropout.
- **Confidence**: Variety proves you can handle different challenges.
- **Freshness**: Novel workouts maintain training enthusiasm.

### What Good Variation Looks Like

For each workout type, appropriate variation includes:

**Easy Runs:**
- Distance: 4-8mi range based on weekly load, not same every day
- Terrain: Flat, rolling, trail (if athlete history shows trail use)
- Time-based vs distance-based alternation

**Threshold Work (precise labels, no “tempo” catch-all):**
- Week 1: 3×10min at T-pace (2min jog recovery)
- Week 2: 2×15min cruise intervals
- Week 3: 20min continuous threshold
- Week 4: 4×8min at T-pace (hills if applicable)
- Progression: Extend duration or reduce recovery as fitness builds

**Long Runs:**
- Distance progression: 14 → 16 → 18 → 15 (cutback) → 18 → 20 → 16 (cutback)
- Structure variation:
  - Easy throughout
  - Marathon pace finish (last 4-8mi)
  - Progressive (start easy, finish moderate)
  - MP sandwich (easy-MP-easy-MP-easy)

**Strides/Hills:**
- Strides: 6×20s, 4×30s, 8×15s - vary count and duration
- Hills: Short power hills (10-15s steep), long hills (60-90s steady grade)
- Alternation: Flat strides one week, hill sprints next

## Decision

Implement a **Workout Variation Engine** as a Phase 2 enhancement with these components:

### 1. Workout Template Library

Create structured templates for each workout type with multiple variants:

```python
THRESHOLD_VARIANTS = [
    {
        "id": "cruise_intervals_3x10",
        "name": "Cruise Intervals",
        "structure": "3×10min @ T-pace, 2min jog",
        "total_quality_minutes": 30,
        "progression_week": [1, 5, 9],  # When to use
        "fatigue_cost": "moderate"
    },
    {
        "id": "threshold_continuous_20",
        "name": "Threshold Run (continuous)",
        "structure": "20min continuous @ T-pace",
        "total_quality_minutes": 20,
        "progression_week": [2, 6, 10],
        "fatigue_cost": "moderate"
    },
    {
        "id": "threshold_hills_4x3",
        "name": "Threshold Hills",
        "structure": "4×3min uphill @ T-effort, jog down",
        "total_quality_minutes": 12,
        "progression_week": [3, 7, 11],
        "fatigue_cost": "high",
        "requires": ["hill_access"]
    },
    # ... more variants
]
```

### 2. Variation Selector Logic

```python
def select_workout_variant(
    workout_type: str,
    week_number: int,
    phase: TrainingPhase,
    athlete_preferences: Dict,
    recent_workouts: List[str],  # Avoid immediate repeats
    constraints: Dict  # e.g., no hills, no track access
) -> WorkoutTemplate:
    """Select appropriate workout variant."""
    # Filter to appropriate phase
    candidates = [v for v in TEMPLATES[workout_type] if phase in v["phases"]]
    
    # Filter by constraints
    if "no_hills" in constraints:
        candidates = [v for v in candidates if "hills" not in v["id"]]
    
    # Avoid recent repeats (last 2 uses of same variant)
    candidates = [v for v in candidates if v["id"] not in recent_workouts[-2:]]
    
    # Select based on progression or random within valid set
    return select_for_week(candidates, week_number)
```

### 3. Progressive Long Run Structure

Long runs should progress in both distance AND structure:

```python
LONG_RUN_PROGRESSION = {
    "base": [
        {"week_pct": 0.0-0.3, "structure": "easy_throughout"},
        {"week_pct": 0.3-0.5, "structure": "easy_with_pickups"},  # 4×1min surge
    ],
    "build": [
        {"week_pct": 0.0-0.25, "structure": "easy_throughout"},
        {"week_pct": 0.25-0.5, "structure": "mp_finish_short"},   # Last 4mi @ MP
        {"week_pct": 0.5-0.75, "structure": "progressive"},        # Negative split
        {"week_pct": 0.75-1.0, "structure": "mp_finish_long"},    # Last 8mi @ MP
    ],
    "peak": [
        {"structure": "race_simulation"},  # Full dress rehearsal
    ]
}
```

### 4. Easy Run Distance Variation

Easy runs should not all be the same distance:

```python
def distribute_easy_miles(
    weekly_easy_miles: float,
    num_easy_days: int,
    constraints: List[str]  # e.g., ["short_tuesday", "medium_saturday"]
) -> List[float]:
    """Distribute easy miles with intentional variation."""
    # Example for 35 easy miles over 4 days:
    # [6, 8, 10, 11] instead of [8.75, 8.75, 8.75, 8.75]
    
    variation_factor = 0.3  # 30% deviation allowed
    # Implementation distributes with natural-feeling variation
```

### 5. Feature Flag

```python
VARIATION_ENGINE_ENABLED = feature_flag("plan.variation_engine", default=False)
```

## Implementation Plan

### Phase 2a: Template Library (Foundation)
1. Define `WorkoutTemplate` dataclass
2. Create initial template library (8-10 variants per workout type)
3. Add variant selection logic with repeat avoidance
4. Feature flag: `plan.variation_templates`

### Phase 2b: Long Run Progression
1. Implement `LONG_RUN_PROGRESSION` mapping
2. Add structure selection based on cycle phase and week
3. Generate appropriate descriptions for each structure
4. Feature flag: `plan.long_run_variation`

### Phase 2c: Easy Run Distribution
1. Implement non-uniform easy mile distribution
2. Respect constraints (e.g., short before quality, longer on recovery days)
3. Feature flag: `plan.easy_variation`

### Phase 2d: Full Integration
1. Combine all variation systems
2. Add UI display for workout variants
3. Track variant history to prevent repeats
4. Master feature flag: `plan.variation_engine`

## Consequences

### Positive
- **Better adaptation**: Varied stimuli prevent accommodation
- **Injury reduction**: Reduced repetitive stress
- **Psychological freshness**: More engaging training
- **Specificity**: Can match athlete preferences (hills vs flat, etc.)

### Negative
- **Complexity**: More code paths to test and maintain
- **Unpredictability**: Harder to compare week-over-week
- **Testing burden**: Need to verify all variants are physiologically sound

### Neutral
- **Migration**: Existing plans continue to work; variation is additive
- **Data model**: May need to store variant IDs for plan recreation

## Success Metrics

1. **User Engagement**: Reduced plan abandonment rate
2. **Injury Rate**: Decreased overuse injuries in users with variation enabled
3. **Training Compliance**: Higher adherence to prescribed workouts
4. **User Feedback**: Qualitative improvement in "plan feels personalized" ratings

## Related ADRs

- ADR-022: Individual Performance Model (foundation for plan generation)
- ADR-031: Constraint-Aware Planning (respects athlete constraints)
- ADR-033: Narrative Translation Layer (will need variant-aware narratives)

## References

- Bompa, T. & Haff, G. (2009). Periodization: Theory and Methodology of Training
- Seiler, S. (2010). What is Best Practice for Training Intensity Distribution?
- Foster, C. (1998). Monitoring training in athletes with reference to overtraining syndrome

## Notes for Next Agent

### Current State (Phase 1 Complete)
The following Phase 1 fixes have been implemented:
1. **τ1-aware taper**: `calculate_optimal_taper_days()` now considers τ1 (fast adapters get 1.75×τ2, bounded 7-14d)
2. **Strides in all phases**: Added `easy_strides` to base, build, peak, and taper structures
3. **Terminology clarity**: Renamed "Threshold Workout" to "Threshold Intervals" with explicit structure
4. **Rationale field**: Added `rationale` to `DayPlan` dataclass for transparency

### Files Modified in Phase 1
- `apps/api/services/individual_performance_model.py`: Enhanced `calculate_optimal_taper_days()`, added `get_taper_rationale()`
- `apps/api/services/model_driven_plan_generator.py`: Updated week structures, added rationale to workouts

### Where to Start Phase 2
1. Create `apps/api/services/workout_templates.py` with `WorkoutTemplate` dataclass
2. Define template library in `apps/api/data/workout_templates.json` or Python module
3. Add `select_workout_variant()` function to plan generator
4. Test with feature flag `plan.variation_templates`

### Key Design Decisions Needed
- Should variants be stored in JSON (flexible, editable) or Python (type-safe, testable)?
- How to handle athlete terrain constraints (no hills, no track)?
- Should we track workout variant history in DB for repeat avoidance?

### Testing Requirements
- Each variant must have unit test verifying physiological soundness
- Integration test: generated plan contains variety over 16 weeks
- Regression test: TSS totals remain within bounds with variation enabled
