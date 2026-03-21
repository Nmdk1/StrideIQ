# Plan: coached output & load contract (spec)

**Status:** Draft for implementation  
**Date:** 2026-03-22  
**Read with:** `docs/PLAN_CUTBACK_MP_POLICY.md`, `docs/TRAINING_PLAN_REBUILD_PLAN.md`, Vega notes (long-run curve, weighted easy fill, progression copy)

## Purpose

Move plan generation from **“template that passes validators”** to **“reads like a coach”** while grounding **risk** in **N=1 history and signals** the product already captures.

This spec separates:

1. **Static template improvements** — no DB; better progression curve, easy-day texture, copy.  
2. **History-aware load contract** — uses synced `Activity` (+ classification) and optional injury/return context.  
3. **Adaptive modulation** — uses `DailyCheckin`, `ActivityFeedback`, completion; tightens or relaxes **next week** prescriptions.

---

## Existing data (verified in codebase)

| Signal | Model / module | Notes |
|--------|----------------|--------|
| Runs (distance, time, start) | `Activity` | `distance_m`, `duration_s`, `start_time`; `workout_type`, `workout_zone`, `intensity_score` |
| Morning check-in | `DailyCheckin` | `soreness_1_5`, `readiness_1_5`, sleep, stress, optional Garmin fields |
| Post-run perception | `ActivityFeedback` | `leg_feel`, `perceived_effort`, mood/energy |
| Canonical activity queries | `get_canonical_run_activities` | `services/mileage_aggregation.py` |
| Long-run stats (4 weeks) | `FitnessBankCalculator._calculate_current_long_run` | Max long in **last 28 days**; long = ≥10 mi or ≥90 min — **align to 30d policy below** |
| Established baseline (12 mo) | `ModelDrivenPlanGenerator._get_established_baseline` | Peak week, long runs ≥13 mi, MP long detection, `is_returning_from_injury` heuristic |

**Gap:** `plan_framework` **standard generator** (`PlanGenerator.generate_standard`) is largely **history-blind**. Wiring load contract to **personalized** paths (`generate_semi_custom` / custom / constraint-aware) should be explicit in phased work.

---

## Definitions

### D1 — Easy long (for spike baseline)

Runs that count toward **“longest easy long in rolling window”** for **spike** checks:

- **Primary:** `Activity` classified as easy / endurance / long_easy (exact `workout_type` set TBD with classifier team) **or** HR/pace band vs athlete threshold when streams exist.  
- **Fallback (conservative):** if classification missing, use **duration ≥ 90 min** and **not** tagged threshold/interval/race (`workout_type` / zone).

### D2 — Rolling baseline for distance spike

