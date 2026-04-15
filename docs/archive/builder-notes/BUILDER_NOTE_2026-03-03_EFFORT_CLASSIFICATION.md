# Builder Note — N=1 Effort Classification

**Date:** March 3, 2026
**Spec:** `docs/specs/EFFORT_CLASSIFICATION_SPEC.md`
**Assigned to:** Backend Builder
**Advisor sign-off required:** No — spec approved by founder
**Urgency:** Critical — blocking Recovery Fingerprint, 6 of 9 correlation
sweep metrics, and degrading workout classification, TSS, and insights

---

## Before Your First Tool Call

Read in order:

1. `docs/FOUNDER_OPERATING_CONTRACT.md` — how you work (non-negotiable)
2. `docs/PRODUCT_MANIFESTO.md` — the soul
3. `docs/specs/EFFORT_CLASSIFICATION_SPEC.md` — the full architectural spec.
   Read every line. This is a precisely scoped design decision, not a vague ask.
4. `docs/BUILDER_NOTE_2026-03-03_CORRELATION_ENGINE_QUALITY.md` — context on
   what was just fixed (confounder control, direction safety gate)
5. This builder note

---

## Objective

Replace all `athlete.max_hr`-gated effort classification with a single
shared function (`classify_effort()`) that uses the athlete's own HR
percentile distribution. No athlete should need a profile field set before
the system works at full capability.

---

## Scope

### Phase 1: Core classification engine

1. **Create `apps/api/services/effort_classification.py`** with:
   - `classify_effort(activity, athlete_id, db) → "hard" | "moderate" | "easy"`
   - `get_effort_thresholds(athlete_id, db) → dict`
   - `classify_effort_bulk(activities, athlete_id, db) → Dict[UUID, str]`
   - `log_rpe_disagreement(athlete_id, activity_id, hr_tier, rpe_tier, db)`

2. **Tier 1 (primary) — HR Percentile Distribution:**
   - Query all activities with `avg_hr` for the athlete
   - Compute P80 and P40 from the distribution
   - `avg_hr >= P80` → hard, `P40–P79` → moderate, `< P40` → easy
   - This is the primary method and must work with zero profile fields set

3. **Tier 2 (secondary) — HRR with Observed Peak:**
   - Eligibility: 20+ activities with HR data AND 3+ classified as hard by Tier 1
   - `observed_peak_hr = MAX(Activity.max_hr)` from history
   - `resting_hr` from most recent GarminDay or DailyCheckin
   - `HRR = (avg_hr - resting_hr) / (observed_peak_hr - resting_hr)`
   - `HRR >= 0.75` → hard, `0.45–0.74` → moderate, `< 0.45` → easy
   - When both tiers are available, use Tier 1 as primary. Log agreement/disagreement.

4. **Tier 3 (tertiary) — Workout Type + RPE:**
   - When fewer than 10 activities have `avg_hr`
   - Race/interval/tempo/threshold → hard; easy/recovery → easy; RPE >= 7 → hard; RPE <= 4 → easy

5. **RPE Disagreement Logging:**
   - When Tier 1 and RPE disagree by more than one tier, log the event
   - Fields: `athlete_id`, `activity_id`, `date`, `hr_classification`, `rpe_value`, `rpe_classification`
   - Store in a new table `EffortDisagreement` or append to existing logging
   - Not blocking, not alerting — captured for future correlation input

6. **Redis caching:**
   - Key: `effort_thresholds:{athlete_id}`
   - Contains: `p80_hr`, `p40_hr`, `tier`, `observed_peak_hr`, `resting_hr`,
     `activity_count`, `hard_count`
   - Invalidate when new activities sync (add cache-bust in activity ingestion path)

### Phase 2: Migration of all max_hr consumers

Migrate each consumer in the order below. Each migration is mechanical:
replace the max_hr gate with a call to `classify_effort()` or
`get_effort_thresholds()`.

**Build order (dependency-safe):**

| Order | File | What to change |
|-------|------|----------------|
| 1 | `services/recovery_metrics.py` | Replace `HARD_SESSION_HR_THRESHOLD` and the `if not athlete.max_hr: return None` gate. Use `classify_effort_bulk()` to get hard/easy session lists. |
| 2 | `services/correlation_engine.py` | Replace max_hr gates in `aggregate_pace_at_effort()`, `aggregate_efficiency_by_effort_zone()`, `aggregate_race_pace()`. Use `get_effort_thresholds()` for HR boundaries. |
| 3 | `services/workout_classifier.py` | Replace `_calculate_hr_zone()` and `_calculate_intensity()` max_hr deps. Replace hard finish detection gate. Use `get_effort_thresholds()`. |
| 4 | `services/run_analysis_engine.py` | Replace HR-based classification and red flag detection max_hr deps. |
| 5 | `services/training_load.py` | Replace hrTSS max_hr gate. Use observed peak from `get_effort_thresholds()` when Tier 2 eligible, otherwise fall back to rTSS (already implemented). |
| 6 | `services/coach_tools.py` | Replace effort zone evidence and HR zones display max_hr deps. |
| 7 | `services/insight_aggregator.py` | Remove hardcoded `185` fallback. Use `get_effort_thresholds()`. |
| 8 | `services/activity_analysis.py` | Remove `220 - age` formula. Use `classify_effort()`. |

