# Kimi Adoption Spec — kimi-k2-turbo-preview

**Date:** 2026-03-17  
**Status:** Builder-ready  
**Owner:** Technical advisor -> Builder  
**Goal:** Evaluate and safely adopt `kimi-k2-turbo-preview` for selected Sonnet paths without trust regression.

**Model decision (final):** `kimi-k2-turbo-preview` for all three call sites — briefing, coach, knowledge extraction.  
**Rationale:** All LLM calls in StrideIQ are narrative generation against structured engine output. The correlation engine does the analysis. The LLM writes human language around it. That is a generation task, not a reasoning task. `kimi-k2-turbo-preview` runs at 60-100 tok/s (~800ms), supports `response_format: json_object` natively, and has configurable temperature. `kimi-k2.5` is a reasoning model with locked sampling params — inappropriate for real-time structured generation.

---

## 1) Why this rescope exists

Full production "shadow mode" (dual-calling every request for 7 days) is not the right default for current StrideIQ infra and workflow.

This spec replaces heavy shadowing with a practical sequence:

1. Credential readiness gate  
2. Privacy/legal gate  
3. Offline replay comparison on real prompts  
4. Founder-only live canary  
5. Small allowlist ramp (optional)

No athlete-facing rollout until gates pass.

---

## 2) Non-negotiables

1. Zero tolerance for hallucinated athlete facts on coach/briefing.
2. No regression in briefing JSON compliance.
3. No ambiguous data-residency/privacy posture.
4. Fallback-first operation at all times.
5. Cost savings do not override quality/safety failures.

---

## 3) Gate -1: Credential Readiness (required before coding)

Kimi keys are currently not configured in local or production runtime.

Required:

1. Provision provider key:
   - `KIMI_API_KEY`
   - `KIMI_BASE_URL=https://api.moonshot.cn/v1`
2. Inject secrets into runtime:
   - API container/runtime
   - Worker container/runtime
3. Add local dev secret wiring (no plaintext secrets in repo).
4. Run smoke test from API runtime and worker runtime:
   - simple non-athlete prompt response success
   - log latency + token usage if available
5. Evidence in handoff:
   - presence booleans only (no key values),
   - smoke-test success output (redacted).

If Gate -1 fails, stop.

---

## 4) Gate 0: Privacy / data residency approval

Because prompts include athlete health/training context (sleep, HRV, soreness, pain/injury language),
Moonshot usage must be explicitly approved.

Required:

1. Written vendor policy review:
   - retention,
   - training-on-customer-data policy,
   - residency/processing region,
   - deletion controls.
2. Internal sign-off (founder/security/legal decision owner).
3. Written go/no-go result.

If not approved, stop at offline comparison only.

---

## 5) Current Sonnet usage map (actual codebase)

1. Coach high-stakes lane:
   - `apps/api/services/ai_coach.py`
2. Morning briefing:
   - `apps/api/routers/home.py`
   - `apps/api/tasks/home_briefing_tasks.py`
3. Knowledge extraction:
   - `apps/api/services/knowledge_extraction_ai.py`

Notes:
- Coach default is Gemini Flash; Sonnet is not the dominant volume path.
- Briefing is highest-volume Sonnet consumer and highest JSON-structure risk.

---

## 6) Technical design (required)

## 6.1 Shared abstraction

Create:
- `apps/api/core/llm_client.py`

Must support:
- provider routing by model family,
- text + strict JSON response modes,
- normalized response object (`text`, `model`, tokens, latency, finish reason),
- timeout/retry policy,
- unified error taxonomy,
- explicit fallback chain.

## 6.2 Provider adapters

Implement adapters behind abstraction:
- Anthropic (existing Sonnet path)
- Kimi via OpenAI-compatible client
- Gemini (existing)

## 6.3 Fallback chain

For any Kimi-selected call:

1. Primary: `kimi-k2-turbo-preview`
2. Fallback 1: `claude-sonnet-4-6` (if configured)
3. Fallback 2: existing Gemini fallback path

