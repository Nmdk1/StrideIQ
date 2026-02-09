# ADR-022: Individual Performance Model for Plan Generation

**Status:** PROPOSED  
**Date:** 2026-01-15  
**Author:** AI Assistant  
**Reviewers:** Michael Shaffer

---

## Context

Current plan generation uses template-based approaches with RPI-derived paces and fixed periodization structures. While methodologically sound, this approach:

1. Uses **generic constants** (τ1=42, τ2=7) rather than individual response parameters
2. Does not **predict outcomes** — no race time projection from current trajectory
3. Does not **optimize load** — uses templates, not calculated optimal TSS trajectories
4. Does not **use pre-race fingerprint** to calculate exact taper parameters
5. Does not **surface counter-conventional findings** that contradict population wisdom

## Decision

Build an **Individual Performance Model (IPM)** that:

1. **Calibrates individual time constants** (τ1, τ2) from athlete's historical data
2. **Calculates optimal load trajectory** to maximize race-day fitness
3. **Predicts race time** from current fitness trajectory
4. **Computes taper** from pre-race fingerprint optimal state
5. **Applies counter-conventional findings** from causal attribution

### Key Constraint

**No LLM/GPT dependency.** All calculations must be algorithmic and execute in real-time when athlete creates a plan.

---

## Architecture

### Component 1: Model Calibration Service

**Purpose:** Fit individual τ1 (fitness decay) and τ2 (fatigue decay) from athlete's historical data.

**Algorithm:** Banister Impulse-Response Model fitting

```
Performance(t) = p0 + k1 * Fitness(t) - k2 * Fatigue(t)

where:
  Fitness(t) = Σ [TSS(i) * e^(-(t-i)/τ1)]  for all training days i < t
  Fatigue(t) = Σ [TSS(i) * e^(-(t-i)/τ2)]  for all training days i < t
```

**Inputs:**
- Historical TSS series (from training_load.py)
- Historical performance markers (race times converted to RPI, or efficiency trend)

**Outputs:**
- Calibrated τ1 (fitness time constant, typical 30-60 days)
- Calibrated τ2 (fatigue time constant, typical 5-15 days)
- Calibrated k1, k2 (scaling factors)
- Confidence level (based on data quantity/quality)

**Fallback:** If insufficient data (<90 days history or <3 performance markers), use population defaults with low confidence flag.

**Implementation:**
```python
from scipy.optimize import minimize

def fit_banister_model(
    tss_series: List[Tuple[date, float]],  # (date, TSS)
    performance_series: List[Tuple[date, float]],  # (date, RPI or EF)
) -> BanisterModel:
    """
    Fit Banister model parameters to athlete's data.
    
    Uses Nelder-Mead optimization to minimize prediction error.
    """
    def objective(params):
        tau1, tau2, k1, k2, p0 = params
        
        # Constrain to reasonable ranges
        if tau1 < 20 or tau1 > 80: return 1e10
        if tau2 < 3 or tau2 > 20: return 1e10
        if k1 < 0 or k2 < 0: return 1e10
        
        total_error = 0
        for perf_date, actual_perf in performance_series:
            predicted = predict_performance(tss_series, perf_date, tau1, tau2, k1, k2, p0)
            total_error += (predicted - actual_perf) ** 2
        
        return total_error
    
    # Initial guess: population defaults
    x0 = [42, 7, 1.0, 2.0, 50.0]
    
    result = minimize(objective, x0, method='Nelder-Mead')
    
    return BanisterModel(
        tau1=result.x[0],
        tau2=result.x[1],
        k1=result.x[2],
        k2=result.x[3],
        p0=result.x[4],
        fit_error=result.fun,
        confidence=calculate_confidence(len(performance_series), result.fun)
    )
```

---

### Component 2: Optimal Load Calculator

**Purpose:** Given race date and target state, calculate week-by-week TSS to maximize race-day fitness.

**Algorithm:** Backward propagation from target TSB

```
Target: TSB_race = CTL_race - ATL_race = target (e.g., +15)

Given:
- Current CTL, ATL
- Race date (N weeks away)
- Calibrated τ1, τ2

Calculate:
- Optimal weekly TSS for weeks 1 to N-taper
- Taper TSS reduction to hit target TSB
```

