# Quality Proof Gate — Fingerprint Lifecycle Coach Integration

**Purpose:** The Phase 4 tests prove the mechanics work (translation, grouping,
single-emerging cap, TTL expiry, fact promotion). This gate proves the *outcomes*
are good — that the coach produces better, more honest responses with lifecycle
context than without it.

**Gate structure:** Two tiers. Tier 1 is CI-checkable and must pass before
production deploy. Tier 2 is a manual review pass run by the founder before the
feature is considered complete.

---

## Tier 1 — Automated CI Checks (`test_coach_lifecycle_quality.py`)

Deterministic tests using mocked findings. No LLM calls, no cost.
If any fail, the feature does not ship.

### T1-1: No raw field names in coach-facing output

Generate `build_fingerprint_prompt_section` output with findings spanning all
`INPUT_TO_LIMITER_TYPE` keys. Regex scan for any key in `INPUT_TO_LIMITER_TYPE`
that appears as a bare DB field name (underscore-separated lowercase words).
The `_translate()` function must convert every one. Generic fallback
(`field_name.replace("_", " ")`) is acceptable only for keys NOT in the
translation dictionary.

**Pass:** No raw DB field name (e.g., `long_run_ratio`, `daily_session_stress`)
appears in the prompt output. Translated equivalents (e.g., "long runs",
"session intensity") appear instead.

**Fail:** Any `INPUT_TO_LIMITER_TYPE` key appears verbatim in the output.

### T1-2: Closed findings grouped, never individually listed

A fingerprint with multiple closed findings produces a prompt section containing
exactly one closed summary line ("Previously solved: ..."), not individual
`[CLOSED]` entries.

**Pass:** `"Previously solved"` appears once. `"[CLOSED"` does not appear.

**Fail:** Individual `[CLOSED]` entries appear, or multiple closed summary lines.

### T1-3: Single emerging finding per prompt payload

When multiple emerging findings exist, `build_fingerprint_prompt_section` includes
only the single most recently emerged finding. This is a hard payload cap, not
model guidance.

**Pass:** Exactly one `[EMERGING — ask athlete]` line appears in the output,
and it corresponds to the finding with the most recent
`lifecycle_state_updated_at`.

**Fail:** Zero or 2+ emerging finding lines in the output.

### T1-4: No statistical internals in suggestions payload

The dynamic suggestions API output for lifecycle-driven suggestions (source 7)
contains no correlation coefficients, p-values, raw field names, or confidence
scores.

Forbidden patterns: `r=`, `p=`, `long_run_ratio`, `pace_threshold`,
`daily_session_stress`, `atl`, `tsb` (as bare tokens), confidence scores.

**Pass:** All suggestion titles, descriptions, and prompts are clean.

**Fail:** Any forbidden pattern appears.

### T1-5: Resolving attribution surfaced

When a finding is in `resolving` state with a `resolving_context` value, the
formatted finding line includes the attribution text.

**Pass:** `format_finding_line` output for a resolving finding includes
`"— Attribution:"` followed by the resolving context content.

**Fail:** Attribution missing from resolving findings that have context.

### T1-6: Structural traits not framed as fixable

When a finding is in `structural` state, the formatted label is `[STRUCTURAL]`.
The prompt header instructs "adjust delivery, do not try to fix." Structural
findings must never appear with `[ACTIVE]` or `[EMERGING]` labels.

**Pass:** Structural findings are labeled `[STRUCTURAL]`. No structural finding
renders as active or emerging.

**Fail:** Structural finding renders with wrong lifecycle label.

### T1-7: NULL lifecycle state backward compatibility

Findings with `lifecycle_state = None` (pre-Phase-3 data) render with
`times_confirmed`-based tier labels (`STRONG`, `CONFIRMED`, `EMERGING`).
They must not render with lifecycle labels (`CLOSED`, `RESOLVING`, etc.).

**Pass:** Finding with `lifecycle_state=None` and `times_confirmed=8` renders
with `[STRONG 8x]`.

**Fail:** Finding with `lifecycle_state=None` renders with a lifecycle label.

### T1-8: No promotion without athlete fact

An `emerging` finding with no matching `limiter_context` fact stays `emerging`
after `_apply_fact_promotion`.

**Pass:** `_apply_fact_promotion(emerging_finding, "emerging", [])` returns
`"emerging"`.

**Fail:** State changes without a supporting fact.

---

## Tier 2 — Manual Review Pass (Founder)

These require a human to evaluate coach behavior against specific criteria.
Run before production deploy. Founder reviews and signs off.

### Review Protocol

Use three test conversations — one per athlete profile (Michael, Larry, Brian).
For each, run the specified prompt and evaluate the coach response against the
criteria. Record pass/fail with a brief note. All criteria must pass for all
three athletes before the feature ships.

### Test Conversation Set 1 — Emerging Limiter Surfacing

**Setup:** Michael. One emerging finding: threshold work strengthening in L90.

**Prompt to coach:** "How is my training looking?"

| # | Criterion | Pass | Fail |
|---|-----------|------|------|
| MR-1 | Lifecycle question is asked | Coach asks one natural-language question about the emerging pattern | Coach does not mention the pattern, or asks multiple lifecycle questions |
| MR-2 | Curiosity framing | Question feels like curiosity — "I'm noticing..." or "Your data suggests..." | Question feels like a diagnosis, accusation, or alarm |
| MR-3 | No statistical language | Response contains no r=, p=, metric field names, or raw numbers from the correlation | Any statistical internal appears |
| MR-4 | One question only | Exactly one lifecycle-related question in the response | Two or more lifecycle questions asked |
| MR-5 | Question is answerable | An athlete could answer without understanding how the engine works | Question requires understanding of correlation, lifecycle states, or technical concepts |

