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

## 7. Delta bridge — recommended sequence

### Tier A — Make the **framework** defensible (all distances)

1. **Run matrix in `strict=True`** on a branch; collect **failures** → single backlog ordered by severity (injury risk first).
2. **Fix `generator` / `workout_scaler`** where rules contradict **PLAN_GENERATION_FRAMEWORK.md** / Source B.
3. **Volume fill:** audit **easy fill** interactions with **low-volume** and **taper** weeks (common “looks insane” source).
4. **Half / 10K / 5K:** explicit review of **`_get_secondary_quality`** and **7-day `quality_or_easy`** — highest risk of **double quality** or **wrong touch**.

### Tier B — Recovery spec P0 (production failures)

5. **P0-A** fallback intent — **constraint-aware** + router.  
6. **P0-B / P0-C** — **`plan_quality_gate`** + prescription **distance-aware** thresholds and **long-run floor**.  
7. **P0-D** — **endpoint-level** tests with fallback branch.

### Tier C — Use registry to **tighten** logic (after A/B moving)

8. **Map** each scaler “shape” to **one default variant** + **alternates** by `build_context_tag` (injury_return, minimal_sharpen, etc.) — requires **`AthletePlanProfile`** or equivalent signal.
9. **Phase 4** eligibility matrix tests **replace** snapshot stubs per fluency spec.

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

- **“All distances, all variations”** in **one** audit means: **framework matrix** (standard) is shared; **paid / elite** paths add **different failure modes** (gates, Fitness Bank, fallbacks).  
- **Registry work** gives you **IDs and KB linkage**; **competence** is **`PlanGenerator` + scaler + gates + athlete truth**.  
- The **bridge** is **strict validators → fix code → recovery P0 → then eligibility-driven variant choice**.

*This document is an audit snapshot; update it when strict matrix goes green or P0 items ship.*