---

## Out of Scope

- Changing the `max_hr` field on the Athlete model (it stays, just stops being a gate)
- Any UI changes (the Progress page reads from existing APIs — fixing the
  backend fixes the page)
- Correlation engine confounder methodology changes (separate builder note, already shipped)
- Training plan or phase-related work

---

## Implementation Contracts (non-negotiable)

1. **One function, one place to improve.** All effort classification goes
   through `classify_effort()`. No service computes its own HR zones
   independently.

2. **"The statement is always true from the data that exists."** The
   percentile method makes no claim about a ceiling the data doesn't
   contain. This philosophy must be reflected in code comments on the
   core function.

3. **Never gate on a null profile field.** No code path may return None,
   empty list, or skip processing solely because `athlete.max_hr` is null.

4. **Never use population formulas.** No `220 - age`. No hardcoded `185`.
   No age-derived estimate. These are explicitly banned.

5. **Tier selection is logged.** Every call to `classify_effort()` records
   which tier was used. This is auditable.

6. **Existing tests must pass.** If an existing test asserts behavior that
   depends on max_hr, update the test to use the new classification —
   don't delete the test.

7. **Scoped commits.** Phase 1 (core engine + tests) is one commit. Each
   migration file is its own commit or grouped logically (max 3 files per
   commit).

---

## Files to Change

| File | Change |
|------|--------|
| `apps/api/services/effort_classification.py` | **New** — core classification engine |
| `apps/api/services/recovery_metrics.py` | Remove max_hr gate, use classify_effort_bulk() |
| `apps/api/services/correlation_engine.py` | Remove max_hr gates in 3 aggregate functions |
| `apps/api/services/workout_classifier.py` | Replace HR zone + intensity calculations |
| `apps/api/services/run_analysis_engine.py` | Replace HR-based classification |
| `apps/api/services/training_load.py` | Replace hrTSS max_hr gate |
| `apps/api/services/coach_tools.py` | Replace effort zone evidence + HR zones display |
| `apps/api/services/insight_aggregator.py` | Remove hardcoded 185 fallback |
| `apps/api/services/activity_analysis.py` | Remove 220-age formula |
| `apps/api/tests/test_effort_classification.py` | **New** — tests for all tiers, eligibility, RPE disagreement |
| `docs/SITE_AUDIT_LIVING.md` | Update post-deploy |

---

## Tests Required

### Unit tests (`test_effort_classification.py`)

1. Tier 1: classify_effort returns "hard" for activity at P85
2. Tier 1: classify_effort returns "moderate" for activity at P60
3. Tier 1: classify_effort returns "easy" for activity at P20
4. Tier 1: works with zero `athlete.max_hr` set
5. Tier 2: not activated with fewer than 20 activities
6. Tier 2: not activated without 3 hard sessions
7. Tier 2: activated and returns correct classification when eligible
8. Tier 3: workout_type "race" → hard when HR data sparse
9. Tier 3: RPE >= 7 → hard when HR data sparse
10. Tier 3: returns "moderate" for ambiguous signals
11. RPE disagreement: logged when gap > 1 tier
12. RPE disagreement: not logged when gap <= 1 tier
13. classify_effort_bulk: returns dict mapping activity IDs to classifications
14. get_effort_thresholds: returns correct structure with all fields
15. get_effort_thresholds: cached result matches fresh computation

### Integration tests

16. Recovery Fingerprint returns real data for athlete with no max_hr but 50+ activities
17. Correlation engine `aggregate_pace_at_effort()` returns non-empty for athlete with no max_hr
18. Correlation engine `aggregate_efficiency_by_effort_zone()` returns non-empty for athlete with no max_hr

### Regression tests

19. All existing `test_progress_knowledge.py` pass (15 tests)
20. All existing `test_progress_narrative.py` pass (14 tests)
21. All existing `test_correlation_quality.py` pass (14 tests)

### Production smoke checks

