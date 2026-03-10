# Correlation Engine — Vision & Roadmap

**Date:** March 3, 2026
**Status:** Founder vision — not yet scoped for build
**Origin:** Founder articulated, advisor annotated

---

## What the engine is

The correlation engine is not a feature. It's a scientific instrument
pointed at a single human. Most sports science was built by pointing
instruments at populations. This does something different — and the
implications go further than what's currently implemented.

---

## What exists today (after effort classification ships)

- Bivariate Pearson correlation, single input → single output
- Time-shifted 0–7 day lags, peak lag selected
- Statistical gates: |r| >= 0.3, p < 0.05, n >= 10
- Confirmation tracking: `times_confirmed` increments on repeated significance
- Partial correlation with confounder control (daily session stress)
- Direction validation with safety gate
- Daily sweep across 9 output metrics
- N=1 effort classification (HR percentile, HRR earned, workout type + RPE)

This finds things like "motivation predicts efficiency 2 days later."
Powerful. But it's still thinking in pairs. One cause, one effect, one
lag. The world doesn't work that way and neither does a human body.

---

## Capability layers (in proposed build order)

### Layer 1: Threshold Detection

**What it does:** Finds the point where a relationship changes character.

Sleep might have no measurable effect until it drops below 6.2 hours,
then effects are dramatic. Training load might be fine until it crosses
a personal ceiling, then adaptation turns to breakdown.

**Method:** Segment the input range into bins. Compute the correlation
within each bin. Find where the coefficient jumps. If the correlation is
flat above 7 hours but steep below 6.5, the threshold is in that gap.

**Output:** A single number per confirmed correlation — the athlete's
personal threshold for that input. "Your sleep cliff is at 6.2 hours."
Population research says 7 hours. Your data says 6.2. That's the N=1
claim made completely specific.

**Why first:** Produces the most immediately actionable output. Changes
behavior tonight. A correlation coefficient never does.

**Data requirement:** Works with existing data depth (~200+ activities).

---

### Layer 2: Asymmetric Response Detection

**What it does:** Detects when the damage from a bad input is larger
than the gain from a good one.

Poor sleep may cost more than good sleep gains. High stress may hurt
more than low stress helps. If the negative effect is 3× the positive
effect, the coaching recommendation changes from "sleep more to perform
better" to "don't sleep less or you'll pay disproportionately."

**Method:** Split the correlation analysis by direction relative to
baseline. Compute the effect magnitude for "input above baseline" and
"input below baseline" separately. Compare magnitudes.

**Output:** An asymmetry ratio for each confirmed correlation. When
asymmetry is significant, the insight framing changes from bidirectional
("sleep affects efficiency") to protective ("protect your sleep floor").

**Why second:** Straightforward extension of existing correlation.
Reframes how every confirmed pattern is communicated on the Progress
page.

**Data requirement:** Works with existing data depth.

---

### Layer 3: Cascade Detection (Mediation Analysis)

**What it does:** Finds chains of causation: A→B→C instead of just A→C.

Poor sleep → elevated resting HR → reduced efficiency. High stress →
poor sleep → reduced completion rate. The intermediate variable tells
you where to intervene.

**Method:** The tool already exists. `compute_partial_correlation()`
is mediation analysis. When partialing out B from the A→C relationship
causes the direct effect to disappear, B mediates the chain. Currently
pointed at confounders (variables to remove). Point it at mediators
(variables to discover).

**Output:** Causal chains with identified mediating variables. "The
sleep→efficiency correlation weakens when resting HR is controlled for
— resting HR mediates the relationship. The lever isn't sleep directly.
It's whatever normalizes resting HR after poor sleep."

**Why third:** Half-built. The partial correlation function exists in
production. This is a configuration change on an existing instrument,
not new infrastructure. The data is already there — resting HR in
GarminDay, sleep in DailyCheckin, efficiency on every activity.

**Data requirement:** Works with existing data depth.

---

### Layer 4: Lagged Decay Curves

**What it does:** Maps the full time profile of an input's effect, not
just the peak lag.

