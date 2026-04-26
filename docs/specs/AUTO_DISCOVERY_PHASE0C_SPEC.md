# AutoDiscovery Phase 0C — Founder Review and Controlled Promotion

**Date:** March 11, 2026
**Status:** Proposed build spec
**Owner:** Top advisor
**Depends on:** `docs/specs/AUTO_DISCOVERY_PHASE0_SPEC.md`, tech-verified `docs/specs/AUTO_DISCOVERY_PHASE0B_SPEC.md`
**Build target:** Founder-reviewable shadow intelligence with explicit approve / reject / defer flow

---

## Why Phase 0C Exists

Phase 0A proved AutoDiscovery could run safely in founder-only shadow mode.

Phase 0B made it intellectually useful:

- real FQS-driven scoring
- pairwise interaction loop
- pilot registry tuning loop
- founder-reviewable nightly report

But after 0B, the center of gravity changes.

The next real question is no longer:

- "Can the shadow system generate candidates?"

It becomes:

- "Can the founder review them cleanly?"
- "Can the system remember what keeps showing up?"
- "Can we explicitly promote the right candidates toward live use without accidental leakage?"

Phase 0C is therefore the trust-and-promotion phase.

It should create the first explicit bridge from:

- nightly shadow learning

to:

- durable founder review
- manual approval
- controlled promotion pathways

without yet turning AutoDiscovery into a self-mutating production engine.

---

## Critical Carry-Forward From 0B

Before new 0C surfaces are considered complete, Phase 0C must absorb the remaining 0B fidelity work identified in tech review.

This is not optional cleanup. It is part of 0C.

### Required 0B carry-forward fixes

1. **`interaction_scan` score summary must become value-bearing**
   - `score_summary["interaction_scan"]` cannot leave aggregate score fields as `None` when the interaction loop already computes scored candidates.
   - Phase 0C must make the interaction loop report real aggregate score information.

2. **FQS provenance must survive the persisted/report path**
   - Component-level provenance from `fqs_adapters.py` cannot be flattened into only numeric rollups.
   - Phase 0C must preserve a compact provenance block so the founder can tell what is exact vs inferred vs registry-default.

If these two items are not closed, 0C is not complete even if the review/promotion layer ships.

---

## Objective

Build the first explicit founder-control layer for AutoDiscovery that can:

1. preserve and present nightly shadow candidates in a reviewable durable form
2. track candidate persistence across nights rather than treating every run as isolated
3. let the founder explicitly approve, reject, or defer candidates
4. stage approved candidates for controlled promotion
5. keep all promotion pathways non-athlete-facing until explicitly released

This phase is about **trust, memory, and control**.

Not autonomy.
Not motif mining.
Not self-writing registry values.

---

## Product Intent

If AutoDiscovery is going to become a real part of StrideIQ's scientific instrument, the founder must be able to do three things cleanly:

1. See what the system keeps finding
2. Understand why it thinks the finding is valuable
3. Decide whether that finding should move one step closer to live use

Phase 0B gave us "nightly report."

Phase 0C should give us:

- "nightly report plus memory"
- "nightly report plus judgment"
- "nightly report plus explicit promotion state"

That is the right next step before any deeper loop complexity.

---

## Phase 0C Scope

Phase 0C includes four workstreams:

### Workstream 1: 0B Scoring and Provenance Completion
### Workstream 2: Candidate Persistence Across Nights
### Workstream 3: Founder Review State Machine
### Workstream 4: Controlled Promotion Staging

---

## Workstream 1 — 0B Scoring and Provenance Completion

### Goal

Close the remaining report/score fidelity gap from 0B so founder review is built on honest, value-bearing outputs.

### Required outcomes

1. **Interaction score summary becomes value-bearing**
   - `interaction_scan` aggregate score fields must be populated from real interaction candidate scores
   - The pairwise loop is single-arm discovery (no A/B candidate variant exists by design), so
     `aggregate_candidate_score` and `aggregate_delta` are **structurally absent** — not placeholders.
   - This is not a gap: it must be documented explicitly with `loop_design: "single_arm_discovery"`.
   - Required persisted shape in run report:
     - `score_summary["interaction_scan"]["experiments_run"]`
     - `score_summary["interaction_scan"]["kept"]`
     - `score_summary["interaction_scan"]["aggregate_baseline_score"]` — mean `interaction_score` of kept candidates; null only when nothing kept
     - `score_summary["interaction_scan"]["aggregate_all_score"]` — mean `interaction_score` across all tested experiments; always numeric when loop ran
     - `score_summary["interaction_scan"]["aggregate_candidate_score"]` — always `null` (single-arm; no candidate variant)
     - `score_summary["interaction_scan"]["aggregate_delta"]` — always `null` (single-arm; no candidate variant)
     - `score_summary["interaction_scan"]["loop_design"]` — always `"single_arm_discovery"`
   - `aggregate_baseline_score` and `aggregate_all_score` must be numeric (not `None`) when interaction experiments ran.