Never hard-fail athlete request solely because Kimi failed.

## 6.4 Coach tool-call parity requirement

Coach is not plain completion. Must preserve tool behavior parity:
- tool selection,
- arg schema correctness,
- multi-step tool loops,
- tool error handling,
- timeout behavior.

No live canary if tool-call contract tests fail.

---

## 7) Evaluation plan (rescoped)

## Phase 1 - Offline replay comparison (required)

Build script:
- `scripts/compare_kimi_vs_sonnet.py`

Replay with real captured prompt/context snapshots:
- Coach: 10 representative prompts (high-stakes + normal)
- Briefing: 5 real context snapshots
- Knowledge extraction: 3 representative docs

Output artifacts:
- side-by-side outputs,
- latency/tokens/cost table,
- scoring sheet.

### Phase 1 pass criteria

1. Average quality score >= 4.2
2. No case score < 3
3. Hallucinated athlete facts = 0
4. Briefing JSON valid parse >= 99%
5. Coach tool-call contract tests pass 100% on required scenarios

If any fail, stop.

---

## Phase 2 - Founder-only live canary (no broad shadow)

Duration:
- 48 to 72 hours minimum

Scope:
- founder account only, explicit canary toggle
- no general athlete exposure

Required runtime controls:
- `KIMI_CANARY_ENABLED`
- `KIMI_CANARY_ATHLETE_IDS`
- immediate kill switch env toggle

### Phase 2 pass criteria

1. Hallucination incidents = 0
2. Briefing JSON parse success >= 99.5%
3. p95 latency <= 1.5x Sonnet baseline
4. No increase in user-visible failures/timeouts
5. Founder subjective quality: "equal or better"

If any fail, revert to Sonnet immediately and stop.

---

## Phase 3 - Small allowlist rollout (optional)

Only after Phase 2 pass.

Rollout:
1. Small allowlist (non-critical users)
2. 24h checkpoint
3. Expand gradually if clean

Rollback triggers:
- any hallucinated athlete fact,
- parse compliance breach,
- quality trust regression,
- provider instability.

---

## 8) Cost/accounting expectations

Expected directional savings remain meaningful but not primary decision driver at current volume.
Use measured canary metrics for final decision.

Required report:
- baseline Sonnet cost/latency,
- Kimi canary cost/latency,
- net savings estimate at current and 10x traffic.

---

## 9) Files impacted

| File | Change |
|------|--------|
| `apps/api/core/llm_client.py` | new abstraction |
| `apps/api/services/ai_coach.py` | route through abstraction + canary gating + tool parity handling |
| `apps/api/routers/home.py` | briefing route through abstraction + canary gating |
| `apps/api/tasks/home_briefing_tasks.py` | briefing model selection and telemetry |
| `apps/api/services/knowledge_extraction_ai.py` | route through abstraction |
| `scripts/compare_kimi_vs_sonnet.py` | offline replay comparator |
| `requirements.txt` | verify/add `openai` dependency |
| env/deploy config | Kimi keys, canary toggles, fallback controls |

---

## 10) Builder acceptance checklist

Builder must deliver:

1. Files changed (exact list)
2. Test output pasted
3. Offline replay comparison report attached
4. Founder canary metrics (latency, parse compliance, failures)
5. Explicit go/no-go recommendation
6. Known risks remaining

---

## 11) Explicit no-go conditions

Do not proceed beyond current phase if any occur:

1. Missing credentials (Gate -1 fail)
2. No privacy/residency approval (Gate 0 fail)
3. Any hallucinated athlete fact in eval/canary
4. Briefing JSON compliance below threshold
5. Coach tool-call contract failures
6. Founder quality veto

# Kimi K2.5 vs Sonnet 4.6 - Production Readiness Spec (Hardened)

**Date:** 2026-03-17  
**Status:** Proposed (hardened for technical review)  
**Owner:** Technical Advisor + Builder  
**Goal:** Determine if Kimi K2.5 can replace Sonnet 4.6 at selected call sites with zero trust regression.

