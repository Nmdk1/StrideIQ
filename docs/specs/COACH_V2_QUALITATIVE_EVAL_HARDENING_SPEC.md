# Coach V2 Qualitative Eval Hardening Spec

Status: Draft for founder review.
Created: 2026-04-27.
Owner: StrideIQ founder + implementation agents.

## 1. Purpose

V2 has already been rebuilt. This spec does not authorize another runtime
rebuild.

The purpose is to add a thin qualitative gate on top of the existing coach evals
so the product can catch answers that are factually grounded and tactically
reasonable, but still feel bad in the product: too long, too mechanical, too
obsessed with stale context, too much like database proof instead of coaching.

The existing evals are real and remain authoritative:

- `apps/api/tests/fixtures/coach_eval_cases.json`
- `apps/api/tests/test_coach_real_standard.py`
- `apps/api/tests/fixtures/coach_value_cases.json`
- `apps/api/tests/test_coach_value_contract.py`
- `apps/api/services/coaching/comparison_harness.py`
- `apps/api/tests/fixtures/v2_acceptance_set.json`
- `docs/specs/REPLAY_RUBRIC_SPEC.md`
- `docs/specs/V2_VOICE_CORPUS.md`

This spec adds the missing layer: qualitative scoring of actual V2 outputs for
compression, relevance discipline, system-language suppression, and conversational
feel.

## 2. Diagnosis

The current eval stack catches many severe failures:

- invented or stale facts
- correction failures
- missing evidence
- tactical mistakes
- generic cheerleading
- template phrases
- race-day contract failures
- weak or missing decision frames

It does not reliably catch these production-visible failures:

- The answer proves packet access instead of coaching.
- The answer contains too many numbers for the question.
- The answer carries the same race, calf, or pace-zone context into unrelated
  domains.
- The answer leads with missing-data warnings when the decision is already
  answerable.
- The answer uses system-facing phrases such as "athlete_facts" or "unknown in
  your profile."
- "Surface the unasked" becomes a visible section or habit instead of a rare,
  earned coaching move.
- Curated passing answers pass the eval while live V2 output would not.

The gap is not truth. The gap is taste, compression, and relevance.

## 3. Non-Goals

This work must not:

- create a Coach Runtime V3
- reintroduce V1 fallback
- replace Artifact 7 or Phase 8
- change the coach's domain logic before tests demonstrate the failure
- use LLM judge scores as the only gate
- require production data to be committed
- widen OAuth or third-party API permissions

## 4. New Evaluation Layer

Add a qualitative output evaluator that can score any completed coach answer.
It should run against:

1. Curated fixture answers, to keep the existing case bank useful.
2. Live or recorded V2 outputs, to catch actual runtime behavior.
3. Production smoke transcripts after de-identification, when the founder
   approves promotion into the repo.

The evaluator should be deterministic first. LLM-as-judge may remain a Tier 3
review aid, but deterministic checks must catch the recurring failure classes.

## 5. Qualitative Dimensions

### 5.1 Compression

The response should match the size of the moment.

Suggested first-pass word ceilings:

| Contract | Max words | Notes |
|---|---:|---|
| `quick_check` | 120 | Answer first. One reason. One action. |
| `decision_point` | 220 | Recommendation, tradeoff, default. |
| `nutrition_fueling` | 260 | Practical timing/food guidance, one personalization question max. |
| `recovery_sleep_stress` | 220 | Triage and stop rule. No lecture. |
| `injury_pain_triage` | 240 | Red flags and decision rule. |
| `race_strategy` | 420 | Longer allowed because execution details matter. |
| `race_day` | 360 | Timeline, warmup, execution cues. |
| `post_run_interpretation` | 380 | Meaning of the run, not full packet narration. |
| `deep_analysis` | 700 | Allowed only when the user's question asks for synthesis. |

Failures:

- response exceeds contract ceiling without a deep-analysis classification
- more than one follow-up question in non-deep-analysis answers
- answer contains more paragraphs than the moment needs
- simple questions receive a full evidence essay

### 5.2 Evidence Density

Evidence should support the read, not dominate it.

Suggested first-pass limits:

| Contract | Max athlete-specific numeric anchors |
|---|---:|
| `quick_check` | 2 |
| `decision_point` | 4 |
| `nutrition_fueling` | 3, excluding general nutrition protocol quantities |
| `recovery_sleep_stress` | 3 |
| `injury_pain_triage` | 3 |
| `race_strategy` | 8 |
| `race_day` | 6 |
| `post_run_interpretation` | 8 |
| `deep_analysis` | 14 |

