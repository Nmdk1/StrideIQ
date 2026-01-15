# ADR-023: Individual Performance Model Validation

**Status:** ACCEPTED  
**Date:** 2026-01-15  
**Author:** AI Assistant  
**Reviewers:** Michael Shaffer

---

## Context

ADR-022 introduced the Individual Performance Model (IPM) for personalized plan generation. Before enabling for beta/elite users, we must validate that:

1. Model calibration produces reasonable τ1/τ2 values
2. Race time predictions are accurate (within acceptable MAE)
3. Model handles edge cases (injury recovery, age 50+, sparse data)

The N=1 philosophy demands validation against real athlete data, not population averages.

## Decision

**Validate offline using:**
1. Developer's historical data from Strava sync (N=1 ground truth)
2. Figshare anonymized running datasets as N=1 proxies (each "athlete" tested individually)

**Methodology:**
- Train on first 80% of each athlete's history
- Predict held-out 20% (race times, TSB at race day)
- Quantify accuracy: MAE/RMSE on race times
- Surface per-athlete insights, not population averages

## Alternatives Considered

| Alternative | Rejected Because |
|-------------|------------------|
| Synthetic data only | Doesn't validate real-world edge cases |
| Live A/B testing first | Risk of inaccurate predictions to users |
| Population average comparison | Violates N=1 philosophy |

## Trade-offs

| Trade-off | Decision |
|-----------|----------|
| Offline vs live | Offline first—safe, can iterate |
| Full dataset vs sample | Sample 3-5 figshare proxies—sufficient for edge cases |
| Strict vs lenient pass criteria | MAE <5% of race time → pass |

## Implementation

### Validation Script

`apps/api/scripts/validate_performance_model.py`

1. Load developer's data from dev DB
2. Load figshare sample CSVs (simulated or downloaded)
3. For each athlete:
   - Split 80/20 train/test
   - Calibrate model on train set
   - Predict race times on test set
   - Calculate MAE, RMSE, % error
   - Compare predicted vs actual TSB on race days
4. Output validation report (JSON + console)
5. Log audit trail (timestamp, athlete_id, metrics)

### Metrics

| Metric | Formula | Pass Threshold |
|--------|---------|----------------|
| MAE (race time) | mean(abs(predicted - actual)) | <5% of race time |
| RMSE (race time) | sqrt(mean((predicted - actual)^2)) | <7% of race time |
| TSB accuracy | mean(abs(predicted_tsb - actual_tsb)) | <10 points |

### Data Sources

| Source | Type | Notes |
|--------|------|-------|
| Dev DB | Strava sync | Developer's real data |
| Figshare sample 1 | CSV | Age 30-40, regular training |
| Figshare sample 2 | CSV | Age 50+, masters runner |
| Figshare sample 3 | CSV | Injury recovery pattern |
| Figshare sample 4 | CSV | Sparse data (<90 days) |
| Figshare sample 5 | CSV | High volume marathoner |

### Output

```json
{
  "validation_timestamp": "2026-01-15T10:30:00Z",
  "athletes_tested": 6,
  "results": [
    {
      "athlete_id": "dev_user",
      "n_training_days": 365,
      "n_races_train": 4,
      "n_races_test": 1,
      "calibrated_tau1": 38.2,
      "calibrated_tau2": 6.8,
      "model_confidence": "high",
      "race_predictions": [
        {
          "race_date": "2025-11-15",
          "distance": "half_marathon",
          "predicted_seconds": 5280,
          "actual_seconds": 5320,
          "error_seconds": -40,
          "error_percent": -0.75
        }
      ],
      "mae_seconds": 40,
      "mae_percent": 0.75,
      "pass": true,
      "notes": ["τ1=38 indicates faster adaptation than population default"]
    }
  ],
  "summary": {
    "passed": 5,
    "failed": 1,
    "overall_mae_percent": 2.3,
    "recommendation": "Model ready for beta rollout"
  }
}
```

## Security

- No user data exposure—run locally against dev DB
- Figshare data is anonymized public research data
- Audit log stored locally, not transmitted

## Test Plan

### Unit Tests
- Metric calculation (MAE, RMSE)
- Data loading from CSV
- Train/test split logic

### Integration Tests
- Full validation pipeline on mock data
- Report generation

## Success Criteria

1. Developer's data passes (<5% MAE)
2. At least 4/5 figshare proxies pass
3. Edge cases (age 50+, sparse) produce appropriate low-confidence flags

---

*ADR-023: Individual Performance Model Validation*
