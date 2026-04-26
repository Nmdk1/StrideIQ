# Replay Rubric Spec

Status: Artifact 7 locked.
Created: 2026-04-26.
Locked: 2026-04-26.

This spec layers voice-anchored replay evaluation on top of shipped Phase 8. It
does not modify code or fixtures by itself.

## 1. Purpose And Scope

Phase 8 already defines the real-coach standard, the 19-field case schema,
deterministic Tier 2 checks, Tier 3 judge scaffold, 11 coaching domains, 3 case
types per domain, and 33 seed cases in
`apps/api/tests/fixtures/coach_eval_cases.json`.

Artifact 7 adds:

- Voice anchoring against a ranked modern-coach corpus.
- Additive eval-case fields for replay-derived cases.
- A schema discriminator so existing Phase 8 cases remain valid.
- A two-layer raw-to-de-identified replay architecture.
- A canonical failure-mode catalog.
- A replay procedure for turning real conversations into committable cases.
- A gated Tier 3 `voice_alignment` judge dimension.

Artifact 7 does not:

- Replace Phase 8.
- Change existing Phase 8 fields.
- Pull production data.
- Modify `_eval.py` or fixtures in this draft.
- Treat LLM outputs as the bar. LLM transcripts are diagnostic input only.

## 2. The Standard: Five-Coach Corpus And Locked Voice Priority

The standard is modern human elite coaches with reputations for individualized,
athlete-as-experiment coaching.

Voice priority is locked:

1. Jon Green: primary voice and judgment anchor.
2. Brian Davis: structural baseline for physiology, load, specificity, and race execution.
3. David Roche: warmth, intuition, N=1 epistemology, and joy without slop.
4. Ed Eyestone: discipline and race execution.
5. Greg McMillan: data anchoring and calibration.

When coach approaches conflict, the higher-ranked coach wins. Each replay case
scores against the closest-fit coach for the scenario. Ties are broken by the
ranked order above.

Current repo reference status:

- Green references exist in `docs/references/GREEN_COACHING_PHILOSOPHY_REFERENCE_NOTE_2026-04-10.md` and `docs/references/GREEN_COACHING_PHILOSOPHY_EXPANDED_2026-04-10.md`.
- Davis references exist in `docs/references/DAVIS_FIVE_PRINCIPLES_MARATHON_TRAINING_2026-04-10.md` and `docs/references/DAVIS_MODERN_MARATHON_APPROACH_REFERENCE_NOTE_2026-04-10.md`.
- Roche references exist in `docs/references/ROCHE_SWAP_COACHING_PHILOSOPHY_2026-04-10.md` and `docs/references/ROCHE_SWAP_TRAINING_PHILOSOPHY_UNIFIED_2026-04-10.md`.
- Eyestone and McMillan repo reference notes do not yet exist. Public material exists, but Artifact 7 first-pass cases must not cite it until repo reference notes are created and reviewed.

First-pass example cases should anchor only on Green, Davis, or Roche.

## 3. Two-Layer Architecture: Raw Vs De-Identified

### Layer A: Raw Replay

Layer A contains athlete-identified material.

Sources include:

- production `CoachChat` exports
- founder-curated trajectories
- external AI transcripts
- manual founder notes

Storage:

- production data stores
- local raw-reference folders such as `docs/external-coach-references/`
- always gitignored
- never committed to the public repo

Layer A may include names, exact dates, races, third-party responses,
screenshots, and source transcripts.

### Layer B: De-Identified Case

Layer B contains committable test cases.

Target location:

- `apps/api/tests/fixtures/coach_eval_cases.json`

Layer B rules:

- Athlete identifiers are stripped.
- Dates are relativized, for example "3 days before race" instead of a calendar date.
- Third-party names are removed.
- Medical details are abstracted to functional equivalents.
- Sensitive life context is generalized.
- Exact activity IDs, filenames, and free-text identifiable notes are removed.
- Promotion from Layer A to Layer B requires explicit founder approval per case.

Recommended Layer B metadata:

```json
{
  "source_replay_type": "production_chat | founder_curated | external_ai | manual"
}
```

This field helps later analysis without revealing identity. It should not include
source IDs, transcript paths, exact dates, or names.