**Implementation:**
```python
def calculate_optimal_load_trajectory(
    current_ctl: float,
    current_atl: float,
    race_date: date,
    target_tsb: float,  # From pre-race fingerprint
    tau1: float,
    tau2: float,
    max_weekly_tss: float,  # Athlete's sustainable maximum
    min_weekly_tss: float,  # Minimum to maintain fitness
) -> List[WeeklyLoadTarget]:
    """
    Calculate optimal TSS trajectory to maximize race-day CTL 
    while hitting target TSB.
    """
    weeks_to_race = (race_date - date.today()).days // 7
    
    # Phase 1: Build phase (weeks 1 to N-3)
    # Goal: Maximize CTL accumulation within sustainable limits
    
    # Phase 2: Taper phase (final 2-3 weeks)
    # Goal: Reduce ATL faster than CTL to hit target TSB
    
    # Key insight: ATL decays faster than CTL (τ2 < τ1)
    # So reducing load drops fatigue faster than fitness
    
    trajectory = []
    
    # Build phase: Push sustainable load
    build_weeks = max(1, weeks_to_race - 3)
    for week in range(build_weeks):
        # Progressive build with cutback every 4th week
        if (week + 1) % 4 == 0:
            weekly_tss = max_weekly_tss * 0.7  # Cutback week
        else:
            weekly_tss = max_weekly_tss * (0.85 + 0.05 * min(week, 3))  # Build to max
        
        trajectory.append(WeeklyLoadTarget(
            week_number=week + 1,
            target_tss=weekly_tss,
            phase="build"
        ))
    
    # Simulate CTL/ATL at end of build
    projected_ctl, projected_atl = project_ctl_atl(
        current_ctl, current_atl, trajectory, tau1, tau2
    )
    
    # Taper phase: Calculate required reduction to hit target TSB
    taper_weeks = weeks_to_race - build_weeks
    taper_trajectory = calculate_taper(
        projected_ctl, projected_atl, target_tsb, taper_weeks, tau1, tau2
    )
    
    trajectory.extend(taper_trajectory)
    
    return trajectory
```

---

### Component 3: Race Time Predictor

**Purpose:** Predict race time from current fitness trajectory.

**Algorithm:** Performance = f(CTL, efficiency_trend, race_distance)

**Implementation:**
```python
def predict_race_time(
    athlete_id: UUID,
    race_date: date,
    race_distance_m: float,
    db: Session
) -> RacePrediction:
    """
    Predict race time based on projected race-day fitness.
    
    Uses:
    1. Projected CTL on race day (from load trajectory)
    2. Current efficiency trend (from efficiency_trending.py)
    3. Historical performance at this distance
    4. Pre-race fingerprint match
    """
    # Get calibrated model
    model = get_or_calibrate_model(athlete_id, db)
    
    # Project fitness on race day
    projected_fitness = project_performance(
        athlete_id, race_date, model, db
    )
    
    # Convert fitness to predicted RPI
    predicted_rpi = fitness_to_rpi(projected_fitness, athlete_id, db)
    
    # RPI to race time
    predicted_time = rpi_to_race_time(predicted_rpi, race_distance_m)
    
    # Confidence interval based on model fit quality and data recency
    confidence_interval = calculate_confidence_interval(
        predicted_time, model.fit_error, model.confidence
    )
    
    return RacePrediction(
        predicted_time_seconds=predicted_time,
        confidence_interval_seconds=confidence_interval,
        projected_rpi=predicted_rpi,
        model_confidence=model.confidence,
        factors_considered=["CTL trajectory", "efficiency trend", "historical performance"]
    )
```

---

### Component 4: Taper Calculator (from Pre-Race Fingerprint)

**Purpose:** Calculate exact taper to hit athlete's optimal pre-race state.

**Algorithm:** Work backward from target state

