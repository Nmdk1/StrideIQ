# ADR-056: Race-Result-Only Pace Calibration (Training Pace Calculator) + Onboarding Value Artifact

## Status
**Accepted (Implemented)**

## Date
2026-01-24

## Context
StrideIQ’s onboarding interview collects meaningful goal context (race type/date, target outcome, limiter, time availability), but it does **not** immediately return a concrete, usable artifact. This creates a trust gap: we ask for high-leverage inputs yet provide little immediate value.

Separately, **prescriptive training paces cannot be derived reliably from general training data**:
- Training runs are often mis-labeled (Strava titles/segments), effort is variable, terrain/weather distort pace, and HR can be noisy.
- “Appeasing” with estimated paces from low-quality inputs violates the trust contract.

We already ship a **Training Pace Calculator** implementation (physics-based Daniels/Gilbert equations) used elsewhere. We need to use that same calculator to produce deterministic, trustworthy paces—**but only when we have a valid performance anchor**.

## Decision
We will calibrate prescriptive training paces **only** from a user-provided **most recent race/time-trial result** (distance + finish time).

1) **Onboarding interview change (Goals stage)**
- Ask for **most recent race/time trial**:
  - distance (standard set + “other”)
  - finish time (HH:MM:SS or MM:SS)
  - optional date
- If the athlete does not provide a race/time-trial result, the UI must explicitly state:
  - **No prescriptive paces yet**
  - Prescriptive paces unlock after a race/time-trial is completed and entered

2) **Computation**
- Use the existing **Training Pace Calculator** formulas to compute:
  - Easy (range), Marathon, Threshold, Interval, Repetition (mi + km)
- Do **not** compute paces from general training activity data in v1.

3) **Persistence (durable profile primitives)**
- Store the anchor and computed paces in dedicated tables:
  - `AthleteRaceResultAnchor` (source-of-truth performance anchor)
  - `AthleteTrainingPaceProfile` (derived paces with provenance)
- Critical safety invariant: **do not mutate existing `Athlete.rpi` / `Athlete.threshold_pace_per_km`** in this implementation. This prevents unintended changes to existing plans or other computations.

4) **Immediate user value (“value artifact”)**
- After the Goals stage is saved:
  - If an anchor is present and calculation succeeds, show a compact **Training Pace Profile** summary.
  - If not present, show a clear “locked until race/time trial” message.

## Feature Flag
- Flag key: `onboarding.pace_calibration_v1`
- Default: enabled (100% rollout) after implementation lands.

## Considered Options (Rejected)
- **Infer paces from training data (Strava activities)**: rejected for trust/correctness; too noisy for prescriptive ranges and encourages false precision.
- **Always compute an estimate**: rejected; violates “no appeasement with bad data.”
- **Overwrite `Athlete.rpi` / pace columns**: rejected for safety; could silently change existing athlete experience and plan generation behavior.

## Consequences
### Positive
- Immediate onboarding value that is deterministic and defensible.
- A clear trust stance: prescriptive paces require a real performance anchor.
- Durable, queryable “profile primitives” for future surfaces (coach context, plan generation) without re-asking.

### Negative / Trade-offs
- Some athletes will not get prescriptive paces on day 1 until they perform a time trial/race.
- Requires additional UI fields and persistence schema.

## Security / Privacy Highlights
- Race results are personal performance data; treat as normal user data (no secrets).
- Do not log raw times unnecessarily in server logs.
- Paces are derived values; store with provenance so we can explain “why these paces.”

## Test Strategy
- **Backend**
  - Saving Goals intake with a race result computes a pace profile and persists both anchor + paces.
  - Saving Goals intake without a race result does **not** create a pace profile and returns an explicit “no paces yet” signal.
  - Determinism: same input → same computed outputs.
- **Frontend**
  - Goals stage shows race result fields when the feature flag is enabled.
  - After saving, the UI renders either the computed pace profile summary or the “locked” message.

## Rebuild / Verify
- Apply migration
- Run API tests
- Run web tests
- Manual smoke:
  - Complete onboarding Goals stage with a race result → see pace summary
  - Complete onboarding Goals stage without a race result → see “no prescriptive paces yet”

## Blocker Question
**What if an athlete has no recent race/time trial?**

**Answer:** We do not generate prescriptive paces. We present effort-based guidance and prompt them to complete a short time trial/race to unlock prescriptive paces.

