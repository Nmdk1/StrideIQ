# AutoDiscovery Phase 1 — The Loop Closes

**Date:** March 12, 2026
**Status:** Proposed spec — advisor + founder discussion
**Owner:** Top advisor
**Depends on:** Phase 0C (shipped), correlation engine (70 inputs live), FQS adapters (operational)
**Build target:** AutoDiscovery produces real improvements to the athlete's fingerprint every night

---

## Why This Exists

Phase 0A/0B/0C built a shadow research platform:

- 3 loop families (rescan, interaction, tuning)
- FQS scoring with origin-aware adapters
- Candidate persistence with cross-run memory
- Review state machine with audit logging
- 6 feature flags

None of it improves anything. Every night the system discovers, scores, persists, and forgets. The daily correlation sweep at 08:00 ignores everything AutoDiscovery found at 04:00. The athlete's fingerprint is exactly as dense this morning as it was last night.

The system just expanded from 21 to 70 input signals. The pairwise interaction space is 2,415 combinations × 9 output metrics × 6 time windows × 14 lag shifts. The daily sweep runs one 90-day pass. The vast majority of the search space has never been explored.

Phase 1 is about one thing: **when AutoDiscovery finds something real, it makes the system smarter.**

---

## The Contract

AutoDiscovery Phase 1 operates under these rules:

1. **When a discovery passes significance gates, it becomes a real finding.** The same statistical gates that protect the daily sweep (`|r| >= 0.3, p < 0.05, n >= 10`) protect AutoDiscovery. If a correlation discovered at a 180-day window passes those gates, it's a real finding — not a shadow candidate.

2. **When an existing finding is validated across multiple windows, it gets stability evidence.** This is annotation, not mutation. The finding already passed significance. The stability data makes it more trustworthy.

3. **When a tuning improvement is proven, it applies.** If changing an investigation's window from 90 to 180 days produces a higher-FQS finding for this athlete without degrading other findings, the parameter applies. The next time the investigation runs, it uses the better parameters.

4. **When an interaction clears threshold across multiple runs, it becomes a finding.** Pairwise effects that are statistically significant and reproduce across nights enter the fingerprint.

5. **The founder has visibility and override, not approval over every change.** An admin endpoint shows what changed overnight. The founder can deactivate any finding or revert any parameter. But the default is: the system improves, and the guardrails catch mistakes.

6. **The experience guardrail remains the downstream safety net.** 25 daily assertions catch "technically correct but experientially wrong" outputs. This protects against AutoDiscovery producing real-but-misleading findings.

7. **Eventually the system plateaus.** When the search space is well-explored and new discoveries slow down, that's the fingerprint reaching maturity. That's fine. The system reports "nothing new tonight" and the athlete's portrait is stable.

---

## Phase 1 Safety + Mutation Contracts (Non-Negotiable)

Phase 1 writes to production state. The following contracts are required before enabling live mutation:

1. **Idempotent promotion contract.**
   - Every promoted change must map to a deterministic identity key.
   - Re-running the same run payload must not create duplicate findings/config rows.
   - Promotion uses upsert semantics with explicit conflict keys.

2. **Typed change ledger contract.**
   - Every applied mutation writes one row to a durable change log table.
   - Revert actions operate on change-log rows (not ad hoc lookup logic).
   - `change_id` is globally unique and references one reversible unit.

3. **Transaction boundary contract.**
   - For each athlete-run, either all intended mutations commit or none do.
   - No partial-apply state across finding creation, stability writes, and tuning override apply.
   - On failure, record error in run/report and skip mutation for that athlete.

4. **Mutation kill contract.**
   - Global kill switch: `auto_discovery.mutation.live` can disable all apply paths immediately.
   - Per-loop kill switches: rescan promotion, interaction promotion, tuning apply are independently disableable.
   - If auto-disable threshold trips, loop halts mutation and records machine-readable disable reason.

5. **Rollbackability contract.**
   - Every mutation type (new finding, finding update, stability annotation, tuning override) must be individually reversible.
   - Revert writes an audit record and never hard-deletes evidence rows.

6. **No-surprise surfacing contract.**
   - New findings from AutoDiscovery still follow existing surfacing gates (`times_confirmed >= 3`) unless explicitly approved in a separate spec.
   - If a promoted finding bypasses surfacing gates by design, that requires an explicit, separate contract.

---

## What Changes From Phase 0

