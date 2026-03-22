# Plan Generation — Comprehensive Path to World-Class N=1

**Status:** Advisor-scoped, pending founder approval  
**Date:** 2026-03-22  
**Author:** Top Advisor (Vega)  
**Read with:** `TRAINING_PLAN_REBUILD_PLAN.md`, `PLAN_COACHED_OUTPUT_AND_LOAD_CONTRACT.md`, `PLAN_GENERATION_FULL_AUDIT_2026-03-22.md`, `PLAN_GENERATION_VISION_ALIGNMENT_RECOVERY_SPEC.md`

---

## 1. Where we are (honest assessment)

### What's done and working

| Area | Status |
|------|--------|
| P1 — Long-run progression curve | Implemented in `workout_scaler._scale_long_run` |
| P2 — Weighted easy fill | Implemented in `generator._apply_weighted_easy_volume_fill` |
| P3.0 — MP long narrative | Implemented via `workout_narrative.mp_long_option_a_copy` / `option_b_copy` |
| P3.1 — Threshold continuous narrative | Implemented via `workout_narrative.threshold_continuous_description` |
| P3.2 — MP touch + HMP long narrative | Implemented via `workout_narrative.mp_touch_copy` / `hmp_long_copy` |
| P4 — LoadContext (standard + semi-custom) | `load_context.build_load_context` wired into `PlanGenerator` for standard and semi-custom |
| Inline deduplication | `mileage_aggregation.get_canonical_run_activities` in FitnessBank and volume_tiers |
| Validation matrix (standard path) | 528-line parametric matrix covering 4 distances × tiers × durations |

### What's broken or missing

| Area | Severity | Detail |
|------|----------|--------|
| **Starter plan goal date** | **P0 bug** | `_goal_date_from_intake` (starter_plan.py:66-69) returns `None` when intake HAS a date. Date parsing at lines 153-156 is dead code after `return plan` at line 152. Every new athlete with a race date gets a default 8-week plan. |
| **`generate_custom` NameError** | **P0 bug** | generator.py:684 references `recent_activities` — undefined in scope. Custom plan crashes if Priority 3 pace path is hit. |
| **Threshold intervals narrative not wired** | **P1 gap** | `threshold_intervals_description` defined in `workout_narrative.py` but never called from scaler. P3.1 marked "implemented" in spec; threshold interval copy still uses old generic text. |
| **Quality gate is 10K-only** | **Structural** | `plan_quality_gate.py` has distance-specific rules only for 10K (lines 41-72). Marathon, half, and 5K get one check: "any week > band_max × 1.15?" No MP progression, no HMP mix, no interval composition, no personal floor for 3 of 4 distances. |
| **LoadContext not in constraint-aware** | **Structural** | The most sophisticated generation path (`constraint_aware_planner.py`) uses FitnessBank but not LoadContext. P4 wired LoadContext into standard/semi-custom only. |
| **Two competing floor systems** | **Structural** | `plan_quality_gate._compute_personal_long_run_floor` (p75/p50, 10K only) and `load_context.build_load_context.l30_max_easy_long_mi` (30-day max, standard/semi only). Different data, different windows, different eligibility, different generation paths. No documented precedence when they disagree. |
| **Recovery spec §6: 4/10, all mocked** | **Coverage** | Tests 1, 8, 9, 10 exist in `test_constraint_aware_recovery_contract.py`. All mock the planner and gate — no real generation exercised. Tests 2-7 missing entirely. |
| **Validation matrix tests ONE path** | **Coverage** | All of `test_plan_validation_matrix.py` uses `generate_standard(db=None)`. Semi-custom, custom, model-driven, constraint-aware have zero parametric validation. |
| **Stale monetization in live code** | **Drift** | `pace_access.py` queries `PlanPurchase` for $5 one-time. Router uses `tier_satisfies("guided")`. `/options` returns `"price": 5`. `constants.py:15` says `# $5, questionnaire-based`. `feature_flags.py` references guided/premium hierarchy and `PlanPurchase`. |
| **Baseline snapshot in rebuild plan** | **Drift** | Lines 9-28 of `TRAINING_PLAN_REBUILD_PLAN.md` still show "Monetization: CONTRACT ONLY — 29 xfail" despite monetization being complete. |

---

## 2. The path (7 phases, ordered by dependency)

### Phase 0 — Stop the Bleeding

Production bugs affecting athletes right now. No architectural decisions. Builder-ready.

#### 0A: Fix starter plan goal date

**Files:** `apps/api/services/starter_plan.py`

**Problem:** `_goal_date_from_intake` (lines 66-69) has an early return on `if not s: return None` but when `s` IS truthy, the function falls off without returning — the `date.fromisoformat(str(s))` at lines 153-156 is dead code after `return plan` at line 152.