General protocol numbers such as "10-15 minutes before" or "4-6 oz water" do
not count as athlete-specific numeric anchors. Athlete-specific anchors include
activity dates, mileage, pace, heart rate, age, percent fade, weekly volume, and
race countdown.

Failures:

- number count exceeds the contract limit
- answer lists evidence without converting it into a coaching read
- same anchor appears repeatedly across adjacent turns without adding new value

### 5.3 Relevance Discipline

The answer should use current context only when it changes the decision.

Failures:

- active race context appears in nutrition, recovery, or general coaching when it
  does not change the recommendation
- calf or injury context appears in non-injury answers without affecting the
  decision
- pace-zone unknowns are repeated after the answer has already given an
  effort-based plan
- a single recent event dominates unrelated domains

Allowed:

- race context in race-week training decisions
- injury context in training or recovery decisions when it changes the default
- pace-zone unknowns in pacing prescriptions when the answer cannot safely set
  pace targets without them

### 5.4 System-Language Suppression

The athlete should not see implementation vocabulary.

Deterministic forbidden phrases:

- `athlete_facts`
- `unknown in your profile`
- `unknowns`
- `ledger`
- `packet`
- `runtime`
- `tool`
- `retrieved evidence`
- `confidence athlete_stated`
- `context block`
- `same_turn_table_evidence`

Allowed exception:

- Internal logs, debug traces, or developer-only reports may use these terms.
  Visible coach answers may not.

### 5.5 Unknown Handling

Missing facts should be surfaced only when they change the decision.

Failures:

- answer opens with a missing-data warning when a safe practical answer is
  possible
- same unknown is asked in consecutive turns
- missing pace zones block effort-based guidance
- profile gaps are phrased as database gaps instead of natural coach questions

Preferred pattern:

1. Give the best safe answer.
2. Name the missing fact only if it would materially tighten the guidance.
3. Ask one question.

### 5.6 Natural Coaching Shape

The answer should feel like a coach with judgment, not a report.

Default shape:

1. Read.
2. Decision.
3. One reason or one tradeoff.
4. Optional one question.

Allowed deviations:

- Race execution can use a compact timeline.
- Deep analysis can use sections.
- Correction/dispute can lead with trust repair.
- Emotional-load turns can lead with regulation and agency.
- Observe-and-ask turns can lead with an earned observation and end in an open
  question.
- Uncertainty-disclosure turns can lead with the work performed and the limit of
  what can honestly be inferred.

Failures:

- visible "The unasked:" section in quick-check or decision-point turns
- visible structural headings such as "The read," "The deeper read," or
  "Decision for today" when the answer would be better as plain coaching prose
- more than one closing question
- answer reads like a generated rubric rather than a human coaching turn

Important distinction: the eval should reject visible labels, not the underlying
coaching structure. The coach should still read, decide, and act. It should not
perform those moves as headings unless the mode specifically calls for a compact
race-day timeline or another explicit structured format.

## 6. Required New Replay Cases

Add de-identified cases from the April 27 production smoke review only after
founder approval.

### Case A: Easy Run Focus, Compression

Prompt:

> What is one thing I should pay attention to on easy runs this week?

Failure being caught:

- Too many anchors and race-week context for a one-thing question.
- Answer should be short and actionable.

Passing answer shape:

> Watch whether the second half turns into a progression run. Keep the back half
> no faster than the front half; if you keep closing hard, the easy-day
> prescription is failing.

### Case B: Nutrition Adjustment, Relevance

Prompt sequence:

> I have a hard 75 minute workout tomorrow morning. What should I eat tonight and
> before the workout?
>
> I usually tolerate gels but get stomach slosh with too much fluid. Adjust that
> advice.

Failure being caught:

- Race/calf/training context crowding out the nutrition answer.
- Good protocol buried under unrelated training narrative.

Passing answer shape:

> Gel stays. Fluid drops. Take one gel 10-15 minutes before with 4-6 oz water,
> then skip extra fluid unless heat changes the equation.

### Case C: Profile Correction, Fact Coherence

Prompt sequence:

> Correction for this thread: I am not training for a marathon right now, I am
> focused on short road races.
>
> Given that correction, should tomorrow be more endurance or sharpening?

Failure being caught:

- Incoherent fact phrase such as "5K with a sub-1:22 goal."
- Overlong evidence narration before the recommendation.

Passing answer shape:

> Sharpening, but not a workout. Short road-race focus means turnover matters;
> five days out, the dose is easy running plus strides, not endurance.

### Case D: Calf Soreness, Agency

Prompt:

> My left calf is a little sore after yesterday but not sharp. Should I run easy,
> cross-train, or rest?

Failure being caught:

- Excessive drama or command voice.
- Risk framed as DNS/DNF without enough evidence.

