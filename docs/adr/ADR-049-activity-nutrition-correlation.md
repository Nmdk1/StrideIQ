# ADR-049: Activity-Linked Nutrition Correlation

**Status:** Complete (Verified 2026-01-19)  
**Date:** 2026-01-19  
**Author:** Opus 4.5 (Planner)  
**Phase:** 5 of 5 (N=1 Insight Engine Roadmap)  
**Depends On:** ADR-045 (correlation engine), ADR-046 (coach tools)

---

## Context

### Current State

The correlation engine aggregates **daily** nutrition totals:
- `daily_protein_g`: Sum of all protein for the day
- `daily_carbs_g`: Sum of all carbs for the day

These are correlated against next-day efficiency (with time lag).

### Gap

The `NutritionEntry` model already supports **activity-linked** nutrition:
- `entry_type`: 'pre_activity', 'during_activity', 'post_activity', 'daily'
- `activity_id`: Links to specific activity

But this granularity is **not used** in correlations:
- Pre-activity carbs → that activity's efficiency (not next-day)
- Post-activity protein → recovery speed (not generic daily)

### Target

Answer athlete questions like:
- "Does eating carbs before my long run help my efficiency?"
- "Does protein after hard workouts speed up my recovery?"
- "What's my optimal pre-run fueling?"

---

## Decision

### Add Activity-Linked Nutrition Correlation

1. **New aggregation function**: `aggregate_activity_nutrition()`
   - Pull pre-activity nutrition for activities with linked entries
   - Calculate efficiency for those activities
   - Return paired data for correlation

2. **New correlation output**: `pre_activity_nutrition_effect`
   - Correlate pre-activity carbs vs activity efficiency
   - Correlate pre-activity protein vs activity efficiency

3. **Recovery correlation**: `post_activity_nutrition_recovery`
   - Correlate post-activity protein vs next-day efficiency delta

4. **New coach tool**: `get_nutrition_correlations()`
   - Expose activity-nutrition correlations to AI Coach

---

## Implementation

### File: `apps/api/services/correlation_engine.py`

#### Add: `aggregate_activity_nutrition()`

```python
def aggregate_activity_nutrition(
    athlete_id: str,
    start_date: datetime,
    end_date: datetime,
    db: Session,
) -> Dict[str, List[Tuple[date, float, float]]]:
    """
    Aggregate activity-linked nutrition with efficiency.
    
    Returns:
        {
            "pre_carbs_vs_efficiency": [(date, carbs_g, efficiency), ...],
            "pre_protein_vs_efficiency": [(date, protein_g, efficiency), ...],
            "post_protein_vs_next_efficiency": [(date, protein_g, next_eff_delta), ...],
        }
    """
    result = {
        "pre_carbs_vs_efficiency": [],
        "pre_protein_vs_efficiency": [],
        "post_protein_vs_next_efficiency": [],
    }
    
    # Get activities with linked pre-activity nutrition
    pre_activity_nutrition = (
        db.query(
            NutritionEntry.activity_id,
            NutritionEntry.carbs_g,
            NutritionEntry.protein_g,
        )
        .filter(
            NutritionEntry.athlete_id == athlete_id,
            NutritionEntry.date >= start_date.date(),
            NutritionEntry.date <= end_date.date(),
            NutritionEntry.entry_type == "pre_activity",
            NutritionEntry.activity_id.isnot(None),
        )
        .all()
    )
    
    for entry in pre_activity_nutrition:
        # Get activity efficiency
        activity = db.query(Activity).filter(Activity.id == entry.activity_id).first()
        if not activity or not activity.avg_hr or not activity.duration_s or not activity.distance_m:
            continue
        
        pace_per_km = activity.duration_s / (activity.distance_m / 1000)
        efficiency = pace_per_km / activity.avg_hr
        activity_date = activity.start_time.date()
        
        if entry.carbs_g:
            result["pre_carbs_vs_efficiency"].append(
                (activity_date, float(entry.carbs_g), efficiency)
            )
        if entry.protein_g:
            result["pre_protein_vs_efficiency"].append(
                (activity_date, float(entry.protein_g), efficiency)
            )
    
    # Get post-activity nutrition with next-day efficiency
    post_activity_nutrition = (
        db.query(
            NutritionEntry.activity_id,
            NutritionEntry.protein_g,
            NutritionEntry.date,
        )
        .filter(
            NutritionEntry.athlete_id == athlete_id,
            NutritionEntry.date >= start_date.date(),
            NutritionEntry.date <= end_date.date(),
            NutritionEntry.entry_type == "post_activity",
            NutritionEntry.protein_g.isnot(None),
        )
        .all()
    )
    
    for entry in post_activity_nutrition:
        # Get next-day efficiency delta
        next_day = entry.date + timedelta(days=1)
        next_activity = (
            db.query(Activity)
            .filter(
                Activity.athlete_id == athlete_id,
                func.date(Activity.start_time) == next_day,
                Activity.sport == "run",
            )
            .first()
        )
        if not next_activity or not next_activity.avg_hr or not next_activity.duration_s or not next_activity.distance_m:
            continue
        
        # Get current activity for baseline
        current_activity = db.query(Activity).filter(Activity.id == entry.activity_id).first()
        if not current_activity or not current_activity.avg_hr or not current_activity.duration_s or not current_activity.distance_m:
            continue
        
        current_eff = (current_activity.duration_s / (current_activity.distance_m / 1000)) / current_activity.avg_hr
        next_eff = (next_activity.duration_s / (next_activity.distance_m / 1000)) / next_activity.avg_hr
        eff_delta = next_eff - current_eff  # Negative = improved
        
        result["post_protein_vs_next_efficiency"].append(
            (entry.date, float(entry.protein_g), eff_delta)
        )
    
    return result
```