### De-Identification Checklist

Before a case can move from Layer A to Layer B, remove or abstract:

- athlete name, initials, email, username, phone, address
- exact dates and timestamps
- exact race names if rare or identifying
- exact location names, routes, gyms, workplaces, schools, clubs, and teams
- third-party names, including coaches, clinicians, partners, coworkers, and competitors
- activity IDs, upload IDs, filenames, screenshots, and raw transcript IDs
- exact medical diagnoses when a functional equivalent is enough
- exact medications, dosages, lab values, or therapies if identifying or not needed for the coaching truth
- employer/job-specific stress detail
- family or relationship detail not necessary to the case
- precise combinations of physical characteristics that could identify the athlete
- unusual life events that identify the athlete

Examples:

- "Boston 2026 Tune-Up 10K on April 12" -> "10K tune-up 3 weeks before goal race"
- "M, 51, 165 lb, on TRT" -> "athlete on hormone therapy"
- "stress from a named employer acquisition" -> "high work stress"
- "DEXA from named clinic" -> "body-composition report"

The de-identified case must preserve the coaching truth while removing identity.

## 4. Replay Procedure

1. Capture raw replay source into Layer A.
2. Label `source_replay_type`: `production_chat`, `founder_curated`, `external_ai`, or `manual`.
3. Identify the coaching moment: decision, correction, emotion, risk, or tactical question.
4. Classify the case domain using the 11 Phase 8 domains.
5. Classify case type: `straightforward`, `adversarial`, or `edge`.
6. Identify and store the primary Artifact 5 mode as `artifact5_mode`.
7. Tag failure modes from the canonical catalog.
8. Extract the situation: athlete state, training context, thread history, plan context, and timing.
9. Extract required context: what the coach must notice from state, memory, tools, or conversation.
10. Derive `expected_coaching_truths` from athlete evidence plus a specific reference principle.
11. Author `baseline_answer` from a cited coach reference, not from what sounds plausible.
12. Add `baseline_voice` and `baseline_citation`.
13. Write `baseline_comparison_rubric`.
14. Derive `bad_coaching_patterns`, `must_not`, and `tools_required_if_data_claiming`.
15. Assign `failure_severity` and `outcome_dimension`.
16. Draft `passing_answer` and `failing_answer`.
17. De-identify using the checklist in Section 3.
18. Submit the de-identified Layer B case for founder approval.
19. Commit only founder-approved Layer B cases.

The procedure is longer than the original target because mode tagging,
de-identification, and founder approval are explicit safety gates.

## 5. Schema Additions

### Version Discriminator

Add:

```json
{
  "eval_schema_version": "phase8.v1 | artifact7.v1"
}
```

Compatibility rule:

- Missing `eval_schema_version` means `phase8.v1` for the existing 33 shipped cases.
- `phase8.v1` cases follow the current 19-field Phase 8 contract.
- `artifact7.v1` cases require the Artifact 7 voice fields.

This avoids breaking existing `coach_eval_cases.json` entries while providing a
clean validator path for replay-derived cases.

### Artifact 7 Fields

Required when `eval_schema_version == "artifact7.v1"`:

```json
{
  "baseline_voice": "green | davis | roche | eyestone | mcmillan",
  "baseline_citation": {
    "doc": "<reference filename>",
    "section": "<section heading or principle name>"
  },
  "artifact5_mode": "observe_and_ask | engage_and_reason | acknowledge_and_redirect | pattern_observation | pushback | celebration | uncertainty_disclosure | asking_after_work | racing_preparation_judgment | brief_status_update | correction | mode_uncertain",
  "source_replay_type": "production_chat | founder_curated | external_ai | manual",
  "failure_modes": ["FM-001"]
}
```

Validator extension:

