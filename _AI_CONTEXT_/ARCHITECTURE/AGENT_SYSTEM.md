# Agent System Architecture

*Performance Focused Coaching - AI Agent Design*
*Last Updated: 2026-01-08*

---

## Overview

Each athlete gets a persistent AI agent that:
- Remembers their history, preferences, and what works for them
- Maintains conversation continuity (no "starting over")
- Provides personalized coaching based on their data
- Respects usage limits based on subscription tier

---

## Core Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         ATHLETE PROFILE                              │
│  (Permanent - PostgreSQL)                                           │
│                                                                      │
│  - Demographics (age, gender)                                       │
│  - Goals (target race, goal time)                                   │
│  - Injury history                                                   │
│  - Training philosophy preferences                                  │
│  - Historical PRs                                                   │
│  - What works / what doesn't for this athlete                       │
│  - Athlete type (speed-dominant, endurance-dominant, balanced)      │
└─────────────────────────────────────────────────────────────────────┘
                                  ↓
┌─────────────────────────────────────────────────────────────────────┐
│                    OPENAI ASSISTANT (Per Athlete)                    │
│                                                                      │
│  - System instructions (our methodology)                            │
│  - Thread ID (conversation memory - persists across sessions)       │
│  - Tools:                                                           │
│    • query_activities(days, limit)                                  │
│    • get_training_load()                                            │
│    • get_efficiency_trends()                                        │
│    • get_checkin_history()                                          │
│    • query_knowledge_base(topic)                                    │
└─────────────────────────────────────────────────────────────────────┘
                                  ↓
┌─────────────────────────────────────────────────────────────────────┐
│                     CONTEXT INJECTION                                │
│  (Per Query - Built Dynamically)                                    │
│                                                                      │
│  TIER 1: IMMEDIATE (Last 7 days) - Full Detail                      │
│    - Every activity with splits                                     │
│    - All check-ins verbatim                                         │
│    - Recent conversation context                                    │
│                                                                      │
│  TIER 2: RECENT (Last 30 days) - Summarized                         │
│    - Weekly summaries (volume, intensity split)                     │
│    - Key workouts only (long runs, quality sessions)                │
│    - Trend indicators (↑↓→)                                         │
│                                                                      │
│  TIER 3: TRAINING BLOCK (Last 120-160 days) - Compressed            │
│    - Phase detection (base/build/peak/recovery)                     │
│    - Monthly volume progression                                     │
│    - Fitness trajectory (CTL curve)                                 │
│    - Injuries/interruptions                                         │
│                                                                      │
│  TIER 4: CAREER (All time) - Metadata Only                          │
│    - PRs by distance                                                │
│    - Injury history                                                 │
│    - Training philosophy learned                                    │
│    - What works/doesn't work for this athlete                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Context Token Budget

| Tier | Content | Approx Tokens |
|------|---------|---------------|
| Tier 1 (7 days) | Full activity details | ~1,000 |
| Tier 2 (30 days) | Weekly summaries | ~500 |
| Tier 3 (120-160 days) | Compressed training block | ~1,000 |
| Tier 4 (Career) | PRs, injury history, preferences | ~500 |
| **Total Context** | | **~3,000 tokens** |

This leaves room for:
- User query: ~100-500 tokens
- System instructions: ~1,000 tokens
- AI response: ~1,000 tokens
- **Total per interaction: ~5,500 tokens**

---

## Usage Limits by Tier

### Subscription Tiers

| Tier | Price | Queries/Month | Token Budget | Context History |
|------|-------|---------------|--------------|-----------------|
| **Free** | $0 | 10 | 50K | 30 days |
| **Base** | $5 | 50 | 250K | 120 days |
| **Pro** | $25 | 300 | 1.5M | Unlimited |
| **Team** | $75 | 1000 | 5M | Unlimited + athletes |

### Enforcement

```python
class UsageLimiter:
    def check_query_allowed(self, athlete_id: UUID) -> bool:
        """Check if athlete can make another query this billing cycle."""
        usage = get_current_usage(athlete_id)
        limit = get_tier_limit(athlete_id)
        
        if usage.queries >= limit.max_queries:
            return False
        if usage.tokens >= limit.max_tokens:
            return False
        return True
    
    def record_usage(self, athlete_id: UUID, tokens_used: int):
        """Record query and token usage."""
        increment_query_count(athlete_id)
        add_tokens_used(athlete_id, tokens_used)
    
    def get_remaining(self, athlete_id: UUID) -> dict:
        """Return remaining queries and tokens."""
        usage = get_current_usage(athlete_id)
        limit = get_tier_limit(athlete_id)
        return {
            "queries_remaining": limit.max_queries - usage.queries,
            "tokens_remaining": limit.max_tokens - usage.tokens,
            "reset_date": get_billing_reset_date(athlete_id)
        }
```

