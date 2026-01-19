# ADR-045: Complete Correlation Wiring

**Status:** Complete (Verified 2026-01-19) — **See ADR-045-A for required amendment**  
**Date:** 2026-01-19  
**Author:** Opus 4.5 (Planner)  
**Depends On:** None (foundational)  
**Blocked By:** None

---

## Context

The N=1 Insight Engine requires correlating ALL collected data points against ALL performance outputs. Currently, only a subset of data is wired into the correlation engine:

**Current State:**
- 9 inputs correlated (sleep, HRV, resting HR, work stress/hours, protein, carbs, weight, BMI)
- 1 output correlated (efficiency_factor)
- 6+ DailyCheckin fields collected but NOT correlated
- TSB/CTL/ATL calculated but NOT used as correlation inputs
- Multiple performance outputs available but NOT correlated

**Gap:** Athletes cannot answer questions like:
- "Does my stress level affect my efficiency?"
- "How does my TSB correlate with performance?"
- "Does my motivation predict workout quality?"

---

## Decision

Expand `correlation_engine.py` to include:

### New Inputs (add to `aggregate_daily_inputs`)

| Input | Source | Priority |
|-------|--------|----------|
| `stress_1_5` | DailyCheckin.stress_1_5 | P1 |
| `soreness_1_5` | DailyCheckin.soreness_1_5 | P1 |
| `rpe_1_10` | DailyCheckin.rpe_1_10 | P1 |
| `enjoyment_1_5` | DailyCheckin.enjoyment_1_5 | P2 |
| `confidence_1_5` | DailyCheckin.confidence_1_5 | P2 |
| `motivation_1_5` | DailyCheckin.motivation_1_5 | P2 |
| `overnight_avg_hr` | DailyCheckin.overnight_avg_hr | P2 |
| `hrv_sdnn` | DailyCheckin.hrv_sdnn | P2 |
| `tsb` | TrainingLoadCalculator (derived) | P1 |
| `ctl` | TrainingLoadCalculator (derived) | P1 |
| `atl` | TrainingLoadCalculator (derived) | P1 |

### New Outputs (add to correlation analysis)

| Output | Source | Calculation | Priority |
|--------|--------|-------------|----------|
| `pace_at_easy_hr` | Activity | Pace when avg_hr < 75% max_hr | P1 |
| `recovery_speed` | Efficiency trend | Days until EF normalizes post-hard effort | P1 |
| `workout_completion_rate` | PlannedWorkout | Completed / Scheduled (7-day rolling) | P1 |
| `decoupling_pct` | ActivitySplit | (2nd half pace / 1st half pace) - 1 | P2 |

---

## Implementation

### File: `apps/api/services/correlation_engine.py`

#### 1. Expand `aggregate_daily_inputs` function

Add after existing input queries (around line 275):

