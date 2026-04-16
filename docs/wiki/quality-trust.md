# Quality & Trust Principles

## Current State

StrideIQ's quality framework is built on five non-negotiable principles that govern every surface — coach, briefing, plan, Manual, and all intelligence outputs. These principles have been violated by previous agents who didn't know them. Every builder must internalize them.

## The Five Principles

### 1. N=1 Only — No Population Statistics

Every claim must come from **this athlete's data**. Never cite population averages, published studies, or "runners typically" patterns. The correlation engine discovers individual relationships; the coach speaks them. If the engine hasn't confirmed a pattern for this athlete, the system stays silent.

- **Wrong:** "Most runners see efficiency gains after 6 hours of sleep"
- **Right:** "Your last 27 runs show efficiency improves when you get 7+ hours" (confirmed by correlation engine)
- **Wrong:** "Studies show strength training reduces injury risk"
- **Right:** Silence (unless the engine has confirmed this for this athlete)

### 2. Suppression Over Hallucination

When the system doesn't have enough data, it says nothing — not something plausible. An empty card is better than a wrong card. A briefing that skips a topic is better than one that guesses.

- The coach earns trust incrementally: Phase 1 (Narrator) → Phase 2 (Advisor) → Phase 3 (Conditional Autonomy)
- Findings require `|r| >= 0.3`, `p < 0.05`, `n >= 10`, and `times_confirmed >= 3` before surfacing
- The KB violation scanner (`_check_kb_violations` in `services/coaching/_constants.py`) catches claims that violate known rules
- Template narratives are banned — every statement must be grounded in data

### 3. The Athlete Decides, The System Informs

The system does NOT silently swap workouts, override the athlete, or "protect" them from productive stress. When it detects a divergence, it proposes an adjustment and the athlete accepts or rejects.

- Plan adaptations require explicit athlete approval
- Silence = keep original plan (not acceptance)
- The coach can suggest but never prescribe without data backing
- `PlanAdaptationProposal` model tracks proposals with accept/reject/expire lifecycle

### 4. No Threshold Is Universal

Easy pace is a **ceiling**, not a range. Training zones are individual. RPI (Race Performance Index) is the **only** source for race predictions and training paces — never Riegel, never VDOT tables, never population-derived formulas.

- **`AthleteTrainingPaceProfile`** stores individual pace zones derived from race history
- Race predictions come from `individual_performance_model.py` using RPI only
- BC-12 in the plan evaluator: no pace predictions when `rpi: None`

### 5. Never Hide Numbers

Raw data is always visible. Interpretation sits on top of data, never replaces it. Both HRV values displayed (Recovery HRV = `hrv_5min_high`, Overnight Avg = `hrv_overnight_avg`). TSS breakdown shown (running + cross-training). The athlete sees exactly what goes into their numbers.

## Implementation: Where These Principles Are Enforced

### KB Rule Registry

76 annotated rules in `docs/specs/KB_RULE_REGISTRY_ANNOTATED.md`. Evaluated by `scripts/eval_kb_rules.py` (445 PASS / 0 FAIL / 17 WAIVED as of Apr 4, 2026). Categories include:

- **GP-** (General Principles)
- **PH-** (Phase Rules)
- **WS-** (Workout Selection)
- **REC-** (Recovery)
- **QD-** (Quality Density)

### Coach Anti-Hallucination Guardrails

Located in `services/coaching/core.py` (and mixins under `services/coaching/`):

- **Data-verification discipline:** "When citing specific paces, splits, or workout metrics in comparison, you MUST use the actual data from the tools available to you. Never infer from workout titles or summaries."
- **Athlete calibration:** The prompt adapts to athlete experience level — an experienced BQ runner with proven self-regulation patterns does not get default conservatism
- **Fatigue threshold context:** During deliberate build/overreach phases approaching a race, fatigue thresholds are acknowledged as context, not surfaced as warnings
- **Date rendering:** All dates in LLM context include pre-computed relative labels via `_relative_date()` in `services/coach_tools/_utils.py` — the LLM never computes relative time itself

### Briefing Guardrails

Located in `routers/home.py`:

- **Environmental comparison discipline:** Never compare runs across seasons without accounting for heat adjustment (`heat_adjustment_pct`, dew point model)
- **Sleep source contract:** Only cite Garmin-measured sleep, never self-reported unless explicitly labeled
- **Workout structure authority:** When `shape_classification` disagrees with `_summarize_workout_structure`, trust the shape extractor (stream-level resolution vs mile splits)
- **Recent activity window:** "Recent Runs" section is date-bounded (10 days), not unbounded `.limit(5)`

### Plan Quality Gates

- `plan_quality_gate.py` — quality checks before surfacing plans
- `scripts/eval_plan_quality.py` — evaluator (143 PASS / 0 FAIL / 11 WAIVED)
- P0 gate on `plan_framework/` changes — requires attestation in CI
- 12 Blocking Criteria (BC-1 through BC-12) from `N1_ENGINE_ADR_V2.md`

### OutputMetricMeta

Defined in `n1_insight_generator.py`. Whitelist of metrics with verified directional interpretation. Any metric not in the whitelist is fail-closed — the system cannot make directional claims about it.

## Known Issues

- **Interval classification false positives:** Rebuilt with 5-gate architecture (Apr 7, 2026) but the underlying problem — two independent classification systems (`shape_extractor` and `_summarize_workout_structure`) — remains architectural debt
- **Weekly digest quality:** LLM-coached digest via `send_coached_digest()` in `email_service.py` is functional but the founder rated it unsatisfactory. Long-term fix: wire to confirmed findings from the intelligence layer instead of raw `analyze_correlations()` output
- **Coach conservatism calibration:** Prompt was updated to be athlete-calibrated (Apr 6, 2026) but new athletes still need a mechanism to communicate their experience level beyond what Garmin data shows

## What's Next

- Briefing-to-coach response loop (tappable emerging pattern questions → coach chat with pre-loaded finding context → fact extraction → lifecycle classifier)
- Environmental comparison normalization in briefing (pre-filter or explicitly instruct LLM)
- Athlete Hypothesis Testing (`docs/specs/ATHLETE_HYPOTHESIS_TESTING_SPEC.md`) — athlete-stated hypotheses tested against their own data

## Sources

- `docs/FOUNDER_OPERATING_CONTRACT.md` — non-negotiable principles (verbatim)
- `docs/PRODUCT_MANIFESTO.md` — voice and trust philosophy
- `docs/specs/KB_RULE_REGISTRY_ANNOTATED.md` — 76 rules
- `docs/specs/N1_ENGINE_ADR_V2.md` — blocking criteria
- `docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md` — never-hide-numbers, HRV standard
- `docs/COACH_RUNTIME_CAP_CONFIG.md` — cap configuration
