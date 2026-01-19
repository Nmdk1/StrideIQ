# Tester Handoff: ADR-049 Activity-Linked Nutrition Correlation

**Date:** 2026-01-19  
**ADR:** ADR-049  
**Status:** Ready for Verification

---

## Objective

Verify that `get_nutrition_correlations()` returns activity-linked nutrition correlations with interpretations.

---

## Acceptance Criteria

| AC | Description |
|----|-------------|
| AC1 | Tool count = 11 |
| AC2 | Function returns all 3 expected keys |
| AC3 | Each key has `sample_size` field |
| AC4 | Insufficient data returns `note` field |
| AC5 | Tool registered in AI Coach |

---

## Test Commands

### AC1: Tool count

```powershell
docker-compose exec -T api python -c "from services.ai_coach import AICoach; from database import SessionLocal; db=SessionLocal(); c=AICoach(db); tools=c._assistant_tools(); print(f'Tool count: {len(tools)}'); assert len(tools)==11, f'Expected 11, got {len(tools)}'; print('PASS AC1')"
```

### AC2 & AC3: Expected keys and sample_size

```powershell
docker-compose exec -T api python -c "
from services.coach_tools import get_nutrition_correlations
from database import SessionLocal
from models import Athlete

db = SessionLocal()
athlete = db.query(Athlete).first()
if not athlete:
    print('SKIP: No athlete')
    exit(0)

result = get_nutrition_correlations(db, athlete.id)
print(f'ok: {result.get(\"ok\")}')

data = result.get('data', {})
expected_keys = ['pre_carbs_vs_efficiency', 'pre_protein_vs_efficiency', 'post_protein_vs_next_efficiency']

for key in expected_keys:
    assert key in data, f'FAIL AC2: Missing key {key}'
print('PASS AC2: All 3 keys present')

for key in expected_keys:
    assert 'sample_size' in data[key], f'FAIL AC3: {key} missing sample_size'
print('PASS AC3: All keys have sample_size')

db.close()
"
```

### AC4: Insufficient data handling

```powershell
docker-compose exec -T api python -c "
from services.coach_tools import get_nutrition_correlations
from database import SessionLocal
from models import Athlete

db = SessionLocal()
athlete = db.query(Athlete).first()
if not athlete:
    print('SKIP: No athlete')
    exit(0)

result = get_nutrition_correlations(db, athlete.id)
data = result.get('data', {})

# Check for graceful handling
for key, val in data.items():
    if val.get('sample_size', 0) < 5:
        assert val.get('note') == 'insufficient data', f'FAIL AC4: {key} should have note for small sample'
        print(f'{key}: sample_size={val.get(\"sample_size\")}, note present')
    else:
        assert 'correlation' in val, f'FAIL AC4: {key} should have correlation'
        assert 'interpretation' in val, f'FAIL AC4: {key} should have interpretation'
        print(f'{key}: sample_size={val.get(\"sample_size\")}, correlation={val.get(\"correlation\")}')

print('PASS AC4: Graceful handling verified')
db.close()
"
```

### AC5: Tool in AI Coach dispatch

```powershell
docker-compose exec -T api python -c "
from services.ai_coach import AICoach
from database import SessionLocal

db = SessionLocal()
c = AICoach(db)
tools = c._assistant_tools()
tool_names = [t['function']['name'] for t in tools]

assert 'get_nutrition_correlations' in tool_names, 'FAIL AC5: Tool not registered'
print('PASS AC5: Tool registered in AI Coach')
print(f'All tools: {tool_names}')
db.close()
"
```

---

## Expected Output

For athlete WITHOUT activity-linked nutrition:
```
pre_carbs_vs_efficiency: sample_size=0, note present
pre_protein_vs_efficiency: sample_size=0, note present
post_protein_vs_next_efficiency: sample_size=0, note present
```

For athlete WITH activity-linked nutrition (5+ entries):
```
pre_carbs_vs_efficiency: sample_size=X, correlation=-0.XXX
pre_protein_vs_efficiency: sample_size=X, correlation=-0.XXX
post_protein_vs_next_efficiency: sample_size=X, correlation=-0.XXX
```

---

## CRITICAL: Domain Validation

If athlete has nutrition data linked to activities:
- Verify `sample_size` matches actual count of linked entries
- Verify `correlation` is a valid number between -1 and 1
- Verify `interpretation` makes sense for the correlation value

---

## Report Format

```
## ADR-049 Tester Verification

AC1: PASS/FAIL (tool count: X)
AC2: PASS/FAIL (keys present: yes/no)
AC3: PASS/FAIL (sample_size fields: yes/no)
AC4: PASS/FAIL (graceful handling: yes/no)
AC5: PASS/FAIL (tool registered: yes/no)

Data returned:
- pre_carbs_vs_efficiency: sample_size=X, correlation=X
- pre_protein_vs_efficiency: sample_size=X, correlation=X
- post_protein_vs_next_efficiency: sample_size=X, correlation=X

Overall: VERIFIED COMPLETE / FAILED
```

---

**Ready for Tester verification.**
