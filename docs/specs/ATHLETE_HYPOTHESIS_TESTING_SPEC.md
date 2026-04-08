# Athlete Hypothesis Testing — "I Have a Theory"

**Date:** April 5, 2026
**Origin:** External research session (Anthropic) + founder reaction
**Status:** Scoped, not scheduled
**Depends on:** Correlation engine (L1-L4 ✅), Coach tools, CorrelationFinding persistence

---

## The Insight

The correlation engine discovers patterns autonomously. The athlete has no
way to aim it. But serious athletes think in hypotheses constantly:

- "I think I run better when I do strides the day before intervals"
- "I think my long runs are better when I sleep more than 7 hours two nights before"
- "I think morning runs are faster for me than afternoon runs"
- "I think cutting back strength training the week before a race helps"

These are testable claims against the athlete's own data. The engine
already has the statistical machinery. This feature gives the athlete
the trigger.

---

## Why This Matters

The founder's reaction: "This is how I think and what would make me be
here like I was glued to it."

The athlete becomes a collaborator in their own science. Their hypotheses
live alongside the system's autonomous discoveries in the Manual. The
journey of watching evidence accumulate is the stickiness — not the
final verdict.

An athlete watching 4 out of 6 observations confirm their hypothesis
is not leaving this product. Ever.

---

## Core Concept

The athlete states a hypothesis. The system:

1. **Accepts and tracks** — Creates an `AthleteHypothesis` record
2. **Tags evidence** — As relevant activity pairs occur, they're matched
3. **Shows a living evidence board** — Updated after every relevant observation
4. **Progresses toward confirmation or rejection** — With honest uncertainty at every stage
5. **Graduates to the Manual** — Confirmed hypotheses become findings alongside engine-discovered ones

---

## Data Model

```
AthleteHypothesis
  id: UUID
  athlete_id: FK → Athlete
  hypothesis_text: Text          -- "I run better when I do strides the day before intervals"
  input_signal: Text             -- Parsed or athlete-selected: e.g., "strides_day_before"
  input_condition: Text          -- "present" | "above_threshold" | "below_threshold"
  input_threshold: Float?        -- e.g., 7.0 (for sleep > 7h)
  output_metric: Text            -- e.g., "efficiency" | "pace_threshold"
  time_lag_days: Integer          -- e.g., 1
  status: Text                   -- "tracking" | "early_signal" | "confirmed" | "rejected" | "insufficient_data"
  observations_for: Integer      -- Count of observations supporting
  observations_against: Integer  -- Count of observations against
  observations_total: Integer    -- Total relevant observations
  current_effect_size: Float?    -- Running Cohen's d or correlation
  confidence_note: Text?         -- Human-readable: "4 of 6 support this — too early to confirm"
  created_at: DateTime
  last_evidence_at: DateTime?
  confirmed_at: DateTime?
  source: Text                   -- "athlete" (vs "engine" for auto-discovered)
```

---

## Entry Points

### 1. Coach Chat — "I have a theory"

The athlete tells the coach: "I think I run better after strides."
The coach:
- Parses the hypothesis into input/output/lag
- Confirms the interpretation: "I'll track whether doing strides the day
  before your quality sessions correlates with better interval efficiency.
  I'll check after every relevant pair."
- Creates the `AthleteHypothesis` record
- Uses existing coach tools to check historical data for any early signal

### 2. Manual Page — "Test a theory" button

A structured form:
- "I think [input] affects my [output]"
- Dropdowns populated from the 70 correlation engine inputs and 9 outputs
- Optional: threshold, lag, condition
- Submit creates the hypothesis and starts tracking

### 3. Finding Card — "I want to test the opposite"

On any confirmed finding in the Manual, a "What if..." link that
lets the athlete propose a counter-hypothesis or a refinement.

---

## Evidence Board (Living Display)

Lives on the Manual page alongside engine-discovered findings.
Separate section: "Your Theories."

Each hypothesis card shows:

```
┌─────────────────────────────────────────────────┐
│ YOUR THEORY                                      │
│ "Strides the day before intervals help"          │
│                                                   │
│ ████████░░░░  4 of 6 support (67%)               │
│                                                   │
│ Status: Early signal — consistent but needs       │
│ more observations before confirmation             │
│                                                   │
│ Last evidence: Apr 3 — interval efficiency was    │
│ 8% above baseline after Tuesday strides           │
│                                                   │
│ Next test opportunity: Apr 10 (intervals planned) │
│                                                   │
│ Started tracking: Mar 15 · 6 observations         │
└─────────────────────────────────────────────────┘
```

### Status Progression

| Status | Condition | Display |
|--------|-----------|---------|
| `tracking` | < 4 observations | "Collecting evidence..." |
| `early_signal` | 4-9 observations, >60% consistent | "Early signal — [X] of [Y] support this" |
| `confirmed` | ≥ 10 observations, p < 0.05, \|r\| ≥ 0.3 | "Confirmed — this is real for you" |
| `rejected` | ≥ 10 observations, effect not significant | "Not supported — no consistent pattern found" |
| `insufficient_data` | > 6 months, < 10 observations | "Not enough test opportunities yet" |

### Honest Uncertainty at Every Stage

- At n=2: "Two observations — far too early to draw conclusions"
- At n=5: "5 of 5 support this, but small samples can be deceiving. Need more data."
- At n=8, 6 supporting: "The signal is consistent (75%) but hasn't reached statistical confirmation yet"
- At n=12, p < 0.05: "Confirmed. This pattern is statistically significant in your data."

The system never overclaims. Suppression over hallucination applies here too.

---

## Engine Integration

### Observation Matching

After each activity sync, check all `tracking` hypotheses for the athlete:

1. Does today's activity match the output metric? (e.g., was this an interval session?)
2. Does the input condition exist in the lag window? (e.g., were strides done yesterday?)
3. If both: compute the output metric value, compare to baseline, record observation

Uses existing correlation engine aggregation functions. No new statistical
machinery needed.

### Graduation to CorrelationFinding

When a hypothesis reaches `confirmed`:
- Create a `CorrelationFinding` with `discovery_source = "athlete_hypothesis"`
- Links to the `AthleteHypothesis` for provenance
- Enters the normal finding lifecycle (can strengthen, resolve, close)
- Appears in the Manual alongside engine-discovered findings
- The athlete's theory sits next to the system's discoveries as an equal

### Cross-Reference with AutoDiscovery

When AutoDiscovery finds a pattern that matches an active hypothesis:
- Flag it: "The system independently discovered the same pattern you hypothesized"
- Accelerate confirmation if both athlete observation and engine correlation agree

---

## What This Does NOT Do

- Does not let athletes fabricate findings (statistical gates still apply)
- Does not bypass Bonferroni correction for confirmation
- Does not surface unconfirmed hypotheses as findings in the briefing
- Does not give the athlete control over the engine's autonomous discovery
- Does not require immediate results (honest about timelines)

---

## Build Estimate

| Component | Effort |
|-----------|--------|
| `AthleteHypothesis` model + migration | Small |
| Coach parsing (hypothesis → structured record) | Medium — prompt engineering + validation |
| Observation matcher (post-sync hook) | Medium — reuses correlation aggregation |
| Evidence board UI on Manual page | Medium |
| Graduation to CorrelationFinding | Small — upsert logic exists |
| Manual "Test a theory" form | Small |
| Coach tool: `check_hypothesis_status` | Small |
| AutoDiscovery cross-reference | Small |

Total: ~2 focused sessions. No new statistical machinery. Heavy reuse
of existing correlation engine, finding persistence, and Manual rendering.

---

## The Product Moment

An athlete opens their Manual. They see:

**Your Science**
- 86 confirmed findings (engine-discovered)
- 3 theories in progress
- 1 theory confirmed last week: "Strides before intervals → confirmed.
  Your interval efficiency is 6% higher on average when you include
  strides the day before. 12 observations, p = 0.03."

Their hypothesis, confirmed by their data, living next to the system's
autonomous discoveries. They didn't just consume intelligence — they
contributed to it. That's not a feature. That's ownership.
