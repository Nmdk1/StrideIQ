# ADR-046: Expose Hidden Analytics to Coach

**Status:** Complete (Verified 2026-01-19)  
**Date:** 2026-01-19  
**Author:** Opus 4.5 (Planner)  
**Phase:** 2 of 5 (N=1 Insight Engine Roadmap)  
**Depends On:** ADR-045, ADR-045-A (correlation engine)

---

## Context

### Current State

`coach_tools.py` exposes 5 tools:
1. `get_recent_runs` — Activity data
2. `get_efficiency_trend` — Efficiency over time
3. `get_plan_week` — Current week's plan
4. `get_training_load` — CTL/ATL/TSB
5. `get_correlations` — Statistical correlations

### Hidden Capabilities (Built but Not Exposed)

| Service | Capability | Value to Athlete |
|---------|------------|------------------|
| `race_predictor.py` | Race time predictions | "What can I run?" |
| `recovery_metrics.py` | Recovery half-life, durability, false fitness detection | "Am I recovering well?" |
| `insight_aggregator.py` | Prioritized actionable insights | "What should I focus on?" |
| `correlation_engine.py` (ADR-045-A) | Pre-PB patterns, efficiency by effort zone | "What conditions led to my PRs?" |

### Problem

Athletes cannot ask:
- "What's my predicted marathon time?"
- "How fast do I recover compared to before?"
- "Am I at risk of overtraining?"
- "What was my TSB when I ran my PRs?"

The data exists. The Coach cannot access it.

---

## Decision

Add 5 new tools to `coach_tools.py`:

### 1. `get_race_predictions`

```python
def get_race_predictions(db: Session, athlete_id: UUID) -> Dict[str, Any]:
    """
    Race time predictions for standard distances.
    """
    from services.race_predictor import RacePredictor
    
    now = datetime.utcnow()
    predictor = RacePredictor(db)
    
    distances = ["5K", "10K", "Half Marathon", "Marathon"]
    predictions = {}
    
    for distance in distances:
        try:
            result = predictor.predict(athlete_id, distance)
            if result:
                predictions[distance] = {
                    "predicted_time": result.predicted_time,
                    "confidence": result.confidence,
                    "pace_per_km": result.pace_per_km,
                    "based_on": result.based_on,
                }
        except Exception as e:
            predictions[distance] = {"error": str(e)}
    
    return {
        "ok": True,
        "tool": "get_race_predictions",
        "generated_at": _iso(now),
        "data": {"predictions": predictions},
        "evidence": [
            {
                "type": "derived",
                "id": f"race_predictions:{athlete_id}",
                "date": date.today().isoformat(),
                "value": f"Predictions for {len(predictions)} distances",
            }
        ],
    }
```

### 2. `get_recovery_status`

```python
def get_recovery_status(db: Session, athlete_id: UUID) -> Dict[str, Any]:
    """
    Recovery metrics: half-life, durability, overtraining risk.
    """
    from services.recovery_metrics import (
        calculate_recovery_half_life,
        calculate_durability_index,
        detect_false_fitness,
        detect_masked_fatigue,
    )
    
    now = datetime.utcnow()
    
    half_life = calculate_recovery_half_life(db, str(athlete_id))
    durability = calculate_durability_index(db, str(athlete_id))
    false_fitness = detect_false_fitness(db, str(athlete_id))
    masked_fatigue = detect_masked_fatigue(db, str(athlete_id))
    
    return {
        "ok": True,
        "tool": "get_recovery_status",
        "generated_at": _iso(now),
        "data": {
            "recovery_half_life_days": half_life,
            "durability_index": durability,
            "false_fitness_risk": false_fitness,
            "masked_fatigue_risk": masked_fatigue,
        },
        "evidence": [
            {
                "type": "derived",
                "id": f"recovery_status:{athlete_id}",
                "date": date.today().isoformat(),
                "value": f"Recovery half-life: {half_life} days" if half_life else "Insufficient data",
            }
        ],
    }
```

### 3. `get_active_insights`

```python
def get_active_insights(db: Session, athlete_id: UUID, limit: int = 5) -> Dict[str, Any]:
    """
    Prioritized actionable insights.
    """
    from services.insight_aggregator import get_active_insights as fetch_insights
    
    now = datetime.utcnow()
    limit = max(1, min(int(limit), 10))
    
    insights = fetch_insights(db, str(athlete_id), limit=limit)
    
    insight_rows = []
    for insight in insights:
        insight_rows.append({
            "type": insight.insight_type,
            "priority": insight.priority,
            "title": insight.title,
            "message": insight.message,
            "action": insight.recommended_action,
            "confidence": insight.confidence,
        })
    
    return {
        "ok": True,
        "tool": "get_active_insights",
        "generated_at": _iso(now),
        "data": {
            "insight_count": len(insight_rows),
            "insights": insight_rows,
        },
        "evidence": [
            {
                "type": "derived",
                "id": f"insights:{athlete_id}",
                "date": date.today().isoformat(),
                "value": f"{len(insight_rows)} active insights",
            }
        ],
    }
```

### 4. `get_pb_patterns`

