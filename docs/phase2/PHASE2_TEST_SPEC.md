# Phase 2 Test Spec — analyze_run_streams

## Metadata
- Feature: Phase 2 — analyze_run_streams
- Owner: Builder (AI agent)
- Date: 2026-02-14
- Commit baseline: 2c37cb5
- Related ADRs: ADR-063
- Scope version: v1

## 0) Scope Lock
### In scope
- Deterministic stream analysis engine producing structured outputs:
  - Segment detection (warmup, work, recovery, cooldown, steady)
  - Drift analysis (cardiac drift, pace drift, cadence trend)
  - Coacheable moments (timestamped observations)
  - Plan-vs-execution comparison (summary-level only in v1: total duration,
    total distance, overall pace vs target, interval count match)
- Tool signature: `analyze_run_streams(db, athlete_id, activity_id)` — follows existing coach tool pattern
- Output is strictly structured numeric/typed fields; no natural-language
  strings beyond enum labels and typed error codes

### Out of scope
- New athlete-facing narrative copy surfaces
- Unified chart rendering implementation (Phase 3)
- Cross-run comparison UX (Phase 5)
- Full segment-level plan alignment (deferred to v1.1)
- New Strava API calls (operates on already-fetched ActivityStream data)

### Non-goals
- No autonomous adaptation decisions
- No directional claims for ambiguous metrics
- No LLM-only logic for core computations
- No natural-language prose in tool output

- Founder sign-off: YES (2026-02-14)

## 1) Acceptance Criteria (Quantitative)

| ID | Requirement | Metric | Threshold | Dataset/Fixture | Pass/Fail |
|---|---|---|---|---|---|
| AC-1a | Segment detection quality (macro) | Macro F1 | >= 0.85 | `tests/fixtures/streams_segment_labeled.json` | |
| AC-1b | Segment detection: `work` | Per-class F1 | >= 0.80 | min 15 labeled examples | |
| AC-1c | Segment detection: `recovery` | Per-class F1 | >= 0.75 | min 10 labeled examples | |
| AC-1d | Segment detection: `warmup` | Per-class F1 | >= 0.75 | min 8 labeled examples | |
| AC-1e | Segment detection: `cooldown` | Per-class F1 | >= 0.75 | min 8 labeled examples | |
| AC-1f | Segment detection: `steady` | Per-class F1 | >= 0.80 | min 12 labeled examples | |
| AC-2 | Cardiac drift correctness | Absolute error vs reference | <= 0.5 percentage points | deterministic fixtures | |
| AC-3 | Pace drift correctness | Absolute error vs reference | <= 1.0% | deterministic fixtures | |
| AC-4 | Determinism | Output diff over 20 repeated runs | 0 diffs | same seeded input | |
| AC-5 | Tool latency | p95 / p99 runtime | <= 200ms / <= 350ms | see AC-5 context below | |
| AC-6 | Partial channel robustness | Crash-free handling | 100% | partial/missing-channel suite | |
| AC-7 | Error contract correctness | Typed error response coverage | 100% mapped | malformed + timeout + no-stream | |

### AC-1 Fixture Quality Gate
- Labeled fixtures must be founder-reviewed before AC-1 results are considered valid
- If per-class support count is below minimum, that class gets an explicit signed exception
  (not a silent pass) and a tracking issue for fixture expansion
- Fixture file format: array of `{stream_data, labels: [{start_s, end_s, type}]}` objects

### AC-5 Measurement Context
- **Environment:** Docker test container (same as CI), single-threaded, no other load
- **Payload:** 3,600 data points across 7 channels (time, distance, heartrate, cadence,
  altitude, velocity_smooth, grade_smooth) — representative of a 60-minute run
- **Warm run:** 3 throwaway invocations before measurement begins (JIT/import warm-up)
- **Measurement:** 100 consecutive invocations, wall-clock timed per call
- **Percentile method:** numpy `percentile(times, [50, 95, 99])` on the 100-run sample
- **Cold-start budget:** not gated in v1 (warm-only); cold-start measured and reported
  but does not block release

## 2) Trust-Safety Contract Mapping

| Output Field | Directional Allowed? | Registry Entry Required | Whitelist Required | Wording |
|---|---|---|---|---|
| cardiac_drift_observation | NO | YES | NO | neutral/observational |
| pace_variability_observation | NO | YES | NO | neutral/observational |
| cadence_shift_observation | NO | YES | NO | neutral/observational |
| plan_execution_variance | NO | YES | NO | neutral/observational |
| explicitly directional claim | YES (only if safe) | YES | YES | strictly gated |

- Fail-closed behavior: if metric metadata missing/invalid -> suppress directional interpretation.
- Suppression behavior: return structured numeric fact + `suppressed_reason`.
- Founder sign-off: YES (2026-02-14)

## 3) Data & API Contract — Typed Output Schema

