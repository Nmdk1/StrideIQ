# ADR-061: Hybrid Model Architecture with Cost Caps

**Date:** January 2026  
**Status:** Approved  
**Supersedes:** Original Anthropic-only proposal

---

## Decision

Use **GPT-4o-mini for 95% of queries** (cost-efficient) with **Claude Opus 4.5 for 5% high-stakes queries** (maximum reasoning quality), plus hard cost caps to guarantee predictable unit economics.

---

## Context

### The Problem

Real-world coach usage generates ~960K tokens/month per athlete (post-architecture optimization):
- 2× one-hour conversations/week
- 4+ daily questions
- Context accumulation in threads

At $12.42/month subscription, model costs must stay below ~10% of revenue to maintain healthy margins.

### Cost Reality (January 2026 Pricing)

| Model | Input | Output | Blended Rate | 960K tokens/mo |
|-------|-------|--------|--------------|----------------|
| GPT-4o-mini | $0.15/1M | $0.60/1M | $0.33/1M | **$0.32** |
| GPT-4o | $2.50/1M | $10.00/1M | $5.50/1M | **$5.28** |
| Claude Sonnet 4.5 | $3.00/1M | $15.00/1M | $8.00/1M | **$7.68** |
| Claude Opus 4.5 | $5.00/1M | $25.00/1M | $13.00/1M | **$12.48** |

**Finding:** Quality models (Sonnet/Opus for 100% of queries) exceed subscription revenue. GPT-4o-mini is the only model that survives at volume.

### The Insight

Not all queries require premium reasoning:
- **95% of queries** = training advice, progress reviews, general Q&A → GPT-4o-mini is adequate
- **5% of queries** = injury assessment, return-from-break, load decisions → Maximum reasoning quality matters (liability, safety)

---

## Architecture

### Model Routing

| Query Type | Model | Share | Why |
|------------|-------|-------|-----|
| Standard coaching | GPT-4o-mini | ~90% | Cost-efficient, adequate for simple queries |
| High-stakes decisions | Claude Opus 4.5 | ~5% | Injury/recovery/load (liability risk) |
| High-complexity reasoning | Claude Opus 4.5 | ~5% | Causal + ambiguity (needs real reasoning) |

### Opus Triggers (Two Categories)

**1. High-Stakes (Liability Risk)**
- Injury/pain mentions
- Return-from-break decisions
- Load adjustments
- Overtraining concerns

**2. High-Complexity (Reasoning Required)**
- Causal questions ("why am I...", "what's causing...")
- Ambiguity signals ("but", "despite", "even though")
- Multi-factor analysis (2+ concerns in one query)

### High-Stakes Signals (Opus Triggers)

```python
from enum import Enum

class HighStakesSignal(Enum):
    """Signals that trigger Opus routing for maximum reasoning quality."""
    
    # Injury/pain (liability risk)
    INJURY = "injury"
    PAIN = "pain"
    
    # Recovery concerns
    OVERTRAINING = "overtraining"
    FATIGUE = "fatigue"
    
    # Load decisions
    SKIP_DECISION = "skip"
    LOAD_ADJUSTMENT = "load"
    
    # Return-from-break (high error risk)
    RETURN_FROM_BREAK = "return"
    
    # Illness recovery
    ILLNESS = "illness"


HIGH_STAKES_PATTERNS = [
    # Injury/pain signals
    "injury", "injured", "pain", "painful", "hurt", "hurting",
    "sore", "soreness", "ache", "aching", "sharp", "stabbing",
    "tender", "swollen", "swelling", "inflammation",
    "strain", "sprain", "tear", "stress fracture",
    "knee", "shin", "achilles", "plantar", "it band", "hip",
    
    # Recovery concerns
    "overtrain", "overtraining", "burnout", "exhausted",
    "can't recover", "not recovering", "always tired",
    "resting heart rate", "hrv dropping", "hrv crashed",
    
    # Return-from-break
    "coming back", "returning from", "time off", "break",
    "haven't run", "first run back", "starting again",
    "after illness", "after sick", "after covid",
    "after surgery", "post-op",
    
    # Load decisions
    "should i run", "safe to run", "okay to run",
    "skip", "should i skip", "take a day off",
    "reduce mileage", "cut back", "too much",
    "push through", "run through",
]
```

