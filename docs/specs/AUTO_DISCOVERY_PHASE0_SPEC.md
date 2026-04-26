# AutoDiscovery Phase 0 — Shadow Research Platform

**Date:** March 11, 2026
**Status:** Proposed build spec
**Owner:** Top advisor
**Depends on:** `docs/BUILD_ROADMAP_2026-03-09.md`, `docs/specs/AUTOINVESTIGATION_LOOP_SPEC.md`, `docs/specs/DAILY_EXPERIENCE_GUARDRAIL_SPEC.md`
**Build target:** Founder-only shadow mode first, rollout-ready architecture for all athletes

---

## Why This Exists

The original `AUTOINVESTIGATION_LOOP_SPEC.md` captured an important idea but framed it too narrowly around tuning existing investigations.

The actual product direction is broader:

- continuously rescan the full 70+ input universe
- test pairwise interactions and grouped effects
- tune existing investigations where tuning improves finding quality
- do all of that in shadow mode first
- surface nothing athlete-facing until the system proves it is getting smarter rather than merely busier

This spec defines the first buildable version of that platform.

The goal is not "AI for AI's sake."

The goal is to create a founder-only nightly research substrate that makes StrideIQ's understanding of a single athlete compound over time, with full logging, scoring, and rollback safety.

---

## Product Intent

StrideIQ should become a living research instrument aimed at one human body.

Every night, the system should be able to:

1. Re-examine the athlete's full history, not just the most recent 90 days
2. Compare findings across multiple windows
3. Test whether interactions between signals are stronger than isolated signals
4. Tune existing investigation parameters in shadow mode
5. Score whether candidate changes actually improve the value of findings
6. Keep a complete record of what it tried and what got better

Phase 0 is the foundation for that platform.

It is **not** the final "hidden physiological grammar" engine.

---

## Scope

Phase 0 includes three founder-only shadow loops running under one orchestration layer:

### Track A: Correlation Rescan Loop

Extends the existing correlation engine into a shadow research mode that rescans the full input universe across multiple windows.

Purpose:
- distinguish stable findings from recent-only findings
- detect lag drift across time windows
- detect findings that strengthen only in longer history
- create a richer evidence base for future surfacing

### Track B: Pairwise Interaction Loop

Extends the current combination-correlation path into a persisted shadow discovery loop.

Purpose:
- identify input pairs whose combined effect is stronger than either signal alone
- score interaction findings in shadow mode
- persist interaction candidates for review rather than dumping one-off responses

### Track C: Registry Tuning Loop

Adds tunable parameter metadata to a pilot subset of existing investigations and runs shadow parameter experiments.

Purpose:
- improve existing investigations without rewriting their underlying logic
- learn per-athlete windows, sensitivities, and thresholds safely
- create the architecture for future optimization without requiring production mutation

---

## Build Slicing (Required)

Phase 0 is intentionally broad. To keep risk controlled and avoid pseudo-shipping,
implementation must be sliced into two buildable steps:

### Phase 0A (Foundation, ship first)

Deliver only:

1. Experiment ledger persistence:
   - `auto_discovery_run`
   - `auto_discovery_experiment`
2. Founder-only orchestrator task scaffold that:
   - runs in shadow mode
   - writes run + experiment rows
   - writes the structured nightly report
   - guarantees no athlete-facing mutation
3. FQS v1 adapter interfaces and initial implementation:
   - `CorrelationFindingFQSAdapter`
   - `AthleteFindingFQSAdapter`
4. Founder-only feature flags and athlete allowlist gating
5. One pilot loop enabled end-to-end in shadow mode:
   - correlation multi-window rescan (no registry mutation)

Explicitly not in 0A:
- pairwise persistence loop execution
- registry tuning execution
- any keep/discard automation that writes to live configuration

### Phase 0B (Loop expansion, after 0A validates)

Enable:
- persisted pairwise interaction loop
- pilot registry tuning experiments in shadow mode
- keep/discard recommendations with manual founder review gate

No live mutation is allowed in 0B unless explicitly approved in a separate spec.

---

## Explicit Non-Goals

Phase 0 does **not** do the following:

