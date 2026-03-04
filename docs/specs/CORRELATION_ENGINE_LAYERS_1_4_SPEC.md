# Correlation Engine Layers 1–4 — Architectural Spec

**Date:** March 3, 2026
**Status:** Approved by founder — ready for build
**Roadmap:** `docs/specs/CORRELATION_ENGINE_ROADMAP.md`
**Depends on:** Effort classification (shipped), confounder control
(shipped), daily correlation sweep (shipped)

---

## What exists today

The correlation engine finds bivariate Pearson correlations between
single inputs and single outputs at time-shifted lags (0–7 days).
Statistical gates: |r| >= 0.3, p < 0.05, n >= 10. Partial correlation
controls for confounders. Direction validation suppresses
counterintuitive findings. Daily sweep covers 9 output metrics.

Findings are stored in `CorrelationFinding` with reproducibility
tracking (`times_confirmed`).

This tells the athlete: "motivation correlates with efficiency at a
2-day lag." Useful. But it doesn't tell them:

- At what point does sleep stop mattering? (threshold)
- Does bad sleep hurt more than good sleep helps? (asymmetry)
- Does sleep affect efficiency directly, or through resting HR? (cascade)
- How many days does the sleep effect last? (decay)

These four layers answer those questions. Each one transforms a
confirmed correlation from a statistical fact into actionable
knowledge.

---

## Layer 1: Threshold Detection

### The question

"At what value does this input's effect change character?"

Sleep might have no measurable effect above 6.5 hours but dramatic
effects below. Training load might be fine until it crosses a personal
ceiling. The relationship isn't linear — it has a breakpoint.

### Method

For each confirmed correlation finding (is_active, times_confirmed >= 3):

1. Collect the aligned (input, output) data pairs at the finding's
   confirmed lag.
2. Sort by input value.
3. Test candidate thresholds by splitting the data at each unique
   input value:
   - Compute Pearson r for the data below the split point
   - Compute Pearson r for the data above the split point
   - Compute the difference in r between the two segments
4. The threshold is the split point that maximizes the absolute
   difference in r between segments, subject to:
   - Each segment has at least 5 data points (n >= 5)
   - The difference in |r| between segments is >= 0.2
   - At least one segment has |r| >= 0.3 (a real relationship exists
     on at least one side)

If no split point meets these criteria, the relationship is
approximately linear and no threshold exists. That's a valid result —
store it.

### Output

New fields on `CorrelationFinding`:

```python
threshold_value = Column(Float, nullable=True)
threshold_direction = Column(Text, nullable=True)  # "below_matters" or "above_matters"
r_below_threshold = Column(Float, nullable=True)
r_above_threshold = Column(Float, nullable=True)
n_below_threshold = Column(Integer, nullable=True)
n_above_threshold = Column(Integer, nullable=True)
```

### What the athlete sees

- "Your sleep cliff is at 6.2 hours. Below that, efficiency drops
  measurably (r = -0.71). Above it, sleep has no significant effect
  (r = -0.08)."
- "Training load above 45 miles/week shows no additional efficiency
  gain (r = 0.04). Below 45, more volume clearly helps (r = 0.52)."
- "No threshold detected — your motivation-to-efficiency relationship
  is approximately linear across your observed range."

### Implementation

Add `detect_threshold()` to `services/correlation_engine.py`:

```python
def detect_threshold(
    input_data: List[Tuple[datetime, float]],
    output_data: List[Tuple[datetime, float]],
    lag_days: int = 0,
    min_segment_size: int = 5,
    min_r_difference: float = 0.2,
) -> Optional[Dict]:
    """
    Find the input value where the correlation changes character.

    Returns None if no threshold detected (linear relationship).
    Returns dict with:
      threshold_value, threshold_direction,
      r_below, r_above, n_below, n_above
    """
```

Wire into the daily correlation sweep: after a finding is confirmed
(times_confirmed >= 3), run `detect_threshold()` and store the result.
Threshold detection is not run on every sweep — only when a finding
crosses the confirmation threshold or is reconfirmed.

### Known limitation: unobserved range

