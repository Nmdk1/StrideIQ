# Tester Handoff: ADR-047 Coach Architecture Refactor

**Date:** 2026-01-19  
**From:** Builder  
**To:** Tester  
**ADR:** `docs/adr/ADR-047-coach-architecture-refactor.md`  
**Status:** VERIFIED COMPLETE (2026-01-19)

---

## What Was Implemented

1. **5 new tools registered** in OpenAI Assistant (total now 10)
2. **Tool dispatch** for all 5 new tools
3. **2-tier model selection**: gpt-3.5-turbo (simple) / gpt-4o-mini (standard)
4. **Dynamic model selection** per query with logging

---

## Builder Verification Output (Already Passing)

```
Total tools: 10
  - get_recent_runs
  - get_efficiency_trend
  - get_plan_week
  - get_training_load
  - get_correlations
  - get_race_predictions
  - get_recovery_status
  - get_active_insights
  - get_pb_patterns
  - get_efficiency_by_zone

Classification tests:
  PASS What is my TSB? -> simple
  PASS Analyze my training -> standard
  PASS Show my race predictions -> simple
  PASS Why am I tired? -> standard
```

---

## Tester MUST Verify

### AC1: Tool Count = 10
```bash
docker-compose exec -T api python -c "from services.ai_coach import AICoach; from core.database import SessionLocal; db = SessionLocal(); coach = AICoach(db); tools = coach._assistant_tools(); print(f'Total tools: {len(tools)}'); assert len(tools) == 10, f'Expected 10, got {len(tools)}'; print('AC1 PASS')"
```

### AC2: New Tools Present
```bash
docker-compose exec -T api python -c "from services.ai_coach import AICoach; from core.database import SessionLocal; db = SessionLocal(); coach = AICoach(db); tools = coach._assistant_tools(); names = [t['function']['name'] for t in tools]; required = ['get_race_predictions', 'get_recovery_status', 'get_active_insights', 'get_pb_patterns', 'get_efficiency_by_zone']; missing = [r for r in required if r not in names]; assert not missing, f'Missing: {missing}'; print('AC2 PASS: All 5 new tools registered')"
```

### AC3: Simple Query Classification
```bash
docker-compose exec -T api python -c "from services.ai_coach import AICoach; from core.database import SessionLocal; db = SessionLocal(); coach = AICoach(db); result = coach.classify_query('What is my TSB?'); assert result == 'simple', f'Expected simple, got {result}'; print('AC3 PASS: Simple query classified correctly')"
```

### AC4: Standard Query Classification
```bash
docker-compose exec -T api python -c "from services.ai_coach import AICoach; from core.database import SessionLocal; db = SessionLocal(); coach = AICoach(db); result = coach.classify_query('Analyze my training'); assert result == 'standard', f'Expected standard, got {result}'; print('AC4 PASS: Standard query classified correctly')"
```

### AC5: Model Selection
```bash
docker-compose exec -T api python -c "from services.ai_coach import AICoach; from core.database import SessionLocal; db = SessionLocal(); coach = AICoach(db); simple_model = coach.get_model_for_query('simple'); standard_model = coach.get_model_for_query('standard'); assert simple_model == 'gpt-3.5-turbo', f'Simple should be gpt-3.5-turbo, got {simple_model}'; assert standard_model == 'gpt-4o-mini', f'Standard should be gpt-4o-mini, got {standard_model}'; print(f'AC5 PASS: simple={simple_model}, standard={standard_model}')"
```

---

## Report Format

```
AC1: PASS/FAIL (tool count)
AC2: PASS/FAIL (new tools present)
AC3: PASS/FAIL (simple classification)
AC4: PASS/FAIL (standard classification)
AC5: PASS/FAIL (model selection)

Overall: VERIFIED COMPLETE / FAILED (with explanation)
```

---

## Notes

- Live Coach testing (actual OpenAI calls) can be done manually if needed
- Model selection logging will appear in container logs during real usage
- No database changes to verify

---

**Begin verification.**
