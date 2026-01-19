# Builder Handoff: ADR-047 Coach Architecture Refactor

**Date:** 2026-01-19  
**From:** Planner  
**To:** Builder  
**ADR:** `docs/adr/ADR-047-coach-architecture-refactor.md`  
**Status:** Approved

---

## Task Summary

1. Register 5 ADR-046 tools in OpenAI Assistant
2. Add tool dispatch for new tools
3. Implement simple 2-tier model selection (3.5-turbo / 4o-mini)

**Single file change:** `apps/api/services/ai_coach.py`

---

## Step 1: Add Model Constants

At class level (after `SYSTEM_INSTRUCTIONS`), add:

```python
MODEL_SIMPLE = "gpt-3.5-turbo"    # ~$0.002/query
MODEL_STANDARD = "gpt-4o-mini"    # ~$0.01/query
```

---

## Step 2: Add 5 New Tool Definitions

In `_assistant_tools()` method, add after the existing 5 tools:

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

---

## Step 3: Add Tool Dispatch

In `chat()` method, find the tool dispatch section (~line 685). Add BEFORE the `else` case:

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

---

## Step 4: Add Query Classification

Add these methods to the `AICoach` class:

```python
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
    """Map query type to model."""
    if query_type == "simple":
        return self.MODEL_SIMPLE
    return self.MODEL_STANDARD
```

---

## Step 5: Modify chat() for Dynamic Model Selection

In `chat()` method, BEFORE thread creation, add:

```python
# Classify query and get model
query_type = self.classify_query(message)
model = self.get_model_for_query(query_type)

# Log model selection for cost tracking
logger.info(f"Coach query: type={query_type}, model={model}")
```

Then modify `runs.create()` call to pass the model:

```python
run = self.client.beta.threads.runs.create(
    thread_id=thread_id,
    assistant_id=self.assistant_id,
    model=model,  # Override model per query
)
```

---

## Verification Commands

```bash
# Check syntax
docker-compose exec -T api python -c "from services.ai_coach import AICoach; print('Import OK')"

# Verify tool definitions (10 total)
docker-compose exec -T api python -c "
from services.ai_coach import AICoach
from core.database import SessionLocal
db = SessionLocal()
coach = AICoach(db)
tools = coach._assistant_tools()
print(f'Total tools: {len(tools)}')
for t in tools:
    print(f'  - {t[\"function\"][\"name\"]}')
"

# Verify classification
docker-compose exec -T api python -c "
from services.ai_coach import AICoach
from core.database import SessionLocal
db = SessionLocal()
coach = AICoach(db)

tests = [
    ('What is my TSB?', 'simple'),
    ('Analyze my training', 'standard'),
    ('Show my race predictions', 'simple'),
    ('Why am I tired?', 'standard'),
]
for msg, expected in tests:
    result = coach.classify_query(msg)
    status = '✓' if result == expected else '✗'
    print(f'{status} \"{msg}\" -> {result} (expected {expected})')
"
```

---

## Expected Results

| Check | Expected |
|-------|----------|
| Total tools | 10 |
| New tools present | get_race_predictions, get_recovery_status, get_active_insights, get_pb_patterns, get_efficiency_by_zone |
| "What is my TSB?" | simple |
| "Analyze my training" | standard |

---

## Do NOT

- Add new database tables
- Add tier gating logic
- Add rate limiting
- Modify existing tool definitions

---

## When Done

Report:
1. Tools registered (count and names)
2. Classification test results
3. Any deviations from ADR

---

**Begin implementation.**
