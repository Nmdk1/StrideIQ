# Builder Handoff: ADR-045 Complete Correlation Wiring

**Date:** 2026-01-19  
**From:** Planner (Opus 4.5)  
**To:** Builder  
**ADR:** `docs/adr/ADR-045-complete-correlation-wiring.md`  
**Status:** Approved by Judge

---

## Task Summary

Expand the correlation engine to include all DailyCheckin fields, TSB/CTL/ATL metrics, and new performance outputs.

---

## File to Modify

**Primary file:** `apps/api/services/correlation_engine.py`

---

## Implementation Steps

### Step 1: Add New Imports (if needed)

At the top of the file, ensure these imports exist:

```python
from models import DailyCheckin, Activity, PlannedWorkout, TrainingPlan, Athlete
from uuid import UUID
```

### Step 2: Expand `aggregate_daily_inputs` Function

Locate the `aggregate_daily_inputs` function (around line 145).

**Add the following code blocks** after the existing input queries (after the `bmi` query, around line 275):

Copy the code from ADR-045 Section "Implementation → 1. Expand `aggregate_daily_inputs` function"

This adds:
- stress_1_5
- soreness_1_5
- rpe_1_10
- enjoyment_1_5
- confidence_1_5
- motivation_1_5
- overnight_avg_hr
- hrv_sdnn

### Step 3: Add `aggregate_training_load_inputs` Function

Add this **new function** after `aggregate_daily_inputs`:

Copy the code from ADR-045 Section "Implementation → 2. Add TSB/CTL/ATL as inputs"

### Step 4: Add `aggregate_pace_at_effort` Function

Add this **new function** after the previous one:

Copy the code from ADR-045 Section "Implementation → 3. Add new output: `aggregate_pace_at_effort`"

### Step 5: Add `aggregate_workout_completion` Function

Add this **new function** after the previous one:

Copy the code from ADR-045 Section "Implementation → 4. Add new output: `aggregate_workout_completion`"

### Step 6: Update `analyze_correlations` Function

Modify the `analyze_correlations` function signature and body:

1. Add new parameters:
   - `include_training_load: bool = True`
   - `output_metric: str = "efficiency"`

2. After getting standard inputs, merge training load inputs
3. Add output metric selection logic

See ADR-045 Section "Implementation → 5. Update `analyze_correlations`"

---

## Testing Commands

After implementation, run:

```bash
# From project root
docker-compose exec -T api pytest tests/test_correlation_engine.py -v

# Run all tests to ensure no regressions
docker-compose exec -T api pytest tests/ -q --tb=short
```

---

## Verification Checklist

Before handoff to Tester, verify:

- [ ] No syntax errors (file loads without error)
- [ ] `aggregate_daily_inputs` returns dict with new keys
- [ ] `aggregate_training_load_inputs` function exists and is callable
- [ ] `aggregate_pace_at_effort` function exists and is callable
- [ ] `aggregate_workout_completion` function exists and is callable
- [ ] `analyze_correlations` accepts new parameters
- [ ] Existing tests still pass

---

## Common Pitfalls

1. **Missing imports** — Ensure `UUID`, `TrainingPlan`, `Athlete` are imported
2. **Indentation** — Match existing code style (4 spaces)
3. **None handling** — All queries filter out None values
4. **Type conversion** — Use `float()` for numeric values
5. **Date handling** — Be careful with date vs datetime

---

## Do NOT

- Change existing function signatures (only add optional parameters)
- Modify database schema
- Touch other files unless necessary for imports
- Add new dependencies

---

## Questions?

If requirements are unclear, document what you tried and hand back to Judge for Planner clarification.

---

## After Completion

1. Document what was implemented
2. Note any deviations from ADR
3. List files changed
4. Hand off to Tester with instructions

---

**Begin implementation.**
