# Coach Improvement Plan

**Status:** Planning  
**Created:** 2026-04-24  
**Owner:** StrideIQ founder + implementation agents  
**Read first for this work:** `docs/FOUNDER_OPERATING_CONTRACT.md`, then this document

## Product Standard

The coach is not successful because it answers a prompt. The coach is successful when the athlete is better for having had the conversation.

"Better" means the athlete leaves clearer, sharper, steadier, more capable, or more accurately calibrated than when they entered.

The coach should feel like the voice of the athlete's own body, training history, instincts, goals, and constraints translated into coaching judgment. It is not a generic runner chatbot, not Garmin plus prose, and not a safety nanny. It should be a high-trust N=1 coach and research analyst that knows the athlete's actual history, respects athlete agency, and earns trust by being specific, grounded, and useful.

## Why This Exists

A recent coach conversation exposed failures that cannot be fixed by prompt edits alone:

- The coach failed to find an older activity that existed in history.
- It claimed or implied limited access instead of searching correctly.
- It ignored or underused athlete corrections.
- It misread nutrition totals.
- It made temporal mistakes.
- It over-relied on generic caution and weak model outputs.
- It did not understand race psychology or current training context deeply enough.
- It produced answers that were sometimes less helpful than what the athlete already knew.

The goal of this plan is to rebuild the coach around trust, conversation outcomes, and N=1 value.

## Research Findings From Code

The current coach path is centered on `AICoach` in `apps/api/services/coaching/core.py`.

Key implementation facts:

- HTTP entrypoints live in `apps/api/routers/ai_coach.py`.
- The production chat path is intended to be Kimi-first: `AICoach.chat()` -> `_query_kimi_with_fallback()` -> `query_kimi_coach()` in `apps/api/services/coaching/_llm.py`, with Sonnet fallback.
- `apps/api/services/coaching/core.py` still has a stale `self.gemini_client` hard gate before Kimi runs. Gemini is not the primary chat model, but `query_gemini()` is still a live guardrail-retry fallback in `apps/api/services/coaching/_guardrails.py` when the turn guard retries and Anthropic is unavailable. Do not simply delete Gemini; re-scope the chat availability gate and guardrail branch.
- `athlete_state` and `finding_id` context are built in `core.py`, but `query_kimi_coach()` does not currently inject `athlete_state` into the Kimi request payload. Verified with the builder agents: this is a bug, not an intentional omission. The same parameter is also ignored by `query_opus()` today.
- `get_recent_runs()` in `apps/api/services/coach_tools/activity.py` accepts up to 730 days but caps query results at `.limit(50)`, which can hide older relevant races inside the claimed window.
- There is no existing free-text/arbitrary-filter coach activity search helper. The richest filter logic lives inline in `apps/api/routers/activities.py::list_activities`; a coach search tool should factor that query logic into a reusable service rather than duplicating it.
- `get_nutrition_log()` in `apps/api/services/coach_tools/wellness.py` returns entries and averages, but lacks a strong "today through now" / visible coverage / evidence contract.
- Multiple `NutritionEntry` rows for the same date are additive partial logs. There is no uniqueness constraint on `(athlete_id, date, entry_type)`. `services/nutrition_targets.py::get_daily_actuals()` sums all rows for the day.
- Conversation persistence uses `CoachChat` in `apps/api/services/coaching/_thread.py`.
- Durable facts come from `AthleteFact` via async extraction in `apps/api/tasks/fact_extraction_task.py`. Builder guidance for v1: do not add synchronous `AthleteFact` writes during chat. Keep immediate correction handling in conversation context; let the existing async extraction contract persist facts after the turn.
- Race history has multiple source pieces but no single race-strategy service. Relevant sources include `services/race_signal_contract.py`, `services/performance_event_pipeline.py`, `services/race_predictor.py`, `services/routes/route_fingerprint.py`, `services/athlete_diagnostic.py::get_race_history`, `services/coach_tools/performance.py`, and `AthleteRaceResultAnchor`.
- The frontend coach page already supports collapsed markdown evidence via `## Evidence` in `apps/web/app/coach/page.tsx`; structured evidence UI is not required for the first backend slice.

## Guiding Principles

1. Trust before cleverness.
   The coach must stop making false claims, misreading data, and repeating corrected mistakes before more sophisticated behavior matters.

2. Athlete state improvement is the outcome.
   Each meaningful answer should target a useful outcome: clarity, decision quality, confidence calibration, execution, self-knowledge, emotional steadiness, or strategic sharpness.

3. Athlete agency is non-negotiable.
   The coach informs and frames tradeoffs. The athlete decides. Productive fatigue is not a bug.

4. Suppression over hallucination.
   If the coach cannot verify a claim, it should search better, say exactly what it searched, label the claim as athlete-stated, or suppress the claim.