2. **FQS provenance survives report/persistence**
   - Preserve compact component provenance for founder review
   - Minimum expectation:
     - component averages where applicable
     - component quality labels (`exact`, `inferred`, `registry_default`, etc.)
   - Minimum required persisted shape in experiment/report payloads:
     - `score_provenance.component_values`
     - `score_provenance.component_quality`
     - `score_provenance.has_inferred_components` (boolean)

3. **Report contract is upgraded, not blurred**
   - the nightly report must clearly separate:
     - numeric score rollups
     - provenance/confidence shape

### Acceptance criteria for Workstream 1

- `interaction_scan` score summary: `aggregate_baseline_score` and `aggregate_all_score` are numeric when loop ran; `aggregate_candidate_score`/`aggregate_delta` are explicitly null with `loop_design="single_arm_discovery"`
- FQS provenance is visible in persisted/report output
- founder can distinguish exact vs inferred score structure in report artifacts

---

## Workstream 2 — Candidate Persistence Across Nights

### Problem

Phase 0B nightly runs are useful, but they are still too run-local.

The founder needs to know:

- what appeared once
- what keeps reappearing
- what is strengthening
- what is fading

### Goal

Introduce a durable candidate memory layer that groups recurring shadow candidates across runs.

### Required implementation

Add a persistence layer for recurring candidates.

Required table name:

- `auto_discovery_candidate`

Minimum fields:

- `id`
- `candidate_type`
  - `stable_finding`
  - `strengthened_finding`
  - `interaction`
  - `registry_tuning`
- stable candidate key / fingerprint
- `athlete_id`
- `first_seen_run_id`
- `last_seen_run_id`
- `times_seen`
- `current_status`
  - `open`
  - `approved`
  - `rejected`
  - `deferred`
  - `promoted`
- latest compact summary payload
- latest score / score delta
- provenance snapshot
- timestamps

### Candidate key rule

The grouping key must be stable and inspectable.

Examples:

- correlation candidates: input/output/direction/(lag/threshold family if needed)
- interaction candidates: pair + output metric + direction
- registry tuning candidates: investigation name + parameter change signature

Do not make this fuzzy/semantic in 0C.

Candidate keys must be deterministic and unique per athlete + candidate family.
Enforce this with a unique constraint/index on `(athlete_id, candidate_type, candidate_key)`.

### Acceptance criteria for Workstream 2

- recurring candidates are grouped across nights
- founder can see `times_seen`, first seen, last seen, and latest score
- candidate review state remains durable across process restarts and new nightly runs
- candidate persistence does not mutate athlete-facing surfaces

---

## Workstream 3 — Founder Review State Machine

### Goal

Let the founder explicitly review AutoDiscovery candidates without turning review into an ad hoc notebook exercise.

### Required review states

Each durable candidate must support:

- `open`
- `approved`
- `rejected`
- `deferred`

Optional:

- `promoted`
- `superseded`

### Required founder actions

For each candidate, the founder must be able to:

1. approve
2. reject
3. defer
4. add an optional short note

### Delivery format

This does **not** require a polished UI in 0C.

Acceptable first versions:

- founder-only admin API
- founder-only CLI/script + persisted DB state

The important thing is that review state becomes structured and durable.

### Required review query

The system must support a founder-review view/query that can show:

- open candidates sorted by value
- candidates seen 2+ times
- candidates newly strengthened tonight
- approved / rejected / deferred history

### Acceptance criteria for Workstream 3

- founder review state is persisted
- founder actions are explicit and durable
- review does not rely on reading raw nightly reports alone

---

## Workstream 4 — Controlled Promotion Staging

### Goal

Create the first safe promotion layer from approved shadow candidates toward live use.

### Important boundary

Phase 0C does **not** directly surface approved candidates to athletes.

It only stages them for the next explicit decision layer.

### Required implementation

For approved candidates, define a promotion target category such as:

- `surface_candidate`
- `registry_change_candidate`
- `investigation_upgrade_candidate`
- `manual_research_candidate`

This can live:

- on the durable candidate table
- or in a separate promotion-state table if cleaner

### Promotion rules

Promotion staging must remain:

- founder-only
- non-athlete-facing
- non-auto-mutating

No approved candidate should silently:

- write to live investigation registry
- write to live surfaced findings
- alter home/activity outputs

### Deliverable expectation

At the end of 0C, the founder should be able to say:

- "this one should stay shadow-only"
- "this one is worth staging for product use later"
- "this one is noise"

without any automatic product mutation happening yet.

### Acceptance criteria for Workstream 4

- approved candidates can be staged for promotion
- staged promotion intent is persisted
- no athlete-facing mutation occurs

---

## Explicit Non-Goals

Phase 0C does **not** include:

- live athlete-facing surfacing of approved candidates
- automatic registry mutation
- LLM-generated candidate proposals
- motif / sequence grammar mining
- three-way or higher-order interaction search
- cohort priors
- autonomous approval logic
- a polished broad admin UI