- does not modify live production registry parameters
- does not modify live athlete-facing surfaced findings
- does not produce athlete-facing "learned something new overnight" copy
- does not use LLMs for proposal generation
- does not attempt free-form temporal motif mining yet
- does not attempt 3-way or higher-order interaction search
- does not build cross-athlete prior sharing
- does not rewrite the logic of existing investigations
- does not replace the existing daily correlation sweep

This is a **shadow research platform**, not a production auto-mutator.

---

## Relationship to Existing Systems

Phase 0 must extend existing architecture rather than creating a second competing engine.

### Existing foundations to build on

- `apps/api/services/correlation_engine.py`
  - `analyze_correlations()`
  - `discover_combination_correlations()`
  - 70+ aggregated input signals
- `apps/api/tasks/correlation_tasks.py`
  - nightly correlation sweep
  - layer pass on confirmed findings
- `apps/api/services/race_input_analysis.py`
  - `INVESTIGATION_REGISTRY`
  - registered investigation functions
- `apps/api/services/finding_persistence.py`
  - `AthleteFinding` supersession logic
- `apps/api/models.py`
  - `CorrelationFinding`
  - `AthleteFinding`
  - `ExperienceAuditLog`
- Experience Guardrail
  - existing safety net for bad downstream output

### Architectural rule

Phase 0 must not fork discovery logic into an entirely separate system.

It should add:
- shadow orchestration
- metadata
- scoring
- experiment logging
- founder-only scheduling

It should reuse:
- the existing correlation engine
- the existing investigation functions
- the existing persistence models where possible

---

## New Concepts

Phase 0 introduces four core concepts:

1. **Shadow Baseline**
   - the current parameter/config state being evaluated for one athlete and one loop family

2. **Candidate Experiment**
   - one proposed modification against that baseline

3. **Finding Quality Score (FQS)**
   - an explicit ranking score for findings
   - origin-aware so correlation findings and investigation findings are scored through different adapters

4. **Experiment Ledger**
   - persisted record of every run, experiment, delta, keep/discard decision, and summary report

---

## FQS v1

FQS v1 must be honest about what is exact versus inferred from current data structures.

### Top-level rule

Do **not** force a single naive formula across `CorrelationFinding` and `AthleteFinding`.

Instead implement:

- `CorrelationFindingFQSAdapter`
- `AthleteFindingFQSAdapter`

Both must return a shared normalized score interface:

```python
{
    "origin": "correlation" | "investigation",
    "base_score": float,
    "final_score": float,
    "components": {
        "confidence": float,
        "specificity": float,
        "actionability": float,
        "stability": float,
        "cascade_bonus": float,
    },
    "component_quality": {
        "confidence": "exact" | "inferred",
        "specificity": "exact" | "inferred",
        "actionability": "exact" | "registry_default",
        "stability": "exact" | "inferred",
    }
}
```

### CorrelationFindingFQSAdapter

Initial expected sources:

- confidence:
  - `times_confirmed`
  - `last_confirmed_at`
  - `is_active`
- specificity:
  - threshold width if available
  - lag precision if available
  - layer richness (threshold/asymmetry/decay/mediator presence)
- actionability:
  - derived from new registry metadata for the underlying input
- stability:
  - inferred from confirmation recency and active/inactive history

### AthleteFindingFQSAdapter

Initial expected sources:

- confidence:
  - confidence tier mapped into numeric range
  - recency of `last_confirmed_at`
- specificity:
  - receipts richness
  - sentence specificity heuristics kept minimal in v1
- actionability:
  - declared in registry metadata
- stability:
  - supersession history and persistence over time

### Cascade bonus

Keep the concept from the AutoInvestigation spec, but only award it when the underlying chain evidence is explicit and persisted enough to justify it.

If that evidence is not yet robust, award `0` and do not fake it.

### Validation requirement

Before any keep/discard automation is allowed, run FQS manually against current founder findings and verify:

- high-FQS findings feel more valuable than low-FQS findings
- obviously weak findings do not outrank strong actionable ones
- the score is directionally credible

If this validation fails, tuning the optimizer is blocked.

---

## Tunable Registry Metadata

`InvestigationSpec` in `apps/api/services/race_input_analysis.py` is currently too thin for shadow tuning.

