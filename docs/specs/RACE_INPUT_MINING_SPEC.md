# Race Input Mining — Phase 1D

**Author:** Builder, with founder direction and advisor review

**Problem:** The Racing Fingerprint produces "findings" that restate things
the athlete already knows — race times, PB trajectories, disruption
acknowledgments. The founder called them "things any runner knows since
childhood." The system has been describing products (races) instead of
mining inputs (activities) to find what builds the best products.

**Principle:** Races are products. Activities are inputs. The system's job
is to mine the inputs to find what combination — for THIS athlete only —
builds the best products. Every claim must have receipts (specific
activities). No conventional coaching wisdom. No assumed directions.
N of 1 only.

---

## The bar

**Table stakes:** The system should automatically find patterns that a
coach reviewing the training log would see in 5 minutes. Recurring
workout structures (15-mile runs every Tuesday), workout type
progressions (threshold sessions going from failed to completed),
new stimulus introductions. The athlete already knows these — they
lived them. But the system finding them proves it can read data.
If it can't find the obvious, it can't find the non-obvious.

**The real value:** Patterns the athlete CAN'T see themselves. The
things buried across hundreds of activities and dozens of variables
that no human can hold in their head. Second-order relationships.
Cross-variable correlations. Timing patterns that span months. The
system exists for the things the athlete doesn't know about their
own training — not for restating what they do know.

Table stakes are the proof the engine works. The real value is what
it finds after that.

---

## What exists today

The block_signature on each PerformanceEvent already computes:
- `weekly_volumes_km` — full volume trajectory (NOT USED in analysis)
- `intensity_distribution` — easy/moderate/hard split (NOT USED)
- `peak_volume_km`, `quality_sessions`, `long_run_max_km` (used, but
  compared as single numbers without context)

The Activity model has per-run:
- distance, duration, pace, avg/max HR, elevation gain
- workout_type (easy_run, tempo_run, long_run, interval, race)
- intensity_score (0-100)
- splits with per-mile pace, HR, cadence, GAP
- per-second streams (HR, pace, altitude, cadence)

Existing services NOT wired into fingerprint analysis:
- `pattern_recognition.py` — 28-day trailing context, workout type mix
- `correlation_engine.py` — time-shifted input→output correlations
- `pre_race_fingerprinting.py` — race-day readiness (HRV, sleep, resting HR)
- `causal_attribution.py` — Granger-style analysis

---

## Three layers of analysis

### Layer A: Pre-Race Training Profiles
What mix of training inputs preceded each race output?

### Layer B: Adaptation Curve Detection
How did the athlete respond to specific training stimuli over time?
When did the adaptation click? What race output followed?

### Layer C: Readiness Signal Correlation
What do the athlete's race-day readiness signals (HRV, sleep, resting HR)
actually predict for THIS athlete? No assumed direction — let the data
decide.

---

## Layer A: Pre-Race Training Profiles

### RI-1: Profile Computation

For each confirmed PerformanceEvent, build a training profile from ALL
activities in the preceding 6 weeks (42 days). Also compute a 12-week
(84-day) profile as secondary analysis. Store as `training_profile`
(JSONB) on the PerformanceEvent.

**Dimensions (pruned per advisor review — ~14, not 25):**

```
Volume & Frequency:
  total_volume_km         float   Total distance
  runs_per_week           float   Average runs per week
  rest_days_per_week      float   Average rest days per week
  avg_run_distance_km     float   Average run distance

Long Runs (distance > 20 km / 12.4 mi):
  long_run_count          int     Number of long runs
  long_run_avg_km         float   Average long run distance
  last_long_run_days_before int   Days between last long run and race

Intensity Distribution:
  pct_easy                float   % of runs classified easy
  pct_hard                float   % of runs classified hard
  avg_intensity_score     float   Average intensity score (0-100)

Aerobic Proxies (independent of workout choice):
  avg_easy_pace_km        float   Average pace on easy runs
  avg_easy_hr             float   Average HR on easy runs

Quality Work:
  quality_session_count   int     Tempo + threshold + interval sessions
  last_quality_days_before int    Days between last quality session and race

Volume Shape:
  week_volumes_km         list    Weekly volumes for each of 6 weeks
  volume_trend            str     'increasing', 'decreasing', 'stable', 'peaked'

Context:
  season                  str     'winter', 'spring', 'summer', 'fall'
```