---

## 1) Executive Summary

This is **not** a model-name swap.

Sonnet paths currently use Anthropic request/response + tool-calling behavior assumptions.
Kimi K2.5 uses an OpenAI-compatible API surface and requires request, response, timeout, retry,
and tool-call behavior parity verification.

The migration is allowed only if all quality, safety, compliance, and reliability gates pass.

---

## 2) Current Sonnet Usage Map

| # | Service | File | Purpose | Relative Volume | Risk |
|---|---------|------|---------|-----------------|------|
| 1 | AI Coach high-stakes lane | `apps/api/services/ai_coach.py` | injury/pain/load/high-complexity/founder-VIP responses | Medium | Critical |
| 2 | Morning Briefing | `apps/api/routers/home.py`, `apps/api/tasks/home_briefing_tasks.py` | morning voice + structured fields | Highest | Critical |
| 3 | Knowledge Extraction | `apps/api/services/knowledge_extraction_ai.py` | extraction workflows | Low | Medium |

Notes:
- Coach default remains Gemini Flash; Sonnet is routed for higher-stakes paths.
- Briefing is the highest-volume Sonnet consumer.

---

## 3) Non-Negotiable Constraints

1. **No athlete-facing regression** in factuality, tone trust, or structured output compliance.
2. **Zero tolerance for hallucinated athlete facts** on coach and briefing surfaces.
3. **No privacy/compliance ambiguity** before any production shadowing.
4. **No uncontrolled fan-out** (cost/latency spike) during comparison runs.
5. **Fallback-first architecture**: failure always degrades to current known-safe path.

---

## 4) Mandatory Gate 0: Privacy, Residency, and Compliance (Before Any Shadow)

Because prompts include sensitive athlete health/training context (sleep, HRV, soreness, injury signals),
this gate must pass before Phase 2.

Required deliverables:

1. Vendor policy review memo:
   - data retention,
   - training-on-customer-data policy,
   - regional processing/residency statements,
   - deletion controls.
2. Internal data classification sign-off (security/privacy owner).
3. Explicit go/no-go decision logged in writing.

If Gate 0 is not approved, the project stops at offline evaluation only.

---

## 5) Technical Design Requirements

## 5.1 LLM Client Abstraction (Required)

Create shared abstraction:
- `apps/api/core/llm_client.py`

Must support:
- text responses,
- strict JSON responses,
- tool-call capable flows,
- normalized token/latency accounting,
- timeout/retry policy,
- provider fallback chain,
- consistent error taxonomy.

Suggested interface:

```python
class LLMResponse(TypedDict):
    text: str
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    finish_reason: str | None
    raw: dict | None

def call_llm(
    *,
    model: str,
    system: str,
    messages: list[dict],
    max_tokens: int,
    temperature: float,
    response_mode: Literal["text", "json"],
    tools: list[dict] | None = None,
    timeout_s: int = 45,
) -> LLMResponse:
    ...
```

Routing:
- `claude-*` -> Anthropic adapter
- `kimi-*` -> OpenAI-compatible adapter (Moonshot base URL)
- `gemini-*` -> existing Gemini adapter

## 5.2 Tool-Calling Parity (Required for Coach)

`ai_coach.py` relies on tool orchestration semantics, not just plain text completion.
Parity checks must explicitly verify:
- tool selection correctness,
- argument schema adherence,
- multi-step tool loop completion,
- malformed tool-call recovery behavior,
- timeout handling with fallback.

No production swap if tool parity fails.

---

## 6) Phased Evaluation Plan

## Phase 1: Offline Comparison (No Production Impact)

Build script:
- `scripts/compare_kimi_vs_sonnet.py`

Run matched prompts with full realistic context (not synthetic minimal prompts):
- Coach: 10 prompts across high-stakes and normal intents.
- Briefing: 5 real briefing contexts with expected JSON schema.
- Knowledge extraction: 3 representative documents.

Artifacts:
- side-by-side outputs,
- per-case latency/tokens/cost,
- scorer sheet.

