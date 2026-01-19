# ADR-047: Coach Architecture Refactor

**Status:** Complete (Verified 2026-01-19)  
**Date:** 2026-01-19  
**Author:** Opus 4.5 (Planner)  
**Phase:** 3 of 5 (N=1 Insight Engine Roadmap)  
**Depends On:** ADR-046 (new coach tools)

---

## Context

### Current State

`ai_coach.py` has:
- 5 tools registered in `_assistant_tools()`: `get_recent_runs`, `get_efficiency_trend`, `get_plan_week`, `get_training_load`, `get_correlations`
- Fixed model: `gpt-4o` (~$0.08 per query based on observed usage)
- No intent classification — all queries go to same model
- Tool dispatch hardcoded in `chat()` method

### Problem

1. **ADR-046 tools not registered** — The 5 new tools (`get_race_predictions`, `get_recovery_status`, `get_active_insights`, `get_pb_patterns`, `get_efficiency_by_zone`) exist in `coach_tools.py` but are NOT available to the OpenAI Assistant.

2. **Cost too high** — Simple queries ("What's my TSB?") cost same as complex queries ("Analyze my training periodization"). Target: < $0.01/query.

3. **No intent routing** — All queries use expensive model regardless of complexity.

---

## Decision

### Part 1: Register ADR-046 Tools

Add 5 new tool definitions to `_assistant_tools()`:

```python
{
    "type": "function",
    "function": {
        "name": "get_race_predictions",
        "description": "Get race time predictions for 5K, 10K, Half Marathon, and Marathon.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
},
{
    "type": "function",
    "function": {
        "name": "get_recovery_status",
        "description": "Get recovery metrics: half-life, durability index, false fitness and masked fatigue signals.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
},
{
    "type": "function",
    "function": {
        "name": "get_active_insights",
        "description": "Get prioritized actionable insights for the athlete.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Max insights to return (default 5, max 10).",
                    "minimum": 1,
                    "maximum": 10,
                }
            },
            "required": [],
        },
    },
},
{
    "type": "function",
    "function": {
        "name": "get_pb_patterns",
        "description": "Get training patterns that preceded personal bests, including optimal TSB range.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
},
{
    "type": "function",
    "function": {
        "name": "get_efficiency_by_zone",
        "description": "Get efficiency trend for specific effort zones (easy, threshold, race).",
        "parameters": {
            "type": "object",
            "properties": {
                "effort_zone": {
                    "type": "string",
                    "enum": ["easy", "threshold", "race"],
                    "description": "Effort zone to analyze (default threshold).",
                },
                "days": {
                    "type": "integer",
                    "description": "Days of history (default 90, max 365).",
                    "minimum": 30,
                    "maximum": 365,
                }
            },
            "required": [],
        },
    },
},
```

### Part 2: Add Tool Dispatch

In `chat()` method, add dispatch for new tools:

```python
elif tool_name == "get_race_predictions":
    output = coach_tools.get_race_predictions(self.db, athlete_id)
elif tool_name == "get_recovery_status":
    output = coach_tools.get_recovery_status(self.db, athlete_id)
elif tool_name == "get_active_insights":
    output = coach_tools.get_active_insights(self.db, athlete_id, **args)
elif tool_name == "get_pb_patterns":
    output = coach_tools.get_pb_patterns(self.db, athlete_id)
elif tool_name == "get_efficiency_by_zone":
    output = coach_tools.get_efficiency_by_zone(self.db, athlete_id, **args)
```

### Part 3: Simple 2-Tier Model Selection

The analytical intelligence lives in the tools (correlation engine, race predictor, etc.), not the LLM. The LLM just calls tools and formats responses. Therefore, we use affordable models for all queries.

