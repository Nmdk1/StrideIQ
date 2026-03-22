# P4 Load Context — Technical specification

**Status:** Approved for implementation (constants locked 2026-03-22)  
**Date:** 2026-03-20 (rev. 2026-03-22)  
**Implements:** `PLAN_COACHED_OUTPUT_AND_LOAD_CONTRACT.md` § D1–D2, D4 (partial), **Remaining (P4)** under P1  
**Does not implement:** D3 full intensity envelope (table TBD), P5 adaptation, fluency registry Phase 4

---

## 1. Summary

Introduce a **`LoadContext`** (name fixed at implementation) built from synced **`Activity`** rows for a given **`reference_date`** (typically plan start or “today”). Use it in **`PlanGenerator.generate_semi_custom`** to:

1. Seed **easy-long progression** so the first **planned** easy long respects **`max(L30_max_easy_long_mi, tier-derived start)`** where history exists, then existing P1 **in-plan** spike chain applies.
2. Optionally adjust **starting weekly volume** for progression via **`max(request.current_weekly_miles, observed_recent_mpw)`** with explicit caps (below).

**Slice 4b:** Authenticated **standard** create/preview uses history when **`use_history=True`** (approved **YES** for prod once 4a + CI green).

---

## 2. Definitions (authoritative for this spec)

| ID | Name | Rule |
|----|------|------|
| **H1** | Historical easy-long candidate | `Activity` is a run, **not** classified as race (use same race-detection signals as elsewhere in codebase—e.g. `workout_type`, flags); **duration ≥ 90 minutes** (`duration_s / 60 >= 90` or canonical equivalent). **Distance:** use stored `distance_m` converted to **miles** for `L30_max`. **False positives (v1):** `duration ≥ 90` and not-race can still include occasional **non-easy quality** sessions when import/classification is thin—**accepted for v1** at low rate; revisit when activity classification quality improves. |
| **H2** | L30 window | **30 calendar days** ending **`reference_date`** (inclusive of `reference_date` as end anchor per implementation choice—document in code comment; tests must fix the boundary). |
| **H3** | **L30_max_easy_long_mi** | `max(distance_mi)` over activities satisfying H1 in H2; if none, **`None`** (caller uses tier-only baseline). |
| **H4** | Observed recent weekly miles | **Trailing 4-week average** total run miles ending at `reference_date`, using **canonical run activities** only (`get_canonical_run_activities` or documented equivalent). If insufficient data, **`None`**. |
| **H5** | Relationship to ADR-061 | **ADR-061** uses **105 min** for **long-run identification inside `AthletePlanProfile`**. P4 **H1 uses 90 min** per **D1** in `PLAN_COACHED_OUTPUT_AND_LOAD_CONTRACT.md` for **L30 easy-long max**. This is an **intentional dual threshold**: profile = conservative physiology gate; P4 window = product “recent long session” for spike baseline. **Do not merge** without spec revision. |

---

## 3. `LoadContext` shape (logical; exact types in code)

Minimum fields:

| Field | Type | Description |
|-------|------|-------------|
| `reference_date` | `date` | Anchor for windows. |
| `l30_max_easy_long_mi` | `Optional[float]` | H3. |
| `observed_recent_weekly_miles` | `Optional[float]` | H4. |
| `history_override_easy_long` | `bool` | **D4:** true iff policy says apply looser easy-long spike (see §5). |
| `disclosures` | `List[str]` | Short machine-oriented notes for logging or future UI (e.g. `cold_start_l30`, `d4_override`). |

**Optional** (if implemented in same slice or follow-on): precomputed **D4** counts for tests/debug: `count_long_15plus`, `count_long_18plus`, `recency_last_18plus_days`.

**Builder**

- **`build_load_context(athlete_id, db, reference_date) -> LoadContext`**
- **Deterministic** for the same DB snapshot.
- **No side effects** (read-only queries).

**Module location (proposed):** `apps/api/services/plan_framework/load_context.py`

---

## 4. Semi-custom wiring (`generate_semi_custom`)

**Preconditions:** `athlete_id` is not `None`, `self.db` is not `None`. If either missing, behavior **unchanged** from today (questionnaire-only).

### 4.1 Starting weekly volume

Let `req_mpw = request.current_weekly_miles` (existing parameter). Let `obs = observed_recent_weekly_miles` from `LoadContext`.

- If `obs is None`: `effective_start_mpw = req_mpw` (today’s behavior).
- Else: `effective_start_mpw = max(req_mpw, obs)`.
- **Cap:** `effective_start_mpw` must not exceed **`min(obs * C_upper, tier_max_weekly_miles)`** where **`C_upper`** defaults to **1.15** unless founder changes in review—prevents a single spike week from exploding the plan. If `obs` is very low, cap still respects tier max from `VolumeTierClassifier`.

Document final cap in code + tests.

### 4.2 Easy-long week-1 seed

Let `tier_start_long` = existing P1 logic for first easy long (from tier min weekly and `MIN_STANDARD_EASY_LONG_MILES` / curve entry—use same path `_generate_workouts` already uses for week 1).

Let `L = l30_max_easy_long_mi`.

