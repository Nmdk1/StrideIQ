# Builder Note — Correlation Engine Quality Fix

**Date:** March 3, 2026
**Priority:** Critical — the correlation engine is the heartbeat of this product
**Status:** Phase 1 delivered — correction required (see Post-Delivery Correction)

---

## Before Your First Tool Call

Read these in order:

1. `docs/FOUNDER_OPERATING_CONTRACT.md` — how you work (non-negotiable)
2. `docs/PRODUCT_MANIFESTO.md` — the soul
3. `_AI_CONTEXT_/RESEARCH/05_CORRELATION_METHODOLOGY.md` — confounder mapping and stratified methodology (already specced, never implemented)
4. This builder note — scope, contracts, tests

---

## The Problem

The correlation engine surfaces misleading findings and displays them
on the Progress page as confirmed facts. The page currently shows:

- "High motivation reduces efficiency within 3 days" — STRONG 9x
- "High TSB reduces efficiency within 5 days" — CONFIRMED 4x

Both are **technically true but useless.** The causal chain is:

```
high motivation → hard workout → training load spike → recovery days → efficiency drops
```

The engine sees the first and last links and calls it a direct relationship.
Training load (ATL) is the hidden third variable that causes both. The
engine has zero confounder awareness.

**The founder's words:** "This may be true but also is useless. Are the
deload days following high motivation days trending higher? That would
be an insight — not this."

---

## What Exists But Isn't Used

| Asset | Location | What it contains |
|-------|----------|-----------------|
| Confounder mapping | `_AI_CONTEXT_/RESEARCH/05_CORRELATION_METHODOLOGY.md` lines 192-203 | Table of apparent relationships and their likely confounders |
| Stratified correlation spec | Same file, lines 205-234 | `stratified_correlation()` design |
| Granger causality | `services/causal_attribution.py` lines 339-398 | `granger_causality_test()` — implemented, not wired into engine |

None of this is wired into `correlation_engine.py`. The engine runs
bivariate Pearson with no controls and calls the result a finding.

---

## Architecture

### Current flow (broken)

```
aggregate_daily_inputs() → input time series
aggregate_*_outputs()    → output time series
                              ↓
find_time_shifted_correlations(input, output)
    → bivariate Pearson at lags 0-7
    → filter |r| >= 0.3, p < 0.05
                              ↓
persist_correlation_findings()
    → upsert CorrelationFinding
    → times_confirmed += 1
```

No confounder control. No direction validation. No trend analysis.

### Target flow (Phase 1)

```
aggregate_daily_inputs() → input time series
aggregate_*_outputs()    → output time series
aggregate_training_load_inputs() → confounder time series
                              ↓
find_time_shifted_correlations(input, output)
    → bivariate Pearson at lags 0-7
    → filter |r| >= 0.3, p < 0.05
                              ↓
NEW: compute_partial_correlation(input, output, confounder, lag)
    → partial out confounder variance
    → if partial_r drops below threshold → flag as confounded
                              ↓
NEW: validate_direction(input_name, output_metric, observed_direction)
    → check against DIRECTION_EXPECTATIONS table
    → flag counterintuitive findings
                              ↓
persist_correlation_findings()
    → upsert with new fields (partial_r, confounder_variable, etc.)
    → confounded findings: is_active = False
    → counterintuitive findings: flagged, not surfaced
```

---

## Scope

### Phase 1 — Stop surfacing misleading findings

#### 1. Partial Correlation Function

Add to `services/correlation_engine.py`:

```python
def compute_partial_correlation(
    input_data: List[Tuple[date, float]],
    output_data: List[Tuple[date, float]],
    control_data: List[Tuple[date, float]],
    lag_days: int = 0
) -> Optional[float]:
    """
    Compute partial correlation r_xy.z

    r_xy.z = (r_xy - r_xz * r_yz) / sqrt((1 - r_xz²)(1 - r_yz²))

    Returns None if any component correlation cannot be computed
    (insufficient aligned data).
    """
```

