# Builder Note — RunContext Science Moat (GarminDay Integration)

**Date:** 2026-02-28  
**Assigned to:** Backend Builder  
**Advisor sign-off required:** Yes (before deploy)  
**Urgency:** High ROI / High moat

---

## Before Your First Tool Call

Read in order:
1. `docs/FOUNDER_OPERATING_CONTRACT.md`
2. `docs/TRAINING_PLAN_REBUILD_PLAN.md`
3. `docs/AGENT_WORKFLOW.md`
4. This document

---

## Objective (ROI + Moat)

Wire Garmin health data already stored in `GarminDay` into the run context analysis input snapshot so insights are grounded in real recovery physiology even when check-ins are sparse.

**Why this is high ROI:** better insight quality for engaged Garmin users with minimal UI churn.  
**Why this is moat work:** combines device-derived recovery signals + athlete self-report with explicit source precedence and no fake scale conversions.

---

## Root Cause (Confirmed)

`apps/api/services/run_analysis_engine.py` builds `InputSnapshot` from `DailyCheckin` only.  
`GarminDay` is populated by webhook ingestion but not read in this path.

Result: run context insights may ignore available HRV/sleep/resting-HR data unless manually entered by athlete.

---

## Data Mapping Contract

Use `GarminDay` only to fill null gaps left by `DailyCheckin`.

| Snapshot field | Primary source | Gap-fill source | Conversion |
|---|---|---|---|
| `sleep_last_night` | `DailyCheckin.sleep_h` | `GarminDay.sleep_total_s` | `/ 3600` |
| `sleep_7_day_avg` | avg `DailyCheckin.sleep_h` | avg `GarminDay.sleep_total_s` | `/ 3600` |
| `hrv_today` | `DailyCheckin.hrv_rmssd` | `GarminDay.hrv_overnight_avg` | none |
| `hrv_7_day_avg` | avg `DailyCheckin.hrv_rmssd` | avg `GarminDay.hrv_overnight_avg` | none |
| `resting_hr_today` | `DailyCheckin.resting_hr` | `GarminDay.resting_hr` | none |
| `resting_hr_7_day_avg` | avg `DailyCheckin.resting_hr` | avg `GarminDay.resting_hr` | none |

**Stress rule (important):**
- Do **not** map Garmin stress (`avg_stress` 0-100) into existing self-report stress (`stress_1_5`).
- Add separate optional snapshot fields:
  - `garmin_stress_score: Optional[int]`
  - `garmin_stress_qualifier: Optional[str]` (calm / balanced / stressful / very_stressful)
- Treat Garmin sentinel `avg_stress = -1` as null.

---

## Source Priority Rule (Non-Negotiable)

1. Athlete self-report (`DailyCheckin`) is primary when present.
2. `GarminDay` fills only missing fields.
3. Never overwrite self-report with device values.

This preserves the founder contract: athlete decides, system informs.

---

## Implementation Scope

### Backend (`apps/api/services/run_analysis_engine.py`)

1. Import `GarminDay`.
2. Extend `InputSnapshot` with:
   - `garmin_stress_score: Optional[int] = None`
   - `garmin_stress_qualifier: Optional[str] = None`
3. In `get_input_snapshot()`:
   - Keep current `DailyCheckin` pass unchanged.
   - Query `GarminDay` rows for `athlete_id` between `run_date - 7 days` and `run_date`.
   - Fill only snapshot fields still null after check-in pass.
   - Compute 7-day averages from Garmin rows only when corresponding averages are still null.
   - Map stress into new Garmin-specific fields only.
4. Add helper for stress qualifier bands (deterministic):
   - 0-24: `calm`
   - 25-49: `balanced`
   - 50-74: `stressful`
   - 75-100: `very_stressful`
   - `-1` or null: no value

### Frontend (`apps/web/components/activities/RunContextAnalysis.tsx`)

1. Extend interface for new fields:
   - `garmin_stress_score?: number | null`
   - `garmin_stress_qualifier?: string | null`
2. In pre-run details:
   - Show manual stress as today.
   - If manual stress missing and Garmin qualifier present, show:
     - `Stress (device): <qualifier>`
3. Add source label per row where applicable:
   - `self-reported` vs `from device`

No other UI/flows in scope.

---

## Gate 0 (Run Before Code Changes)

Verify production has usable GarminDay rows for founder athlete.  
If missing, stop and report upstream ingestion/storage issue first.

Minimum fields to verify non-null recently:
- `sleep_total_s`
- `hrv_overnight_avg`
- `resting_hr`

---

## Tests Required

Add/extend tests in `apps/api/tests/test_run_analysis_engine.py` (and frontend tests where needed):

1. **Device-only path:** no check-ins + GarminDay present -> snapshot populated.
2. **Priority path:** both sources present -> check-in values win on overlap.
3. **Hybrid path:** partial check-ins -> Garmin fills only nulls.
4. **Stress sentinel path:** `avg_stress = -1` -> Garmin stress fields remain null.
5. **Graceful empty path:** no GarminDay rows -> no crash, current behavior preserved.
6. **UI source labeling:** pre-run panel labels source correctly for manual vs device values.

---

## Acceptance Criteria (Definition of Done)

- Run context snapshot includes GarminDay-derived sleep/HRV/resting-HR when check-ins are absent.
- Self-report always wins on overlapping fields.
- No scale corruption (Garmin stress never mapped to `/5` field).
- Frontend displays device stress qualifier only when manual stress missing.
- All targeted tests pass.
- No regressions in existing run context behavior.

---

## Evidence Required in Handoff

1. File list changed (scoped only to relevant backend/frontend/test files).
2. Test output pasted (not summarized) for all new/updated tests.
3. One example payload before/after snapshot (redacted IDs) showing gap-fill behavior.
4. Production verification note confirming Gate 0 query results.

---

## Out of Scope

- Correlation engine changes
- N=1 narrative engine redesign
- Efficiency polarity contract changes
- Any Garmin OAuth/webhook auth/router changes