**Sample pass:** "I'm noticing your threshold sessions have been responding well
recently — has something shifted in how you've been approaching your quality work?"

**Sample fail:** "Your emerging lifecycle finding CS-11 shows days_since_quality →
pace_threshold correlation strengthening at r=0.41 in L90. What has changed?"

### Test Conversation Set 2 — Resolving Limiter Attribution

**Setup:** Brian. One finding transitioning active → resolving (L-REC signal
weakening after 6 weeks of 72h spacing and 2-quality-session prescription).

**Prompt to coach:** "Am I making progress?"

| # | Criterion | Pass | Fail |
|---|-----------|------|------|
| MR-6 | Resolving transition noticed | Coach references that a significant pattern is changing | No mention of the transition |
| MR-7 | Attribution present | Coach references the training adjustment as the cause | Coach says the pattern is changing without explaining why |
| MR-8 | Validating not alarming | Framing is positive — athlete solved something | Framing is ambiguous or suggests something is wrong |
| MR-9 | Forward-looking | Response includes what comes next or invites the athlete to confirm | Response ends at observation with no forward direction |

**Sample pass:** "The recovery sensitivity pattern we've been working around —
giving you more space between hard sessions — looks like it's improving. Your
body is adapting to the structure. Does that match what you're feeling?"

**Sample fail:** "Your ATL→efficiency correlation is weakening. This may indicate
your structural L-REC trait is resolving."

### Test Conversation Set 3 — Closed Limiter Context

**Setup:** Michael. L-VOL closed 8 months ago.

**Prompt to coach:** "What should I be focusing on in my training?"

| # | Criterion | Pass | Fail |
|---|-----------|------|------|
| MR-10 | No volume prescription | Coach does not recommend more long runs or increased mileage as a focus | Coach recommends volume increase as primary focus |
| MR-11 | Developmental arc acknowledged if relevant | If history is referenced, volume work framed as completed foundation | Volume framed as ongoing need |
| MR-12 | Current limiter drives response | Response reflects current state (race-specific sharpening) | Response reflects historical state (volume building) |
| MR-13 | Closed finding not repeated | Closed limiters mentioned once at most, as context, not as recommendation | Closed limiters appear multiple times or as primary recommendations |

### Test Conversation Set 4 — Structural Trait Communication

**Setup:** Brian. L-REC structural (51.3h half-life).

**Prompt to coach:** "Why do I only get two quality sessions a week?"

| # | Criterion | Pass | Fail |
|---|-----------|------|------|
| MR-14 | Structural framing | Coach explains this as how Brian's body works — not a problem to fix | Coach frames it as a deficit or something to overcome |
| MR-15 | No false hope | Coach does not suggest this will change with more training | Coach implies the structural trait is solvable with effort |
| MR-16 | Actionable context | Coach explains what the structure enables — better quality when sessions happen | Coach only explains the constraint without the benefit |
| MR-17 | No clinical language | Response does not sound like a medical diagnosis | Response uses clinical or pathological framing |

**Sample pass:** "Your body recovers on a longer timeline than most athletes —
your data consistently shows you perform at your best when sessions are well
separated. Two quality sessions with good spacing gets you more from each one
than three cramped sessions would."

**Sample fail:** "You have been diagnosed with structural L-REC based on your
recovery half-life of 51.3 hours and CS-8 correlation at r=0.58."

---

## A/B Comparison (one-time, pre-ship)

Generate the same coach response for the same athlete message with and without
the fingerprint lifecycle section. The lifecycle version should be:
- More specific (references actual patterns, not generic advice)
- More honest about what's proven vs. what's forming
- Never claims a closed pattern is still active

If the non-lifecycle version accidentally sounds better, the lifecycle prompt
needs tuning before ship.

---

## Gate Summary

| Tier | Items | Automated | Manual | Blocking |
|------|-------|-----------|--------|----------|
| Tier 1 | T1-1 through T1-8 | Yes | No | Yes — must pass CI |
| Tier 2 | MR-1 through MR-17 | No | Yes | Yes — founder sign-off |
| A/B | 1 comparison | No | Yes | Yes — founder sign-off |

**Pass condition:** All 8 Tier 1 checks green in CI. All 17 Tier 2 criteria
pass in manual review with founder sign-off. A/B comparison confirms lifecycle
version is better.

**Failure handling:** Any Tier 1 failure blocks deploy. Any Tier 2 failure
requires a prompt or code fix and a re-run of the affected test conversation.

---

## Scope Boundaries

This gate covers coach layer lifecycle integration only. It does not cover:
- **Plan generation quality** — governed by the KB Rule Evaluator (445 PASS, 0 FAIL)
- **Variant dropdown behavior** — separate shipped feature with its own tests
- **Correlation engine accuracy** — governed by confidence gates CG-1 through CG-12

The gate is intentionally narrow: does the coach layer read lifecycle states
correctly and communicate them in a way that builds athlete trust?

---

*This gate proves that Phase 4 produces correct coaching outcomes, not just
correct mechanics. Tier 1 and Tier 2 together close the gap between passing
tests and a feature that actually works for athletes.*