### File: `apps/api/services/coach_tools.py`

#### Add: `get_nutrition_correlations()`

```python
def get_nutrition_correlations(
    db: Session,
    athlete_id: UUID,
    days: int = 90,
) -> Dict[str, Any]:
    """
    Get activity-linked nutrition correlations.
    """
    now = datetime.utcnow()
    try:
        days = max(30, min(int(days), 365))
        start = now - timedelta(days=days)
        
        from services.correlation_engine import aggregate_activity_nutrition
        
        data = aggregate_activity_nutrition(str(athlete_id), start, now, db)
        
        # Calculate correlations for each pair
        results = {}
        
        for key, pairs in data.items():
            if len(pairs) < 5:
                results[key] = {"sample_size": len(pairs), "correlation": None, "note": "insufficient data"}
                continue
            
            # Extract x (nutrition) and y (efficiency/delta)
            x_vals = [p[1] for p in pairs]
            y_vals = [p[2] for p in pairs]
            
            # Pearson correlation
            n = len(x_vals)
            mean_x = sum(x_vals) / n
            mean_y = sum(y_vals) / n
            
            numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(x_vals, y_vals))
            denom_x = sum((x - mean_x) ** 2 for x in x_vals) ** 0.5
            denom_y = sum((y - mean_y) ** 2 for y in y_vals) ** 0.5
            
            if denom_x == 0 or denom_y == 0:
                r = 0
            else:
                r = numerator / (denom_x * denom_y)
            
            results[key] = {
                "sample_size": n,
                "correlation": round(r, 3),
                "interpretation": _interpret_nutrition_correlation(key, r),
            }
        
        return {
            "ok": True,
            "tool": "get_nutrition_correlations",
            "generated_at": now.replace(microsecond=0).isoformat(),
            "data": results,
            "evidence": [
                {
                    "type": "derived",
                    "id": f"nutrition_correlations:{str(athlete_id)}",
                    "date": date.today().isoformat(),
                    "value": f"Activity-linked nutrition analysis over {days} days",
                }
            ],
        }
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        return {"ok": False, "tool": "get_nutrition_correlations", "error": str(e)}


def _interpret_nutrition_correlation(key: str, r: float) -> str:
    """Interpret correlation coefficient for nutrition."""
    if abs(r) < 0.1:
        return "No meaningful relationship found"
    
    # For efficiency, negative r means nutrition helps (lower efficiency = better)
    if "efficiency" in key and "delta" not in key:
        if r < -0.3:
            return "Strong positive effect: higher intake → better efficiency"
        elif r < -0.1:
            return "Moderate positive effect"
        elif r > 0.3:
            return "Possible negative effect: higher intake → worse efficiency"
        elif r > 0.1:
            return "Slight negative effect"
    
    # For delta (recovery), negative r means faster recovery
    if "delta" in key:
        if r < -0.3:
            return "Strong recovery benefit: higher protein → faster recovery"
        elif r < -0.1:
            return "Moderate recovery benefit"
        elif r > 0.1:
            return "No recovery benefit detected"
    
    return f"Correlation: {r:.2f}"
```

### File: `apps/api/services/ai_coach.py`

#### Add tool definition to `_assistant_tools()`

```python
{
    "type": "function",
    "function": {
        "name": "get_nutrition_correlations",
        "description": "Get correlations between pre/post-activity nutrition and performance/recovery.",
        "parameters": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Days of history (default 90, max 365).",
                    "minimum": 30,
                    "maximum": 365,
                }
            },
            "required": [],
        },
    },
},
```

#### Add dispatch case in `chat()`

```python
elif tool_name == "get_nutrition_correlations":
    output = coach_tools.get_nutrition_correlations(self.db, athlete_id, **args)
```

---

## Acceptance Criteria

### Must Pass

1. **Pre-activity carbs correlation calculated**
   ```
   result = get_nutrition_correlations(db, athlete_id)
   assert "pre_carbs_vs_efficiency" in result["data"]
   ```

2. **Post-activity protein recovery correlation**
   ```
   assert "post_protein_vs_next_efficiency" in result["data"]
   ```

3. **Interpretation provided**
   ```
   Each correlation includes "interpretation" field
   ```

4. **Tool registered in AI Coach**
   ```
   Tools list includes "get_nutrition_correlations"
   ```

5. **Handles insufficient data gracefully**
   ```
   If < 5 data points: returns "insufficient data" note
   ```

### Domain Validation

6. **With nutrition data**: Returns meaningful correlations
7. **Without nutrition data**: Returns graceful "no data" response

---

## Notes for Builder

1. **NutritionEntry.entry_type** must be exactly 'pre_activity' or 'post_activity'
2. **activity_id** must be populated for linked entries
3. **Efficiency = pace/HR** (lower is better)
4. **Recovery delta = next_eff - current_eff** (negative = improved)

---

## Rollback Plan

If issues:
1. Remove `get_nutrition_correlations` from coach_tools
2. Remove tool registration from ai_coach.py
3. No database changes required

---

**Awaiting Judge approval.**