Passing answer shape:

> Cross-train today. Not because this is an injury diagnosis; because calf
> soreness five days before a race is a bad place to spend impact. If it is
> quiet tomorrow after walking and a short jog test, running comes back.

### Case E: Activity Interpretation, Data Dump

Prompt:

> Look at my recent running pattern and tell me what you would be cautious about
> before adding more intensity.

Failure being caught:

- Deep analysis allowed, but not unlimited packet narration.
- The answer must name the pattern and decision without requiring the athlete to
  parse every activity.

Passing answer shape:

> I would be cautious about adding intensity on top of faster easy-day finishes
> and a recent hard effort that faded. That combination says you can access
> speed, but durability is the question. Earn the next workout with three honest
> easy days first.

## 7. Implementation Shape

### Phase Q1: Text Quality Evaluator

Add a deterministic evaluator, likely:

- `apps/api/services/coaching/qualitative_eval.py`
- `apps/api/tests/test_coach_qualitative_eval.py`

It should expose a pure function:

```python
evaluate_qualitative_response(
    *,
    user_message: str,
    assistant_text: str,
    contract_type: str | None = None,
    domain: str | None = None,
    prior_turns: list[dict] | None = None,
    expected_relevant_terms: list[str] | None = None,
    irrelevant_context_terms: list[str] | None = None,
) -> QualitativeEvalResult
```

Required checks:

- word ceiling by contract/domain
- athlete-specific numeric anchor count
- forbidden system-language terms
- repeated unknown phrasing
- max follow-up questions
- banned visible section labels for quick/decision turns
- irrelevant context terms

### Phase Q2: Fixture Integration

Extend replay cases with optional qualitative fields:

```json
{
  "qualitative_contract": {
    "max_words": 220,
    "max_athlete_numeric_anchors": 4,
    "max_followup_questions": 1,
    "forbidden_system_terms": true,
    "forbidden_visible_sections": ["The unasked:"],
    "irrelevant_context_terms": ["calf", "Coke 10K"],
    "must_lead_with_decision": "mode_conditioned"
  }
}
```

Compatibility:

- Existing cases without `qualitative_contract` continue to pass unchanged.
- New qualitative production replay cases must include it.
- `must_lead_with_decision` must be interpreted through the mode classifier.
  It is appropriate for `quick_check`, most `decision_point` turns, and many
  race execution turns. It is not appropriate for `observe_and_ask`,
  `uncertainty_disclosure`, `asking_after_work`, or correction turns that need
  to repair trust before prescribing.

### Phase Q3: Actual V2 Output Harness

Add a harness that can run selected cases through the actual V2 response path or
through saved V2 output records.

The point is not to replace curated passing/failing answers. The point is to
answer:

> Does the current runtime produce an acceptable answer for this case?

Acceptable first version:

- local/dev only by default
- marked integration if it calls the model
- can also evaluate recorded production smoke text stored in a gitignored raw
  file and promoted only after de-identification

### Phase Q4: Production Smoke Qualitative Report

Update the smoke procedure to emit a compact qualitative report:

- runtime version and fallback status
- response word count
- numeric anchor count
- forbidden system terms
- stale context hits
- follow-up question count
- qualitative pass/fail

This report is advisory until founder approves making it deploy-blocking.

## 8. Acceptance Criteria

The work is not done until:

- Existing Phase 8, Artifact 7, value-contract, and comparison-harness tests
  still pass.
- Qualitative evaluator rejects the April 27 failure shapes:
  - overlong easy-run answer
  - nutrition answer with unrelated training/race bleed
  - visible `athlete_facts` phrasing
  - repeated pace-zone unknowns where effort guidance is enough
  - excessive numeric anchors in quick-check answers
- Qualitative evaluator accepts short, direct, grounded answers for the same
  cases.
- At least five founder-approved de-identified replay cases are added.
- A production smoke run can produce qualitative scores for actual V2 answers.
- No V2 runtime architecture is replaced.

## 9. Stop Conditions

Stop and return to founder review if:

- a proposed fix requires a new runtime
- qualitative gates conflict with Artifact 7 voice rules
- deterministic checks start rejecting excellent coach answers because they are
  merely stylistically different
- relevance filtering would suppress safety-critical injury or race-week context
- live V2 output cannot be evaluated without committing production-private data

## 10. Recommended First Build Slice

The first implementation should be intentionally small:

1. Add the pure qualitative evaluator and tests.
2. Add only two replay cases:
   - easy-run compression
   - nutrition relevance
3. Run it against the saved April 27 production responses locally.
4. Report what fails before changing the runtime.

Only after that should implementation touch prompt, packet relevance, or
response-shape enforcement.
