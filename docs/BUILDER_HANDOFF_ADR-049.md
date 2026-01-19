# Builder Handoff: ADR-049 Activity-Linked Nutrition Correlation

**Date:** 2026-01-19  
**ADR:** ADR-049  
**Status:** Ready for Implementation

---

## Objective

Add activity-linked nutrition correlation to answer questions like:
- "Does eating carbs before my long run help my efficiency?"
- "Does protein after hard workouts speed up my recovery?"

---

## Files to Modify

1. `apps/api/services/correlation_engine.py` — Add aggregation function
2. `apps/api/services/coach_tools.py` — Add coach tool
3. `apps/api/services/ai_coach.py` — Register tool + dispatch

---

## Changes Required

### 1. File: `apps/api/services/correlation_engine.py`

Add this function (place near other aggregate functions):

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
        
        current_activity = db.query(Activity).filter(Activity.id == entry.activity_id).first()
        if not current_activity or not current_activity.avg_hr or not current_activity.duration_s or not current_activity.distance_m:
            continue
        
        current_eff = (current_activity.duration_s / (current_activity.distance_m / 1000)) / current_activity.avg_hr
        next_eff = (next_activity.duration_s / (next_activity.distance_m / 1000)) / next_activity.avg_hr
        eff_delta = next_eff - current_eff
        
        result["post_protein_vs_next_efficiency"].append(
            (entry.date, float(entry.protein_g), eff_delta)
        )
    
    return result
```

### 2. File: `apps/api/services/coach_tools.py`

Add these functions at the end of the file:

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
        
        results = {}
        
        for key, pairs in data.items():
            if len(pairs) < 5:
                results[key] = {"sample_size": len(pairs), "correlation": None, "note": "insufficient data"}
                continue
            
            x_vals = [p[1] for p in pairs]
            y_vals = [p[2] for p in pairs]
            
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
    
    if "efficiency" in key and "delta" not in key:
        if r < -0.3:
            return "Strong positive effect: higher intake -> better efficiency"
        elif r < -0.1:
            return "Moderate positive effect"
        elif r > 0.3:
            return "Possible negative effect: higher intake -> worse efficiency"
        elif r > 0.1:
            return "Slight negative effect"
    
    if "delta" in key:
        if r < -0.3:
            return "Strong recovery benefit: higher protein -> faster recovery"
        elif r < -0.1:
            return "Moderate recovery benefit"
        elif r > 0.1:
            return "No recovery benefit detected"
    
    return f"Correlation: {r:.2f}"
```

### 3. File: `apps/api/services/ai_coach.py`

#### Add tool definition to `_assistant_tools()` (after get_efficiency_by_zone):

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

#### Add dispatch case in `chat()` (after get_efficiency_by_zone case):

```python
elif tool_name == "get_nutrition_correlations":
    output = coach_tools.get_nutrition_correlations(self.db, athlete_id, **args)
```

---

## Verification Commands

```powershell
# Check import works
docker-compose exec -T api python -c "from services.correlation_engine import aggregate_activity_nutrition; print('Import OK')"

# Check coach_tools function
docker-compose exec -T api python -c "from services.coach_tools import get_nutrition_correlations; print('Import OK')"

# Check tool count (expect 11)
docker-compose exec -T api python -c "from services.ai_coach import AICoach; from database import SessionLocal; db=SessionLocal(); c=AICoach(db); print(f'Tools: {len(c._assistant_tools())}')"

# Test with athlete
docker-compose exec -T api python -c "
from services.coach_tools import get_nutrition_correlations
from database import SessionLocal
from models import Athlete

db = SessionLocal()
athlete = db.query(Athlete).first()
if athlete:
    result = get_nutrition_correlations(db, athlete.id)
    print(f'ok: {result.get(\"ok\")}')
    print(f'keys: {list(result.get(\"data\", {}).keys())}')
else:
    print('No athlete')
db.close()
"
```

---

## Acceptance Criteria (Builder must verify)

1. Import check passes for both files
2. Tool count = 11
3. Function returns expected keys: `pre_carbs_vs_efficiency`, `pre_protein_vs_efficiency`, `post_protein_vs_next_efficiency`
4. Each key has `sample_size` and either `correlation` or `note`
5. No exceptions on athlete without nutrition data

---

## Rollback

If issues:
1. Remove `get_nutrition_correlations` and `_interpret_nutrition_correlation` from coach_tools.py
2. Remove tool registration and dispatch from ai_coach.py
3. Remove `aggregate_activity_nutrition` from correlation_engine.py

---

**Ready for Builder implementation.**