**Fix:** Move the `try: return date.fromisoformat(str(s)) except: return None` block into `_goal_date_from_intake` as the truthy-s path.

**Done when:** Starter plan with `goal_event_date = "2026-05-02"` in intake produces a plan ending on that date, not 8 weeks from today.

#### 0B: Fix `generate_custom` NameError

**Files:** `apps/api/services/plan_framework/generator.py`

**Problem:** Line 684 references `recent_activities` — undefined variable. If Priority 3 pace estimation fires, `NameError`.

**Fix:** Either query recent activities from DB (the `db` param exists in `generate_custom`) or guard with `if not paces and hasattr(self, '_recent_activities')` — whichever matches original intent. If no DB session is available, remove the dead Priority 3 path.

**Done when:** `generate_custom` with no race data and no RPI does not crash.

#### 0C: Wire threshold intervals narrative

**Files:** `apps/api/services/plan_framework/workout_scaler.py`, `apps/api/services/plan_framework/workout_narrative.py`

**Problem:** `threshold_intervals_description(reps, duration, prev)` exists but is never called from the scaler's threshold intervals path.

**Fix:** Call `threshold_intervals_description` from `_scale_threshold_intervals`, passing `prev_threshold_intervals` (already maintained in generator since P3.1 work).

**Done when:** Threshold interval workouts show progression-aware descriptions ("Progressing from 4×5 to 5×5 min...") instead of generic copy.

#### 0D: Scrub stale monetization from code

**Files and changes:**

| File | Line(s) | Change |
|------|---------|--------|
| `core/pace_access.py` | 1-16, 43-58 | Remove `PlanPurchase` import and query; update docstring to reflect 2-tier model. Access = admin/owner OR `has_active_subscription` OR `tier_satisfies("subscriber")`. |
| `routers/plan_generation.py` | 1-11 | Update module docstring: remove "$5" and "purchase" language |
| `routers/plan_generation.py` | ~419 | Remove `"price": 5` from `/options` semi-custom response |
| `routers/plan_generation.py` | docstrings mentioning "blurred", "nulled" | Update to reflect current model (paces always shown; coach gated by subscription) |
| `services/plan_framework/constants.py` | 15-16 | Remove `# $5, questionnaire-based` and `# Subscription, full personalization` comments |
| `services/plan_framework/feature_flags.py` | 296, 302, 309 | Update docstrings; remove `PlanPurchase` path if unused |

**Done when:** `rg '\$5|PlanPurchase|blurred|nulled' apps/api/services/plan_framework/ apps/api/routers/plan_generation.py apps/api/core/pace_access.py` returns zero matches (excluding comments that reference the old model historically).

**Note on `tier_satisfies("guided")`:** Verify whether `"subscriber"` is now the canonical tier string in the Athlete model. If so, replace `"guided"` with `"subscriber"` in all `tier_satisfies` calls. If the model still uses `"guided"` as a DB value for historical subscribers, add a mapping — do not leave production code referencing a tier name that doesn't exist in the product.

---

### Phase 1 — Make the Validation Matrix Real

Before changing generator logic, prove what's actually failing across all paths. Pure test infrastructure — no generator changes.

#### 1A: Extend matrix to `generate_semi_custom`

**Files:** `apps/api/tests/test_plan_validation_matrix.py`

Add a `SEMI_CUSTOM_VARIANTS` parametrize set that calls `PlanGenerator(db=None).generate_semi_custom(...)` for the same distance × tier × duration grid. Semi-custom is the primary path for athletes with race dates and the path that uses LoadContext.

**Done when:** Semi-custom matrix runs alongside standard matrix in CI; failures documented.

#### 1B: Add constraint-aware smoke matrix

**Files:** New test module or extend `test_plan_quality_recovery_v2.py`

Create 2-3 synthetic profiles (high-data experienced, moderate, cold-start) × 4 distances that exercise `generate_constraint_aware_plan` with synthetic FitnessBank data (no real DB needed — use fixtures). Run through `evaluate_constraint_aware_plan` gate.

**Done when:** Constraint-aware path has parametric coverage for all 4 distances in CI.

#### 1C: Real generation in recovery spec tests

**Files:** `apps/api/tests/test_constraint_aware_recovery_contract.py`

Replace monkeypatched planner/gate in tests 1 and 10 with real `ConstraintAwarePlanner` + real `evaluate_constraint_aware_plan`. These tests should prove the full pipeline, not just the HTTP envelope.

**Done when:** Tests 1 and 10 generate real plans and verify real gate behavior.

#### 1D: Fix 5K emphasis contradiction