---

## Cost Caps (Hard Limits)

### Per-Request Limits

| Limit | Value | Purpose |
|-------|-------|---------|
| MAX_INPUT_TOKENS | 4,000 | Bounds context (athlete state + 3 turns) |
| MAX_OUTPUT_TOKENS | 500 | Forces concise responses |

### Per-Athlete Daily Limits

| Limit | Value | Purpose |
|-------|-------|---------|
| MAX_REQUESTS_PER_DAY | 50 | Prevents abuse |
| MAX_OPUS_REQUESTS_PER_DAY | 3 | Protects expensive model |

### Per-Athlete Monthly Limits

| Limit | Value | Purpose |
|-------|-------|---------|
| MONTHLY_TOKEN_BUDGET | 1,000,000 | Hard cost ceiling |
| MONTHLY_OPUS_TOKEN_BUDGET | 50,000 | 5% allocation enforced |

---

## Cost Model

### Per-Athlete Economics (Capped)

| Component | Tokens | Rate | Cost |
|-----------|--------|------|------|
| GPT-4o-mini (95%) | 950,000 | $0.33/1M | $0.31 |
| Opus 4.5 (5%) | 50,000 | $13.00/1M | $0.65 |
| **Total (worst case)** | 1,000,000 | | **$0.96** |

### Margin Analysis

| Metric | Value |
|--------|-------|
| Subscription price | $12.42/month |
| Max LLM cost | $0.96/month |
| LLM as % revenue | **7.7%** |
| Gross margin on LLM | **92.3%** |

---

## Implementation

### 1. High-Stakes Classifier

```python
def is_high_stakes_query(message: str) -> bool:
    """
    Determine if query requires Opus for maximum reasoning quality.
    
    Returns True for:
    - Injury/pain mentions
    - Return-from-break queries
    - Load adjustment decisions
    - Overtraining concerns
    """
    message_lower = message.lower()
    return any(pattern in message_lower for pattern in HIGH_STAKES_PATTERNS)
```

### 2. Budget Tracking

```python
# Database model for usage tracking
class CoachUsage(Base):
    __tablename__ = "coach_usage"
    
    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID, ForeignKey("athletes.id"), nullable=False)
    
    # Daily tracking
    date = Column(Date, nullable=False, default=date.today)
    requests_today = Column(Integer, default=0)
    opus_requests_today = Column(Integer, default=0)
    tokens_today = Column(Integer, default=0)
    
    # Monthly tracking (reset on 1st of month)
    month = Column(String(7), nullable=False)  # "2026-01"
    tokens_this_month = Column(Integer, default=0)
    opus_tokens_this_month = Column(Integer, default=0)
    
    __table_args__ = (
        UniqueConstraint("athlete_id", "date", name="uq_coach_usage_athlete_date"),
    )
```

### 3. Budget Check

```python
async def check_budget(athlete_id: UUID, is_opus: bool = False) -> tuple[bool, str]:
    """
    Check if athlete has budget remaining.
    
    Returns:
        (allowed, reason) - True if request can proceed, else False with reason
    """
    usage = get_or_create_usage(athlete_id)
    
    # Daily request limit
    if usage.requests_today >= MAX_REQUESTS_PER_DAY:
        return False, "Daily request limit reached"
    
    # Opus-specific limits
    if is_opus:
        if usage.opus_requests_today >= MAX_OPUS_REQUESTS_PER_DAY:
            return False, "Daily Opus limit reached"
        if usage.opus_tokens_this_month >= MONTHLY_OPUS_TOKEN_BUDGET:
            return False, "Monthly Opus budget exhausted"
    
    # Monthly token budget
    if usage.tokens_this_month >= MONTHLY_TOKEN_BUDGET:
        return False, "Monthly token budget exhausted"
    
    return True, "OK"
```

### 4. Model Router

