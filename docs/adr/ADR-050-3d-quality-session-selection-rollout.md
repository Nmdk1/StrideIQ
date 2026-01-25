# ADR-050: 3D Quality-Session Selection Rollout (Deterministic Core + Shadow Mode)

## Status
**Proposed**

## Date
2026-01-23

## Context

Quality sessions are the highest-risk, highest-signal part of a training plan:
- They drive adaptation (positive ROI) and injury risk (negative ROI).
- They are where advanced athletes immediately detect “template plans” and churn.
- They must be explainable, auditable, and constrained.

StrideIQ’s N=1 mandate is explicit:
> Population averages are noise. The individual is the signal.

Therefore, quality-session generation must **not** depend on population “rules of thumb” as the governing logic. Population defaults may exist only as cold-start placeholders and must be displaced as athlete evidence accumulates.

We already have a deterministic “3D template selection” model defined and implemented:
- **ADR-036** defines the 3D model: **Periodization (phase) × Progression (τ1-informed) × Variance**.
- `apps/api/services/workout_templates.py` implements the selector and emits a detailed `audit_log`.
- `apps/api/services/model_driven_plan_generator.py` can use the selector for `quality` and `sharpening` day slots.

The remaining gap is “production-grade rollout rigor”:
- off/shadow/on gating
- audit logging that is stable and minimally sensitive
- cohort rebuild/verification protocol

## Decision

Adopt/refine the existing 3D model as the deterministic core for quality sessions, and roll it out with **shadow mode** first.

### Deterministic core (3D model)

Each selected quality session is produced by evaluating workout templates across:

1. **Periodization**: template `phases` matched to current phase.
   - Applied as a **soft weight** scaled by `DataTier` (stronger guardrails for cold-start, weaker for calibrated).

2. **Progression**: template `progression_week_range` matched against τ1-adjusted progress within the phase.
   - Progression speed is athlete-specific (τ1), not a population-based progression schedule.

3. **Variance**: template `stimulus_type` + `dont_follow` + recent-repeat penalties.
   - Prevents monotony and avoids consecutive identical stressors.

**Important refinement (approved):** the engine must choose the **workout “Type”** itself (e.g. threshold vs intervals vs hills / sharpening) from a **phase-specific allowlist**, rather than having the phase hard-fix the type. This preserves structure (phase guardrails) while enabling N=1 adaptability (type choice responds to constraints + variance + athlete context).

Hard constraints apply:
- `requires` is a **hard exclude** (cannot schedule what the athlete cannot execute).

N=1 weighting applies when data sufficiency supports it:
- Response history (`athlete_workout_response`) and banked learnings (`athlete_learning`) influence selection.

### Feature flags (off/shadow/on)

We roll out using two boolean flags (current flag system is boolean-only):

- **ON**: `plan.3d_workout_selection`
- **SHADOW**: `plan.3d_workout_selection_shadow`

Mode resolution in plan generation:
- If `plan.3d_workout_selection` enabled → **on** (serve 3D selection)
- Else if `plan.3d_workout_selection_shadow` enabled → **shadow** (compute 3D + log diffs, serve legacy)
- Else → **off** (legacy only)

Shadow mode means:
- For each `quality`/`sharpening` slot, compute 3D selection and emit a structured audit event.
- Continue serving the legacy workout for that slot (no plan behavior change).

## Considered Options (Rejected)

### Option A: Hard phase filter + static rotation
**Rejected:** Enforces population-ish rigidity and limits N=1 adaptation. Also fails auditability when exceptions accumulate.

### Option B: LLM-generated workouts for quality days
**Rejected:** Hard to constrain reliably; higher hallucination and prompt-injection surface; variance/constraints become fragile; violates the trust contract.

### Option C: ML recommender model
**Rejected:** Cold-start is worst; explanations become post-hoc; operational debugging is harder; not necessary to achieve deterministic, auditable N=1 behavior.

## Consequences

### Positive
- Quality sessions become explainable and auditable (template ids, scores, filters, reasons).
- Variance reduces monotony and prevents accidental stress stacking.
- “Observe → Hypothesize → Intervene → Validate” becomes feasible because templates are explicit hypotheses.
- Shadow mode allows validating selection behavior without impacting athletes.

### Negative
- More complexity than hardcoded prescriptions.
- Requires careful telemetry hygiene (logs contain athlete ids and selection traces).
- Exploration introduces non-determinism if enabled (must be controlled/seeded for reproducibility).

## Rationale (N=1, no population averages)

The governing logic is athlete-specific evidence:
- Data tier determines how conservative we must be.
- τ1 adjusts progression and taper behavior based on the athlete’s adaptation speed.
- Response history and banked learnings amplify or suppress stimuli/templates that this athlete has demonstrated as effective or harmful.

Population values exist only as initial defaults (cold-start), and are explicitly displaced as athlete evidence accumulates.

## Audit Logging Requirements (Minimum)

Every 3D selection must emit a single structured event containing:
- `timestamp`
- `athlete_id` (UUID; treat as sensitive)
- `plan_generation_id` (non-persisted id for correlating a single generation run)
- `date`, `day_of_week`
- `phase`, `week_in_phase`, `total_phase_weeks`
- `data_tier`, `tau1_used`
- `recent_quality_ids` window used for variance
- candidate/filter counts (phase/progression/variance/constraints)
- **Type selection (required):**
  - `type_allowlist` (phase-specific allowlist of types considered valid)
  - `type_selected`
  - `type_previous` (immediate predecessor type, if known)
  - `type_candidates_counts` (counts by type after hard constraints)
- `selection_mode` (explore/exploit/fallback), `explore_probability`
- `selected_template_id`, `final_score`, `selection_reason`
- in shadow mode: legacy slot info (`legacy_workout_type`, `legacy_title`)

Logs must remain template-centric; do not dump raw activity history or HR time-series.

## Test Strategy

### Unit invariants
- Constraints (`requires`) are hard excludes.
- `dont_follow` and recent-repeat rules apply.
- Seeded selection is deterministic.
- Audit payload contains required keys.

### Integration scenarios
- Phase transition week: base → build.
- Late-build variance pressure: ensure alternation vs repeats.
- Taper-only: sharpening/low-fatigue behavior.
- Shadow mode: generate both, serve legacy, emit diffs.

## Security / Privacy Considerations

- Audit logs contain athlete UUIDs and must be treated as sensitive telemetry (access control, retention, encryption at rest).
- Avoid logging raw activity identifiers or detailed physiological time-series in selection logs.
- Template library is read-only at runtime; edits must be code-reviewed.
- Plan rebuild endpoints must enforce authorization (no cross-athlete regeneration).

## Rollout / Verification Process

1. Enable **shadow** for a small allowlisted cohort (elite testers).
2. Regenerate plans for representative cohorts (calibrated/learning/cold-start; taper; facility constrained).
3. Verify:
   - No invalid phase selections (especially taper).
   - Variance rules applied; no obvious monotony.
   - Fallback rate not increased.
   - Load/intensity remains within expected bounds.
4. Only then enable **on** for the same allowlist, then expand rollout percentage.

## Related ADRs

- ADR-036: N=1 Learning Workout Selection Engine
- ADR-038: N=1 Long Run Progression

