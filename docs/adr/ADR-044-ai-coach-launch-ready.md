# ADR-044: AI Coach Launch-Ready Implementation

**Status:** Accepted  
**Date:** 2026-01-19  
**Author:** Opus 4.5 (Planner Architect)

---

## Context

The AI Coach feature was built by an early Composer 1 agent and required significant enhancement to be launch-ready. Key gaps included: no conversation memory, no bounded tools, no evidence citations, and static suggestions.

---

## Decision

Implemented a launch-ready Coach with four phases:

### Phase 1: Conversation Memory
- Added `coach_thread_id` column to Athlete model
- Threads persist across sessions and page refreshes
- "New conversation" button clears thread and starts fresh

### Phase 2: Bounded Tools
- Implemented 5 tools via OpenAI function calling:
  - `get_recent_runs` — Last N days of runs
  - `get_efficiency_trend` — Efficiency over time
  - `get_plan_week` — Current week's plan
  - `get_training_load` — CTL/ATL/TSB metrics
  - `get_correlations` — What's working/not working
- Coach requests data through tools, doesn't invent metrics

### Phase 3: Evidence Citations
- All tools return `evidence[]` with `type`, `id`, `date`, `value`
- System prompt requires explicit citations
- Responses cite specific runs, dates, and values
- "I don't have enough data" for insufficient data cases

### Phase 4: Dynamic Suggestions
- Suggestions based on athlete state:
  - Long run tomorrow → "Any tips for tomorrow's long run?"
  - Completed run today → "How did today's run go?"
  - TSB < -20 → "Am I overtraining?"
  - Efficiency improving → "Am I getting fitter?"
  - No recent activity → "I haven't run in a few days..."
- Frontend fetches from API (no hardcoded list)

---

## Consequences

**Positive:**
- Athletes get natural-language access to their data
- Evidence citations build trust and verifiability
- Bounded tools prevent hallucination structurally
- Conversation memory enables natural follow-ups
- Dynamic suggestions feel personalized

**Negative:**
- Token cost per conversation
- Latency for tool calls (~2s per tool)
- Complexity in tool implementation

---

## Rationale

**N=1 Philosophy alignment:**
Coach only speaks from the athlete's actual data. No population defaults, no generic advice. Every claim is backed by tool-derived evidence.

**Architecture alignment:**
Tools call existing StrideIQ services (efficiency analytics, training load, correlations). The LLM is interface compression, not core intelligence.

---

## Files Changed

- `apps/api/models.py` — added `coach_thread_id`
- `apps/api/services/ai_coach.py` — conversation memory, function calling, evidence requirements
- `apps/api/services/coach_tools.py` — new file with 5 bounded tools
- `apps/api/routers/ai_coach.py` — new conversation endpoint, dynamic suggestions
- `apps/web/app/coach/page.tsx` — new conversation button, dynamic suggestions
- Multiple Alembic migrations for schema changes