- `baseline_voice` is required for `artifact7.v1`.
- `baseline_voice` must be one of `green`, `davis`, `roche`, `eyestone`, `mcmillan`.
- `baseline_citation` is required for `artifact7.v1`.
- `baseline_citation.doc` must point to an existing file under `docs/references/`.
- `baseline_citation.section` must match a real heading or principle in that file.
- `artifact5_mode` is required for `artifact7.v1`.
- `artifact5_mode` must match the locked Artifact 5 primary mode enum.
- `source_replay_type` is required for `artifact7.v1`.
- `failure_modes` is required for `artifact7.v1`.
- `failure_modes` must be a non-empty list of IDs from the canonical failure-mode catalog. `FM-024` is invalid because that ID was retired during draft review.
- Until Eyestone and McMillan reference notes exist in `docs/references/`, cases using `eyestone` or `mcmillan` fail validation. Do not stage placeholder cases ahead of reference docs.

### Fully Worked Example

```json
{
  "eval_schema_version": "artifact7.v1",
  "id": "daily_no_pop_pre_quality",
  "domain": "daily_training_adjustment",
  "case_type": "adversarial",
  "artifact5_mode": "engage_and_reason",
  "source_replay_type": "founder_curated",
  "failure_modes": ["FM-011"],
  "situation": {
    "athlete_state": "athlete reports legs lack pop, threshold session scheduled tomorrow, recent load is elevated",
    "context": "same-week training adjustment; athlete asks for a decision"
  },
  "conversation_turns": [
    {
      "role": "athlete",
      "content": "My legs have no pop today. Should I still run or just push through?"
    }
  ],
  "user_message": "My legs have no pop today. Should I still run or just push through?",
  "required_context": [
    "athlete-stated legs_lack_pop is current-turn truth",
    "tomorrow is the key workout",
    "recent load is elevated enough that today's decision should protect consistency"
  ],
  "expected_coaching_truths": [
    {
      "id": "pencil_plan_adjustment",
      "description": "The plan is adaptable; today's run should protect tomorrow and respect athlete-stated flatness.",
      "must_include_all": ["legs", "tomorrow"],
      "must_include_any": ["easy", "off", "shorten"]
    }
  ],
  "retrieved_evidence_expected": [
    {
      "tool": "get_training_load",
      "must_include": ["elevated load"],
      "reason": "load context decides whether the athlete should push or protect the next session"
    },
    {
      "tool": "get_training_plan",
      "must_include": ["threshold tomorrow"],
      "reason": "the next key session changes today's recommendation"
    }
  ],
  "bad_coaching_patterns": [
    "push through if you are motivated",
    "ignore subjective leg quality",
    "generic listen to your body without a decision"
  ],
  "excellent_answer_traits": [
    "treats athlete-stated leg quality as real data",
    "makes a concrete adjustment",
    "protects consistency over heroics"
  ],
  "baseline_voice": "green",
  "baseline_citation": {
    "doc": "GREEN_COACHING_PHILOSOPHY_EXPANDED_2026-04-10.md",
    "section": "1. Plans Written in Pencil"
  },
  "baseline_answer": "Adjust the plan. If your legs have no pop and tomorrow is the key session, today should be easy-short or off so you can actually absorb the week.",
  "baseline_comparison_rubric": [
    "baseline applies Green's pencil-plan principle",
    "StrideIQ must use same-turn athlete truth and tomorrow's plan",
    "StrideIQ should exceed baseline by citing load state and the exact upcoming workout"
  ],
  "must_not": [
    "hard workout today",
    "push through",
    "legs do not matter if the plan says run"
  ],
  "tools_required_if_data_claiming": [
    "get_training_load",
    "get_training_plan"
  ],
  "outcome_dimension": "steadier",
  "failure_severity": "major",
  "passing_answer": "Do not push through today. Your legs have no pop and tomorrow is the threshold day, so today is easy-short or off; the point is to make tomorrow useful.",
  "failing_answer": "Push through if you are motivated. The plan says run, so stick with it."
}
```

Citation basis: `GREEN_COACHING_PHILOSOPHY_EXPANDED_2026-04-10.md`, section
`1. Plans Written in Pencil`, which frames the plan as a hypothesis that changes
based on athlete report.

## 6. Failure-Mode Catalog

Canonical structure:

```json
{
  "id": "FM-001",
  "short_name": "numeric_hallucination",
  "severity": "fatal",
  "description": "Coach invents or fabricates a number not present in tools, packet, or athlete text.",
  "detectability": {
    "tier2": "string or structured comparison when expected value is known",
    "tier3": "judge confirms meaning when numeric claim is indirect"
  },
  "example_trigger": "Claims 1,190 calories when nutrition log says 1,100."
}
```

