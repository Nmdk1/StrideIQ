# ADR-060: Coach LLM Multi-Model Tiering

**Status:** Accepted  
**Date:** 2026-01-31  
**Author:** Michael Shaffer  

---

## Context

The current Coach uses **GPT-4o-mini (2024 version)** - an outdated model with weak reasoning capabilities. This breaks the core trust contract:

**Observed failures:**
- Return-from-injury context: doesn't ask clarifying questions, gives confident but wrong advice
- Comparison queries: confuses "slowest" with "fastest"
- Multi-constraint optimization: fails to balance recovery + stress + race proximity
- Uncertainty handling: hallucinates instead of saying "insufficient data"

**The problem is intelligence, not economics.** Athletes will pay, revenue covers LLM costs. We need a model that can actually reason.

---

## Decision

Adopt OpenAI model tiering based on query complexity:

| Model | Role | Cost/Query | When Used |
|-------|------|------------|-----------|
| **gpt-5-nano** | LOW complexity | $0.0001 | Pure lookups, definitions |
| **gpt-5-mini** | MEDIUM complexity | $0.0005 | Standard coaching (95% of queries) |
| **gpt-5.1** | HIGH complexity | $0.0025 | Multi-factor causal reasoning |
| **gpt-5.2** | HIGH complexity (VIP) | $0.0035 | Flagship for owner + beta testers |

**Why OpenAI vs Claude:** Zero architecture changes. Current Assistants API (threads, tools) works unchanged. Just swap model string.

---

## Opus Usage Constraints

Opus is the **exception**, not the rule. Even for VIPs.

**Who can access Opus:**
- Owner (Michael)
- Explicitly listed beta testers (VIP_ATHLETES set)

**When Opus is used (all gates must pass):**
1. Athlete is in VIP_ATHLETES
2. Per-user cap: < 10 Opus queries this month
3. Global budget: < $50/month total Opus spend
4. Query passes strict complexity check (see below)

**If any gate fails:** Use Sonnet (still excellent)

---

## Query Complexity Classification

**The test:** "Is this deterministic given the data, or does it require weighing competing hypotheses with incomplete information?"

### LOW Complexity (→ GPT-5 Mini, scaffolded)
Pure data retrieval, no reasoning:
- "What was my long run last week?"
- "Show me this week's mileage"
- "What is τ2?"
- "List my personal bests"

### MEDIUM Complexity (→ Claude Sonnet 4.5)
Most coaching questions - rule-based with data:
- "What pace for my tempo run?"
- "Can I move my long run to Saturday?"
- "Should I skip today's workout?"
- "How should I ramp back after 2 weeks off?"
- "Compare this week to last week"

### HIGH Complexity (→ Opus for VIPs, Sonnet for others)
Multi-signal synthesis with ambiguity - requires TRUE reasoning:
- "Why am I getting slower despite running more?" (causal + ambiguity)
- "What's the one thing holding me back?" (multi-signal synthesis)
- "Given I have a work trip, my calf is sore, and I'm behind on sleep, should I do intervals?" (3+ constraints)
- "Is it too soon to do speedwork after my stress fracture?" (ambiguous, needs judgment)

**HIGH requires ALL of:**
1. Causal/synthesis intent (why, what's causing, what's driving)
2. Ambiguity signal (but, despite, even though, not sure)
3. Multiple factors mentioned (2+ "and" or commas)

---

## Considered Alternatives

| Option | Rejected Because |
|--------|------------------|
| **Stay on GPT-4o-mini** | Unacceptable reasoning quality - breaks trust |
| **Upgrade to GPT-4o (current)** | Better, but still overconfident on injury biomechanics |
| **GPT-5** | Inconsistent on sports medicine edge cases |
| **DeepSeek V3.2** | Hallucinates on physiology (DOMS vs injury) - liability |
| **Opus for all VIP queries** | Too expensive ($50/month cap would be hit in days) |

---

## Consequences

### Positive
- Dramatically better reasoning on complex queries
- Respects uncertainty ("I don't have enough data" vs hallucinating)
- Sustainable cost: Sonnet at $0.16/athlete/month
- VIP experience preserved within budget

### Negative
- New SDK dependencies (anthropic, mistralai)
- Additional secrets (ANTHROPIC_API_KEY, MISTRAL_API_KEY)
- Slightly higher latency (1.8s Sonnet vs 0.9s GPT-4o-mini) - acceptable
- Complexity classifier requires tuning

---

## Implementation

### Sprint 1: Anthropic Integration
- [x] ADR written
- [ ] Add `anthropic` SDK to requirements.txt
- [ ] Add `ANTHROPIC_API_KEY` to secrets management
- [ ] Create `ModelRouter` service with Claude adapter
- [ ] Implement `classify_query_complexity()` 
- [ ] Add feature flag: `coach.model_routing` (off/shadow/sonnet)
- [ ] Unit tests for classifier
- [ ] Integration test: Sonnet responds correctly

### Sprint 2: Opus Tiering
- [ ] Implement `should_use_opus()` with all gates
- [ ] Add `VIP_ATHLETES` feature flag
- [ ] Add Opus token tracking (Redis or DB)
- [ ] Per-user and global budget caps
- [ ] Integration test: VIP gets Opus for complex query
- [ ] Integration test: Budget cap triggers Sonnet fallback

### Sprint 3: Rate Limit Resilience
- [ ] Add `mistralai` SDK
- [ ] Implement fallback handler (Anthropic 429 → Mistral)
- [ ] Integration test: Fallback delivers response

### Sprint 4: Cost Optimization
- [ ] Implement prompt caching (if Anthropic supports)
- [ ] A/B test: GPT-5 Mini on LOW complexity queries
- [ ] Telemetry dashboard for model usage

---

## Audit Logging

Every Coach query logs:
- `athlete_id`, `athlete_tier`
- `query_complexity` (LOW/MEDIUM/HIGH)
- `model_selected`, `model_actually_used`
- `opus_gate_results` (which gates passed/failed)
- `fallback_triggered`, `fallback_reason`
- `tokens_in`, `tokens_out`, `latency_ms`
- `opus_spend_month_cents`, `athlete_opus_queries_month`

**Never log:** Full prompt/response content (contains health data)

---

## Feature Flag Approach

**Flag:** `coach.model_routing`

| Value | Behavior |
|-------|----------|
| `off` | Use GPT-4o-mini (current behavior) |
| `shadow` | Generate both, log comparison, serve GPT response |
| `sonnet` | Production: Sonnet default, complexity routing |

**Rollout:**
1. `off` → `shadow` for owner only (verify no errors)
2. `shadow` for 48h with beta testers (verify quality)
3. `sonnet` for all users

---

## Security Considerations

- Secrets follow rotation policy (docs/SECURITY_SECRETS.md)
- No athlete data in logs (prompt/response content)
- VIP_ATHLETES set not exposed in client code
- Model parameter validated against allowlist
- Impersonated sessions log `impersonated_by`
- Budget tracking prevents runaway costs

---

## Rationale (N=1 Philosophy)

GPT-4o-mini's poor reasoning **breaks the core trust contract**. When an athlete asks about returning from injury and gets confident but wrong advice, we lose them forever.

Claude models:
- Respect uncertainty
- Reason correctly on physiology
- Say "I don't have enough data" instead of hallucinating

**This is a quality imperative, not a cost optimization.**
