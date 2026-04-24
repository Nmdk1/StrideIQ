# AI Coach Architecture

## Current State

The AI coach is the primary conversational interface. Every athlete query routes through the `AICoach` class in `services/coaching/core.py` (legacy import path `services/ai_coach.py` is a 5-line shim that still re-exports `AICoach`). The production path is **universal Kimi**: `AICoach.chat` calls `_query_kimi_with_fallback()` -> `query_kimi_coach()` in `services/coaching/_llm.py`, which uses **`settings.COACH_CANARY_MODEL`** (default **`kimi-k2.6`** in `apps/api/core/config.py`). **Claude Sonnet 4.6** is the silent fallback (`query_opus`) on Kimi errors or missing `KIMI_API_KEY`. Chat availability now gates on any configured runtime route (Kimi, Sonnet, or Gemini) instead of requiring Gemini. **Gemini is not the primary chat path**, but `query_gemini()` remains a guardrail-retry fallback when a turn mismatch retry needs an LLM and Anthropic is unavailable.

The `AICoach` class is composed of seven mixins living alongside `core.py` in the `coaching/` package: `_context.py`, `_llm.py`, `_thread.py`, `_tools.py`, `_budget.py`, `_guardrails.py`, `_prescriptions.py`. Shared constants and the KB violation scanner live in `_constants.py`.

## How It Works

### Model Routing

Routing lives on the `AICoach` class in `services/coaching/core.py`:

- **`chat()`** — consent gate, budget check, then **`_query_kimi_with_fallback()`** (Kimi → Sonnet on failure)
- **`get_model_for_query()`** — still logs “premium lane” for budgets; **does not** select Gemini for chat (commentary in code references Kimi universal path)
- **Fallback chain:** Kimi (`COACH_CANARY_MODEL`) → Claude Sonnet 4.6 (on Kimi error / empty content / import or key failure)
- **Model audit trail:** Assistant messages in `coach_chat` JSONB record the **`model`** string returned by the LLM path (e.g. `kimi-k2.6`, `claude-sonnet-4-6`, or deterministic shortcuts)

### Budget & Caps

Implemented in the `_budget.py` mixin (`check_budget`, `_is_founder`, `is_athlete_vip`). Documented in `docs/COACH_RUNTIME_CAP_CONFIG.md`:

| Cap | Standard | VIP | Founder |
|-----|----------|-----|---------|
| Daily requests | 100 | 100 | Uncapped |
| Daily opus requests | 50 | 100 | Uncapped |
| Monthly tokens | 5,000,000 | 5,000,000 | Uncapped |
| Monthly opus tokens | 5,000,000 | 5,000,000 | Uncapped |

Since all traffic routes through the premium lane (Kimi primary = same budget flags as the historical “Opus” lane), the opus and overall caps are aligned at 5M. At Kimi rates ($0.383/M input, $1.72/M output) worst-case 5M tokens ≈ $4.59/user/month against $24.99/mo subscription revenue (18%). Realistic usage (~450K tokens) costs ~$0.84/month (3%). The `opus_*` column names are vestigial from Sonnet-era routing — semantic meaning is now "premium lane."

- **`check_budget()`** — enforces caps per `CoachUsage` records
- **`_is_founder()`** — `OWNER_ATHLETE_ID` env var bypasses all caps
- **`is_athlete_vip()`** — checks `COACH_VIP_ATHLETE_IDS` env var + `athlete.is_coach_vip` DB flag
- **Cost formula:** `(input_tokens * 0.0383 + output_tokens * 0.172) / 100` (Kimi rates)

### Context Building

Three context builders serve different surfaces:

1. **`build_athlete_brief()`** in `services/coach_tools/brief.py` — comprehensive athlete context for coach chat. 14-day recent runs, identity, wellness, PBs, race predictions, fingerprint, weekly volume. Header instructs LLM to USE pre-computed relative labels verbatim.

2. **`_build_athlete_context_for_chat()`** in `services/coaching/_context.py` — 7-day activity summary, 30-day stats, check-ins, Garmin watch data, planned workouts. All dates include `_relative_date()` labels.

3. **`_build_athlete_state_for_opus()`** in `services/coaching/_context.py` — premium context with recent runs, latest check-in. Dates include relative labels. This athlete-state packet is now injected into both Kimi and Sonnet request messages by `services/coaching/_llm.py`, rather than being computed and dropped on the Kimi path.

### System Prompt

The system prompt assembled in `services/coaching/core.py` includes:

- **Athlete calibration:** Adapts to experience level — experienced athletes don't get default conservatism
- **Data verification discipline:** Must query actual data before making pace/split comparisons
- **Fatigue threshold context:** During build phases, thresholds are context not warnings
- **N=1 principles:** No population statistics, no template narratives
- **Anti-hallucination:** Never infer from workout titles, never guess relative dates

### Coach Tools

The coach has access to ~26 tools defined in the `services/coach_tools/` package (split from the former 4.9K-line `coach_tools.py` god file into `brief.py`, `insights.py`, `activity.py`, `wellness.py`, `performance.py`, `plan.py`, `profile.py`, `load.py`, `_utils.py`):

- `get_recent_runs()` — last N days of run activities. As of `fit_run_001`
  every row also carries the FIT-derived metrics (`avg_power_w`,
  `max_power_w`, `avg_stride_length_m`, `avg_ground_contact_ms`,
  `avg_ground_contact_balance_pct`, `avg_vertical_oscillation_cm`,
  `avg_vertical_ratio_pct`, `total_descent_m`, `moving_time_s`) when
  present, plus a resolved `perceived_effort` envelope from
  `services/effort_resolver.py` with `{rpe, source, feel_label, confidence}`.
  The resolver enforces the founder rule: `ActivityFeedback.perceived_effort`
  wins outright (`confidence: high`), Garmin self-eval is a fallback
  (`confidence: low`), never blended.
