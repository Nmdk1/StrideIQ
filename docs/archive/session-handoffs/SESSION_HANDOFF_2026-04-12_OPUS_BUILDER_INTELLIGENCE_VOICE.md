# Session Handoff — Opus Builder: Intelligence Voice Layer

**Date:** April 12, 2026
**From:** Founder's advisor (Opus session, active since Apr 9)
**To:** New Opus builder
**Task:** Build the intelligence voice layer — the translation between StrideIQ's data systems and athlete-facing language

---

## Before You Touch Anything

You are an Opus builder. That means the founder expects you to THINK before you build. Read the operating contract — it says "discuss → scope → plan → test design → build." Not "read spec → start coding." The founder will terminate you if you skip the thinking phase. They have done this before today.

### Mandatory Read Order

Read ALL of these before your first tool call. Not skim — read. If you cannot reference specific content from these docs in your first message to the founder, you haven't read them.

**Vision (understand the soul):**
1. `docs/FOUNDER_OPERATING_CONTRACT.md` — how to work. Non-negotiable. Key sections: "The Cardinal Rule: Do Not Start Coding," "The Planning → Building Loop," "Non-Negotiables" (especially #5 Suppression Over Hallucination, #7 No Threshold Is Universal, #8 No Template Narratives). Anti-patterns 1, 2, 3, and 4 are all directly relevant to your task.
2. `docs/PRODUCT_MANIFESTO.md` — the soul. Key line: "The chart makes you open the app. The intelligence makes you trust it. The voice makes you need it." And: "It just doesn't speak yet." The manifesto describes a system where "scattered along that shape are moments where the system noticed something you couldn't feel." That is your target quality level.
3. `docs/PRODUCT_STRATEGY_2026-03-03.md` — the moat. 16 priority-ranked concepts. Everything flows from the correlation engine producing true, specific, actionable findings about a single human. Read concepts #1 (Pre-Race Fingerprint), #2 (Proactive Coach), #5 (Personal Operating Manual), and #11 (Forward-Projection of Findings) — these are the surfaces your voice layer feeds.
4. `docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md` — Part 1 is critical: the Visual → Narrative → Fluency loop. "The narrative is not decoration on top of the chart. The narrative is what teaches the athlete to read the chart." Part 4 lists explicitly rejected ideas — do NOT re-propose Templates for Coachable Moments.

**Wiki (understand the systems):**
5. `docs/wiki/index.md` — the single onboarding doc. Tells you about every system in one page.
6. `docs/wiki/correlation-engine.md` — the scientific instrument at the heart of the product. Understand: bivariate Pearson with 0-7 day lags, Bonferroni correction, `CorrelationFinding` lifecycle (emerging → active → resolving → closed → structural), `OutputMetricMeta` registry for polarity safety.
7. `docs/wiki/coach-architecture.md` — AI coach system, context builders, tools. Kimi K2.5 universal routing.
8. `docs/wiki/product-vision.md` — current state of all product surfaces. The honest assessment of what's built and what's missing.
9. `docs/wiki/frontend.md` — component architecture, routes, data layer (TanStack Query), contexts. The `StreamHoverContext` pattern is directly relevant.

**Your spec (understand the task):**
10. `docs/specs/INTELLIGENCE_VOICE_SPEC.md` — **THIS IS YOUR PRIMARY SPEC.** Written today by the advisor session after a deep diagnosis with the founder. Contains the problem statement, the Hattiesburg failure case, seven principles, architecture, and surface-by-surface changes needed. Every section is binding.
11. `docs/BUILDER_INSTRUCTIONS_2026-04-12_ACTIVITY_PAGE_TABBED_LAYOUT.md` — the visual layout spec. A **separate Composer builder** is handling this in parallel (see "Parallel Work" section below). You handle the intelligence content. Know what they're building so your output fits their slots.

---

## The Problem You're Solving

The founder — the most engaged user — does not read the Manual or Progress pages. Ever. The activity page intelligence was confidently wrong on his half marathon pacing run. Strava's shallow attaboys on the same run were correct.

### The Hattiesburg Run: The Concrete Failure Case

**The run:** Hattiesburg Half Marathon, 13.2mi at 9:16/mi, pacing someone at their 9:30 target pace. 127bpm avg, 1.2% cardiac drift. A perfectly executed pacing effort — the founder ran 60 seconds/mi slower than his easy pace on purpose, held heart rate rock-steady, and delivered his friend to a finish.

**StrideIQ said:** "Efficiency 7.2% worse than your recent recovery runs. Check for fatigue or illness."

**This was confidently wrong.** The system compared a 13-mile pacing effort against 5-mile recovery jogs by speed/HR ratio, found the ratio was lower (of course — he was running slower on purpose), and concluded something was wrong with the athlete. On a perfectly executed run.

**Strava said:** "Solid half marathon pacing effort — you stayed comfortable in endurance zones while maintaining your 12-day streak with steady consistency."

**This was correct but shallow.** Strava read the title ("9:30 pacer"), understood purpose, compared to the athlete's own history ("slower than your typical 8:39"), and explained the deviation ("expected when pacing others"). No false alarms. But nothing the athlete didn't already know.

**What a coach would say:** "You held 127bpm across 13 miles with 1.2% cardiac drift. Three months ago you were drifting 6% at the same effort over 10 miles. Your aerobic base is genuinely rebuilding."

**This is the StrideIQ standard: correct AND deep.** One sentence. Uses data the system already has (drift trend from stream analysis history). Tells the athlete something they didn't know — that today's stability represents measurable progress from where they were post-injury. It matters to them.

---

## Root Cause Analysis

Seven root causes produce the wrong, obvious, or dead language across every intelligence surface. These are not hypothetical — they are verified in the codebase.

### 1. Two classification systems don't talk to each other

`WorkoutClassifier` in `services/workout_classifier.py` runs at sync time. It reads the activity title, parses keywords (tempo, interval, race, pacer, etc.), handles negation contexts ("skipped intervals"), and writes a purpose-aware `workout_type` to `Activity.workout_type`. It correctly identified the Hattiesburg run.

`RunAnalysisEngine.classify_workout()` in `services/run_analysis_engine.py` (line 304) runs at view time. It **ignores the title entirely** and **ignores the stored `workout_type`**. Its only race detection is a substring check on `activity.workout_type` for the word "race" (line 327). It then falls through to `classify_effort()` which classifies by HR alone. Low HR → "easy" regardless of distance, intent, or context. The Hattiesburg run at 127bpm was classified "easy" and evaluated as a failed easy run instead of a successful pacing effort.

**The fix:** Wire `WorkoutClassifier`'s stored `workout_type` into `RunAnalysisEngine` as the primary classification source. The classification hierarchy should be: (1) athlete's manual WorkoutTypeSelector input, (2) stored `workout_type` from sync-time classifier, (3) planned workout match, (4) effort classification from metrics as last resort.

### 2. The efficiency metric (speed/HR) is wrong for easy/recovery runs

`get_efficiency_attribution()` in `services/run_attribution.py` (line 373) computes efficiency as `speed_mps / avg_hr` (via `_compute_gap_efficiency`). This metric penalizes deliberately slow running. A pacing run at 9:30/mi scores "low efficiency" vs 8:20/mi easy runs because speed is lower at the same HR. That's not inefficiency — that's intentional pace restraint.

The tiered fallback cascade (lines 430-494) means a 13-mile pacing run with no Tier 1 peers gets compared to Tier 2 (same type, any distance), then Tier 3 (similar distance), then Tier 4 (all recent runs in 28 days). By Tier 4, it's comparing against 5-mile recovery jogs. The resulting "7.2% worse" is mathematically correct but semantically wrong.

The right metric for easy/recovery/pacing efforts is **cardiac decoupling** — the drift between HR and pace over the run. Low drift = aerobically efficient regardless of absolute pace. `run_stream_analysis.py` already computes this. The Hattiesburg run's 1.2% drift is exceptional.

**The fix:** Replace speed/HR efficiency with purpose-appropriate metrics. Easy/recovery/pacing: cardiac decoupling. Workout/tempo: pace hold vs target. Races: split consistency, negative split analysis. Long runs: decoupling + pace stability in final third.

### 3. Activity findings are not activity-specific

`GET /v1/activities/{id}/findings` in `routers/activities.py` (line 884) returns the global top-3 active correlation findings by `times_confirmed`. Same three findings on every single activity — whether it's a recovery jog or a marathon. No relevance filtering against what actually happened on this run.

```python
# Current code (line 905-915): just queries global top-3
findings = (
    db.query(_CF)
    .filter(
        _CF.athlete_id == current_user.id,
        _CF.is_active.is_(True),
        _CF.times_confirmed >= 3,
        ~_CF.input_name.in_(_suppressed),
    )
    .order_by(_CF.times_confirmed.desc())
    .limit(3)
    .all()
)
```

**The fix:** Filter findings to those relevant to THIS activity. Show an efficiency finding when decoupling was notably high or low. Show a sleep finding when pre-run sleep was poor. Show a load finding after a volume spike week. Show nothing when nothing applies to this run.

### 4. N=1 insight language is algorithm-speak ("dead language")

`_build_insight_text()` in `services/n1_insight_generator.py` (line 530) produces text like:

> "Based on your data: YOUR running efficiency is noticeably associated with changes the following day when your leg freshness is higher."

Every finding reads the same. Same structure, same cadence, same dead energy. This is a template applied to a statistical output. It is not a voice. No athlete reads this. No coach would say it. The founder literally never visits the Manual page because of this language.

The template pattern (line 571-574):
```python
text = (
    f"Based on your data: YOUR {friendly_output} is {qual} "
    f"associated with changes{timing} when your {friendly_input} is higher."
)
```

**The fix:** Redesign `_build_insight_text` to produce coaching-voice text with implications and specificity. "When your sleep drops below 6.5 hours, your easy pace the next day is about 15 seconds/mi slower — this has held 12 times." Not "YOUR running efficiency is associated with changes when your sleep is higher."

### 5. Obvious findings aren't suppressed

"Fresh legs improve efficiency" is not worth saying. "Sleep affects performance" is not worth saying. Any correlation that a runner would already know provides zero value and creates reading fatigue. There is no novelty or actionability filter.

**The fix:** Add a novelty gate before surfacing any finding. The bar: would the athlete say "I didn't know that" or "I should change something"? If not, suppress. Known-obvious pairs (leg freshness → efficiency, sleep → performance) should be explicitly suppressed unless the specific threshold or timing is surprising.

### 6. No per-chart intelligence

Strava puts an "Athlete Intelligence" card under each chart (pace, HR, HR zones). Our system shows one generic block. The system has the per-chart data — drift, zones, segments, moments — in `run_stream_analysis.py`. Nobody assembles it into per-chart insights.

**The fix:** Generate deterministic 1-2 sentence observations for each chart. Pace chart: pace consistency, split trend, comparison to target if planned. HR chart: drift, decoupling, HR ceiling. Zone breakdown: time-in-zone relative to purpose. Each card describes something visible in the chart PLUS the deeper context the chart alone can't show (longitudinal trend, correlation finding, plan context).

### 7. No longitudinal comparison

"1.2% cardiac drift" is a number. "1.2% drift — down from 6% three months ago over shorter distance" is a story. The stream analysis cache has historical drift data. Nobody queries it for comparison. Every metric is a snapshot, never a trajectory.

**The fix:** Compute drift/decoupling trend across last N similar-effort runs. Surface trajectory: "improving," "stable," "declining" with magnitude. This is the difference between Strava (correct but shallow) and a coach who knows you (correct AND deep).

---

## What You're Building: Three-Phase Plan

The Intelligence Voice Spec (`docs/specs/INTELLIGENCE_VOICE_SPEC.md`) has the full architecture. Build in this order.

### Phase 1: Stop Being Wrong (the floor)

This phase eliminates false positives. After this, the system never confidently says something wrong about a well-executed run.

1. **Wire `WorkoutClassifier`'s stored `workout_type` into `RunAnalysisEngine`** as the primary classification source.
   - `classify_workout()` (line 304 of `run_analysis_engine.py`) should check `activity.workout_type` from the DB before falling through to HR-based classification.
   - The priority: (1) athlete's manual `WorkoutTypeSelector` reclassification, (2) stored `workout_type` from sync-time `WorkoutClassifier`, (3) planned workout match, (4) effort classification from HR/pace metrics.

2. **Replace speed/HR efficiency with cardiac decoupling for easy/recovery runs** in `run_attribution.py`.
   - When `workout_type` indicates easy, recovery, or pacing: use cardiac decoupling from `run_stream_analysis.py` instead of speed/HR ratio.
   - When `workout_type` indicates workout/tempo: use pace hold vs target.
   - When `workout_type` indicates race: use split consistency.
   - Speed/HR ratio can remain as an internal diagnostic but should NOT be surfaced to the athlete as "efficiency" for easy-effort runs.

3. **Make the comparison peer set distance-mandatory.**
   - Don't fall back from Tier 1 → Tier 2 → Tier 3 → Tier 4 when there aren't enough similar runs.
   - If Tier 1 (same type + similar distance) has fewer than 2 peers, suppress the efficiency attribution entirely rather than comparing against meaningless peer sets.
   - Silence over wrong confidence.

4. **Suppress "check for fatigue" when the run's purpose explains the deviation.**
   - If the run was classified as pacing/recovery/easy and the speed was deliberately lower, don't flag low speed/HR as a problem.

### Phase 2: Say Something Worth Hearing (the ceiling)

This phase produces intelligence worth reading. After this, the athlete learns something they didn't know.

1. **Per-chart insight generation.**
   - Deterministic 1-2 sentence observations for: pace chart, HR chart, zone breakdown.
   - Each card is tied to what the chart shows PLUS longitudinal context.
   - Pace chart: pace consistency, split trend, comparison to target. Add: "vs your last 3 similar efforts."
   - HR chart: drift metric, decoupling, HR ceiling context. Add: "trend over last N runs."
   - Zone breakdown: time-in-zone relative to purpose. Add: "compared to your typical distribution."

2. **Activity-relevant finding filter.**
   - Replace the global top-3 in `GET /v1/activities/{id}/findings` with activity-specific filtering.
   - Match finding `input_name` to this activity's actual pre-state (sleep, HRV, stress, load).
   - Show a sleep finding when pre-run sleep was notably low/high relative to the finding's threshold.
   - Show nothing when no finding's input is relevant to this run's signals.

3. **Longitudinal comparison.**
   - Query stream analysis cache for historical drift/decoupling on similar-effort runs.
   - Compute trend (improving/stable/declining) with specific magnitude.
   - Surface: "1.2% drift today — down from 6% three months ago" instead of just "1.2% drift."

4. **Purpose-aware evaluation criteria.**
   - Different output for easy runs (decoupling, HR stability) vs workouts (pace hold) vs races (split consistency) vs long runs (decoupling + final-third stability).

### Phase 3: Rewrite the Dead Language

This phase transforms algorithm-speak into coaching voice. After this, the Manual page is worth reading.

1. **Redesign `_build_insight_text` in `n1_insight_generator.py`.**
   - Replace the template pattern with coaching-voice text.
   - Include specific thresholds: "below 6.5 hours" not "when your sleep is higher."
   - Include magnitude: "about 15 seconds/mi slower" not "associated with changes."
   - Include confirmation count: "this has held 12 times" — builds trust.

2. **Add novelty filter.**
   - Suppress findings that any runner would already know without being told.
   - Explicit suppression list for known-obvious pairs.
   - Algorithmic suppression for low-information findings (e.g., r < 0.4 with obvious direction).

3. **Add actionability.**
   - Close the loop from "X correlates with Y" to "this means Z for your training."
   - "When your sleep drops below 6.5h, your easy pace the next day suffers by ~15sec/mi. You slept 5.2h last night."
   - Connect findings to the athlete's current state when context exists.

---

## What the Founder Expects From You

1. **Discuss before building.** Your first response should show you've read and understood the problem. Present your analysis. Ask questions. Identify the hard technical decisions. The founder will tell you when to start coding. If you immediately start writing code, you will be terminated. This has happened to other agents.

2. **Show evidence, not claims.** Paste test output. Show real activity data run through the new logic. Don't claim "this is better" — prove it against the Hattiesburg run and other real activities. "It should work" is not acceptable. "All tests pass" without pasted output is not acceptable.

3. **The quality bar is coaching quality.** Every piece of text your system produces must pass the test: "Would a running coach who knows this athlete say this?" If not, suppress it or rewrite it. The founder is an experienced runner and coach — BQ qualifier, coaches state-record holders, ran 84mpw at peak, currently rebuilding from injury at 57 years old. They will immediately catch bad coaching logic.

4. **Suppression over hallucination.** If the system doesn't have enough data to say something specific, say nothing. Zero insights on an activity is better than one wrong insight. This is Non-Negotiable #5 from the operating contract, and it applies with extra force on athlete-facing intelligence.

5. **No template narratives.** This is Non-Negotiable #8. "A template gets old the second time you read it. I would want to puke." — the founder's actual words (operating contract, anti-pattern #2). If the system can't say something genuinely contextual — referencing this athlete's recent data, this point in their training cycle, what happened last week — it says nothing.

6. **The Athlete Trust Safety Contract applies.** Read `n1_insight_generator.py` lines 1-59 and the cursor rule `athlete-trust-efficiency-contract.mdc`. Efficiency (speed/HR) is polarity-ambiguous. Never claim "improving" or "declining" for ambiguous metrics. Use `OutputMetricMeta` registry for all directional language. This contract was created because agents kept making wrong directional claims.

---

## Parallel Work: Composer Is Building the Layout

A separate Composer agent is building the tabbed layout from `docs/BUILDER_INSTRUCTIONS_2026-04-12_ACTIVITY_PAGE_TABBED_LAYOUT.md` and `docs/SESSION_HANDOFF_2026-04-12_COMPOSER_TABBED_LAYOUT.md`. They are:

- Creating a tab container (Overview, Splits, Analysis, Context, Feedback) — desktop left sidebar, mobile horizontal tabs
- Extracting "Going In" and Findings into dedicated components (`GoingInStrip.tsx`, `GoingInCard.tsx`, `FindingsCards.tsx`)
- Setting up hover linkage (chart → map → elevation profile) across tabs
- **Leaving intelligence card SLOTS empty** until your backend work produces insights worth showing
- Explicitly NOT rendering `WhyThisRun` or `RunContextAnalysis` in the Overview tab — those produce wrong intelligence

Your backend work feeds into their frontend slots. The coordination points:

| What | How it connects |
|------|----------------|
| Per-chart insights | Your backend returns them via updated `/v1/activities/{id}/attribution` response → Composer's empty card slots under each chart |
| Activity-relevant findings | Your backend filters them via updated `/v1/activities/{id}/findings` endpoint → Composer's `FindingsCards.tsx` on Context tab |
| Purpose-aware classification | Your backend sets correct `workout_type` → Composer can display purpose label in header |

The Composer is not waiting for you — they're building the layout with empty slots. You are not waiting for them — you're fixing the backend intelligence. The endpoints already exist; you're changing what they return, not creating new routes.

---

## Complete File Reference

### Backend files you will modify

| File | What it does now | What's broken | What to fix |
|------|-----------------|---------------|-------------|
| `apps/api/services/run_analysis_engine.py` | Classifies workout by HR, computes context analysis | `classify_workout()` (line 304) ignores stored `workout_type` and activity title. Only race detection is substring check for "race" (line 327). Falls through to HR-based classification which calls `classify_effort()`. | Wire `activity.workout_type` as primary source. Use effort classification only as fallback. |
| `apps/api/services/run_attribution.py` | Computes "Why This Run?" attributions: pace decay, TSB, pre-state, efficiency | `get_efficiency_attribution()` (line 373) uses speed/HR ratio universally. Tier 1-4 fallback cascade (lines 430-494) degrades to meaningless peer sets. "Check for fatigue or illness" message (line 528) fires on purpose-low-speed runs. | Replace speed/HR with purpose-appropriate metrics. Suppress when no meaningful peer set exists. Remove false-alarm messaging for pacing/recovery runs. |
| `apps/api/services/n1_insight_generator.py` | Generates finding text for correlation insights | `_build_insight_text()` (line 530) produces template algorithm-speak: "YOUR {output} is {qual} associated with changes{timing} when your {input} is higher." No novelty filter, no actionability, no specificity. | Redesign text generation for coaching voice with thresholds, magnitudes, confirmation counts. Add novelty suppression. Add actionability implications. |
| `apps/api/routers/activities.py` | Serves activity findings endpoint | `get_activity_findings()` (line 884) returns global top-3 by `times_confirmed`. No relevance filtering. Same three findings on every activity. | Filter findings to those relevant to THIS activity's pre-state, effort type, and signals. Show 0 findings when none are relevant. |
| `apps/api/services/effort_classification.py` | Four-tier effort classification (TPP, HR percentile, HRR, workout_type fallback) | Works correctly as a component. The problem is that `RunAnalysisEngine` calls it as the primary classifier instead of using stored `workout_type`. | May need minor interface changes but core logic is sound. |

### Backend files you will read but likely not modify

| File | What it provides | Why you need it |
|------|-----------------|----------------|
| `apps/api/services/workout_classifier.py` | Title-based classification at sync time. Reads keywords, handles negation, writes `Activity.workout_type`. | This is the classification you're wiring INTO `RunAnalysisEngine`. Understand its output values. |
| `apps/api/services/run_stream_analysis.py` | Computes drift, decoupling, zones, moments, segments. Pure computation, no DB. | This provides the cardiac decoupling metric you'll use instead of speed/HR for easy runs. Also provides per-chart data for Phase 2 insights. |
| `apps/api/services/correlation_persistence.py` | Stores `CorrelationFinding` rows with `insight_text`. | Understand finding schema to filter relevantly in Phase 2. |
| `apps/api/services/operating_manual.py` | Assembles Manual page. Deterministic, no LLM. `_rewrite_headline`. | Phase 3 affects how findings display here. |
| `apps/api/services/daily_intelligence.py` | Daily intelligence engine with rule-based messages. | May need Phase 3 language improvements. |
| `apps/api/services/moment_narrator.py` | LLM-narrated (Gemini 2.5 Flash) per-moment coaching text. | Understand the existing LLM narration pattern. |
| `apps/api/services/efficiency_calculation.py` | `calculate_activity_efficiency_with_decoupling` | Imported by `run_analysis_engine.py`. Understand what decoupling data is already computed. |
| `apps/api/services/efficiency_trending.py` | `analyze_efficiency_trend` with `TrendDirection`, `TrendConfidence` | Already provides trending infrastructure. May be useful for longitudinal comparison. |

### Frontend files (the Composer's domain, not yours — but know them)

| File | Relevance |
|------|-----------|
| `apps/web/app/activities/[id]/page.tsx` | The activity detail page. Composer is restructuring into tabs. |
| `apps/web/components/activities/WhyThisRun.tsx` | Consumes your `/v1/activities/{id}/attribution` endpoint. Will be replaced with per-chart cards. |
| `apps/web/components/activities/RunContextAnalysis.tsx` | Consumes your `/v1/run-analysis/{id}` endpoint. Will be replaced. |
| `apps/web/lib/hooks/queries/manual.ts` | TanStack Query hooks for data fetching. |
| `apps/web/lib/context/StreamHoverContext.tsx` | Hover linkage between chart and map. |

### Spec and reference documents

| Document | What it contains |
|----------|-----------------|
| `docs/specs/INTELLIGENCE_VOICE_SPEC.md` | **Your primary spec.** The full diagnosis, seven principles, architecture, surface-by-surface changes. |
| `docs/BUILDER_INSTRUCTIONS_2026-04-12_ACTIVITY_PAGE_TABBED_LAYOUT.md` | The Composer's layout spec. Defines WHERE intelligence goes. |
| `docs/SESSION_HANDOFF_2026-04-12_COMPOSER_TABBED_LAYOUT.md` | Composer's task handoff. Know what they're building. |
| `docs/SESSION_HANDOFF_2026-04-12_ADVISOR_HANDOFF.md` | The advisor session that diagnosed these problems. |
| `.cursor/rules/athlete-trust-efficiency-contract.mdc` | Binding cursor rule: efficiency is polarity-ambiguous, `OutputMetricMeta` is the sole authority. |
| `docs/specs/EFFORT_CLASSIFICATION_SPEC.md` | The effort classification design spec (4 tiers). |
| `docs/specs/CORRELATION_ENGINE_ROADMAP.md` | 12-layer roadmap for the correlation engine. Layers 1-4 built. |
| `docs/FINGERPRINT_VISIBILITY_ROADMAP.md` | How backend intelligence connects to product surfaces. |
| `docs/wiki/correlation-engine.md` | Finding lifecycle, limiter taxonomy, cross-training inputs. |
| `docs/wiki/coach-architecture.md` | Kimi K2.5 routing, context builders, tools. |

### Key model and endpoint references

| Endpoint | Router location | What it returns |
|----------|----------------|-----------------|
| `GET /v1/activities/{id}/attribution` | `routers/activities.py` line 828 | Feature-flagged. Calls `get_run_attribution()`. Returns `RunAttributionResult` with attributions list. |
| `GET /v1/activities/{id}/findings` | `routers/activities.py` line 884 | Returns up to 3 `FindingAnnotation` objects. Currently global top-3, needs activity-specific filtering. |
| `GET /v1/run-analysis/{id}` | `routers/run_analysis.py` | Calls `RunAnalysisEngine.analyze()`. Returns `RunContextAnalysis`. |

| Model | File | Key fields |
|-------|------|------------|
| `Activity` | `models.py` | `workout_type`, `avg_hr`, `distance_m`, `duration_s`, `name` (title), `pre_recovery_hrv`, `pre_sleep_h`, `athlete_title` |
| `CorrelationFinding` | `models.py` | `input_name`, `output_metric`, `direction`, `r_value`, `lag_days`, `times_confirmed`, `is_active`, `insight_text`, `lifecycle_state` |
| `OutputMetricMeta` | `n1_insight_generator.py` | `polarity_ambiguous`, `higher_is_better`, `friendly_name` — single registry authority for metric interpretation |

---

*"The chart makes you open the app. The intelligence makes you trust it. The voice makes you need it." — Product Manifesto*

*This spec exists because the voice is currently absent or wrong. Every system below it works. This is the layer that makes them speak.*