```python
# Stress (1-5 scale)
stress_data = db.query(
    DailyCheckin.date,
    DailyCheckin.stress_1_5
).filter(
    DailyCheckin.athlete_id == athlete_id,
    DailyCheckin.date >= start_date.date(),
    DailyCheckin.date <= end_date.date(),
    DailyCheckin.stress_1_5.isnot(None)
).all()

inputs["stress_1_5"] = [(row.date, float(row.stress_1_5)) for row in stress_data]

# Soreness (1-5 scale)
soreness_data = db.query(
    DailyCheckin.date,
    DailyCheckin.soreness_1_5
).filter(
    DailyCheckin.athlete_id == athlete_id,
    DailyCheckin.date >= start_date.date(),
    DailyCheckin.date <= end_date.date(),
    DailyCheckin.soreness_1_5.isnot(None)
).all()

inputs["soreness_1_5"] = [(row.date, float(row.soreness_1_5)) for row in soreness_data]

# RPE (1-10 scale)
rpe_data = db.query(
    DailyCheckin.date,
    DailyCheckin.rpe_1_10
).filter(
    DailyCheckin.athlete_id == athlete_id,
    DailyCheckin.date >= start_date.date(),
    DailyCheckin.date <= end_date.date(),
    DailyCheckin.rpe_1_10.isnot(None)
).all()

inputs["rpe_1_10"] = [(row.date, float(row.rpe_1_10)) for row in rpe_data]

# Enjoyment (1-5 scale)
enjoyment_data = db.query(
    DailyCheckin.date,
    DailyCheckin.enjoyment_1_5
).filter(
    DailyCheckin.athlete_id == athlete_id,
    DailyCheckin.date >= start_date.date(),
    DailyCheckin.date <= end_date.date(),
    DailyCheckin.enjoyment_1_5.isnot(None)
).all()

inputs["enjoyment_1_5"] = [(row.date, float(row.enjoyment_1_5)) for row in enjoyment_data]

# Confidence (1-5 scale)
confidence_data = db.query(
    DailyCheckin.date,
    DailyCheckin.confidence_1_5
).filter(
    DailyCheckin.athlete_id == athlete_id,
    DailyCheckin.date >= start_date.date(),
    DailyCheckin.date <= end_date.date(),
    DailyCheckin.confidence_1_5.isnot(None)
).all()

inputs["confidence_1_5"] = [(row.date, float(row.confidence_1_5)) for row in confidence_data]

# Motivation (1-5 scale)
motivation_data = db.query(
    DailyCheckin.date,
    DailyCheckin.motivation_1_5
).filter(
    DailyCheckin.athlete_id == athlete_id,
    DailyCheckin.date >= start_date.date(),
    DailyCheckin.date <= end_date.date(),
    DailyCheckin.motivation_1_5.isnot(None)
).all()

inputs["motivation_1_5"] = [(row.date, float(row.motivation_1_5)) for row in motivation_data]

# Overnight average HR
overnight_hr_data = db.query(
    DailyCheckin.date,
    DailyCheckin.overnight_avg_hr
).filter(
    DailyCheckin.athlete_id == athlete_id,
    DailyCheckin.date >= start_date.date(),
    DailyCheckin.date <= end_date.date(),
    DailyCheckin.overnight_avg_hr.isnot(None)
).all()

inputs["overnight_avg_hr"] = [(row.date, float(row.overnight_avg_hr)) for row in overnight_hr_data]

# HRV SDNN
hrv_sdnn_data = db.query(
    DailyCheckin.date,
    DailyCheckin.hrv_sdnn
).filter(
    DailyCheckin.athlete_id == athlete_id,
    DailyCheckin.date >= start_date.date(),
    DailyCheckin.date <= end_date.date(),
    DailyCheckin.hrv_sdnn.isnot(None)
).all()

inputs["hrv_sdnn"] = [(row.date, float(row.hrv_sdnn)) for row in hrv_sdnn_data]
```

#### 2. Add TSB/CTL/ATL as inputs

Add new function after `aggregate_daily_inputs`:

```python
def aggregate_training_load_inputs(
    athlete_id: str,
    start_date: datetime,
    end_date: datetime,
    db: Session
) -> Dict[str, List[Tuple[datetime, float]]]:
    """
    Aggregate TSB/CTL/ATL into time-series data for correlation.
    
    These are derived metrics from TrainingLoadCalculator.
    """
    from services.training_load import TrainingLoadCalculator
    
    inputs = {}
    calc = TrainingLoadCalculator(db)
    
    # Get load history for the period
    try:
        load_history = calc.get_load_history(
            athlete_id=UUID(athlete_id),
            days=(end_date - start_date).days + 1
        )
        
        daily_loads = load_history.get("daily_loads", [])
        
        tsb_data = []
        ctl_data = []
        atl_data = []
        
        for day_load in daily_loads:
            day_date = day_load.get("date")
            if isinstance(day_date, str):
                day_date = datetime.fromisoformat(day_date).date()
            elif isinstance(day_date, datetime):
                day_date = day_date.date()
            
            if day_load.get("tsb") is not None:
                tsb_data.append((day_date, float(day_load["tsb"])))
            if day_load.get("ctl") is not None:
                ctl_data.append((day_date, float(day_load["ctl"])))
            if day_load.get("atl") is not None:
                atl_data.append((day_date, float(day_load["atl"])))
        
        inputs["tsb"] = tsb_data
        inputs["ctl"] = ctl_data
        inputs["atl"] = atl_data
        
    except Exception as e:
        logger.warning(f"Failed to get training load for correlation: {e}")
        inputs["tsb"] = []
        inputs["ctl"] = []
        inputs["atl"] = []
    
    return inputs
```

#### 3. Add new output: `aggregate_pace_at_effort`