**Files:** `apps/api/tests/test_plan_validation_matrix.py`

`test_5k_emphasis` docstring says "VO2max dominant (I > T)" but validator enforces T ≥ I. Either the docstring or the validator is wrong. Check against the phase builder and Source B: 5K race-specific phase allows `intervals` — is the intent that total interval miles exceed threshold miles? Resolve and align.

**Done when:** Docstring matches validator behavior and both match the coaching intent.

---

### Phase 2 — Quality Gate for All Distances

The single highest-leverage structural fix. The gate currently cannot catch bad plans for 3 of 4 distances.

**Files:** `apps/api/services/plan_quality_gate.py`

#### 2A: Marathon gate rules

| Rule | Check |
|------|-------|
| MP progression | At least N `long_mp` sessions across plan (N scales with duration) |
| MP total floor | Sum of MP-quality miles ≥ tier-appropriate minimum (align with `assert_mp_total` in validators) |
| Long-run progression | Long runs trend toward `peak_long_run_miles` over build weeks |
| Cutback reality | At least one week with ≥15% volume drop (align with `assert_cutback_pattern`) |

#### 2B: Half gate rules

| Rule | Check |
|------|-------|
| HMP presence | At least one `long_hmp` session in race-specific phase |
| Threshold balance | Threshold work present in threshold phase |
| No marathon artifacts | No `long_mp` sessions in half plans |

#### 2C: 5K gate rules

| Rule | Check |
|------|-------|
| Interval presence | `intervals` or `repetitions` present in race-specific phase |
| No long-distance artifacts | No `long_mp`, no `long_hmp` |

#### 2D: Personal floor for all distances

Extend `_compute_personal_long_run_floor` to accept any `race_distance` and apply distance-appropriate minimums:

| Distance | Injury floor minimum |
|----------|---------------------|
| Marathon | 12.0 mi |
| Half / 10 mile | 10.0 mi |
| 10K | 10.0 mi (current) |
| 5K | 8.0 mi |

Apply floor enforcement in weeks 1-2 for all distances when athlete is high-data eligible.

**Done when:** Each distance has at least 3 gate rules beyond the generic volume check. Phase 1 tests exercise them.

---

### Phase 3 — Reconcile Floor Systems

Two systems compute "how long should this athlete's long run be." World-class N=1 needs one answer.

#### 3A: Define unified `compute_athlete_long_run_floor`

**Files:** New function in `plan_quality_gate.py` or shared utility

Formula (proposed — founder to approve):

```
unified_floor = max(
    l30_max_easy_long_mi,      # recent peak (30 days, ≥90 min, non-race)
    recent_8w_p75_long_run,    # sustained capacity (8 weeks)
    recent_16w_p50_long_run    # deeper history (16 weeks)
)
```

Eligibility: `recent_16w_run_count ≥ 24` AND `peak_long_run_miles ≥ 13` (current p75/p50 criteria).

Injury adjustment: `floor × 0.90`, with distance minimums per Phase 2D.

#### 3B: Wire unified floor into constraint-aware path

Pass `unified_floor` into `constraint_aware_planner` as part of the generation context. Apply at week-1 easy long seed and as final gate invariant.

#### 3C: Deprecate separate floor computations

`load_context.build_load_context.l30_max_easy_long_mi` and `plan_quality_gate._compute_personal_long_run_floor` both delegate to the unified function.

**Done when:** One function, one formula, used everywhere. Gate and generator agree.

**Founder decision needed:** Is `max(L30, p75_8w, p50_16w)` the right formula? This is the most generous interpretation — it says "you've proven you can do this distance." Alternative: `max(L30, p75_8w)` (drops the 16-week tail). Your call.

---

### Phase 4 — Complete Recovery Spec §6

With Phases 1-3 done, the 6 missing tests become meaningful and exercisable.

**Files:** `apps/api/tests/test_constraint_aware_recovery_contract.py` (expand) or new module

| # | Test | What it proves |
|---|------|----------------|
| 2 | `test_high_data_10k_long_run_floor_not_breached` | Unified floor works end-to-end for 10K |
| 3 | `test_10k_valid_high_mileage_plan_not_false_flagged` | Gate doesn't reject good high-mileage 10K plans |
| 4 | `test_marathon_not_10k_gated` | Distance isolation — marathon gate rules don't inherit 10K artifacts |
| 5 | `test_half_quality_mix_remains_threshold_mp` | Half plans have correct HMP/threshold mix |
| 6 | `test_cutback_is_real_reduction` | Cutback weeks have genuine volume + intensity drops |
| 7 | `test_prediction_contract_unchanged` | Prediction payload fields present and populated |

**Done when:** 10/10 recovery spec tests pass in CI using real generation (not mocks).

