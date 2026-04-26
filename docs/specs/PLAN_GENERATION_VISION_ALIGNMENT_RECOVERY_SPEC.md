# Plan Generation Vision Alignment Recovery Spec (Northstar Review)

**Status:** Draft for review  
**Owner:** Rook  
**Priority:** P0  
**Goal:** Restore minimum competent global plan generation and re-align behavior with athlete-truth-first vision.

---

## 1) Problem Statement

Current plan generation has crossed below baseline coaching competence in production for at least one high-data athlete profile. This is not a single tuning issue; it is an architecture and control-flow issue where:

1. Athlete truth is not preserved through fallback/regeneration paths.
2. Multiple layers can clamp/downshift plans independently.
3. Quality gates can pass "safe-looking but wrong-for-athlete" outputs.
4. Invariants are not enforced end-to-end at the endpoint level.

---

## 2) Is This Only a 10K Problem?

**No.**  
10K is where failures were most visible, but there are cross-distance failure vectors.

### 10K-specific amplification
- 10K has additional long-run dominance gating and composition constraints.
- Previous gate thresholds could trigger false "dominance" and force fallback/downshift.
- 10K distance logic intentionally disables MP long runs and shifts quality mix, making gate interactions more sensitive.

### Cross-distance shared risk (all distances)
- Fallback/regeneration path can replace athlete intent with safety peak.
- Volume contract clamps can compress weekly targets regardless of race distance.
- FitnessBank confidence/band derivation and cache state can affect all race types.
- Multi-layer controls (theme %, contract bounds, injury clamp, quality gate) can compound and erase athlete truth.

### Distance risk assessment
- **5K:** medium risk (sensitive to short-distance caps and long-run floor logic).
- **10K:** high risk (known failures + extra gating sensitivity).
- **10 mile/half:** medium-high risk (shared clamp/fallback path + MP/threshold mix interactions).
- **Marathon:** medium risk (shared fallback/contract path; long-run floor generally less aggressively capped).

---

## 3) Current Architecture (Relevant Paths)

### Constraint-aware endpoint
`POST /v2/plans/constraint-aware`:
1. Build FitnessBank.
2. Build `volume_contract`.
3. Generate themes + weekly targets.
4. Generate workouts.
5. Run quality gate.
6. On fail: regenerate once with fallback profile.
7. Save plan.

### Starter path
`starter_plan.ensure_starter_plan`:
1. Generate semi-custom or standard.
2. Apply cold-start guardrails when no history.
3. Starter quality gate.
4. Optional single retry.
5. Save.

### Key issue
The fallback and gate behavior can violate athlete-truth intent unless explicit invariants are carried and enforced through both passes.

---

## 4) Recovery Contracts (Hard Requirements)

These are pass/fail, not preferences.

### C1. Athlete truth continuity through fallback
- Fallback must never silently replace explicit athlete override intent.
- Response must include requested/applied/clamped/clamp_reason fields.
- If fallback cannot satisfy invariants with athlete intent preserved, return explicit hard-block error.

### C2. Long-run invariant for high-data athletes
- For athletes with dense history + proven long-run capacity, generated long-run start cannot fall below personal floor unless explicit injury constraint justifies it.
- Personal floor must be enforced at final gate stage (not only prescription layer).

**Locked personal floor definition (P0):**
- High-data athlete eligibility:
  - at least 24 run activities in the last 16 weeks, and
  - `peak_long_run_miles >= 13`.
- Compute weekly long-run maxima from canonical runs:
  - `recent_8w_p75_long_run`
  - `recent_16w_p50_long_run`
- `personal_floor = max(recent_8w_p75_long_run, recent_16w_p50_long_run)`.
- If `constraint_type == INJURY`, apply injury adjustment:
  - `injury_floor = personal_floor * 0.90`,
  - but never below `10.0` for 10K/10 mile/half and never below `12.0` for marathon.
- Final gate invariant:
  - first two build weeks must have `long_run >= applicable_floor`.

### C3. Workout-type and variant competency
- Build weeks must contain coherent mix by distance:
  - 5K: VO2/speed/threshold mix.
  - 10K: threshold/VO2 with no marathon-style dominance.
  - Half/10 mile: threshold+MP integration.
  - Marathon: MP+threshold with long-run progression.
- Variants must rotate sensibly (strides/hills/interval patterns) and avoid repeated stale templates.

### C4. Cutback and consolidation
- Every 3-4 build weeks includes a real cutback:
  - weekly load reduction,
  - long-run reduction,
  - quality reduction.
