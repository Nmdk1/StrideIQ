# ADR-045-A: Complete Performance Correlation (Amendment)

**Status:** Complete (Verified 2026-01-19)  
**Date:** 2026-01-19  
**Author:** Opus 4.5 (Planner)  
**Amends:** ADR-045  
**Reason:** Original ADR failed methodology AND outputs

---

## Context

### Judge's Original Requirement
> "literally every single data point we collect MUST be usable as a correlate to output (improved performance metrics - efficiency, pace, PRs, etc...)"

### What ADR-045 Got Wrong

1. **Missing outputs:** No PB events, race pace, trend analysis
2. **Flawed methodology:** Correlating TSB vs raw EF across ALL runs
3. **No effort segmentation:** Mixing easy runs (HR 101) with races (HR 158)
4. **No trend analysis:** Point-in-time values instead of improvement rate

### Proof of Failure

Athlete data shows:
- Nov 29: Half Marathon at 4.13 min/km, HR 151 → Pace/HR = **1.64**
- Oct 2024: Similar runs at 5.3+ min/km → Pace/HR = 2.2-2.7
- **30-40% efficiency improvement** — correlation engine returned **0 correlations**

This is unacceptable.

---

## Decision

### Part 1: Fix Methodology (Effort-Segmented Analysis)

```python
def aggregate_efficiency_by_effort_zone(
    athlete_id: str,
    start_date: datetime,
    end_date: datetime,
    db: Session,
    effort_zone: str = "threshold"  # "easy", "threshold", "race"
) -> List[Tuple[date, float]]:
    """
    Aggregate efficiency for COMPARABLE runs only.
    
    Effort zones (% max HR):
    - easy: < 75%
    - threshold: 80-88%
    - race: > 88%
    
    Returns Pace/HR ratio (lower = better efficiency at that effort)
    """
    from models import Athlete, Activity
    
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    if not athlete or not athlete.max_hr:
        return []
    
    max_hr = athlete.max_hr
    
    if effort_zone == "easy":
        hr_min, hr_max = 0, int(max_hr * 0.75)
    elif effort_zone == "threshold":
        hr_min, hr_max = int(max_hr * 0.80), int(max_hr * 0.88)
    elif effort_zone == "race":
        hr_min, hr_max = int(max_hr * 0.88), 999
    else:
        return []
    
    activities = db.query(Activity).filter(
        Activity.athlete_id == athlete_id,
        Activity.start_time >= start_date,
        Activity.start_time <= end_date,
        Activity.avg_hr >= hr_min,
        Activity.avg_hr <= hr_max,
        Activity.distance_m >= 3000,  # Minimum 3km for meaningful data
        Activity.duration_s > 0
    ).order_by(Activity.start_time).all()
    
    result = []
    for a in activities:
        pace_sec_km = a.duration_s / (a.distance_m / 1000)
        efficiency = pace_sec_km / a.avg_hr  # Lower = faster at same HR
        result.append((a.start_time.date(), efficiency))
    
    return result
```

### Part 2: Add Efficiency Trend Analysis

```python
def aggregate_efficiency_trend(
    athlete_id: str,
    start_date: datetime,
    end_date: datetime,
    db: Session,
    effort_zone: str = "threshold",
    window_days: int = 30
) -> List[Tuple[date, float]]:
    """
    Calculate rolling efficiency improvement rate.
    
    Returns % change in efficiency vs baseline (negative = improvement)
    """
    raw_data = aggregate_efficiency_by_effort_zone(
        athlete_id, start_date, end_date, db, effort_zone
    )
    
    if len(raw_data) < 5:
        return []
    
    # Baseline: first 5 data points average
    baseline = sum(d[1] for d in raw_data[:5]) / 5
    
    result = []
    for d, eff in raw_data[5:]:
        pct_change = ((eff - baseline) / baseline) * 100
        result.append((d, pct_change))
    
    return result
```

### Part 3: Add PB Event Correlation

