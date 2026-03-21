# Plan generation — full audit & delta bridge (2026-03-22)

**Purpose:** Answer: *what plan generation is today*, *what it must become*, *what new tools exist*, and *how to bridge the gap* — across **all shipped distances** and **major code paths**.  
**Audience:** Founder + builders. **Not** a UI document.

---

## 1. Executive summary

| Dimension | Today | Target (north stars) |
|-----------|--------|----------------------|
| **Core schedule logic** | Single **`PlanGenerator`** (`plan_framework`) drives **standard / semi-custom / custom** after phases + weekly templates are fixed. **Workout shapes** come from **`WorkoutScaler`** (caps, progressions). | **Athlete-truth-first** schedules: coherent mix **by distance**, real cutbacks, no silent downshifts, long-run floors for high-data athletes (**recovery spec C1–C5**). |
| **Workout fluency (registry)** | **`workout_variant_id`** resolved **after** scaler output and **persisted** on `planned_workout` for framework v2 saves. Registry = **label + drift control**, **not** selection yet. | **Phase 3 exit:** selection/eligibility informed by **`build_context_tag`** + tests; **Phase 4:** full matrix + codegen (**WORKOUT_FLUENCY_BUILD_SEQUENCE**). |
| **“Horrendous” plans** | Causes are **not** missing variant IDs. They are **volume/intensity mix**, **gate/fallback interactions**, **cold-start**, and **distance-specific dominance** — called out explicitly in **PLAN_GENERATION_VISION_ALIGNMENT_RECOVERY_SPEC.md**. | Fix **prescription + gates + fallbacks** per P0-A–D in that spec; tighten **PlanValidator strict mode** when generator matches KB. |

**Bottom line:** Registry wiring is **necessary infrastructure** for trustworthy, explainable workouts later; **improving what is produced** means changing **`phase_builder` + `generator` + `workout_scaler` + quality gates + constraint/starter paths**, with **tests** as the contract.

---

## 2. Inventory — every way a plan gets built

| Path | Entry (API / service) | Engine | Typical athlete |
|------|-------------------------|--------|-----------------|
| **Framework standard** | `POST /v2/plans/standard` | `PlanGenerator.generate_standard` | Free tier: template + effort; saves via `_save_plan` |
| **Framework semi-custom** | `POST /v2/plans/semi-custom` | `generate_semi_custom` | Questionnaire + race date; paces if entitled |
| **Framework custom** | `POST /v2/plans/custom` | `generate_custom` | Pro; may use **DB history**, `AthleteProfile` hooks |
| **Model-driven** | `POST /v2/plans/model-driven` | `model_driven_plan_generator` | Elite / feature-flag path; **different** object model than `GeneratedPlan` |
| **Constraint-aware** | `POST /v2/plans/constraint-aware` | `constraint_aware_planner` + Fitness Bank | **Highest complexity**: themes, contracts, **quality gate**, **fallback** |
| **Starter** | `starter_plan.ensure_starter_plan` | semi-custom or standard + **cold-start guardrails** | Onboarding |
| **No-race / other** | `no_race_modes`, admin tools | various | Edge SKUs |

**Audit focus for “all distances”:** The **same** `PlanGenerator` stack is used for **5k, 10k, half_marathon, marathon** on standard/semi/custom. **Model-driven** and **constraint-aware** must be audited **separately** — they can violate athlete intent via gates/fallbacks even when the framework logic is fine.

---

## 3. Framework v2 — what it actually is

### 3.1 Constants (`plan_framework/constants.py`)

- **Distances:** `5k`, `10k`, `half_marathon`, `marathon` only (no ultra in this layer).
- **Volume tiers:** `builder`, `low`, `mid`, `high`, `elite` — **shared mileage bands across distances** (philosophy: mileage is mileage; race sets **mix**, not only ceiling).
- **Long-run peaks:** **Distance-specific** caps (e.g. marathon vs 5K long cap).
- **Source B limits:** threshold %, interval %, repetition %, MP caps — applied in **`WorkoutScaler`**.

### 3.2 Phase builder (`phase_builder.py`)

- **Separate phase graphs** per distance: `_build_marathon_phases`, `_build_half_marathon_phases`, `_build_10k_phases`, `_build_5k_phases`.
- **Taper:** `TAPER_WEEKS` by distance + optional **personalized taper days** → week conversion.
- **Output:** `TrainingPhase` list (week indices, `allowed_workouts`, `quality_sessions`, modifiers).

### 3.3 Weekly skeleton (`generator.py` — `WEEKLY_STRUCTURES`)