- `get_wellness_trends()` — 28-day check-in trends
- `get_pb_patterns()` — personal best analysis
- `build_athlete_brief()` — comprehensive context (includes Nutrition Snapshot: today's totals, goal, day tier, targets)
- `get_nutrition_correlations()` — nutrition-related findings from the correlation engine
- `get_nutrition_log()` — recent nutrition entries for an athlete. The response includes explicit coverage, today's logged-so-far totals, per-date additive totals, entry count, and evidence. Multiple same-date `daily` entries are additive partial logs, not replacements or complete-day totals.
- `search_activities()` — explicit activity lookup by date/name/race/distance/sport/workout type. This exists so the coach can verify older races or athlete corrections without pretending `get_recent_runs()` is full-history search. Query construction is shared with the activities API via `services/activity_search.py`.
- Activity data queries, plan data, correlation findings

### Conversation Management

- **`ConversationQualityManager`** — manages conversation flow and quality
- **`MessageRouter`** — routes messages to appropriate handlers
- **`CoachChat`** model — stores conversations with JSONB messages
- **`AthleteFact` memory** — async fact extraction runs after saved coach turns and stores athlete-stated facts in `models/athlete.py`. `services/coaching/_context.py` now renders coaching-memory facts separately from generic facts: race psychology, injury context, invalid race anchors, training intent, fatigue strategy, sleep baseline, stress boundaries, coaching preference, and strength context are injected as coaching constraints rather than flat facts. This preserves the async contract: no synchronous `AthleteFact` writes during chat.
- **Turn guard** (`services/turn_guard_monitor.py`) — prevents infinite loops
- **Conversation outcome contract** (`services/coaching/_conversation_contract.py`) — lightweight classifier for `quick_check`, `decision_point`, `correction_dispute`, `emotional_load`, `race_strategy`, and related conversation types. The contract is injected into model context and then enforced post-response in `services/coaching/_guardrails.py`: contract failures trigger one targeted retry before the response is saved. Quick checks enforce a word cap, decision points require a tradeoff/default frame, correction/dispute turns require verification or athlete-stated labeling, emotional-load turns reject prying, and race strategy must include an execution shape.

### KB Violation Scanner

`_check_kb_violations()` in `services/coaching/_constants.py` scans coach output against the 76-rule KB registry. Catches claims that violate known principles (e.g., citing population statistics, making directional claims without data).

## Key Decisions

- **Universal Kimi coach** (Apr 2026): Replaced per-tier Gemini/Sonnet routing for chat. All athletes share the same Kimi tool path; production default model id advanced to **`kimi-k2.6`** via `COACH_CANARY_MODEL` (was marketed as K2.5 during rollout).
- **Caps recalibrated** (Apr 7, 2026): Raised from Sonnet-era levels (50K tokens/month) to Kimi-appropriate levels (2M standard, 5M VIP). No athlete should ever cap out — it's a product-killer.
- **Date rendering fix** (Apr 7, 2026): All 7 date-emitting code paths now include pre-computed relative labels. `_relative_date()` precision extended to day-level through 30 days.
- **Athlete calibration** (Apr 6, 2026): Coach prompt no longer defaults to conservatism regardless of athlete experience.
- **Nutrition context** (Apr 9, 2026): `build_athlete_brief` now includes a Nutrition Snapshot section. Two new tools (`get_nutrition_correlations`, `get_nutrition_log`) let the coach query nutrition data on demand.
- **FIT metrics + effort resolver in coach context** (Apr 19, 2026 — `fit_run_001` Phase 3): Every recent run row now carries power, running dynamics, true moving time, and a resolved perceived-effort envelope with provenance. The new `services/effort_resolver.py` is the single source of truth — athlete-provided RPE always wins over Garmin self-eval, never blended.
- **Coach trust foundation slice** (Apr 24, 2026): Added `search_activities`, shared activity query construction, Kimi/Sonnet athlete-state injection, Gemini gate re-scope, additive nutrition evidence, and the conversation outcome contract skeleton.
- **Conversation contract enforcement** (Apr 24, 2026): Turn guard now validates normalized model output against the conversation outcome contract and retries once with a targeted correction when the answer violates the expected shape. Tool-use validation recognizes race, nutrition, calendar-day, split, and activity-search tools as grounding tools so grounded answers do not raise false no-data warnings.
- **N=1 coaching memory slice** (Apr 24, 2026): Fact extraction now recognizes coaching-memory types and the coach prompt renders them as constraints so future turns can respect boundaries, invalid anchors, race psychology, fatigue strategy, sleep baseline, and strength context.

## Known Issues

- **Two context builders** (`build_athlete_brief` and `_build_athlete_context_for_chat`) overlap significantly. Could be consolidated.

## What's Next

- Briefing-to-coach response loop: tappable emerging patterns → coach opens with pre-loaded finding context
- Fact extraction from coach conversations feeds the limiter lifecycle classifier

## Sources

- `docs/COACH_RUNTIME_CAP_CONFIG.md` — canonical cap reference
- `docs/specs/COACH_MODEL_ROUTING_RESET_SPEC.md` — routing architecture
- `docs/specs/KIMI_K25_COMPARISON_SPEC.md` — Kimi adoption
- `docs/BUILDER_INSTRUCTIONS_2026-03-08_FOUNDER_OPUS_ROUTING.md` — VIP routing
- `apps/api/services/coaching/` — coach package (`core.py` + 7 mixins + `_constants.py`)
- `apps/api/services/coach_tools/` — coach tool package (9 files by concern)
- `apps/api/services/ai_coach.py` — legacy 5-line shim (preserves `from services.ai_coach import AICoach`)
