# Coach Improvement Plan

**Status:** Phases 1-7 shipped.  
**Created:** 2026-04-24  
**Updated:** 2026-04-25 — Phase 7 shipped after race-morning founder conversation exposed failures that survived Phases 1-6.  
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

Apr 24 slice shipped: `/v1/coach/chat`, `/v1/coach/chat/stream`, and `/v1/coach/history`
now expose lightweight trust metadata (`tools_used`, `tool_count`, `conversation_contract`).
`/coach` renders checked-tool chips under assistant messages and adds a "That's wrong"
button that pre-fills an athlete-authored correction prompt.

### Potential Work

- Structured searched-source chips.
- Stable activity/source IDs for source-linked evidence chips.
- Better display of searched criteria beyond tool names.
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

## Phase 7: Voice, Knowledge, and Guardrail Overhaul

**Added:** 2026-04-25
**Shipped:** 2026-04-25

### Why This Phase Exists

Phases 1-6 fixed the plumbing. The coach can now search activities, receive athlete state, handle corrections, classify conversation intent, assemble race packets, and run eval cases.

On 2026-04-25, the founder had a race-morning conversation with the coach about bicarb supplementation and 5K race strategy. The coach had every mechanical advantage — activity history, stream data, training load, race predictions — and still produced answers worse than an outside LLM that had zero athlete data and only conversation context.

The outside LLM:
- Answered bicarb timing in the first response (60-90 min window, dose at venue arrival, bathroom logistics, half-dose GI risk reduction)
- Read the training block as a narrative ("400s → 800s → busted 1200 → 4x mile → shakeout stride at 5:20 = the speed is there, the fast-twitch is awake")
- Gave mile-by-mile execution guidance with effort scales (7-8/10, 8-9/10, "this is where bicarb shows up or you find out")
- Said "That's not a tune-up pace, that's a war" — direct, human, trust-building

The StrideIQ coach:
- Punted on bicarb entirely ("I don't have your nutrition log entries," "I can't verify your past use from the tools")
- Failed to find the 16x400 workout until the founder pointed to the exact date
- Hedged every statement ("still aggressive," "I still don't have," "The question is execution, not fitness")
- Stated threshold pace as 6:31/mi and built risk analysis on that number, even though the athlete's recent 400s at 5:41-5:50 suggest the zones are stale
- Never gave a warmup prescription, a dosing timeline, or a mile-by-mile execution plan
- Required three "That's wrong" corrections to reach conclusions the outside LLM reached in two messages

The root failures are both mechanical and behavioral. The coach did not merely
choose the wrong tone; it failed to retrieve and rank the decisive evidence
before forming a judgment.

1. **The retrieval layer missed or buried decisive workouts.**
   The 2026-03-28 16x400 workout was in the database, in `get_recent_runs(30d)`,
   findable by a normalized activity search, and verifiable through splits/streams.
   The race packet still omitted it because the curated workout list capped out
   on newer broad distance matches.
2. **The coach refuses to use knowledge it already has.**
3. **The coach hedges instead of coaching.**
4. **The guardrails make it less useful than an unconstrained LLM.**

### Guiding Principle Additions

Add to the existing Guiding Principles:

7. Knowledge before data dependency.
   When the coach has athlete-specific data, use it. When it does not, use general sports science knowledge and label it as general guidance. Never punt an answerable question because the database is empty. "I don't have your bicarb history, but the standard protocol is 60-90 minutes pre-race" is infinitely better than "I can't verify your past use from the tools."

8. Direct voice, not hedge voice.
   The coach leads with its position. If it has a recommendation, it states the recommendation first, then the reasoning. Hedge words ("still," "may," "could potentially," "it's possible that") are treated with the same discipline as banned words. The coach can express uncertainty — "I'm not confident in this zone number given your recent 400s" — but it does not wrap every sentence in qualifiers. Compare: "The 5:55 attempt is still aggressive" vs "5:55 is between your interval and repetition pace — you have the speed, the question is whether you can hold it without the rest intervals." Both are honest. One coaches, the other hedges.

9. Race day is not race planning.
   When the athlete has a race today, the coach is in execution mode. The output is a timeline, a warmup prescription, a dosing window, mile-by-mile effort targets, and a mental cue. It is not a risk assessment, not a prediction debate, and not a hedge about whether the goal is realistic. The athlete decided. The coach helps execute.

### 7A: Knowledge Suppression Fix

#### Problem