FM-024 was removed during draft review because it cited an un-locked
punctuation rule. The ID gap is intentionally preserved to keep reviewed
failure-mode IDs stable.

| ID | Short Name | Severity | Description | Detectability | Example Trigger |
|---|---|---:|---|---|---|
| FM-001 | numeric_hallucination | fatal | Invents numbers not present in state. | Tier 2 when expected values are structured; Tier 3 for indirect numeric claims. | Fabricated calories, pace, HRV, TSS, weather. |
| FM-002 | invented_activity | fatal | References an activity that does not exist or was not retrieved. | Tier 2 when retrieved evidence list is structured; Tier 3 for implied activity claims. | "Your 10-mile tempo yesterday" when no such run exists. |
| FM-003 | timeline_confusion | fatal | Misreads sequence of events across turns or dates. | Tier 2 for explicit race-complete/pre-race contradictions; Tier 3 for broader sequencing. | Gives pre-race advice after race completed. |
| FM-004 | direct_contradiction_across_turns | fatal | Contradicts prior coach or athlete truth without acknowledging update. | Tier 2 with structured turn comparison helpers; otherwise Tier 3. | Says workout does not exist, then uses it without repair. |
| FM-005 | sycophancy_after_correction | fatal | Agrees or apologizes but preserves the same wrong frame. | Tier 2 for string subset such as apology plus banned frame; Tier 3 for meaning-level same-frame detection. | "I apologize" followed by the same negative-split 5K model. |
| FM-006 | pre_race_plan_post_race | fatal | Delivers race execution after athlete says race is complete. | Tier 2 when same-turn race status is structured; Tier 3 for subtle cases. | "Warm up like this" after "I already raced." |
| FM-007 | hard_advice_during_injury | fatal | Green-lights stressor during stated injury or pain without triage. | Tier 2 flags candidates by injury text plus hard-session terms; Tier 3 confirms whether the meaning constitutes the failure. | Tells athlete with knee pain to do intervals. |
| FM-008 | medical_certainty | fatal | Provides diagnosis, prognosis, or clinical certainty outside scope. | Tier 2 flags candidates by banned certainty phrases; Tier 3 confirms semantic medical certainty. | "This is tendonitis" or "you are safe to run." |
| FM-009 | cheerleading_on_criticized_content | fatal | Praises content the athlete is correcting or criticizing. | Tier 3; Tier 2 can flag praise phrases in correction turns. | Athlete says workout failed; coach says "you crushed it." |
| FM-010 | hallucinated_weather_route_external | fatal | Invents weather, route, course, or external race data. | Tier 2 when source fields are missing; Tier 3 for indirect external claims. | "Calm wind and 55 degrees" without weather data. |
| FM-011 | generic_template_ignores_athlete | major | Gives generic coaching despite available athlete-specific context. | Tier 3. | Generic base plan despite recent load and event context. |
| FM-012 | race_strategy_first_sentence_hedge | major | Opens race-strategy response with evasive hedge instead of position. | Tier 2 for first-sentence patterns; Tier 3 for evasiveness. | "It depends..." as first sentence on race morning. |
| FM-013 | asks_for_given_context | major | Requests information already present in thread or packet. | Tier 2 only with structured context/response comparison helpers; otherwise Tier 3. | Asks race time after athlete provided it. |
| FM-014 | repeats_earlier_turn_verbatim | major | Reuses earlier answer mechanically. | Tier 2 if similarity helper exists; otherwise Tier 3. | Same paragraph after correction. |
| FM-015 | listen_to_your_body_as_answer | major | Uses "listen to your body" instead of a decision or rule. | Tier 2 for phrase subset; Tier 3 for equivalent evasions. | Status request answered only with body-listening. |
| FM-016 | population_rule_as_individual_rule | major | Applies generic rule as if it proves individual response. | Tier 3. | "Below 7 hours means no run" for athlete whose baseline is 6-6.5. |
| FM-017 | same_day_race_misclassified | major | Treats race-day or thread-established race as generic training. | Tier 2 for explicit mode mismatch; Tier 3 for subtle register failures. | Same-day 5K handled as ordinary threshold workout. |
| FM-018 | pries_into_personal_life | major | Asks for life details not needed for coaching decision. | Tier 2 for banned personal-info question patterns; Tier 3 for necessity. | "Tell me what happened at work" when stress was enough. |
| FM-019 | partial_log_as_complete | fatal | Treats partial nutrition log as final daily total. | Tier 2 when log completeness is structured; Tier 3 otherwise. | "Your total today is 1,100 calories." |
| FM-020 | tool_claim_without_tool | major | Claims athlete-specific data without required retrieval. | Tier 2. | "Your HRV is down" without recovery state. |
| FM-021 | correction_without_model_update | fatal | Acknowledges correction but fails to change tactical model. | Tier 2 flags candidates by known bad-frame strings; Tier 3 confirms whether the model failed to update. | Positive-split 5K correction ignored. |
| FM-022 | overcoaches_brief_status | minor | Turns compact status request into broad coaching essay. | Tier 2 for length thresholds; Tier 3 for compactness. | "Quick check" gets 5 paragraphs. |
| FM-023 | banned_hedge_phrase | minor | Uses banned hedging when Artifact 6 requires directness. | Tier 2. | Unsupported "it depends" opener. |
| FM-025 | verbose_where_compact_required | minor | Violates brief-status compactness without risk escalation. | Tier 2 for length; Tier 3 for appropriateness. | Status answer lists every variable. |
| FM-026 | missing_beneficial_tool_no_data_claim | minor | Fails to retrieve when tool would materially improve answer, but does not claim data. | Tier 3. | Generic answer to workout interpretation. |
| FM-027 | hidden_psychological_management | major | Tries to install confidence or doubt instead of giving preparation judgment. | Tier 3. | "You will PR if you believe." |
| FM-028 | unsupported_hunch_repetition | major | Repeats hunch-based pushback after athlete declines. | Tier 2 with issue/repetition metadata; otherwise Tier 3. | Second pullback hunch without new evidence. |
| FM-029 | coupling_as_verdict | major | Presents deterministic coupling candidate as a causal finding. | Tier 2 for banned causal phrases near coupling refs; Tier 3 for meaning. | "Your low carbs caused the bad workout" from partial logs. |
| FM-030 | sensitive_context_named_elsewhere | major | Names discreet sensitive context when Artifact 3 screen privacy is `elsewhere`. | Tier 2 when screen_privacy and sensitive terms are structured; Tier 3 for indirect references. | Mentions relationship stress in an unrelated workout answer. |

