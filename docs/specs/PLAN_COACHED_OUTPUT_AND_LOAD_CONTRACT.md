# Plan: coached output & load contract (spec)

**Status:** P1 implemented in `workout_scaler` + `generator` (2026-03-22); P2+ pending  
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

### D1 — Easy long (for spike baseline) — **resolved (Vega)**

- **Planned:** only `workout_type == "long"` for easy-long spike chaining; `long_mp` / `long_hmp` use MP/HMP rules.  
- **Historical (synced):** `duration >= 90 min`, not race (`workout_type` / candidate flags); no pace-based “easy” until per-athlete easy thresholds exist.

### D2 — Rolling baseline for distance spike

- **Window:** **30 calendar days** (product default; cite Nguyen-style “recent max session” logic in copy — see founder [Forget the 10% Rule](https://mbshaf.substack.com/p/forget-the-10-rule)).  
- **Baseline metric:** `L30_max_easy_long` = max distance (mi) of runs satisfying D1 in window (**P4** — not yet merged into scaler; P1 uses in-plan chain).  

**Spike rule (Vega) — in-plan (P1):** **Step is primary**, **% is secondary**. Each week’s allowed ceiling vs the previous **planned** easy long:  
`min(previous + step_mi, previous * (1 + spike_pct))` (more conservative of the two).  

| Tier | Step | % guard (secondary) |
|------|------|---------------------|
| builder | +1.5 mi | 15% |
| low | +2 mi | 12% |
| mid | +2 mi | 10% |
| high / elite | +2 mi | 10% |
| history override (D4) | +3 mi | 15% |

**Planned progression (Q3 — resolved):** Yes — Week *N* easy long is checked against Week *N−1* **planned** easy long. With history: `baseline = max(L30_max_easy_long, previous_planned_long)` when P4 wires L30 (P1 uses in-plan chain only; D4 override already uses activity history for tier loosening).

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

### P1 — Long-run progression curve (template + scaler) — **implemented**

**Intent:** Easy long follows a **curve** from `start_long` → `peak_long` over build weeks, with **cutback** and **taper** shaping, **in-plan spike** vs last planned easy long, **weekly soft cap** 35% of week (matches relaxed `B1-LR-PCT`), **`MIN_STANDARD_EASY_LONG_MILES = 8`** (founder: never 5 mi builder long).

- **Start (standard, no history):** `max(8, min_weekly_miles * 0.25)` from `VOLUME_TIER_THRESHOLDS` (Vega table → builder 20→**8** not 5).  
- **Curve:** linear in `plan_week` over `duration_weeks - 2` build weeks; taper weeks use `peak * 0.52` / `peak * 0.38`; **cutback × 0.70** on curve target.  
- **Legacy scaler calls** (no `plan_week` / `duration_weeks`): old `% of week` behavior for tests.  
- **Code:** `workout_scaler._scale_long_run`, `WorkoutScaler.scale_workout(..., duration_weeks, is_cutback, previous_easy_long_mi, history_override)`, `generator._generate_week` + `easy_long_state`.

**Remaining (P4):** merge `L30_max_easy_long` into baseline when generating from synced history.

### P2 — Weighted easy fill (`generator.py`) — **implemented**

**Intent:** Same weekly total; **vary** easy days by **same-week** adjacency:

- Day after quality: **0.7** share weight  
- Day before long (`long` / `long_mp` / `long_hmp`): **0.8**  
- Both: **0.56** (0.7×0.8)  
- Standalone easy: **1.2**  
- **Normalize** to hit `weekly_volume` remainder after non-easy miles; per-slot **[3, 12]** mi; iterative nudge if clamping drifts total.

**Code:** `PlanGenerator._apply_weighted_easy_volume_fill`, `_easy_fill_adjacency_weight`, `_EASY_FILL_*` type sets in `generator.py`.

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

**Minimum completion before acting on check-ins (Q4 — resolved):** **3 weeks** at **≥ 70%** workout completion; until then log signals only.

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

## Resolved Q&A (Vega + founder, 2026-03-22)

See **D1**, **D2** table, **D4** gates, **P1**, **P5** above. Founder amendment: **minimum easy long = 8 mi** for standard plans (not 5 mi on builder).

---

## Implementation order (recommended)

1. ~~P1 scaler curve + clamps~~ **done**  
2. ~~P2 weighted easy fill~~ **done**  
3. P3 narrative templates.  
4. P4 `LoadContext` + 30d spike + `max(L30, previous_planned)` baseline.  
5. P5 adaptation hook (≥3wk / 70% gate).
