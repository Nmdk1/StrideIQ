# ADR-036: N=1 Learning Workout Selection Engine

## Status
**Accepted**

## Date
2026-01-17

## Context

StrideIQ's plan generator currently produces monotonous, non-adaptive plans that fail to:
1. Learn from individual athlete responses
2. Vary stimulus types appropriately
3. Adapt progression to individual τ1/τ2 characteristics
4. Respect distance-specific physiological demands

The core problem: we're generating plans, not coaching athletes.

### The N=1 Mandate

From the Manifesto:
> "Population averages are noise. The individual is the signal."

Every workout selection must be informed by:
- What THIS athlete responds well to (not what "runners" respond to)
- THIS athlete's proven capabilities (not age-group norms)
- THIS athlete's recovery patterns (τ1/τ2, not "rest 48 hours")

## Decision

Implement a **Learning-First Workout Selection Engine** that treats:
- Workout templates as **hypotheses** to be validated
- Athlete history as **curriculum** that teaches the system
- RPE gaps and race outcomes as **feedback signals**
- τ1/τ2 calibration as **individual adaptation profile**

### Core Principles

1. **Templates are Hypotheses**
   - No template is "the right workout"
   - Each prescription tests: "Will this stimulus produce positive adaptation for THIS athlete?"
   - Feedback loop validates or invalidates the hypothesis

2. **Athlete Data is Curriculum**
   - More data → more personalized selection
   - Less data → conservative guardrails, faster exploration
   - Zero data → sensible defaults with explicit uncertainty

3. **Exploration/Exploitation Balance**
   - Uncalibrated athletes: 50% exploration (try different stimuli)
   - Learning athletes: 30% exploration
   - Calibrated athletes: 10% exploration (exploit what works)

4. **τ1-Informed Progression**
   - Fast adapters (τ1 < 30): Can progress faster, shorter tapers
   - Slow adapters (τ1 > 45): Need more patience, longer absorption
   - Individual, not distance-based

## Architecture

### Data Sufficiency Tiers

```
┌─────────────────┬──────────────────┬─────────────────────────────────┐
│ Tier            │ Criteria         │ Selection Behavior              │
├─────────────────┼──────────────────┼─────────────────────────────────┤
│ UNCALIBRATED    │ < 30 activities  │ Phase guardrails, high explore  │
│                 │ No race data     │ Default τ1=42, conservative     │
├─────────────────┼──────────────────┼─────────────────────────────────┤
│ LEARNING        │ 30-100 activities│ Soft phase weights, medium      │
│                 │ Some RPE data    │ explore, emerging preferences   │
├─────────────────┼──────────────────┼─────────────────────────────────┤
│ CALIBRATED      │ 100+ activities  │ Full N=1 weighting, low explore │
│                 │ Race calibration │ τ1/τ2 from Banister model       │
│                 │ RPE history      │ Exploit proven patterns         │
└─────────────────┴──────────────────┴─────────────────────────────────┘
```

### Selection Algorithm