5. N=1 beats population defaults.
   The coach should reason from this athlete's history, corrections, race behavior, sleep baseline, injury context, nutrition data, and training intent.

6. Evidence must be useful, not performative.
   Receipts should show what was searched and what data supported the answer. They should not be vague decoration.

## Phase 1: Trust Foundation

### Objective

Stop trust-breaking failures in retrieval, grounding, context delivery, corrections, and nutrition.

### Required Work

Add a full activity search tool rather than stretching `get_recent_runs()` beyond its job.

Implementation direction:

- Factor the activity filtering/query-building logic currently inline in `apps/api/routers/activities.py::list_activities` into a reusable service helper.
- Use that helper from both the existing activity list endpoint and the new coach-facing search tool when feasible.
- Keep `get_recent_runs()` as a recent run summary tool.
- Use DB-backed tests with `db_session` + `test_athlete`, following the real-row pattern in `apps/api/tests/test_coach_quality_fixes_hardened.py`, not the MagicMock-heavy pattern in `test_coach_tools_phase3.py`.

Likely new tool: `search_activities`

Inputs:

- `start_date`
- `end_date`
- `name_contains`
- `sport`
- `workout_type`
- `race_only`
- `distance_min_m`
- `distance_max_m`
- `limit`

Expected behavior:

- Searches by date/name/race/distance across the real activity table.
- Returns explicit search criteria and count.
- Returns evidence rows for matched activities.
- Makes "I searched and found no match" possible.
- Prevents "I cannot see it" when the coach simply used the wrong recent-run tool.

Fix Kimi runtime context:

- Replace the stale Gemini-only availability gate in `AICoach.chat()`.
- Gate on the actual configured runtime options: Kimi primary, Sonnet fallback, and Gemini only for the remaining guardrail-retry fallback.
- Keep `query_gemini()` unless the guardrail retry path is explicitly redesigned.
- Inject `athlete_state` into Kimi and Sonnet requests in a controlled internal block.
- Ensure `finding_id` context reaches the model when the coach opens from a briefing deep link.

Harden nutrition grounding:

- Return today's totals, date coverage, entry count, visible entries, and evidence.
- Treat same-date nutrition rows as additive partial logs.
- Distinguish "logged so far today" from "complete total daily intake."
- Do not let the coach answer nutrition questions from generic advice when log data is available.

Add correction/dispute handling:

- Detect athlete corrections and disputes.
- Force verification or explicit athlete-stated labeling on the next response.
- Do not allow the coach to repeat the disproven claim.
- Do not write correction facts synchronously to `AthleteFact` in v1; immediate handling should use current message + thread context while async extraction persists durable facts after save.

### Likely Files

- `apps/api/services/coach_tools/activity.py`
- `apps/api/services/activity_search.py` or equivalent factored activity query helper
- `apps/api/services/coach_tools/wellness.py`
- `apps/api/services/coach_tools/__init__.py`
- `apps/api/routers/activities.py`
- `apps/api/services/coaching/_tools.py`
- `apps/api/services/coaching/core.py`
- `apps/api/services/coaching/_llm.py`
- `apps/api/services/coaching/_guardrails.py`
- `apps/api/tests/test_coach_tools_activity_lookup.py`
- `apps/api/tests/test_coach_nutrition_grounding.py`
- `apps/api/tests/test_coach_kimi_canary.py`
- `apps/api/tests/test_coach_output_contract_chat.py`
- `apps/api/tests/test_coach_contract.py`
- `docs/wiki/coach-architecture.md`

### Acceptance Criteria

- An activity older than the latest 50 runs is findable by date/name/race/distance.
- `get_recent_runs()` remains a recent summary tool and no longer carries the burden of full-history lookup.
- Coach chat does not require `GOOGLE_AI_API_KEY` when Kimi/Sonnet are configured.
- Kimi request payload includes the `athlete_state` built in `core.py`.
- Nutrition output cannot turn approximately 2200 logged calories into approximately 1190.
- Correction turns trigger verification or athlete-stated labeling.
- The coach cannot say "I don't see it" without indicating what it searched.

### Real Blockers

- Existing tests are heavily mocked. Activity lookup needs DB-backed fixtures or it will not prove the production failure.
- Adding a new tool changes tool-count and tool-schema contract tests.
- Kimi currently forces `get_weekly_volume` and `get_recent_runs` before every answer. That blunt mandate may harm nutrition, correction, and race-strategy turns. Intent-specific required tools may need to replace it.
- The Gemini gate cannot be removed as a simple deletion because Gemini still has one live guardrail-retry caller.
- Nutrition entries are partial/additive by design. A snack is not a day total. The tool must represent coverage honestly.
- Refactoring `list_activities` query logic must preserve the existing `/v1/activities` filter behavior and tests.

## Phase 2: Conversation Outcome Contract

### Objective

