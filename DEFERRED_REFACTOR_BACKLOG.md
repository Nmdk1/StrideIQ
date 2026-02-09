# Deferred Refactors & Archived Features

This document tracks features and code that have been deferred or archived for future consideration.

---

## Critical Speed + D' Model

| Field | Value |
|-------|-------|
| **Feature** | Critical Speed + D' Predictor |
| **Status** | Archived |
| **Date Archived** | 2026-01-14 |
| **Branch** | `archive/cs-model-2026-01` |
| **ADR** | ADR-011, ADR-017 |

### Description

A race time predictor using the Critical Speed (CS) and D' (D-prime) model — a hyperbolic power-duration curve fitted to the athlete's personal best data.

### Why Archived

1. **Redundancy**: Training Pace Calculator (RPI-based) already predicts race times more simply and accurately
2. **Low perceived value**: Users don't understand D' (421m) and CS (3.96 m/s) metrics
3. **User confusion**: Two tools showing different predictions for same distance
4. **Data complexity**: Required multiple PRs correctly synced — proved error-prone

### Files Removed

- `apps/api/services/critical_speed.py`
- `apps/web/components/tools/CriticalSpeedPredictor.tsx`
- `apps/api/tests/test_critical_speed.py`
- `apps/api/tests/test_cs_prediction.py`
- `/v1/analytics/cs-prediction` endpoint
- CS signals from Home, Analytics, Activity Detail

### Potential Revival (Insight-Only Pivot)

The CS model could be revived if pivoted to **insight-only mode**:

- "Your D' is low (100m) — suggests adding short speed work"
- "CS trending up 2% over 8 weeks — aerobic ceiling improving"
- Race pacing strategy based on D' depletion modeling
- "Distance suitability: Your profile favors 10K+ over 5K"

This would provide unique value that RPI cannot offer — insights about the athlete's speed vs endurance profile, not just time predictions.

### How to Revive

```bash
git checkout archive/cs-model-2026-01
# Review and adapt the code for insight-only use
# Merge back with: git merge archive/cs-model-2026-01
```

---
