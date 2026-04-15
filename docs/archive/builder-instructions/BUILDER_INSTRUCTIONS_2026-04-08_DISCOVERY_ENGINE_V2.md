# Builder Instructions: Discovery Engine V2

**Date:** April 8, 2026
**Status:** APPROVED SPEC — reviewed by founder + advisor. Do not build until founder says BUILD.
**Scope:** Restructure the correlation engine from univariate point-in-time correlations to a multi-layer discovery system with derived signals, segmented outputs, domain-specified interactions, intra-workout cardiovascular extraction, and sequence monitoring.

---

## Context

The current correlation engine (`services/correlation_engine.py`) tests individual daily values against a single "efficiency" output at fixed lags 0-7 days using Pearson correlation. This is Layer 1. It works for linear relationships between individual inputs and individual outputs with enough data. It cannot detect:

- Trends and trajectories (5-day HRV decline vs single bad day)
- Signal volatility and stability
- Non-linear / threshold relationships
- Interaction effects (load × recovery)
- Sequential patterns (overreaching cascades)
- Direction reversals caused by moderating conditions
- Non-stationary relationships that change across training phases

This spec defines six layers that build on each other. Each layer is independently deployable and testable.

---

## Exclusions — Remove Before Building

### Permanently exclude from input space

| Signal | Reason |
|--------|--------|
| `garmin_body_battery_end` | Proprietary composite of upstream signals we already have raw. Uninterpretable. If it correlates, we don't know why. If Garmin changes the algorithm, historical findings break silently. |
| `garmin_avg_stress` | Same. Opaque composite. Remove from `_GARMIN_SIGNALS`, `CONFOUNDER_MAP`, and `DIRECTION_EXPECTATIONS`. |
| `garmin_max_stress` | Same. |

### Demote DIRECTION_EXPECTATIONS to advisory

Do NOT remove the table entirely — it serves coaching language generation. But change its role: direction expectations are **advisory for insight phrasing**, never for filtering or deprioritizing findings. A counterintuitive finding that survives significance gates is real for that athlete. The `direction_counterintuitive` flag stays for display purposes but must not suppress surfacing.

### Signal suppression inheritance

`fingerprint_context.py` has `_SUPPRESSED_SIGNALS` (garmin_steps, body_battery, etc.) and `_ENVIRONMENT_SIGNALS` (dew_point_f, temperature_f, etc.) that control what surfaces to the athlete. This spec introduces derived signals and interactions from these parents (e.g., `garmin_steps_trend_5d`, `heat_stress_index` which uses `dew_point_f × humidity_pct`).

**Rule:** Derived signals and interaction terms inherit suppression status from their parent signals **for athlete-facing surfaces only**. The engine still tests them internally and persists findings to the database. Findings exist; they just don't surface to the athlete via fingerprint, briefing, or coach context.

This keeps the research layer open (the engine discovers what matters) while respecting product decisions (the athlete sees curated signals). If a suppressed derived signal turns out to be consistently significant, that's evidence to reconsider the suppression decision — but the founder makes that call, not the engine.

**Implementation:** Check parent suppression status at display time in `fingerprint_context.py` and `n1_insight_generator.py`, not at computation time in the engine.

---

## Layer 1: Current Engine (cleanup only)

What exists today. Individual inputs → individual outputs at lags 0-7 days with Pearson correlation, significance gates (`|r| >= 0.3`, `p < 0.05`, `n >= 10`), temporal weighting, confounder control via partial correlation.

**Changes:**
- Remove excluded signals (body battery, Garmin stress)
- **Keep `hrv_rhr_ratio`** as a daily compound recovery metric. It captures absolute recovery magnitude (ratio of 1.2 vs 0.8 is meaningful). The Layer 4 `hrv_rhr_convergence` interaction measures something different — directional trend agreement, not magnitude. Both are valuable and neither replaces the other.
- Keep everything else as-is