---

### Phase 5 — LoadContext into Constraint-Aware

The constraint-aware path is the most important path for experienced athletes. It uses FitnessBank but not LoadContext.

#### 5A: Build LoadContext inside constraint-aware planner

FitnessBank already queries canonical activities. Extract `l30_max_easy_long_mi` and `history_override_easy_long` from the same activity data (or call `build_load_context` alongside FitnessBank).

#### 5B: Use L30 as easy-long seed

When constraint-aware generates the plan, use `l30_max_easy_long_mi` as the week-1 easy long floor (same as standard/semi-custom behavior).

#### 5C: Apply D4 history override

For athletes with dense 15+/18+ long-run history (`count_long_15plus`, `count_long_18plus`, `recency_last_18plus_days`), allow higher starting long and larger spike allowance — per the spike table in `PLAN_COACHED_OUTPUT_AND_LOAD_CONTRACT.md` §D4.

**Done when:** Constraint-aware plans for experienced athletes start at appropriate long-run distances matching their recent training, not template defaults.

---

### Phase 6 — Flip to Strict Validation

After Phases 0-5, the generator should satisfy Source B rules. Make it prove it.

#### 6A: Run full matrix with `strict=True`

Execute `test_plan_validation_matrix.py` with strict thresholds across standard + semi-custom.

#### 6B: Fix remaining failures

Likely candidates:
- MP% on specific marathon cutback weeks (B1-MP-PCT) — may need scaler MP cap relative to actual weekly volume
- Interval% on builder 10K (B1-I-PCT) — may need hard cap on interval miles at low weekly volume

#### 6C: Remove unjustified xfails

Any xfail that exists because "the generator can't pass this yet" — either fix the generator or get a documented founder waiver for that specific case.

#### 6D: Strict mode in CI

Add `strict=True` as a required CI check. Plans that violate Source B limits fail the build.

**Done when:** `PlanValidator(strict=True)` passes for all 4 distances × all relevant tiers, and CI enforces it.

---

### Phase 7 — Document Cleanup

#### 7A: Update baseline snapshot

`TRAINING_PLAN_REBUILD_PLAN.md` lines 9-28: update phase table, test counts, and xfail counts to reflect current reality. Remove "Monetization: CONTRACT ONLY — 29 xfail."

#### 7B: Update audit evidence table

`PLAN_GENERATION_FULL_AUDIT_2026-03-22.md` §7.0: re-run the strict validator evidence snapshot after each phase and update counts.

**Done when:** Every guiding document accurately reflects current state.

---

## 3. Deferred (by design)

| Item | Why | Trigger |
|------|-----|---------|
| **10-mile as `Distance`** | Framework enum doesn't include it. Founder decision: add as first-class distance or map 10-mile races to half-marathon training. | Founder decides |
| **P5 adaptive modulation** | Requires 3+ weeks at ≥70% completion before acting. Build the hook; it only fires after the plan has been running. | After Phases 0-6 |
| **Ultra / 50K** | Phase 4 in rebuild plan. New primitives (back-to-back longs, time-on-feet, nutrition). Separate scope. | Post-core stabilization |
| **Registry-driven workout selection** | `workout_variant_dispatch` maps IDs; selection from `build_context_tag` is Phase 3+/4 per fluency spec. Not needed for "world-class" — needed for "evolving." | After strict matrix is green |
| **Option B segment math** | Cooldown hardcoded at 2mi; segments can be inconsistent with `total_miles`. Low-priority cosmetic. | When athletes notice |

---

## 4. Execution model

- **Phase 0:** Builder-ready now. No founder decisions needed. Ship immediately.
- **Phase 1:** Builder-ready. Test infrastructure only. No generator changes.
- **Phase 2:** Needs brief founder review of gate rule set (are these the right checks per distance?). Then builder-ready.
- **Phase 3:** **Founder decision required** on unified floor formula before build.
- **Phase 4:** Builder-ready after Phases 1-3.
- **Phase 5:** Builder-ready after Phase 3.
- **Phase 6:** Builder-ready after Phases 0-5. May surface new generator fixes.
- **Phase 7:** Advisor or builder, anytime after Phase 6.

**Critical path:** 0 → 1 → 2 → 3 (founder decision) → 4+5 (parallel) → 6 → 7

---

## 5. Founder approval

- [ ] Phase 0 scope approved
- [ ] Phase 1 scope approved
- [ ] Phase 2 gate rules approved per distance
- [ ] Phase 3 unified floor formula approved: `max(L30, p75_8w, p50_16w)` or alternative
- [ ] 10-mile decision: add to `Distance` enum or map to half-marathon training
- [ ] Full path approved — proceed with execution
