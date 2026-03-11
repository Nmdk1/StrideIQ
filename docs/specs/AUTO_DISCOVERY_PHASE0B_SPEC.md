# AutoDiscovery Phase 0B — Real Scoring, Interaction, and Pilot Tuning

**Date:** March 11, 2026
**Status:** Proposed build spec
**Owner:** Top advisor
**Depends on:** `docs/specs/AUTO_DISCOVERY_PHASE0_SPEC.md`, completed Phase 0A shadow foundation
**Build target:** Founder-only shadow mode, rollout-ready architecture retained

---

## Why Phase 0B Exists

Phase 0A proved the platform can run:

- founder-only nightly shadow pass
- run/experiment ledger
- multi-window correlation rescans
- structured nightly report skeleton
- hard no-mutation / no-surfacing guarantees

But Phase 0A is still foundational rather than genuinely insightful:

- shadow rescans still rely on count-like scoring in orchestration
- FQS adapters exist but are not yet driving experiment scoring
- interaction loop is not yet wired
- registry tuning loop is not yet wired
- shadow isolation is not fully clean if shared cache/state is still touched

Phase 0B turns the platform from "it runs safely" into "it produces meaningful founder-reviewable shadow learning."

---

## Objective

Build the first version of AutoDiscovery that can:

1. score findings with real FQS adapters
2. run a real pairwise interaction loop in shadow mode
3. run a real pilot registry tuning loop in shadow mode
4. produce a founder-reviewable nightly report with ranked outputs
5. remain fully non-mutating to athlete-facing surfaces and live production registry values

This is still **not** the full hidden-physiological-grammar engine.

It is the first version that can plausibly say: "the shadow system found something better tonight."

---

## Phase 0B Scope

Phase 0B includes four workstreams:

### Workstream 1: Shadow Isolation Hardening

Fix all known Phase 0A shadow-mode leaks or weak guarantees.

Required outcomes:

- no production cache writes from shadow rescans
- no accidental persisted writes outside the AutoDiscovery ledger tables
- correct preservation of lag metadata in shadow findings
- per-athlete loop enablement, not task-wide loop inference from the first athlete

This is not optional cleanup. It is required before deeper loops are trustworthy.

### Workstream 2: Real FQS Integration

Phase 0A added origin-aware adapters. Phase 0B must make them operational.

Required outcomes:

- `CorrelationFindingFQSAdapter` drives correlation-rescan scoring
- `AthleteFindingFQSAdapter` drives registry-tuning scoring
- `baseline_score`, `candidate_score`, and `score_delta` become real values
- nightly reports summarize score improvements using FQS, not just counts

### Workstream 3: Pairwise Interaction Loop

Build the first persisted, scored, founder-only interaction loop.

Required outcomes:

- pairwise interactions run in shadow mode
- results are persisted as AutoDiscovery experiments
- the nightly report contains ranked `candidate_interactions`
- pairwise interactions are scored explicitly and inspectably

### Workstream 4: Pilot Registry Tuning Loop

Build the first founder-only shadow tuning loop for the pilot investigation subset.

Required outcomes:

- bounded candidate parameter generation for pilot investigations
- baseline vs candidate evaluation over founder historical corpus
- keep/discard shadow decision persisted in ledger
- nightly report contains ranked `registry_tuning_candidates`

---

## Explicit Non-Goals

Phase 0B does **not** include:

- live production registry mutation
- athlete-facing surfacing of AutoDiscovery outputs
- all-athlete rollout
- LLM-generated proposals
- temporal motif mining
- three-way or higher-order interactions
- cohort priors or cross-athlete transfer
- rewriting core investigation logic
- replacing the existing daily correlation sweep

If the work starts drifting into "sequence grammar" or "motif discovery," stop. That belongs to a later phase.

---

## Workstream 1 — Shadow Isolation Hardening

### Problem

Phase 0A is shadow-safe at the database commit layer, but shadow execution must also avoid collateral mutation of:

- shared cache state
- shared task-wide control flow assumptions
- metadata loss inside result summaries

### Required fixes

1. **No production cache pollution from shadow rescans**
   - If `analyze_correlations()` writes cache entries during shadow runs, the shadow layer must bypass or isolate those writes.
   - Acceptable solutions:
     - explicit `shadow_mode=True` path in correlation analysis that skips cache writes
     - separate shadow cache namespace
   - Preferred in Phase 0B:
     - skip cache writes entirely in shadow mode

