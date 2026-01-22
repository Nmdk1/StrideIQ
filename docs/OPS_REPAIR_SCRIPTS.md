## Ops repair scripts (maintained)

These scripts exist to **repair data safely** when ingestion is partial or when we need to correct legacy text. They are intended to be run **inside the API container** and default to **DRY_RUN** unless `--commit` is provided.

### Personal bests (PB) / BestEffort repairs

StrideIQ PBs should be derived from Strava `best_efforts` (stored in `BestEffort`), then materialized into `PersonalBest`. When `BestEffort` extraction is incomplete, PBs can be wrong or missing.

- `apps/api/scripts/backfill_best_efforts_fast.py`
  - **What it does**: fetches Strava activity details for the athlete’s *fastest* runs first, extracts `best_efforts`, and (optionally) regenerates PBs.
  - **When to use**: “PBs look wrong/missing” and we want a quick, high-yield backfill without scanning everything.

- `apps/api/scripts/find_better_mile_effort.py`
  - **What it does**: scans unprocessed Strava activities (those with no `BestEffort` rows yet) and stops once it finds a “mile” effort better than the current stored best.
  - **When to use**: “Mile PB is clearly wrong” and we want a targeted search rather than a full backfill.

Safety:
- Both scripts default to **DRY_RUN**. Use `--commit` to persist.
- They include basic request pacing (`--sleep` + `--jitter`) to reduce rate-limit pressure.

### Planned workout text normalization

Older planned workouts can contain mojibake (UTF-8 mis-decoding), e.g. `â†’` instead of `→`.

- `apps/api/scripts/normalize_planned_workout_text.py`
  - **What it does**: normalizes `title`, `description`, `coach_notes` (and can optionally clear fields).
  - **When to use**: legacy text repair, not routine plan edits.

---

## Notes

- These scripts are **ops tooling**, not product features. They should remain safe-by-default and narrowly scoped.
- If a repair script becomes something we need frequently, promote it into the **Admin Heartbeat** phase as a guarded admin action.

