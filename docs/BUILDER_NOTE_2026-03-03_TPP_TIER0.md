# Builder Note — TPP (Tier 0) Effort Classification

**Date:** March 3, 2026
**Spec:** `docs/specs/EFFORT_CLASSIFICATION_SPEC.md` (Tier 0 addendum)
**Assigned to:** Builder
**Advisor sign-off required:** No — spec approved by founder + two advisors
**Urgency:** High — improves classification accuracy for all correlation
engine findings

---

## Before Your First Tool Call

Read in order:

1. `docs/FOUNDER_OPERATING_CONTRACT.md`
2. `docs/specs/EFFORT_CLASSIFICATION_SPEC.md` — read the FULL spec, not
   just the Tier 0 section. Understand Tiers 1–3 that already exist.
3. `apps/api/services/effort_classification.py` — the file you're extending
4. `apps/api/services/pace_normalization.py` — where GAP is computed
5. `apps/api/services/rpi_calculator.py` — where threshold pace comes from
6. This builder note

---

## Objective

Add Tier 0 (TPP — Threshold Pace Percentage) to the existing
`classify_effort()` function. When an athlete has an RPI and the
activity has split GAP data, classify effort by what they actually ran
relative to what they've proven they can sustain. When either is
missing, fall through to the existing tiers unchanged.

---

## Scope

### 1. Compute activity-level GAP

Add `compute_activity_gap(activity_id, db) -> Optional[float]` to
`services/effort_classification.py`.

- Query `ActivitySplit` records for the activity
- Filter to splits where `gap_seconds_per_mile` is not null
- Return the distance-weighted average of `gap_seconds_per_mile`
- Return None if no splits with GAP exist

### 2. Get threshold pace from RPI

- Read `athlete.rpi` from the database
- If RPI is null, Tier 0 cannot activate — return None
- If RPI exists, call `rpi_calculator.calculate_training_paces(rpi)`
  to get threshold pace in seconds per mile

### 3. Compute TPP

**The exact formula:**

```python
tpp = threshold_pace_sec_per_mile / activity_gap_sec_per_mile
```

Both values in seconds per mile. A faster activity (lower sec/mi)
produces a higher TPP.

**Examples to verify your implementation against:**
- Easy run: 10:00/mi (600s) with threshold 7:30/mi (450s) → 450/600 = 0.75 (easy)
- Tempo: 7:45/mi (465s) with threshold 7:30/mi (450s) → 450/465 = 0.97 (hard)
- Moderate: 8:30/mi (510s) with threshold 7:30/mi (450s) → 450/510 = 0.88 (moderate)

### 4. Classification thresholds

```python
if tpp >= 0.92:
    return "hard"
elif tpp >= 0.78:
    return "moderate"
else:
    return "easy"
```

### 5. Combined TPP + HR classification

When Tier 0 activates, ALSO compute the HR percentile classification
(existing Tier 1 logic). Then combine:

| TPP says | HR says | Final | Reason |
|----------|---------|-------|--------|
| hard | hard | hard | Agree |
| moderate | moderate | moderate | Agree |
| easy | easy | easy | Agree |
| moderate | hard | **hard** | Environmental stress degrading pace |
| easy | hard | **moderate** | Body under load at easy pace |
| hard | easy | **hard** | Pace anchors — HR cannot downgrade |
| hard | moderate | hard | Pace anchors |
| easy | moderate | easy | Minor elevation, not enough to override |
| moderate | easy | moderate | Pace anchors |

**Critical rule: HR can upgrade the classification. HR cannot downgrade
it.** If the athlete ran hard pace, the effort was hard regardless of
what HR did.

### 6. Disagreement logging

Log EVERY case where TPP and HR produce different classifications.
Not just large gaps — any mismatch.

Fields to log: `athlete_id`, `activity_id`, `date`,
`tpp_classification`, `hr_classification`, `tpp_value`, `activity_gap`,
`threshold_pace`, `avg_hr`.

Use the same logging mechanism as RPE disagreements (already
implemented).

### 7. Update `get_effort_thresholds()`

Add to the returned dict:
- `threshold_pace`: seconds/mile (from RPI), or None
- `five_k_pace`: seconds/mile (from RPI), or None
- Update `tier` to return `"tpp"` when Tier 0 is active

### 8. Update caching

The Redis cache `effort_thresholds:{athlete_id}` must now also
invalidate when `athlete.rpi` changes (not just when new activities
sync).

### 9. Wire into `classify_effort()`