Threshold detection requires sufficient data on both sides of the
candidate split point. Athletes with consistently healthy inputs may
not have enough below-baseline observations to detect thresholds that
exist at extreme values. An athlete who never sleeps below 5.8 hours
cannot reveal a cliff at 5.2 hours. The system correctly returns "no
threshold detected," but for the wrong reason — the data range doesn't
include the dangerous zone, not because the cliff doesn't exist.

The coaching implication differs: "no threshold — linear relationship"
means small changes produce proportional effects. "No threshold — data
range may not include cliff" means the relationship looks linear
because the athlete hasn't been in the danger zone. The system cannot
distinguish these cases from data alone. This is acceptable — the
absence of a detected threshold does not rule out a cliff outside the
observed range, and the spec should never claim otherwise.

### Computational cost

Low. For each confirmed finding, the threshold scan is O(n) where n is
the number of aligned data points (typically 30–90 for a 90-day
window). One Pearson correlation per candidate split, each O(n). Total:
O(n²) per finding, which for n=90 is trivial.

---

## Layer 2: Asymmetric Response Detection

### The question

"Does a bad input hurt more than a good input helps?"

If sleeping below baseline costs 3x the efficiency that sleeping above
baseline gains, the coaching recommendation changes from "sleep more"
to "never sleep less."

### Method

For each confirmed correlation finding:

1. Compute the athlete's personal baseline for the input variable
   (median over the analysis window).
2. Split the aligned data into two groups:
   - Below baseline: data points where input < median
   - Above baseline: data points where input >= median
3. Compute the regression slope on each side of the baseline:
   - `effect_below` = slope of (input → output) for below-baseline points
   - `effect_above` = slope of (input → output) for above-baseline points
   - These slopes measure response sensitivity: how much the output
     changes per unit of input change in each direction.
4. Statistical test: two-sample t-test between below-baseline and
   above-baseline output values. If p >= 0.1, report as "symmetric"
   regardless of slope ratio (relaxed threshold because we're
   subdividing already-significant data).
5. Compute asymmetry ratio: `|effect_below| / |effect_above|`
   - Ratio > 2.0: strongly asymmetric — negative input is
     disproportionately harmful
   - Ratio 0.67–1.5: approximately symmetric
   - Ratio < 0.67: inverted asymmetry — positive input is
     disproportionately helpful

**Design note (production):** The original spec proposed using mean
output deviations from overall mean. This produces ratio = 1.0 for
equal-sized groups (which median split always creates). The shipped
implementation uses regression slopes instead, which correctly
captures response sensitivity per direction.

### Output

New fields on `CorrelationFinding`:

```python
asymmetry_ratio = Column(Float, nullable=True)
asymmetry_direction = Column(Text, nullable=True)  # "negative_dominant", "positive_dominant", "symmetric"
effect_below_baseline = Column(Float, nullable=True)
effect_above_baseline = Column(Float, nullable=True)
baseline_value = Column(Float, nullable=True)  # the median used
```

### What the athlete sees

- "Bad sleep costs you 2.8x more than good sleep gains. Nights below
  6.5 hours drop your efficiency by 0.0031. Nights above 7.5 hours
  improve it by only 0.0011. Protect the floor."
- "Stress is approximately symmetric for you. High stress days and low
  stress days affect completion rate roughly equally."
- "Motivation is asymmetric in the positive direction — high motivation
  days boost your efficiency 2.1x more than low motivation days hurt
  it. Finding ways to stay engaged matters more than avoiding bad days."

### Implementation

Add `detect_asymmetry()` to `services/correlation_engine.py`:

```python
def detect_asymmetry(
    input_data: List[Tuple[datetime, float]],
    output_data: List[Tuple[datetime, float]],
    lag_days: int = 0,
    min_segment_size: int = 5,
) -> Optional[Dict]:
    """
    Detect whether the negative effect of an input is larger than the
    positive effect.

    Returns None if insufficient data.
    Returns dict with:
      asymmetry_ratio, asymmetry_direction,
      effect_below_baseline, effect_above_baseline, baseline_value
    """
```

Wire into the daily sweep alongside threshold detection. Same trigger:
confirmed findings only.

### Computational cost

Trivial. One median, two means, one t-test per finding.

---

## Layer 3: Cascade Detection (Mediation Analysis)

### The question

"Does A affect C directly, or through B?"

