# System Audit: N=1 Insight Engine

**Date:** 2026-01-19  
**Auditor:** Opus 4.5 (Planner)  
**Purpose:** Map current state to desired N=1 Insight Engine architecture

---

## Executive Summary

StrideIQ has substantial analytical infrastructure already built. The gap is not capability—it's **wiring**. Data is collected but not fully correlated. Services exist but aren't orchestrated as an insight engine. The Coach uses LLM reasoning where tool computation should dominate.

**Key Finding:** 82 services exist. The architecture is there. Completing the vision requires:
1. Expanding correlation inputs (check-in fields, TSB as input)
2. Expanding correlation outputs (pace/effort, recovery speed, PRs)
3. Reframing Coach as tool orchestrator, not reasoning engine
4. Building dynamic insight suggestions from computed data

---

## 1. Data Models (32 Tables)

### 1.1 Core Athlete Data

| Model | Purpose | Fields | Used in Correlations |
|-------|---------|--------|---------------------|
| `Athlete` | User profile | 30+ fields including physiological baselines (max_hr, rpi, threshold_pace) | Partially (baselines not correlated) |
| `Activity` | Training activities | duration, distance, HR, pace, workout_type, weather | ✅ Yes |
| `ActivitySplit` | Per-mile/km data | pace, HR, cadence, GAP | ✅ Yes (efficiency calculation) |
| `PersonalBest` | PRs by distance | time, pace, distance_category | ❌ Not used as output |
| `BestEffort` | Strava best efforts | Within-activity bests | ❌ Not used |

### 1.2 Check-In / Wellness Data

| Model | Purpose | Fields | Used in Correlations |
|-------|---------|--------|---------------------|
| `DailyCheckin` | Daily wellness | sleep_h, stress_1_5, soreness_1_5, rpe_1_10, hrv_rmssd, resting_hr, enjoyment_1_5, confidence_1_5, motivation_1_5 | **Partial** |

**Gap:** Only `sleep_h`, `hrv_rmssd`, `resting_hr` are pulled into correlation engine. Missing:
- `stress_1_5`
- `soreness_1_5`
- `rpe_1_10`
- `enjoyment_1_5`
- `confidence_1_5`
- `motivation_1_5`

### 1.3 Nutrition Data

| Model | Purpose | Fields | Used in Correlations |
|-------|---------|--------|---------------------|
| `NutritionEntry` | Food tracking | calories, protein_g, carbs_g, fat_g, fiber_g, timing, entry_type | **Partial** |

**Gap:** Daily aggregates (protein, carbs) are correlated. Missing:
- Pre-activity nutrition → activity efficiency (activity_id link exists but unused)
- Post-activity nutrition → recovery speed
- Timing effects (meal timing relative to workout)

### 1.4 Body Composition

| Model | Purpose | Fields | Used in Correlations |
|-------|---------|--------|---------------------|
| `BodyComposition` | Weight/body metrics | weight_kg, body_fat_pct, muscle_mass_kg, bmi | ✅ weight_kg, bmi correlated |

### 1.5 Work/Life Context

| Model | Purpose | Fields | Used in Correlations |
|-------|---------|--------|---------------------|
| `WorkPattern` | Work stress/hours | work_type, hours_worked, stress_level | ✅ Yes |

### 1.6 Training Plans

| Model | Purpose | Fields | Used in Correlations |
|-------|---------|--------|---------------------|
| `TrainingPlan` | Plan definition | goal_race, target_time, phases | ❌ Not correlated |
| `PlannedWorkout` | Scheduled workouts | workout_type, target metrics, completion status | ❌ Not correlated |

**Gap:** Plan adherence (completed vs skipped) not correlated with outcomes.

### 1.7 N=1 Learning Models (ADR-036)

| Model | Purpose | Status |
|-------|---------|--------|
| `AthleteCalibratedModel` | Banister τ1/τ2 parameters | ✅ Built, not exposed to Coach |
| `AthleteWorkoutResponse` | How athlete responds to stimulus types | ✅ Built, not exposed to Coach |
| `AthleteLearning` | What works/doesn't for this athlete | ✅ Built, not exposed to Coach |

**Gap:** These N=1 learning models exist but aren't surfaced as Coach tool outputs.

---

## 2. Analytical Services (82 Services)

### 2.1 Core Analytics (Used)

