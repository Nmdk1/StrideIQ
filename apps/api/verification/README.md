# Verification Scripts

Manual verification tools for plan generation invariants.

**Not part of runtime or CI.**

## Scripts

| Script | Purpose |
|--------|---------|
| `verify_all_distances.py` | Tests ADR-038 long run progression across all distances (5k, 10k, 10mi, half, marathon) and timelines (6, 8, 12, 16 weeks) |
| `verify_different_athletes.py` | Tests ADR-038 with 8 different athlete profiles (elite, intermediate, beginner, injury return, etc.) |
| `regenerate_plan.py` | Regenerates and saves a plan to the database for frontend verification |

## Usage

```bash
docker-compose exec api python verification/verify_all_distances.py
docker-compose exec api python verification/verify_different_athletes.py
docker-compose exec api python verification/regenerate_plan.py
```

## When to delete

Safe to delete once invariants are covered by:
- Unit tests in `tests/test_long_run_progression.py`
- Integration tests that verify end-to-end plan generation

## History

Created: 2026-01-17
Purpose: Verify ADR-038 N=1 Long Run Progression fix