| Phase 0 | Phase 1 |
|---------|---------|
| Shadow-only: no production writes | Writes real findings, stability data, and tuning params |
| Candidates stored in JSONB, invisible | Discoveries flow into `CorrelationFinding`, `AthleteFinding`, investigation config |
| Manual review required for every candidate | Auto-promotion for statistically significant discoveries; founder override available |
| `is_live_mutation_enabled()` returns `False` always | Returns `True` when feature flag is enabled for the athlete |
| `is_athlete_surfacing_enabled()` returns `False` always | Returns `True` — discoveries enter the normal surfacing pipeline |
| Admin endpoint: none | Admin endpoint: what changed, what's pending, what was reverted |

---

## Data Model Additions Required

Minimum schema contract for Phase 1:

1. **`auto_discovery_change_log`** (new, required)
   - `id` (UUID)
   - `run_id` (FK -> auto_discovery_run)
   - `athlete_id`
   - `change_type` (enum/string): `new_correlation_finding`, `stability_annotation`, `new_interaction_finding`, `tuning_override_applied`, `tuning_override_reverted`, `finding_deactivated`
   - `change_key` (deterministic identity key for idempotency)
   - `before_state` (JSONB)
   - `after_state` (JSONB)
   - `reverted` (bool), `reverted_at`, `reverted_by`, `revert_reason`
   - `created_at`
   - Unique index on `(athlete_id, change_type, change_key, run_id)` to prevent duplicate ledger entries in the same run.

2. **`athlete_investigation_config`** (new, required)
   - `athlete_id`
   - `investigation_name`
   - `param_overrides` (JSONB)
   - `applied_from_run_id`
   - `applied_change_log_id`
   - `reverted` + timestamps/audit metadata
   - Unique index on `(athlete_id, investigation_name, reverted=false)` or equivalent single-active-record rule.

3. **`correlation_finding` stability fields** (required)
   - `discovery_source`
   - `discovery_window_days`
   - `stability_class`
   - `windows_confirmed`
   - `stability_checked_at`
   - Any added fields must be backward-compatible with existing readers.

4. **Coverage persistence**
   - Either dedicated table or explicit extension of experiment ledger.
   - Must uniquely identify `(athlete_id, loop_type, test_key)` with last-scanned metadata.

---

## Loop 1: Multi-Window Discovery + Stability Enrichment

### What it does now

Runs `analyze_correlations()` across 6 windows (30d, 60d, 90d, 180d, 365d, full history), rolls back all writes, classifies stability, stores in JSONB.

### What it should do

**A. Discover new correlations at deeper windows.**

The daily sweep runs at 90 days. AutoDiscovery runs at 180d, 365d, and full history. Some correlations only emerge with longer data — seasonal effects, long-cycle patterns, training-block-level relationships.

When a correlation passes significance gates (`|r| >= 0.3, p < 0.05, n >= 10`) at a window the daily sweep doesn't cover, it should be created as a real `CorrelationFinding` with:
- `discovery_source = "auto_discovery"`
- `discovery_window_days` = the window where it was found
- `times_confirmed = 1` (it still needs to re-confirm through normal channels)

Promotion identity key (required):
- `athlete_id + input_name + output_metric + direction + lag_days + discovery_source`
- Existing row with same key must be updated (no duplicate create).

This finding enters the normal confirmation cycle. If the daily sweep confirms it in subsequent runs, `times_confirmed` increments. If it never re-confirms, it stays at 1 and doesn't surface (existing surfacing gate: `times_confirmed >= 3`).

**B. Annotate existing findings with stability evidence.**

For findings that already exist in `CorrelationFinding`, write stability metadata:
- `stability_class`: `stable` | `recent_only` | `strengthening` | `unstable`
- `windows_confirmed`: integer count of windows where the finding passed significance
- `stability_checked_at`: timestamp of last stability evaluation

This enrichment requires no approval. It's read-only analysis of existing data producing metadata about an already-confirmed finding.

**C. Detect and flag degrading findings.**

If a finding that was previously confirmed is no longer significant in any window shorter than 180 days, flag it:
- `stability_class = "degrading"`
- Log the degradation in the nightly report
- Do NOT auto-deactivate — the founder can review and decide

### Safety

- New findings still require `times_confirmed >= 3` before surfacing (existing gate)
- Stability annotation doesn't change the finding's significance or surfacing eligibility
- Degrading findings are flagged, not deactivated
- Experience guardrail catches bad downstream output