### User Experience

| Usage Level | Action |
|-------------|--------|
| 0-80% | Normal operation |
| 80-100% | Warning: "You have X queries remaining this month" |
| 100% | Soft block: "Upgrade to continue" or wait for reset |

---

## OpenAI Assistant Configuration

### System Instructions

```
You are a personal running coach for [ATHLETE_NAME]. 

You have access to their complete training history and profile.

Core Principles:
- Show patterns, don't prescribe ("When you do X, Y happens")
- Never say "you should" - say "you might consider"
- Be direct and sparse - athletes don't want essays
- Context matters: understand their current phase and goals
- Easy must be easy - flag when recovery runs aren't easy
- Consistency beats intensity - celebrate showing up

You have tools to query their data. Use them when needed.

Current athlete context will be injected with each message.
```

### Tools

| Tool | Description |
|------|-------------|
| `query_activities` | Get activities by date range or type |
| `get_training_load` | Current ATL/CTL/TSB |
| `get_efficiency_trends` | Efficiency over time |
| `get_checkin_history` | Sleep, stress, soreness data |
| `get_injury_history` | Past injuries and recovery |
| `query_knowledge_base` | Search our methodology |

---

## Thread Management

### Thread Lifecycle

1. **Creation:** When athlete first interacts with AI coach
2. **Persistence:** Thread ID stored in athlete record
3. **Continuation:** Same thread used for all conversations
4. **Pruning:** OpenAI automatically manages thread length
5. **Reset:** Athlete can request "start fresh" (new thread)

### Conversation Memory

The thread maintains:
- Previous questions and answers
- Commitments made ("I'll try more easy runs")
- Topics discussed
- Athlete feedback on recommendations

---

## Future: Custom Features Per Athlete

### Vision (Phase 2)

Athletes can request custom views/features:
1. Athlete asks: "Can I see my long run paces over time?"
2. Agent spins up a custom visualization for THEIR profile
3. Tests and validates on their data
4. Pushes to their dashboard
5. If successful, adds to feature library for all athletes

### Implementation

```python
class FeatureRequest:
    athlete_id: UUID
    request_text: str
    feature_type: str  # "visualization", "analysis", "alert"
    status: str  # "requested", "building", "testing", "deployed", "library"
    
class FeatureBuilder:
    def process_request(self, request: FeatureRequest):
        # 1. Parse intent
        intent = parse_feature_intent(request.request_text)
        
        # 2. Generate code
        code = generate_feature_code(intent, request.athlete_id)
        
        # 3. Test on athlete's data
        result = test_feature(code, request.athlete_id)
        
        # 4. Deploy to athlete's dashboard
        if result.success:
            deploy_to_athlete(code, request.athlete_id)
            
        # 5. Optionally add to library
        if result.generalizable:
            add_to_feature_library(code)
```

---

## Cost Analysis

### Per Interaction Cost (GPT-4 Turbo)

| Component | Tokens | Cost |
|-----------|--------|------|
| Context injection | 3,000 | $0.03 |
| User query | 200 | $0.002 |
| AI response | 800 | $0.024 |
| **Total** | 4,000 | **~$0.05** |

### Margin Analysis

| Tier | Price | Max Cost | Min Margin |
|------|-------|----------|------------|
| Free | $0 | $0.50 | N/A (acquisition) |
| Base | $5 | $2.50 | 50% |
| Pro | $25 | $15.00 | 40% |
| Team | $75 | $50.00 | 33% |

### At Scale

| Athletes | Monthly AI Cost | Monthly Revenue | Gross Margin |
|----------|-----------------|-----------------|--------------|
| 100 | $150 | $750 | 80% |
| 1,000 | $1,500 | $7,500 | 80% |
| 10,000 | $15,000 | $75,000 | 80% |

---

## Implementation Priority

### Phase 1 (Now)
1. ✅ Sanitize knowledge base
2. Create OpenAI Assistant with system instructions
3. Implement context injection (4 tiers)
4. Add usage tracking and limits

### Phase 2 (Post-Beta)
1. Thread management and persistence
2. Tool implementations (query_activities, etc.)
3. Soft/hard limits with upgrade prompts

### Phase 3 (Growth)
1. Custom feature requests
2. Feature library
3. Cross-athlete learning (anonymized)

---

*Performance Focused Coaching - Agent Architecture v1.0*


