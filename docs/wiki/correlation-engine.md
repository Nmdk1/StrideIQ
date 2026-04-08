# Correlation Engine & Intelligence Pipeline

## Current State

The correlation engine is a scientific instrument for one athlete. It discovers individual relationships between inputs (sleep, HRV, stress, training load, weather, cross-training) and outputs (efficiency, pace, HR drift, recovery). The engine processes ~70 correlation inputs across daily and activity-level aggregations.

## How It Works

### Core Pipeline

Located in `services/correlation_engine.py`:

1. **Input aggregation:** `aggregate_daily_inputs()` and `aggregate_activity_level_inputs()` compute ~70 input signals per observation
2. **Bivariate Pearson correlation:** Each input vs each output metric, with 0-7 day lags (peak lag selected)
3. **Statistical gates:** `|r| >= 0.3`, `p < 0.05`, `n >= 10`
4. **Bonferroni correction:** Applied in the N1 insight path to control false discovery
5. **Temporal weighting:** Recent data matters more — L30: 4x, L31-90: 2x, L91-180: 1x, >180d: 0.75x
6. **Confirmation tracking:** `times_confirmed` increments on each sweep that re-confirms the pattern
7. **Direction validation + safety gate:** Via `OutputMetricMeta` whitelist

### Correlation Layers (L1-L4)

Implemented in `services/correlation_layers.py`:

- **L1 — Threshold detection:** Identifies non-linear boundaries (e.g., efficiency drops below 6.5h sleep)
- **L2 — Asymmetric response:** Tests whether above-threshold and below-threshold effects differ
- **L3 — Cascade/mediation:** Partial correlation with confounders. `compute_partial_correlation()` checks if a relationship survives controlling for mediators
- **L4 — Lagged decay:** Temporal offset effects (e.g., strength training → efficiency 5 days later)

### Finding Lifecycle

`CorrelationFinding` model stores discovered patterns with lifecycle states:

| State | Meaning | Who reads it |
|-------|---------|--------------|
| `emerging` | Pattern detected, not yet confirmed | Briefing (as question) |
| `active` | Confirmed ≥3 times, statistically significant | Manual, coach, plan engine |
| `active_fixed` | Rule-based (e.g., L-SPEC), not data-driven | Plan engine |
| `resolving` | Recent data no longer supports the pattern | Coach (context only) |
| `closed` | Resolved for ≥4 weeks without reasserting | Archive |
| `structural` | Long-standing physiological trait | Fingerprint bridge |
| `structural_monitored` | Structural but being tracked for change | Fingerprint bridge |

**Transition detection** (Limiter Engine Phase 5, built Apr 6, 2026):
- `active` → `resolving`: L30-weighted correlation drops below significance
- `resolving` → `closed`: Pattern stays resolved for 4 weeks
- `resolving` → `active`: Pattern reasserts

### Limiter Taxonomy

Seven limiter categories derived from active findings:

| Category | Meaning |
|----------|---------|
| L-VOL | Volume limiter |
| L-CEIL | Ceiling limiter |
| L-THRESH | Threshold limiter |
| L-REC | Recovery limiter (3-tier half-life gates) |
| L-CON | Consistency limiter |
| L-SPEC | Race-specific (rule-based, `active_fixed`) |
| L-NONE | No dominant limiter |

Resolution priority: L-SPEC (0) through L-NONE (6).

### Cross-Training Inputs (Phase 5)

Six cross-training inputs added to the correlation engine (Apr 5, 2026):

- `ct_strength_sessions_7d`, `ct_strength_tss_7d`, `ct_cycling_tss_7d`
- `ct_cross_training_tss_7d`, `ct_hours_since_strength`, `ct_hours_since_cross_training`

Direction expectations are **empty** — the engine discovers relationships without pre-baked assumptions.

### AutoDiscovery

Located in `services/auto_discovery/`:

- **Orchestrator** (`orchestrator.py`): Nightly at 4 AM UTC
- **Rescan loop** (`rescan_loop.py`): Re-evaluates existing candidates
- **Interaction loop** (`interaction_loop.py`): Tests input interactions
- **Tuning loop** (`tuning_loop.py`): Tunes thresholds and parameters
- **FQS adapters** (`fqs_adapters.py`): Finding Quality Score computation
- **Feature flags** (`feature_flags.py`): Master switch + individual loop flags

Models: `AutoDiscoveryRun`, `AutoDiscoveryExperiment`, `AutoDiscoveryCandidate`, `AutoDiscoveryChangeLog`, `AutoDiscoveryScanCoverage`.

The engine runs nightly and has produced: ~100 promoted findings, 62 stability annotations, 20 interaction candidates (as of Apr 6, 2026 manual trigger — nightly schedule confirmed working via beat startup dispatch fix).

### Fingerprint Bridge

`services/plan_framework/fingerprint_bridge.py` translates confirmed physiological findings into plan parameters:

- Recovery half-life → recovery spacing
- Quality spacing → minimum hours between quality sessions
- Cutback frequency → deload cadence

Currently only `cutback_frequency` and `quality_spacing_min_hours` are fully consumed by `n1_engine.py`. Wiring `limiter` and `primary_quality_emphasis` is a remaining step.

## Key Decisions

- **N=1 only:** No population statistics, no cohort defaults
- **Empty direction expectations:** Cross-training inputs have no pre-baked assumptions
- **Temporal weighting:** Recent data weighted 4x over historical (L30 vs >180d)
- **Bonferroni correction:** Controls false discovery rate in the N1 insight path
- **AutoDiscovery as shadow research:** Runs nightly, accumulates evidence, promotes to `CorrelationFinding` when statistically confident

## Known Issues

- **Nightly task scheduling:** Fixed via beat startup dispatch (Apr 6, 2026), but the underlying issue (beat container recreation on deploy) could regress if the dispatch pattern is removed
- **Fingerprint bridge partial consumption:** Plan engine only reads `cutback_frequency` and `quality_spacing_min_hours` from the bridge — `limiter` and `primary_quality_emphasis` are computed but not fully wired
- **Weekly digest bypasses intelligence:** The email surface runs `analyze_correlations()` raw instead of pulling from confirmed findings. LLM-coached digest is an interim step; long-term fix is wiring to the intelligence layer

## What's Next

- Wire `limiter` and `primary_quality_emphasis` from fingerprint bridge into `n1_engine.py` session scheduling
- Athlete Hypothesis Testing — athlete-stated hypotheses tested against individual data
- Cohort Intelligence (Layer 11) — matching confirmed individual patterns across athletes at ~500 users

## Sources

- `docs/specs/CORRELATION_ENGINE_ROADMAP.md` — vision and layer definitions
- `docs/specs/CORRELATION_ENGINE_LAYERS_1_4_SPEC.md` — layer implementation
- `docs/specs/CORRELATION_ENGINE_FULL_INPUT_WIRING_SPEC.md` — input wiring
- `docs/specs/LIMITER_TAXONOMY.md` — limiter categories and lifecycle
- `docs/specs/LIMITER_ENGINE_BRIEF.md` — limiter engine brief
- `docs/FINGERPRINT_VISIBILITY_ROADMAP.md` — visibility and surfaces
- `docs/specs/AUTO_DISCOVERY_PHASE0_SPEC.md` through `PHASE1_SPEC.md` — AutoDiscovery phases
- `apps/api/services/correlation_engine.py` — core engine
- `apps/api/services/correlation_layers.py` — L1-L4
- `apps/api/services/plan_framework/fingerprint_bridge.py` — bridge to plan engine