```python
def select_quality_workout(
    athlete: Athlete,
    phase: TrainingPhase,
    week_in_phase: int,
    total_phase_weeks: int,
    recent_quality_ids: List[str],
    db: Session
) -> WorkoutTemplate:
    """
    Select workout using N=1 learning approach.
    """
    # 1. Assess data sufficiency
    data_tier = assess_data_sufficiency(athlete, db)
    
    # 2. Get calibrated or default model
    model = get_athlete_model(athlete, db, data_tier)
    
    # 3. Load templates
    templates = load_template_library()
    candidates = list(templates)
    
    # 4. Phase weighting (SOFT, not hard filter)
    phase_penalty = {
        "uncalibrated": 0.1,  # Strong penalty for out-of-phase
        "learning": 0.3,
        "calibrated": 0.7     # Weak penalty - trust athlete intelligence
    }.get(data_tier, 0.3)
    
    for t in candidates:
        t.phase_weight = 1.0 if phase.value in t.phases else phase_penalty
    
    # 5. τ1-informed progression filter
    progress_pct = week_in_phase / total_phase_weeks
    progression_speed = 42.0 / model.tau1  # Normalized to population mean
    adjusted_progress = progress_pct * progression_speed
    
    candidates = [t for t in candidates 
                  if t.progression_week_range[0] <= adjusted_progress <= t.progression_week_range[1]]
    
    # 6. Variance filter (avoid consecutive same stimulus)
    last_stimulus = get_stimulus_type(recent_quality_ids[-1]) if recent_quality_ids else None
    candidates = [t for t in candidates if t.stimulus_type != last_stimulus]
    candidates = [t for t in candidates if t.id not in recent_quality_ids[-2:]]
    
    # 7. N=1 Response weighting
    if data_tier in ["learning", "calibrated"]:
        response_model = get_athlete_workout_response(athlete.id, db)
        for t in candidates:
            t.score = 1.0
            
            # Boost templates with positive response history
            if t.stimulus_type in response_model:
                rpe_gap = response_model[t.stimulus_type].avg_rpe_gap
                if rpe_gap < 0:  # Felt easier than expected
                    t.score *= 1.0 + abs(rpe_gap) * 0.2
                elif rpe_gap > 1:  # Felt much harder
                    t.score *= 0.7
            
            # Apply what_works / what_doesnt_work from athlete profile
            if t.id in athlete.what_works:
                t.score *= 1.5
            if t.id in athlete.what_doesnt_work:
                t.score *= 0.2
    else:
        for t in candidates:
            t.score = 1.0
    
    # 8. Apply phase weight to final score
    for t in candidates:
        t.final_score = t.score * t.phase_weight
    
    # 9. Constraint filter (HARD - can't do hills if no hills)
    candidates = [t for t in candidates 
                  if all(req in athlete.available_facilities for req in t.requires)]
    
    # 10. Explore/exploit selection
    if not candidates:
        return get_phase_fallback(phase)
    
    explore_prob = {
        "uncalibrated": 0.5,
        "learning": 0.3,
        "calibrated": 0.1
    }.get(data_tier, 0.3)
    
    if random.random() < explore_prob:
        # Explore: weighted random
        return weighted_random_choice(candidates, key=lambda t: t.final_score)
    else:
        # Exploit: highest score
        return max(candidates, key=lambda t: t.final_score)
```

### Distance-Specific Guardrails (NOT Rules)

Guardrails are safety limits, not prescriptions:

| Distance | Max Long Run | MP Work | Primary Quality Focus |
|----------|--------------|---------|----------------------|
| 5K       | 12 mi        | No      | VO2max, Speed        |
| 10K      | 14 mi        | Minimal | Threshold, VO2max    |
| Half     | 16 mi        | Late build | Threshold, Tempo  |
| Marathon | 22 mi        | Yes     | MP, Threshold        |

These caps prevent absurd plans (5K athlete doing 22mi long runs), but progression WITHIN these limits is individualized by τ1 and proven capabilities.

### Feedback Loop Integration

```
Workout Prescribed
        │
        ▼
Athlete Executes
        │
        ▼
┌───────────────────────────────────┐
│ Feedback Captured:                │
│ - Actual vs prescribed pace       │
│ - RPE reported vs expected        │
│ - Completion rate                 │
│ - Recovery quality next day       │
└───────────────────────────────────┘
        │
        ▼
Update athlete_workout_responses
        │
        ▼
Inform future selections
```

## Template Library Structure

External JSON file (`workout_templates.json`):

```json
{
  "templates": [
    {
      "id": "tempo_2x3mi",
      "name": "2x3mi @ T",
      "stimulus_type": "threshold",
      "phases": ["build", "peak"],
      "progression_week_range": [0.3, 0.9],
      "description_template": "{warm}E + 2x3mi @ {t_pace} w/ 2min jog + {cool}E",
      "total_miles": 10,
      "quality_miles": 6,
      "fatigue_cost": 0.7,
      "requires": [],
      "dont_follow": ["tempo_3x2mi", "tempo_4mi_straight"],
      "experience_minimum": "intermediate"
    }
  ]
}
```

Schema validation via Pydantic at startup - malformed templates fail fast.

## Data Model Extensions

### athlete_workout_responses table

