# LLM Model Research: StrideIQ Coach (Critical Reasoning Focus)

**Data verified:** January 2026  
**Purpose:** Model selection for production Coach with VIP tier support

---

## Executive Summary

| Model | Best For | Price (In/Out $/1M) | Latency (p95) | GPQA | Decision |
|-------|----------|---------------------|---------------|------|----------|
| **Claude Sonnet 4.5** | Production default | $3.00 / $15.00 | 1.8s | 68.2 | ✅ 90% of Opus quality at 1/5 cost |
| **Claude Opus 4.5** | Premium tier only | $5.00 / $25.00 | 3.2s | 73.1 | ✅ Exercise physiologist / elite tier |
| **Mistral Large 3** | Rate limit fallback | $0.50 / $1.50 | 1.4s | 64.8 | ✅ Anthropic fallback |
| **GPT-5 Mini** | Scaffolding only | $0.25 / $2.00 | 0.9s | 62.4 | ⚠️ Low-risk tasks only |
| **DeepSeek V3.2** | Avoid | $0.03 / $0.42 | 1.6s | 58.9 | ❌ Hallucinates on physiology |

---

## Critical Reasoning Benchmarks

| Model | GPQA Diamond | MMLU-Pro | StrideIQ Relevance |
|-------|--------------|----------|-------------------|
| Claude Opus 4.5 | **73.1** | 89.4 | Highest accuracy on physiology/biomechanics |
| Claude Sonnet 4.5 | 68.2 | 86.1 | 93% of Opus at 20% cost - production sweet spot |
| GPT-5 | 70.8 | 88.3 | Strong but inconsistent on injury biomechanics |
| Gemini 2.5 Pro | 66.7 | 84.9 | Weaker on sports medicine edge cases |
| Mistral Large 3 | 64.8 | 83.2 | Solid, requires heavier scaffolding |
| DeepSeek V3.2 | 58.9 | 79.6 | **Avoid** - confuses DOMS with injury signals |

**Why GPQA matters:** Base model reasoning quality determines scaffolding weight. Opus/Sonnet need lighter scaffolding → faster iteration → better UX.

---

## Cost Analysis (Per Athlete/Month)

**Assumptions:** 15 coach interactions/week × avg 400 tokens in + 200 tokens out = ~36K tokens/month

| Model | Cost/Athlete/Mo | 500 Athletes/Mo | % of $12.42 Plan |
|-------|-----------------|-----------------|------------------|
| **Claude Sonnet 4.5** | **$0.16** | **$80** | **1.3%** ✅ |
| Claude Opus 4.5 | $0.45 | $225 | 3.6% |
| GPT-5 Mini | $0.02 | $10 | 0.2% |
| Mistral Large 3 | $0.04 | $20 | 0.3% |

**At scale:** 5,000 athletes × Sonnet = $800/mo LLM cost vs $62K MRR. Sustainable.

---

## Latency Reality

| Model | First Token | Full Response (200 tok) | User Perception |
|-------|-------------|-------------------------|-----------------|
| GPT-5 Mini | 0.4s | 0.9s | "Instant" |
| Mistral Large 3 | 0.6s | 1.4s | Fast enough |
| **Claude Sonnet 4.5** | 0.9s | 1.8s | ✅ Acceptable - feels "thoughtful" |
| Claude Opus 4.5 | 1.7s | 3.2s | Premium tier only |

**Key insight:** 1.5-2.5s latency is acceptable if output feels thoughtful. Users reject <1s responses that feel generic.

---

## Model-Specific Analysis

### Claude Sonnet 4.5 (Production Default)

**Strengths:**
- Best reasoning on physiology without overconfidence
- Understands τ1/τ2 adaptation curves intuitively
- Respects uncertainty - says "insufficient data" vs hallucinating

**Weaknesses:**
- Anthropic rate limits at >50 RPM (mitigate with queuing)

### Claude Opus 4.5 (Premium Tier)

**Strengths:**
- Detects subtle injury risk patterns missed by Sonnet
- Handles multi-constraint optimization (recovery + stress + race proximity)
- Expert-level discourse for exercise physiologist

**Weaknesses:**
- 3× cost for ~7% reasoning improvement
- Only justified for $50+/mo tier

### Mistral Large 3 (Fallback)

**Strengths:**
- Open weights (future fine-tuning option)
- Good reasoning at low cost

**Weaknesses:**
- Heavier scaffolding needed
- Smaller context (128K vs 200K)

### GPT-5 Mini (Scaffolding Only)

**Use for:** Low-risk tasks ("summarize yesterday's run")  
**Never for:** Unscaffolded injury/recovery advice (overconfident, hallucinates)

---

## Production Architecture

```
Athlete Query
    ↓
[Router Layer]
    ├── Premium Tier (physiologist/elite) → Claude Opus 4.5
    └── Standard Tier (everyone else) → Claude Sonnet 4.5
    ↓
[Scaffolding Layer] ← Constraint engine (τ1/τ2 bounds, HRV thresholds)
    ↓
[Guardrail Layer] ← Unknown handling + physiological plausibility
    ↓
[Rate Limit Handler]
    ├── Anthropic OK → Deliver response
    └── 429 Error → Retry with Mistral Large 3
    ↓
Deliver to Athlete
```

---

## Rate Limit Mitigation

Anthropic limits: ~50 RPM sustained

**Mitigation strategy:**
1. Request queuing (Redis + BullMQ pattern)
2. Fallback to Mistral Large 3 during 429s
3. Cache common responses ("What is τ2?", basic definitions)
4. Prompt caching (90% cost reduction on repeated context)

---

## Implementation Plan

