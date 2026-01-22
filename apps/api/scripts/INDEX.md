## Scripts index (inventory + placement rules)

This is a lightweight map of what lives in `apps/api/scripts/`.

### High-level buckets (by intent)

- **Verification harnesses (preferred long-term)**
  - Prefixes: `golden_path_*`, `verify_*`, `e2e_*`, some `test_*`
  - Goal: repeatable “is the stack healthy?” checks against a running environment.

- **Ops / repair tooling (keep, but safe-by-default)**
  - Prefixes: `backfill_*`, `migrate_*`, `recalculate_*`, `seed_*`, `reset_*`, `set_*`, `fix_*`
  - Goal: repair or maintain data integrity.
  - Rule: DRY_RUN default, require `--commit` for writes.

- **Research / analysis (should not creep into production workflows)**
  - Prefixes: `analyze_*`, `deep_*`, `extract_*`, `validate_*`, `view_*`, `download_*`, `crawl_*`, `process_*`
  - Goal: exploration, model validation, content extraction.
  - Rule: keep parameterized; use `_scratch/` for one-offs.

### “Where should new scripts go?”

- **One-off experiments**: `apps/api/scripts/_scratch/` (gitignored)
- **Anything intended to be reused**: keep it in this folder, but:
  - no hardcoded credentials
  - no hardcoded personal identifiers
  - no secret printing
  - DRY_RUN by default if it writes

### Current folder composition (quick signal)

Based on filenames, the biggest clusters are:
- `test_*` (~19)
- `verify_*` (~16)
- `extract_*` (~14)
- `check_*` (~11)

### Maintained repair scripts

See `docs/OPS_REPAIR_SCRIPTS.md`.

