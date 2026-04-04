# Coach Model Routing Reset Spec

**Date:** March 11, 2026  
**Status:** Proposed for tech review  
**Owner:** Michael Shaffer  
**Purpose:** Remove `Opus` from live runtime use, promote `Sonnet 4.6` to the premium Anthropic lane, repair `Gemini` tool-call reliability, and keep premium access capped for non-founders.

---

## Why This Spec Exists

The current coach/runtime model setup is no longer justified.

We now know:

1. `Opus` is too expensive for the role it is playing.
2. The founder does **not** want `Opus` in live runtime use.
3. `Sonnet` is strong enough to take the premium Anthropic lane.
4. `Gemini` is currently unreliable in coach chat because the tool-call integration path is broken (`thought_signature` failures), not because it was fairly disqualified on quality.
5. No more live eval spend should happen until:
   - `Opus` is removed from runtime use
   - `Gemini` is repaired

This spec resets routing around those facts.

---

## Decisions

### Decision 1 — Remove `Opus` from live runtime use

`claude-opus-4-6` must no longer be used in production runtime paths.

That means:

- no coach chat runtime use
- no home briefing runtime use
- no automatic fallback to `Opus`

`Opus` may remain in:

- historical docs
- old artifacts
- regression fixtures where needed for clarity

But it is out of live runtime behavior.

### Decision 2 — `Sonnet 4.6` becomes the premium Anthropic lane

`claude-sonnet-4-6` replaces `claude-opus-4-6` anywhere runtime currently expects premium Anthropic behavior.

This includes:

- high-stakes/premium coach reasoning path
- Anthropic home briefing path
- Anthropic fallback paths currently wired to Opus

### Decision 3 — `Gemini` remains default lane, but must be repaired

`Gemini` remains the standard/default lane.

But current coach chat reliability is broken by tool-call handling (`thought_signature` INVALID_ARGUMENT class), so the lane is not trustworthy.

This spec therefore requires:

- fix the Gemini tool-call reliability bug
- keep Gemini as the default lane
- do **not** run new large evals before fix completion

### Decision 4 — Non-founder premium access stays capped

Premium access remains available to non-founders, but under hard limits.

Important:

- cap applies to the **premium Anthropic lane**, not only historical `Opus` semantics
- otherwise cost simply migrates from Opus to Sonnet

Founder access remains uncapped unless explicitly changed later.

---

## Confirmed Live Runtime Touchpoints

Minimum runtime paths in scope:

1. `apps/api/services/ai_coach.py`
- `MODEL_HIGH_STAKES = "claude-opus-4-6"`
- high-stakes routing + budget/fallback branches

2. `apps/api/routers/home.py`
- `_call_opus_briefing_sync()` hardcodes `model="claude-opus-4-6"`

3. `apps/api/tasks/home_briefing_tasks.py`
- Opus-first dispatch ordering
- `source_model` labels tied to Opus

If tech review finds another live Opus runtime path, include it in this same change.

Implementation note for this pass:

- function names may remain `*_opus_*` to avoid broad import/test churn.
- runtime model IDs and behavior must still switch to Sonnet.

---

## Objectives

1. Remove Opus from all live runtime use
2. Make Sonnet 4.6 the premium Anthropic model
3. Repair Gemini tool-call reliability in coach chat
4. Preserve non-founder premium cost controls

---

## Scope

### Part A — Replace live Opus runtime usage with Sonnet 4.6

Update model selection and direct provider calls so premium Anthropic routing uses `claude-sonnet-4-6`.

Includes:

- coach high-stakes path
- Anthropic fallback path
- home briefing Anthropic generation path
- any source-model metadata emitted by those paths

### Part B — Reframe premium caps to lane semantics

Current cap logic and counters are Opus-named.

Minimum requirement:

- non-founder premium usage remains capped after Sonnet promotion

Preferred requirement:

- code comments / return reasons / docs clearly state these controls now meter the premium Anthropic lane

Important boundary:

- **No DB migration required in this reset.**
- Existing `CoachUsage` fields may remain `opus_*` in this pass if behavior is unambiguous.

### Part C — Fix Gemini coach tool-call reliability

Observed live failure class:

- repeated `400 INVALID_ARGUMENT`
- message: missing `thought_signature` in functionCall parts
- degraded athlete-facing output ("Coach is temporarily unavailable")

Required result:

- tool calls complete successfully on normal valid prompts
- this error class is removed from normal chat path
- default lane is reliable enough for continued production use

Code-path requirement (`apps/api/services/ai_coach.py`):

1. Preserve Gemini function-call context across turns without stripping provider metadata from function-call parts.
2. Pass function responses in provider-expected shape.
3. Multi-turn tool loop must complete without `INVALID_ARGUMENT` thought-signature failures.
4. Errors must remain diagnosable (`error_detail`) without silent healthy-path degradation.

Allowed implementation choice:

- keep `gemini-3-flash-preview` if reliability is fixed, or
- move default to a stable Gemini tool-calling model if required for reliability (document exact model ID).

### Part D — No new eval before reset is complete

Do not run new expensive evals before:

1. Opus removed from runtime
2. Sonnet promoted in runtime
3. Gemini tool reliability repaired

After that, only a small follow-up eval is allowed if still needed.

---

## Non-Goals

This spec does **not** include:

- dashboard/UI work for model usage
- generic whole-platform routing rewrite
- broad observability platform work
- new benchmark platform
- further Opus-vs-others eval rounds before repair
- promoting Gemini to premium lane

---

## Policy Intent

Steady state after this work:

- `Gemini`: standard/default lane
- `Sonnet 4.6`: premium/high-stakes Anthropic lane
- `Opus`: not used in live runtime

Premium lane remains:

- founder-accessible
- capped for non-founders

---

## Technical Requirements

### 1) Model string verification

Before merging routing changes:

- verify `claude-sonnet-4-6` with a real provider call in runtime path

No bulk string swaps without live verification.

### 2) Fallback behavior

After merge:

- no fallback path routes to Opus
- fallback resolves only among:
  - Sonnet
  - Gemini
  - deterministic degraded messaging (path-specific)

### 3) Premium cap behavior

Minimum:

- request-count cap for non-founders
- token/spend-aware cap for non-founders

Preferred:

- founder bypass preserved
- clean fallback when premium cap is hit

### 4) Gemini fix quality bar

Gemini is considered fixed only if:

- thought-signature INVALID_ARGUMENT class is gone on normal prompts
- tool-using prompts complete successfully
- athlete does not receive temporary-unavailable response from this bug class

Minimum smoke set for sign-off (real runtime path):

- 3 tool-using prompts through `AICoach.chat()`/`query_gemini()`
- each run executes at least one tool call
- zero thought-signature INVALID_ARGUMENT failures

---

## Suggested Build Order

1. Verify Sonnet model identifier live
2. Replace live Opus runtime behavior with Sonnet
3. Align premium cap semantics to premium lane
4. Repair Gemini tool-call path
5. Run targeted validation
6. Update docs/audit state

Do not start with new eval work.

---

## Validation

### A) Runtime path verification

- coach premium path uses Sonnet, not Opus
- home briefing Anthropic path uses Sonnet, not Opus
- no fallback path silently routes to Opus

### B) Limit verification

- founder still receives premium access
- non-founder premium usage is capped
- cap-hit fallback is clean and deterministic

### C) Gemini verification

Use a tiny smoke set after the fix:

- 2-3 real tool-using prompts
- stop immediately if same provider/tool error repeats

This is smoke validation, not another expensive benchmark.

### D) Regression tests

Targeted tests for:

- model routing
- fallback logic
- cap behavior
- Gemini tool-call loop

CI must be green.

---

## Acceptance Criteria

Complete only if all are true:

1. Opus removed from all live runtime paths
2. Sonnet 4.6 is live premium Anthropic model
3. Non-founder premium access remains capped
4. Gemini tool-call reliability bug is fixed
5. No fallback depends on Opus
6. No new expensive eval required for reset completion
7. Runtime validation + CI pass

---

## Deliverable Expected From Builder

Builder handoff must include:

1. exact files changed
2. exact runtime model strings after change
3. proof no runtime Opus path remains
4. proof premium cap behavior still works for non-founders
5. proof Gemini thought-signature failure class is fixed
   - include 2-3 successful tool-using prompt runs
   - include exact Gemini model string used
6. targeted test output
7. CI URL and status

---

## Final Note

This is a routing reset, not a model-debate round.

Decision frame is fixed:

- Opus out
- Sonnet in
- Gemini repaired

Tech review focus: scope correctness, implementation safety, and verification quality.
# Coach Model Routing Reset Spec