- **5 / 6 / 7** days per week → fixed slot types: `rest`, `easy`, `quality`, `long`, `medium_long`, `easy_strides`, `quality_or_easy`, etc.
- **Same skeleton** for all distances; **distance** only enters in **`_get_workout_for_day`**, **`_get_long_run_type`**, **`_get_quality_workout`**, **`_get_secondary_quality`**, and scaler routing.

### 3.4 Distance-specific behavior (generator — high level)

| Topic | Marathon | Half | 10K | 5K |
|--------|----------|------|-----|-----|
| **Long-run spice** | `long_mp` in marathon-specific / race-specific (alternating weeks) | `long_hmp` in race-specific (alternating) | Easy long only | Easy long only |
| **Primary quality (threshold phase)** | T-intervals → continuous T | Same pattern | Same pattern | Same pattern |
| **Race-specific quality** | T / T-intervals mix | T / T-intervals mix | **`intervals`** | **`intervals`** |
| **Base speed** | hills / strides; high-mileage → early **`intervals`** touch | Similar | **reps / hills / strides** cycle | **reps / hills / strides** cycle |
| **Cutback quality** | lighter T | lighter T | **strides** | **repetitions** |

### 3.5 Workout scaler (`workout_scaler.py`)

- **Single dispatch** `scale_workout(workout_type, …, distance=..., plan_week=..., phase=..., athlete_ctx=...)`.
- **Distance branches:** **`5k`** and **`10k`** get dedicated **`_scale_5k_intervals`** / **`_scale_10k_intervals`** progressions; default marathon path uses **1K-style** intervals unless base-speed branch fires.
- **Caps:** **10% / 8% / 5%** of weekly volume for T / I / reps (approximate mile conversions).
- **Volume fill:** After week generation, **easy / recovery / medium_long** miles adjusted so week hits `weekly_volume` target (min 3 mi, cap 12 mi per easy).

### 3.6 What the new fluency layer does **not** do (yet)

- **`workout_variant_dispatch.resolve_workout_variant_id`** maps **existing** title/type/segments → registry id. It does **not**:
  - choose between cruise vs broken threshold,
  - read **`build_context_tag`** or injury state,
  - change **which** workout type is scheduled.

That is **by design** for Phase 3 wiring; **selection** is Phase 3+ / Phase 4 per **WORKOUT_FLUENCY_REGISTRY_SPEC**.

---

## 4. Tests & “what good looks like” today

### 4.1 Plan validation matrix (`tests/test_plan_validation_matrix.py` + `plan_validation_helpers.py`)

- **Parametric matrix:** marathon, half, 10k, 5k × tiers × durations × 5–6 days — all run through **`generate_standard`** with a fixed start Monday.
- **Mode:** **`strict=False` (relaxed)** thresholds in CI for most rules — intentional buffer while generator ≠ strict KB (**see comments in `plan_validation_helpers.py`**).
- **Strict mode:** **`strict=True`** encodes **Source B**-aligned numbers; **Phase 1B** intent was to flip matrix to strict when generator is fixed.
- **Known xfail:** e.g. **marathon builder** MP % at very low volume — documented as **N=1 / scaling** boundary, not “ignore.”

### 4.2 Other high-signal tests (non-exhaustive)

- `test_plan_framework_system_coverage.py` — high-volume experienced + VO2 touch + no `tempo` emission.
- `test_plan_quality_recovery_v2.py` — recovery / founder-style scenarios.
- Recovery spec **§6** lists **required CI-gated** endpoint tests (many may still be aspirational — verify `grep` / CI).

---

## 5. North-star gaps (recovery spec vs framework)

**Source:** `docs/specs/PLAN_GENERATION_VISION_ALIGNMENT_RECOVERY_SPEC.md`

| Contract | Intent | Bridge to framework |
|----------|--------|-------------------|
| **C1** | Athlete truth through **fallback** | **constraint-aware** + **`plan_generation` router** — not `PlanGenerator` alone |
| **C2** | **High-data long-run floor** (10K/half/marathon rules) | **`plan_quality_gate`**, **`workout_prescription`**, possibly **volume fill** in generator |
| **C3** | **Coherent mix by distance** + variant rotation | **`_get_quality_workout` / `_get_secondary_quality` / phase allowances** + future **registry eligibility** |
| **C4** | **Real cutback** (volume, long, quality) | **Cutback flags** in `generator` + validator rules |
| **C5** | **Prediction payload** preserved | **model-driven** response contracts |

**P0-A–D** in that spec are the **ordered engineering** items for “plans stop being wrong for real athletes.”

---

## 6. Tools we now have (fluency / registry)