If the work starts drifting into "the system should auto-apply good findings," stop. That is a later phase.

---

## Data Model Expectations

Phase 0C may add one durable candidate table and, if needed, one founder-review audit table.

Preferred additions:

- `auto_discovery_candidate`
- optional `auto_discovery_review_log`

Reuse existing `auto_discovery_run` and `auto_discovery_experiment` ledger rather than creating a parallel run ledger.

The candidate layer should point back to:

- latest/first supporting run
- latest/first supporting experiment

so provenance remains traceable.

---

## Reporting Standard for 0C

The nightly report should remain, but its role changes slightly.

By end of 0C it should support two levels:

### Nightly run report

Still contains:

- stable findings
- strengthened findings
- candidate interactions
- registry tuning candidates
- discarded experiments
- score summary
- no-surface guarantee

### Cross-run candidate summary

New founder-review output should be able to show:

- new candidates tonight
- candidates that reappeared
- candidates that strengthened materially
- candidates awaiting founder decision

The founder should not need to manually diff two JSON reports to understand what matters.

---

## Rollout and Safety

### Rollout

- founder-only
- shadow mode retained
- no athlete-facing changes
- feature-flag controlled

### Safety rules

1. no automatic athlete-facing surfacing
2. no automatic live registry mutation
3. no promotion without explicit founder action
4. every founder review action must be auditable
5. all candidate provenance remains traceable back to supporting runs/experiments

---

## Acceptance Criteria

Phase 0C is complete only if all are true:

1. The outstanding 0B scoring/report fidelity work is closed:
   - `interaction_scan` summary is value-bearing
   - FQS provenance survives into persisted/report output

2. Recurring candidates are grouped across runs:
   - `times_seen`
   - first seen
   - last seen
   - latest score/provenance
   - deterministic candidate key with uniqueness enforced in DB

3. Founder review state exists and is durable:
   - approve
   - reject
   - defer

4. Approved candidates can be staged for controlled promotion

5. No athlete-facing mutation occurs
6. No live registry mutation occurs
7. Founder-only rollout remains enforced

8. 0C persistence schema is migration-backed:
   - new table(s) for durable candidates (and review log if added)
   - migration verification evidence included in handoff

---

## Tests and Handoff Evidence (Required)

Builder handoff must include concrete evidence, not claims.

### Required tests

1. **Workstream 1 fidelity tests**
   - `interaction_scan` score summary: `aggregate_baseline_score` and `aggregate_all_score` are numeric when candidates exist; `loop_design="single_arm_discovery"` is present; `aggregate_candidate_score`/`aggregate_delta` are null by design
   - provenance block is present in persisted experiment/report output and includes `component_quality`

2. **Candidate durability tests**
   - same candidate across two runs increments `times_seen` and updates `last_seen_run_id`
   - review status persists across subsequent runs (open -> approved/rejected/deferred remains durable)
   - uniqueness constraint prevents duplicate candidate rows for same `(athlete_id, candidate_type, candidate_key)`

3. **Founder review action tests**
   - approve/reject/defer actions persist
   - optional note persists
   - review history is auditable (via candidate row history fields or review-log table)

4. **Promotion safety tests**
   - staging intent can be set for approved candidates
   - no athlete-facing tables/surfaces mutate as part of 0C promotion staging
   - no live registry mutation occurs as part of 0C promotion staging

### Required handoff evidence

- migration revision id(s) and table/index summary
- pytest output for all new/changed 0C tests
- one sample founder-review query output
- one sample nightly report excerpt showing:
  - value-bearing `interaction_scan` score summary
  - preserved FQS provenance block
- explicit confirmation that athlete-facing outputs and live registry values remain unchanged

---

## Suggested Build Order

1. Close the two 0B fidelity gaps
2. Add durable candidate grouping across runs
3. Add founder review state machine
4. Add promotion staging
5. Upgrade founder summary/query output
6. Validate founder-only end to end

---

## Read Order for Builder

1. `docs/FOUNDER_OPERATING_CONTRACT.md`
2. `docs/BUILD_ROADMAP_2026-03-09.md`
3. `docs/specs/AUTO_DISCOVERY_PHASE0_SPEC.md`
4. `docs/specs/AUTO_DISCOVERY_PHASE0B_SPEC.md`
5. This document
6. `apps/api/services/auto_discovery/orchestrator.py`
7. `apps/api/services/auto_discovery/fqs_adapters.py`
8. `apps/api/services/auto_discovery/interaction_loop.py`
9. `apps/api/services/auto_discovery/tuning_loop.py`
10. `apps/api/models.py`

---

## Final Note

Phase 0C should be the first time AutoDiscovery feels less like "nightly experiments" and more like "a founder-reviewable research memory."

Not autonomous.
Not athlete-facing.
Not self-mutating.

But finally something you can inspect, judge, and move one careful step closer to live product use.