| Service | Purpose | Coach Tool? |
|---------|---------|-------------|
| `efficiency_analytics.py` | EF calculation, trends, stability | ✅ via `get_efficiency_trend` |
| `training_load.py` | TSB/CTL/ATL calculation | ✅ via `get_training_load` |
| `correlation_engine.py` | Statistical correlations | ✅ via `get_correlations` |
| `coach_tools.py` | Coach-facing data access | ✅ Primary interface |

### 2.2 Advanced Analytics (Built but Not Wired to Coach)

| Service | Purpose | Coach Tool? |
|---------|---------|-------------|
| `attribution_engine.py` | Multi-factor performance drivers | ❌ Not exposed |
| `trend_attribution.py` | What's driving efficiency trends | ❌ Not exposed |
| `causal_attribution.py` | Granger causality testing | ❌ Not exposed |
| `insight_aggregator.py` | Generates prioritized insights | ❌ Not exposed |
| `run_analysis_engine.py` | Workout-level analysis | ❌ Not exposed |
| `feedback_loop.py` | Hypothesis → Intervention → Validation | ❌ Not exposed |
| `recovery_metrics.py` | Recovery half-life, durability | ❌ Not exposed |
| `query_engine.py` | Flexible data queries | ❌ Not exposed |
| `race_predictor.py` | Race time predictions | ❌ Not exposed |

**Key Finding:** Substantial analytical capability exists but isn't accessible to the Coach.

### 2.3 Service Dependency Map

```
User Query
    ↓
AI Coach (ai_coach.py)
    ↓
coach_tools.py (5 tools)
    ↓
┌──────────────────────────────────────────────────────────┐
│ efficiency_analytics.py                                   │
│ training_load.py (TrainingLoadCalculator)                │
│ correlation_engine.py                                     │
└──────────────────────────────────────────────────────────┘
    ↓
Database Models
```

**Missing connections:**
```
attribution_engine.py ─────┐
trend_attribution.py ──────┤
insight_aggregator.py ─────┼─── NOT CONNECTED TO COACH
recovery_metrics.py ───────┤
query_engine.py ───────────┘
```

---

## 3. Correlation Engine Gap Analysis

### 3.1 Current Inputs (aggregate_daily_inputs)

| Input | Source | Status |
|-------|--------|--------|
| sleep_hours | DailyCheckin.sleep_h | ✅ |
| hrv_rmssd | DailyCheckin.hrv_rmssd | ✅ |
| resting_hr | DailyCheckin.resting_hr | ✅ |
| work_stress | WorkPattern.stress_level | ✅ |
| work_hours | WorkPattern.hours_worked | ✅ |
| daily_protein_g | NutritionEntry (aggregated) | ✅ |
| daily_carbs_g | NutritionEntry (aggregated) | ✅ |
| weight_kg | BodyComposition.weight_kg | ✅ |
| bmi | BodyComposition.bmi | ✅ |

### 3.2 Missing Inputs

| Input | Source | Priority |
|-------|--------|----------|
| stress_1_5 | DailyCheckin | P1 |
| soreness_1_5 | DailyCheckin | P1 |
| rpe_1_10 | DailyCheckin | P1 |
| enjoyment_1_5 | DailyCheckin | P2 |
| confidence_1_5 | DailyCheckin | P2 |
| motivation_1_5 | DailyCheckin | P2 |
| overnight_avg_hr | DailyCheckin | P2 |
| TSB (current) | TrainingLoadCalculator | P1 |
| CTL (fitness) | TrainingLoadCalculator | P1 |
| ATL (fatigue) | TrainingLoadCalculator | P1 |
| pre_activity_carbs | NutritionEntry (linked) | P2 |
| workout_type_yesterday | Activity | P2 |
| days_since_long_run | Activity | P2 |
| plan_adherence_7d | PlannedWorkout | P2 |

### 3.3 Current Outputs

| Output | Source | Status |
|--------|--------|--------|
| efficiency_factor | Activity + Splits | ✅ Only output |

### 3.4 Missing Outputs

| Output | Source | Priority |
|--------|--------|----------|
| pace_at_easy_hr | Activity (HR zone filtered) | P1 |
| pace_at_threshold_hr | Activity (HR zone filtered) | P1 |
| recovery_speed | EF normalization post-hard effort | P1 |
| workout_completion_rate | PlannedWorkout | P1 |
| PR_delta | PersonalBest (improvement rate) | P2 |
| decoupling_pct | ActivitySplit (2nd half vs 1st) | P2 |
| long_run_fade | ActivitySplit (last 25% pace drop) | P2 |