The function now tries Tier 0 first:

```python
def classify_effort(activity, athlete_id, db):
    thresholds = get_effort_thresholds(athlete_id, db)

    # Tier 0: TPP (when RPI and split GAP available)
    if thresholds.get("threshold_pace"):
        activity_gap = compute_activity_gap(activity.id, db)
        if activity_gap and activity_gap > 0:
            tpp = thresholds["threshold_pace"] / activity_gap
            tpp_class = _classify_from_tpp(tpp)

            # Combined: also compute HR classification
            hr_class = _classify_from_hr_percentile(activity, thresholds)
            final = _combine_tpp_hr(tpp_class, hr_class)

            # Log disagreement if any
            if tpp_class != hr_class:
                _log_tpp_hr_disagreement(...)

            logger.debug(f"Tier 0 (TPP): tpp={tpp:.3f}, "
                         f"tpp_class={tpp_class}, hr_class={hr_class}, "
                         f"final={final}")
            return final

    # Tier 1, 2, 3: existing logic unchanged
    ...
```

**Do not modify the existing Tier 1/2/3 logic.** Tier 0 is added
above it. If Tier 0 can't activate, the function falls through to
what already works.

---

## Out of Scope

- Populating `Activity.avg_gap_min_per_mile` (deferred to FIT parsing)
- Learning personal zone boundaries from training patterns (future)
- Weather/environmental data integration (HR catches this via the
  combined classification)
- Any UI changes
- Any changes to Tiers 1, 2, or 3

---

## Implementation Contracts (non-negotiable)

1. **Output domain is `"hard" | "moderate" | "easy"`.** No new return
   values. Race-effort sessions classify as hard. Race detection is a
   separate concern via `workout_type`.

2. **HR cannot downgrade classification.** If TPP says hard and HR says
   easy, the result is hard. This is the core design principle.

3. **Tier 0 is additive, not replacement.** Existing tiers are
   untouched. Tier 0 sits above them. If it can't activate, the
   function falls through.

4. **All disagreements are logged.** Any TPP/HR mismatch, not just
   large gaps.

5. **The formula is `threshold / activity_gap`.** Verify with the
   examples in the spec. If your easy run comes out as hard, you
   inverted it.

6. **Scoped commits.** Tier 0 addition is one commit. Test updates
   are one commit.

---

## Files to Change

| File | Change |
|------|--------|
| `apps/api/services/effort_classification.py` | Add `compute_activity_gap()`, TPP classification, combined TPP+HR logic, disagreement logging, update `get_effort_thresholds()` |
| `apps/api/tests/test_effort_classification.py` | Add Tier 0 tests (see below) |
| `docs/SITE_AUDIT_LIVING.md` | Update post-deploy |

---

## Tests Required

### New tests for Tier 0

1. `compute_activity_gap` returns correct distance-weighted average
2. `compute_activity_gap` returns None when no splits have GAP
3. Tier 0 activates when athlete has RPI and activity has split GAP
4. Tier 0 falls through to Tier 1 when RPI is null
5. Tier 0 falls through to Tier 1 when no split GAP data
6. TPP 0.75 (easy run) → easy
7. TPP 0.88 (moderate) → moderate
8. TPP 0.97 (tempo) → hard
9. Combined: moderate TPP + hard HR → hard (environmental stress)
10. Combined: hard TPP + easy HR → hard (no downgrade)
11. Combined: easy TPP + hard HR → moderate
12. Disagreement logged when TPP and HR differ
13. Disagreement NOT logged when TPP and HR agree
14. Formula verification: 450/600 = 0.75, 450/465 = 0.97, 450/510 = 0.88

### Regression tests

15. All existing `test_effort_classification.py` tests still pass
16. All existing `test_progress_knowledge.py` pass (15 tests)
17. All existing `test_correlation_quality.py` pass (14 tests)

### Production smoke checks