This is the standard partial correlation formula. One function, ~30 lines.

#### 2. Confounder Map

A lookup table defining which variable to partial out for each
input→output pair. Based on the research doc + founder diagnosis:

```python
CONFOUNDER_MAP: Dict[Tuple[str, str], str] = {
    # (input_name, output_metric): confounder_variable
    #
    # Motivation/enjoyment/confidence → efficiency:
    #   confounder is ATL (hard workout days have high motivation AND
    #   high efficiency, followed by recovery dips)
    ("motivation_1_5", "efficiency"): "atl",
    ("enjoyment_1_5", "efficiency"): "atl",
    ("confidence_1_5", "efficiency"): "atl",
    ("motivation_1_5", "pace_easy"): "atl",
    ("motivation_1_5", "pace_threshold"): "atl",

    # TSB → efficiency:
    #   TSB is derived from ATL/CTL. High TSB = rested = better efficiency
    #   is expected but the engine finds negative because low TSB days
    #   (hard training) produce high same-day efficiency, and high TSB
    #   days (recovery) produce low efficiency. ATL is the confounder.
    ("tsb", "efficiency"): "atl",
    ("tsb", "pace_easy"): "atl",
    ("tsb", "pace_threshold"): "atl",

    # Sleep → pace:
    #   Taper produces both more sleep AND faster race pace.
    #   CTL change rate is a proxy for taper phase.
    ("sleep_hours", "pace_easy"): "ctl",
    ("sleep_hours", "pace_threshold"): "ctl",

    # Soreness → efficiency:
    #   High soreness follows hard workouts (ATL spike), and the
    #   efficiency on sore days is naturally lower.
    ("soreness_1_5", "efficiency"): "atl",
    ("rpe_1_10", "efficiency"): "atl",
}
```

**Rule:** If a (input, output) pair is in the confounder map, the engine
MUST compute the partial correlation. If the partial r drops below
`MIN_CORRELATION_STRENGTH` (0.3), the finding is flagged as confounded
and `is_active` is set to `False`.

**If a pair is NOT in the map,** bivariate correlation is used as-is.
The map grows over time as new confounders are identified.

#### 3. Direction Expectations Table

A lookup defining what physiological direction is expected for each pair:

```python
DIRECTION_EXPECTATIONS: Dict[Tuple[str, str], str] = {
    # (input_name, output_metric): expected_direction
    ("motivation_1_5", "efficiency"): "positive",
    ("motivation_1_5", "completion"): "positive",
    ("sleep_hours", "efficiency"): "positive",
    ("sleep_hours", "pace_easy"): "positive",
    ("hrv_rmssd", "efficiency"): "positive",
    ("stress_1_5", "efficiency"): "negative",
    ("stress_1_5", "completion"): "negative",
    ("soreness_1_5", "efficiency"): "negative",
    ("soreness_1_5", "pace_easy"): "negative",
    ("tsb", "efficiency"): "positive",   # fresh = better
    ("tsb", "pace_easy"): "positive",
    ("tsb", "pace_threshold"): "positive",
    ("rpe_1_10", "efficiency"): "negative",
}
```

**Rule (UPDATED — see Post-Delivery Correction):** If observed direction
contradicts expected direction, the finding is flagged as
`direction_counterintuitive = True` AND `is_active = False`. This is a
safety gate to protect athlete trust. Counterintuitive findings are
suppressed regardless of partial correlation result until confounder
methodology is corrected (ATL → daily TSS).

#### 4. New Model Fields

Add to `CorrelationFinding` in `models.py`:

```python
# --- Confounder control (Phase 1) ---
partial_correlation_coefficient = Column(Float, nullable=True)
confounder_variable = Column(Text, nullable=True)
is_confounded = Column(Boolean, default=False, nullable=False)
direction_expected = Column(Text, nullable=True)       # "positive" or "negative"
direction_counterintuitive = Column(Boolean, default=False, nullable=False)
```