**Removed (per advisor review):**
- `avg_training_hr`, `avg_training_pace_km` — confounded with intensity mix
- `avg_hard_pace_km`, `avg_hard_hr` — circular (faster fitness → faster
  hard pace → better race; this is definitionally true, not a finding)
- `total_elevation_gain_m`, `avg_elevation_per_run_m` — noise unless
  specific hill campaigns exist
- `long_run_total_km`, `long_run_max_km` — redundant with count + avg
- `pct_moderate` — redundant (pct_easy + pct_hard determine it)
- `total_runs` — redundant with runs_per_week

### RI-2: Profile Comparison

Compare profiles across races. Primary analysis within 5K (7 races).
Cross-distance secondary for non-volume dimensions only (timing,
frequency, intensity distribution — not volume, which scales with
race distance).

**Method:**
1. Within each distance category (5K primary), rank races by
   effective_time_seconds. Split into top half and bottom half.
   (Top third / bottom third with middle excluded if N >= 9.)

2. For each dimension, compute separation between groups.

3. Apply **Benjamini-Hochberg FDR correction at 10%** across all
   dimensions tested. This is the primary defense against false
   findings from multiple comparisons. (Codex advisor recommendation.)

4. Additional signal filters after FDR:
   - **Consistency:** Pattern holds for at least 2/3 of races in
     each group.
   - **Outlier resistance:** Removing any single race from either
     group does not flip the finding.
   - **Recency confound detection:** Compute correlation between
     race date and performance. If > 0.8, flag any finding as
     "may reflect fitness progression, not training pattern."
     Present with that flag — let the athlete decide from receipts.

5. **Include residual fitness races.** The founder's two best
   performances were post-disruption. Excluding them throws away
   the most important data. If the training profile before those
   races produces signal, that signal is real — the campaign built
   fitness that survived injury.

---

## Layer B: Adaptation Curve Detection

This is the layer the original spec missed entirely. The founder's
insight: "Adding medium-long runs and threshold focus is what unlocked
my speed. The medium-long runs broke me at first and I couldn't
complete the first few thresholds as prescribed. But right before
the half marathon I was getting them."

The signal isn't in comparing training blocks between races. The
signal is in how the athlete adapted to specific stimuli WITHIN the
training.

### RI-6: Stimulus Introduction Detection

Detect when the athlete introduces a new training stimulus — a workout
type they weren't doing before, or a significant change in frequency/
intensity of an existing type.

**Method:**
1. Compute a rolling 4-week workout type frequency for each type
   (easy, tempo, threshold, interval, long_run, medium_long_run).
   Define medium_long_run as 16-22 km midweek (not weekend long run).

2. Detect introduction points: the first week where a workout type
   appears at >= 1x/week after being absent or < 0.5x/week for the
   prior 4 weeks.

3. Detect frequency changes: a workout type goes from Nx/week to
   >= 1.5Nx/week sustained for 3+ weeks.

### RI-7: Adaptation Curve Tracking

For each workout type the athlete does regularly, track execution
quality over time. **Minimum data requirement:** 6 sessions of a
workout type over 8+ weeks before attempting adaptation curve
analysis. Fewer than 6 sessions can't support changepoint detection.

**Primary adaptation metric — Pace at HR:**
The single most valuable adaptation signal. If the athlete's pace
at HR 135 went from 5:50/km in June to 5:20/km in October, that's
aerobic adaptation they may not have tracked consciously. Compute
across ALL run types — this signal reflects what the training
campaign actually built, independent of workout choice.