```bash
# 1. Verify Tier 0 activates for founder
docker exec strideiq_api python -c "
from database import SessionLocal
from models import Athlete
from services.effort_classification import get_effort_thresholds
db = SessionLocal()
user = db.query(Athlete).filter(Athlete.email=='mbshaf@gmail.com').first()
print(f'RPI: {user.rpi}')
t = get_effort_thresholds(str(user.id), db)
print(f'Tier: {t[\"tier\"]}')
print(f'Threshold pace: {t.get(\"threshold_pace\")} sec/mi')
assert t['tier'] == 'tpp', f'FAIL: expected tpp, got {t[\"tier\"]}'
assert t.get('threshold_pace') is not None, 'FAIL: no threshold pace'
print('PASS: Tier 0 (TPP) active for founder')
db.close()
"

# 2. Classify a recent activity with Tier 0
docker exec strideiq_api python -c "
from database import SessionLocal
from models import Athlete, Activity
from services.effort_classification import classify_effort
db = SessionLocal()
user = db.query(Athlete).filter(Athlete.email=='mbshaf@gmail.com').first()
act = db.query(Activity).filter(
    Activity.athlete_id == user.id
).order_by(Activity.start_date.desc()).first()
result = classify_effort(act, str(user.id), db)
print(f'Activity: {act.name} ({act.start_date.date()})')
print(f'Classification: {result}')
print('PASS: Tier 0 classification succeeded')
db.close()
"

# 3. Verify formula direction (easy run should be easy)
docker exec strideiq_api python -c "
from database import SessionLocal
from models import Athlete, Activity
from services.effort_classification import classify_effort, compute_activity_gap, get_effort_thresholds
db = SessionLocal()
user = db.query(Athlete).filter(Athlete.email=='mbshaf@gmail.com').first()
t = get_effort_thresholds(str(user.id), db)
# Find an activity with low avg pace (easy run)
acts = db.query(Activity).filter(
    Activity.athlete_id == user.id,
    Activity.avg_speed_m_s.isnot(None),
).order_by(Activity.avg_speed_m_s.asc()).limit(3).all()
for a in acts:
    gap = compute_activity_gap(a.id, db)
    if gap:
        tpp = t['threshold_pace'] / gap
        cls = classify_effort(a, str(user.id), db)
        pace_min = gap / 60
        print(f'{a.name}: GAP {pace_min:.1f} min/mi, TPP {tpp:.3f}, class={cls}')
print('PASS: formula direction verified')
db.close()
"

# 4. All existing tests pass
docker exec strideiq_api python -m pytest tests/test_effort_classification.py -v
```

---

## Evidence Required in Handoff

1. **Commit hash(es)** — scoped commits
2. **Files changed table** — file + one-line description
3. **Test output** — full pytest output, 0 failures
4. **Production smoke check output** — all 4 checks above
5. **Founder's Tier 0 profile** — paste output of smoke check #1
   showing TPP is active with threshold pace
6. **Formula verification** — paste output of smoke check #3 showing
   easy runs classified as easy (not inverted)
7. **AC checklist** — AC11–AC20 marked with evidence

---

## Acceptance Criteria

From spec:

- [ ] AC11: Tier 0 activates when athlete has RPI and activity has split GAP data
- [ ] AC12: Tier 0 falls through to Tier 1 when RPI is null
- [ ] AC13: Tier 0 falls through to Tier 1 when activity has no split GAP data
- [ ] AC14: Activity-level GAP derived correctly from distance-weighted split averages
- [ ] AC15: TPP thresholds: < 0.78 → easy, 0.78–0.91 → moderate, >= 0.92 → hard
- [ ] AC16: Combined TPP+HR: HR upgrades effort when pace degraded (moderate TPP + hard HR → hard)
- [ ] AC17: HR does not downgrade classification (hard TPP + easy HR → still hard)
- [ ] AC18: All TPP-HR disagreements (any tier mismatch) logged for future correlation input
- [ ] AC19: Founder classified as Tier 0 (TPP) — has RPI and split GAP data
- [ ] AC20: All existing tests still pass after Tier 0 addition

---

## Known Limitation

Activity-level classification uses distance-weighted average TPP across
all splits. This is correct for simple sessions but loses structure in
mixed workouts — a 12-mile run with a 4-mile tempo finish classifies as
moderate when the tempo splits are the training stimulus that matters.
The correlation engine's aggregation functions should eventually operate
at the split level, pulling splits where TPP meets the threshold
regardless of parent activity. Activity-level classification becomes a
display label only. This is the follow-up that makes the correlation
engine genuinely accurate about structured sessions.

---

## Mandatory: Site Audit Update

After deploy, update `docs/SITE_AUDIT_LIVING.md`:

1. New entry under "Delta Since Last Audit"
2. Note: "Effort classification now uses Threshold Pace Percentage (TPP)
   as primary signal when RPI and split GAP data are available. HR serves
   as confirming signal — can upgrade classification when environmental
   conditions degrade pace, cannot downgrade. All TPP-HR disagreements
   logged for future correlation input."
3. Update `last_updated` date
