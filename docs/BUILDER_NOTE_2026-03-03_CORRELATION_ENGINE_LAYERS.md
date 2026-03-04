# Builder Note — Correlation Engine Layers 1–4

**Date:** March 3, 2026
**Spec:** `docs/specs/CORRELATION_ENGINE_LAYERS_1_4_SPEC.md`
**Assigned to:** Backend Builder
**Advisor sign-off required:** No — spec approved by founder
**Urgency:** High — this is the moat. Everything downstream (Pre-Race
Fingerprint, Proactive Coach, Personal Operating Manual) depends on
these layers producing actionable findings.

---

## Before Your First Tool Call

Read in order:

1. `docs/FOUNDER_OPERATING_CONTRACT.md` — how you work (non-negotiable)
2. `docs/PRODUCT_MANIFESTO.md` — the soul
3. `docs/specs/CORRELATION_ENGINE_LAYERS_1_4_SPEC.md` — the full
   architectural spec. Read every line. Methods, thresholds, output
   schemas, known limitations, acceptance criteria — it's all there.
4. `docs/specs/CORRELATION_ENGINE_ROADMAP.md` — where these layers
   sit in the broader vision
5. This builder note

---

## Objective

Every confirmed correlation finding (times_confirmed >= 3) gains four
dimensions of specificity: where the effect starts (threshold), which
direction matters more (asymmetry), how long it lasts (decay), and what
it works through (cascade). The daily sweep runs all four analyses on
confirmed findings and persists the results.

---

## Scope

### In scope

- **Layer 1: Threshold Detection** — `detect_threshold()` function,
  6 new columns on `CorrelationFinding`
- **Layer 2: Asymmetric Response Detection** — `detect_asymmetry()`
  function, 5 new columns on `CorrelationFinding`
- **Layer 4: Lagged Decay Curves** — `compute_decay_curve()` function,
  3 new columns on `CorrelationFinding`
- **Layer 3: Cascade Detection** — `detect_mediators()` function, new
  `CorrelationMediator` table
- **Alembic migration** for all new columns + new table
- **Daily sweep integration** — second pass on confirmed findings
- **Tests** for all four layer functions + integration

### Out of scope

- Frontend changes (Progress page will consume these fields in a
  separate build)
- Narration / insight text generation from layer outputs
- Any changes to the existing correlation engine logic (Pearson,
  confounder control, direction validation — all untouched)
- Population-level comparisons

---

## Build Order

Build and test in this order. Each layer is independently shippable.

1. **Layers 1 + 2 together** — threshold + asymmetry. Highest immediate
   value, trivially cheap to compute, both add columns to the same
   table. One commit.
2. **Layer 4** — decay curves. Leverages data already computed in the
   sweep, simple curve classification. Second commit.
3. **Layer 3** — cascade detection. Most complex, requires new
   `CorrelationMediator` table, but produces the most profound insight
   type. Third commit.

---

## Implementation Notes

### Files to create

| File | Purpose |
|------|---------|
| `apps/api/services/correlation_layers.py` | All four detection functions: `detect_threshold()`, `detect_asymmetry()`, `compute_decay_curve()`, `detect_mediators()` |
| `apps/api/tests/test_correlation_layers.py` | Tests for all four functions with synthetic data |

### Files to modify

| File | Change |
|------|--------|
| `apps/api/models.py` | Add 14 columns to `CorrelationFinding`, add `CorrelationMediator` model |
| `apps/api/services/correlation_engine.py` | Wire second pass into daily sweep after findings are persisted |
| `alembic/versions/xxx_correlation_layers.py` | Migration for new columns + table |

### Key contracts

1. **Never modify existing correlation engine logic.** The bivariate
   Pearson, confounder control, direction validation, and persistence
   logic are untouched. The four layers run AFTER findings are persisted,
   as a second pass on confirmed findings only.

2. **Confirmed-only gate.** Layers run only on findings where
   `is_active == True` AND `times_confirmed >= 3`. Never on first-time
   or unconfirmed findings.

3. **Fire-and-forget.** Layer analysis failures must never break the
   correlation sweep. Wrap each layer call in try/except, log warnings
   on failure, continue. The sweep must always complete.

4. **All new columns are nullable.** A finding without threshold/
   asymmetry/decay/mediator data is valid — it means the analysis
   didn't find a pattern or hasn't run yet.

5. **`compute_partial_correlation()` already exists** in
   `correlation_engine.py` and is in production. Use it for cascade
   detection. Do not reimplement.

