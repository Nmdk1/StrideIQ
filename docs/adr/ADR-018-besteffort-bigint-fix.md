# ADR-018: BestEffort strava_effort_id BigInteger Fix

## Status

Implemented

## Date

2026-01-14

## Context

The BestEffort table stores Strava's "best efforts" (splits from any run, like fastest mile within a 10K). The `strava_effort_id` column was defined as `Integer` (32-bit signed), but Strava's effort IDs exceed the 32-bit integer maximum (2,147,483,647).

Example Strava effort ID: `71766851694`

This caused the sync function `sync_strava_best_efforts()` to fail with:
```
psycopg2.errors.NumericValueOutOfRange: integer out of range
```

As a result:
- BestEffort table was empty (0 records)
- PersonalBest table used only Activity-based logic (standalone races)
- Strava's splits (like a fast mile within a longer race) were never imported
- CS model lacked short-distance data for accurate predictions

## Decision

1. **Change column type**: `strava_effort_id` from `Integer` to `BigInteger`
2. **Create Alembic migration**: Safe ALTER COLUMN operation (no data loss)
3. **Re-sync BestEfforts**: Populate from Strava API
4. **Merge PB sources**: Take MIN of Activity-based and BestEffort-based times
5. **Fix is_race flags**: Ensure BestEffort-sourced PBs inherit race status from Activity

## Schema Change

```python
# Before (models.py)
strava_effort_id = Column(Integer, nullable=True)

# After
strava_effort_id = Column(BigInteger, nullable=True)
```

## Migration

```sql
ALTER TABLE best_effort
ALTER COLUMN strava_effort_id TYPE BIGINT;
```

Migration file: `67e871e3b7c2_change_strava_effort_id_to_bigint.py`

## PersonalBest Data Flow

After fix:

```
Strava API (activity details) → best_efforts array
    ↓
sync_strava_best_efforts() → BestEffort table (ALL splits)
    ↓
Merge with Activity-based PBs → PersonalBest table (MIN per distance)
    ↓
CS model uses race PRs → Better predictions
```

## Results

Before fix:
- BestEffort records: 0
- Mile PB: 6:18 (from standalone activity only)
- 5K prediction error: +2.7%

After fix:
- BestEffort records: 300+
- Mile PB: 6:08 (from race splits)
- 5K prediction error: +0.9% ✅

## Trade-offs

### Pros
- Strava splits now sync correctly
- CS model has more accurate short-distance data
- PersonalBest merges both standalone and split times

### Cons
- Sync is slow (Strava API rate limits)
- BestEffort table grows with each activity
- Migration required for existing deployments

## Security Review

- Migration is non-destructive (BIGINT can store all INTEGER values)
- No data loss
- No user input involved (internal data flow)
- Rollback possible (but would lose new effort IDs exceeding INTEGER max)

## Test Plan

1. **Unit tests**: BigInteger column accepts large IDs
2. **Integration tests**: Sync → BestEffort → PersonalBest → CS prediction flow
3. **Validation**: Compare predicted vs actual times for all PB distances

## Related

- ADR-011: Critical Speed Model
- ADR-017: Tools Page CS Predictor
- CS_MODEL_SHORT_DISTANCE_DIAGNOSIS.md