### Phase 1 Scoring Rubric

Score each response 1-5 on:
- factual accuracy against known context,
- specificity to athlete data,
- safety and contract adherence,
- tone quality,
- brevity appropriateness,
- JSON validity (briefing only).

Pass thresholds:
- average >= 4.2,
- no score < 3,
- hallucination count = 0 on athlete facts,
- briefing JSON valid parse >= 99%.

If any threshold fails, stop.

---

## Phase 1B: Tool-Call Contract Tests (Coach)

Required test set for `ai_coach.py` flows:
- high-stakes query with mandatory tools,
- multi-tool sequence,
- tool error injection fallback,
- no-tool shortcut prevention.

Pass thresholds:
- tool contract pass rate 100% on required cases,
- no uncited-athlete-fact output in test corpus.

If fails, stop.

---

## Phase 2: Shadow Mode (Production, Zero Athlete Impact)

Scope:
- sampled shadow only (do **not** mirror every call).
- recommended sample rates:
  - briefing: 10%
  - coach Sonnet-lane: 10%
  - knowledge extraction: 20% (low volume)

Rules:
- Sonnet remains source-of-truth output shown to users.
- Kimi output is logged only for comparison.
- hard daily cap for shadow requests and tokens.

Required telemetry:
- parse success/failure rates,
- latency p50/p95,
- provider error rates,
- token/cost deltas,
- hallucination audit counts via automated checker + human review sample.

Duration:
- 7 consecutive days minimum.

Abort conditions (immediate kill switch):
- any confirmed hallucinated athlete fact in shadow sample,
- briefing JSON parse success < 99.5%,
- p95 latency > 1.5x Sonnet for 2 consecutive days,
- provider error rate > 2x Sonnet baseline for 2 consecutive days.

---

## Phase 3: Controlled Live Canary (If Phase 2 Passes)

Canary order:
1. Founder-only canary.
2. Small allowlist cohort.
3. Gradual ramp by percentage.

At each stage:
- maintain Sonnet fallback and emergency kill switch.
- require 24h stability checkpoint before ramp.

Roll back immediately on:
- hallucination incident,
- parse-compliance breach,
- user-facing quality regression.

---

## 7) Cost and Performance Accounting

Projected savings remain valid as directional estimate, but decision uses measured shadow data.

Decision minimums:
- confirmed savings >= 50% at observed traffic,
- no breach of quality/safety/SLO gates.

Cost savings alone can never override safety/quality failure.

---

## 8) Environment and Config

Required vars:
- `KIMI_API_KEY`
- `KIMI_BASE_URL=https://api.moonshot.cn/v1`
- `COACH_PRIMARY_MODEL`
- `BRIEFING_PRIMARY_MODEL`
- `KNOWLEDGE_PRIMARY_MODEL`
- `KIMI_SHADOW_ENABLED`
- `KIMI_SHADOW_SAMPLE_RATE_COACH`
- `KIMI_SHADOW_SAMPLE_RATE_BRIEFING`
- `KIMI_SHADOW_DAILY_TOKEN_CAP`

Keep:
- `ANTHROPIC_API_KEY` for fallback.

Dependency:
- verify `openai` package availability and pin compatible version if missing.

---

## 9) Risks and Mitigations (Hardened)

| Risk | Severity | Mitigation |
|------|----------|------------|
| Coach tool-call behavior mismatch | Critical | Phase 1B contract tests, block swap on any fail |
| Hallucinated athlete facts | Critical | zero tolerance, automated + human checks, immediate rollback |
| Briefing JSON compliance drift | Critical | strict parse SLOs, fallback on parse fail |
| Data residency/compliance mismatch | Critical | mandatory Gate 0 approval before shadow |
| Latency regression | High | p95 guardrail and staged canary |
| Shadow cost explosion | Medium | sampling + daily token caps |
| Provider outage | Medium | fallback chain + kill switch |

---

## 10) Go/No-Go Criteria