The coach treats any gap in athlete-specific data as a reason to refuse the question. An LLM with no guardrails knows sodium bicarb timing, warmup protocols, carb-loading windows, caffeine half-life, and race-day nutrition. The StrideIQ coach knows all of this too — the base model has the knowledge — but the system prompt or guardrails suppress it because "the tools don't have data."

#### Required Change

The system prompt and guardrail layer must distinguish between two failure modes:

- **Hallucinating athlete-specific facts** (bad — suppress this): "Your bicarb response has been positive in the past" when no data exists.
- **Refusing general sports science** (also bad — stop doing this): "I can't verify your past use from the tools" when the athlete asked about dosing timing, not their personal history.

The contract: when the coach lacks athlete-specific data on a topic, it provides its best general sports science answer, clearly labeled, and asks a follow-up to personalize. Never say "I don't have data on that" as a terminal answer.

#### Likely Files

- `apps/api/services/coaching/_context.py` (system prompt)
- `apps/api/services/coaching/_llm.py` (Kimi system message construction)
- `apps/api/services/coaching/_guardrails.py` (post-response validation)
- `apps/api/tests/test_coach_output_contract_chat.py`

#### Acceptance Criteria

- "Should I take bicarb before my race?" produces timing guidance, dosing protocol, and GI risk context — not "I don't have your nutrition data."
- "How should I warm up for a 5K?" produces a specific warmup protocol — not "I don't have your warmup history."
- General guidance is labeled: "Based on standard sports science..." or "Generally for a hard 5K..." — not presented as athlete-specific fact.

### 7B: Voice and Confidence Directive

#### Problem

The coach hedges reflexively. Every recommendation is wrapped in qualifiers that erode trust. The Product Standard says "not a safety nanny" but the output reads like one.

#### Required Change

Add a voice directive to the system prompt with the same enforcement weight as the banned-word list. Specifically:

- Lead with the recommendation or position. Reasoning follows.
- Do not use hedge phrases as filler: "still aggressive," "it's worth noting," "that said," "it's possible that," "I would suggest considering." State the thing.
- Uncertainty is allowed when genuine. "I'm not confident your threshold is still 6:31 — your recent 400s suggest it's faster" is direct uncertainty. "The 5:55 attempt is still aggressive" is hedge.
- Match the athlete's energy. If the athlete is excited and decisive, the coach matches that intensity. If the athlete is anxious, the coach is steady. The coach does not default to caution regardless of context.

Add a post-response guardrail check: if more than N hedge phrases appear in the response, flag it the same way banned words are flagged.

#### Likely Files

- `apps/api/services/coaching/_context.py` (system prompt voice directive)
- `apps/api/services/coaching/_guardrails.py` (hedge detection)
- `apps/api/services/coaching/_constants.py` (hedge phrase list)
- `apps/api/tests/test_coach_output_contract_chat.py`

#### Acceptance Criteria

- Response to "I'm going out at 5:50 pace" does not contain "still aggressive" or equivalent hedges. It reads like a direct coach.
- The coach's first sentence in a race-strategy response is a position, not a qualifier.
- A hedge-detection guardrail exists and fires on responses that over-qualify.

### 7C: Race-Day Execution Mode

#### Problem

Phase 4 built race strategy assembly. But "I have a race in 3 hours" and "I'm thinking about racing a 5K next month" are fundamentally different conversations. The coach treated this morning's race-day conversation like a planning conversation — risk assessments, prediction debates, threshold analysis — when the athlete needed a timeline and execution cues.

#### Required Change

Split the `race_strategy` conversation contract into two modes:

- **`race_planning`**: days or weeks before. Training block assessment, pace target discussion, taper evaluation, course research. The current Phase 4 output is appropriate here.
- **`race_day`**: same day. The output is:
  - **Timeline**: leave time → arrival → packet → warmup → race, with dosing/fueling slotted in.
  - **Warmup prescription**: specific drills, strides, duration. "4-6 strides at 5K effort, 60-80m, full walk-back recovery. Do not skip this."
  - **Mile-by-mile execution**: effort scale per segment, not just pace. "Mile 1: 7-8/10, controlled. Mile 2: 8-9/10, questioning your choices. Mile 3: everything."
  - **Mental cues**: "If mile 1 feels like a 9, pull back to 6:00. If it feels like a 7, you're exactly where you need to be."
  - **Supplement/fueling timing** if discussed: exact timing relative to race start, not generic windows.

Detection: if the athlete mentions a race today, this morning, or within the next 12 hours, classify as `race_day` not `race_planning`.

#### Likely Files

