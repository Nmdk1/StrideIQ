# Tester Handoff: ADR-045 Complete Correlation Wiring

**Date:** 2026-01-19  
**From:** Builder  
**To:** Tester  
**ADR:** `docs/adr/ADR-045-complete-correlation-wiring.md`  
**Status:** VERIFIED COMPLETE (2026-01-19)

---

## What Was Implemented

### New Inputs (8 DailyCheckin fields)
- stress_1_5
- soreness_1_5
- rpe_1_10
- enjoyment_1_5
- confidence_1_5
- motivation_1_5
- overnight_avg_hr
- hrv_sdnn

### Training Load Inputs
- tsb
- ctl
- atl

### New Output Aggregators
- `aggregate_pace_at_effort(..., effort_level="easy"|"threshold")`
- `aggregate_workout_completion(..., window_days=7)`

### Updated Function
- `analyze_correlations(..., include_training_load=True, output_metric="efficiency")`

---

## Files Changed

- `apps/api/services/correlation_engine.py`

---

## Acceptance Criteria to Verify

### Must Pass

1. **All DailyCheckin fields queryable as correlates**
   ```bash
   docker-compose exec -T api python -c "
   from datetime import datetime, timedelta
   from core.database import SessionLocal
   from services.correlation_engine import aggregate_daily_inputs
   from models import Athlete
   
   db = SessionLocal()
   athlete = db.query(Athlete).filter(Athlete.email == 'mbshaf@gmail.com').first()
   
   inputs = aggregate_daily_inputs(
       str(athlete.id),
       datetime.now() - timedelta(days=30),
       datetime.now(),
       db
   )
   
   expected = ['stress_1_5', 'soreness_1_5', 'rpe_1_10', 'enjoyment_1_5', 
               'confidence_1_5', 'motivation_1_5', 'overnight_avg_hr', 'hrv_sdnn']
   
   for field in expected:
       assert field in inputs, f'Missing: {field}'
   print('PASS: All DailyCheckin fields present')
   "
   ```

2. **TSB/CTL/ATL available as inputs**
   ```bash
   docker-compose exec -T api python -c "
   from datetime import datetime, timedelta
   from core.database import SessionLocal
   from services.correlation_engine import aggregate_training_load_inputs
   from models import Athlete
   
   db = SessionLocal()
   athlete = db.query(Athlete).filter(Athlete.email == 'mbshaf@gmail.com').first()
   
   inputs = aggregate_training_load_inputs(
       str(athlete.id),
       datetime.now() - timedelta(days=30),
       datetime.now(),
       db
   )
   
   assert 'tsb' in inputs, 'Missing: tsb'
   assert 'ctl' in inputs, 'Missing: ctl'
   assert 'atl' in inputs, 'Missing: atl'
   print(f'PASS: TSB/CTL/ATL present (tsb has {len(inputs[\"tsb\"])} points)')
   "
   ```

3. **Pace at effort calculable**
   ```bash
   docker-compose exec -T api python -c "
   from datetime import datetime, timedelta
   from core.database import SessionLocal
   from services.correlation_engine import aggregate_pace_at_effort
   from models import Athlete
   
   db = SessionLocal()
   athlete = db.query(Athlete).filter(Athlete.email == 'mbshaf@gmail.com').first()
   
   outputs = aggregate_pace_at_effort(
       str(athlete.id),
       datetime.now() - timedelta(days=90),
       datetime.now(),
       db,
       'easy'
   )
   
   assert isinstance(outputs, list), 'Should return list'
   print(f'PASS: pace_at_effort returns {len(outputs)} data points')
   "
   ```

4. **Workout completion rate calculable**
   ```bash
   docker-compose exec -T api python -c "
   from datetime import datetime, timedelta
   from core.database import SessionLocal
   from services.correlation_engine import aggregate_workout_completion
   from models import Athlete
   
   db = SessionLocal()
   athlete = db.query(Athlete).filter(Athlete.email == 'mbshaf@gmail.com').first()
   
   outputs = aggregate_workout_completion(
       str(athlete.id),
       datetime.now() - timedelta(days=30),
       datetime.now(),
       db
   )
   
   assert isinstance(outputs, list), 'Should return list'
   print(f'PASS: workout_completion returns {len(outputs)} data points')
   "
   ```

5. **Correlations run without error**
   ```bash
   docker-compose exec -T api python -c "
   from datetime import datetime, timedelta
   from core.database import SessionLocal
   from services.correlation_engine import analyze_correlations
   from models import Athlete
   
   db = SessionLocal()
   athlete = db.query(Athlete).filter(Athlete.email == 'mbshaf@gmail.com').first()
   
   result = analyze_correlations(
       str(athlete.id),
       days=30,
       db=db,
       include_training_load=True,
       output_metric='efficiency'
   )
   
   assert result.get('ok') is True, f'Failed: {result}'
   print('PASS: analyze_correlations runs successfully')
   print(f'Correlations found: {len(result.get(\"correlations\", []))}')
   "
   ```

### Should Pass

6. **New inputs appear in correlation results** (if data exists)
7. **Multiple output metrics work** (test with output_metric="pace_easy")

---

## Test Commands

```bash
# Run correlation engine tests
docker-compose exec -T api pytest tests/test_correlation_engine.py -v

# Run full test suite
docker-compose exec -T api pytest tests/ -q --tb=short
```

---

## Known Deviations (Approved)

1. Training load history handled both dict and list return types
2. Default days kept at 90 (existing) instead of 30 (ADR)
3. recovery_speed and decoupling_pct NOT implemented (ADR lacked specs)

---

## Report Format

After testing, report:
1. Pass/Fail for each acceptance criterion
2. Any new issues discovered
3. Test output excerpts

---

---

## Test Results (2026-01-19)

| AC | Criterion | Result | Evidence |
|----|-----------|--------|----------|
| 1 | DailyCheckin fields | ✅ PASS | All 8 fields present |
| 2 | TSB/CTL/ATL inputs | ✅ PASS | 91 data points each |
| 3 | Pace at effort | ✅ PASS | Returns list (0 = no easy-HR runs in range) |
| 4 | Workout completion | ✅ PASS | 8 data points |
| 5 | Correlations run | ✅ PASS | Valid structure returned |

**Verdict: ALL ACCEPTANCE CRITERIA PASS**

### Notes
- No correlations returned because athlete has 0 DailyCheckin logs (expected)
- 66 activities, 91 TSB/CTL/ATL points correctly aggregated
- PowerShell quoting issue in docs (non-blocking, documentation fix only)