Sleep → efficiency is a confirmed correlation. But is it direct? Or
does sleep → resting HR → efficiency, with resting HR as the mediator?
The answer tells the athlete where to intervene.

### Method

`compute_partial_correlation()` already exists and is in production.
Mediation analysis IS partial correlation pointed at a different
question.

For each confirmed finding (input A → output C):

1. Identify candidate mediators: all other input variables that:
   - Correlate with A (the original input) at |r| >= 0.3
   - Correlate with C (the output) at |r| >= 0.3
   - Are not A itself
2. For each candidate mediator B:
   - Compute the direct effect: `partial_r(A, C | B)` — the
     correlation between A and C after removing B's influence
   - Compute the indirect effect: `r(A,C) - partial_r(A,C|B)`
   - Mediation ratio: `indirect / total = 1 - (partial_r / r)`
3. If the mediation ratio > 0.4 (B explains more than 40% of the A→C
   relationship), B is a significant mediator.
4. If `partial_r(A,C|B)` drops below MIN_CORRELATION_STRENGTH (0.3),
   B fully mediates the relationship — A does not affect C directly.

### Output

New model: `CorrelationMediator` (one row per mediator per finding):

```python
class CorrelationMediator(Base):
    __tablename__ = "correlation_mediator"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    finding_id = Column(UUID, ForeignKey("correlation_finding.id"), nullable=False, index=True)
    mediator_variable = Column(Text, nullable=False)
    direct_effect = Column(Float, nullable=False)     # partial_r(A,C|B)
    indirect_effect = Column(Float, nullable=False)   # r(A,C) - partial_r
    mediation_ratio = Column(Float, nullable=False)   # indirect / total
    is_full_mediation = Column(Boolean, default=False) # partial_r < 0.3
    detected_at = Column(DateTime(timezone=True), server_default=func.now())
```

### What the athlete sees

- "Sleep affects your efficiency, but mostly through resting heart rate.
  When resting HR is accounted for, the direct sleep→efficiency link
  drops from r=0.62 to r=0.18. Whatever normalizes your resting HR
  after bad sleep — easy movement, hydration, breathing — is the real
  lever."
- "Motivation affects efficiency directly (partial r=0.54 after
  controlling for session stress). This isn't mediated through working
  harder — you actually run more efficiently when motivated, independent
  of how hard the session was."

### Implementation

Add `detect_mediators()` to `services/correlation_engine.py`:

```python
def detect_mediators(
    finding: CorrelationFinding,
    inputs: Dict[str, List[Tuple[datetime, float]]],
    outputs: List[Tuple[datetime, float]],
    db: Session,
) -> List[Dict]:
    """
    For a confirmed finding (A → C), identify variables that mediate
    the relationship.

    Uses compute_partial_correlation() — already in production.

    Returns list of mediator dicts:
      mediator_variable, direct_effect, indirect_effect,
      mediation_ratio, is_full_mediation
    """
```

Wire into the daily sweep. For each confirmed finding, test all other
available input variables as candidate mediators. Store results in
`CorrelationMediator`.

### Computational cost

Moderate. For each confirmed finding, test N candidate mediators (where
N is the number of input variables, typically 15–20). Each test is one
call to `compute_partial_correlation()`, which is O(n) where n is the
aligned data size. Total: O(N × n) per finding. For 10 confirmed
findings × 20 candidates × 90 data points = ~18,000 operations. Well
within a daily sweep budget.

---

## Layer 4: Lagged Decay Curves

### The question

"How long does this input's effect last?"

The engine currently finds the peak lag — "sleep affects efficiency
with a 1-day lag." But the effect doesn't turn on and off at a single
day. It has a curve: 8% effect at day 1, 5% at day 2, 2% at day 3,
nothing by day 4. The full curve is more actionable than a single
number.

### Method

The engine already tests multiple lags (0–7 days) via
`find_time_shifted_correlations()`. Instead of selecting only the peak
lag, capture the full lag profile:

For each confirmed finding:

1. Compute Pearson r at every lag from 0 to 7 days (already done
   during the sweep).
2. Store the full lag profile: `[r_lag0, r_lag1, ..., r_lag7]`
3. Fit an exponential decay to the significant portion of the profile:
   - Start from the peak lag
   - The decay half-life is the number of days until |r| drops to
     half of the peak |r|
   - If the profile doesn't decay monotonically from the peak, the
     effect is not a simple decay — flag as "complex" and store the
     raw profile only