**Execution quality metrics (quality sessions only):**
Split ratio measures execution quality only for continuous efforts
— threshold runs, tempo runs, long runs. Easy runs don't have
"execution quality" in the same sense.
- **Continuous efforts (tempo, threshold, long run):** Compare
  first-half splits to second-half splits. Negative split ratio
  (later splits faster) = strong execution. Positive split ratio
  (pace degradation) = struggled.
- **Interval sessions:** Rep-to-rep consistency within work
  portions, not overall first-half/second-half. Split ratio across
  the whole session is meaningless when recovery intervals are slow
  by design.

**Additional metrics:**
- **Completion:** Did the athlete finish the intended distance?
  (Compare to the athlete's typical distance for this workout type.)
- **Recovery cost:** How did the next day's run look? (Pace and HR
  on the following easy run, if one exists.)

**Output per workout type:**
- Time series of execution quality (pace at HR for all types,
  split ratio / rep consistency for quality sessions)
- Trend direction (improving, stable, declining)
- Inflection point: the session (or week) where the trend shifted
  from struggling to executing. Detected by piecewise linear fit or
  changepoint detection on the execution quality time series.

### RI-8: Adaptation → Race Connection

Connect adaptation inflection points to subsequent race outputs.

**Method:**
1. For each detected inflection point (where a workout type went from
   "struggling" to "executing"), find the next race after the inflection.

2. Produce a finding:
   - The workout type that adapted
   - The inflection date
   - The specific sessions showing the before/after (receipts)
   - The race that followed and its result
   - Time between inflection and race

**Example finding:**
"Your threshold sessions showed pace degradation in the final miles
from June through August. Starting in September, your last 4 threshold
sessions held pace throughout. Your half marathon PB came 10 weeks
after the threshold sessions clicked. Here are the sessions: [receipts]"

---

## Layer C: Readiness Signal Correlation

The founder's HRV was 22 on the day he ran a 10K PB. This is counter
to conventional research (high HRV = readiness = better performance).
The system must discover what readiness signals predict for THIS
athlete, not assume direction from research.

### RI-9: Race-Day Readiness Profile

For each race, pull readiness signals from the day of (or day before):
- HRV
- Resting HR
- Sleep duration
- Sleep quality (if available)
- Stress score (if available)

### RI-10: Readiness → Performance Analysis

Analyze each readiness signal against race performance. **No assumed
polarity.** Do not assume high HRV = good.

**Critical nuance:** Simple linear correlation may be misleading.
The founder's data shows PBs at HRV 22 (broken femur, extreme
stress) AND at HRV 30+ (healthy). A Spearman correlation would
find weak/no signal and miss the real pattern: performance may be
INDEPENDENT of readiness state — meaning the athlete can produce
PB output across a wide range of stress levels because their
fitness base is deep enough to override readiness.

That independence IS a finding. "Your race performance doesn't
correlate with your race-day readiness" is genuinely non-obvious
and tells the athlete something about themselves.

**Method:**
1. For each readiness signal with data for >= 5 races, compute
   Spearman rank correlation with performance.
2. Three possible outcomes:
   - Strong correlation (|r| > 0.5, p < 0.10): surface it, with
     direction. If counter to conventional research, note that.
   - No correlation (|r| < 0.3): that IS a finding if the signal
     is one that conventionally predicts performance (e.g., HRV).
     "Your race results don't depend on your race-day HRV" tells
     the athlete their fitness base overrides readiness state.
   - Insufficient data (< 5 races with signal): store data, don't
     attempt analysis. Surface: "2 more races with HRV data would
     let the system analyze your readiness patterns."
3. Receipts: list each race with its readiness value and result.

**What this layer is really looking for:** Not "what predicts your
races" but "what matters and what doesn't for YOU." If training
inputs (Layer A/B) predict race quality but readiness signals don't,
that tells the athlete: your race outcomes are built in training,
not on race day. That's a real insight.

---

## Receipt Generation (applies to all layers)

Every finding references specific activities or data points. A finding
without receipts is a claim. A finding with receipts is evidence.