Make the coach understand what kind of conversation moment it is in and what success means for that moment.

### New Concept

Add a lightweight deterministic contract layer that classifies the latest athlete message and gives the model an internal response objective.

Potential new file:

- `apps/api/services/coaching/_conversation_contract.py`

### Contract Types

- `quick_check`: concise executable guidance.
- `decision_point`: tradeoff clarity and a recommendation frame.
- `race_strategy`: specific execution plan.
- `post_run_interpretation`: what the workout means for training.
- `emotional_load`: steadier athlete state without therapy or prying.
- `correction_dispute`: trust repair through verification.
- `identity_context_update`: persist or use durable athlete context.
- `deep_analysis`: non-obvious synthesis across history.

### Required Outcome Targets

- Quick check -> answer briefly and directly.
- Decision point -> name the decision, tradeoff, and default recommendation.
- Race strategy -> produce an executable race plan, not a generic prediction.
- Emotional load -> reduce chaos, respect boundaries, and give a next step.
- Correction/dispute -> verify, correct, and avoid defensiveness.
- Deep analysis -> surface something the athlete probably did not already know.

### Likely Files

- `apps/api/services/coaching/_conversation_contract.py`
- `apps/api/services/coaching/core.py`
- `apps/api/services/coaching/_guardrails.py`
- `apps/api/services/coaching/_context.py`
- `apps/api/tests/test_coach_conversation_contract.py`
- `docs/COACH_OUTPUT_CONTRACT_V1.md`
- `docs/wiki/coach-architecture.md`

### Acceptance Criteria

- "Keep it brief" cannot produce an essay.
- "Should I postpone threshold?" produces decision criteria and a recommendation frame.
- "You are wrong, that race exists" triggers verification behavior.
- "I am stressed and want food" gives grounded meal guidance without prying into life events.
- Race-strategy prompts produce execution strategy, not generic encouragement.

### Real Blockers

- Deterministic intent classification can be wrong. It must be small, transparent, and easy to override.
- Prompt-only enforcement is insufficient. The contract needs pre-response routing and post-response validation.
- "Better for having had it" is partly subjective. Automated tests can catch failures and enforce shape; founder review remains part of the quality gate.

## Phase 3: N=1 Coaching Memory

### Objective

Remember coaching truths, not only extracted facts.

### Memory Types

- `race_psychology`
- `injury_context`
- `invalid_race_anchor`
- `training_intent`
- `fatigue_strategy`
- `sleep_baseline`
- `stress_boundary`
- `coaching_preference`
- `strength_training_context`

### Required Behavior

The coach should remember and use facts such as:

- The athlete deliberately builds fatigue during specific blocks.
- Heavy legs Monday affects Tuesday but may be an intentional durability stimulus.
- The athlete races aggressively and may close far faster than workouts suggest.
- The current 5K limiter may be lactate tolerance/execution, not general fitness.
- Chronic 6 to 6.5 hour sleep is baseline and should not be treated as acute collapse unless athlete-specific data supports it.
- Running is an escape from life stress; do not pry when the athlete sets that boundary.
- Some race results are invalid anchors because injury compromised them.

### Likely Files

- `apps/api/tasks/fact_extraction_task.py`
- `apps/api/services/coaching/_context.py`
- `apps/api/services/coaching/_tools.py`
- `apps/api/tests/test_fact_extraction.py`
- `apps/api/tests/test_coach_memory_context.py`
- `apps/api/models/athlete.py` only if `AthleteFact` is insufficient

### Acceptance Criteria

- "I had a fractured femur during that 10K" changes future interpretation of that race.
- "Running is my escape; do not discuss the life stress" is respected.
- "I deliberately build fatigue until the 19th" prevents generic recovery warnings.
- "I race controlled chaos" informs future race plans.

### Real Blockers

- Async fact extraction happens after chat save, so it may not help the immediate next turn.
- Some high-signal corrections may need immediate conversation-context handling, but v1 should not add synchronous `AthleteFact` writes.
- `AthleteFact` may be enough for v1, but invalid race anchors may eventually need structured links to `Activity` or `PersonalBest`.
- TTL is tricky. Injury can be historical but permanently relevant for interpreting a race.

## Phase 4: Race Strategist Mode

### Objective

Make race planning a flagship coach behavior.

### Required Race Packet

Race strategy should assemble a packet before the model answers:

- Target race name, date, and distance.
- Prior same-course activity if present.
- Recent race-relevant workouts.
- Current plan week.
- Race history, race-result anchors, and invalid anchors.
- Injury context.
- Training load/fatigue.
- Athlete-stated race psychology.
- Optional weather/course data when available.

### Required Output

The answer should identify:

- Realistic objective.
- Primary limiter.
- False limiter to ignore.
- Pacing or effort shape.
- Course-specific risk.
- Execution cues.
- Success definition beyond time.
- Post-race learning target.