---

## 4. Coach Architecture Gap

### 4.1 Current Architecture

```
User Message
    ↓
OpenAI Assistants API (gpt-4o)
    ↓
LLM decides whether to call tools
    ↓
If yes: coach_tools.py (5 functions)
    ↓
LLM generates response (may ignore tool output)
```

**Problems:**
1. LLM reasoning dominates (expensive, unreliable)
2. Only 5 tools available (tiny fraction of analytical capability)
3. LLM can hallucinate instead of using tool output
4. Model is gpt-4o ($0.08/query)

### 4.2 Target Architecture

```
User Message
    ↓
Intent Parser (gpt-3.5-turbo or gpt-4o-mini)
    ↓
Tool Router (deterministic mapping)
    ↓
Analytics Tools (many services)
    ↓
Structured Results
    ↓
Response Formatter (gpt-3.5-turbo or gpt-4o-mini)
    ↓
Insight with Evidence
```

**Benefits:**
1. Tools do computation (deterministic, auditable)
2. LLM only parses and formats (cheap, simple)
3. All insights grounded in data
4. Cost: ~$0.002/query instead of $0.08

---

## 5. Phased ADR Roadmap

### Phase 1: Complete Correlation Wiring (ADR-045)

**Scope:**
- Add missing check-in fields to correlation inputs
- Add TSB/CTL/ATL as correlation inputs
- Add pace_at_effort and recovery_speed as outputs
- Add workout_completion_rate as output

**Acceptance Criteria:**
- All DailyCheckin fields queryable as correlates
- TSB shows in correlation results
- Recovery speed calculable and correlatable

**Estimated Effort:** Medium (service changes, no new architecture)

---

### Phase 2: Expose Hidden Analytics to Coach (ADR-046)