New Alembic migration: `correlation_quality_001`

#### 5. Wiring

In `analyze_correlations()`, after computing bivariate r for each
input×output pair:

1. Look up `(input_name, output_metric)` in `CONFOUNDER_MAP`
2. If found, get the confounder time series from `inputs` dict
3. Call `compute_partial_correlation(input_data, output_data, confounder_data, lag)`
4. If `partial_r` is None or `abs(partial_r) < MIN_CORRELATION_STRENGTH`:
   mark as confounded
5. Look up `(input_name, output_metric)` in `DIRECTION_EXPECTATIONS`
6. If found and observed direction != expected: mark as counterintuitive
7. Pass all flags through to `persist_correlation_findings()`

In `persist_correlation_findings()`:

1. Save new fields on upsert
2. If `is_confounded = True`: set `is_active = False`
3. **If `direction_counterintuitive = True`: set `is_active = False`**
   (UPDATED — see Post-Delivery Correction. This is a safety gate.
   Counterintuitive findings are suppressed regardless of partial r
   until confounder methodology is corrected.)

#### 6. Re-run Existing Findings

After deploying, trigger a correlation re-analysis for the founder account
to update existing findings with the new quality gates. The two problematic
findings ("motivation reduces efficiency", "TSB reduces efficiency") should
become `is_active = False` after partial correlation with ATL.

---

### Phase 2 — Trend-within-pattern detection (separate builder note)

Not in scope for this build. Defined here for context only.

The founder's actual vision: "After high-motivation hard efforts, your
recovery-day efficiency used to drop to 0.018. Over the last 6 weeks,
those same recovery dips only drop to 0.021. Your floor is rising."

This requires:
1. For each confirmed correlation, collect all instances where the pattern
   occurred (each time the input was "high" and the output changed at lag)
2. Record the output value at the lag point for each instance
3. Fit a linear trend across those output values over time
4. Add `trend_direction` ("rising", "stable", "declining") to the finding
5. Surface the trend as the insight, not the raw correlation

**A separate builder note must be written before this work begins.**

---

## Files to Change

| File | Change |
|------|--------|
| `apps/api/services/correlation_engine.py` | Add `compute_partial_correlation()`, `CONFOUNDER_MAP`, `DIRECTION_EXPECTATIONS`, wire into `analyze_correlations()` |
| `apps/api/services/correlation_persistence.py` | Update `persist_correlation_findings()` to handle new fields, suppress confounded findings |
| `apps/api/models.py` | Add 5 new fields to `CorrelationFinding` |
| `apps/api/alembic/versions/correlation_quality_001_*.py` | Migration for new fields |
| `apps/api/tests/test_correlation_quality.py` | **New** — tests for partial correlation, confounder map, direction validation |
| `docs/SITE_AUDIT_LIVING.md` | Update post-deploy |

---

## Build Contracts (non-negotiable)

1. **Partial correlation is a filter, not a replacement.** The bivariate
   `correlation_coefficient` is still stored. `partial_correlation_coefficient`
   is stored alongside it. Surfacing decisions use partial r when available.

2. **The confounder map is explicit and auditable.** No automatic confounder
   detection. The map is a Python dict. Adding a new confounder pair requires
   a code change and a test.

3. **Confounded findings are deactivated, not deleted.** `is_active = False`
   and `is_confounded = True`. They can be reviewed and the map adjusted.

4. **Direction expectations are now a safety gate (UPDATED).** A
   counterintuitive direction DOES suppress the finding (`is_active = False`).
   This was changed from "advisory only" after Phase 1 delivery revealed
   that ATL is too coarse a confounder for acute-stress relationships
   (see Post-Delivery Correction). This gate will be relaxed only after
   the confounder map is corrected to use daily session stress instead
   of rolling ATL.

5. **No changes to the Progress page.** The page reads `is_active = True`
   findings. Fixing the engine fixes the page automatically.