2. **Preserve lag metadata correctly**
   - Shadow result summaries must store the true lag field shape emitted by correlation analysis.
   - If the engine emits `time_lag_days`, the shadow summary must not remap incorrectly to a missing field.

3. **Per-athlete loop enablement**
   - AutoDiscovery task orchestration must evaluate enabled loops per athlete, not once globally from the first athlete.
   - Founder-only remains the rollout, but the architecture must already support athlete-specific loop enablement cleanly.

### Acceptance criteria for Workstream 1

- shadow rescans do not mutate production cache keys
- lag data is present and correct in persisted shadow result summaries
- loop-family enablement is evaluated per athlete

---

## Workstream 2 — Real FQS Integration

### Problem

Phase 0A created FQS adapters but still treats experiment scoring mostly as "count of findings" inside orchestration.

That is insufficient for real keep/discard logic.

### Required work

1. **Correlation rescan scoring**
   - For each window rescan, compute a scored summary based on `CorrelationFindingFQSAdapter`
   - Aggregate in a transparent way
   - Keep the aggregation simple and inspectable in 0B

2. **Registry tuning scoring**
   - For the pilot tuning loop, compute baseline and candidate scores using `AthleteFindingFQSAdapter`
   - Store scores explicitly on each experiment

3. **Experiment ledger integration**
   - `baseline_score`
   - `candidate_score`
   - `score_delta`
   must be populated when a loop family supports real scoring

4. **Report integration**
   - `score_summary` must speak in FQS terms where applicable
   - counts can remain as supporting context, not primary value

### Important rule

Do not hide approximation.

If a score component is inferred or registry-default, the report/summary layer should preserve that knowledge rather than implying scientific finality.

### Acceptance criteria for Workstream 2

- correlation rescan experiments store real FQS-driven scores
- registry tuning experiments store real FQS-driven scores
- `score_delta` is populated where scoring applies
- report uses real score language rather than only counts

---

## Workstream 3 — Pairwise Interaction Loop

### Goal

Turn interaction discovery from a one-off helper into a persisted, scored shadow loop.

### Required implementation

Create:

- `apps/api/services/auto_discovery/interaction_loop.py`

Responsibilities:

1. run pairwise interaction discovery in shadow mode
2. support a bounded set of output metrics
3. persist one experiment per candidate or per interaction batch, whichever is more inspectable
4. produce ranked founder-reviewable interaction candidates

### Output metric scope

Phase 0B should support more than just raw `efficiency`, but it does not need to support every conceivable output metric.

Minimum acceptable set:

- `efficiency`
- `pace_easy`
- `pace_threshold`
- `completion`

The builder may include more if it is clean and low-risk, but these four are the minimum target.

### Scoring

Interaction candidates must be ranked with a transparent score.

Minimum scoring inputs:

- effect size
- sample support
- stability across windows if feasible
- actionability/control class if available

Do not overcomplicate this in 0B.

The score should be clear enough that you can look at the top candidates and decide whether they feel plausible.

### Nightly report integration

`candidate_interactions` must no longer be an empty list by default.

It must contain ranked founder-reviewable candidates or an explicit statement that none cleared threshold.

### Acceptance criteria for Workstream 3

- interaction loop exists and runs in founder-only shadow mode
- interaction experiments are persisted
- report contains ranked `candidate_interactions`
- interaction output is pairwise-only in 0B

---

## Workstream 4 — Pilot Registry Tuning Loop

### Goal

Turn pilot `InvestigationParamSpec` metadata into actual shadow tuning experiments.

### Pilot investigation subset

Remain on the existing 0A pilot subset:

- `investigate_pace_at_hr_adaptation`
- `investigate_heat_tax`
- `investigate_long_run_durability`
- `investigate_interval_recovery_trend`
- `investigate_workout_variety_effect`
- `investigate_stride_progression`

Do not expand the cohort in 0B.

### Required implementation

Create:

- `apps/api/services/auto_discovery/tuning_loop.py`

Responsibilities:

1. read pilot `InvestigationParamSpec` metadata
2. generate bounded shadow candidates
3. evaluate candidate vs baseline against founder historical corpus
4. score baseline vs candidate using investigation FQS
5. persist experiment rows with keep/discard

### Candidate generation rules

Keep this bounded and mechanical.

Allowed in 0B:

- small step increases/decreases for numeric params
- enum swaps where defined
- boolean flips only if explicitly marked safe

Not allowed in 0B:

- broad random search
- LLM proposal generation
- simultaneous large multi-param sweeps unless tightly bounded

