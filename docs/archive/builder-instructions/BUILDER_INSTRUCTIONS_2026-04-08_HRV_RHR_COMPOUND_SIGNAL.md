# Builder Instructions: HRV/RHR Compound Recovery Signal

**Date:** 2026-04-08
**Priority:** Quick win — estimated 1 session
**Status:** Ready to build

## Hypothesis

HRV and resting HR individually correlate with next-day running
efficiency. The compound signal HRV ÷ RHR may have stronger predictive
power than either alone because it captures parasympathetic recovery
(HRV) normalized against cardiovascular demand (RHR) in a single number.

## What to Build

### 1. Derive compound signal in correlation engine input builder

**File:** `apps/api/services/correlation_engine.py`

After the `_GARMIN_SIGNALS` loop (line ~766, after `inputs[input_key] = series`),
derive the compound signal from the already-loaded `_gd_rows`:

```python
# HRV/RHR compound recovery signal
hrv_rhr_series = []
for row in _gd_rows:
    hrv = getattr(row, "hrv_5min_high", None)
    rhr = getattr(row, "min_hr", None)
    if hrv is not None and rhr is not None and rhr > 0:
        hrv_rhr_series.append((row.calendar_date, float(hrv) / float(rhr)))
inputs["hrv_rhr_ratio"] = hrv_rhr_series
```

This produces a dimensionless ratio. Typical range: 0.5–2.0+. Higher =
better recovery state.

### 2. Add expected direction

In `_EXPECTED_DIRECTIONS` dict, add:

```python
("hrv_rhr_ratio", "efficiency"): "positive",
("hrv_rhr_ratio", "pace_easy"): "positive",
```

Higher ratio = better recovery = better efficiency. Same polarity as HRV.

### 3. Add friendly name

In `services/n1_insight_generator.py` → `friendly_signal_name()` mapping,
add:

```python
"hrv_rhr_ratio": "recovery ratio (HRV÷RHR)",
```

In `services/fingerprint_context.py` → `COACHING_LANGUAGE` dict, add:

```python
"hrv_rhr_ratio": "recovery ratio",
```

In `services/fingerprint_context.py` → `SIGNAL_UNITS` dict, add:

```python
"hrv_rhr_ratio": "",
```

### 4. Do NOT suppress from athlete surfaces

This is a novel, potentially interesting signal. Do not add it to
`_SUPPRESSED_SIGNALS` or `_ENVIRONMENT_SIGNALS`. If it correlates, we
want athletes to see it.

### 5. No migration needed

This is a derived signal computed at correlation time, not stored on any
model. No schema change, no backfill.

## Verification

After deployment, wait for the next nightly correlation sweep (08:00 UTC)
or manually trigger for the founder:

```python
from services.correlation_engine import analyze_correlations
from core.database import SessionLocal
db = SessionLocal()
result = analyze_correlations(athlete_id="<founder_id>", days=90, db=db)
hrv_rhr = [c for c in result.get("correlations", []) if c["input_name"] == "hrv_rhr_ratio"]
print(hrv_rhr)
db.close()
```

If the compound signal appears with a stronger correlation coefficient
than `garmin_hrv_5min_high` alone, the hypothesis is confirmed.

## What NOT to Build

- No new UI element for this signal. It flows through the existing
  correlation pipeline and surfaces naturally through the Manual,
  briefing, and coach if it proves significant.
- No new API endpoint.
- No new model column.

## Acceptance Criteria

- [ ] `hrv_rhr_ratio` appears in `analyze_correlations` output
- [ ] Friendly name renders correctly ("recovery ratio (HRV÷RHR)")
- [ ] Direction is marked positive for efficiency
- [ ] Signal is NOT in the suppression set
- [ ] CI green