```python
def get_model_for_query(
    message: str,
    athlete_id: UUID,
    is_vip: bool = False,
) -> str:
    """
    Route to appropriate model based on query content and budget.
    
    Priority:
    1. VIP athletes always get Opus (if budget allows)
    2. High-stakes queries get Opus (if budget allows)
    3. Everything else gets GPT-4o-mini
    """
    # Check if high-stakes
    wants_opus = is_vip or is_high_stakes_query(message)
    
    if wants_opus:
        # Check Opus budget
        allowed, _ = check_budget(athlete_id, is_opus=True)
        if allowed:
            return "claude-opus-4-5-20251101"
        else:
            # Fallback to GPT-4o (not mini) when Opus budget exhausted
            return "gpt-4o"
    
    return "gpt-4o-mini"
```

### 5. Anthropic Client Integration

```python
from anthropic import Anthropic

class HybridCoach:
    def __init__(self):
        self.openai = OpenAI()
        self.anthropic = Anthropic()
    
    async def query_opus(
        self,
        system: str,
        messages: list,
        athlete_state: str,
    ) -> str:
        """
        Query Claude Opus for high-stakes decisions.
        
        Uses direct API (not Assistants) with minimal context.
        """
        response = self.anthropic.messages.create(
            model="claude-opus-4-5-20251101",
            system=system,
            messages=[
                {"role": "user", "content": f"ATHLETE STATE:\n{athlete_state}"},
                *messages[-6:],  # Last 3 exchanges only
            ],
            max_tokens=500,
        )
        return response.content[0].text
```

---

## Soft Degradation

When budgets are near exhaustion, degrade gracefully instead of hard cutoff:

| Budget Level | Behavior |
|--------------|----------|
| 0-80% | Normal operation |
| 80-90% | Force GPT-4o-mini even for high-stakes (warn user) |
| 90-100% | Shorter responses (300 tokens max) |
| >100% | Daily requests drop to 10, notify user |

---

## Environment Variables

```bash
# Model configuration
COACH_MODEL_DEFAULT=gpt-4o-mini
COACH_MODEL_HIGH_STAKES=claude-opus-4-5-20251101
COACH_MODEL_FALLBACK=gpt-4o

# Anthropic API
ANTHROPIC_API_KEY=sk-ant-...

# Cost caps
COACH_MAX_REQUESTS_PER_DAY=50
COACH_MAX_OPUS_REQUESTS_PER_DAY=3
COACH_MONTHLY_TOKEN_BUDGET=1000000
COACH_MONTHLY_OPUS_TOKEN_BUDGET=50000
COACH_MAX_INPUT_TOKENS=4000
COACH_MAX_OUTPUT_TOKENS=500
```

---

## Migration Path

### Phase 1: Add Budget Tracking (This Week)
- Add CoachUsage model
- Track tokens per request
- No behavior change yet

### Phase 2: Enable Opus Routing (Next Week)
- Add Anthropic client
- Implement high-stakes classifier
- Route 5% to Opus with budget enforcement

### Phase 3: Soft Degradation (Following Week)
- Add degradation thresholds
- User-facing usage transparency
- Monitor and tune limits

---

## Monitoring

Track these metrics:
- Opus trigger rate (target: ~5%)
- Budget exhaustion rate (target: <1% of athletes/month)
- Average tokens per request
- Cost per athlete per day

---

## VIP Athlete Policy

VIP athletes use the **same routing rules** as standard athletes (Opus only for high-stakes queries) but get **10× Opus allocation**:

| Limit | Standard | VIP (10×) |
|-------|----------|-----------|
| Opus requests/day | 3 | 30 |
| Opus tokens/month | 50K | 500K |
| Total requests/day | 50 | 50 |
| Total tokens/month | 1M | 1M |

**VIP cost ceiling:** ~$6.50/athlete/month (still sustainable)

---

## Summary

| Decision | Choice |
|----------|--------|
| Standard model | GPT-4o-mini (95%) |
| High-stakes model | Claude Opus 4.5 (5%) |
| Fallback when Opus exhausted | GPT-4o |
| Monthly budget per athlete | 1M tokens |
| Opus budget (standard) | 50K tokens (5%) |
| Opus budget (VIP) | 500K tokens (10×) |
| Max cost per athlete (standard) | $0.96/month |
| Max cost per athlete (VIP) | ~$6.50/month |
| Gross margin on LLM | 92.3% (standard) / 48% (VIP) |