Go only if **all** are true:
1. Gate 0 privacy/compliance approved in writing.
2. Phase 1 thresholds all pass.
3. Phase 1B tool-contract tests all pass.
4. Phase 2 7-day shadow passes all SLO/quality gates.
5. Founder subjective quality check passes ("feels equal or better").
6. Savings >= 50% at measured traffic.

No-go if **any** fail.

---

## 11) Implementation Order

1. Gate 0 privacy/compliance review.
2. Build `core/llm_client.py` abstraction + adapters.
3. Build offline comparison harness.
4. Run Phase 1 + Phase 1B and review.
5. Implement sampled shadow mode instrumentation.
6. Run 7-day shadow and evaluate.
7. If pass, run staged canary with rollback controls.

---

## 12) Files Impacted

| File | Change |
|------|--------|
| `apps/api/core/llm_client.py` | new abstraction |
| `apps/api/services/ai_coach.py` | integrate abstraction + tool parity + shadow hook |
| `apps/api/routers/home.py` | briefing path abstraction + shadow hook |
| `apps/api/tasks/home_briefing_tasks.py` | wiring + telemetry |
| `apps/api/services/knowledge_extraction_ai.py` | abstraction integration |
| `scripts/compare_kimi_vs_sonnet.py` | offline evaluator |
| `requirements.txt` | verify/add `openai` dependency |
| env/deploy config | Kimi + shadow vars |

---

## 13) Required Delivery Evidence (Builder Output)

Builder must include in final handoff:

1. exact files changed,
2. test output (paste),
3. shadow metrics report template and sample output,
4. go/no-go checklist with pass/fail marks,
5. known risks remaining.

# Kimi K2.5 vs Sonnet 4.6 — Comparison Test Spec

**Date:** March 17, 2026
**Status:** Proposed — for technical reviewer
**Goal:** Determine if Kimi K2.5 can fully replace Sonnet 4.6 across all LLM call sites without quality degradation
**Motivation:** ~70% cost reduction ($0.50/M input vs $3/M, $2.50/M output vs $15/M)

---

## Current Sonnet 4.6 Usage Map

| # | Service | File | Purpose | Call Volume |
|---|---------|------|---------|-------------|
| 1 | **AI Coach** | `services/ai_coach.py` | High-stakes chat (injury, pain, load, VIP, founder) | Per-query, routed |
| 2 | **Morning Briefing** | `routers/home.py` + `tasks/home_briefing_tasks.py` | Morning voice, coach_noticed, week/race assessment | Daily per athlete |
| 3 | **Knowledge Extraction** | `services/knowledge_extraction_ai.py` | RPI formulas, pace tables, book principles | On-demand, rare |

### Model routing today

- **Coach:** Gemini Flash is the default. Sonnet 4.6 is used for: founder account, VIP athletes, high-stakes queries (injury/pain/load keywords), high-complexity queries with paid subscription. Controlled by `COACH_MODEL_ROUTING` and `COACH_HIGH_STAKES_ROUTING` env vars.
- **Briefing:** Sonnet 4.6 first, Gemini Flash fallback. Every daily briefing attempts Sonnet.
- **Knowledge extraction:** Uses older `claude-3-5-sonnet-20241022`, falls back to GPT-4 Turbo.

### API format difference

Current code uses the **Anthropic SDK** (`anthropic` Python package):
```python
from anthropic import Anthropic
client = Anthropic(api_key=key)
response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=...,
    system=...,
    messages=[...]
)
text = response.content[0].text
```

Kimi K2.5 uses the **OpenAI-compatible API** (`openai` Python package):
```python
from openai import OpenAI
client = OpenAI(api_key=key, base_url="https://api.moonshot.cn/v1")
response = client.chat.completions.create(
    model="kimi-k2.5",
    messages=[{"role": "system", "content": ...}, {"role": "user", "content": ...}]
)
text = response.choices[0].message.content
```

This is NOT a drop-in model name swap. The SDK, request format, and response parsing are all different.

---

## Comparison Test Design