---

## Loop 2: Pairwise Interaction Discovery

### What it does now

Tests pairwise combinations across 4 output metrics, scores with Cohen's d + sample support, persists as JSONB candidates that nobody reads.

### What it should do

**A. Systematically explore the search space.**

2,415 input pairs × 9 output metrics = 21,735 tests. At current runtime (~1-2 seconds per pair per metric), a full sweep takes hours. AutoDiscovery should schedule this in batches across nights:

- Track which pairs have been tested and when
- Prioritize untested pairs, then pairs not tested in 30+ days
- Run N batches per night (tunable, start with enough to cover ~500 pair-metric tests per night)
- At that rate, full coverage in ~43 nights. Then re-scan for changes.

**B. Create real findings from reproduced interactions.**

When a pairwise interaction:
- Passes effect size threshold (`|d| >= 0.5`)
- Has adequate sample support (`n_high >= 5, n_low >= 5`)
- Has been seen in 3+ nightly runs
- Scores above the keep threshold

Create an `AthleteFinding` with:
- `investigation_type = "interaction_discovery"`
- `finding_type = "pairwise_interaction"`
- Structured `receipts` containing the two input signals, output metric, effect size, sample sizes, direction
- Coaching-language `sentence` using `friendly_signal_name()` for both inputs

Promotion identity key (required):
- `athlete_id + finding_type + sorted(input_a,input_b) + output_metric + lag_bucket`
- Use upsert semantics; repeated nightly confirmations must increment evidence/`times_seen` and update receipts summary, not duplicate rows.

This finding enters the normal surfacing pipeline. The fingerprint context wiring, morning voice, and coach all have access to it.

**C. Track exploration coverage.**

Persist a simple coverage map: which pair-metric combinations have been tested, when, and what the result was. This answers: "how much of the search space has the system explored for this athlete?"

### Safety

- `AthleteFinding` rows from interactions use the same supersession logic as investigation findings
- The `times_seen >= 3` requirement across nightly runs prevents one-night flukes from becoming findings
- `friendly_signal_name()` prevents raw variable names from reaching athletes
- The experience guardrail catches downstream trust breaks
- If a loop-level error rate exceeds threshold in a run, interaction promotion auto-disables for that athlete-run and logs reason.

---

## Loop 3: Per-Athlete Investigation Tuning

### What it does now

Generates bounded parameter candidates for 6 pilot investigations, evaluates baseline vs candidate FQS, persists keep/discard in JSONB.

### What it should do

**A. Apply proven improvements.**

When a tuning experiment shows:
- `score_delta >= TUNING_KEEP_THRESHOLD` (currently 0.03)
- The candidate doesn't degrade FQS for other findings from the same investigation
- The candidate has been kept across 2+ consecutive runs

Apply the parameter change. Store the per-athlete override in a config structure that the investigation reads at runtime:

```python
# Per-athlete investigation config (new)
AthleteInvestigationConfig(
    athlete_id: UUID,
    investigation_name: str,
    param_overrides: dict,  # e.g. {"lookback_days": 180, "min_samples": 15}
    applied_from_run_id: UUID,  # provenance
    applied_at: datetime,
    reverted: bool = False,
    reverted_at: Optional[datetime] = None,
)
```

Investigations check for per-athlete overrides before using registry defaults. This is the mechanism that makes investigations sharpen per-athlete over time.

Apply identity key (required):
- `athlete_id + investigation_name + normalized(param_overrides)`
- Same override should not be re-applied as a new active row on each run.

**B. Expand the pilot set gradually.**

Start with the 6 pilot investigations. As tuning proves stable (no founder reverts for 30 days), add more investigations to the tunable set. The goal is: every investigation with numeric parameters eventually gets per-athlete optimization.

**C. Track tuning history.**

For each investigation × athlete, maintain a history of applied parameter changes with FQS deltas. This becomes visible in the operating manual: "Your heat tax investigation uses a 180-day window (tuned from default 90 days, +0.08 FQS improvement)."

### Safety

- `score_delta` threshold prevents marginal changes from applying
- 2+ consecutive runs requirement prevents one-night artifacts
- No-degradation check prevents improving one finding at the cost of others
- Per-athlete config is revertable (set `reverted = True`)
- Founder can see all applied tuning via admin endpoint
- Apply path must enforce single active config per athlete x investigation.

---

## Admin Endpoint