- `apps/api/services/coaching/_conversation_contract.py`
- `apps/api/services/coaching/_context.py`
- `apps/api/services/coaching/_tools.py`
- `apps/api/tests/test_coach_conversation_contract.py`
- `apps/api/tests/test_coach_race_strategy.py`

#### Acceptance Criteria

- "I have a 5K this morning" triggers `race_day`, not `race_strategy` or `race_planning`.
- Race-day response includes a warmup prescription, not just pace analysis.
- Race-day response includes mile-by-mile effort guidance, not just a target pace.
- If the athlete discusses a supplement, the response includes timing relative to their logistics.

### 7D: Training Block Narrative Synthesis

#### Problem

The coach looks at individual workouts in isolation. The outside LLM synthesized the training block into a narrative arc: "400s with short rest → 800s → busted 1200 → came back and did 4x mile → shakeout stride at 5:20" and concluded "the speed is there, the lactate system has been stressed, the fast-twitch is awake." The StrideIQ coach never attempted this synthesis despite having the actual data.

#### Required Change

Add a tool or context builder that assembles a training block summary for the last N weeks. Not individual workout descriptions — a narrative assessment:

- What energy systems were trained and in what sequence.
- What the progression tells you about current fitness.
- What's missing (e.g., no sustained race-pace work, no floats, walking recoveries only).
- How recent the sharpest work is.

This could be a new tool (`get_training_block_narrative`) that returns structured data the model synthesizes, or it could be assembled as part of the race strategy packet. Either way, the coach should never discuss race readiness without first reading the recent training arc.

#### Likely Files

- `apps/api/services/coach_tools/activity.py` or new `training_block.py`
- `apps/api/services/coaching/_tools.py`
- `apps/api/tests/test_coach_tools_training_block.py`

#### Acceptance Criteria

- When asked about race readiness, the coach references the training arc, not just individual workouts.
- The coach identifies what training was done AND what was missing (e.g., "no sustained race-pace work, only reps with rest").
- The coach can read a progression (speed → speed endurance → taper) and name where the athlete is in the arc.

### 7E: Guardrail Audit

#### Problem

The guardrails are making the coach less useful than an unconstrained LLM. This is the opposite of their purpose. Specific symptoms:

- The coach refuses to give general sports science guidance when athlete data is missing.
- The coach hedges every recommendation.
- The coach treats every race goal as a risk to be managed rather than a decision to be supported.
- "I can't verify" appears as a terminal statement rather than a transition to general knowledge.

#### Required Change

Audit every guardrail rule, system prompt instruction, and post-response validation for:

1. **Rules that suppress general knowledge.** Remove or relax them. The coach should be allowed to say what any competent coach would say about bicarb, warmup protocols, carb timing, caffeine, race execution, etc.
2. **Rules that produce hedging.** Either remove them or replace them with direct-voice alternatives. "Be careful about overpromising" becomes "State your honest assessment of what is achievable and why."
3. **Rules that override athlete agency.** If the athlete says "I'm going out at 5:50," the coach helps execute that plan. It does not lecture about whether 5:50 is wise. Risk context is one sentence, not the entire response.
4. **The forced tool mandate.** Kimi currently forces `get_weekly_volume` and `get_recent_runs` before every answer. This is wasteful for nutrition questions, bicarb questions, warmup questions, and emotional support questions. Replace with intent-specific required tools from the conversation contract.

#### Likely Files

- `apps/api/services/coaching/_context.py` (system prompt)
- `apps/api/services/coaching/_guardrails.py`
- `apps/api/services/coaching/_tools.py` (forced tool list)
- `apps/api/services/coaching/_constants.py`
- `apps/api/services/coaching/_llm.py`

#### Acceptance Criteria

- An unconstrained LLM given the same question ("Should I take bicarb before my 5K?") does not produce a materially better answer than the StrideIQ coach. If it does, the guardrails are still too restrictive.
- The forced tool mandate is replaced with intent-specific tool selection.
- No guardrail rule produces "I can't verify" as a terminal response.

### 7F: Zone Accuracy Questioning

#### Problem

The coach stated threshold is 6:31/mi and built its entire risk analysis on that number. But the athlete's recent 400s at 5:41-5:50 and mile repeats near 6:00 suggest the RPI-derived zones may be stale. The coach never questioned its own zones. The outside LLM — with no zone data at all — looked at what the athlete actually ran and drew better conclusions.

#### Required Change

When the coach uses pace zones for analysis, it should cross-reference recent workout evidence. If recent interval or race paces are materially faster than the zone model predicts, the coach should flag the discrepancy and reason from the evidence, not the model.