```python
def aggregate_pace_at_effort(
    athlete_id: str,
    start_date: datetime,
    end_date: datetime,
    db: Session,
    effort_level: str = "easy"  # "easy", "threshold"
) -> List[Tuple[datetime, float]]:
    """
    Aggregate pace at specific effort levels.
    
    Args:
        effort_level: "easy" (< 75% max_hr) or "threshold" (85-92% max_hr)
    
    Returns:
        List of (activity_date, pace_per_km_seconds) tuples
    """
    from models import Athlete
    
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    if not athlete or not athlete.max_hr:
        return []
    
    max_hr = athlete.max_hr
    
    if effort_level == "easy":
        hr_min = 0
        hr_max = int(max_hr * 0.75)
    elif effort_level == "threshold":
        hr_min = int(max_hr * 0.85)
        hr_max = int(max_hr * 0.92)
    else:
        return []
    
    activities = db.query(Activity).filter(
        Activity.athlete_id == athlete_id,
        Activity.start_time >= start_date,
        Activity.start_time <= end_date,
        Activity.avg_hr >= hr_min,
        Activity.avg_hr <= hr_max,
        Activity.distance_m > 0,
        Activity.duration_s > 0
    ).order_by(Activity.start_time).all()
    
    pace_data = []
    for activity in activities:
        pace_per_km = activity.duration_s / (activity.distance_m / 1000.0)
        pace_data.append((activity.start_time.date(), pace_per_km))
    
    return pace_data
```

#### 4. Add new output: `aggregate_workout_completion`

```python
def aggregate_workout_completion(
    athlete_id: str,
    start_date: datetime,
    end_date: datetime,
    db: Session,
    window_days: int = 7
) -> List[Tuple[datetime, float]]:
    """
    Calculate rolling workout completion rate.
    
    Returns:
        List of (date, completion_rate) tuples where rate is 0.0-1.0
    """
    from models import PlannedWorkout, TrainingPlan
    
    # Get active plan
    plan = db.query(TrainingPlan).filter(
        TrainingPlan.athlete_id == athlete_id,
        TrainingPlan.status == "active"
    ).first()
    
    if not plan:
        return []
    
    completion_data = []
    current_date = start_date.date()
    end = end_date.date()
    
    while current_date <= end:
        window_start = current_date - timedelta(days=window_days)
        
        scheduled = db.query(PlannedWorkout).filter(
            PlannedWorkout.plan_id == plan.id,
            PlannedWorkout.scheduled_date >= window_start,
            PlannedWorkout.scheduled_date <= current_date
        ).count()
        
        completed = db.query(PlannedWorkout).filter(
            PlannedWorkout.plan_id == plan.id,
            PlannedWorkout.scheduled_date >= window_start,
            PlannedWorkout.scheduled_date <= current_date,
            PlannedWorkout.completed == True
        ).count()
        
        if scheduled > 0:
            rate = completed / scheduled
            completion_data.append((current_date, rate))
        
        current_date += timedelta(days=1)
    
    return completion_data
```

#### 5. Update `analyze_correlations` to use new inputs/outputs

Modify the main `analyze_correlations` function to merge the new inputs:

```python
def analyze_correlations(
    athlete_id: str,
    days: int = 30,
    db: Session = None,
    include_training_load: bool = True,  # NEW PARAMETER
    output_metric: str = "efficiency"     # NEW PARAMETER: "efficiency", "pace_easy", "completion"
) -> Dict[str, Any]:
    """
    Analyze correlations between inputs and outputs.
    
    Args:
        include_training_load: Include TSB/CTL/ATL as inputs
        output_metric: Which output to correlate against
    """
    # ... existing setup code ...
    
    # Get standard inputs
    inputs = aggregate_daily_inputs(athlete_id, start_date, end_date, db)
    
    # Add training load inputs if requested
    if include_training_load:
        load_inputs = aggregate_training_load_inputs(athlete_id, start_date, end_date, db)
        inputs.update(load_inputs)
    
    # Get outputs based on metric
    if output_metric == "efficiency":
        outputs = aggregate_efficiency_outputs(athlete_id, start_date, end_date, db)
    elif output_metric == "pace_easy":
        outputs = aggregate_pace_at_effort(athlete_id, start_date, end_date, db, "easy")
    elif output_metric == "pace_threshold":
        outputs = aggregate_pace_at_effort(athlete_id, start_date, end_date, db, "threshold")
    elif output_metric == "completion":
        outputs = aggregate_workout_completion(athlete_id, start_date, end_date, db)
    else:
        outputs = aggregate_efficiency_outputs(athlete_id, start_date, end_date, db)
    
    # ... rest of correlation logic ...
```

---

## Acceptance Criteria

### Must Pass