| Asset | Role in bridge |
|--------|----------------|
| **`workout_registry.json`** + pilot markdown | **Definitions** + **tags** for future eligibility |
| **`test_workout_registry.py`**, **`test_stem_coverage_sync.py`** | **Drift control** vs scaler stems |
| **`workout_variant_dispatch.py`** | **Stable id** on emitted shapes; enables **analytics, coach context, Phase 4 matrix** |
| **`planned_workout.workout_variant_id`** | **Persistence** for anything reading DB |
| **`scripts/show_framework_plan.py`** | **Dev/founder inspection** of raw schedule (not product UI) |

**Using them to improve logic:** Next step is **not** “more ids” — it is **(a)** drive **tests** that pin bad mixes (per distance), **(b)** change **generator/scaler/gates**, **(c)** optionally constrain **which variant** of a stem applies when multiple registry rows match (eligibility).

---

## 7. Delta bridge — **concrete** (strict validator + files + order)

This section replaces generic “tiers” with **observed `PlanValidator(strict=True)` rule IDs**, **which plan shape triggers them**, and **where to edit**.

### 7.0 Evidence snapshot (local, `generate_standard`, start Monday 2026-03-02)

| Case | Failures | Rule IDs (first) |
|------|----------|-------------------|
| marathon, **mid**, 18w, 6d | 2 | **B1-MP-PCT** (MP work > 20% of that week’s miles) |
| marathon, **high**, 18w, 6d | 5 | **B1-LR-PCT** (long run > 30% of weekly after easy-fill totals) |
| marathon, **low**, 18w, 5d | 1 | **MP-TOTAL-LOW** (total MP miles < 40 mi spec minimum) |
| marathon, **builder**, 18w, 5d | 3 | **B1-MP-PCT**, **VAL-NO-CUTBACK**, **MP-TOTAL-LOW** |
| half, **mid**, 16w, 6d | 0 | — |
| half, **builder**, 16w, 5d | 1 | **VAL-NO-CUTBACK** |
| 10k, **mid**, 12w, 6d | 0 | — |
| 10k, **builder**, 12w, 5d | 3 | **B1-I-PCT**, **B1-I-PCT**, **VAL-NO-CUTBACK** |
| 5k, **mid**, 12w, 6d | 0 | — |
| 5k, **high**, 12w, 6d | 0 | — |

**Interpretation:** Shorter-distance **mid/high 6d** plans already satisfy **strict Source B + structure** in this slice. The **immediate strict gap** is **marathon (MP %, long %, MP accumulation, cutbacks on low days/week)** and **10k builder interval % + cutback detection**.

---

### Bridge item 1 — **B1-MP-PCT** (marathon mid+)

- **Symptom:** MP work in `long_mp` session exceeds **20%** of that week’s **total** miles (validator: `plan_validation_helpers.assert_source_b_limits`).
- **Likely cause:** `WorkoutScaler._scale_mp_long_run` prescribes **MP miles** that are correct in isolation but **too large vs actual `weekly_volume`** for that week (especially after `_generate_week` easy-fill inflates week totals).
- **Edit locus:** `apps/api/services/plan_framework/workout_scaler.py` (`_scale_mp_long_run`, `_create_mp_option_b`) and/or **pass effective week target** into scaler from `generator.py` `_generate_week` so MP block is capped **after** knowing filled week total (may require two-pass or cap MP as % of `weekly_volume`).
- **Done when:** `PlanValidator(strict=True)` clean for **marathon mid 18w 6d** on fixed start date; add/regress **parametrized strict test** for the week numbers that failed.

---

### Bridge item 2 — **B1-LR-PCT** (marathon high)

- **Symptom:** Long run > **30%** of weekly miles (often **24 mi / 75 mi** class ratios).
- **Likely cause:** `LONG_RUN_PEAKS` + `_scale_long_run` (% of week) **combined** with `_generate_week` easy-fill: fill pushes week total up but long already at peak → **long share** breaches strict 30%.
- **Edit locus:** `generator.py` end-of-week volume fill (easy_types loop): **recompute long share** or **cap long** when enforcing weekly total; alternatively **raise weekly_volume target** from classifier so long % falls — pick one philosophy (prefer **explicit cap** so spec is satisfied).
- **Done when:** strict clean for **marathon high 18w 6d**; regression test pins worst week.

---

### Bridge item 3 — **MP-TOTAL-LOW** (marathon low / builder)

- **Symptom:** Sum of MP-quality miles across plan **< 40 mi** (`assert_mp_total`).
- **Likely cause:** Too few `long_mp` weeks or **too short** MP segments vs spec expectation for 18w marathon.
- **Edit locus:** `phase_builder.py` (race_specific / marathon_specific week count), `generator.py` `mp_week` progression and alternation, `workout_scaler.py` MP progression tables.
- **Done when:** strict clean for **marathon low 18w 5d** and **builder** case, or **documented waiver** in validator for true low-volume marathon if SME decides 40 mi floor is inappropriate for builder (then change **spec + test**, not silent drift).