**Implementation:**
```python
def calculate_personalized_taper(
    athlete_id: UUID,
    race_date: date,
    current_ctl: float,
    current_atl: float,
    db: Session
) -> PersonalizedTaper:
    """
    Calculate taper to hit athlete's optimal pre-race state.
    
    Uses:
    1. Pre-race fingerprint (optimal TSB, days since hard, etc.)
    2. Calibrated τ1, τ2
    3. Counter-conventional findings (if any)
    """
    # Get pre-race fingerprint
    fingerprint = get_readiness_profile(athlete_id, db)
    
    # Extract optimal ranges
    target_tsb = fingerprint.optimal_ranges.get('TSB', (10, 20))
    target_days_rest = fingerprint.optimal_ranges.get('Days Since Hard Workout', (2, 4))
    
    # Get calibrated model
    model = get_or_calibrate_model(athlete_id, db)
    
    # Calculate taper start date
    # Need enough time for ATL to drop sufficiently
    target_tsb_mid = (target_tsb[0] + target_tsb[1]) / 2
    taper_days = calculate_taper_days_needed(
        current_ctl, current_atl, target_tsb_mid, model.tau1, model.tau2
    )
    
    taper_start = race_date - timedelta(days=taper_days)
    
    # Calculate last hard workout date
    days_rest_mid = int((target_days_rest[0] + target_days_rest[1]) / 2)
    last_hard_date = race_date - timedelta(days=days_rest_mid)
    
    # Generate taper week structure
    taper_weeks = generate_taper_structure(
        taper_start, race_date, last_hard_date, model, fingerprint
    )
    
    # Add counter-conventional notes if applicable
    notes = []
    if fingerprint.has_counter_conventional_findings:
        for feature in fingerprint.features:
            if feature.is_significant and feature.pattern_type == 'inverted':
                notes.append(f"Your data: {feature.insight_text}")
    
    return PersonalizedTaper(
        taper_start_date=taper_start,
        taper_days=taper_days,
        last_hard_workout_date=last_hard_date,
        target_tsb=target_tsb_mid,
        weeks=taper_weeks,
        counter_conventional_notes=notes,
        confidence=fingerprint.confidence_level
    )
```

---

### Component 5: Plan Generator Integration

**Purpose:** Replace template-based generation with model-driven generation.

**Flow:**
```
1. Athlete creates plan (race date, distance, goal time)
   ↓
2. Calibrate individual model (τ1, τ2, k1, k2)
   ↓
3. Calculate optimal load trajectory (week-by-week TSS)
   ↓
4. Calculate personalized taper (from fingerprint)
   ↓
5. Convert TSS to mileage/intensity distribution
   ↓
6. Apply decay profile (specific workout prescriptions)
   ↓
7. Add correlation context (workout timing)
   ↓
8. Output: Personalized plan with predictions
```

**Implementation:**
```python
def generate_model_driven_plan(
    athlete_id: UUID,
    race_date: date,
    race_distance: str,
    goal_time: Optional[int],  # seconds, or None for "best effort"
    db: Session
) -> GeneratedPlan:
    """
    Generate plan from individual performance model.
    
    No templates. No LLM. Pure calculation.
    """
    # Step 1: Get or calibrate individual model
    model = get_or_calibrate_model(athlete_id, db)
    
    # Step 2: Get current state
    current_load = TrainingLoadCalculator(db).calculate_training_load(athlete_id)
    
    # Step 3: Calculate optimal load trajectory
    trajectory = calculate_optimal_load_trajectory(
        current_ctl=current_load.current_ctl,
        current_atl=current_load.current_atl,
        race_date=race_date,
        target_tsb=get_target_tsb(athlete_id, db),  # From fingerprint
        tau1=model.tau1,
        tau2=model.tau2,
        max_weekly_tss=estimate_max_sustainable_tss(athlete_id, db),
        min_weekly_tss=estimate_min_maintenance_tss(athlete_id, db)
    )
    
    # Step 4: Calculate personalized taper
    taper = calculate_personalized_taper(
        athlete_id, race_date, current_load.current_ctl, current_load.current_atl, db
    )
    
    # Step 5: Convert TSS to weekly structure
    weeks = []
    for week_target in trajectory:
        week = convert_tss_to_week_structure(
            athlete_id=athlete_id,
            week_number=week_target.week_number,
            target_tss=week_target.target_tss,
            phase=week_target.phase,
            db=db
        )
        weeks.append(week)
    
    # Step 6: Apply decay profile for specific workouts
    decay_profile = get_athlete_decay_profile(athlete_id, db)
    weeks = apply_decay_interventions(weeks, decay_profile, race_distance)
    
    # Step 7: Predict race time
    prediction = predict_race_time(athlete_id, race_date, distance_to_meters(race_distance), db)
    
    # Step 8: Build plan
    return GeneratedPlan(
        athlete_id=str(athlete_id),
        race_date=race_date.isoformat(),
        race_distance=race_distance,
        weeks=weeks,
        taper=taper,
        prediction=prediction,
        model_confidence=model.confidence,
        counter_conventional_notes=taper.counter_conventional_notes,
        generated_at=datetime.now().isoformat()
    )
```

