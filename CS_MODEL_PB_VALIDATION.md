# Critical Speed Model Validation Report

## Date: 2026-01-14

## Athlete Profile
- **Email**: athlete@example.com
- **Total PBs**: 10 distances

---

## CS Model Results

| Metric | Value |
|--------|-------|
| **Critical Speed** | 3.9883 m/s (4:10/km) |
| **D' (D-prime)** | 324.6 m |
| **R-squared** | 0.9994 (excellent fit) |
| **Confidence** | HIGH |
| **PRs Used** | 6 |
| **PRs Excluded** | 2 (800m, mile — as outliers) |

---

## Prediction vs Actual Comparison

| Distance | Actual Time | Actual Pace | Predicted Time | Predicted Pace | Error % | Assessment |
|----------|-------------|-------------|----------------|----------------|---------|------------|
| **800m** | 3:02 | 3:46/km | (excluded) | — | — | Excluded as outlier |
| **Mile** | 6:08 | 3:48/km | 5:22 | ~3:20/km | **-12.5%** | ⚠️ UNDER-predicted by huge margin |
| **2 Mile** | 12:30 | 3:52/km | (not predicted) | — | — | Used in model |
| **5K** | 19:01 | 3:46/km | 19:32 | 3:54/km | **+2.7%** | ⚠️ OVER-predicted (slower) |
| **10K** | 39:14 | 3:55/km | 40:25 | 4:02/km | **+3.1%** | ⚠️ OVER-predicted (slower) |
| **15K** | 1:01:56 | 4:07/km | (used in model) | — | — | Used in model |
| **Half Marathon** | 1:27:14 | 4:08/km | 1:26:48 | 4:07/km | **-0.5%** | ✅ Excellent fit |
| **Marathon** | (no PB) | — | 2:54:58 | ~4:08/km | — | Prediction only |

---

## All Actual Personal Bests

| Distance | Time | Pace/km | Distance (m) | Race? |
|----------|------|---------|--------------|-------|
| 400m | 1:23 | 3:27/km | 400 | No |
| 800m | 3:02 | 3:46/km | 805 | Yes |
| Mile | 6:08 | 3:48/km | 1609 | Yes |
| 2 Mile | 12:30 | 3:52/km | 3219 | Yes |
| 5K | 19:01 | 3:46/km | 5033 | Yes |
| 10K | 39:14 | 3:55/km | 10000 | Yes |
| 15K | 1:01:56 | 4:07/km | 15000 | Yes |
| Half Marathon | 1:27:14 | 4:08/km | 21097 | Yes |
| 25K | 2:23:53 | 5:46/km | 24947 | No (training) |
| 30K | 2:54:45 | 5:49/km | 30000 | No (training) |

---

## Analysis

### 1. Pattern Identified: Long-Distance Bias

The model is **biased toward longer distances** because:

1. **Short-distance PRs excluded as "outliers"**: The 800m (3:02) and Mile (6:08) were excluded because they are FASTER than the model expects based on longer-distance data.

2. **Remaining PRs are all ≥2 mile**: The model only uses 2mi, 5K, 10K, 15K, Half Marathon — all longer efforts.

3. **Result**: CS is pulled DOWN, causing over-prediction at short distances.

### 2. Error Pattern

| Distance Type | Error Direction | Magnitude |
|---------------|-----------------|-----------|
| Mile | Under-predicted (faster) | -12.5% |
| 5K | Over-predicted (slower) | +2.7% |
| 10K | Over-predicted (slower) | +3.1% |
| Half Marathon | Accurate | -0.5% |

**Conclusion**: The athlete has **disproportionately strong short-distance PRs** relative to their longer-distance PRs. The model is incorrectly excluding this data as "outliers."

### 3. Distance Clustering

- **Short distances (≤10K)**: 800m, Mile, 2mi, 5K, 10K — 5 PRs
- **Long distances (>10K)**: 15K, Half, 25K, 30K — 4 PRs

No clustering warning triggered because there's a mix. However, the SHORT distance PRs are being EXCLUDED, effectively creating clustering.