- No fake cutback labels where stress remains flat/higher.

### C5. Prediction contract preservation
- No regression to:
  - `time`
  - `confidence_interval`
  - `rationale_tags`
  - `scenarios`
  - `uncertainty_reason`

---

## 5) P0 Implementation Scope

### P0-A: Fallback intent preservation (all distances)
**Files:**
- `apps/api/routers/plan_generation.py`
- `apps/api/services/constraint_aware_planner.py`

**Implement:**
- Preserve explicit `target_peak_weekly_miles` / range across fallback regeneration.
- Do not auto-substitute fallback peak when explicit athlete intent exists.
- If fallback still fails, hard-block with actionable reasons and explicit payload contract.

**Fail-closed payload contract (locked):**
- HTTP `422`
- Body:
  - `error_code: "quality_gate_failed"`
  - `quality_gate_failed: true`
  - `quality_gate_fallback: true|false`
  - `reasons: string[]`
  - `invariant_conflicts: string[]`
  - `suggested_safe_bounds`:
    - `weekly_miles: { min: number; max: number }`
    - `long_run_miles: { min: number; max: number }`
  - `volume_contract_snapshot`:
    - `band_min`, `band_max`, `source`, `peak_confidence`, `requested_peak`, `applied_peak`, `clamped`, `clamp_reason`
  - `next_action: "adjust_inputs_or_accept_safe_bounds"`

### P0-B: Distance-aware gate correction
**Files:**
- `apps/api/services/plan_quality_gate.py`

**Implement:**
- Recalibrate 10K gate thresholds to avoid false positives for valid high-mileage 10K plans.
- Add distance-aware guard rules for non-10K plans (half/marathon) to prevent analogous failures.

### P0-C: High-data long-run floor protection
**Files:**
- `apps/api/services/workout_prescription.py`
- `apps/api/services/plan_quality_gate.py`

**Implement:**
- Add high-mileage 10K long-run start floor for proven high-volume athletes.
- Encode final quality-gate check to reject outputs below personal floor where data confidence is high.

### P0-D: End-to-end cohort validator (endpoint-level)
**Files:**
- `apps/api/tests/*` (new endpoint-level test module)

**Implement:**
- Full path tests through endpoint logic (including fallback branch), not only component tests.
- Validate per cohort: volume trajectory, long-run progression, workout mix/variants, gate behavior.

---

## 6) Required Test Matrix (CI-gated)

1. `test_constraint_aware_preserves_override_on_fallback`
2. `test_high_data_10k_long_run_floor_not_breached`
3. `test_10k_valid_high_mileage_plan_not_false_flagged_by_gate`
4. `test_marathon_valid_long_run_progression_not_10k-gated`
5. `test_half_distance_quality_mix_remains_threshold_mp`
6. `test_cutback_week_is_real_reduction_in_volume_long_quality`
7. `test_prediction_contract_unchanged_endpoint_response`
8. `test_fallback_hard_blocks_when_invariants_conflict`
9. `test_personal_floor_formula_matches_p75_p50_definition`
10. `test_quality_gate_failed_payload_contract_shape`

---

## 7) Acceptance Criteria

### Founder-like high-mileage 10K
- Long run starts at/above personal floor (data-supported), not collapsed low.
- Week 2 build can reach expected high-mileage trajectory when requested and safe.
- Quality mix reflects 10K structure (not marathon clone).

### Other distances
- Marathon/half/10 mile/5K pass distance-specific mix and progression checks.
- No distance receives 10K-specific gate artifacts.

### Global
- Fallback no longer mutates explicit athlete intent.
- All cohort endpoint tests green in CI.
- Production samples validate cohort behavior.

---

## 8) Rollout Plan

1. Merge P0 with tests.
2. CI green required.
3. Deploy.
4. Run production sample script for each cohort.
5. If any cohort fails -> rollback and hold.

---

## 9) Evidence Required in Handoff

1. Commit SHA(s) + file list.
2. Full test output (including endpoint cohort tests).
3. Distance matrix before/after table:
   - weekly totals,
   - long-run sequence,
   - workout mix/variants,
   - volume contract and fallback metadata.
4. CI run URL + green status.
5. Production sample payloads for 10K, half, marathon, and cold-start.

---

## 10) Northstar Decisions Needed

1. Approve that this is **cross-distance architecture risk**, not 10K-only.
2. Approve endpoint-level cohort tests as release gate (mandatory).
3. Approve fail-closed behavior when athlete invariants conflict with safety fallback.
4. Approve distance-aware gate thresholds as policy surface (versioned).