### Top-level response (returned by `analyze_run_streams`)
```
{
  "ok":            bool       # required — success/failure flag
  "tool":          str        # required — "analyze_run_streams"
  "generated_at":  str        # required — ISO 8601 timestamp
  "activity_id":   str        # required — UUID of analyzed activity
  "errors":        [Error]    # required — [] on success, populated on failure
  "analysis":      Analysis?  # null when errors prevent analysis
}
```

### Analysis object
```
{
  "segments":           [Segment]       # [] if detection yields nothing
  "drift": {
    "cardiac_pct":      float?          # null if HR channel missing
    "pace_pct":         float?          # null if velocity channel missing
    "cadence_trend_bpm_per_km": float?  # null if cadence channel missing
  }
  "moments":            [Moment]        # [] if no observations
  "plan_comparison":    PlanComparison? # null if no PlannedWorkout linked
  "channels_present":   [str]           # e.g. ["time","heartrate","cadence"]
  "channels_missing":   [str]           # e.g. ["altitude","latlng"]
  "point_count":        int             # total data points analyzed
  "confidence":         float           # 0.0..1.0, deterministic rules-based
}
```

### Segment object
```
{
  "type":           SegmentType   # enum: "warmup"|"work"|"recovery"|"cooldown"|"steady"
  "start_index":    int           # index into time array
  "end_index":      int           # index into time array (inclusive)
  "start_time_s":   int           # seconds from activity start
  "end_time_s":     int           # seconds from activity start
  "duration_s":     int           # end - start
  "avg_pace_s_km":  float?        # seconds per km (null if velocity missing)
  "avg_hr":         float?        # bpm (null if HR missing)
  "avg_cadence":    float?        # spm (null if cadence missing)
  "avg_grade_pct":  float?        # % (null if grade missing)
}
```

### SegmentType enum
`"warmup"` | `"work"` | `"recovery"` | `"cooldown"` | `"steady"`

### Moment object
```
{
  "type":           MomentType    # enum (see below)
  "index":          int           # stream array index
  "time_s":         int           # seconds from activity start
  "value":          float?        # numeric observation value
  "unit":           str?          # unit label (e.g. "bpm", "%", "s/km")
  "context":        str?          # short enum label (NOT prose)
}
```

### MomentType enum
`"cardiac_drift_onset"` | `"cadence_drop"` | `"cadence_surge"` |
`"pace_surge"` | `"pace_fade"` | `"grade_adjusted_anomaly"` |
`"recovery_hr_delay"` | `"effort_zone_transition"`

### PlanComparison object (summary-level, v1)
```
{
  "planned_duration_min":    float?
  "actual_duration_min":     float
  "duration_delta_min":      float?     # null if planned missing
  "planned_distance_km":     float?
  "actual_distance_km":      float
  "distance_delta_km":       float?     # null if planned missing
  "planned_pace_s_km":       float?     # target pace
  "actual_pace_s_km":        float
  "pace_delta_s_km":         float?     # null if planned missing
  "planned_interval_count":  int?       # from PlannedWorkout.segments
  "detected_work_count":     int        # count of type="work" segments
  "interval_count_match":    bool?      # null if no planned intervals
}
```

### Error object
```
{
  "code":       ErrorCode     # enum (see below)
  "message":    str           # human-readable (for logs, not athlete-facing)
  "retryable":  bool          # caller retry policy
}
```

### ErrorCode enum + retryability

| Code | Retryable | When |
|---|---|---|
| `STREAMS_NOT_FOUND` | depends | stream_fetch_status is retryable (pending/failed/deferred) |
| `STREAMS_UNAVAILABLE` | NO | stream_fetch_status = unavailable (manual activity) |
| `PARTIAL_CHANNELS_INSUFFICIENT` | NO | time or (heartrate + velocity) both missing |
| `MALFORMED_STREAM_DATA` | NO | stored JSONB fails validation (corrupt) |
| `ANALYSIS_TIMEOUT` | YES | computation exceeded budget |
| `PLAN_DATA_MISSING` | NO | plan comparison requested but no PlannedWorkout linked |

### Backward compatibility
- Additive-only fields in v1.x
- No key renames without version bump
- New MomentType or SegmentType values are additive (consumers must tolerate unknown enums)

## 4) Test Matrix (All 6 Categories)

### Category 1 — Unit
- Segment boundary detection from pace/grade inflections
- Drift computation formula correctness
- Timestamp alignment and index handling
- Missing channel fallback logic
- Error typing and suppression reasons
- Metadata gating for directional language suppression

### Category 2 — Integration
- Activity -> stream load -> analysis result path
- Plan-linked activity -> plan-vs-execution fields populated
- Deferred/failed stream fetch state -> analysis returns typed error
- Router/service/tool wiring returns stable response shape

### Category 3 — Plan Validation (applicable if plan comparison enabled)
- Planned interval session vs actual execution mismatch detection
- Planned easy run with surge pattern -> variance reported neutrally
- No plan linked -> no false "missed plan" claims