### Purpose

Give the founder visibility into what AutoDiscovery changed overnight, without requiring approval for every change.

### Required endpoints

**`GET /v1/admin/auto-discovery/summary`**

Returns for the specified athlete:
- Last run: timestamp, status, experiment count
- Changes applied overnight: new findings created, stability annotations written, parameters tuned
- Pending review: degrading findings flagged, interaction candidates approaching promotion threshold
- Coverage: % of search space explored, pair-metrics tested vs total
- Score trends: aggregate FQS over last 7/30 runs

**`GET /v1/admin/auto-discovery/changes`**

Returns a paginated list of all changes AutoDiscovery has made:
- New findings created (with source, window, significance)
- Stability annotations applied
- Parameters tuned (with before/after and FQS delta)
- Findings flagged as degrading

Each change has a `revert` action available.

Required fields in every change item:
- `change_id`
- `change_type`
- `change_key`
- `run_id`
- `athlete_id`
- `created_at`
- `before_state`
- `after_state`
- `reverted` / `reverted_at`

**`POST /v1/admin/auto-discovery/revert/{change_id}`**

Reverts a specific change:
- Deactivates a finding created by AutoDiscovery
- Removes a stability annotation
- Reverts a parameter override to registry default

**`GET /v1/admin/auto-discovery/candidates`**

Returns the existing `get_founder_review_summary()` output — candidates that haven't yet met auto-promotion criteria but are worth watching.

### Auth

Founder-only. Use founder-gated route pattern consistent with current admin hardening:
- `Depends(get_current_user)` + explicit founder check
- no subscription-tier middleware gate
- malformed UUID query/body params must return 422 (schema validation), not 500.

---

## Search Space Management

### The problem

70 inputs × 9 outputs × 6 windows × 14 lags = 52,920 single-signal tests.
2,415 pairs × 9 outputs × 6 windows = 130,410 pairwise tests.
Total search space: ~183,000 tests.

Running all of these every night is unnecessary and expensive. The system needs to be smart about what it explores.

### Scheduling strategy

1. **First pass: full coverage.** Work through the entire single-signal and pairwise space in batches across nights. Track coverage. The goal is to explore everything at least once within 60 nights.

2. **Re-scan confirmed findings.** Findings that have been confirmed get re-scanned more frequently (every 14 days) to detect stability changes or degradation.

3. **Deprioritize dead ends.** Pair-metric combinations that produced no signal in the first pass get re-scanned less frequently (every 90 days). They're not dead — the athlete might start logging new data that changes things — but they're lower priority.

4. **Prioritize recent data expansion.** When a new input signal starts appearing (athlete begins daily check-ins, or starts logging nutrition), all combinations involving that signal get priority scanning.

### Runtime budget + fairness contract (required)

- Per-athlete nightly caps must be explicit and configurable:
  - max single-signal tests/night
  - max pairwise tests/night
  - max tuning experiments/night
  - max wall-clock time/night
- Scheduler must enforce fairness:
  - no single athlete can starve others
  - unfinished work rolls forward deterministically
- Timeout policy:
  - timed-out experiments are recorded as `error` with reason
  - no retry storm in same run
- Auto-disable trigger:
  - if error rate for a loop exceeds threshold (e.g., 20% in run), stop that loop's promotions for the run and emit alert field in report.

### Persistence

Add a scan coverage table or extend the experiment ledger to track:
- `(athlete_id, input_a, input_b_or_null, output_metric, window_days)` → last scanned, result (signal / no_signal / error)

This is the "research memory" that prevents redundant work and tracks progress.

---

## Feature Flag Changes

### Phase 1 flags

- `auto_discovery.mutation.live` → enabled for founder. `is_live_mutation_enabled()` returns the flag value instead of hardcoded `False`.
- `auto_discovery.surfacing.athlete` → enabled for founder. Discoveries enter the normal surfacing pipeline.
- `auto_discovery.auto_promote.stability` → enabled. Stability annotations auto-apply.
- `auto_discovery.auto_promote.findings` → enabled. New findings that pass gates auto-create.
- `auto_discovery.auto_promote.tuning` → enabled. Tuning improvements that pass criteria auto-apply.

Each auto-promote flag can be independently disabled if a loop produces bad results.

### Auto-disable thresholds (required)