6. **Re-analysis required post-deploy.** The builder must trigger a
   correlation re-analysis for the founder account and verify the two
   problematic findings are now `is_active = False`.

---

## Required Tests

1. `compute_partial_correlation` returns correct r_xy.z for known data
2. `compute_partial_correlation` returns None when control data has insufficient overlap
3. Confounder map: (motivation_1_5, efficiency) → atl
4. Confounder map: (sleep_hours, efficiency) → not in map (no confounder)
5. Direction expectations: (motivation_1_5, efficiency) → "positive"
6. Direction expectations: (stress_1_5, completion) → "negative"
7. Finding with |partial_r| < 0.3 after confounder control → is_confounded = True, is_active = False
8. Finding with |partial_r| >= 0.3 after confounder control → is_confounded = False, is_active = True
9. Counterintuitive direction → is_active = False (regardless of confounder result)
10. ~~Counterintuitive direction + NOT confounded → is_active = True~~ REMOVED — see Post-Delivery Correction
11. Finding NOT in confounder map → uses bivariate r, no partial_r stored
12. Existing finding updated with new fields on re-run (upsert preserves times_confirmed)
13. `get_surfaceable_findings()` excludes confounded findings
14. No regressions: existing `test_progress_knowledge.py` still passes

---

## Production Smoke Checks (post-deploy)

```bash
# 1. Migration applied — new columns exist
docker exec strideiq_api python -c "
from database import SessionLocal
from models import CorrelationFinding
db = SessionLocal()
f = db.query(CorrelationFinding).first()
if f:
    print(f'partial_r: {f.partial_correlation_coefficient}')
    print(f'confounder: {f.confounder_variable}')
    print(f'confounded: {f.is_confounded}')
    print(f'dir_expected: {f.direction_expected}')
    print(f'dir_counter: {f.direction_counterintuitive}')
print('PASS: columns exist')
db.close()
"

# 2. Re-run correlation analysis for founder
docker exec strideiq_api python -c "
from database import SessionLocal
from services.correlation_engine import analyze_correlations
db = SessionLocal()
from models import Athlete
user = db.query(Athlete).filter(Athlete.email=='mbshaf@gmail.com').first()
result = analyze_correlations(str(user.id), days=90, db=db, output_metric='efficiency')
print(f'Correlations: {len(result.get(\"correlations\", []))}')
db.close()
"

# 3. Verify problematic findings are now inactive
docker exec strideiq_api python -c "
from database import SessionLocal
from models import CorrelationFinding, Athlete
db = SessionLocal()
user = db.query(Athlete).filter(Athlete.email=='mbshaf@gmail.com').first()
problems = db.query(CorrelationFinding).filter(
    CorrelationFinding.athlete_id == user.id,
    CorrelationFinding.input_name.in_(['motivation_1_5', 'tsb']),
    CorrelationFinding.output_metric == 'efficiency',
).all()
for f in problems:
    print(f'{f.input_name} → {f.output_metric}: active={f.is_active}, confounded={f.is_confounded}, counterintuitive={f.direction_counterintuitive}, partial_r={f.partial_correlation_coefficient}')
    assert not f.is_active, f'FAIL: {f.input_name} still active despite being counterintuitive'
    assert f.direction_counterintuitive, f'FAIL: {f.input_name} not flagged as counterintuitive'
print('PASS: problematic findings suppressed')
db.close()
"

# 4. Progress page now shows only valid findings
TOKEN=$(...generate token...)
curl -s -H "Authorization: Bearer $TOKEN" \
  https://strideiq.run/v1/progress/knowledge | python3 -c "
import sys, json
d = json.load(sys.stdin)
edges = d['correlation_web']['edges']
for e in edges:
    print(f'{e[\"source\"]} → {e[\"target\"]}: r={e[\"r\"]}, confirmed={e[\"times_confirmed\"]}')
facts = d['proved_facts']
for f in facts:
    print(f'{f[\"headline\"]}: {f[\"confidence_tier\"]}')
print(f'Edges: {len(edges)}, Facts: {len(facts)}')
print('PASS: only valid findings displayed')
"
```