### Output

New fields on `CorrelationFinding`:

```python
lag_profile = Column(JSONB, nullable=True)  # [r_lag0, r_lag1, ..., r_lag7]
decay_half_life_days = Column(Float, nullable=True)
decay_type = Column(Text, nullable=True)  # "exponential", "complex", "sustained"
```

Decay types:
- **exponential**: r decays monotonically from peak. Half-life is
  meaningful. "Your sleep effect lasts ~2.8 days."
- **sustained**: r stays significant across 4+ lags. No meaningful
  decay. "Sleep affects your efficiency persistently — the effect
  doesn't fade within a week."
- **complex**: r is non-monotonic (rises, falls, rises again). Store
  raw profile only. "The sleep-efficiency relationship has a complex
  time profile — the effect peaks at day 1, fades by day 3, and
  reappears at day 5."

### What the athlete sees

- "Your sleep effect decays over approximately 2.8 days. A bad night
  tonight will affect your runs through Wednesday. Protect your sleep
  for 3 nights before a key session."
- "Motivation's effect on efficiency is sustained — it doesn't decay
  within the 7-day window. High motivation produces better running
  for the entire period we can measure."
- "Stress affects your completion rate only on the same day (r=-0.55
  at lag 0, r=-0.12 at lag 1). Tomorrow is a clean slate."

### Implementation

Add `compute_decay_curve()` to `services/correlation_engine.py`:

```python
def compute_decay_curve(
    input_data: List[Tuple[datetime, float]],
    output_data: List[Tuple[datetime, float]],
    peak_lag: int,
    max_lag: int = 7,
    min_samples: int = 10,
) -> Optional[Dict]:
    """
    Compute the full lag profile and fit a decay curve.

    Returns None if insufficient data.
    Returns dict with:
      lag_profile: list of r values at each lag
      decay_half_life_days: float or None
      decay_type: "exponential", "sustained", or "complex"
    """
```

**Key implementation detail:** The lag profile data is already computed
inside `find_time_shifted_correlations()` — it tests every lag and
keeps only the best. Modify the function to return all tested lags (not
just the best), or recompute them in `compute_decay_curve()`. The
former is more efficient; the latter is simpler and doesn't touch
existing logic. Recommend the latter for initial implementation.

Wire into the daily sweep alongside threshold and asymmetry. Same
trigger: confirmed findings only.

### Computational cost

Low. The lag correlations are already computed during the sweep. This
layer adds the curve fitting, which is O(max_lag) per finding.

---

## Database Migration

One Alembic migration for all four layers:

```python
# correlation_layers_1_4_001
# New columns on CorrelationFinding
op.add_column('correlation_finding', sa.Column('threshold_value', sa.Float(), nullable=True))
op.add_column('correlation_finding', sa.Column('threshold_direction', sa.Text(), nullable=True))
op.add_column('correlation_finding', sa.Column('r_below_threshold', sa.Float(), nullable=True))
op.add_column('correlation_finding', sa.Column('r_above_threshold', sa.Float(), nullable=True))
op.add_column('correlation_finding', sa.Column('n_below_threshold', sa.Integer(), nullable=True))
op.add_column('correlation_finding', sa.Column('n_above_threshold', sa.Integer(), nullable=True))

op.add_column('correlation_finding', sa.Column('asymmetry_ratio', sa.Float(), nullable=True))
op.add_column('correlation_finding', sa.Column('asymmetry_direction', sa.Text(), nullable=True))
op.add_column('correlation_finding', sa.Column('effect_below_baseline', sa.Float(), nullable=True))
op.add_column('correlation_finding', sa.Column('effect_above_baseline', sa.Float(), nullable=True))
op.add_column('correlation_finding', sa.Column('baseline_value', sa.Float(), nullable=True))

op.add_column('correlation_finding', sa.Column('lag_profile', postgresql.JSONB(), nullable=True))
op.add_column('correlation_finding', sa.Column('decay_half_life_days', sa.Float(), nullable=True))
op.add_column('correlation_finding', sa.Column('decay_type', sa.Text(), nullable=True))

# New table for mediators
op.create_table('correlation_mediator',
    sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column('finding_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('correlation_finding.id'), nullable=False),
    sa.Column('mediator_variable', sa.Text(), nullable=False),
    sa.Column('direct_effect', sa.Float(), nullable=False),
    sa.Column('indirect_effect', sa.Float(), nullable=False),
    sa.Column('mediation_ratio', sa.Float(), nullable=False),
    sa.Column('is_full_mediation', sa.Boolean(), default=False, nullable=False),
    sa.Column('detected_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
)
op.create_index('ix_mediator_finding', 'correlation_mediator', ['finding_id'])
```

