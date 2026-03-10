# Effort Classification Tier 0 Proposal

**Date:** March 8, 2026
**Status:** Proposal only — not shipped
**Depends on:** shipped effort classification in
`docs/specs/EFFORT_CLASSIFICATION_SPEC.md`

This document holds the future pace-anchored Tier 0 concept that was
previously mixed into the shipped spec. It is preserved here so the idea
stays alive without implying that it already exists in production.

---

## Why Tier 0 Exists

The shipped system removed `max_hr` as a hard gate and restored working
effort classification using the athlete's own HR history. That solved
the immediate trust and functionality problem.

The next question is deeper: what should define effort when pace and HR
disagree?

The proposal here is that pace should anchor the classification when the
system has enough context to interpret it correctly, because pace is what
the athlete actually did. HR remains valuable as a confirming or anomaly
signal, especially when conditions degrade pace.

This is product philosophy and future design, not live behavior.

---

## Proposed Decision

Add a new preferred tier ahead of the shipped HR-based tiers:

### `classify_effort(activity, athlete_id, db) -> "hard" | "moderate" | "easy"`

Tier order if this ships:

1. Tier 0: TPP (Threshold Pace Percentage)
2. Tier 1: HR Percentile Distribution
3. Tier 2: HRR with Observed Peak
4. Tier 3: Workout Type + RPE

---

## Tier 0: TPP

Classify effort by what the athlete actually ran, relative to what they
have proven they can sustain.

**Formula:**

```text
TPP = threshold_pace_sec_per_mile / activity_gap_sec_per_mile
```

Both values are in seconds per mile. A faster activity produces a higher
TPP.

| TPP | Classification |
|-----|----------------|
| >= 0.92 | hard |
| 0.78-0.91 | moderate |
| < 0.78 | easy |

### Eligibility Gate

Tier 0 only activates when:

- the athlete has an RPI-derived threshold pace
- the activity has split data with GAP computed

If either input is missing, classification falls through to Tier 1.

### Why It Matters

- effort-anchored: measures what the athlete controlled
- self-calibrating: as threshold pace improves, the same absolute pace
  becomes a lower percentage automatically
- uses data already present in the system: RPI, split GAP, threshold
  pace derivation

### Activity-Level GAP

The proposal assumes activity-level GAP is derived as the
distance-weighted average of `ActivitySplit.gap_seconds_per_mile` across
the run.

---

## Combined TPP + HR Logic

GAP handles hills. It does not fully handle heat, humidity, altitude, or
other conditions that degrade pace at the same physiological effort.

Under this proposal, pace still anchors the classification, but HR can
upgrade it when conditions clearly made pace slower than the athlete's
true effort.

| TPP says | HR says | Final classification | Rationale |
|----------|---------|----------------------|-----------|
| hard | hard | hard | signals agree |
| moderate | moderate | moderate | signals agree |
| easy | easy | easy | signals agree |
| moderate | hard | hard | conditions degraded pace |
| easy | hard | moderate | body under load at easy pace |
| hard | easy | hard | keep pace anchor, flag review |
| hard | moderate | hard | keep pace anchor |
| easy | moderate | easy | minor HR elevation does not override pace |
| moderate | easy | moderate | keep pace anchor |

### Principle

- pace anchors the classification
- HR can upgrade when it reveals higher effective load
- HR does not downgrade hard pace into an easier effort

### Logging

Every TPP-vs-HR disagreement would be logged as a future correlation
input.

---

## Proposed Implementation Shape

### `services/effort_classification.py`

If Tier 0 ships, the shared classifier would expand to:

```python
def classify_effort(activity: Activity, athlete_id: str, db: Session) -> str:
    """
    Tier 0: TPP — grade-adjusted pace as percentage of threshold pace.
    Tier 1: HR percentile from athlete's own distribution.
    Tier 2: HRR with observed peak (when eligible).
    Tier 3: Workout type + RPE (when pace and HR data are sparse).
    """
```

Supporting work would likely include:

- computing activity-level GAP from splits
- exposing threshold pace from RPI in the shared thresholds helper
- logging TPP/HR disagreements as correlation inputs
- regression coverage across pace-rich and pace-poor athletes

---

## Acceptance Criteria

- [ ] AC11: Tier 0 activates when athlete has RPI and activity has split GAP data
- [ ] AC12: Tier 0 falls through to Tier 1 when RPI is null
- [ ] AC13: Tier 0 falls through to Tier 1 when activity has no split GAP data
- [ ] AC14: Activity-level GAP derived correctly from distance-weighted split averages
- [ ] AC15: TPP thresholds classify correctly: <78% easy, 78-92% moderate, >92% hard
- [ ] AC16: Combined TPP+HR logic upgrades effort when conditions degrade pace
- [ ] AC17: HR does not downgrade a hard pace classification
- [ ] AC18: All TPP-HR disagreements are logged for future correlation input
- [ ] AC19: Founder resolves as Tier 0 when RPI and split GAP data exist
- [ ] AC20: Existing effort-classification tests still pass after Tier 0 addition

---

## Not Shipped

Nothing in this document should be cited as current production behavior.
Until this proposal is explicitly approved and built, the source of truth
for live behavior is:

- `docs/specs/EFFORT_CLASSIFICATION_SPEC.md`