```python
def aggregate_pb_events(
    athlete_id: str,
    start_date: datetime,
    end_date: datetime,
    db: Session
) -> List[Tuple[date, float]]:
    """
    Aggregate PB events as binary time series.
    
    Returns:
        List of (date, 1.0) for PB days, (date, 0.0) for non-PB days
    """
    from models import PersonalBest, Activity
    
    # Get all PB dates
    pbs = db.query(PersonalBest.achieved_at).filter(
        PersonalBest.athlete_id == athlete_id,
        PersonalBest.achieved_at >= start_date,
        PersonalBest.achieved_at <= end_date
    ).all()
    
    pb_dates = {pb.achieved_at.date() for pb in pbs}
    
    # Get all activity dates
    activities = db.query(Activity.start_time).filter(
        Activity.athlete_id == athlete_id,
        Activity.start_time >= start_date,
        Activity.start_time <= end_date
    ).all()
    
    activity_dates = {a.start_time.date() for a in activities}
    
    # Create binary series
    result = []
    for d in sorted(activity_dates):
        result.append((d, 1.0 if d in pb_dates else 0.0))
    
    return result
```

### 2. `aggregate_race_pace`

Pace on hard/race efforts only (efforts where avg_hr > 85% max_hr OR distance > 5km).

```python
def aggregate_race_pace(
    athlete_id: str,
    start_date: datetime,
    end_date: datetime,
    db: Session
) -> List[Tuple[date, float]]:
    """
    Aggregate pace on race-like efforts.
    
    Filters to activities that are likely races or hard efforts:
    - avg_hr > 85% max_hr, OR
    - distance > 5km with avg_hr > 80% max_hr
    
    Returns:
        List of (date, pace_per_km_seconds) tuples
    """
    from models import Athlete, Activity
    
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    if not athlete or not athlete.max_hr:
        return []
    
    max_hr = athlete.max_hr
    hr_threshold_high = int(max_hr * 0.85)
    hr_threshold_mid = int(max_hr * 0.80)
    
    # Race-like efforts: high HR OR long + moderately high HR
    activities = db.query(Activity).filter(
        Activity.athlete_id == athlete_id,
        Activity.start_time >= start_date,
        Activity.start_time <= end_date,
        Activity.distance_m > 0,
        Activity.duration_s > 0,
        Activity.avg_hr.isnot(None)
    ).filter(
        db.or_(
            Activity.avg_hr >= hr_threshold_high,
            db.and_(
                Activity.distance_m >= 5000,
                Activity.avg_hr >= hr_threshold_mid
            )
        )
    ).order_by(Activity.start_time).all()
    
    pace_data = []
    for activity in activities:
        pace_per_km = activity.duration_s / (activity.distance_m / 1000.0)
        pace_data.append((activity.start_time.date(), pace_per_km))
    
    return pace_data
```

### 3. `aggregate_pre_pb_state`

TSB/CTL values in the 3 days before each PB (for pattern discovery).

```python
def aggregate_pre_pb_state(
    athlete_id: str,
    start_date: datetime,
    end_date: datetime,
    db: Session,
    days_before: int = 3
) -> Dict[str, Any]:
    """
    Analyze training state in days leading up to PBs.
    
    Returns summary statistics, not time series.
    """
    from models import PersonalBest
    from services.training_load import TrainingLoadCalculator
    
    pbs = db.query(PersonalBest).filter(
        PersonalBest.athlete_id == athlete_id,
        PersonalBest.achieved_at >= start_date,
        PersonalBest.achieved_at <= end_date
    ).all()
    
    if not pbs:
        return {"pb_count": 0, "patterns": None}
    
    calc = TrainingLoadCalculator(db)
    history = calc.get_load_history(athlete_id, days=365)
    
    # Build lookup
    load_by_date = {}
    for item in history:
        d = item.date if hasattr(item, 'date') else item.get('date')
        if hasattr(d, 'date'):
            d = d.date()
        load_by_date[d] = item
    
    pre_pb_tsb = []
    pre_pb_ctl = []
    
    for pb in pbs:
        pb_date = pb.achieved_at.date()
        # Get state 1 day before PB
        check_date = pb_date - timedelta(days=1)
        if check_date in load_by_date:
            item = load_by_date[check_date]
            tsb = item.tsb if hasattr(item, 'tsb') else item.get('tsb')
            ctl = item.ctl if hasattr(item, 'ctl') else item.get('ctl')
            if tsb is not None:
                pre_pb_tsb.append(tsb)
            if ctl is not None:
                pre_pb_ctl.append(ctl)
    
    return {
        "pb_count": len(pbs),
        "pre_pb_tsb_mean": sum(pre_pb_tsb) / len(pre_pb_tsb) if pre_pb_tsb else None,
        "pre_pb_tsb_min": min(pre_pb_tsb) if pre_pb_tsb else None,
        "pre_pb_tsb_max": max(pre_pb_tsb) if pre_pb_tsb else None,
        "pre_pb_ctl_mean": sum(pre_pb_ctl) / len(pre_pb_ctl) if pre_pb_ctl else None,
        "optimal_tsb_range": (min(pre_pb_tsb), max(pre_pb_tsb)) if pre_pb_tsb else None
    }
```