A bad night of sleep might reduce efficiency by 8% the next day, 5% two
days later, 2% three days later, and nothing by day four. The full decay
curve is more useful than "the effect peaks at day 1."

**Method:** The engine already tests multiple lags. Instead of selecting
the peak, fit an exponential decay curve across all tested lags. The
decay half-life becomes a personal parameter.

**Output:** "Your sleep effect decays over approximately 2.8 days." Tells
the athlete exactly how long to protect their sleep before an important
session. More actionable than a single lag number.

**Data requirement:** Works with existing data depth.

---

### Layer 5: Confidence Trajectory

**What it does:** Distinguishes "currently active and strengthening"
from "historically true but possibly stale."

`times_confirmed = 6` could mean six consecutive confirmations this
month or six sporadic confirmations over two years. These are different
confidence states.

**Method:** Track recency-weighted confirmation momentum. For each
finding, record the date of each confirmation. Compute a recency score
that decays over time. A finding confirmed 3 times in the last 30 days
has higher momentum than one confirmed 6 times total with the last
confirmation 4 months ago.

**Output:** Confidence state per finding: "strengthening", "stable",
"weakening", "stale". Findings that are weakening get flagged — the
athlete's physiology may have changed. Findings that are strengthening
get promoted to higher visibility.

**Data requirement:** Works with existing data, improves with time depth.

---

### Layer 6: Rate of Change Correlations (Momentum Effects)

**What it does:** Finds patterns where the trend matters more than the
absolute value.

Three consecutive nights improving from 5.5 to 6.8 hours might predict
performance differently than a stable 6.8 hours. The trend is the
signal, not the value.

**Method:** Compute rolling 3-day and 7-day deltas for each input.
Feed these momentum signals into the correlation sweep as additional
input variables alongside the absolute values.

**Output:** "When your sleep is trending upward for 3+ consecutive days,
your efficiency gain is 40% larger than when sleep is stable at the same
level." The trajectory matters, not just the snapshot.

**Data requirement:** Works with existing data depth.

---

### Layer 7: Interaction Effects

**What it does:** Detects when two inputs combine to produce an outcome
neither produces alone.

What happens when sleep is low AND motivation is high? Does motivation
compensate? What about high training load AND poor sleep AND high stress
simultaneously — the overreaching signature?

**Method:** For each pair of inputs, create an interaction term
(input_A × input_B, or categorize both as high/low and test the 2×2
combinations). Correlate the interaction against outputs.

**Output:** "Your efficiency holds when sleep is low IF motivation is
high. But when both are low simultaneously, efficiency drops more than
either predicts alone."

**Why later:** 10 inputs produce 45 pairwise combinations × 9 outputs
= 405 tests. With 200–400 activities and multiple comparison correction,
many tests will be underpowered. This capability gets better with time
depth. With two years of data, some tests clear. With three years, more.
This is the capability most impossible to shortcut — a competitor needs
years of data to populate it.

**Data requirement:** Benefits from 300+ activities. Improves significantly
with 500+.

---

### Layer 8: Failure Mode Detection

**What it does:** Identifies what constellation of inputs precedes the
athlete's worst performances, injury events, motivation crashes, DNFs.

**Method:** Define "failure events" explicitly — bad race relative to
fitness prediction, DNS, injury-forced rest, motivation crash below
threshold. Run the correlation sweep backward: what were the inputs in
the 7–14 days before each failure event? What pattern recurs?

**Output:** "When you see this combination, something bad happens within
2 weeks." The injury fingerprint concept applied by the correlation
engine rather than manual pattern matching.

**Data requirement:** Requires enough failure events (minimum 3–5) to
establish patterns. Most athletes accumulate these over 12–18 months.

---

### Layer 9: Antagonistic & Synergistic Pair Detection

**What it does:** Finds inputs that push the same output in opposite
directions and measures how they interact.

Stress reduces completion rate. Motivation increases it. When both are
high, does one dominate?

**Method:** For each output, identify input pairs with opposite
direction expectations. Test whether the positive input buffers or
overwhelms the negative input when both are present.

**Output:** "When your motivation is high, high stress only reduces your
completion rate by 20% of its normal effect. Your motivation partially
buffers the stress impact."