---

## Layer 2: Derived Signals

### Concept

For each raw metric, compute trend, volatility, and baseline deviation signals at physiologically meaningful windows. These become new inputs alongside the raw values.

### Windows

Do NOT use a single arbitrary window. Use multiple windows and let the engine discover which matters for each athlete:

| Window | Rationale |
|--------|-----------|
| 3 days | Acute stimulus-response cycle (24-72h recovery arc) |
| 5 days | Short-term trend — captures one quality session + recovery |
| 14 days | Micro-cycle adaptation — is this training block working? |
| 30 days | Baseline reference — what is normal for this athlete right now? |

### Derivatives to compute

For each raw signal with sufficient data (>= window + 5 data points):

| Derivative | Computation | Signal name pattern |
|-----------|-------------|-------------------|
| **Trend (slope)** | Linear regression slope over rolling window, normalized by signal SD | `{signal}_trend_{window}d` |
| **Volatility** | Standard deviation over rolling window | `{signal}_volatility_{window}d` |
| **Baseline deviation** | `(today - rolling_mean_30d) / rolling_sd_30d` | `{signal}_deviation` |
| **State duration** | Consecutive days above or below 30-day rolling mean. Positive = above, negative = below. | `{signal}_state_days` |

### Which raw signals get derivatives

**Health signals (calendar-indexed, daily):**
- `garmin_hrv_5min_high` — trends at 3d, 5d. Baseline deviation. (Peak HRV — 39 data points currently, growing daily.)
- `garmin_hrv_overnight_avg` — trends at 3d, 5d. Baseline deviation. (Average HRV across overnight window — more stable than 5min peak for trend analysis. ~166 data points currently from wellness import.)
- `garmin_min_hr` — trends at 5d, 14d. Baseline deviation. (Absolute minimum observed HR, often during deepest sleep. Noisier — a single deep-sleep dip can spike it down.)
- `garmin_resting_hr` — trends at 5d, 14d. Baseline deviation. (Garmin's computed resting HR — `restingHeartRateInBeatsPerMinute`. More stable for trend analysis than `min_hr`. Add to `_GARMIN_SIGNALS` alongside `min_hr`. Let the engine discover which matters per athlete.)
- `garmin_sleep_score` — trends at 3d, 5d.
- `garmin_sleep_deep_s` — trends at 3d, 5d.
- `garmin_sleep_rem_s` — trends at 3d, 5d.

**Training load signals:**
- `tsb` — trend at 5d, 14d. State duration.
- `ctl` — trend at 14d, 30d.
- `atl` — trend at 5d, 14d.

**NOT derived (insufficient daily density or irrelevant):**
- Nutrition signals (sparse, self-reported)
- Body composition (weekly at best)
- Environmental (per-session, not daily)
- Work stress/hours (sparse)

### Implementation location

New function `compute_derived_signals()` in `correlation_engine.py`. Takes the raw `inputs` dict from `aggregate_daily_inputs()`. Returns additional derived series. Called after all raw inputs are aggregated, before correlation testing.

### Multiple comparison correction — Benjamini-Hochberg FDR

**Do NOT use Bonferroni correction.** The test count scales to ~4,000+ (100 inputs × 8 lags × 5 outputs). Bonferroni at `p < 0.05 / 4000 = 0.0000125` would require `|r| > 0.85` with n=39 to survive — no physiological signal produces that. The engine would be sterilized.

Use **Benjamini-Hochberg FDR** (false discovery rate) control instead, applied **per output metric**:

1. For each output metric (e.g., `efficiency_easy`), collect all p-values from the (input × lag) tests.
2. Rank them from smallest to largest: p(1), p(2), ..., p(m).
3. Find the largest rank k where `p(k) <= (k / m) × 0.05`.
4. All tests with rank <= k are significant.

This controls the *proportion* of false positives among discoveries at 5%, not the probability of *any* false positive. This is the correct framework for an exploratory discovery engine — you accept that ~5% of findings may be false, and the lifecycle tracking (`times_confirmed`, `time_stability_score`) weeds those out over time.

**Per-output partitioning rationale:** Each output metric is a separate research question. Testing whether sleep affects easy-run efficiency is independent of whether load affects interval quality. Treating them as one family penalizes plausible tests for implausible ones.

**Implementation:** Replace the flat `SIGNIFICANCE_LEVEL = 0.05` gate with a BH-FDR procedure in `analyze_correlations()`. The existing `|r| >= 0.3` and `n >= 10` gates remain as pre-filters before the FDR step.

---

## Layer 3: Output Segmentation

### Concept

Replace single "efficiency" output with session-type-specific outputs. A signal that predicts interval quality may have no relationship to easy run efficiency.

### Segmented outputs

| Output key | What it measures | How to compute |
|-----------|-----------------|---------------|
| `efficiency_easy` | Aerobic base — pace/HR on easy efforts | Filter activities where `workout_type` or `workout_zone` indicates easy/recovery. Existing `aggregate_efficiency_by_effort_zone(db, "easy")` may already do this. |
| `efficiency_threshold` | Lactate threshold performance | Filter for threshold/tempo sessions. Existing `aggregate_efficiency_by_effort_zone(db, "threshold")`. |
| `efficiency_hard` | VO2max/interval expression | Filter for interval/VO2max sessions. |
| `recovery_rate` | HRV rebound speed post-hard-session | Delta between `hrv_5min_high` on hard-session day and `hrv_5min_high` 48h later, divided by the drop. Higher = faster recovery. Use `hrv_5min_high` for the actual delta measurement (more sensitive to acute recovery). **Gated output:** only computed when athlete has 5+ `hrv_overnight_avg` readings per week (use `hrv_overnight_avg` for the gating check — it's more consistently populated; `hrv_5min_high` at 39 readings would rarely activate the gate). |

### What already exists

`aggregate_efficiency_by_effort_zone()` and `aggregate_pace_at_effort()` already exist in the engine but are only called when `output_metric` is explicitly set. The current default `analyze_correlations()` only uses unsegmented efficiency. Change: run the full input set against ALL segmented outputs in a single sweep, not separate calls. The existing unsegmented `efficiency` output remains and is included in the sweep as a fifth output metric.

### `workout_type` fallback chain

Some activities will have `workout_type = NULL` (particularly on the Garmin ingestion path — verify classifier wiring during build). Segmented outputs require session classification. Use this fallback chain:

1. `Activity.workout_type` (top-level indexed column, preferred)
2. `Activity.run_shape["summary"]["workout_classification"]` (JSONB path from shape extractor — note: this is a JSONB path, not a column. Access via `Activity.run_shape["summary"]["workout_classification"]`, not `Activity.workout_classification`.)
3. If both are NULL: exclude from segmented outputs. The activity still participates in unsegmented efficiency.

### Implementation

Modify `analyze_correlations()` to iterate over output metrics internally. Each (input, output_metric) pair is a separate test. Total tests = inputs × output_metrics × lags.

---

## Layer 4: Domain-Specified Interactions

### Concept

Auto-discovery cannot find interaction effects. These are explicit hypotheses informed by coaching knowledge. The engine tests them; it doesn't discover them.

### Interaction terms to construct and test

| Interaction | Computation | Hypothesis |
|------------|-------------|-----------|
| `load_x_recovery` | `tsb × garmin_hrv_5min_high_deviation` (both z-scored first) | High load with good recovery = productive. High load with poor recovery = overreaching. Neither alone predicts well. |
| `sleep_quality_x_session_intensity` | `garmin_sleep_score × next_day_intensity_score` | Poor sleep before easy run = irrelevant. Poor sleep before intervals = performance disaster. |
| `hrv_rhr_convergence` | `garmin_hrv_5min_high_trend_5d × (-1 × garmin_resting_hr_trend_5d)`. Positive when both trending in recovery direction. Use `resting_hr` not `min_hr` — convergence is about trending direction and `resting_hr` is more stable for trend detection. | Sustained convergent recovery predicts better quality sessions. |
| `heat_stress_index` | `dew_point_f × (1 + humidity_pct/100)` or similar validated heat index | Combined heat stress more predictive than either component. |
| `hrv_rhr_divergence_flag` | Binary: 1 when HRV and RHR trends disagree in direction for 3+ days, 0 otherwise | Divergence between autonomic indicators = unusual state worth flagging. |

### How interaction terms enter the engine

Computed in a new function `compute_interaction_terms()`. Takes raw + derived inputs. Returns additional (date, value) series. These are tested against all segmented outputs using the same correlation framework as Layer 1. They are inputs like any other — the engine doesn't know they're interactions.

### Adding new interactions

New interactions require a code change. This is intentional — each interaction is a hypothesis with a physiological rationale. The engine answers the question; the founder/coach asks it.

---

## Layer 5: Intra-Workout Cardiovascular Extraction

### Concept

The raw per-second HR trace (`ActivityStream.stream_data["heartrate"]`) combined with phase identification from `Activity.run_shape` allows computing intra-workout cardiovascular signals that are invisible to pre/post-session metrics.

### Prerequisites

- `ActivityStream` with `heartrate` and `time` channels (exists for Garmin runs)
- `Activity.run_shape` with phases and `workout_classification` (exists when shape extractor has run)
- Lap/phase boundaries that distinguish work from recovery periods

### Signals to extract

| Signal | Computation | Stored where |
|--------|-------------|-------------|
| `hr_recovery_60s` | HR at work phase end minus HR 60 seconds later. Average across all work phases in session. | New JSONB field on Activity or separate table |
| `hr_recovery_degradation` | `hr_recovery_60s` on first work phase minus `hr_recovery_60s` on last work phase. Measures intra-session autonomic fatigue. | Same |
| `hr_drift_pct` | For continuous threshold efforts: (HR in last 20% of effort - HR in first 20%) / HR in first 20% × 100. | Same |
| `peak_hr_response` | Max HR reached during work phases. Compared against athlete's recent max HR for same effort type. | Same |
| `session_cardiac_signature` | JSONB array of per-interval `{interval_num, avg_hr, peak_hr, recovery_60s, time_to_target_hr}` | New JSONB on Activity |

### Implementation

New service: `services/cardiac_signature.py`. 

Input: Activity + ActivityStream + run_shape.
Output: Cardiac signature dict, persisted on the Activity.

Called: after shape extraction completes for a new activity (or as a backfill job for existing activities with streams).

### Feeding into the correlation engine

The per-session cardiac signals become activity-level inputs (like `avg_cadence` or `elevation_gain_m` today). Added to `aggregate_activity_level_inputs()`:

- `intra_recovery_60s_avg` — average 60s recovery across intervals
- `intra_recovery_degradation` — first vs last interval recovery delta
- `hr_drift_pct` — cardiac drift on continuous efforts
- `peak_hr_deviation` — deviation from rolling peak HR for this effort type

### Session-over-session tracking

For comparable sessions (matched by `workout_type` + `workout_classification` + similar interval count):

- `cardiac_efficiency_trend` — slope of `hr_recovery_60s_avg` across last N comparable sessions
- `fatigue_resistance_trend` — slope of `hr_recovery_degradation` across last N comparable sessions

**Session-count windows, not calendar windows.** A fixed 28-day window fails for infrequent session types (threshold twice/month = 2 data points, no slope). Use:
- Last N comparable sessions, minimum N=4 to compute a meaningful slope
- Maximum lookback of 90 days (sessions separated by > 90 days may reflect different fitness states)
- If fewer than 4 comparable sessions exist within 90 days, this derivative is not computed for that session type

These are computed in `compute_derived_signals()` but using session-indexed data, not calendar-indexed.

### Protocol matching

Two sessions are "comparable" when:
- Same `workout_classification` (from shape extractor)
- Interval count within ±2
- Total duration within ±20%
- Not separated by > 90 days

This is a heuristic. RPI-relative matching is deferred until historical RPI backfill is implemented (separate scope).

---

## Layer 6: Sequence Monitoring

### Concept

Not correlation. Pattern matching with threshold logic. When multiple sensitive signals trend wrong simultaneously, flag it. This is a watchdog, not a statistical test.

### Monitored signals

The "overreaching dashboard" — these are the signals most sensitive to accumulated fatigue:

1. `garmin_hrv_5min_high_trend_5d` (from Layer 2)
2. `garmin_resting_hr_trend_5d` (from Layer 2) — inverted: rising RHR = bad. Use `resting_hr` not `min_hr` for the watchdog — trend detection needs the more stable signal.
3. `tsb` (raw) — declining into deep negative
4. `garmin_sleep_score_trend_5d` (from Layer 2)
5. Subjective feel trend (when available and calibrated — see below)

### Flagging logic

```
red_count = 0
if hrv_trend_5d < -threshold_hrv: red_count += 1
if rhr_trend_5d > +threshold_rhr: red_count += 1
if tsb < threshold_tsb: red_count += 1
if sleep_trend_5d < -threshold_sleep: red_count += 1

if red_count >= 3: flag "overreaching_risk"
if red_count >= 2 for 3+ consecutive days: flag "sustained_warning"
```

### Thresholds

Initially hardcoded at 1 SD below/above baseline. Per-athlete calibration comes later — after enough flagged events accumulate, the system can learn which threshold combinations preceded actual bad outcomes for this specific athlete.

### Subjective signals

Subjective feel (RPE, readiness, soreness) is included in monitoring ONLY when the engine has established that the athlete's subjective ratings have predictive value (i.e., the Layer 1 correlation between subjective inputs and performance outputs is significant with `|r| >= 0.3` for that athlete). For athletes where subjective data is noise (new runners, uncalibrated perception), subjective signals are excluded from the watchdog. The engine determines this automatically — no manual configuration.

### Implementation

New function `evaluate_overreaching_risk()` in a new service `services/readiness_monitor.py`. Called daily (via beat schedule) and on-demand before briefing generation. Returns a risk level and contributing signals. The briefing system and coach can reference this.

### Relationship to existing `readiness_score.py`

`services/readiness_score.py` already contains `ReadinessScoreCalculator` — a daily composite score using TSB, efficiency trend, completion, and recovery halflife. This is a **different concept**: a single scalar readiness score for display. The Layer 6 watchdog is a multi-signal convergence detector that flags specific risk patterns. They are architecturally separate services with different purposes. Do NOT merge them. The watchdog may reference the readiness score as one of its inputs, but it is not an extension of it.

### NOT a correlation

This layer does not produce findings or persisted CorrelationFinding rows. It produces a daily readiness assessment. It's operational monitoring, not research.

---

## Build Sequence

Each layer is independently deployable and testable. Dependencies flow downward.

| Phase | Layer | Dependency | Estimated scope |
|-------|-------|-----------|----------------|
| **A** | Exclusions + Layer 1 cleanup | None | Small — remove 3 signals, adjust DIRECTION_EXPECTATIONS role |
| **B** | Layer 2: Derived signals | Phase A | Medium — `compute_derived_signals()`, BH-FDR implementation |
| **C** | Layer 3: Output segmentation | Phase A | Medium — modify `analyze_correlations()` to sweep outputs |
| **D** | Layer 4: Interaction terms | Phases B + C | Medium — `compute_interaction_terms()`, 5 initial interactions |
| **E** | Layer 5: Intra-workout extraction | Independent of B/C/D | Large — new service, schema addition, backfill job, stream parsing |
| **F** | Layer 5 integration | Phases C + E | Medium — feed cardiac signals into engine, session-over-session tracking |
| **G** | Layer 6: Sequence monitoring | Phase B | Medium — `readiness_monitor.py`, beat schedule integration |

### Phase A+B+C together is the foundational build.

It transforms the engine from "single raw value vs single output" to "derived signals at multiple windows vs segmented outputs." Everything else builds on this.

### Phase E is the most novel and can run in parallel.

Cardiac signature extraction is independent of the correlation engine changes. It produces new data that Phase F then connects.

---

## What Is NOT In Scope

| Item | Why excluded |
|------|-------------|
| **Historical RPI backfill** | Required for RPI-relative protocol matching. Separate scope, separate spec. Session-over-session analysis uses heuristic matching until this exists. |
| **Non-linear / U-shape detection** | Requires replacing Pearson with mutual information or Spearman + threshold search. Valuable but complex. Deferred to V3 after V2 data accumulates. |
| **Full discriminant analysis of pre-session windows** | Requires labeled best/worst sessions and different statistical framework. Deferred until outcome labeling and sufficient session count exist. |
| **Automated interaction discovery** | Testing all possible pairs is combinatorially explosive. Domain-specified interactions (Layer 4) are the right approach. New interactions added by code change with physiological rationale. |
| **Time-varying relationships** | Detecting that a correlation changes across training phases requires segmented analysis windows. Partially addressed by temporal weighting. Full solution deferred. |
| **Nutrition signal derivatives** | Data too sparse for most athletes to compute meaningful trends. Revisit when nutrition tracking adoption increases. |
| **Long run durability output** | Deferred to V3. Requires reliable identification of runs > 15km, split selection logic for first-half/second-half efficiency, and split-level data. Not trivial — the builder should not make this call. |

---

## Data Requirements

| Signal | Current data points (founder) | Minimum for meaningful derivatives |
|--------|------------------------------|----------------------------------|
| `garmin_hrv_5min_high` | 39 | Trend at 3d needs 8+, at 5d needs 10+ — barely sufficient. Will improve organically. Do NOT compute 14d or 30d derivatives — insufficient data. |
| `garmin_hrv_overnight_avg` | ~166 | Sufficient for 3d and 5d trends. More stable than 5min peak. |
| `garmin_min_hr` | 168 | Sufficient for all windows. |
| `garmin_resting_hr` | ~168 (verify — populated from daily summary) | Sufficient for all windows. More stable than min_hr for trend analysis. |
| `garmin_sleep_score` | 326 | Sufficient. |
| `garmin_sleep_deep_s` | 326 | Sufficient. |
| `tsb` / `ctl` / `atl` | 366 | Sufficient. |
| Activities with streams | Unknown — need to verify count of ActivityStream rows with heartrate channel | Intra-workout extraction needs this for each session. |

---

## Success Criteria

**Phase A+B+C (foundational):**
- Engine produces findings from derived signals that were invisible to raw-value correlations
- Segmented outputs show different correlations per session type (confirming that lumping them was lossy)
- Total findings increase but BH-FDR-controlled significant findings are more robust than current

**Phase D (interactions):**
- At least one interaction term produces a significant finding where neither component was individually significant
- `load_x_recovery` or `hrv_rhr_convergence` demonstrates interaction effect

**Phase E+F (intra-workout):**
- Cardiac signatures computed for 80%+ of interval/threshold sessions with streams
- Session-over-session cardiac efficiency trajectory computable for at least one protocol type
- At least one intra-workout signal correlates with next-day HRV suppression or subsequent session quality

**Phase G (sequence monitoring):**
- Overreaching risk flag triggers on historically known fatigue periods (e.g., founder's November 2025 pre-injury period, retrospectively)
- Flag does NOT trigger during normal training variation (false positive rate < 20%)