```python
def get_pb_patterns(db: Session, athlete_id: UUID) -> Dict[str, Any]:
    """
    Training patterns that preceded personal bests.
    """
    from services.correlation_engine import aggregate_pre_pb_state
    
    now = datetime.utcnow()
    start = now - timedelta(days=365)
    
    result = aggregate_pre_pb_state(str(athlete_id), start, now, db)
    
    return {
        "ok": True,
        "tool": "get_pb_patterns",
        "generated_at": _iso(now),
        "data": result,
        "evidence": [
            {
                "type": "derived",
                "id": f"pb_patterns:{athlete_id}",
                "date": date.today().isoformat(),
                "value": f"{result.get('pb_count', 0)} PBs analyzed, optimal TSB range: {result.get('optimal_tsb_range')}",
            }
        ],
    }
```

### 5. `get_efficiency_by_zone`

```python
def get_efficiency_by_zone(
    db: Session, 
    athlete_id: UUID, 
    effort_zone: str = "threshold",
    days: int = 90
) -> Dict[str, Any]:
    """
    Efficiency trend for specific effort zones (comparable runs only).
    """
    from services.correlation_engine import (
        aggregate_efficiency_by_effort_zone,
        aggregate_efficiency_trend,
    )
    
    now = datetime.utcnow()
    start = now - timedelta(days=days)
    days = max(30, min(int(days), 365))
    
    zone_data = aggregate_efficiency_by_effort_zone(
        str(athlete_id), start, now, db, effort_zone
    )
    trend_data = aggregate_efficiency_trend(
        str(athlete_id), start, now, db, effort_zone
    )
    
    # Calculate summary
    if zone_data:
        efficiencies = [e for d, e in zone_data]
        current = efficiencies[-1] if efficiencies else None
        best = min(efficiencies) if efficiencies else None
        avg = sum(efficiencies) / len(efficiencies) if efficiencies else None
    else:
        current = best = avg = None
    
    return {
        "ok": True,
        "tool": "get_efficiency_by_zone",
        "generated_at": _iso(now),
        "data": {
            "effort_zone": effort_zone,
            "window_days": days,
            "data_points": len(zone_data),
            "current_efficiency": round(current, 3) if current else None,
            "best_efficiency": round(best, 3) if best else None,
            "average_efficiency": round(avg, 3) if avg else None,
            "recent_trend_pct": round(trend_data[-1][1], 1) if trend_data else None,
            "note": "Lower Pace/HR = better efficiency (faster at same heart rate)",
        },
        "evidence": [
            {
                "type": "derived",
                "id": f"efficiency_zone:{athlete_id}:{effort_zone}",
                "date": date.today().isoformat(),
                "value": f"{effort_zone} zone: {len(zone_data)} runs, current {current:.3f}" if current else "No data",
            }
        ],
    }
```

---

## Implementation

### File to Modify

`apps/api/services/coach_tools.py`

### Steps

1. Add imports at top:
```python
from services.race_predictor import RacePredictor
from services.recovery_metrics import (
    calculate_recovery_half_life,
    calculate_durability_index,
    detect_false_fitness,
    detect_masked_fatigue,
)
from services.insight_aggregator import get_active_insights as fetch_insights
from services.correlation_engine import (
    aggregate_pre_pb_state,
    aggregate_efficiency_by_effort_zone,
    aggregate_efficiency_trend,
)
```

2. Add the 5 functions defined above

3. Verify each service function signature matches actual implementation

---

## Acceptance Criteria

### Must Pass

1. **Race predictions return data**
   ```python
   result = get_race_predictions(db, athlete_id)
   assert result["ok"] is True
   assert "5K" in result["data"]["predictions"]
   ```

2. **Recovery status returns metrics**
   ```python
   result = get_recovery_status(db, athlete_id)
   assert "recovery_half_life_days" in result["data"]
   ```

3. **Active insights returns list**
   ```python
   result = get_active_insights(db, athlete_id)
   assert "insights" in result["data"]
   ```

4. **PB patterns returns TSB range**
   ```python
   result = get_pb_patterns(db, athlete_id)
   assert result["data"]["pb_count"] >= 1  # Judge has 6 PBs
   assert result["data"]["optimal_tsb_range"] is not None
   ```

5. **Efficiency by zone returns effort-segmented data**
   ```python
   result = get_efficiency_by_zone(db, athlete_id, "threshold", 90)
   assert result["data"]["data_points"] > 0
   ```

### Domain Validation

6. **Judge's PB patterns match known data**
   - TSB max before PBs should be ~28 (Dec 13 10K PR)
   - PB count should be 6

7. **Efficiency zone shows improvement**
   - Recent trend should be negative (improvement)

---

## Testing Protocol

**Tester MUST:**
1. Run each function with Judge's athlete_id
2. Verify output structure matches spec
3. Cross-check numerical values against known data
4. If any function returns error/empty unexpectedly → FAIL and investigate

---

## Notes for Builder

1. **Verify function signatures** before implementing — read actual service files
2. **Handle exceptions gracefully** — return `{"ok": False, "error": ...}` on failure
3. `RacePredictor` may need athlete_id as UUID or string — check implementation
4. `insight_aggregator.get_active_insights` may have different parameter names — verify
5. Follow existing `coach_tools.py` patterns for consistency

---

## Rollback Plan

If issues arise:
1. Remove the 5 new functions
2. No database changes required
3. Coach falls back to existing 5 tools

---

## Dependencies

- ADR-045-A functions: `aggregate_pre_pb_state`, `aggregate_efficiency_by_effort_zone`, `aggregate_efficiency_trend`
- Existing services: `race_predictor.py`, `recovery_metrics.py`, `insight_aggregator.py`

---

**Awaiting Judge approval.**