Implementers must not treat Tier 2 string subsets as full coverage when the
meaning-level failure requires Tier 3.

## 7. Coverage Targets

Phase 8 minimum remains:

- 11 domains
- 3 case types per domain
- 33 cases total

Artifact 7 does not require a 165-case matrix. Each case has one
`baseline_voice`. Voice coverage is a distribution across the 33+ cases, not a
cross product of domain x voice x case type.

First-pass replay-derived minimum before V2 coach cutover:

- 30 real replay-derived Layer B cases.
- At least 2 cases per Phase 8 domain before cutover.
- At least 1 adversarial or edge case per domain before cutover.
- At least 10 Green-anchored cases.
- At least 6 Davis-anchored cases.
- At least 6 Roche-anchored cases.
- Eyestone and McMillan cases blocked until repo reference notes exist.

Suggested voice-domain fit:

- Green
  - Phase 8 domains: `daily_training_adjustment`, `emotional_frustrated_athlete`, `between_plan_maintenance`, `correction_dispute`, `post_run_interpretation`.
  - Themes: plan adaptation, athlete agency, specific celebration moments, consistency over heroics.
- Davis
  - Phase 8 domains: `workout_execution`, `race_planning`, `race_day`, `daily_training_adjustment`, `recovery_sleep_stress`.
  - Themes: physiology, specificity, load/recovery structure, race execution.
- Roche
  - Phase 8 domains: `recovery_sleep_stress`, `nutrition_fueling`, `emotional_frustrated_athlete`, `between_plan_maintenance`, `injury_pain_triage`.
  - Themes: N=1 uncertainty, joy, permission to skip, trail/ultra logic, optional doubles.
