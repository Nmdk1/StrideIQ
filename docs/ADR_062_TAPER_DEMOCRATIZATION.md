# ADR-062: Taper Democratization

**Status:** Accepted  
**Date:** 2026-02-12  
**Phase:** 1D  
**Approved and Implemented**

---

## Context

Every athlete gets the same fixed taper: 2 weeks for marathon/half, 1 week
for 10K/5K.  The `phase_builder.py` reads `TAPER_WEEKS` from constants and
that's it.  No personalization, no adaptation-rate awareness, no learning
from the athlete's own history.

Meanwhile `individual_performance_model.py` has a Banister impulse-response
model that can compute a taper duration from τ1/τ2.  But:

1. The Banister model requires 60+ training days and 3+ performance markers
   to calibrate — most athletes never qualify.
2. Even when calibrated, it's a 1970s model that assumes training stress is
   a single number and that fitness/fatigue superpose linearly.  Useful as
   one signal.  Not a foundation to build on.
3. The existing `calculate_optimal_taper_days()` is already implemented and
   available.  It doesn't need to be rewritten — it just shouldn't be the
   center of the taper system.

Phase 1C delivered `AthleteProfile` with `recovery_half_life_hours` and
`suggested_cutback_frequency` — direct observables from actual training
data.  These are more honest signals than a model parameter.

The build plan says: "Athletes without τ1: taper estimated from efficiency
rebound speed after cutback weeks (proxy for adaptation rate)."  The
correction: efficiency rebound IS the signal, not a proxy for something
else.  How fast the athlete bounces back from reduced volume is the direct
measurement of what taper duration needs to accomplish.

---

## Decision

### Taper is empirical, not model-driven

The taper system uses **observable athlete behavior** as the primary signal,
not model parameters.  The hierarchy:

| Priority | Signal | What It Is | Who Gets It |
|----------|--------|-----------|-------------|
| 1 | **Observed taper history** | What did the 2-3 weeks before the athlete's best races look like? Volume drop %, days of reduced load, performance outcome. | Athletes with 3+ races in the system |
| 2 | **Recovery rebound speed** | How fast does performance/volume normalize after cutback weeks? Directly measured from `AthleteProfile.recovery_half_life_hours`. | Athletes with 4+ weeks of data (Phase 1C) |
| 3 | **Banister model** | `BanisterModel.calculate_optimal_taper_days()` when a calibrated model exists. One input, not the answer. | Athletes with calibrated IPM (rare) |
| 4 | **Distance-appropriate defaults** | Population defaults. Honest about being a template. | Cold start |

The shift: recovery half-life is not a "proxy for τ1."  It's a direct
observable — how fast this specific human recovers.  τ1 is a parameter in
a 1970s model that attempts to describe the same phenomenon mathematically.
The observation is more trustworthy than the model.

### What each signal tells us

**Observed taper history** (Priority 1):

If the athlete has raced before and the system has activity data for the
2-3 weeks preceding those races, we can directly measure:
- Volume reduction pattern (how much did they cut?)
- Duration of reduced volume (how many days/weeks?)
- Performance outcome (was this a good race?)

Compare their best races vs worst races.  If their best marathon came after
12 days of reduced volume and their worst came after 21 days, that's a
stronger signal than any model.  This is the same principle as
`pre_race_fingerprinting.py` — pattern matching on actual outcomes.

```python
def derive_taper_from_race_history(
    activities: List[Activity],
    races: List[Activity],  # is_race_candidate or user_verified_race
) -> Optional[ObservedTaperPattern]:
    """
    Analyze pre-race volume patterns for the athlete's best races.

    For each race, look at the 21 days prior:
    - Calculate daily/weekly volume
    - Identify the volume inflection point (when did they start tapering?)
    - Measure taper duration in days
    - Correlate with race performance (age-graded %)

    Returns the pattern from their best performances, or None if
    insufficient race data.
    """
```

**Recovery rebound speed** (Priority 2):

`recovery_half_life_hours` from Phase 1C measures how quickly the athlete
returns to baseline after hard efforts.  This directly predicts taper
response:

- Fast rebound (≤ 36 hours): The athlete adapts quickly.  They don't need
  a long taper — fitness decays quickly too.  10-12 days is plenty for a
  marathon.  7 days for shorter races.
- Normal rebound (36-60 hours): Standard adaptation rate.  12-14 days
  marathon, 7-10 days half, 5-7 days 10K/5K.
- Slow rebound (> 60 hours): The athlete takes longer to absorb training
  stress but also retains fitness longer.  Can benefit from 14-18 days
  for marathon.  10-14 days for half.

```python
TAPER_DAYS_BY_REBOUND = {
    # (rebound_speed, distance) → taper_days
    ("fast", "marathon"): 10,
    ("fast", "half_marathon"): 7,
    ("fast", "10k"): 5,
    ("fast", "5k"): 4,
    ("normal", "marathon"): 13,
    ("normal", "half_marathon"): 9,
    ("normal", "10k"): 7,
    ("normal", "5k"): 5,
    ("slow", "marathon"): 17,
    ("slow", "half_marathon"): 12,
    ("slow", "10k"): 9,
    ("slow", "5k"): 7,
}
```

No τ1 conversion.  No Banister math.  Direct mapping from an observable
to a prescription.  The numbers are anchored to coaching literature
(Daniels, Pfitzinger, Vigil) and calibrated against real outcomes over
time.

**Banister model** (Priority 3):

When a calibrated model exists, `model.calculate_optimal_taper_days()` is
one input.  It's not overridden — it's averaged with the other signals,
weighted by its confidence level.  The model is most useful when recovery
rebound data is thin (adequate but not rich profile), because it
incorporates a different kind of data (training load curve shape).

**Population defaults** (Priority 4):

Cold start.  Marathon: 14 days.  Half: 10 days.  10K: 7 days.  5K: 5 days.
Disclosed honestly.

### Taper structure: progressive, intensity-maintained

Volume reduction is progressive, not a cliff:

| Taper Phase | Volume (% of peak) | Intensity | Quality Sessions |
|-------------|-------------------|-----------|-----------------|
| Early taper (if 3 weeks) | 70% | Full — last real quality session | 1 (threshold or MP) |
| Main taper | 50% | Maintained — short threshold touches (15-20 min) | 1 (threshold_short) |
| Race week | 30% | Strides only — neuromuscular maintenance | 0 (strides don't count) |

The coaching principle: taper reduces VOLUME, not INTENSITY.  The lactate
clearance rate and neuromuscular recruitment patterns built over months of
training decay faster than aerobic fitness.  Short, sharp sessions in the
taper preserve them without adding fatigue.

### Days, not weeks

The current system quantizes to 1 or 2 weeks.  A 10-day taper and a
14-day taper are meaningfully different.  The new system works in days
and the phase builder converts to week-phase structure:

- 4-7 days: race week only (volume reduction starts within race week)
- 8-10 days: 1 taper week + race week
- 11-14 days: 1 taper week + race week (longer taper week)
- 15-21 days: 2 taper weeks + race week

### N=1 always wins

Every athlete preference expressed through their actual race history
overrides any model or population default.  Some runners race best off
10-day marathon tapers.  Some need 3 weeks.  The system should detect
the pattern and respect it — with a disclosure explaining what the data
shows and why.

---

## Implementation Plan

### 1. New: `apps/api/services/taper_calculator.py`

Thin service that evaluates all available signals and returns a recommendation:

```python
@dataclass
class TaperRecommendation:
    taper_days: int
    source: str          # "race_history" | "recovery_rebound" | "banister" | "default"
    confidence: float    # 0.0-1.0
    rationale: str       # Human-readable explanation
    disclosure: str      # What the athlete should know

class TaperCalculator:
    def calculate(
        self,
        distance: str,
        profile: AthleteProfile = None,
        banister_model: BanisterModel = None,
        race_history: List[Activity] = None,
        all_activities: List[Activity] = None,
    ) -> TaperRecommendation:
        """Select best taper signal and return recommendation."""
```

### 2. Modified: `phase_builder.py`

- `build_phases()` gains optional `taper_days: int` parameter
- Converts days to progressive taper phase structure
- Falls back to `TAPER_WEEKS` when not provided (backward compatible)

### 3. Modified: `generator.py`

- `generate_custom()` computes taper via `TaperCalculator`
- Passes `taper_days` to `phase_builder.build_phases()`
- `generate_standard()` unchanged (uses defaults)

### 4. Modified: `constants.py`

- Add `TAPER_DAYS_DEFAULT` alongside `TAPER_WEEKS`
- Marathon: 14, Half: 10, 10K: 7, 5K: 5

### 5. Modified: `plan_validation_helpers.py`

- `assert_taper_structure()` validates taper bounds
- Profile-aware: fast adapters allowed shorter taper

### 6. New: `tests/test_taper_calculator.py`

- Signal priority tests
- Recovery-to-taper mapping tests
- Race history pattern detection tests
- Edge cases: no data, conflicting signals, very short/long recommendations

---

## Files Changed

| File | Change |
|------|--------|
| **New:** `apps/api/services/taper_calculator.py` | Taper signal evaluation + recommendation |
| **Modified:** `apps/api/services/plan_framework/phase_builder.py` | Accept `taper_days`, progressive structure |
| **Modified:** `apps/api/services/plan_framework/generator.py` | Compute taper days, pass to phase builder |
| **Modified:** `apps/api/services/plan_framework/constants.py` | `TAPER_DAYS_DEFAULT` |
| **Modified:** `apps/api/tests/plan_validation_helpers.py` | Taper duration bounds |
| **New:** `apps/api/tests/test_taper_calculator.py` | Unit tests |

---

## Acceptance Criteria Mapping

| Build Plan Criterion | How It's Met |
|---------------------|-------------|
| Athletes with calibrated τ1: taper uses individual model | Priority 3 signal: `BanisterModel.calculate_optimal_taper_days()` available when model exists |
| Athletes without τ1: estimated from cutback rebound | Priority 2 signal: direct mapping from `recovery_half_life_hours`, no τ1 conversion needed |
| Taper maintains intensity while reducing volume | Progressive volume reduction with `threshold_short` + `strides` preserved through taper |
| Pre-race fingerprinting available | Priority 1 signal: race history pattern analysis for athletes with 3+ races |
| Fast adapters shorter taper, slow adapters longer | Recovery rebound speed directly maps to taper duration |

---

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| Race history analysis requires enough races | Falls through to priority 2 (recovery rebound) or 3 (Banister) gracefully |
| Recovery rebound is noisy for thin data | Confidence-gated: only used when `recovery_confidence >= 0.4` |
| Banister model overrides better empirical signals | Priority 3, not 1. Weighted by model confidence. Never overrides observed taper history. |
| Existing plans break | `taper_days` is optional on `build_phases()`. Zero breaking changes. |

---

## What This ADR Does NOT Cover

- **Daily taper adaptation** — Phase 2 concern
- **Taper workout prescription details** — workout_scaler concern
- **Nutrition/sleep taper strategies** — out of scope
- **Banister model improvements** — the model exists and works; this ADR
  just stops treating it as the center of the taper system

---

## Resolved Questions

1. **Observed taper history lives in `pre_race_fingerprinting.py`.**
   The fingerprinting service already does race analysis.
   `derive_pre_race_taper_pattern()` is a natural extension.  The
   `TaperCalculator` consumes the output, doesn't replicate the logic.

2. **2 races minimum, no artificial confidence penalty.**  Two races
   with clear pre-race taper patterns and good performances is signal,
   not noise.  The confidence score from 2 data points is naturally
   lower than from 5 — the math does its job.  One race is too few
   (fluke).  Two showing a consistent pattern is the minimum.

3. **Distance scaling stays.**  Longer races warrant longer tapers
   because the training block generates qualitatively different fatigue.
   The MP long runs, glycogen depletion from 20-milers, musculoskeletal
   load — all need more unwinding.  Taper duration is a function of
   what you're tapering FROM, not just who's tapering.