1. **All DailyCheckin fields queryable as correlates**
   - Test: Call `aggregate_daily_inputs` → verify all 8 new fields present
   - Verify: `stress_1_5`, `soreness_1_5`, `rpe_1_10`, `enjoyment_1_5`, `confidence_1_5`, `motivation_1_5`, `overnight_avg_hr`, `hrv_sdnn`

2. **TSB/CTL/ATL available as inputs**
   - Test: Call `aggregate_training_load_inputs` → verify tsb, ctl, atl lists populated
   - Verify: Values match TrainingLoadCalculator output

3. **Pace at effort calculable**
   - Test: Call `aggregate_pace_at_effort(athlete_id, ..., "easy")` → returns data
   - Verify: Only activities with avg_hr < 75% max_hr included

4. **Workout completion rate calculable**
   - Test: Call `aggregate_workout_completion` → returns 7-day rolling rate
   - Verify: Rate matches manual calculation

5. **Correlations run without error**
   - Test: `analyze_correlations(athlete_id, days=30, include_training_load=True)`
   - Verify: Returns results with new inputs included

### Should Pass

6. **New inputs appear in correlation results**
   - Verify: If stress_1_5 has data, it appears in correlation output

7. **Multiple output metrics work**
   - Test: `analyze_correlations(..., output_metric="pace_easy")`
   - Verify: Correlations computed against pace data

---

## Testing Strategy

### Unit Tests

Add to `tests/test_correlation_engine.py`:

```python
class TestExpandedInputs:
    """Test new correlation inputs."""
    
    def test_stress_input_collected(self, db, test_athlete):
        # Create check-in with stress
        checkin = DailyCheckin(
            athlete_id=test_athlete.id,
            date=date.today(),
            stress_1_5=4
        )
        db.add(checkin)
        db.commit()
        
        inputs = aggregate_daily_inputs(
            str(test_athlete.id),
            datetime.now() - timedelta(days=7),
            datetime.now(),
            db
        )
        
        assert "stress_1_5" in inputs
        assert len(inputs["stress_1_5"]) == 1
        assert inputs["stress_1_5"][0][1] == 4.0


class TestTrainingLoadInputs:
    """Test TSB/CTL/ATL as correlation inputs."""
    
    def test_tsb_collected(self, db, test_athlete_with_activities):
        inputs = aggregate_training_load_inputs(
            str(test_athlete_with_activities.id),
            datetime.now() - timedelta(days=30),
            datetime.now(),
            db
        )
        
        assert "tsb" in inputs
        assert "ctl" in inputs
        assert "atl" in inputs


class TestNewOutputs:
    """Test new correlation outputs."""
    
    def test_pace_at_easy_effort(self, db, test_athlete_with_activities):
        outputs = aggregate_pace_at_effort(
            str(test_athlete_with_activities.id),
            datetime.now() - timedelta(days=30),
            datetime.now(),
            db,
            "easy"
        )
        
        assert isinstance(outputs, list)
        # Further assertions based on test data
```

### Integration Test

```python
def test_full_correlation_with_new_inputs(db, test_athlete_with_full_data):
    """End-to-end correlation with all new inputs."""
    result = analyze_correlations(
        athlete_id=str(test_athlete_with_full_data.id),
        days=30,
        db=db,
        include_training_load=True,
        output_metric="efficiency"
    )
    
    assert result["ok"] is True
    correlations = result.get("correlations", [])
    
    # Verify new inputs appear if they have data
    input_names = [c["input_name"] for c in correlations]
    # At minimum, training load inputs should appear
    assert any(name in input_names for name in ["tsb", "ctl", "atl"])
```

---

## Rollback Plan

If issues arise:
1. Revert changes to `correlation_engine.py`
2. New parameters have defaults that maintain existing behavior
3. No database schema changes required

---

## Dependencies

- **Requires:** TrainingLoadCalculator (already exists)
- **Requires:** DailyCheckin model fields (already exist)
- **Requires:** PlannedWorkout.completed field (already exists)

---

## Notes for Builder

1. Follow existing patterns in `aggregate_daily_inputs` for consistency
2. Handle None values gracefully (skip, don't error)
3. Log warnings for edge cases but don't fail
4. Maintain backward compatibility with existing `analyze_correlations` calls
5. Add appropriate imports at top of file

---

## Post-Implementation

After Builder completes:
1. Tester verifies all acceptance criteria
2. Planner documents lessons learned
3. coach_tools.py `get_correlations` automatically benefits (no changes needed)

---

**Ready for Builder execution.**