This is not a pace-zone recalibration task. It is a coaching judgment task: "Your threshold model says 6:31, but you ran 400s at 5:45 four weeks ago. I'm going to reason from what you actually ran."

#### Likely Files

- `apps/api/services/coaching/_context.py` (system prompt instruction)
- `apps/api/services/coach_tools/performance.py`

#### Acceptance Criteria

- When recent workout paces materially exceed zone predictions, the coach acknowledges the discrepancy.
- The coach does not build risk assessments solely on zone numbers when recent evidence contradicts them.

### 7G: Search Brittleness Fix

#### Problem

The activity search tool can find the March 28 workout when queried as
`16 x 400`, but not when queried as `16x400` or `400s`. That is not acceptable
for coach conversation. Athletes do not type database titles; they type natural
workout language.

The search result also proved a deeper issue: the workout is named "Morning Run"
but contains 16 device/work-like 400m reps in the splits. Title search alone
will always be brittle for Garmin/Strava activities with generic names.

#### Required Change

Normalize workout search terms before building the activity query:

- Treat `16x400`, `16 x 400`, `16X400m`, `16 by 400`, `400s`, and `400 repeats`
  as equivalent search intent.
- Normalize casing, spacing, plural suffixes, and optional `m`.
- Search activity `name`, `athlete_title`, `shape_sentence`, and `workout_type`.
- When the query implies a structured workout (`400`, `800`, `1200`, mile reps,
  intervals, repeats), fall through to split-aware search instead of returning
  "no match" from title text alone.

This belongs in the shared activity search layer so the activities API and coach
tool do not diverge.

#### Likely Files

- `apps/api/services/activity_search.py`
- `apps/api/services/coach_tools/activity.py`
- `apps/api/tests/test_coach_tools_activity_lookup.py`
- `apps/api/tests/test_coach_phase7_retrieval.py`

#### Acceptance Criteria

- Searching for `16x400`, `16 x 400`, `16X400m`, and `400s` all returns the
  March 28 `Morning Run` fixture when its splits contain 16 work reps around
  400m.
- A generic activity title does not prevent retrieval when split structure
  proves the workout.
- Empty search results must include searched criteria and whether split-aware
  fallback ran.

### 7H: Race Packet Workout Cap Fix

#### Problem

`get_race_strategy_packet` currently returns only six recent race-relevant
workouts. In production, that list was filled by Apr 16-23 activities and omitted
the March 28 16x400 workout, even though the 400s were decisive evidence for a
5K race-day pace conversation.

The ranking logic also treats broad distance matches as relevant. Recent easy
or medium-long runs can crowd out older but much more race-specific interval
sessions.

#### Required Change

Change `_recent_relevant_workouts` from "latest rows that loosely match" to
"ranked race-specific evidence":

- Raise the returned cap from 6 to at least 15.
- Rank quality sessions above easy distance matches.
- Weight split-confirmed workouts above title/name matches.
- Preserve recency as a secondary ranking factor, not the primary factor.
- Include enough evidence metadata for the model to know why the workout was
  included: `selection_reason`, `quality_rank`, `split_summary`, and
  `race_specificity`.

#### Likely Files

- `apps/api/services/coach_tools/race_strategy.py`
- `apps/api/tests/test_coach_race_strategy.py`
- `apps/api/tests/test_coach_phase7_retrieval.py`

#### Acceptance Criteria

- A fixture with 8 newer easy runs plus one 4-week-old 16x400 workout still
  includes the 16x400 in `recent_race_relevant_workouts`.
- Race packet evidence lists the 16x400 ahead of easy runs for a 5K target.
- Easy runs can still appear when useful, but cannot crowd out quality sessions.

### 7I: Thread-Aware Conversation Classification

#### Problem

The production conversation classified every key message as `general`:

- "I'm considering taking Maurten bicarb this morning..."
- "I did 16 x 400 faster than that"
- "That was on March 28th"
- "I'm going out at 5:50 pace"

That classification failure means the model never entered race-day execution
mode, correction mode, or retrieval-repair mode. The latest message alone is
not enough; a thread can carry race-day context forward across several short
turns.

#### Required Change

`classify_conversation_contract` should accept recent conversation context and
promote ambiguous follow-ups when the thread is clearly about a same-day race.

Rules:

- If recent thread context contains same-day race language, classify supplement,
  warmup, target pace, splits, and workout-evidence follow-ups as `race_day`.