```sql
CREATE TABLE athlete_workout_responses (
    id UUID PRIMARY KEY,
    athlete_id UUID REFERENCES athletes(id),
    stimulus_type VARCHAR(50),
    template_id VARCHAR(100),
    execution_count INTEGER DEFAULT 0,
    avg_rpe_gap FLOAT,           -- actual - expected
    avg_pace_gap FLOAT,          -- actual - prescribed (%)
    completion_rate FLOAT,
    last_executed TIMESTAMP,
    positive_outcomes INTEGER,   -- PRs, good race performances after
    negative_outcomes INTEGER,   -- injuries, poor races after
    updated_at TIMESTAMP
);
```

### athlete_intelligence table

```sql
CREATE TABLE athlete_intelligence (
    athlete_id UUID PRIMARY KEY REFERENCES athletes(id),
    what_works JSONB,            -- template_ids that work
    what_doesnt_work JSONB,      -- template_ids to avoid
    injury_triggers JSONB,       -- patterns that preceded injuries
    sweet_spot_volume FLOAT,     -- weekly miles where they thrive
    recovery_needs VARCHAR(20),  -- fast/normal/slow
    notes TEXT,
    updated_at TIMESTAMP
);
```

## Audit Logging Requirements

Every workout selection MUST log:

```json
{
  "timestamp": "2026-01-17T10:30:00Z",
  "athlete_id": "uuid",
  "data_tier": "learning",
  "phase": "build",
  "week_in_phase": 3,
  "candidates_initial": 24,
  "candidates_after_phase": 18,
  "candidates_after_progression": 12,
  "candidates_after_variance": 8,
  "candidates_after_constraints": 7,
  "selection_mode": "exploit",
  "selected_template_id": "tempo_2x3mi",
  "selected_score": 1.35,
  "runner_up_id": "tempo_3x2mi",
  "runner_up_score": 1.28,
  "tau1_used": 38.5,
  "recent_quality_ids": ["intervals_5x1k", "tempo_4mi"]
}
```

## Feature Flag Approach

Flag: `plan.3d_workout_selection`

| State   | Behavior |
|---------|----------|
| off     | Legacy selection (current) |
| shadow  | Run both, log comparison, serve legacy |
| on      | Serve new selection |

Shadow mode comparison metrics:
- Template match rate
- Stimulus type agreement
- Variance violations in legacy

Rollout criteria:
1. Shadow mode 2 weeks with no errors
2. Comparison shows new engine provides more variety
3. No regression in plan completion rates

## Test Strategy

### Unit Tests

1. Phase filter respects data tier penalties
2. Progression filter adjusts for τ1 correctly
3. Variance filter prevents consecutive same stimulus
4. Variance filter prevents template repeat in last 2
5. Response weighting boosts positive RPE gap templates
6. Response weighting penalizes high RPE gap templates
7. Constraint filter removes inaccessible templates
8. Fallback returns valid template when candidates empty

### Integration Tests

1. Full selection flow for uncalibrated athlete
2. Full selection flow for calibrated athlete with response history
3. Comparison: shadow mode produces valid logs
4. Plan generation produces varied week-over-week quality

## Success Metrics

1. **Variety Score**: Unique template IDs used / total quality days ≥ 0.7
2. **Completion Rate**: Workouts completed as prescribed ≥ current baseline
3. **RPE Alignment**: |actual - expected| trending down over time
4. **Athlete Satisfaction**: Subjective plan ratings (future feature)

## Security Considerations

1. Audit logs contain athlete_id - treat as PII, apply retention policy
2. Template library is read-only at runtime
3. Response data updates require authenticated athlete context
4. No string interpolation in template descriptions beyond pace values

## Consequences

### Positive
- Plans become genuinely personalized over time
- Explicit handling of data uncertainty
- Auditable decision trail
- Foundation for continuous learning

### Negative
- More complex than static rules
- Requires feedback capture infrastructure
- Cold-start problem for new athletes

### Mitigations
- Data tier system handles cold start gracefully
- Feedback capture already partially exists (RPE in activity sync)
- Audit logging enables debugging

## Related ADRs

- ADR-031: Constraint-Aware Planning Framework
- ADR-028: Fitness Bank Data Model
- ADR-025: Banister Model Calibration