**Data requirement:** Similar to interaction effects — 300+ activities.

---

### Layer 10: Seasonal & Circadian Patterns

**What it does:** Detects systematic differences by time of day, season,
or training phase.

Performance may differ morning vs evening, summer vs winter. The
correlation between sleep and efficiency might be stronger during high
training load phases.

**Method:** Add time-of-day and season as contextual dimensions to the
correlation sweep. Test whether correlation coefficients differ
significantly across these dimensions.

**Output:** "Your efficiency is 4% higher on morning runs versus
afternoon runs — confirmed across 40 activities." Or "your
HRV-to-performance correlation is stronger during build phases."

**Data requirement:** Requires 12+ months of data for seasonal patterns.
Time-of-day patterns can emerge sooner.

---

### Layer 11: Adaptive Input Weighting

**What it does:** Lets the engine learn which inputs matter most for
this specific athlete and prioritize accordingly.

Currently all inputs are weighted equally. But the engine knows which
ones are predictive for this athlete. Motivation predicts efficiency.
Soreness predicts pace. HRV predicts completion.

**Method:** Rank inputs by historical predictive power per output.
Run high-priority inputs more frequently with tighter gates.
Deprioritize inputs that have never shown meaningful correlations.

**Output:** The instrument becomes increasingly calibrated to the
subject. The sweep gets smarter over time, not just broader.

**Data requirement:** Requires 6+ months of sweep history to establish
input rankings.

---

### Layer 12: Cross-Athlete Cohort Intelligence

**What it does:** Uses anonymous aggregate patterns across all athletes
to accelerate individual discovery and provide population context.

An individual finding confirmed by 73% of athletes on the platform is
more trustworthy. An individual finding that contradicts the cohort is
more interesting.

**Method:** Run the correlation sweep at both individual and anonymous
cohort levels. When an individual pattern matches the cohort, confidence
gates clear faster. When it contradicts, the contradiction is itself the
finding. "Most athletes show a stress-completion correlation. You don't.
Your completion rate is unusually resilient to high stress."

**Output:** Population context that makes the N=1 discovery more
meaningful, not less. Shows the individual where they sit relative to
the broader pattern.

**Why last:** Requires users. The engine should be designed now to
support it later — but the value arrives with product-market fit and
user growth.

**Business significance:** This is the network effect. Every new user
makes the instrument better for every other user. This is what makes
StrideIQ defensible as a business, not just as a tool.

**Data requirement:** Requires 50+ active athletes for meaningful
cohort patterns.

---

## The deeper architectural possibility

Everything above is still a correlation engine — finding relationships
between variables. The deeper possibility is a personal physiological
model. Not just "A correlates with C" but "here is a dynamic model of
how this body responds to inputs, derived entirely from this athlete's
own data."

A model that can simulate. Given planned training load, expected sleep,
predicted stress — what does the model predict for efficiency, completion
rate, race performance in 3 weeks?

That's not a feature. That's a different category of product.

The correlation engine as it exists is the foundation. Every confirmed
finding, every interaction effect, every threshold, every decay curve —
each one is a parameter in that model. The more data arrives, the more
accurate the model becomes, the more irreplaceable the product becomes.

Nobody else is building this for amateur athletes. The sports science
exists. The data infrastructure exists. The gap is someone who cares
enough to do it properly for one person at a time.

---

## Design principles (non-negotiable, all layers)

1. **The athlete decides, the system informs.** No prescription. No
   automation of training decisions. Present findings with evidence.
2. **N=1 first, always.** Individual data drives every finding. Cohort
   data provides context, never overrides.
3. **Suppression over hallucination.** If a finding doesn't clear the
   statistical gate, it doesn't surface. Silence is better than noise.
4. **The statement must be true from the data that exists.** No claims
   about ceilings, limits, or parameters the data doesn't contain.
5. **Every finding is explorable.** Click through to the evidence —
   the scatter plot, the instances, the confidence trajectory.
6. **The instrument improves with use.** More data → more findings →
   higher confidence → better calibration. Time is the moat.