- **Window:** **30 calendar days** (product default; cite Nguyen-style “recent max session” logic in copy — see founder [Forget the 10% Rule](https://mbshaf.substack.com/p/forget-the-10-rule)).  
- **Baseline metric:** `L30_max_easy_long` = max distance (mi) of runs satisfying D1 in window.  
- **Planned spike check:** next planned easy long `L_planned` must satisfy  
  `L_planned <= L30_max_easy_long * (1 + spike_allowance)` unless **history override** (D4) applies.

**Default `spike_allowance`:** **10%** for typical runners (align with article framing).  
**Step rule (easy-only progression):** prefer **+2 mi** steps when the long is **easy-only** (no fast finish, no strides on that session) — can coexist with % cap as **soft** check.

### D3 — Intensity envelope (reinjury vector)

Separate from distance spike:

- Track **`days_since_last_quality`** where quality = threshold, threshold_intervals, intervals, repetitions at race-sharpening intent, or MP blocks inside long runs (definition table TBD).  
- **Return-from-injury / cold intensity:** even if easy long is allowed, **do not** schedule threshold/intervals until explicit progression rules satisfied (founder example: no T/I since injury date until medically cleared + completion-based gates).

### D4 — History override (experienced long-run tolerance)

For athletes with **dense historical long-run practice**, **distance novelty** is lower risk at a given mileage.

**Inputs (from synced history, e.g. 12–24 months):**

- `count_long_15plus` — runs ≥ 15 mi  
- `count_long_18plus` — runs ≥ 18 mi  
- `recency_last_18plus` — days since last ≥18 mi easy long  

**Policy sketch (tunable):**

- If `count_long_15plus >= N` and `recency_last_18plus <= M days` **before** layoff, allow **higher starting long** or **slightly larger spike_allowance** only for **easy** longs — **does not** auto-unlock intensity (D3).

**Founder edge case:** first run back 15 mi **easy** can be coherent when history shows **many** 15+ / 18+ longs; still gate **intensity** separately.

### D5 — Weekly % long run (Source B today)

Current validators use **long ≤ ~30% of week**. Treat as:

- **Default population:** **warn** or **soft cap** in UI/copy, not necessarily **hard fail** for **easy** long when D2 passes and density is low (e.g. many small easy days).  
- **Hard fail:** when combined with **high quality density** or **mixed MP long** — exact rule in test matrix.

---

## Product behaviors (priority order)

### P1 — Long-run progression curve (template + scaler)

**Intent:** Long run follows a **planned curve** toward `peak_long` by phase/week, not only `weekly_volume * 0.28`.

- Inputs: `plan_week`, `duration_weeks`, `phase`, `is_cutback`, `is_taper`, `peak_long` (tier/distance), optional `L30_max_easy_long` / `start_long`.  
- **Order of application:** target from curve → **clamp D2** → clamp **soft % of week** → clamp **absolute peak**.  
- Cutback long: **~70%** of current week target (Vega) unless N=1 says hold.

**Tests:** golden weeks for marathon mid 18w; monotonicity except cutback/taper; spike respected when history injected.

### P2 — Weighted easy fill (`generator.py`)

**Intent:** Same weekly total; **vary** easy days by adjacency:

- Day after quality: **0.7×** weight  
- Day before long: **0.8×**  
- Standalone easy: **1.2×**  
- Normalize + floors (min mi per easy slot for 5d schedules)

**Tests:** ordering properties (e.g. recovery day ≤ mid-week easy when structure fixed); sum invariants.

### P3 — Progression narrative (scaler titles/descriptions)

**Intent:** Grounded copy only — e.g. “Building from **8 mi MP** last cycle to **12 mi** continuous — fueling practice at race pace.”

- Inputs: previous week same workout family, `mp_week` index, phase.  
- **No LLM** for core narrative (avoid hallucination); templates + numbers from scaler state.

### P4 — Wire D2/D3/D4 into personalized generation

- Reuse / extend `FitnessBankCalculator` (30d window, D1 filter).  
- Expose a small **`LoadContext`** dataclass into `generate_semi_custom` / custom / constraint planner.  
- **Standard** plans: optional “typical runner” defaults only (no DB).

### P5 — Adaptive modulation (check-ins + feedback)

- If `soreness_1_5` or `leg_feel` crosses threshold → **repeat long week**, **remove +2 step**, or **shorten quality** next week.  
- Requires job or **on plan refresh** hook — not only at generation time.

---

## Non-goals (this phase)

- New workout types.  
- Frontend layout changes (copy may surface in API payloads only).  
- Replacing entire constraint-aware stack — **integrate** where athlete has data.

---

## Acceptance / CI

- Extend `plan_validation_helpers` or parallel **N=1 contract tests**: spike, intensity gap, history override fixtures.  
- Keep existing Source B tests; migrate **easy-long %** toward **warn** or tiered fail per D5.  
- `P0-GATE` attestation when touching `plan_framework` per registry spec.

---

## Open questions for Vega / founder

1. Exact **workout_type** whitelist for D1 (easy long) from classifier.  
2. **spike_allowance** for builder vs mid vs history override.  
3. Whether **planned** longs in the **future** week count toward “next spike” pre-validation (recommended: yes for schedule coherence).  
4. Minimum **completion** before trusting check-ins for adaptation (avoid adapting on empty weeks).

---

## Implementation order (recommended)

1. P1 scaler curve + clamps (template-only baseline).  
2. P2 weighted easy fill.  
3. P3 narrative templates.  
4. P4 `LoadContext` + 30d spike + history override on personalized paths.  
5. P5 adaptation hook.