---

## Data Requirements

### Minimum for Model Calibration
- 90+ days of training history
- 3+ performance markers (races or time trials)

### Fallback for Insufficient Data
- Use population defaults (τ1=42, τ2=7)
- Flag as "low confidence"
- Show: "More race data will improve predictions"

### Data Sources Used
| Data | Source | Required |
|------|--------|----------|
| Daily TSS | `training_load.py` | Yes |
| Race performances | `Activity.is_race` | Yes |
| Efficiency trend | `efficiency_trending.py` | No (enhances) |
| Pre-race state | `pre_race_fingerprinting.py` | No (enhances) |
| Decay profile | `pace_decay.py` | No (enhances) |
| Correlations | `causal_attribution.py` | No (enhances) |

---

## Files to Create/Modify

### New Files
1. `apps/api/services/individual_performance_model.py` - Model calibration, prediction
2. `apps/api/services/optimal_load_calculator.py` - Load trajectory calculation
3. `apps/api/services/model_driven_plan_generator.py` - Plan generation orchestration
4. `apps/api/tests/test_individual_performance_model.py` - Unit tests

### Modified Files
1. `apps/api/routers/plan_generation.py` - Add model-driven endpoint
2. `apps/api/services/training_load.py` - Expose projection functions

---

## Test Plan

### Unit Tests
1. Model calibration with synthetic data
2. Load trajectory calculation
3. Taper calculation from fingerprint
4. Race time prediction
5. Fallback behavior with insufficient data

### Integration Tests
1. Full plan generation flow
2. Plan generation with minimal data (fallback)
3. Plan generation with rich data (full model)

### Validation
1. Compare predicted vs actual race times for historical data
2. Compare calculated taper to best historical tapers

---

## Security Review

- [ ] No PII exposed in model parameters
- [ ] Model cached per-athlete, not shared
- [ ] Prediction confidence clearly communicated
- [ ] Fallback behavior doesn't mislead

---

## Feature Flag

```python
FEATURE_FLAGS = {
    "plan.model_driven_generation": {
        "enabled": False,  # Start disabled
        "description": "Use individual performance model for plan generation"
    }
}
```

---

## Rollout Plan

1. **Phase 1:** Implement model calibration, validate on historical data
2. **Phase 2:** Implement load trajectory calculator, test against templates
3. **Phase 3:** Implement taper calculator, validate against fingerprints
4. **Phase 4:** Integrate into plan generation behind feature flag
5. **Phase 5:** A/B test model-driven vs template-driven plans
6. **Phase 6:** Gradual rollout based on model confidence

---

## Success Metrics

1. **Prediction Accuracy:** Predicted race time within 3% of actual for athletes with calibrated models
2. **Model Confidence:** 60% of active subscribers have "high" confidence models
3. **Athlete Satisfaction:** Plan completion rate higher for model-driven plans

---

## Appendix: Mathematical Foundations

### Banister Model
```
Performance(t) = p0 + k1·CTL(t) - k2·ATL(t)

CTL(t) = CTL(t-1)·e^(-1/τ1) + TSS(t)·(1 - e^(-1/τ1))
ATL(t) = ATL(t-1)·e^(-1/τ2) + TSS(t)·(1 - e^(-1/τ2))

TSB(t) = CTL(t) - ATL(t)
```

### Taper Duration Calculation
```
Given: Current CTL, ATL, target TSB on race day, τ1, τ2

Current TSB = CTL - ATL

During taper (assuming TSS ≈ 0):
  CTL(t) = CTL(0)·e^(-t/τ1)
  ATL(t) = ATL(0)·e^(-t/τ2)
  TSB(t) = CTL(0)·e^(-t/τ1) - ATL(0)·e^(-t/τ2)

Solve for t where TSB(t) = target_tsb

This is transcendental, solve numerically.
```

### Optimal Load Trajectory
```
Goal: Maximize CTL(race_day) subject to:
  1. TSB(race_day) = target_tsb
  2. Weekly TSS ≤ max_sustainable
  3. Weekly TSS ≥ min_maintenance
  4. Cutback weeks every 3-4 weeks

This is a constrained optimization problem.
Can be solved with gradient descent or grid search.
```

---

*ADR-022: Individual Performance Model for Plan Generation*