### Phase 1: Offline Quality Comparison (no production impact)

Build a standalone comparison script that runs the same prompts through both models and produces side-by-side output for human evaluation.

#### Test Set: Coach Responses (10 prompts)

Use real production prompts from the founder's coach history. Pull 10 diverse queries:

| # | Category | Example Query Type |
|---|----------|--------------------|
| 1 | High-stakes: injury | "My knee has been hurting after long runs" |
| 2 | High-stakes: pain | "I'm experiencing shin pain, should I run today?" |
| 3 | Training load | "Am I overtraining? My form has been dropping" |
| 4 | Race prep | "I have a marathon in 3 days, what should I do?" |
| 5 | Recovery | "How should I recover after yesterday's 20-miler?" |
| 6 | Nutrition | "What should I eat the night before my race?" |
| 7 | Fingerprint-referencing | "What does my data say about sleep and performance?" |
| 8 | Conversational follow-up | "Tell me more about that" (with prior context) |
| 9 | Ambiguous/short | "Legs feel heavy" |
| 10 | General knowledge | "What's the difference between tempo and threshold?" |

For each prompt, include the FULL system prompt and athlete context that the coach normally sends (fingerprint context, recent activities, facts, etc.). The comparison must test with realistic context, not bare prompts.

#### Test Set: Morning Briefing (5 briefings)

Pull 5 different days of briefing context (the full prompt sent to `_call_opus_briefing_sync`). Run each through both models. Compare:

- `coach_noticed` quality
- `morning_voice` naturalness and specificity
- `week_assessment` accuracy
- `race_assessment` accuracy (if applicable)
- JSON format compliance (the briefing expects structured JSON output)

#### Test Set: Knowledge Extraction (3 documents)

Pull 3 knowledge extraction prompts. Compare extraction accuracy.

#### Comparison Script Structure

```
scripts/compare_kimi_vs_sonnet.py

Usage:
  python scripts/compare_kimi_vs_sonnet.py --test-set coach
  python scripts/compare_kimi_vs_sonnet.py --test-set briefing
  python scripts/compare_kimi_vs_sonnet.py --test-set knowledge

Output:
  results/kimi_comparison_YYYY-MM-DD/
    coach_01_sonnet.txt
    coach_01_kimi.txt
    coach_02_sonnet.txt
    coach_02_kimi.txt
    ...
    briefing_01_sonnet.json
    briefing_01_kimi.json
    ...
    summary.md  (side-by-side with metadata: latency, token counts, cost)
```

#### Quality Rubric (scored by founder, 1-5 per dimension)

**Coach responses:**

| Dimension | What to evaluate |
|-----------|------------------|
| Accuracy | Does it say anything factually wrong about the athlete's data? |
| Specificity | Does it reference the athlete's actual patterns, or give generic advice? |
| Safety | Does it avoid medical claims, avoid overriding athlete decisions? |
| Tone | Does it sound like a knowledgeable peer, not a chatbot? |
| Brevity | Is it concise, or does it over-explain? |
| JSON compliance | (briefing only) Does it return valid JSON with all required fields? |

**Scoring:**
- 5: Indistinguishable from or better than Sonnet
- 4: Slightly worse but acceptable
- 3: Noticeably worse but usable
- 2: Meaningfully worse, would degrade experience
- 1: Unacceptable (hallucination, wrong data, broken format)

**Pass threshold:** Average score >= 4.0 across all dimensions and test cases. No individual score below 3.

---

### Phase 2: Shadow Mode (production, no athlete impact)

If Phase 1 passes, run Kimi K2.5 in shadow alongside Sonnet in production for 7 days:

- Every Sonnet call also fires a Kimi call (async, non-blocking)
- Both responses are logged with latency, token counts, and cost
- Kimi response is NEVER shown to the athlete
- Daily report compares: response length, latency, cost, and any JSON parse failures

#### Implementation approach

Add a shadow call in the coach and briefing paths:

```python
# After Sonnet returns successfully:
if settings.KIMI_SHADOW_ENABLED:
    asyncio.create_task(_shadow_kimi_call(prompt, sonnet_response, context))
```

Shadow results log to a `kimi_shadow_comparison` table or structured log.

#### What to watch for

- **JSON compliance failures:** Does Kimi return valid JSON for briefings? Rate of parse errors.
- **Latency:** Kimi's response time vs Sonnet's. If Kimi is slower, the cost savings may not justify the UX regression.
- **Hallucination rate:** Does Kimi invent data, make up findings, or reference patterns that don't exist in the athlete's fingerprint?
- **Instruction following:** The coach and briefing prompts have strict formatting instructions. Does Kimi follow them as reliably as Sonnet?
- **Context window utilization:** Current prompts can be large (fingerprint + recent activities + facts + conversation history). At 256K context, Kimi has headroom, but quality may degrade with large contexts.

---

### Phase 3: Live Swap (if Phase 1 + 2 pass)

#### Environment variable changes

| Variable | Current | After |
|----------|---------|-------|
| `ANTHROPIC_API_KEY` | Anthropic key | Keep (fallback) |
| `KIMI_API_KEY` | (new) | Moonshot API key |
| `KIMI_BASE_URL` | (new) | `https://api.moonshot.cn/v1` |
| `COACH_PRIMARY_MODEL` | (new) | `kimi-k2.5` or `claude-sonnet-4-6` |
| `BRIEFING_PRIMARY_MODEL` | (new) | `kimi-k2.5` or `claude-sonnet-4-6` |

#### Code changes required

**1. Add a model-agnostic LLM client abstraction**

The current code has Anthropic client calls scattered across 3 files with different patterns. Before swapping, extract a shared interface:

```python
# core/llm_client.py (new)

class LLMResponse:
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: float

def call_llm(
    model: str,           # "claude-sonnet-4-6" or "kimi-k2.5"
    system: str,
    messages: list[dict],
    max_tokens: int = 4096,
    temperature: float = 0.7,
    response_format: str = "text",  # or "json"
) -> LLMResponse:
    """Route to the correct SDK based on model prefix."""
    if model.startswith("claude"):
        return _call_anthropic(model, system, messages, max_tokens, temperature)
    elif model.startswith("kimi"):
        return _call_kimi(model, system, messages, max_tokens, temperature)
    elif model.startswith("gemini"):
        return _call_gemini(model, system, messages, max_tokens, temperature)
    else:
        raise ValueError(f"Unknown model: {model}")
```

This abstraction:
- Makes future model swaps trivial (change one env var)
- Normalizes response format across SDKs
- Centralizes token counting and cost attribution
- Keeps fallback logic in one place

**2. Update the 3 call sites to use the abstraction**

| File | Current | After |
|------|---------|-------|
| `services/ai_coach.py` | `self.anthropic_client.messages.create(...)` | `call_llm(model=self.model, ...)` |
| `routers/home.py` | `client.messages.create(model="claude-sonnet-4-6", ...)` | `call_llm(model=settings.BRIEFING_PRIMARY_MODEL, ...)` |
| `services/knowledge_extraction_ai.py` | `anthropic_client.messages.create(...)` | `call_llm(model=settings.KNOWLEDGE_MODEL, ...)` |

**3. Add `openai` to requirements**

```
openai>=1.30.0,<2.0.0
```

The `openai` package is likely already present (used for knowledge extraction fallback). Verify.

**4. Fallback chain**

```
Primary: Kimi K2.5
  → on failure: Sonnet 4.6 (if ANTHROPIC_API_KEY set)
    → on failure: Gemini Flash (existing fallback)
```

---

## Cost Projection

### Current Sonnet 4.6 spend estimate

| Service | Calls/day | Avg input tokens | Avg output tokens | Daily cost |
|---------|-----------|-----------------|-------------------|------------|
| Briefing | ~10 athletes | ~4,000 | ~800 | ~$0.24 |
| Coach (Sonnet path) | ~20 queries | ~6,000 | ~1,200 | ~$0.72 |
| Knowledge extraction | ~2 | ~3,000 | ~1,500 | ~$0.06 |
| **Total** | | | | **~$1.02/day** |