### 4. Update `analyze_correlations` output_metric options

```python
# Add to output_metric options:
elif output_metric == "pb_events":
    outputs = aggregate_pb_events(athlete_id, start_date, end_date, db)
elif output_metric == "race_pace":
    outputs = aggregate_race_pace(athlete_id, start_date, end_date, db)
```

### Part 4: Update analyze_correlations

```python
# Add new output_metric options:
elif output_metric == "efficiency_threshold":
    outputs = aggregate_efficiency_by_effort_zone(athlete_id, start_date, end_date, db, "threshold")
elif output_metric == "efficiency_race":
    outputs = aggregate_efficiency_by_effort_zone(athlete_id, start_date, end_date, db, "race")
elif output_metric == "efficiency_trend":
    outputs = aggregate_efficiency_trend(athlete_id, start_date, end_date, db, "threshold")
elif output_metric == "pb_events":
    outputs = aggregate_pb_events(athlete_id, start_date, end_date, db)
elif output_metric == "race_pace":
    outputs = aggregate_race_pace(athlete_id, start_date, end_date, db)
```

---

## Acceptance Criteria

### DOMAIN VALIDATION (Critical — Tester MUST verify)

**1. Known efficiency improvement MUST be detected**

```python
# Nov 29 Half Marathon: 4.13 min/km @ HR 151 = Pace/HR 1.64
# Oct 2024 similar runs: 5.3+ min/km @ similar HR = Pace/HR 2.2+
# Expected: ~25-30% improvement in efficiency_threshold

data = aggregate_efficiency_by_effort_zone(athlete_id, start, end, db, "threshold")
nov29_eff = [e for d, e in data if d == date(2025, 11, 29)][0]
oct24_eff = [e for d, e in data if d.year == 2024 and d.month == 10]
avg_oct24 = sum(oct24_eff) / len(oct24_eff)

improvement = (avg_oct24 - nov29_eff) / avg_oct24 * 100
assert improvement > 20, f"Expected >20% improvement, got {improvement:.1f}%"
```

**2. Pre-PB TSB pattern MUST match known data**

```python
# Dec 13 10K PR: TSB day before was +28.1
# Nov 29 HM: TSB day before was +18.0

result = aggregate_pre_pb_state(athlete_id, start, end, db)
assert result["pre_pb_tsb_min"] >= 7, "Min TSB before PBs should be >= 7"
assert result["pre_pb_tsb_max"] >= 25, "Max TSB before PBs should be >= 25"
```

**3. Correlation with PB events MUST return results**

```python
result = analyze_correlations(
    athlete_id,
    days=365,  # Full year for enough PBs
    include_training_load=True,
    output_metric="pb_events"
)
# At minimum, TSB should appear in correlations (positive or negative)
assert len(result.get("correlations", [])) > 0 or result.get("sample_sizes", {}).get("inputs", {}).get("tsb", 0) > 0
```

**4. Effort-segmented efficiency returns different data than raw efficiency**

```python
raw = aggregate_efficiency_outputs(athlete_id, start, end, db)
threshold = aggregate_efficiency_by_effort_zone(athlete_id, start, end, db, "threshold")

assert len(threshold) < len(raw), "Threshold should filter out non-threshold runs"
```

### Structural Tests

5. `aggregate_efficiency_by_effort_zone` returns data for each zone
6. `aggregate_efficiency_trend` returns % change values
7. `aggregate_pb_events` returns 1.0 on Dec 13 (10K PR)
8. `aggregate_race_pace` filters to high-HR activities only
9. `aggregate_pre_pb_state` returns TSB/CTL statistics

---

## Testing Protocol

**Tester MUST NOT accept "runs without error" as passing.**

For EACH acceptance criterion:
1. Run the specific test
2. Verify the OUTPUT makes domain sense
3. Cross-check against known athlete data
4. If output contradicts known reality → FAIL

---

## Notes for Builder

1. Import `or_` from sqlalchemy for race_pace filter
2. Import `date` from datetime
3. Use 365 days for PB analysis (need enough PBs)
4. Pre-PB state is summary, not time series
5. Efficiency Pace/HR: LOWER = better (faster at same HR)

---

## Files to Modify

- `apps/api/services/correlation_engine.py`

---

**Awaiting Judge approval.**