**Scope:**
- Add coach tools for:
  - `get_attribution` (what's driving trends)
  - `get_recovery_metrics` (recovery half-life, durability)
  - `get_insights` (prioritized insight list)
  - `get_race_prediction` (physics-based projection)
  - `get_learning` (what works for this athlete)

**Acceptance Criteria:**
- Coach can answer "what's affecting my efficiency" with attribution data
- Coach can answer "how fast do I recover" with calculated metrics
- Coach surfaces N=1 learnings

**Estimated Effort:** Medium (wiring existing services)

---

### Phase 3: Coach Architecture Refactor (ADR-047)

**Scope:**
- Implement intent parser (classify query type)
- Implement tool router (map intent to tools)
- Switch to cheaper model for parse/format
- Add model decision tree (simple → 3.5, standard → mini, complex → 4o)
- Force tool usage for all data queries

**Acceptance Criteria:**
- Cost per query < $0.01
- All factual responses backed by tool output
- No hallucinated metrics

**Estimated Effort:** High (architectural change)

---

### Phase 4: Dynamic Insight Suggestions (ADR-048)

**Scope:**
- Replace static suggestion templates with computed insights
- Suggestions reference actual data ("Your tempo Tuesday showed...")
- Suggestions surface anomalies and patterns
- Suggestions are ranked by relevance/recency

**Acceptance Criteria:**
- Suggestions include specific dates, metrics, comparisons
- Suggestions update based on athlete's current state
- At least 3 context-aware suggestions per session

**Estimated Effort:** Medium (uses insight_aggregator + formatting)

---

### Phase 5: Activity-Linked Nutrition Correlation (ADR-049)

**Scope:**
- Correlate pre-activity nutrition with that activity's efficiency
- Correlate post-activity nutrition with recovery speed
- Track meal timing relative to workout start

**Acceptance Criteria:**
- Can answer "does eating carbs before my long run help?"
- Can answer "does protein intake affect my recovery?"

**Estimated Effort:** Medium (data model supports it, needs correlation logic)

---

## 6. Cost Model

### Current (gpt-4o)

| Metric | Value |
|--------|-------|
| Cost per query | ~$0.08 |
| 2000 athletes × 5 queries/day | $800/day |
| Monthly cost | **$24,000** |

### Target (tool-centric with model routing)

| Query Type | Model | Cost |
|------------|-------|------|
| Factual lookup | gpt-3.5-turbo | $0.001 |
| Standard coaching | gpt-4o-mini | $0.002 |
| Complex generation | gpt-4o | $0.08 |

| Scenario | Mix | Monthly Cost |
|----------|-----|--------------|
| 80% simple, 15% standard, 5% complex | Weighted | ~$1,500 |

**Savings:** ~$22,500/month at scale

---

## 7. Dependencies

```
Phase 1 (Correlation Wiring)
    ↓
Phase 2 (Expose Analytics) ←── Can run in parallel with Phase 1
    ↓
Phase 3 (Coach Refactor) ←── Requires Phase 1 & 2 complete
    ↓
Phase 4 (Dynamic Suggestions) ←── Requires Phase 2
    ↓
Phase 5 (Nutrition Correlation) ←── Independent, can run anytime
```

---

## 8. Recommendation

**Start with Phase 1 (ADR-045)** — Completing the correlation wiring is foundational. Every subsequent phase benefits from having all data points correlatable.

**Parallel Phase 2 (ADR-046)** — Exposing hidden analytics is low-risk and immediately valuable.

**Phase 3 (ADR-047) is the big win** — Coach architecture refactor delivers the cost savings and reliability improvements.

---

## Appendix A: Service Inventory (82 Services)

<details>
<summary>Full list</summary>

**Core Analytics:**
- efficiency_analytics.py
- training_load.py
- correlation_engine.py
- coach_tools.py

**Attribution/Causal:**
- attribution_engine.py
- trend_attribution.py
- causal_attribution.py
- run_attribution.py

**Insights/Patterns:**
- insight_aggregator.py
- pattern_recognition.py
- feedback_loop.py
- run_analysis_engine.py

**Performance:**
- race_predictor.py
- rpi_calculator.py
- rpi_enhanced.py
- performance_engine.py
- pace_normalization.py
- pace_decay.py

**Recovery/Metrics:**
- recovery_metrics.py
- athlete_metrics.py
- consistency_streaks.py

**N=1 Learning:**
- individual_performance_model.py
- model_cache.py
- optimal_load_calculator.py

**Plan Generation:**
- plan_generator.py
- plan_generator_v2.py
- model_driven_plan_generator.py
- constraint_aware_planner.py
- week_theme_generator.py
- workout_prescription.py
- principle_plan_generator.py

**Query/Context:**
- query_engine.py
- athlete_context.py
- contextual_comparison.py
- activity_comparison.py
- activity_analysis.py

**Coach/AI:**
- ai_coach.py
- ai_coaching_engine.py
- knowledge_extraction.py
- knowledge_extraction_ai.py
- narrative_translator.py
- narrative_memory.py

**Integration:**
- strava_service.py
- strava_webhook.py
- strava_pbs.py
- garmin_service.py
- platform_integration.py

**Utilities:**
- token_encryption.py
- email_service.py
- audit_logger.py
- data_export.py
- bmi_calculator.py
- neutral_terminology.py
- wma_age_factors.py
- alan_jones_2025_factors.py
- best_effort_service.py
- personal_best.py
- activity_deduplication.py
- blending_heuristics.py
- runner_typing.py
- anchor_finder.py
- pre_race_fingerprinting.py
- efficiency_calculation.py
- efficiency_trending.py
- outcome_tracking.py
- workout_classifier.py
- perception_prompts.py
- run_delivery.py
- calendar_signals.py
- home_signals.py
- availability_service.py
- ab_test_plans.py
- fitness_bank.py
- plan_audit.py
- plan_export.py
- workout_feedback_capture.py
- workout_templates.py
- nutrition_parser.py
- rpi_lookup.py (DEPRECATED - copyrighted)

</details>

---

## Appendix B: Model Field Inventory

<details>
<summary>All DailyCheckin fields</summary>

- id (UUID)
- athlete_id (UUID)
- date (Date)
- sleep_h (Numeric) ✅ Correlated
- stress_1_5 (Integer) ❌ Not correlated
- soreness_1_5 (Integer) ❌ Not correlated
- rpe_1_10 (Integer) ❌ Not correlated
- notes (Text)
- hrv_rmssd (Numeric) ✅ Correlated
- hrv_sdnn (Numeric) ❌ Not correlated
- resting_hr (Integer) ✅ Correlated
- overnight_avg_hr (Numeric) ❌ Not correlated
- enjoyment_1_5 (Integer) ❌ Not correlated
- confidence_1_5 (Integer) ❌ Not correlated
- motivation_1_5 (Integer) ❌ Not correlated

</details>

---

**Audit Complete. Ready for Judge approval to proceed with ADR-045.**