### Statistical thresholds (from spec)

| Parameter | Value | Used in |
|-----------|-------|---------|
| Min segment size | 5 data points | Threshold (each side of split) |
| Min r difference | 0.2 | Threshold (between segments) |
| Min segment r | 0.3 | Threshold (at least one side) |
| Asymmetry p threshold | 0.1 | Asymmetry (t-test between groups) |
| Mediation ratio cutoff | 0.4 | Cascade (B explains >40% of A→C) |
| Full mediation threshold | 0.3 | Cascade (partial_r drops below) |
| Sustained decay lags | 4+ | Decay (significant across 4+ lags) |

---

## Tests Required

### Unit tests (per layer)

**Layer 1 — Threshold:**
- Linear synthetic data → returns None (no threshold)
- Step-function data with known breakpoint → returns correct threshold
- Insufficient data on one side of split → returns None
- Verify min segment size enforced (n >= 5)

**Layer 2 — Asymmetry:**
- Symmetric data → ratio ~1.0, direction "symmetric"
- Asymmetric data (negative dominant) → ratio > 2.0
- Asymmetric data (positive dominant) → ratio < 0.67
- Insufficient data → returns None

**Layer 4 — Decay:**
- Monotonically decaying profile → type "exponential", correct half-life
- Sustained profile (4+ significant lags) → type "sustained"
- Non-monotonic profile → type "complex"
- Single-lag finding → lag_profile with only one significant entry

**Layer 3 — Cascade:**
- Known mediator (A→B→C) → detects B, correct mediation ratio
- Full mediation (partial_r < 0.3) → is_full_mediation = True
- No mediator candidates → returns empty list
- Variable that correlates with A but not C → not returned as mediator

### Integration tests

- Full daily sweep with synthetic athlete data produces threshold,
  asymmetry, decay, and mediator results on confirmed findings
- Unconfirmed findings (times_confirmed < 3) are skipped
- Layer failures don't break the sweep
- Migration applies cleanly and rolls back cleanly

### Production smoke checks

```bash
# After deploy — verify migration applied
docker exec strideiq_api python -c "
from models import CorrelationFinding
print([c.name for c in CorrelationFinding.__table__.columns if 'threshold' in c.name or 'asymmetry' in c.name or 'decay' in c.name or 'lag_profile' in c.name])
"

# Verify mediator table exists
docker exec strideiq_api python -c "
from models import CorrelationMediator
print('CorrelationMediator table:', CorrelationMediator.__tablename__)
"

# Run sweep for founder and check layer results
docker exec strideiq_api python -c "
from database import SessionLocal
from models import CorrelationFinding
db = SessionLocal()
findings = db.query(CorrelationFinding).filter(
    CorrelationFinding.times_confirmed >= 3,
    CorrelationFinding.is_active == True,
).all()
for f in findings:
    print(f'{f.input_name} → {f.output_metric}: threshold={f.threshold_value}, asymmetry={f.asymmetry_ratio}, decay_type={f.decay_type}')
db.close()
"
```

---

## Evidence Required in Handoff

1. Scoped file list changed (no `git add -A`)
2. Test output — verbatim paste of all layer tests passing
3. Migration output — applied cleanly on dev
4. Production smoke check output — founder's confirmed findings show
   layer data after a full sweep
5. Any findings where layers detected something interesting — paste
   the actual threshold values, asymmetry ratios, decay types found
   in the founder's data

---

## Acceptance Criteria

From the spec (23 total — see `docs/specs/CORRELATION_ENGINE_LAYERS_1_4_SPEC.md`
for the complete list):

- AC1–5: Threshold detection (correct identification, None for linear,
  segment size enforced, stored on finding, confirmed-only)
- AC6–9: Asymmetry detection (correct ratio, symmetric case handled,
  stored on finding, median baseline)
- AC10–13: Cascade detection (mediator identified, full mediation
  detected, stored in new table, candidate filtering)
- AC14–18: Decay curves (correct profile, half-life, sustained type,
  complex type, JSONB storage)
- AC19–23: Integration (daily sweep wiring, confirmed-only gate, all
  existing tests pass, founder's data populated, migration complete)

---

## Mandatory: Site Audit Update

`docs/SITE_AUDIT_LIVING.md` must be updated in the same session.

Required update block in the delivery pack:

1. Exact section(s) updated in `docs/SITE_AUDIT_LIVING.md`
2. What changed in product truth (not plan text)
3. Any inventory count/surface/tool updates

No task is complete until this is done.