---

## Wiring into the Daily Sweep

The daily sweep (`run_daily_correlation_sweep`) currently runs
`analyze_correlations()` for each output metric and persists findings.

After the sweep persists findings, add a second pass for confirmed
findings only:

```python
confirmed = db.query(CorrelationFinding).filter(
    CorrelationFinding.athlete_id == athlete_id,
    CorrelationFinding.is_active == True,
    CorrelationFinding.times_confirmed >= 3,
).all()

for finding in confirmed:
    # Rehydrate the aligned data for this finding
    input_data = inputs[finding.input_name]
    output_data = outputs_for_metric[finding.output_metric]

    # Layer 1: Threshold
    threshold = detect_threshold(input_data, output_data, finding.time_lag_days)
    if threshold:
        finding.threshold_value = threshold["threshold_value"]
        finding.threshold_direction = threshold["threshold_direction"]
        finding.r_below_threshold = threshold["r_below"]
        finding.r_above_threshold = threshold["r_above"]
        finding.n_below_threshold = threshold["n_below"]
        finding.n_above_threshold = threshold["n_above"]

    # Layer 2: Asymmetry
    asymmetry = detect_asymmetry(input_data, output_data, finding.time_lag_days)
    if asymmetry:
        finding.asymmetry_ratio = asymmetry["asymmetry_ratio"]
        finding.asymmetry_direction = asymmetry["asymmetry_direction"]
        finding.effect_below_baseline = asymmetry["effect_below_baseline"]
        finding.effect_above_baseline = asymmetry["effect_above_baseline"]
        finding.baseline_value = asymmetry["baseline_value"]

    # Layer 3: Cascade (mediators)
    mediators = detect_mediators(finding, inputs, output_data, db)
    # Persist mediators to CorrelationMediator table

    # Layer 4: Decay curve
    decay = compute_decay_curve(input_data, output_data, finding.time_lag_days)
    if decay:
        finding.lag_profile = decay["lag_profile"]
        finding.decay_half_life_days = decay["decay_half_life_days"]
        finding.decay_type = decay["decay_type"]

db.commit()
```

This second pass runs only on confirmed findings (small set) and only
during the daily sweep (not on-demand API calls). Computational cost
is bounded and predictable.

---

## What the Progress Page Shows

Each layer enriches the existing "What the Data Proved" section:

**Without layers (current):**
> High Sleep improves Efficiency within 2 days — EMERGING 1x

**With layers:**
> **Sleep and your efficiency**
> Your sleep cliff is at 6.2 hours. Below that, efficiency drops
> sharply (r = -0.71). Above it, sleep barely matters (r = -0.08).
> Bad sleep costs you 2.8x more than good sleep gains — protect the
> floor, don't chase the ceiling. The effect lasts approximately 2.8
> days. A bad night tonight affects your runs through Wednesday.
> Sleep affects efficiency mostly through resting heart rate — whatever
> normalizes your resting HR after poor sleep is the real lever.

That paragraph is assembled entirely from the four layer outputs —
threshold value, asymmetry ratio, decay half-life, and mediator
variable. No LLM needed for the core content. The LLM can refine the
language, but the facts are deterministic.

---

## Build Order

Each layer is independent and can be built and shipped separately.
The recommended order is:

1. **Layer 1 (Threshold)** — highest immediate value, simplest
   implementation
2. **Layer 2 (Asymmetry)** — changes coaching framing, trivial
   computation
3. **Layer 4 (Decay)** — leverages data already computed, simple
   curve fit
4. **Layer 3 (Cascade)** — most complex, uses existing partial
   correlation function but requires candidate selection logic