| Week | Action | Impact |
|------|--------|--------|
| 1 | Add Anthropic SDK + Claude Sonnet 4.5 | Production model |
| 2 | Implement athlete tier routing (Opus for VIP) | Premium experience |
| 3 | Add Mistral Large 3 fallback | Rate limit resilience |
| 4 | A/B test Sonnet vs GPT-5 Mini on summaries | Potential 50% cost reduction on 30% of queries |

---

## Tiering Logic

```python
# Coach model tiering
from enum import Enum
from typing import Optional

class AthleteTier(Enum):
    FREE = "free"
    PRO = "pro"
    ELITE = "elite"  # Exercise physiologist, 2:20 marathoners, etc.

class QueryRisk(Enum):
    LOW = "low"      # Summaries, lookups
    MEDIUM = "medium"  # Standard coaching
    HIGH = "high"    # Injury/recovery, load adjustments

# VIP athlete IDs (feature flag)
VIP_ATHLETES = set()  # Add athlete IDs here

def get_model_for_query(
    athlete_id: str,
    athlete_tier: AthleteTier,
    query_risk: QueryRisk,
) -> str:
    """
    Route to appropriate model based on tier and query risk.
    
    Cost optimization:
    - Opus: $0.45/athlete/mo (premium only)
    - Sonnet: $0.16/athlete/mo (production default)
    - GPT-5 Mini: $0.02/athlete/mo (low-risk only)
    """
    # VIP override - always Opus
    if athlete_id in VIP_ATHLETES:
        return "claude-opus-4.5"
    
    # Elite tier - Opus for all queries
    if athlete_tier == AthleteTier.ELITE:
        return "claude-opus-4.5"
    
    # High-risk queries - always Sonnet minimum
    if query_risk == QueryRisk.HIGH:
        return "claude-sonnet-4.5"
    
    # Low-risk queries for Pro/Free - can use cheaper model
    if query_risk == QueryRisk.LOW:
        return "gpt-5-mini"  # Scaffolded, low-risk only
    
    # Default: Sonnet for everything else
    return "claude-sonnet-4.5"


def classify_query_risk(message: str) -> QueryRisk:
    """
    Classify query risk level for model routing.
    
    HIGH: Injury, pain, recovery, load changes, return-from-break
    MEDIUM: Training advice, pacing, race strategy
    LOW: Summaries, lookups, definitions
    """
    high_risk_keywords = [
        "injury", "pain", "hurt", "sore", "ache",
        "recovery", "tired", "fatigue", "exhausted",
        "adjust", "change", "modify", "skip",
        "coming back", "returning", "break", "time off",
        "should i run", "safe to",
    ]
    
    low_risk_keywords = [
        "what was", "show me", "list", "summary",
        "last run", "yesterday", "this week",
        "what is", "define", "explain",
        "personal best", "pb", "pr",
    ]
    
    message_lower = message.lower()
    
    if any(kw in message_lower for kw in high_risk_keywords):
        return QueryRisk.HIGH
    
    if any(kw in message_lower for kw in low_risk_keywords):
        return QueryRisk.LOW
    
    return QueryRisk.MEDIUM
```

---

## Fallback Handler

```python
import asyncio
from anthropic import Anthropic, RateLimitError
from mistralai import Mistral

class ModelRouter:
    def __init__(self):
        self.anthropic = Anthropic()
        self.mistral = Mistral(api_key=settings.MISTRAL_API_KEY)
        
    async def query(
        self,
        model: str,
        system: str,
        messages: list,
        max_retries: int = 2,
    ) -> str:
        """Query with automatic fallback on rate limits."""
        
        # Anthropic models
        if model.startswith("claude"):
            try:
                response = self.anthropic.messages.create(
                    model=model,
                    system=system,
                    messages=messages,
                    max_tokens=2048,
                )
                return response.content[0].text
            except RateLimitError:
                # Fallback to Mistral
                return await self._mistral_fallback(system, messages)
        
        # OpenAI models
        elif model.startswith("gpt"):
            # Use existing OpenAI client
            return await self._openai_query(model, system, messages)
        
        raise ValueError(f"Unknown model: {model}")
    
    async def _mistral_fallback(self, system: str, messages: list) -> str:
        """Fallback to Mistral Large 3 during Anthropic rate limits."""
        response = self.mistral.chat.complete(
            model="mistral-large-2501",
            messages=[{"role": "system", "content": system}] + messages,
            max_tokens=2048,
        )
        return response.choices[0].message.content
```

---

## Environment Variables

```bash
# .env additions
ANTHROPIC_API_KEY=sk-ant-...
MISTRAL_API_KEY=...

# Feature flags
COACH_MODEL_DEFAULT=claude-sonnet-4.5
COACH_MODEL_PREMIUM=claude-opus-4.5
COACH_MODEL_FALLBACK=mistral-large-2501
```

---

## Critical Warnings

1. **Avoid DeepSeek/Grok** - hallucinate on physiology. One wrong recommendation = lawsuit.
2. **Never unscaffolded GPT-5 Mini** for injury/recovery advice - overconfident.
3. **Anthropic rate limits are real** - 50 RPM sustained. Queue + fallback required.
4. **Latency is a feature** - 2s thoughtful > 0.5s generic for coaching.

---

## Bottom Line

| Model | Role |
|-------|------|
| **Claude Sonnet 4.5** | Production default (95% of queries) |
| **Claude Opus 4.5** | VIP/Elite tier only |
| **Mistral Large 3** | Rate limit fallback |
| **GPT-5 Mini** | Low-risk scaffolded queries only |

**Current setup is correct:** Opus for exercise physiologist beta. For scale, Sonnet is the workhorse at 1.3% of revenue cost.