- If the athlete disputes a data claim ("I did 16 x 400 faster than that"),
  classify as correction/retrieval repair even without the literal phrase
  "that's wrong."
- If the athlete supplies a date after a failed lookup, force verification
  behavior and specific activity search.

#### Likely Files

- `apps/api/services/coaching/_conversation_contract.py`
- `apps/api/services/coaching/core.py`
- `apps/api/services/coaching/_guardrails.py`
- `apps/api/tests/test_coach_conversation_contract.py`

#### Acceptance Criteria

- In a thread that began with "race this morning," "I did 16 x 400 faster than
  that" is not classified as `general`.
- "That was on March 28th" after a failed workout lookup triggers
  correction/retrieval repair.
- Race-day context persists for short follow-up turns without requiring the
  athlete to restate "race" every time.

### 7J: Training Block Structure-Aware Enhancement

#### Problem

The training block needs to be interpreted from workouts, not activity titles.
The March 28 workout was titled "Morning Run" but its splits show 16 x 400m.
A name-based narrative builder would miss the same evidence the coach missed.

#### Required Change

`get_training_block_narrative` must inspect `ActivitySplit` rows:

- Detect repeated work reps by distance/time pattern.
- Classify energy-system emphasis from split structure:
  - 400m/short reps -> speed / VO2 / repetition support
  - 800m-1200m reps -> VO2 / lactate tolerance
  - mile / 10-minute reps -> threshold / speed endurance
  - continuous fast segments -> tempo / progression
- Summarize rest type and rest duration when available.
- Fall back to name/workout-type heuristics only when splits are absent.

#### Likely Files

- `apps/api/services/coach_tools/training_block.py` (preferred new tool)
- `apps/api/services/interval_detector.py`
- `apps/api/services/coaching/_tools.py`
- `apps/api/tests/test_coach_tools_training_block.py`
- `apps/api/tests/test_coach_phase7_retrieval.py`

#### Acceptance Criteria

- A "Morning Run" fixture with 16 x 400m split structure is classified as speed
  / VO2 support, not generic aerobic running.
- The training block narrative can state the arc: 400s -> 800s -> 1200/mile
  work -> race-day sharpness.
- The output names both what is present and what is missing, such as "speed is
  present; continuous 5K-specific work is the limiter."

### 7K: DB-Backed Retrieval Eval Scenarios

#### Problem

The Phase 5 value harness checks behavioral prose and required tools, but it
does not prove the real retrieval pipeline surfaces the right evidence. A
synthetic "good answer" can pass while production still misses the workout.

#### Required Change

Add DB-backed retrieval evals that seed actual `Activity` and `ActivitySplit`
rows and run the real tools:

- Interval workout with generic name (`Morning Run`) and 16 x 400m splits.
- Several newer easy/medium-long activities that would previously crowd out the
  interval workout.
- Same-day race conversation context and follow-up correction turns.

The eval should assert retrieval outcomes before response prose. If the tool
layer cannot surface the right workout, no LLM output should be considered
passing.

#### Likely Files

- `apps/api/tests/test_coach_phase7_retrieval.py`
- `apps/api/tests/fixtures/coach_value_cases.json`
- `apps/api/tests/test_coach_value_contract.py`
- `apps/api/services/coaching/_value_eval.py`

#### Acceptance Criteria

- The retrieval eval fails red against current production behavior.
- The eval proves `search_activities`, `get_race_strategy_packet`, and
  `get_training_block_narrative` all surface the 16x400 fixture.
- The eval includes a negative case where title-only search would fail but
  split-aware retrieval succeeds.
- The coach value harness adds race-morning cases for bicarb timing, 5:50 pace,
  thread-aware 16x400 correction, and zone-vs-workout evidence conflict.

### Phase 7 Regression Case (Add to Phase 5 Seed Cases)

- Athlete asks about bicarb timing on race morning. Coach gives dosing protocol, not "I can't verify."
- Athlete says "I'm going out at 5:50 pace" for a 5K in 3 hours. Coach gives mile-by-mile execution plan, warmup prescription, and mental cues — not a risk assessment.
- Athlete has done 16x400 at 5:45, 8x800, 4x mile in the last 4 weeks. Coach reads the training arc and names what was built and what is missing, not just individual workout stats.
- Coach's first sentence in a race-strategy response is a position or recommendation, not a hedge.
- Coach's threshold/zone model disagrees with recent workout evidence. Coach reasons from the evidence.
- Retrieval pipeline surfaces a generic-name interval workout from splits, not
  just activity title text.