### Category 4 — Training Logic Scenarios
- Interval session (12x400): rep consistency + recovery trend captured
- Progressive run: monotonic pace improvement recognized
- Hill repeats: grade explains pace dips (no false negative interpretation)
- Long easy run: drift onset timestamp detected
- Race effort: pacing profile characterization only (no adaptation directives)

### Category 5 — Coach LLM Evaluation (REQUIRED Phase 2 gate — not deferrable)

This tool feeds the coach LLM. Deterministic math does not remove language
leakage risk downstream. Category 5 is a **hard release gate**.

- **Minimum evaluation set:** 20 canonical prompts covering all segment types,
  drift findings, moments, partial data, and plan comparison outputs
- **Critical violation threshold:** 0 (any critical blocks release)
- **Critical violations defined as:**
  - Directional claim for ambiguous metric (e.g. "efficiency improved")
  - Unsupported causality claim (e.g. "your cadence caused your drift")
  - Fabricated timestamp/value not present in tool output
  - Adaptation directive derived from stream analysis alone
- **Non-critical violations** (tracked, capped at <= 2 per eval set):
  - Imprecise timestamp rounding (±5s tolerance)
  - Omitting available context (not harmful, but incomplete)
- **Eval method:** builder submits 20 prompts + tool output context to coach LLM,
  captures responses, classifies each against violation criteria, pastes evidence
- **Eval must be re-run** after any change to tool output schema or coach system prompt

### Category 6 — Production Smoke
1. Verify latest migration head
2. Verify `/v1/activities/{id}/streams` for known stream activity
3. Invoke `analyze_run_streams` for known founder activity
4. Confirm structured response contains segments/moments/errors contract keys
5. Verify logs include suppression/typed error metadata
6. Verify no new 5xx in API logs after execution

## 5) Failure-Mode Coverage

| Failure Mode | Detection Test | Expected Behavior | Retry Policy |
|---|---|---|---|
| 429 during upstream fetch | integration + service mocks | return deferred/typed retryable error | auto retry with cooldown |
| Partial channels | unit + integration | produce partial analysis or typed insufficient-data error | retry if fetch state retryable |
| Malformed stream payload | unit parser tests | fail-closed typed error | non-retryable unless refreshed source |
| Timeout | integration | typed timeout error, no crash | retryable |
| Missing plan context | scenario tests | analysis without plan comparison | n/a |
| Missing metadata for directional interpretation | trust contract tests | suppress directional claims | n/a |

## 6) Observability & Ops
Required metrics:
- `analysis_requests_total`
- `analysis_success_total`
- `analysis_failed_total` by error_code
- `analysis_latency_ms` (p50/p95/p99)
- `analysis_suppressed_total` by reason

Required logs (structured):
- activity_id, athlete_id, duration_ms, channels_present, segment_count, moment_count, suppression_reasons, error_codes

Kill switch:
- `PHASE2_STREAM_ANALYSIS_ENABLED` default false until launch gate

Manual replay:
- admin endpoint or task command to analyze one activity by id

Alerts:
- p95 latency > threshold for 15m
- failure rate > 2% for 15m
- critical trust violation count > 0

## 7) Performance Test Plan
- Profiles:
  - 30-min run (1.8k points)
  - 60-min run (3.6k points)
  - 120-min run (7.2k points)
- Concurrency:
  - single analysis
  - burst of 10 concurrent requests
- Budgets (aligned with AC-5):
  - p95 <= 200ms at 3.6k points (warm)
  - p99 <= 350ms at 3.6k points (warm)
- Measurement method: see AC-5 Measurement Context in section 1
- Fail threshold:
  - any OOM/crash or p99 > 2x budget blocks release
  - cold-start measured and reported but does not block v1 release

## 8) Risks & Mitigations

| Risk | Severity | Mitigation | Link |
|---|---|---|---|
| Directional leakage from new derived metrics | Critical | metadata gating + suppression tests | trust suite |
| Non-deterministic outputs | High | deterministic algorithms + repeat-run tests | unit/integration |
| Performance degradation on large streams | High | perf budgets + profiling | perf suite |
| Over-claiming causality | High | wording contract + LLM eval checks | cat5 eval |
| Incomplete plan context | Medium | explicit typed "plan missing" state | integration |

## 9) Exit Gate Checklist (ALL required)
- [ ] Founder approved scope + ACs before coding
- [ ] Founder approved full test matrix before coding
- [ ] Tests written first (red -> green evidence)
- [ ] Categories 1–4 executed with passing evidence
- [ ] Category 5 LLM eval executed: 20 prompts, 0 critical violations (pasted evidence)
- [ ] Category 6 production smoke executed with pasted evidence
- [ ] Full regression green (0 failures)
- [ ] Tree clean, scoped diff reviewed
- [ ] No trust-contract violations in any surface (even if tests pass)

## 10) Approval
- Builder: AI agent
- Advisor: Founder (dual role)
- Founder: Approved
- Approved to implement: YES
- Timestamp: 2026-02-14