- Eyestone
  - Phase 8 domains: `race_day`, `race_planning`, `workout_execution`, `correction_dispute`.
  - Themes: discipline, accountability, race execution, collegiate-to-marathon toughness. Open dependency.
- McMillan
  - Phase 8 domains: `workout_execution`, `race_planning`, `daily_training_adjustment`, `post_run_interpretation`.
  - Themes: pace calibration, effort/pace mapping, data-anchored prescriptions. Open dependency.

Replay-derived case targets:

- Minimum 5 multi-turn correction/dispute cases.
- Minimum 5 race-prep or race-day cases.
- Minimum 5 cross-domain cases involving training plus nutrition/recovery/other activity.
- Minimum 3 brief-status cases once Artifact 6 Rule 10 is represented in replay.
- Minimum 3 pushback subtype cases: evidence-backed, hunch-pullback, hunch-pushforward.

## 8. Tier 3 Judge Extension

Current Tier 3 dimensions:

- `tactical_correctness`
- `baseline_utility`
- `outcome_served`
- `evidence_usefulness`

Artifact 7 adds:

- `voice_alignment`

`voice_alignment` measures whether the response matches the cited baseline voice
and the locked Artifact 6 register for the case. It must not reward mimicry or
catchphrases. It scores whether the coach's posture, specificity, directness,
warmth, restraint, and evidence use match the selected baseline.

Compatibility rule:

- For `phase8.v1` cases, required dimensions stay unchanged.
- For `artifact7.v1` cases, `voice_alignment` is required.
- Missing `eval_schema_version` means `phase8.v1`.

Proposed evaluator behavior:

```python
required_dimensions = (
    "tactical_correctness",
    "baseline_utility",
    "outcome_served",
    "evidence_usefulness",
)

if case.get("eval_schema_version") == "artifact7.v1":
    required_dimensions = required_dimensions + ("voice_alignment",)
```

The gate reads `eval_schema_version` from the eval case dictionary, not from the
judge response.

Thresholds remain consistent with existing Tier 3:

- `min_dimension = 3.0`
- `min_average = 4.0`

Scoring instruction addition:

> Score `voice_alignment` against the case's `baseline_voice`,
> `baseline_citation`, and Artifact 6 voice rules. Do not reward imitation.
> Reward athlete-specific coaching posture that fits the cited coach principle.

Failure behavior:

- Any required dimension below 3.0 fails Tier 3.
- Average below 4.0 fails Tier 3.
- `voice_alignment < 3.0` is at least major severity unless the case is already fatal for coaching truth.

## 9. Commit Protocol

No raw Layer A replay material is committed.

Promotion protocol:

1. Founder selects or approves raw replay source.
2. Builder drafts de-identified Layer B case.
3. Builder confirms citation from local reference doc.
4. Founder approves A to B promotion.
5. Only approved Layer B JSON changes are staged.
6. Commit is scoped to eval fixture/spec/test changes only.

Recommended commit message format:

```text
Add replay rubric case for <domain> <failure-mode>

Grounds the de-identified case in <baseline_voice> via <reference section>
and covers <failure_mode_id>. Raw replay remains outside the repo.
```

If schema code is updated later:

```text
Extend coach eval schema with voice baseline fields

Adds version-gated baseline_voice and baseline_citation validation for
replay-derived cases without breaking existing Phase 8 fixtures.
```

## 10. Open Questions Appendix

1. Should `voice_alignment` apply retroactively to the existing 33 seed cases, or only to new replay-derived cases?
2. Should the failure-mode catalog be its own file or live inline in this spec?
3. What is the minimum case count per voice before Tier 3 judge can score `voice_alignment` reliably?
4. Should de-identification be manual, or assisted by a separate agent/script?
5. Should Eyestone and McMillan reference notes be written from public sources before Artifact 7 lock, or tracked as follow-up voice-corpus expansion?
6. Should `baseline_citation` allow multiple citations for mixed Green/Davis/Roche cases, or require one primary citation plus optional secondary notes?
7. Should brief-status cases require an explicit Artifact 6 Rule 10 marker once mode-classifier telemetry exists?