Phase 0 must extend investigation metadata to support tuning for a pilot subset.

Add the following concepts:

```python
InvestigationParamSpec(
    name: str,
    param_type: Literal["int", "float", "bool", "enum"],
    default: Any,
    min_value: Optional[float],
    max_value: Optional[float],
    enum_values: Optional[list[str]],
    search_enabled: bool,
    description: str,
)
```

And extend `InvestigationSpec` with:

- `tunable_params: list[InvestigationParamSpec]`
- `runtime_cost_hint: str`
- `actionability_class: "controllable" | "environmental" | "mixed"`
- `shadow_enabled: bool`

### Pilot-only requirement

Do not parameterize all investigations in Phase 0.

Pilot subset only:

- `investigate_pace_at_hr_adaptation`
- `investigate_heat_tax`
- `investigate_long_run_durability`
- `investigate_interval_recovery_trend`
- `detect_adaptation_curves`
- `investigate_workout_variety_effect`

The builder may substitute one investigation if actual parameter surfaces are materially cleaner elsewhere, but the total pilot count must remain between 4 and 6.

---

## Multi-Window Rescan

The current correlation sweep is mostly a 90-day analysis.

Phase 0 must add founder-only shadow rescans across multiple windows.

Minimum supported windows:

- 30 days
- 60 days
- 90 days
- 180 days
- 365 days
- full history

Each window run must:

- reuse existing aggregation logic
- reuse `analyze_correlations()`
- persist shadow results or summaries
- compare stability of:
  - finding existence
  - lag
  - direction
  - score

### Output of this loop

This loop should be able to say:

- this finding is stable across all windows
- this finding is recent-only
- this finding strengthens only in longer history
- this lag appears unstable across windows

That is the real founder value of multi-window rescans in Phase 0.

---

## Pairwise Interaction Loop

Phase 0 must promote the existing combination logic from one-off utility to inspectable shadow research.

### Requirements

- support multiple output metrics, not just raw efficiency
- persist interaction candidates
- score and rank interaction findings
- keep sample-size and effect-size thresholds explicit
- remain pairwise-only in Phase 0

### Important restraint

Do not market or implement this as the final grouped-effects engine.

This is a persisted pairwise interaction layer.

It is a bridge toward later motif and conditional-discovery loops, not the endpoint.

---

## Experiment Ledger

This must be fully specified before implementation starts.

### New table: `auto_discovery_run`

Purpose:
- one founder-only nightly shadow session

Required fields:

- `id`
- `athlete_id`
- `started_at`
- `finished_at`
- `status` (`running`, `completed`, `failed`, `partial`)
- `loop_types` (JSONB list)
- `experiment_count`
- `kept_count`
- `discarded_count`
- `report` (JSONB)
- `notes` (nullable text)

Required indexes:
- `(athlete_id, started_at desc)`
- `(status, started_at desc)`

### New table: `auto_discovery_experiment`

Purpose:
- one experiment inside one run

Required fields:

- `id`
- `run_id`
- `athlete_id`
- `loop_type` (`correlation_rescan`, `interaction_scan`, `registry_tuning`)
- `target_name`
  - investigation name, input name, or interaction pair identifier
- `baseline_config` (JSONB)
- `candidate_config` (JSONB)
- `baseline_score` (float)
- `candidate_score` (float)
- `score_delta` (float)
- `kept` (bool)
- `runtime_ms`
- `result_summary` (JSONB)
- `failure_reason` (nullable text)
- `created_at`

Required indexes:
- `(run_id)`
- `(athlete_id, loop_type, created_at desc)`
- `(loop_type, kept, created_at desc)`

### Optional table: `auto_discovery_baseline`

Use this if needed to store the current founder-only shadow baseline separately from live production logic.

If omitted, the builder must still define where the shadow baseline lives and how it is loaded.

---

## Nightly Session Report

This is required output, not a nice-to-have log file.

Every completed founder-only run must produce a structured report with these sections:

1. **Stable Findings**
   - findings that remain strong across multiple windows

2. **Strengthened Findings**
   - findings whose FQS improved materially in shadow analysis

3. **Candidate Interactions**
   - pairwise interactions worth founder review