### 4. Athlete Strength/Weakness Analysis

Based on pace analysis:

| Distance | Pace/km | Relative Strength |
|----------|---------|-------------------|
| 400m | 3:27 | ⚡ Very strong (short sprints) |
| 800m | 3:46 | ⚡ Strong |
| Mile | 3:48 | ⚡ Strong |
| 5K | 3:46 | ⚡ Strong (best aerobic) |
| 10K | 3:55 | Moderate dropoff |
| 15K | 4:07 | Expected decay |
| Half | 4:08 | Expected decay |

**Athlete Profile**: Strong speed with expected pace decay at longer distances. This is classic for a runner with good VO2max but building endurance.

---

## Root Cause of Model Error

### The Problem

The outlier detection is **incorrectly excluding the athlete's best short-distance PRs** because:

1. When fitting only long-distance data, the model calculates a lower CS.
2. When checking short-distance PRs against this model, they appear "too fast" (negative residuals).
3. The 10% residual threshold excludes them as outliers.
4. This removes the data that would CORRECT the model.

### Current Behavior

```
Model uses: 2mi, 5K, 10K, 15K, Half
Model excludes: 800m, Mile (as outliers)
Result: CS = 3.99 m/s (too slow for short distances)
```

### Expected Behavior

```
Model should use: 800m, Mile, 2mi, 5K, 10K, 15K, Half (with weights)
Result: Higher CS, better short-distance predictions
```

---

## Recommendations (DO NOT IMPLEMENT YET)

### 1. Invert Outlier Logic for Short Distances

Current: Exclude PRs that are faster than model expects.
Proposed: **Include** short PRs that are faster, as they indicate true speed capacity.

Specifically:
- If a short-distance PR has a NEGATIVE residual (faster than model), it's valuable data, not an outlier.
- Only exclude short-distance PRs with POSITIVE residuals (slower than model, possibly a bad race).

### 2. Increase Short-Distance Weight Further

Current: 1.5× weight for ≤10K.
Proposed: **2.0×** weight for distances ≤5K, since these define speed ceiling.

### 3. Separate Outlier Thresholds by Distance

Current: 10% threshold for all distances.
Proposed:
- Short (≤5K): 15% threshold (more lenient, keep more data)
- Long (>10K): 8% threshold (stricter, as these should fit well)

### 4. Add "Speed Ceiling" Constraint

If athlete has a verified short-distance PR (800m/Mile), use it to set a FLOOR for CS:
```
CS_min = PR_speed * 0.95
```

This prevents the model from calculating a CS that's obviously too slow for known short-distance performance.

### 5. Report Excluded PRs as "High Potential"

Instead of just "excluded as outliers", show:
```
"Mile PR (6:08) suggests higher CS than model. Consider updating with more short-distance races."
```

---

## Summary

| Issue | Severity | Status |
|-------|----------|--------|
| Short PRs excluded as outliers | **HIGH** | ⚠️ Needs fix |
| 5K over-predicted by 2.7% | MODERATE | Related to above |
| 10K over-predicted by 3.1% | MODERATE | Related to above |
| Half Marathon accurate | — | ✅ Working |
| Marathon prediction reasonable | — | ✅ Working |

**Overall Assessment**: The weighted regression fixes from the previous update are **not sufficient** because the outlier detection is removing the short-distance data BEFORE weighting is applied.

**Priority Fix**: Change outlier detection to NOT exclude short-distance PRs that are faster than the model (these are valuable, not outliers).

---

## Test Data for Future Validation

After fixes, re-run with expected results:

| Distance | Actual | Target Prediction | Target Error |
|----------|--------|-------------------|--------------|
| Mile | 6:08 | 6:05 - 6:15 | <2% |
| 5K | 19:01 | 18:50 - 19:10 | <1% |
| 10K | 39:14 | 38:50 - 39:40 | <2% |
| Half Marathon | 1:27:14 | 1:26:00 - 1:28:30 | <2% |

---

*Report generated: 2026-01-14*
*CS Model Version: ADR-011 with N=1 tuning (weighted regression)*