- If `L is None`: `seed_long = tier_start_long` (no change).
- Else: `seed_long = max(L, tier_start_long)`.
- Pass **`easy_long_floor_mi`** into `_scale_long_run` for the **first** easy long only (`previous_easy_long_mi is None`). **Ordering vs 35% soft cap:** apply **`min(..., weekly_soft_cap, peak)`** then **`max(MIN_STANDARD_EASY_LONG_MILES, ...)`** then **`max(..., easy_long_floor_mi)`** then **`min(..., peak)`** — same “floor may exceed soft cap” contract as the 8 mi policy in `PLAN_COACHED_OUTPUT_AND_LOAD_CONTRACT.md`.

**In-plan weeks 2+:** Unchanged P1 chain: compare to **previous planned** easy long.

### 4.3 Tier classification

`VolumeTierClassifier.classify` today uses `current_weekly_miles`. Use **`effective_start_mpw`** for classification when LoadContext applied.

---

## 5. D4 — `history_override` for easy-long spike

Reuse existing **`history_override`** on `WorkoutScaler.scale_workout` / `_scale_long_run` where already implemented.

**Enable when** (tunable constants in one place, tested):

- `count_long_15plus >= N` with **`N = 8`** (trailing **24 months**), and  
- `recency_last_18plus <= M` days before `reference_date` with **`M = 120`** (locked).

**If** profile service already exposes compatible signals, **prefer reading from `AthletePlanProfileService.derive_profile`** for D4 counts to avoid duplicate query logic—otherwise duplicate with a comment linking H5.

**D4 does not** change threshold/interval scheduling (D3).

---

## 6. Slice 4 — Standard plan (4a / 4b)

### 6a — Implementation

- Extend **`generate_standard`** to accept **optional** `athlete_id: Optional[UUID] = None` and optional **`use_history: bool = False`** (exact API per code review).
- When `use_history` is **False**, behavior identical to today.
- When **True** and `athlete_id` + `db` set: apply same LoadContext rules as semi-custom for **volume + easy-long seed** where applicable; tier still comes from **request** `volume_tier` unless spec revision says otherwise.

### 6b — Product enable (**approved YES**)

- Routers (`plan_generation.py`): **`use_history=True`** for authenticated **standard** **create** and **preview** when `athlete` is present (optional auth on preview: enable when athlete is not `None`).
- Monetization / positioning unchanged.

---

## 7. Tests (required)

### 7.1 Unit — `LoadContext`

- Empty activities → `l30_max_easy_long_mi is None`, `observed_recent_weekly_miles is None`.
- Single 95 min / 12 mi run in window → `l30_max_easy_long_mi == 12` (within float tol).
- Race flagged → excluded from L30 max.
- 89 min run → excluded from L30 max.
- Boundary: run exactly 30 days before `reference_date` — in or out per chosen boundary rule; test must lock behavior.

### 7.2 Unit — semi-custom merge

- Fixture athlete: `observed_recent_weekly_miles` high, `request` low → `effective_start_mpw` rises; cap enforced.
- Fixture: L30 = 14 mi, tier would start at 8 → first easy long target **≥ 14** (exact assertion on generated `GeneratedWorkout` for first `long` in week 1).

### 7.3 Regression

- Existing **`test_output_validation`**, **`test_p1_p2_regression`**, **`test_workout_narrative`**, **`test_workout_variant_dispatch`** (or subset in CI job) remain green.
- No change to **custom** `generate_custom` outputs for unchanged inputs (smoke test or explicit case).

### 7.4 Slice 4 (if approved)

- `generate_standard(..., use_history=False)` byte-identical or metric-identical to baseline suite for fixed seeds.
- `use_history=True` with fixtures → expected shift in first long / volume.

---

## 8. API / schema

**Default:** No change to public request/response JSON.  
If **disclosures** or debug fields are exposed, require **separate approval** and version bump in API docs.

---

## 9. Performance & safety

- **Queries:** bounded by athlete + date window; no full-table scan; use existing indexes on `athlete_id`, `start_time`.
- **Failure:** if `build_load_context` raises, **log and fall back** to non-history path (same as today)—do not fail plan generation unless founder later decides otherwise.

---

## 10. Completion criteria (judge checklist)

- [ ] Slice 0: H5 and H2 documented; any code comments for boundary choice.
- [ ] Slice 1: `LoadContext` + §7.1 tests green.
- [ ] Slice 2–3: semi-custom wired + §7.2–7.3 green.
- [ ] Slice 4a/4b: only if approved; §6 + §7.4 green.
- [ ] CI green on merge branch.
- [ ] Prod: deploy + smoke per operator; report in completion note.
- [ ] `PLAN_COACHED_OUTPUT_AND_LOAD_CONTRACT.md` **Remaining (P4)** line updated to **implemented** with pointer to this spec.

---

## 11. References

- `docs/specs/PLAN_COACHED_OUTPUT_AND_LOAD_CONTRACT.md` — D1, D2, D4, P1 remaining P4  
- `docs/specs/P4_LOAD_CONTEXT_SCOPE_AND_PROCESS.md` — process and approvals  
- `docs/ADR_061_ATHLETE_PLAN_PROFILE.md` — profile long-run definition (105 min)  
- `apps/api/services/plan_framework/generator.py` — `generate_semi_custom`, `generate_standard`  
- `apps/api/services/mileage_aggregation.py` — `get_canonical_run_activities`  
- `apps/api/routers/plan_generation.py` — entrypoints  

---

## 12. Approval

**Technical spec approved:** Northstar / founder — **2026-03-22**  

**Constants locked:** `C_upper = 1.15`, `D4_N = 8`, `D4_M = 120` days  

**Slice 4b (standard history):** **enabled YES**  