4. **Registry Tuning Candidates**
   - parameter changes that would have improved finding quality

5. **Discarded Experiments**
   - what was tried and why it was rejected

6. **Score Summary**
   - aggregate FQS before/after by loop family

7. **No-Surface Guarantee**
   - explicit confirmation that no athlete-facing surfaced findings were changed

### Acceptance rule

If the report does not contain these sections in structured form, Phase 0 is not complete.

---

## Scheduling and Rollout

### Initial rollout

- founder-only
- shadow mode only
- no athlete-facing output
- no live mutation
- no automatic registry writeback

### Required rollout controls

Feature flags must exist for:

- entire AutoDiscovery system
- loop family
  - rescan
  - interaction
  - tuning
- athlete allowlist
- live mutation enablement
- athlete-facing surfacing enablement

### Design rule

The architecture must allow rollout to all athletes immediately once founder approval is given, without redesign.

That means:
- athlete scoping must be data-driven
- loop enablement must be feature-flag driven
- founder-only status must be configuration, not hardcoded architecture

---

## Safety Rules

1. No candidate experiment may mutate live production registry logic in Phase 0.
2. No candidate experiment may directly rewrite surfaced findings.
3. Failed experiments must be logged, not hidden.
4. Every score must be inspectable.
5. Experience Guardrail remains the downstream safety net, but Phase 0 must not rely on it as the only brake.
6. Shadow mode must be the default for every loop family.

---

## Acceptance Criteria

Phase 0 is complete only if all of the following are true:

1. A founder-only nightly AutoDiscovery run executes in shadow mode without changing live athlete-facing outputs.
2. The system supports three loop families:
   - correlation rescan
   - pairwise interaction scan
   - pilot registry tuning
3. Multi-window rescans run across at least:
   - 30d
   - 60d
   - 90d
   - 180d
   - 365d
   - full history
4. Pairwise interaction findings are persisted and inspectable rather than returned as ephemeral output only.
5. A pilot subset of 4-6 investigations can declare tunable parameter metadata and run shadow parameter experiments.
6. FQS v1 exists with origin-aware adapters for `CorrelationFinding` and `AthleteFinding`.
7. Every nightly run writes a structured session report containing:
   - stable findings
   - strengthened findings
   - candidate interactions
   - registry tuning candidates
   - discarded experiments
   - aggregate score summary
   - no-surface guarantee
8. Every experiment is persisted with baseline config, candidate config, before/after score, delta, keep/discard, and runtime.
9. Founder-only rollout is enforced by feature flags, not by architecture assumptions.
10. The architecture is ready for all-athlete shadow rollout without redesign once approved.

### Phase 0A acceptance gate (must pass before 0B starts)

1. Founder-only nightly run executes and writes:
   - one `auto_discovery_run` row
   - >=1 `auto_discovery_experiment` rows
   - full structured report sections
2. Correlation multi-window rescan loop runs in shadow mode only.
3. FQS adapters produce inspectable component-level outputs with component quality labels.
4. No athlete-facing surfaces change as a result of the run.
5. No production investigation registry values are mutated.
6. Run can be disabled instantly via feature flag without deploy.

---

## Read Order for Builder

1. `docs/FOUNDER_OPERATING_CONTRACT.md`
2. `docs/PRODUCT_MANIFESTO.md`
3. `docs/BUILD_ROADMAP_2026-03-09.md`
4. `docs/specs/AUTOINVESTIGATION_LOOP_SPEC.md`
5. `docs/specs/DAILY_EXPERIENCE_GUARDRAIL_SPEC.md`
6. This document
7. `apps/api/services/correlation_engine.py`
8. `apps/api/tasks/correlation_tasks.py`
9. `apps/api/services/race_input_analysis.py`
10. `apps/api/services/finding_persistence.py`
11. `apps/api/models.py`

---

## Final Note

This phase is intentionally founder-only and intentionally silent.

The purpose is not to create athlete-facing magic immediately.

The purpose is to build a trustworthy shadow research substrate so that future loops can make the system genuinely smarter about a single athlete over time.

If Phase 0 succeeds, StrideIQ stops being a static engine that runs once a day and starts becoming a continuous discovery instrument.