```bash
# 1. Verify effort_classification module loads
docker exec strideiq_api python -c "
from services.effort_classification import classify_effort, get_effort_thresholds
print('PASS: module imports')
"

# 2. Compute thresholds for founder (no max_hr set)
docker exec strideiq_api python -c "
from database import SessionLocal
from models import Athlete
from services.effort_classification import get_effort_thresholds
db = SessionLocal()
user = db.query(Athlete).filter(Athlete.email=='mbshaf@gmail.com').first()
print(f'max_hr on profile: {user.max_hr}')
t = get_effort_thresholds(str(user.id), db)
print(f'Tier: {t[\"tier\"]}')
print(f'P80 HR: {t[\"p80_hr\"]}')
print(f'P40 HR: {t[\"p40_hr\"]}')
print(f'Activities with HR: {t[\"activity_count\"]}')
print(f'Hard sessions: {t[\"hard_count\"]}')
assert t['tier'] in ('percentile', 'hrr', 'workout_type'), 'FAIL: invalid tier'
assert t['p80_hr'] is not None, 'FAIL: no P80 computed'
print('PASS: thresholds computed for athlete with no max_hr')
db.close()
"

# 3. Verify Recovery Fingerprint now returns data
docker exec strideiq_api python -c "
from database import SessionLocal
from models import Athlete
from services.recovery_metrics import compute_recovery_curve
db = SessionLocal()
user = db.query(Athlete).filter(Athlete.email=='mbshaf@gmail.com').first()
result = compute_recovery_curve(user, db)
assert result is not None, 'FAIL: Recovery curve still returns None'
print(f'Before curve points: {len(result.get(\"before\", []))}')
print(f'Now curve points: {len(result.get(\"now\", []))}')
print('PASS: Recovery Fingerprint produces data')
db.close()
"

# 4. Verify correlation sweep metrics produce output
docker exec strideiq_api python -c "
from database import SessionLocal
from services.correlation_engine import analyze_correlations
from models import Athlete
db = SessionLocal()
user = db.query(Athlete).filter(Athlete.email=='mbshaf@gmail.com').first()
metrics = ['efficiency', 'pace_easy', 'pace_threshold', 'pace_race',
           'completion', 'distance_weekly', 'ctl_delta',
           'efficiency_by_zone', 'race_pace']
empty = []
for m in metrics:
    try:
        r = analyze_correlations(str(user.id), days=90, db=db, output_metric=m)
        if not r.get('correlations'):
            empty.append(m)
    except Exception as e:
        empty.append(f'{m} (error: {e})')
if empty:
    print(f'WARNING: empty metrics: {empty}')
else:
    print('PASS: all 9 metrics produce output')
db.close()
"

# 5. Verify no hardcoded max_hr values remain
docker exec strideiq_api bash -c "
grep -rn '220.*age\|220 -\|hardcoded.*185\|= 185' /app/services/ || echo 'PASS: no population formulas found'
"

# 6. Progress page shows Recovery Fingerprint
TOKEN=$(...generate token...)
curl -s -H "Authorization: Bearer $TOKEN" \
  https://strideiq.run/v1/progress/knowledge | python3 -c "
import sys, json
d = json.load(sys.stdin)
rc = d.get('recovery_curve')
if rc:
    print(f'Recovery curve: {len(rc.get(\"before\",[]))} before pts, {len(rc.get(\"now\",[]))} now pts')
    print('PASS: Recovery Fingerprint on Progress page')
else:
    print('FAIL: no recovery_curve in response')
"
```

---

## Evidence Required in Handoff

1. **Commit hash(es)** — scoped commits only
2. **Files changed table** — file + one-line description
3. **Test output** — full pytest output for `test_effort_classification.py`,
   `test_progress_knowledge.py`, `test_progress_narrative.py`,
   `test_correlation_quality.py` — 0 failures
4. **Production smoke check output** — paste results of all 6 checks above
5. **Before/after table** showing:
   - Recovery Fingerprint: None → real data
   - Correlation sweep: X of 9 metrics empty → 0 of 9 empty
   - hrTSS: skipped → computed (or explain why still falling back)
6. **Founder's effort thresholds** — paste the output of smoke check #2
7. **Proof that no population formulas remain** — paste output of smoke check #5
8. **AC checklist** from spec — every criterion marked with evidence

---

## Acceptance Criteria

From `docs/specs/EFFORT_CLASSIFICATION_SPEC.md`:

- [ ] AC1: `classify_effort()` returns valid classification for athletes with no `max_hr` set
- [ ] AC2: Recovery Fingerprint renders real data for the founder
- [ ] AC3: All 9 correlation sweep metrics produce non-empty output for the founder
- [ ] AC4: No code path uses `220 - age` or hardcoded `185`
- [ ] AC5: No code path returns None/empty solely because `athlete.max_hr` is null
- [ ] AC6: Percentile thresholds are cached and recalculated on new activity
- [ ] AC7: Tier selection is logged (which tier was used for each classification)
- [ ] AC8: All existing tests pass (with updated expectations where needed)
- [ ] AC9: New tests cover all three tiers and the eligibility gate for Tier 2
- [ ] AC10: RPE disagreement events (>1 tier gap) are logged for future correlation input

---

## Mandatory: Site Audit Update

After deploy, update `docs/SITE_AUDIT_LIVING.md`:

1. New entry under "Delta Since Last Audit"
2. Note: "Replaced all max_hr-gated effort classification with N=1
   percentile-based system. Recovery Fingerprint, correlation sweep,
   workout classification, hrTSS, and insight generation now work for
   athletes with no max_hr set."
3. Update tool/service inventory to reflect new `effort_classification.py`
4. Update `last_updated` date