### Projected Kimi K2.5 spend

| Service | Calls/day | Avg input tokens | Avg output tokens | Daily cost |
|---------|-----------|-----------------|-------------------|------------|
| Briefing | ~10 | ~4,000 | ~800 | ~$0.04 |
| Coach (Kimi path) | ~20 | ~6,000 | ~1,200 | ~$0.12 |
| Knowledge extraction | ~2 | ~3,000 | ~1,500 | ~$0.01 |
| **Total** | | | | **~$0.17/day** |

**Projected monthly savings:** ~$25/month at current scale. Savings grow linearly with athlete count.

*Note: These are rough estimates. Actual numbers depend on prompt lengths, conversation depth, and routing percentages. The shadow mode in Phase 2 will produce exact cost comparisons.*

---

## Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| Quality degradation in coaching responses | High | Phase 1 rubric scoring, Phase 2 shadow comparison |
| JSON parse failures on briefings | High | Phase 2 tracks parse error rate; abort if > 5% |
| Hallucination about athlete data | Critical | Phase 1 tests with real fingerprint context; Phase 2 monitors |
| Latency increase | Medium | Phase 2 measures p50/p95 latency; abort if p95 > 2x Sonnet |
| Kimi API availability/reliability | Medium | Sonnet fallback chain always available; monitor error rate |
| Chinese API provider data residency concerns | Low-Medium | Review Moonshot AI data handling policy; all data is training data (prompts contain athlete health info) |
| 256K context window insufficient | Low | Current largest prompts are ~10-15K tokens; massive headroom |

---

## Decision Criteria

**Swap if ALL of the following are true:**
1. Phase 1 average quality score >= 4.0, no individual score below 3
2. Phase 2 JSON parse error rate < 5%
3. Phase 2 p95 latency within 1.5x of Sonnet
4. Phase 2 hallucination rate = 0 (zero tolerance for invented data)
5. No data residency concerns after policy review
6. Cost savings confirmed at >= 50%

**Do NOT swap if ANY of the following are true:**
- Coach responses feel generic compared to Sonnet (specificity score < 4)
- Briefing JSON compliance < 95%
- Any hallucination about athlete data in Phase 1 or Phase 2
- Founder subjective assessment: "this doesn't feel like my coach"

---

## Implementation Order

1. **Now:** Founder reviews this spec, tech reviewer refines
2. **Day 1:** Build comparison script, pull real prompts from production
3. **Day 2:** Run Phase 1 offline comparison, founder scores
4. **Day 2-3:** If Phase 1 passes, implement shadow mode
5. **Day 3-10:** Phase 2 shadow for 7 days, collect metrics
6. **Day 10:** Review shadow data, make go/no-go decision
7. **Day 11-12:** If go, build LLM client abstraction and swap
8. **Day 12:** Deploy with Sonnet fallback, monitor

Total timeline: ~2 weeks from start to live swap (if quality passes).

---

## Files Impacted

| File | Phase | Change |
|------|-------|--------|
| `scripts/compare_kimi_vs_sonnet.py` | 1 | New: offline comparison script |
| `core/llm_client.py` | 3 | New: model-agnostic LLM abstraction |
| `services/ai_coach.py` | 2-3 | Shadow call (Phase 2), swap to abstraction (Phase 3) |
| `routers/home.py` | 2-3 | Shadow call (Phase 2), swap to abstraction (Phase 3) |
| `tasks/home_briefing_tasks.py` | 2-3 | Shadow call (Phase 2), swap to abstraction (Phase 3) |
| `services/knowledge_extraction_ai.py` | 3 | Swap to abstraction |
| `requirements.txt` | 3 | Add/verify `openai` package |
| `.env` / docker-compose | 3 | Add `KIMI_API_KEY`, `KIMI_BASE_URL`, model selection vars |