**Date:** March 11, 2026  
**Status:** Proposed for tech review  
**Owner:** Michael Shaffer  
**Purpose:** Remove `Opus` from live runtime use, promote `Sonnet 4.6` to the premium Anthropic lane, repair `Gemini` tool-call reliability, and keep premium access capped for non-founders.

---

## Why This Spec Exists

The current coach/runtime model setup is no longer justified.

We now know:

1. `Opus` is too expensive for the role it is playing.
2. The founder does **not** want to keep `Opus` in live runtime use.
3. `Sonnet` is strong enough to take the premium Anthropic lane.
4. `Gemini` is currently unreliable in the coach path because the tool-call wiring is broken, not because the model has been fairly disqualified on quality.
5. No more live eval money should be spent until:
   - `Opus` is removed from runtime use
   - `Gemini` is repaired

This spec resets the routing architecture around those facts.

---

## Decisions

### Decision 1 — Remove `Opus` from live runtime use

`claude-opus-4-6` should no longer be used in production runtime paths.

That means:

- no coach chat runtime use
- no home briefing runtime use
- no automatic fallback to `Opus`

`Opus` may remain in:

- historical docs
- test fixtures where needed for regression clarity
- old artifacts

But it should be removed from live runtime behavior.

### Decision 2 — `Sonnet 4.6` becomes the premium Anthropic lane

`claude-sonnet-4-6` replaces `claude-opus-4-6` anywhere the live runtime currently expects the premium Anthropic model.

This includes:

- premium/high-stakes coach reasoning
- home briefing Anthropic path
- any direct Anthropic runtime fallback currently using `Opus`

### Decision 3 — `Gemini` remains the standard/default lane, but must be fixed

`Gemini` is still the default/standard path conceptually.

But the current coach wiring is broken by tool-call handling (`thought_signature` failure), so it is not a reliable runtime lane right now.

This spec therefore requires:

- fix the tool-call reliability bug
- keep `Gemini` in the standard/default role
- do **not** re-run large model evals before the fix is complete

### Decision 4 — Non-founder premium access stays capped

Premium access should remain available to non-founders, but under hard limits.

Important:

- the cap must apply to the **premium lane**, not just the old `Opus` lane
- otherwise cost simply migrates from `Opus` to `Sonnet`

Founder access remains uncapped unless Michael chooses otherwise later.

---

## Confirmed Live Runtime Touchpoints

The currently identified live `Opus` runtime touchpoints are:

1. `apps/api/services/ai_coach.py`
- `MODEL_HIGH_STAKES = "claude-opus-4-6"`
- premium coach routing
- Anthropic fallback path

2. `apps/api/routers/home.py`
- direct Anthropic home briefing call uses `claude-opus-4-6`

3. `apps/api/tasks/home_briefing_tasks.py`
- source-model labeling and Anthropic-first briefing behavior assume `Opus`

These are the minimum production paths this spec covers.

If tech review finds another live runtime `Opus` path, it should be included in this same change rather than deferred.

---

## Objectives

This change should achieve four things:

1. Remove `Opus` from all live runtime use
2. Make `Sonnet 4.6` the premium Anthropic model everywhere `Opus` was previously used
3. Repair `Gemini` coach tooling so the default lane is actually reliable
4. Preserve cost control by keeping hard non-founder premium limits

---

## Scope

### Part A — Replace live `Opus` runtime usage with `Sonnet 4.6`

Update live runtime model selection and direct provider calls so premium Anthropic routing uses `claude-sonnet-4-6`.

This includes:

- coach high-stakes/premium path
- Anthropic fallback path
- home briefing Anthropic generation path
- any source-model metadata written for these paths

### Part B — Reframe limits around the premium lane

Current naming and counters are `Opus`-centric.

That no longer matches the product decision.

The implementation should therefore move toward premium-lane semantics for non-founder limits.

Minimum requirement:

- non-founder premium usage remains capped

Preferred implementation:

- rename or clearly reinterpret the relevant limit logic so it is about the premium Anthropic lane rather than `Opus` specifically

The founder should not need to mentally translate:

- "Opus limit" meaning "Sonnet limit"

If full renaming is too invasive for the first pass, code comments and return reasons must still make the behavior unambiguous.

### Part C — Fix `Gemini` coach tool-call reliability