### Likely Files

- `apps/api/services/coach_tools/activity.py`
- `apps/api/services/coach_tools/performance.py`
- `apps/api/services/coach_tools/plan.py`
- `apps/api/services/race_signal_contract.py`
- `apps/api/services/routes/route_fingerprint.py`
- `apps/api/services/athlete_diagnostic.py`
- `apps/api/services/coaching/_tools.py`
- `apps/api/services/coaching/_conversation_contract.py`
- `apps/api/tests/test_coach_race_strategy.py`
- `docs/wiki/coach-architecture.md`

### Acceptance Criteria

For a Tuscaloosa Mayor's Cup 5K style prompt, the coach should:

- Find prior course/race activity if it exists.
- Use recent race-relevant workouts.
- Respect injury context.
- Identify continuous lactate tolerance/execution as the likely limiter rather than generic fitness.
- Respect the athlete's aggressive goal without pretending pace precision is easy.
- Produce a race script that fits the athlete's psychology.

### Real Blockers

- Course/weather data may not exist beyond activity-level weather/elevation.
- Same-course matching should use GPS route fingerprints when possible (`services/routes/route_fingerprint.py`) rather than only activity title matching.
- PersonalBest history may not include all races if race detection/import is incomplete; include authoritative race signals, `PerformanceEvent`, and `AthleteRaceResultAnchor` where appropriate.
- This mode can get expensive if it calls every tool every time. Retrieval must be intent-specific.

## Phase 5: Coach Value Eval Harness

### Objective

Prove the coach improves athlete state, not just tool usage.

### Eval Dimensions

- Factual grounding.
- Correction incorporation.
- Decision clarity.
- Athlete agency.
- N=1 specificity.
- Emotional appropriateness.
- Non-obvious usefulness.
- Evidence quality.

### Likely Files

- `apps/api/tests/test_coach_value_contract.py`
- `apps/api/tests/fixtures/coach_value_cases.json`
- `apps/api/tests/test_coach_dispute_turn.py`
- `apps/api/tests/test_coach_race_strategy.py`

### Seed Regression Cases

- Older activity exists but is outside latest 50 runs.
- Athlete corrects the coach: "that race exists."
- Athlete says "today is Thursday."
- Nutrition total is approximately 2200, not approximately 1190.
- Athlete says a race was run on a fractured femur.
- Athlete explains a social run or pacing context that invalidates naive efficiency interpretation.
- Athlete is stressed and wants food but does not want to discuss life events.
- Athlete wants aggressive 5K strategy and has a known race psychology.

### Real Blockers

- Exact prose tests will be brittle.
- Behavioral assertions should check required facts, forbidden claims, required tools, outcome shape, and evidence quality.
- Live LLM evals cost money and can be flaky. Deterministic contract tests should run every commit; live coach evals should run pre-deploy or nightly.
- Automated tests can prove bad answers fail. They cannot fully prove excellence. Founder-reviewed eval remains necessary.

## Phase 6: Frontend Trust UX

### Objective

Expose evidence and correction workflows only after backend behavior earns them.

### Current State

`apps/web/app/coach/page.tsx` already splits trailing `## Evidence` / `## Receipts` into a collapsed evidence block.

### Potential Work

- Structured searched-source chips.
- "That is wrong" correction affordance.
- Better display of searched criteria.
- Optional source links to activities.

### Likely Files

- `apps/web/app/coach/page.tsx`
- `apps/web/lib/api/services/ai-coach.ts`
- `apps/web/__tests__/coach-scroll-layout.test.tsx`
- New frontend coach message/evidence tests if structured data is added.

### Real Blockers

- Frontend source chips require structured response or SSE metadata changes.
- Current streaming client only handles `delta`, `error`, and `done`.
- Backend behavior should be fixed first; otherwise UI polish will expose unreliable evidence.

## Recommended First Production Slice

Do not build everything at once.

First slice:

1. Add `search_activities`.
2. Remove stale Gemini gate.
3. Inject `athlete_state` into Kimi.
4. Harden nutrition grounding.
5. Add correction/dispute contract.
6. Add conversation contract skeleton for:
   - `quick_check`
   - `decision_point`
   - `correction_dispute`
   - `race_strategy`
7. Add deterministic tests for all of the above.
8. Update `docs/wiki/coach-architecture.md` when behavior changes.

This slice is small enough to validate and large enough to move the coach from "less wrong" toward "actually useful."

## Definition Of Done

The first build slice is not done until:

- Targeted tests pass with evidence.
- New tests cover the production failure modes.
- The coach can retrieve older activities by search.
- The coach can handle correction turns without repeating false claims.
- Nutrition responses are grounded in visible log coverage.
- Kimi receives the context the system builds.
- The wiki is updated for shipped behavior.
- The remaining blockers are documented before moving to race strategist depth.

