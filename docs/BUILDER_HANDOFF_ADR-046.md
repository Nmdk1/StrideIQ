# Builder Handoff: ADR-046 Expose Hidden Analytics

**Date:** 2026-01-19  
**From:** Planner  
**To:** Builder  
**ADR:** `docs/adr/ADR-046-expose-hidden-analytics.md`  
**Status:** Approved

---

## Task Summary

Add 5 new tools to `coach_tools.py` that expose existing analytical services.

---

## File to Modify

`apps/api/services/coach_tools.py`

---

## CRITICAL: Verify Function Signatures First

Before implementing, read the actual service files to verify function signatures match. The ADR contains pseudocode that may not match reality.

```bash
# Check each service's actual function signatures
docker-compose exec -T api python -c "
from services.race_predictor import RacePredictor
from services.recovery_metrics import calculate_recovery_half_life, calculate_durability_index, detect_false_fitness, detect_masked_fatigue
from services.insight_aggregator import get_active_insights
from services.correlation_engine import aggregate_pre_pb_state, aggregate_efficiency_by_effort_zone, aggregate_efficiency_trend
import inspect

print('=== RacePredictor.predict ===')
print(inspect.signature(RacePredictor.predict) if hasattr(RacePredictor, 'predict') else 'No predict method')

print('=== calculate_recovery_half_life ===')
print(inspect.signature(calculate_recovery_half_life))

print('=== get_active_insights ===')
print(inspect.signature(get_active_insights))

print('=== aggregate_pre_pb_state ===')
print(inspect.signature(aggregate_pre_pb_state))
"
```

---

## Implementation Steps

### Step 1: Add Imports

Add at top of `coach_tools.py` after existing imports:

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

### Step 2: Add 5 Functions

Add at end of file. See ADR-046 for full function code:
1. `get_race_predictions`
2. `get_recovery_status`
3. `get_active_insights`
4. `get_pb_patterns`
5. `get_efficiency_by_zone`

### Step 3: Handle Exceptions

Each function must handle exceptions gracefully:
```python
try:
    # service call
except Exception as e:
    return {"ok": False, "tool": "tool_name", "error": str(e)}
```

---

## Verification Commands

After implementation:

```bash
# Test each function
docker-compose exec -T api python -c "
from core.database import SessionLocal
from models import Athlete
from services.coach_tools import get_race_predictions, get_recovery_status, get_active_insights, get_pb_patterns, get_efficiency_by_zone

db = SessionLocal()
athlete = db.query(Athlete).filter(Athlete.email == 'mbshaf@gmail.com').first()

print('=== get_race_predictions ===')
r = get_race_predictions(db, athlete.id)
print('ok:', r.get('ok'))
print('predictions:', list(r.get('data', {}).get('predictions', {}).keys()))

print()
print('=== get_recovery_status ===')
r = get_recovery_status(db, athlete.id)
print('ok:', r.get('ok'))
print('data keys:', list(r.get('data', {}).keys()))

print()
print('=== get_active_insights ===')
r = get_active_insights(db, athlete.id)
print('ok:', r.get('ok'))
print('insight_count:', r.get('data', {}).get('insight_count'))

print()
print('=== get_pb_patterns ===')
r = get_pb_patterns(db, athlete.id)
print('ok:', r.get('ok'))
print('pb_count:', r.get('data', {}).get('pb_count'))
print('optimal_tsb_range:', r.get('data', {}).get('optimal_tsb_range'))

print()
print('=== get_efficiency_by_zone ===')
r = get_efficiency_by_zone(db, athlete.id, 'threshold', 90)
print('ok:', r.get('ok'))
print('data_points:', r.get('data', {}).get('data_points'))
print('current_efficiency:', r.get('data', {}).get('current_efficiency'))
"
```

---

## Expected Results

| Tool | Expected |
|------|----------|
| get_race_predictions | ok=True, predictions for 4 distances |
| get_recovery_status | ok=True, 4 metric keys |
| get_active_insights | ok=True, insights list |
| get_pb_patterns | ok=True, pb_count=6, optimal_tsb_range present |
| get_efficiency_by_zone | ok=True, data_points > 0 |

---

## Do NOT

- Modify existing functions
- Change function signatures of existing tools
- Add database schema changes
- Skip signature verification step

---

## When Done

Report:
1. Functions added
2. Verification output
3. Any deviations from ADR

---

**Begin implementation.**
