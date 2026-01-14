# CS Model Short Distance Diagnosis

## Date: 2026-01-14

## Issue Reported

User stated:
- Mile PR is **5:32** (or ~5:34 per Strava)
- 5K PR pace is faster than the mile time — this is wrong
- CS model is not using the fast mile PR

---

## Investigation Results

### 1. Strava Best Efforts vs Our Database

| Distance | Strava Best Effort | Our Database PB | Gap |
|----------|-------------------|-----------------|-----|
| **1 mile** | **5:34** | 6:08 | **34 sec missing** |
| 5K | 18:54 | 19:01 | 7 sec missing |
| 10K | 39:14 | 39:14 | ✅ Match |
| Half | 1:27:14 | 1:27:14 | ✅ Match |

**Source**: Strava profile screenshot shows "Best Efforts" which are splits from ANY run.

### 2. Root Cause: BestEffort Table is EMPTY

```
BestEffort records in database: 0
```

**Why?** The sync function `sync_strava_best_efforts()` has a **critical bug**:

```python
# In models.py line 226:
strava_effort_id = Column(Integer, nullable=True)  # BUG: Should be BigInteger

# Strava effort IDs exceed 32-bit integer max:
# Example: 71766851694 > 2,147,483,647 (max 32-bit signed int)
```

When the sync runs, it fails with:
```
psycopg2.errors.NumericValueOutOfRange: integer out of range
```

### 3. Current Data Flow (BROKEN)

```
Strava API → best_efforts in response
     ↓
sync_strava_best_efforts() → FAILS on INSERT (Integer overflow)
     ↓
BestEffort table → EMPTY
     ↓
PersonalBest regeneration → NEVER RUNS (nothing to aggregate)
     ↓
PersonalBest uses Activity-based logic only → Misses splits
```

### 4. What SHOULD Happen

```
Strava API → best_efforts in response
     ↓
sync_strava_best_efforts() → Stores ALL efforts in BestEffort table
     ↓
BestEffort table → Contains 5:34 mile, 18:54 5K, etc.
     ↓
regenerate_personal_bests() → MIN per distance from BestEffort
     ↓
PersonalBest contains correct 5:34 mile
     ↓
CS model uses 5:34 mile → Better predictions
```

---

## Current PersonalBest Sources

Our database populates PersonalBest from **standalone activities only**, not Strava splits:

| Distance | Time | Source | Is This a Split? |
|----------|------|--------|------------------|
| 400m | 1:23 | Standalone activity | No |
| 800m | 3:02 | Standalone race | No |
| Mile | **6:08** | Standalone race | No |
| 2 Mile | 12:30 | Standalone race | No |
| 5K | **19:01** | Standalone race | No |
| 10K | 39:14 | Standalone race | No |
| 15K | 1:01:56 | Within longer race | Yes (but full activity) |
| Half | 1:27:14 | Standalone race | No |

The **5:34 mile** is a split from within a longer run — never synced.

---

## Strava API Test

I manually tested the Strava API and confirmed it DOES return best efforts:

```
Activity: Some days are just better than others...
External ID: 17039328200
Distance: 19317m

Best efforts from Strava API:
  400m -> 400m : 1:53
  1/2 mile -> None (unmapped)
  1K -> None (unmapped)
  1 mile -> mile : 7:57 (this activity)
  2 mile -> 2mile : 16:13
  5K -> 5k : 25:55
  10K -> 10k : 52:42
  15K -> 15k : 82:16
  10 mile -> None (unmapped)
```

The mapping works. The issue is the database INSERT failing.

---

## Impact on CS Model

Because BestEffort sync is broken:

1. **Mile PB wrong**: 6:08 instead of 5:34 (-34 sec / -10%)
2. **5K PB slightly wrong**: 19:01 instead of 18:54 (-7 sec / -0.6%)
3. **CS model over-predicts short distances** because it doesn't have the fast mile data

Current CS model inputs (from PersonalBest):
```
PRs used: 5k, 10k, 15k, half_marathon, 2mile
PRs excluded as outliers: mile (6:08), 800m (3:02)
```

If we had the 5:34 mile:
```
Mile pace: 3:26/km
5K pace: 3:46/km
```

This would INCREASE CS and improve short-distance predictions.

---

## Diagnostic Table

| Distance | Actual Time | Included in CS Fit? | Reason Excluded | Predicted Pace | Error % |
|----------|-------------|---------------------|-----------------|----------------|---------|
| 800m | 3:02 | ❌ | Outlier (too fast) | — | — |
| **Mile** | **5:34** (Strava) | ❌ | **NOT IN DATABASE** | 5:22 | -3.6% |
| Mile | 6:08 (DB) | ❌ | Outlier (too fast) | 5:22 | -12.5% |
| 2 Mile | 12:30 | ✅ | — | — | — |
| 5K | 19:01 | ✅ | — | 19:32 | +2.7% |
| 10K | 39:14 | ✅ | — | 40:25 | +3.1% |
| 15K | 1:01:56 | ✅ | — | — | — |
| Half | 1:27:14 | ✅ | — | 1:26:48 | -0.5% |

---

## Recommendations (DO NOT IMPLEMENT YET)

### Fix 1: Database Schema Bug (CRITICAL)

**Problem**: `strava_effort_id` is `Integer` (32-bit) but Strava IDs exceed this.

**Fix**:
```python
# In models.py:
strava_effort_id = Column(BigInteger, nullable=True)  # Was: Integer
```

**Migration required**: Alter column type from INTEGER to BIGINT.

### Fix 2: Re-run BestEffort Sync

After schema fix:
1. Clear BestEffort table (if any partial data)
2. Run `sync_strava_best_efforts(athlete, db, limit=500)` for all activities
3. Run `regenerate_personal_bests(athlete, db)`

### Fix 3: Add 1K and 10-mile mapping

Currently unmapped in `STRAVA_EFFORT_MAP`:
```python
'1k': None,       # Should map to '1k' or skip
'10 mile': None,  # Should map to '10mile' or skip
'1/2 mile': None, # Should map to '800m' or skip
```

### Fix 4: Verify CS Model Uses BestEffort-sourced PRs

After PersonalBest regeneration, verify CS model sees:
- Mile: 5:34 (not 6:08)
- 5K: 18:54 (not 19:01)

---

## Summary

| Issue | Severity | Root Cause |
|-------|----------|------------|
| Mile PB wrong (5:34 vs 6:08) | **CRITICAL** | BestEffort sync broken |
| 5K PB slightly wrong | MODERATE | BestEffort sync broken |
| CS over-predicts short | HIGH | Missing fast mile data |
| strava_effort_id overflow | **CRITICAL** | Integer column for BigInt data |

**Priority**: Fix the database schema bug FIRST, then re-sync best efforts.

---

*Report generated: 2026-01-14*