The current eval failure was provider/runtime integration failure:

- repeated `thought_signature` errors
- no useful output
- athlete-facing degradation to generic unavailability

This spec requires repairing the coach `Gemini` tool-call path so that:

- tool calls execute successfully
- valid prompts do not fail on provider argument errors
- the default lane becomes trustworthy enough for continued production use

This is not optional. The routing reset is incomplete if `Sonnet` goes live while the default lane stays structurally broken.

### Part D — No new eval until after the above is complete

Do not spend more live-eval money before:

1. `Opus` is gone from runtime
2. `Sonnet` is in place
3. `Gemini` is fixed

After those are complete, a much smaller and cheaper follow-up eval may be run if still needed.

---

## Non-Goals

This spec does **not** include:

- any dashboard or admin UI for model usage
- a generic all-product model router rewrite
- broader LLM observability beyond what is required for this routing reset
- a new benchmark platform
- further `Opus` evaluation
- expanding `Gemini` upward into the premium lane before reliability is fixed

---

## Product/Policy Intent

The intended steady-state after this work is:

- `Gemini`: standard/default lane
- `Sonnet 4.6`: premium/high-stakes Anthropic lane
- `Opus`: not used in live runtime

The premium lane should remain:

- available to founder
- capped for non-founders

This preserves quality where needed without allowing premium costs to run loose.

---

## Technical Requirements

### 1. Model identifier verification

Before changing live routing:

- verify `claude-sonnet-4-6` with a real provider call

Do not repeat the earlier failure mode where model strings were batch-swapped without confirming they worked.

### 2. Fallback behavior

After this change:

- fallback paths must not route back to `Opus`
- fallback behavior should resolve between:
  - `Gemini`
  - `Sonnet`
  - deterministic failure messaging

depending on the path and what is available

### 3. Premium cap behavior

The cap should protect against runaway non-founder premium usage.

At minimum:

- request count limit
- token or spend-aware limit

Preferred:

- preserve founder bypass
- preserve a clean fallback when cap is hit

### 4. Gemini fix quality bar

`Gemini` is considered fixed only if:

- the current `thought_signature` tool-call failure is gone
- real tool-using coach prompts complete successfully
- the athlete does not receive `"Coach is temporarily unavailable"` for normal valid prompts caused by this bug class

---

## Suggested Build Order

1. Verify live `Sonnet 4.6` identifier
2. Replace live runtime `Opus` references with `Sonnet`
3. Rework premium limit semantics for non-founders
4. Fix `Gemini` tool-call reliability
5. Run targeted validation
6. Update docs/audit state

Do not start with a new evaluation harness. The routing fix comes first.

---

## Validation

Validation should include:

### A. Runtime path verification

- coach premium path uses `Sonnet`, not `Opus`
- home briefing Anthropic path uses `Sonnet`, not `Opus`
- no fallback path silently routes to `Opus`

### B. Limit verification

- founder still gets premium access
- non-founder premium usage is capped
- cap hit falls back cleanly to the standard lane or defined degraded behavior

### C. Gemini verification

Use a very small prompt set only after the fix:

- `2-3` real tool-using prompts max
- stop immediately if the same provider/tool error repeats

This is a smoke check, not another full expensive eval.

### D. Regression tests

Targeted tests for:

- model routing
- fallback logic
- cap behavior
- Gemini tool-call path

CI must be green.

---

## Acceptance Criteria

This spec is complete only if all are true:

1. `Opus` is removed from all live runtime paths
2. `Sonnet 4.6` is the live premium Anthropic model
3. Non-founder premium access is still capped
4. `Gemini` coach tool-call reliability bug is fixed
5. Fallback paths no longer depend on `Opus`
6. No new expensive eval was required to complete the routing reset
7. Runtime validation and CI both pass

---

## Deliverable Expected From Builder

The builder handoff should include:

1. exact files changed
2. exact model strings now live in runtime
3. proof that no runtime `Opus` path remains
4. proof that non-founder premium caps still work
5. proof that the `Gemini` thought-signature failure is fixed
6. targeted test output
7. CI URL and status

---

## Final Note

This is intentionally a decisive reset, not an experiment matrix.

The decision has already been made:

- `Opus` out
- `Sonnet` in
- `Gemini` repaired

Tech review should focus on whether the scope is correct and whether the implementation order is safe, not on reopening the model-choice debate.
