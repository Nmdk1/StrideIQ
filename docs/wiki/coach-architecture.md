# AI Coach Architecture

## Current State

The AI coach is the primary conversational interface. Every athlete query routes through `services/ai_coach.py`. The current production model is **Kimi K2.5** for all athletes (universal routing as of Apr 6, 2026). Claude Sonnet 4.6 is the silent fallback on Kimi errors only. Gemini Flash is retired from the coach path.

## How It Works

### Model Routing

All routing logic is in `services/ai_coach.py`:

- **`_determine_model()`** — routes every query to Kimi K2.5
- **`_handle_coach_query()`** — orchestrates the full query lifecycle
- **`get_model_for_query()`** — legacy complexity query classification (now all premium lane)
- **Fallback chain:** Kimi K2.5 → Claude Sonnet 4.6 (on Kimi error only)
- **Model audit trail:** Every coach response records `"model": "kimi-k2.5"` (or fallback model) in the `coach_chat` JSONB message dict

### Budget & Caps

Configured in `ai_coach.py` (lines 76-94), documented in `docs/COACH_RUNTIME_CAP_CONFIG.md`:

| Cap | Standard | VIP | Founder |
|-----|----------|-----|---------|
| Daily requests | 100 | 100 | Uncapped |
| Daily opus requests | 50 | 100 | Uncapped |
| Monthly tokens | 5,000,000 | 5,000,000 | Uncapped |
| Monthly opus tokens | 5,000,000 | 5,000,000 | Uncapped |

Since all traffic routes through the "opus" lane (Kimi K2.5 = premium lane), the opus and overall caps are aligned at 5M. At Kimi K2.5 rates ($0.383/M input, $1.72/M output), worst-case 5M tokens ≈ $4.59/user/month against $24.99/mo subscription revenue (18%). Realistic usage (~450K tokens) costs ~$0.84/month (3%). The `opus_*` column names are vestigial from Sonnet-era routing — semantic meaning is now "premium lane."

- **`check_budget()`** — enforces caps per `CoachUsage` records
- **`_is_founder()`** — `OWNER_ATHLETE_ID` env var bypasses all caps
- **`is_athlete_vip()`** — checks `COACH_VIP_ATHLETE_IDS` env var + `athlete.is_coach_vip` DB flag
- **Cost formula** (line ~656): `(input_tokens * 0.0383 + output_tokens * 0.172) / 100` (Kimi rates)

### Context Building

Three context builders serve different surfaces:

1. **`build_athlete_brief()`** in `coach_tools.py` (line ~3505) — comprehensive athlete context for coach chat. 14-day recent runs, identity, wellness, PBs, race predictions, fingerprint, weekly volume. Header instructs LLM to USE pre-computed relative labels verbatim.

2. **`_build_athlete_context_for_chat()`** in `ai_coach.py` (line ~2530) — 7-day activity summary, 30-day stats, check-ins, Garmin watch data, planned workouts. All dates include `_relative_date()` labels.

3. **`_build_athlete_state_for_opus()`** in `ai_coach.py` (line ~4818) — premium context with recent runs, latest check-in. Dates include relative labels.

### System Prompt

The system prompt in `ai_coach.py` includes:

- **Athlete calibration:** Adapts to experience level — experienced athletes don't get default conservatism
- **Data verification discipline:** Must query actual data before making pace/split comparisons
- **Fatigue threshold context:** During build phases, thresholds are context not warnings
- **N=1 principles:** No population statistics, no template narratives
- **Anti-hallucination:** Never infer from workout titles, never guess relative dates

### Coach Tools

The coach has access to ~26 tools defined in `services/coach_tools.py`:

- `get_recent_runs()` — last N days of run activities
- `get_wellness_trends()` — 28-day check-in trends
- `get_pb_patterns()` — personal best analysis
- `build_athlete_brief()` — comprehensive context (includes Nutrition Snapshot: today's totals, goal, day tier, targets)
- `get_nutrition_correlations()` — nutrition-related findings from the correlation engine
- `get_nutrition_log()` — recent nutrition entries for an athlete
- Activity data queries, plan data, correlation findings

### Conversation Management

- **`ConversationQualityManager`** — manages conversation flow and quality
- **`MessageRouter`** — routes messages to appropriate handlers
- **`CoachChat`** model — stores conversations with JSONB messages
- **Turn guard** (`services/turn_guard_monitor.py`) — prevents infinite loops

### KB Violation Scanner

`_check_kb_violations()` in `ai_coach.py` scans coach output against the 76-rule KB registry. Catches claims that violate known principles (e.g., citing population statistics, making directional claims without data).

## Key Decisions

- **Universal Kimi K2.5** (Apr 6, 2026): Replaced per-tier routing. All athletes get the same model. Canary flag removed.
- **Caps recalibrated** (Apr 7, 2026): Raised from Sonnet-era levels (50K tokens/month) to Kimi-appropriate levels (2M standard, 5M VIP). No athlete should ever cap out — it's a product-killer.
- **Date rendering fix** (Apr 7, 2026): All 7 date-emitting code paths now include pre-computed relative labels. `_relative_date()` precision extended to day-level through 30 days.
- **Athlete calibration** (Apr 6, 2026): Coach prompt no longer defaults to conservatism regardless of athlete experience.
- **Nutrition context** (Apr 9, 2026): `build_athlete_brief` now includes a Nutrition Snapshot section. Two new tools (`get_nutrition_correlations`, `get_nutrition_log`) let the coach query nutrition data on demand.

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
- `apps/api/services/ai_coach.py` — implementation
- `apps/api/services/coach_tools.py` — tool implementations