**Receipt format:**
```json
{
  "layer": "A|B|C",
  "finding_type": "string",
  "sentence": "Human-readable finding",
  "receipts": {
    "activities": [
      {
        "date": "2025-09-15",
        "type": "threshold",
        "distance_km": 12.0,
        "pace_min_km": 4.35,
        "avg_hr": 165,
        "split_ratio": 0.98,
        "notes": "held pace throughout"
      }
    ],
    "races": [
      {
        "date": "2025-11-29",
        "distance": "half_marathon",
        "time": "1:27:14",
        "rpi": 92.5
      }
    ],
    "readiness": [
      {
        "date": "2025-12-13",
        "hrv": 22,
        "resting_hr": 48,
        "race_result": "39:39 10K PB"
      }
    ]
  }
}
```

---

## Anti-Pattern Suppression

Suppress findings that match any of these:

1. **Restating known facts.** "You ran more before your better races."
2. **Universal coaching wisdom.** "You tapered before your best races."
3. **Obvious preparation scaling.** "You ran higher volume before your
   half marathon than before your 5K."
4. **Insufficient separation.** Differences that don't survive FDR
   correction at 10%.
5. **Outlier-driven.** Removing one race flips the finding.
6. **Condition-confounded.** Training differences explained by race
   distance or seasonal differences (unless within same distance).
7. **Recency confound.** If all best races are recent and all worst
   are early, flag as potential fitness progression artifact.
8. **Seasonal confound.** If all best races are fall and all worst
   are summer, the finding may reflect weather, not training.
9. **Circular dimensions.** If the "input" is a proxy for the output
   itself (e.g., hard session pace predicting race pace).
10. **Volume as proxy for health.** If the athlete's highest-volume
   blocks are also their healthiest periods and lowest-volume blocks
   are injury-affected, then "more volume = better race" is really
   "being healthy = better race." The receipts should make this
   visible — if all low-volume pre-race periods contain injury gaps,
   the finding is about health, not volume strategy.

---

## Honest Gaps

When the data cannot distinguish what mattered, say so.

"Your 5K fingerprint is emerging — 7 races give enough signal to see
patterns. Your half marathon needs 2-3 more races before the system
can distinguish what training built your best one. Your 10K profile
is suggestive but not yet reliable."

This turns an honest gap into a reason to keep racing and using the
product. It's not a cop-out — it's the system telling the athlete
what additional data would sharpen the picture.

---

## Architecture

**New service:** `services/race_input_analysis.py`
- `compute_training_profile(event_id, db)` → dict (profile)
- `detect_adaptation_curves(athlete_id, db)` → list of curves
- `correlate_readiness_signals(athlete_id, db)` → list of correlations
- `mine_race_inputs(athlete_id, db)` → combined findings with receipts

**New model field:** `training_profile` (JSONB, nullable) on
PerformanceEvent (alongside existing `block_signature` and
`campaign_data`)

**Integration:** `mine_race_inputs` is called as Layer 6 in
`extract_fingerprint_findings`. Existing Layers 1-5 are reviewed
for whether they add value. Trajectory findings (Layer 5) that just
restate known times should be suppressed if Layer 6 produces real
findings.

---

## Gates

### Gate H: Profile Accuracy
- Training profiles computed for all confirmed races
- Spot-check 3 profiles: activity counts, volume, long run counts
  match what the founder remembers
- Adaptation curves detected for threshold and medium-long run types
- No crashes, no missing data

### Gate I: Finding Quality (HUMAN GATE)
- Present all surviving findings WITH RECEIPTS to the founder
- The founder examines the receipts and says either:
  - "That's real — I didn't know that about my training" → PASS
  - "That's obvious / wrong / noise" → finding gets killed
- If zero findings survive Gate I, that's an honest result
- The system does not hallucinate patterns that don't exist

---

## What this spec does NOT do

- Does not make recommendations ("you should do X")
- Does not reference coaching literature or general best practices
- Does not assume conventional direction for any metric
- Does not interpret WHY a pattern exists — only that it exists
- Does not require a minimum number of findings to pass
- Does not claim patterns from noise — silence is an acceptable output