Layers 1 and 2 can be shipped together in one commit if desired.
Layer 3 requires a new database table and is best as a separate commit.

---

## Acceptance Criteria

### Layer 1: Threshold Detection
- [ ] AC1: `detect_threshold()` returns None for linear relationships
- [ ] AC2: `detect_threshold()` identifies the correct split point for
      synthetic data with a known breakpoint
- [ ] AC3: Threshold stored on CorrelationFinding when detected
- [ ] AC4: Minimum segment size enforced (n >= 5 per side)
- [ ] AC5: Threshold detection runs only on confirmed findings
      (times_confirmed >= 3)

### Layer 2: Asymmetric Response Detection
- [ ] AC6: `detect_asymmetry()` returns correct ratio for known
      asymmetric data
- [ ] AC7: `detect_asymmetry()` returns "symmetric" when effects are
      balanced (ratio 0.67–1.5)
- [ ] AC8: Asymmetry stored on CorrelationFinding when detected
- [ ] AC9: Baseline computed as median of input values

### Layer 3: Cascade Detection
- [ ] AC10: `detect_mediators()` identifies known mediator in synthetic
       data (A→B→C where B explains >40% of A→C)
- [ ] AC11: `detect_mediators()` correctly identifies full mediation
       (partial_r drops below 0.3)
- [ ] AC12: Mediators stored in CorrelationMediator table
- [ ] AC13: Only input variables that correlate with both A and C are
       tested as candidates (not exhaustive)

### Layer 4: Decay Curves
- [ ] AC14: `compute_decay_curve()` returns correct lag profile
- [ ] AC15: Exponential decay half-life computed correctly for
       monotonically decaying profiles
- [ ] AC16: "sustained" type detected when r stays significant across
       4+ lags
- [ ] AC17: "complex" type detected for non-monotonic profiles
- [ ] AC18: Lag profile stored as JSONB on CorrelationFinding

### Integration
- [ ] AC19: All four layers run in the daily sweep second pass
- [ ] AC20: Layers only run on confirmed findings (times_confirmed >= 3)
- [ ] AC21: All existing tests pass
- [ ] AC22: Founder's confirmed findings have threshold, asymmetry,
       decay, and mediator data after a full sweep
- [ ] AC23: Migration creates all new columns and the mediator table

---

## What the Four Layers Together Represent

When all four layers are running on a confirmed finding, the system
has a personal dose-response curve for that input. Threshold tells
you where the effect starts. Asymmetry tells you which direction
matters more. Decay tells you how long it lasts. Cascade tells you
the mechanism.

That's not a correlation finding anymore — that's a pharmacokinetic
model of how this specific human responds to a specific input.
Applied to sleep, motivation, stress, HRV. Built from field data,
N=1, continuously updated from the athlete's own history.

The sports science for this exists at the elite level in lab
conditions. Nobody has built it for amateur athletes from real-world
data. That's the moat in a single sentence.

---

## What This Unlocks

Each confirmed correlation transforms from a single sentence
("A correlates with B") into a complete understanding:

- **Where it matters** (threshold)
- **How much it matters in each direction** (asymmetry)
- **What it actually works through** (cascade)
- **How long the effect lasts** (decay)

For the founder with 2 years of data: every confirmed pattern gains
four dimensions of specificity. The Progress page becomes the most
detailed physiological self-knowledge document any amateur athlete
has ever seen.

For the Pre-Race Fingerprint (next build): thresholds define what
values to watch for in the pre-race window. Asymmetry defines which
inputs to protect vs which to optimize. Decay defines how far out
each input matters. Cascades define where to intervene. The
fingerprint becomes actionable instead of observational.

For the Proactive Coach: threshold violations become the trigger.
"Your sleep dropped below your 6.2-hour cliff" is a genuinely useful
proactive message. Without the threshold, the coach can only say
"your sleep was low" — which the athlete already knows.

**Frontend build note:** The paragraph in "What the Progress Page
Shows" is assembled deterministically from four layer outputs. No
LLM is required for the facts — the data tells the story. The LLM
may polish the language, but the threshold value, asymmetry ratio,
decay half-life, and mediator variable are all computed values
rendered directly. The builder must not generate that content with
an LLM call. The intelligence is in the engine, not the narrator.