### Keep/discard rule

Define a simple founder-reviewable keep rule:

- keep when `score_delta` exceeds a minimum threshold and no stability regression rule is violated
- otherwise discard

The exact threshold can be calibrated, but it must be explicit in code and test-covered.

### Nightly report integration

`registry_tuning_candidates` must contain:

- target investigation
- parameter change
- baseline score
- candidate score
- score delta
- keep/discard
- short rationale

or explicitly state that no candidate cleared threshold.

### Acceptance criteria for Workstream 4

- tuning loop exists and runs founder-only in shadow mode
- pilot metadata is actually exercised, not merely declared
- tuning experiments persist with real scores and keep/discard
- report contains ranked `registry_tuning_candidates`

---

## Nightly Session Report — Phase 0B Standard

The nightly report must become genuinely founder-reviewable.

Required sections remain:

1. `stable_findings`
2. `strengthened_findings`
3. `candidate_interactions`
4. `registry_tuning_candidates`
5. `discarded_experiments`
6. `score_summary`
7. `no_surface_guarantee`

### Phase 0B enhancement requirement

The report must now contain actual value-bearing content for sections 3 and 4 unless no candidates cleared threshold.

If no candidate cleared threshold:
- the section must still be present
- it must explicitly say none cleared threshold

### Minimum score summary content

`score_summary` must include, by loop family where applicable:

- experiments run
- experiments kept
- aggregate baseline score
- aggregate candidate score
- aggregate delta

Counts alone are no longer sufficient for 0B.

---

## Data Model Expectations

The `auto_discovery_run` and `auto_discovery_experiment` tables from 0A remain the primary ledger.

Phase 0B should reuse them rather than introducing a second ledger unless a truly blocking reason appears.

Potential additions are allowed only if essential, but the builder should prefer extending `result_summary` structure over multiplying tables.

---

## Rollout and Safety

### Rollout

- founder-only
- shadow mode only
- feature-flag controlled
- architecture remains rollout-ready for all athletes later

### Safety rules

1. No live production registry mutation
2. No athlete-facing surfacing
3. No shared production cache mutation from shadow paths
4. All failures logged in ledger
5. All keep/discard decisions inspectable

---

## Acceptance Criteria

Phase 0B is complete only if all are true:

1. Known 0A shadow isolation issues are resolved:
   - no production cache pollution
   - no lag-field mismatch
   - per-athlete loop enablement works

2. FQS is operational, not scaffold-only:
   - rescans use real adapter-driven scores
   - tuning uses real adapter-driven scores
   - experiments persist `baseline_score`, `candidate_score`, and `score_delta`

3. Pairwise interaction loop is live in founder-only shadow mode:
   - interaction experiments are persisted
   - report contains ranked `candidate_interactions`

4. Pilot registry tuning loop is live in founder-only shadow mode:
   - bounded candidates are generated
   - baseline vs candidate evaluation runs
   - keep/discard decisions are persisted
   - report contains ranked `registry_tuning_candidates`

5. Nightly report is founder-reviewable:
   - not just counts
   - not just structural placeholders
   - includes actual ranked outputs or explicit none-cleared-threshold statements

6. No athlete-facing tables or surfaces are mutated
7. No live production registry values are changed
8. Founder-only rollout remains feature-flag controlled and all-athlete expansion remains architecture-ready

---

## Suggested Build Order

1. Fix 0A isolation issues
2. Wire real FQS into orchestrator
3. Implement pairwise interaction loop
4. Implement pilot registry tuning loop
5. Upgrade nightly report to real ranked founder-reviewable content
6. Validate founder-only dry run end to end

---

## Read Order for Builder

1. `docs/FOUNDER_OPERATING_CONTRACT.md`
2. `docs/BUILD_ROADMAP_2026-03-09.md`
3. `docs/specs/AUTO_DISCOVERY_PHASE0_SPEC.md`
4. This document
5. `apps/api/services/auto_discovery/orchestrator.py`
6. `apps/api/services/auto_discovery/fqs_adapters.py`
7. `apps/api/services/auto_discovery/rescan_loop.py`
8. `apps/api/services/correlation_engine.py`
9. `apps/api/services/race_input_analysis.py`
10. `apps/api/models.py`

---

## Final Note

Phase 0B should feel like the first version where AutoDiscovery is doing real intellectual work in shadow mode.

Not the full dream.
Not the final grammar engine.
But the first version where the founder can look at a nightly report and say:

"Yes, this is actually learning."