```python
MODEL_SIMPLE = "gpt-3.5-turbo"    # ~$0.002/query - data lookups
MODEL_STANDARD = "gpt-4o-mini"    # ~$0.01/query  - everything else

def classify_query(self, message: str) -> str:
    """
    Classify query to select appropriate model.
    
    Returns: 'simple' or 'standard'
    """
    message_lower = message.lower()
    
    # Simple: Direct data lookups (single tool call, minimal reasoning)
    simple_patterns = [
        "what's my tsb", "what is my tsb",
        "what's my ctl", "what is my ctl",
        "what's my atl", "what is my atl",
        "show my plan", "this week's plan",
        "my last run", "recent runs",
        "my race predictions", "predicted times",
        "recovery status", "am i recovering",
    ]
    if any(p in message_lower for p in simple_patterns):
        return "simple"
    
    # Everything else: Standard
    return "standard"

def get_model_for_query(self, query_type: str) -> str:
    """Map query type to model. No tier gating needed."""
    if query_type == "simple":
        return self.MODEL_SIMPLE
    return self.MODEL_STANDARD
```

**No tier gating. No rate limiting. No new tables.**

Cost ceiling: ~$0.01/query for all users.

### Part 4: Dynamic Model Selection

Modify `chat()` to use appropriate model per query:

```python
async def chat(self, athlete_id: UUID, message: str, include_context: bool = True) -> Dict[str, Any]:
    # Classify query and get model
    query_type = self.classify_query(message)
    model = self.get_model_for_query(query_type)
    
    # Log model selection for cost tracking
    logger.info(f"Coach query: type={query_type}, model={model}")
    
    # ... existing thread creation ...
    
    # Run with selected model
    run = self.client.beta.threads.runs.create(
        thread_id=thread_id,
        assistant_id=self.assistant_id,
        model=model,  # Override model per query
    )
    
    # ... rest of method unchanged ...
```

---

## Implementation

### File to Modify

`apps/api/services/ai_coach.py` — All changes in one file

**No new models. No migrations. No tier gating.**

### Steps

1. Add model constants at class level: `MODEL_SIMPLE`, `MODEL_STANDARD`
2. Add 5 new tool definitions to `_assistant_tools()` method
3. Add 5 new elif cases in tool dispatch (chat method, around line 685)
4. Add `classify_query()` method
5. Add `get_model_for_query()` method
6. Modify `chat()` to use dynamic model selection

---

## Acceptance Criteria

### Must Pass

1. **New tools callable by Coach**
   ```
   Ask: "What's my predicted marathon time?"
   → Coach calls get_race_predictions
   → Returns actual prediction data
   ```

2. **PB patterns accessible**
   ```
   Ask: "What was my TSB when I ran my PRs?"
   → Coach calls get_pb_patterns
   → Returns TSB range and PB count (6 PBs for Judge)
   ```

3. **Recovery status accessible**
   ```
   Ask: "Am I recovering well?"
   → Coach calls get_recovery_status
   → Returns recovery metrics
   ```

4. **Simple query uses gpt-3.5-turbo**
   ```
   Ask: "What's my TSB?"
   → Log shows: model=gpt-3.5-turbo
   ```

5. **Standard query uses gpt-4o-mini**
   ```
   Ask: "Analyze my training and suggest improvements"
   → Log shows: model=gpt-4o-mini
   ```

### Cost Validation

6. **All queries cost < $0.01**
   - Simple: ~$0.002
   - Standard: ~$0.01
   - No query exceeds $0.01

---

## Testing Protocol

**Tester MUST:**
1. Ask Coach about race predictions → verify `get_race_predictions` tool called
2. Ask Coach about PB patterns → verify correct TSB range returned (6 PBs, TSB max ~28)
3. Ask simple question ("What's my TSB?") → verify gpt-3.5-turbo in logs
4. Ask standard question ("Analyze my training") → verify gpt-4o-mini in logs
5. Cross-check numerical outputs against known athlete data

---

## Notes for Builder

1. **Verify tool dispatch order** — New tools should come before the `else` (unknown tool) case
2. **Model override in runs.create** — The `model` parameter overrides assistant's default model
3. **Log model selection** — Add `logger.info(f"Coach query: type={query_type}, model={model}")`
4. **No migration needed** — All changes in ai_coach.py only
5. **Test with actual OpenAI calls** — Model selection only works in production (not mocked)

---

## Rollback Plan

If issues arise:
1. Revert to fixed gpt-4o-mini for all queries (safe, affordable default)
2. Keep new tool registrations (low risk)

---

## Dependencies

- ADR-046 tools must be implemented in `coach_tools.py` (COMPLETE)
- OpenAI API access with gpt-3.5-turbo and gpt-4o-mini models

---

**Awaiting Judge approval.**