---

### Bridge item 4 — **VAL-NO-CUTBACK** (builder + 5d, multi-distance)

- **Symptom:** `assert_cutback_pattern` finds **no cutback weeks** in 12–18w plans.
- **Likely cause:** `generator.py` cutback flags not firing for **5-day** structures or **builder tier frequency**; or validator expectation mismatch.
- **Edit locus:** `generator.py` (cutback / `is_cutback` propagation from `volume_tiers` / `CUTBACK_RULES`), then **`assert_cutback_pattern`** in `plan_validation_helpers.py` only if generator is correct and test is wrong.
- **Done when:** strict clean for **marathon builder 18w 5d**, **half builder 16w 5d**, **10k builder 12w 5d**.

---

### Bridge item 5 — **B1-I-PCT** (10k builder)

- **Symptom:** Interval **work** miles > **8%** of week when **weekly_volume ~28 mi** (small denominator).
- **Likely cause:** `_scale_10k_intervals` / rep count uses **max_i_miles** but **floor** on reps produces ~3 mi VO2 work → breaches **8%** at low volume.
- **Edit locus:** `workout_scaler.py` `_scale_10k_intervals` (and 5k sibling if same pattern): **hard cap** interval work miles to `min(8% * weekly_volume, interval_abs_mi)` **before** finalizing reps.
- **Done when:** strict clean for **10k builder 12w 5d**.

---

### Bridge item 6 — Recovery spec **P0-A** (constraint-aware / fallback)

- **Spec:** `PLAN_GENERATION_VISION_ALIGNMENT_RECOVERY_SPEC.md` §5 P0-A (athlete peak intent preserved through fallback).
- **Files:** `apps/api/routers/plan_generation.py`, `apps/api/services/constraint_aware_planner.py` (search: fallback, regenerate, `target_peak`).
- **Done when:** tests **P0-A** in spec §6 pass (preserve override on fallback); payload contract **422** with listed fields when hard-block.

---

### Bridge item 7 — Recovery spec **P0-B / P0-C** (gates + long-run floor)

- **Files:** `apps/api/services/plan_quality_gate.py`, `apps/api/services/workout_prescription.py`.
- **Done when:** spec tests **10k false flag**, **high-data long-run floor** pass; marathon/half not damaged by 10k-only thresholds.

---

### Bridge item 8 — Recovery spec **P0-D** (endpoint cohort tests)

- **Files:** new module under `apps/api/tests/` per spec §6 list; exercise **full HTTP path** including fallback branch.
- **Done when:** CI runs them green.

---

### Bridge item 9 — Registry **after** items 1–5 (optional sequencing)

- **Not parallel to 1–5:** `workout_variant_dispatch.py` does **not** fix B1-* or cutbacks.
- **Next use:** introduce **`resolve_eligible_variant_ids(stem, athlete_context)`** (new module) fed by **`AthletePlanProfile`** + registry tags; then **swap** scaler **prescription** only where SME approves (Phase 3 exit scope).
- **Done when:** contract tests per `WORKOUT_FLUENCY_REGISTRY_SPEC` §9 / Phase 4 matrix (separate milestone).

---

## 8. File map (quick reference)

| Area | Primary files |
|------|----------------|
| Framework orchestration | `apps/api/services/plan_framework/generator.py` |
| Phases | `apps/api/services/plan_framework/phase_builder.py` |
| Scaling / caps | `apps/api/services/plan_framework/workout_scaler.py` |
| Defaults / peaks | `apps/api/services/plan_framework/constants.py` |
| Volume classification | `apps/api/services/plan_framework/volume_tiers.py` |
| HTTP + save | `apps/api/routers/plan_generation.py` |
| Validation | `apps/api/tests/plan_validation_helpers.py`, `test_plan_validation_matrix.py` |
| Variant labels | `apps/api/services/plan_framework/workout_variant_dispatch.py` |
| Recovery north star | `docs/specs/PLAN_GENERATION_VISION_ALIGNMENT_RECOVERY_SPEC.md` |
| Fluency ladder | `docs/specs/WORKOUT_FLUENCY_BUILD_SEQUENCE.md`, `WORKOUT_FLUENCY_REGISTRY_SPEC.md` |
| Rebuild plan | `docs/TRAINING_PLAN_REBUILD_PLAN.md` |

---

## 9. Closing

- The **delta bridge** is now **ordered by measured strict failures** (§7.0–7.5) then **recovery P0 file targets** (§7.6–7.8) then **registry selection** (§7.9).  
- Re-run the §7.0 table after each bridge item; update the table in this doc when counts change.

*Update this document when strict matrix goes green or P0 items ship.*