---

## Evidence Required in Handoff

1. **Commit hash(es)** — scoped commits only
2. **Files changed table** — file + one-line description
3. **Test output** — full pytest output, 0 failures, including new + existing tests
4. **Production smoke check output** — paste results of all 4 checks above
5. **Before/after table** for the flagged findings showing all fields:
   - bivariate r, partial r, direction_expected, direction_counterintuitive, is_active
6. **Proof that direction-counterintuitive findings no longer surface on Progress page**
   (curl output or screenshot showing the Correlation Web without the bad edges)
7. **Confirmation that suppression is documented as a safety gate** — the builder
   note's Post-Delivery Correction section must be referenced, not just the code
8. **AC checklist** — every test requirement marked with evidence

---

## Post-Delivery Correction (March 3, 2026)

### What happened

Phase 1 was delivered correctly. Partial correlation with ATL as the
confounder was implemented. But the two problematic findings survived:

| Finding | Bivariate r | Partial r (controlling ATL) | Outcome |
|---------|-------------|---------------------------|---------|
| motivation_1_5 → efficiency (lag 3d) | negative | -0.5679 | Survived — still above 0.3 |
| tsb → efficiency (lag 5d) | negative | -0.3462 | Survived — still above 0.3 |

Both remained `is_active = True` because the original contract said
"direction_counterintuitive alone doesn't suppress."

### Why ATL is the wrong confounder for these pairs

ATL is a 7-day exponentially weighted moving average. It captures
cumulative load, not the acute stress of a specific workout. The causal
chain is:

```
high motivation → hard workout on THAT DAY → acute session stress
    → recovery 3 days later → efficiency dip
```

ATL barely moves from a single hard session because it's a rolling
average. The actual confounder is the **daily session stress** (daily
TSS, or distance × intensity for that specific day). ATL smooths over
the spike that causes the recovery dip.

TSB as an input is worse — TSB = CTL - ATL. Partialing out ATL from a
TSB-derived metric is mathematically circular.

### Corrections applied

1. **Suppression rule changed:** `direction_counterintuitive = True` now
   sets `is_active = False` regardless of partial r. This is a temporary
   safety gate to protect athlete trust while the confounder methodology
   is corrected.

2. **Confounder map to be refined:** For acute-stress relationships
   (motivation, enjoyment, confidence, soreness, RPE → efficiency/pace),
   the confounder should be **daily session stress** (daily TSS or daily
   distance × avg HR), not rolling ATL. This requires:
   - A new aggregation function: `aggregate_daily_session_stress()`
   - Updated CONFOUNDER_MAP entries for acute-stress pairs
   - Re-computation of partial correlations with the corrected confounder
   - If findings now drop below threshold with the right confounder,
     the direction-only safety gate can be relaxed for those pairs

3. **TSB pairs:** Do not use ATL as confounder for TSB→anything. TSB is
   derived from ATL/CTL. Either use a non-derived confounder or accept
   that TSB correlations require a different methodology (e.g., stratified
   analysis by training phase).

### When to relax the safety gate

The `direction_counterintuitive → is_active = False` rule should be
relaxed ONLY when:
1. Daily session stress is implemented as a confounder
2. The problematic findings are re-tested with the corrected confounder
3. If they drop below threshold with the correct confounder, the gate
   was correctly protecting the athlete
4. If they survive even with daily TSS, the relationship is genuinely
   counterintuitive and requires physiological interpretation before
   surfacing

---

## Mandatory: Site Audit Update

After deploy, update `docs/SITE_AUDIT_LIVING.md`:
- New entry under "Delta Since Last Audit"
- Note: "Correlation engine now applies partial correlation for confounder
  control and direction validation. Misleading findings suppressed."
- Document new model fields
- Update `last_updated` date
