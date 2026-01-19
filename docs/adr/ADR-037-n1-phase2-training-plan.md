# ADR-037: N=1 Phase 2 Training Plan Improvements

## Status
**Accepted**

## Date
2026-01-17

## Context

The current plan generator applies population-based constraints uniformly to all athletes, overriding proven individual capabilities. Specifically:

### Bug: Population Caps Override Proven Capability

For athlete `mbshaf@gmail.com`:
- **Proven long run capability:** 22.0 miles (actual longest run in 198-activity history)
- **Population time cap applied:** 18.2 miles (150 min / 8.23 pace)
- **Result:** Plan caps long runs at 18.2mi despite athlete proving 22mi capability

The code uses `min(volume_cap, time_cap, proven_cap)`, which means population rules ALWAYS win if they're lower than proven capability. This violates the N=1 mandate.

### Additional Phase 2 Gaps

1. **Zero strides/hill sprints** despite 75 mpw elite volume
2. **Tempo and threshold treated identically** (different physiological targets)
3. **3-week taper** when 2 weeks is evidence-based for fast adapters (τ1=25)
4. **Monotonous easy runs** (same distance every day, no variety)

### The N=1 Mandate (from Manifesto)

> "Population averages are noise. The individual is the signal."

> "No Age-Based Assumptions: The system makes zero preconceptions about adaptation speed, recovery, durability, or any response curve based on age. All patterns are discovered from the athlete's own data."

## Decision

### 1. Proven Capability Overrides Population Guidelines

**New logic for long run cap:**

```python
def calculate_long_run_cap(bank: FitnessBank, paces: Dict) -> float:
    """
    N=1 long run cap.
    
    For athletes WITH proven capability: their history IS the answer.
    For athletes WITHOUT proven capability: use population guidelines.
    """
    long_pace = paces.get("long", 9.0)
    
    # Population guidelines (fallback only)
    volume_cap = bank.peak_weekly_miles * 0.30
    time_cap = 150 / long_pace  # 150 minutes
    population_cap = min(volume_cap, time_cap)
    
    # Athlete has proven long run capability?
    if bank.peak_long_run_miles >= 15:
        # They've proven it - use their capability
        # Allow small stretch (2mi) for progression
        proven_cap = bank.peak_long_run_miles + 2
        
        # Log that we're using proven capability
        logger.info(f"N=1: Using proven long run cap {proven_cap:.1f}mi "
                   f"(peak={bank.peak_long_run_miles:.1f}mi, "
                   f"population would be {population_cap:.1f}mi)")
        
        return proven_cap
    else:
        # No proven capability - fall back to population guidelines
        logger.info(f"N=1: Using population long run cap {population_cap:.1f}mi "
                   f"(no proven capability > 15mi)")
        return population_cap
```

### 2. Add Strides and Hill Sprints

| Workout Type | Frequency | Phase | Structure |
|--------------|-----------|-------|-----------|
| Strides | 2x/week | Base, Build | 6x20sec after easy runs |
| Hill sprints | 1x/week | Build only | 8x10sec max effort |

Strides are neuromuscular activation, not quality work. They're added to existing easy days, not new workout days.

### 3. Distinguish Tempo vs Threshold

| Type | Pace | Duration | HR Zone | Purpose |
|------|------|----------|---------|---------|
| Tempo | ~85% max HR | 20-40 min sustained | "Comfortably hard" | Aerobic efficiency |
| Threshold | Lactate threshold | 20-30 min intervals | ~88-90% max HR | Lactate clearance |

Plan generator will alternate between tempo and threshold in BUILD phase, not treat them as identical.

### 4. τ1-Driven Taper Length

| τ1 Range | Adaptation Speed | Taper Length |
|----------|-----------------|--------------|
| < 30 | Fast adapter | 2 weeks |
| 30-45 | Normal | 2-3 weeks |
| > 45 | Slow adapter | 3 weeks |

Athlete `mbshaf@gmail.com` has τ1=25 → 2-week taper.

### 5. Easy Run Variation

Instead of identical 8mi easy runs, distribute with intentional variety:

- **Post-quality day:** Shorter recovery (6mi)
- **Mid-week:** Medium (7-8mi)  
- **Pre-long run:** Medium (7mi)
- **Some easy days:** Add strides

Pattern creates psychological freshness and varied stimulus.

## Considered Options

### Option A: Add "experienced athlete" flag to bypass caps
**Rejected:** Still population-first thinking. Creates edge cases. Doesn't scale.

### Option B: ML-based workout selection
**Rejected:** Black box. Can't explain decisions. Cold-start worse. Overkill for deterministic rules.

### Option C: Keep population rules, just raise the caps
**Rejected:** Still arbitrary. 160 minutes instead of 150 is still a population rule overriding individual data.

## Implementation

### Files Modified

1. `apps/api/services/workout_prescription.py`
   - Replace `min(volume_cap, time_cap, proven_cap)` with N=1 logic
   - Add strides to eligible easy days
   - Add tempo vs threshold distinction
   - Add easy run distance variation

2. `apps/api/services/week_theme_generator.py`
   - τ1-driven taper length (already partially implemented, verify)
   - Ensure 2-week taper for fast adapters

3. `apps/api/data/workout_templates.json`
   - Add tempo workout templates (distinct from threshold)
   - Add hill sprint templates
   - Add strides templates

### Audit Logging

Every long run prescription logs:
- `proven_capability_used: true/false`
- `proven_long_run_miles`
- `population_cap_would_be`
- `final_cap_used`
- `fallback_reason` (if population used)

### Tests

1. **Proven capability override:** Athlete with 22mi proven → cap is 24mi, not 18mi
2. **Population fallback:** Athlete with no long runs > 15mi → use population cap
3. **Strides added:** Build weeks include 2 easy+strides days
4. **Tempo vs threshold:** Both appear in BUILD phase, not just one type
5. **τ1-driven taper:** Fast adapter (τ1 < 30) gets 2-week taper

## Consequences

### Positive

- Long runs match proven capability (22mi for experienced marathoners)
- Plans include neuromuscular work (strides, hills)
- Tempo and threshold serve distinct purposes
- Taper length individualized to adaptation speed
- Easy runs have variety for psychological freshness
- Fully auditable decisions

### Negative

- More complex than static rules
- Requires accurate FitnessBank (garbage in → garbage out)
- New athletes get conservative plans until data accumulates

### Mitigations

- Data sufficiency tiers handle cold start
- Audit logging enables debugging
- Feature flag enables safe rollout

## Feature Flag

**Flag:** `plan.phase2_n1_improvements`

| State | Behavior |
|-------|----------|
| `off` | Current behavior |
| `shadow` | Run both, log comparison, serve current |
| `on` | Serve new N=1 behavior |

**Rollout criteria:**
1. Shadow mode 7 days, zero errors
2. Long runs for experienced athletes reach proven capability
3. Strides appear 2x/week in build phase
4. Manual review of `mbshaf@gmail.com` plan approved

## Related ADRs

- ADR-030: Fitness Bank Framework
- ADR-031: Constraint-Aware Planning
- ADR-035: N=1 Individualized TSB Zones
- ADR-036: N=1 Learning Workout Selection Engine