Phase 1 must include machine-readable safeguards:
- `max_mutations_per_athlete_per_run` (default conservative)
- `max_total_mutations_per_run`
- `max_loop_error_rate` (promotion halted when exceeded)
- `max_revert_rate_7d` (auto-pause affected loop pending founder review)

When any threshold is exceeded:
- write disable reason to run report and change ledger
- stop further mutation in affected scope immediately
- continue non-mutating analysis if safe

---

## Acceptance Criteria

Phase 1 is complete when:

1. **Idempotency passes.**
   - Re-running the same athlete-run payload produces zero duplicate promoted findings/config rows.
   - Change log uniqueness constraints hold under replay tests.

2. **Mutation safety passes.**
   - Kill switches stop mutation immediately.
   - Auto-disable thresholds trigger and record machine-readable reasons.
   - No partial commit for athlete-run transaction boundaries.

3. **Promotion quality passes.**
   - New multi-window discoveries are created only when statistical gates pass.
   - Interaction findings promote only after 3+ reproduced runs and effect/sample thresholds.
   - Tuning applies only after threshold + consecutive-run + no-degradation checks.

4. **Revertability passes.**
   - Founder can revert each change type via `change_id`.
   - Revert operations are auditable and restore effective runtime behavior.

5. **Coverage/systematics pass.**
   - Coverage metrics monotonically increase during initial pass.
   - Scheduler honors nightly caps and fairness constraints.
   - Dead-end deprioritization and new-signal priority are evidenced in reports.

6. **Downstream experience safety passes.**
   - Existing surfacing gates remain intact unless explicitly changed.
   - Experience guardrail shows no net regression attributable to promoted changes.

7. **Operational visibility passes.**
   - Admin summary/changes endpoints expose last run, applied changes, pending flags, coverage, and score trends with pagination/filtering.

---

## What This Enables

Once Phase 1 is working:

- **Morning voice gets smarter overnight.** New findings and stability data feed directly into the briefing prompt.
- **Coach context is richer.** Interaction findings give the coach more specific things to say about the athlete's physiology.
- **The operating manual grows.** Stable, multi-window-validated findings are the highest-confidence entries.
- **Layer 5 (confidence trajectory) gets its data.** Stability classification over time IS the confidence trajectory.
- **The moat compounds.** A competitor would need to run the same nightly research for the same duration against the same athlete to catch up. The knowledge is time-locked.

---

## What This Does NOT Do

- Does not use LLMs for proposal generation (still structured optimization)
- Does not attempt 3-way or higher-order interactions (pairwise only)
- Does not build cross-athlete priors (N=1 only)
- Does not replace the daily correlation sweep (extends it)
- Does not auto-deactivate degrading findings (flags for founder review)
- Does not touch Phase 3B/3C gating or workout narratives

---

## Relationship to Build Roadmap

This is Horizon 3 items 3e-3g from `BUILD_ROADMAP_2026-03-09.md`:

> **3e-auto:** FQS metric implementation + validation → **Done (Phase 0B)**
> **3f-auto:** Shadow investigation runner → **Done (Phase 0A)**
> **3g-auto:** AutoInvestigation Loop v1 (structured optimizer) → **This spec**

The Build Roadmap's promise: "Nightly loop: modify investigation params → measure FQS → keep or discard."

Phase 1 fulfills that promise and extends it: not just tuning, but discovery, stability validation, and interaction detection — all feeding real improvements back into the athlete's fingerprint.

---

## Files Impacted

| File | Change |
|------|--------|
| `services/auto_discovery/orchestrator.py` | Add promotion executors, change shadow-only contract |
| `services/auto_discovery/feature_flags.py` | Remove hardcoded `return False` from mutation/surfacing guards |
| `services/auto_discovery/interaction_loop.py` | Add coverage tracking, finding creation |
| `services/auto_discovery/tuning_loop.py` | Add parameter application, history tracking |
| `services/auto_discovery/rescan_loop.py` | Add finding creation for deep-window discoveries, stability writes |
| `models.py` | Add `AthleteInvestigationConfig`, `AutoDiscoveryChangeLog`, stability fields on `CorrelationFinding`, coverage tracking |
| `routers/` (new or existing admin) | Admin endpoint for AutoDiscovery visibility |
| `services/race_input_analysis.py` | Read per-athlete config overrides before registry defaults |
| `alembic/versions/` | Migration for new fields and tables |
| `tests/` | Promotion idempotency tests, coverage tests, revert tests, auto-disable tests, guardrail integration |
