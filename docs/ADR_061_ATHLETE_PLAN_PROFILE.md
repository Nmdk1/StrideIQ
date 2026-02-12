# ADR-061: Athlete Plan Profile — N=1 Override System

**Status:** Draft  
**Date:** 2026-02-12  
**Phase:** 1C  
**Requires Approval Before Implementation**

---

## Context

Phase 1B delivered a marathon generator that passes every coaching rule against population-level defaults. The remaining strict-mode failures are all cases where a population constraint conflicts with individual athlete context:

| Strict Failure | Root Cause | What N=1 Context Resolves |
|----------------|-----------|--------------------------|
| MP > 20% of weekly volume | Weekly volume too low to absorb a correct 12mi MP session | Volume scaling from athlete's actual capacity |
| Long run > 30% of weekly volume | High-tier 24mi runs are correct coaching, not violations | Long run baseline from athlete's established practice |
| MP total < 40mi for low/builder | Fewer specific-phase weeks at low volume | Tier-aware targets from actual training history |
| Builder cutback not detected at 15% | 10% cutback is correct for builder, validator threshold too aggressive | Cutback sensitivity parameterized by tier or observed pattern |

Every one of these resolves when the plan generator has access to `AthleteProfile` — a structured summary of the individual athlete's training patterns derived from their activity data.

The build plan mandates an ADR because this is the highest-risk new service. The four questions it must answer:

1. What counts as a "long run"?
2. What is the minimum data threshold?
3. Is the fallback genuinely N=1 or secretly a template?
4. Edge cases: inconsistent loggers, walks, injury returns.

---

## Decision

Create `apps/api/services/athlete_plan_profile.py` — a stateless derivation service that reads athlete activity history and produces an `AthleteProfile` dataclass. The profile is computed on demand (not stored), is deterministic for a given history snapshot, and every field has an explicit `confidence` and `source` annotation.

### The `AthleteProfile` Dataclass

```python
@dataclass
class AthleteProfile:
    """N=1 training parameters derived from activity history."""
    
    # --- Volume ---
    volume_tier: VolumeTier               # Derived, not questionnaire
    current_weekly_miles: float            # Trailing 4-week average
    peak_weekly_miles: float               # Max week in last 12 weeks
    volume_trend: str                      # "building" | "maintaining" | "declining"
    volume_confidence: float               # 0.0–1.0
    
    # --- Long Run (duration-gated: moving_time >= 105 min) ---
    long_run_baseline_minutes: float       # Median duration of identified long runs
    long_run_baseline_miles: float         # Median distance (for plan prescription)
    long_run_max_minutes: float            # Max long run duration in window
    long_run_max_miles: float              # Max long run distance in window
    long_run_frequency: float              # Long runs per week (e.g., 0.85)
    long_run_typical_pace_per_mile: float  # Median pace of long runs (min/mi)
    long_run_confidence: float             # 0.0–1.0
    long_run_source: str                   # "history" | "tier_default"
    
    # --- Recovery ---
    recovery_half_life_hours: float        # From performance_engine
    recovery_confidence: float             # 0.0–1.0
    suggested_cutback_frequency: int       # 3, 4, or 5 weeks
    
    # --- Quality Tolerance ---
    quality_sessions_per_week: float       # Observed (e.g., 1.8)
    handles_back_to_back_quality: bool     # Ever runs quality on consecutive days without degradation
    quality_confidence: float              # 0.0–1.0
    
    # --- Metadata ---
    weeks_of_data: int                     # How many weeks of usable data
    data_sufficiency: str                  # "rich" | "adequate" | "thin" | "cold_start"
    staleness_days: int                    # Days since most recent activity
    disclosures: List[str]                 # Human-readable transparency notes
```

Every field the generator currently reads from `constants.py` has a corresponding profile field that can override it. When the profile is `cold_start`, all fields fall back to tier defaults — but the `disclosures` list explains this to the athlete.

---

## Question 1: What Counts as a "Long Run"?

### Definition

A long run is any run where **time on feet exceeds the physiological adaptation threshold** — the duration at which the body begins meaningful glycogen depletion, triggering adaptations that shorter runs cannot: mitochondrial biogenesis, enhanced fat oxidation, capillarization, and glycogen storage expansion.

**Distance is incidental. Duration is the gate.**

A fast runner's 10-miler in 65 minutes is a moderate aerobic run — they never enter the adaptation zone. A slower runner's 10-miler in 1:50 is a genuine long run — they get the full physiological stimulus. The same distance produces fundamentally different training effects depending on how long the athlete is running.

### The threshold: 105 minutes (moving time)

The canonical threshold is **105 minutes** (`LONG_RUN_DURATION_THRESHOLD_MIN = 105`). This is where glycogen depletion becomes significant enough to drive the adaptations that define a long run.

The boundary is not a cliff — a 100-minute run captures most of the benefit, and a 120-minute run adds incremental stimulus. But for classification purposes, a single threshold is cleaner than a fuzzy range. 105 minutes is chosen because:

- Below 90 minutes: glycogen depletion is minimal for most runners; aerobic adaptations are available from shorter runs
- 90–105 minutes: transitional zone; meaningful for slower runners, modest for faster ones
- Above 105 minutes: the body is firmly in the depletion/adaptation zone regardless of pace
- The coaching literature (Daniels, Pfitzinger, Vigil) converges on 90–120 minutes as the long run stimulus window; 105 is the midpoint

**Moving time, not elapsed time.** Strava's `moving_time` field excludes stopped time at traffic lights, water stops, and bathroom breaks. A runner who covers 2:10 elapsed but 1:48 moving was running for 108 minutes — that's a long run. Using `elapsed_time` would misclassify a stop-and-go urban runner's 1:30 of actual running as a long run because they waited at 15 red lights.

### Algorithm

```
For each run in the analysis window (last 12 weeks):
    if run.moving_time >= 105 minutes:
        → classify as long run
    else:
        → not a long run (regardless of distance)
```

No volume-relative floor. No distance threshold. No longest-per-week heuristic. Duration is the single gate. This is correct because:

- **A 60 mpw runner doing 10mi at 7:00/mi (70 min) is NOT doing a long run.** It's a moderate aerobic run. The physiological stimulus ends well before glycogen depletion. Classifying this as a long run because it's the "longest that week" would be wrong.

- **A 25 mpw runner doing 10mi at 11:00/mi (1:50) IS doing a long run.** They are firmly in the adaptation zone. The system should not dismiss this because the distance looks modest.

- **A trail runner doing 8mi with 4000ft of gain in 2:15 IS doing a long run.** Duration captures the training effect of elevation gain naturally. No special-casing or "equivalent flat distance" conversion needed — the time on feet tells the story.

### The baseline calculation

```python
identified_long_runs = [r for r in analysis_window if r.moving_time >= 105]

long_run_baseline_minutes = median(r.moving_time for r in identified_long_runs[-8:])
long_run_baseline_miles = median(r.distance_miles for r in identified_long_runs[-8:])
long_run_typical_pace = long_run_baseline_minutes / long_run_baseline_miles
```

Median of the last 8 identified long runs, in both duration and distance. The plan generator prescribes in miles (athletes think in distance), but the identification is duration-gated. The typical pace is stored so the generator can estimate how long a prescribed distance will take for this athlete — ensuring the planned long run actually produces the intended duration stimulus.

8 long runs is approximately 8–10 weeks of training for a once-weekly long runner. Median is robust to outliers (one 3-hour marathon-pace long run in a sea of 2-hour easy long runs doesn't skew the baseline).

### Athletes without long runs

If no runs in the analysis window exceed 105 minutes, the athlete genuinely does not do long runs. This is not a data quality problem — it's a real signal:

- `long_run_frequency` = 0.0
- `long_run_confidence` = 0.0
- The system falls back to tier defaults for the plan's long run prescription
- Disclosure: "None of your recent runs exceed 1:45 — you haven't been doing long runs. Your plan includes them starting at [tier-appropriate distance] to build the aerobic base for [goal distance]. Expect these to feel challenging at first."

This is cleaner than the distance-based approach. There's no ambiguity about whether the athlete has a long run pattern — either they run long enough for the adaptations, or they don't.

### What about prescribing long runs in the plan?

The plan generator prescribes long runs in miles. When the profile has history:

```python
# The athlete's typical long run pace converts a target duration to distance
target_long_run_miles = target_duration_minutes / profile.long_run_typical_pace_per_mile
```

When the profile is cold start, the generator uses tier defaults from `LONG_RUN_PEAKS` in `constants.py` (which are distance-based). The transition from tier defaults to N=1 duration-derived distances happens as data crosses confidence thresholds.

---

## Question 2: What Is the Minimum Data Threshold?

### Tiers of data sufficiency

| Level | Weeks of Data | Runs | What the System Knows | What It Discloses |
|-------|--------------|------|----------------------|-------------------|
| **Rich** | 12+ weeks | 40+ runs | Volume tier, long run baseline, recovery speed, quality tolerance, trend | Full N=1 profile. No disclosures needed. |
| **Adequate** | 8–11 weeks | 25–39 runs | Volume tier, long run baseline, recovery estimate | "Recovery speed and quality tolerance are estimated from limited data. These will refine over the next 4 weeks." |
| **Thin** | 4–7 weeks | 12–24 runs | Volume tier, rough long run estimate | "I have [X] weeks of training data. Volume and long run targets are preliminary — I'll adjust as I learn your patterns." |
| **Cold start** | 0–3 weeks | 0–11 runs | Nothing reliable | "I don't have enough training history to personalize yet. I'm using [tier] defaults based on your reported mileage. Connect Strava or log runs to unlock personalized targets." |

### Why 4 weeks is the minimum for "thin" (not 2)

2 weeks can't distinguish a pattern from noise. An athlete who ran 50 miles one week and 20 the next could be a 35 mpw runner on a cutback or a 50 mpw runner recovering from illness. 4 weeks gives one full cutback cycle, which is the minimum to detect structure.

### Below-threshold behavior

When `data_sufficiency == "cold_start"`:
- All profile fields use tier defaults from `constants.py`
- `long_run_source` = `"tier_default"`
- Every `*_confidence` field = 0.0
- `disclosures` contains a specific message about what data is missing and how to improve it

The system does NOT pretend to know the athlete. It is transparent about operating on defaults.

---

## Question 3: Is the Fallback Genuinely N=1 or Secretly a Template?

### Honest answer: cold start IS a template. And the system says so.

When `data_sufficiency == "cold_start"`, the plan is generated from `constants.py` tier defaults. That is a population-level template. The system must not dress this up as "personalized."

### What makes it N=1 even at cold start

1. **The template is temporary.** Every week of training data improves the profile. The athlete sees disclosures shrink as data accumulates.

2. **The volume tier is auto-detected, not questionnaire.** Even 2 weeks of Strava gives a better volume estimate than "how many miles do you run per week?" from an intake form. Self-reported mileage is unreliable — athletes over-report by 10–20% on average.

3. **The transition is smooth.** As data crosses thresholds (thin → adequate → rich), the profile updates. The generator doesn't suddenly jump from template to N=1 — the overrides phase in gradually as confidence increases.

### The confidence gating mechanism

Each profile field has a confidence score (0.0–1.0). The generator uses the override only when confidence exceeds a threshold:

```python
# In generator, when consuming the profile:
if profile.long_run_confidence >= 0.6:
    long_run_peak = profile.long_run_baseline_miles + progression_delta
else:
    long_run_peak = LONG_RUN_PEAKS[distance][tier]  # tier default
```

This means a "thin" athlete might get N=1 volume tier (high confidence from just 4 weeks of data) but tier-default long run peaks (low confidence from only 2–3 identified long runs). Each dimension transitions independently.

### What the athlete sees

The plan card or plan summary includes a `personalization_level` indicator:

- **"Fully personalized"** — All parameters from your training data (rich, all confidences > 0.6)
- **"Partially personalized"** — Volume and long run from your data; recovery and quality tolerance estimated ([specific fields] will improve with more data)
- **"Estimated defaults"** — Based on your reported mileage and goal. Connect Strava or log 4+ weeks of runs for a personalized plan.

No athlete should ever wonder whether their plan is based on their data or a template. The system tells them.

---

## Question 4: Edge Cases

### Inconsistent loggers

**Problem:** Runs every day one week, nothing for two weeks, then back to daily.

**Detection:** `consistency_index` (already computed by `performance_engine.py`) measures coefficient of variation in weekly volume. High CV (> 0.5) with frequent zero-weeks indicates inconsistent logging, not inconsistent training.

**Handling:**
- Filter out weeks with zero activities when calculating `current_weekly_miles` (use median of non-zero weeks, not mean of all weeks)
- `volume_confidence` reduced proportionally to the fraction of zero-weeks
- Disclosure: "Your logging has gaps — [X] of the last 12 weeks show no runs. Volume targets are based on your active weeks. If you train but don't log, connect auto-sync (Strava, Garmin) for more accurate planning."

### Athletes who log walks and runs in the same account

**Problem:** Strava activity type = "Run" but includes walks, hikes, and cross-training logged as runs.

**Detection:** Already handled by Strava sync. `strava_tasks.py` filters on `activity.type == "Run"`. The `workout_classifier` further classifies runs by pace and HR zone. A "run" at 20:00/mile pace with zone 1 HR is classified as a walk/recovery — it won't be identified as a long run or quality session.

**Additional safeguard:** The long run identification algorithm uses the `long_run_floor` (20% of weekly miles, min 8mi). A 3-mile walk logged as a "Run" will never cross this threshold. And the `_classify_steady_state` in `workout_classifier.py` already separates runs by intensity zone.

### Athletes returning from injury

**Problem:** 2 years of 60 mpw data, then a 6-month gap, then 3 weeks at 20 mpw. The historical data no longer reflects current state.

**Detection:** `staleness_days` — gap between most recent pre-injury activity and first post-injury activity.

**Handling:**

```python
# Recency-weighted analysis window
if gap_detected(activities, threshold_days=28):
    # Use only post-gap data
    analysis_window = activities_after_most_recent_gap
    data_sufficiency = classify_sufficiency(analysis_window)
    
    # But note the pre-injury context
    disclosures.append(
        f"You appear to be returning from a {gap_weeks}-week break. "
        f"Your plan is based on your recent {post_gap_weeks} weeks of training, "
        f"not your pre-break volume. As you rebuild, targets will adjust upward."
    )
```

The system uses only post-gap data for profile derivation but acknowledges the pre-injury history exists. It does NOT assume the athlete can immediately return to 60 mpw. The volume tier classification sees 20 mpw and classifies accordingly. As the athlete rebuilds and logs more data, the profile naturally updates.

**Gap detection threshold:** 28 consecutive days with no run activities = gap. This distinguishes "took a rest week" (7–10 days) from "was injured/on break."

### Taper and race-week data pollution

**Problem:** The athlete is in a taper or just raced. The last 2–3 weeks show deliberately reduced volume that doesn't represent their training capacity.

**Detection:** Check if any activity in the last 3 weeks is a race (from `is_race_candidate` or `user_verified_race`). If so, extend the analysis window backward to capture pre-taper training.

**Handling:**
```python
if has_recent_race(activities, days=21):
    # Include pre-taper window (go back 6 more weeks)
    analysis_window = last_n_weeks(activities, weeks=18)
    disclosures.append(
        "Your recent taper/race period is excluded from baseline calculations. "
        "Targets reflect your pre-taper training capacity."
    )
```

### Single-sport vs multi-sport athletes

**Scope:** This service only reads running activities. Cycling, swimming, and cross-training are excluded from volume and long run calculations. The `Activity.sport` field (or Strava `type`) filters to runs only.

---

## Implementation Plan

### Service Interface

```python
class AthletePlanProfileService:
    """Derives N=1 training parameters from activity history."""
    
    def derive_profile(
        self,
        athlete_id: int,
        db: Session,
        goal_distance: str,
    ) -> AthleteProfile:
        """
        Compute the athlete's training profile from their activity history.
        
        Stateless: no side effects, no writes. Deterministic for a given
        history snapshot. Safe to call repeatedly.
        """
    
    def _get_analysis_window(
        self, activities: List[Activity]
    ) -> Tuple[List[Activity], List[str]]:
        """Select the relevant analysis window, handling gaps and tapers."""
    
    def _derive_volume(
        self, weekly_summaries: List[WeeklySummary]
    ) -> Tuple[VolumeTier, float, float, str, float]:
        """Volume tier, current, peak, trend, confidence."""
    
    def _derive_long_run(
        self, activities: List[Activity], weeks_of_data: int
    ) -> Tuple[float, float, float, float, float, float, float, str]:
        """Duration-gated identification (moving_time >= 105 min).
        Returns: baseline_min, baseline_mi, max_min, max_mi,
                 frequency, typical_pace, confidence, source."""
    
    def _derive_recovery(
        self, activities: List[Activity], athlete: Athlete
    ) -> Tuple[float, float, int]:
        """Half-life, confidence, suggested cutback frequency."""
    
    def _derive_quality_tolerance(
        self, activities: List[Activity], weekly_summaries: List[WeeklySummary]
    ) -> Tuple[float, bool, float]:
        """Sessions/week, handles back-to-back, confidence."""
```

### What It Reuses (Not Reinvents)

| Existing Service | What It Provides | How Profile Uses It |
|-----------------|-----------------|-------------------|
| `VolumeTierClassifier.classify()` | Volume tier from 4-week average | Direct reuse for `volume_tier` |
| `VolumeTierClassifier._get_actual_volume()` | Weekly volume from activity history | Reuse for `current_weekly_miles` |
| `workout_classifier.classify_activity()` | Run type classification (threshold, interval, etc.) | Quality session identification for `quality_tolerance` derivation |
| `performance_engine.calculate_recovery_half_life()` | Recovery half-life in hours | Direct reuse for `recovery_half_life_hours` |
| `performance_engine.calculate_consistency_index()` | Training consistency 0–100 | Input to `volume_confidence` |
| `athlete_metrics.estimate_rpi()` | RPI from personal bests | Not consumed directly, but correlated |

### What's New

1. **Long run identification** — Duration-gated (moving_time >= 105 min), not distance-based (does not exist today)
2. **Confidence scoring** — Per-field confidence based on data quantity and consistency
3. **Gap detection** — Injury/break detection from activity gaps > 28 days
4. **Quality tolerance derivation** — Counting quality sessions per week from classified history
5. **Disclosure generation** — Human-readable transparency notes for the athlete
6. **Profile → Generator wiring** — `constants.py` defaults become overridable by profile fields

### Integration with Generator

```python
# In generator.py generate_custom_plan():
profile = self.profile_service.derive_profile(athlete_id, db, distance)

# Volume tier — always from profile (even cold start uses tier defaults)
tier = profile.volume_tier

# Long run peak — conditional on confidence
# Duration is the physiological gate; distance is the prescription unit.
# Use the athlete's typical long run pace to convert between them.
if profile.long_run_confidence >= 0.6:
    long_run_peak = min(
        profile.long_run_baseline_miles + distance_progression_delta,
        profile.long_run_max_miles + 2  # Never more than 2mi above observed max
    )
    # Sanity check: does the planned peak produce a reasonable duration?
    estimated_duration = long_run_peak * profile.long_run_typical_pace_per_mile
    # Cap at ~3 hours for non-elite (avoid prescribing unsupported duration)
    if estimated_duration > 180 and tier not in ("high", "elite"):
        long_run_peak = 180 / profile.long_run_typical_pace_per_mile
else:
    long_run_peak = LONG_RUN_PEAKS[distance][tier]

# Recovery — maps to cutback frequency
cutback_freq = profile.suggested_cutback_frequency  # 3, 4, or 5

# Quality tolerance — maps to quality_sessions in phase config
max_quality = 2 if profile.quality_sessions_per_week >= 1.5 else 1
```

### Strict Mode Resolution

With the profile wired in, the remaining strict failures resolve:

| Failure | Resolution |
|---------|-----------|
| MP > 20% | Profile shows `current_weekly_miles` is high enough to absorb the MP session, OR the MP session is scaled down for lower-volume athletes |
| LR > 30% | Profile's `long_run_baseline_miles` justifies the long run length; weekly volume is scaled to support it |
| MP total < 40mi | Low-tier athletes get tier-aware MP total targets (e.g., 25mi for builder, 30mi for low) |
| Builder cutback detection | Validator gets `suggested_cutback_frequency` and `cutback_reduction` from profile, matching the actual reduction applied |

### Validator Changes (Small)

The validator gains an optional `profile` parameter:

```python
def validate_plan(plan, strict=False, profile=None):
    validator = PlanValidator(plan, strict=strict, profile=profile)
    return validator.assert_all()
```

When `profile` is provided:
- `B1-LR-PCT` limit adjusts based on `long_run_baseline_miles` (if established practice supports 30%+, allow it)
- `B1-MP-PCT` limit adjusts based on `current_weekly_miles` (if volume supports the MP session, allow it)
- Cutback detection threshold uses `profile.suggested_cutback_frequency` and actual reduction percentage
- MP total target scales with volume tier

---

## Files Changed

| File | Change |
|------|--------|
| **New:** `apps/api/services/athlete_plan_profile.py` | Core service |
| **New:** `apps/api/tests/test_athlete_plan_profile.py` | Unit tests for derivation logic |
| **Modified:** `apps/api/services/plan_framework/generator.py` | Consume profile in `generate_custom_plan()` |
| **Modified:** `apps/api/services/plan_framework/constants.py` | No structural change — profile overrides at consumption point, not mutation |
| **Modified:** `apps/api/tests/plan_validation_helpers.py` | Accept optional `profile` parameter |
| **Modified:** `apps/api/tests/test_plan_validation_matrix.py` | N=1 xfail variants get wired to synthetic profiles, xfails removed |

---

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| Profile derivation is slow (DB queries per plan generation) | Stateless and cacheable. Profile for a given athlete + snapshot doesn't change until new activities sync. Cache with 1-hour TTL. |
| Confidence thresholds are wrong (too aggressive or too conservative) | Start conservative (0.6 for overrides). Log when overrides are applied vs tier defaults. Tune thresholds from production data after 4 weeks. |
| Gap detection misclassifies vacation as injury | 28-day threshold is conservative. A 2-week vacation (14 days) won't trigger. A genuine break (28+ days) will. If wrong, the athlete rebuilds faster than expected — the profile catches up within 4 weeks. |
| Athletes game the system (log fake runs for better profiles) | Not a risk worth engineering against. The plan is for the athlete. Gaming their own plan hurts only them. |

---

## What This ADR Does NOT Cover

- **Daily adaptation** — That's Phase 2. The profile is a pre-plan derivation, not a real-time adjustment.
- **Coach narration of profile** — The coach can reference disclosures, but profile-aware narration is a Phase 3B concern.
- **Periodization model selection** — The build plan mentions "both early-VO2max and late-VO2max approaches supported." This ADR derives the parameters; the periodization strategy is a generator concern for 1E–1G.
- **tau-1 / individual performance model** — That's Phase 1D (taper democratization). The profile's `recovery_half_life_hours` is a simpler signal; tau-1 is a calibrated Banister model.

---

## Open Questions for Review

1. **Should the profile be stored or always computed?** Current design is stateless (compute on demand). Pro: no stale data, no migration. Con: repeated DB queries. A middle ground: compute and cache in Redis with athlete_id + last_activity_date as the cache key. Invalidate on new activity sync.

2. **How does `quality_tolerance` interact with the alternation rule?** Phase 1B enforces "MP long run weeks have no threshold" unconditionally. Should this be relaxable for athletes who demonstrably handle it? The conservative answer is no — the alternation rule is a hard constraint from Source B. But an 80 mpw experienced runner who regularly does MP Tuesday + threshold Thursday might be a valid exception.

3. **What about the 3 N=1 xfail scenarios in the test matrix?** These are `n1-experienced-70mpw-marathon`, `n1-beginner-25mpw-marathon`, `n1-masters-55mpw-half`. Each needs a synthetic `AthleteProfile` in the test. The experienced runner gets a profile with high confidence across all fields. The beginner gets a cold-start profile. The masters runner gets an adequate profile with adjusted cutback frequency (every 3rd week). These synthetic profiles should be defined as test fixtures, not hardcoded in the test matrix.

4. **Is 105 minutes the right threshold, or should it be configurable per athlete?** The 105-minute default is well-supported by physiology. But an elite runner at 5:30/mi pace reaches glycogen depletion differently than a beginner at 12:00/mi pace — the elite runner's higher absolute work rate depletes glycogen faster per minute. In practice, 105 minutes works for the vast majority of recreational and competitive runners. If evidence emerges that the threshold should flex, it can be made a profile field later. For now, a single constant is cleaner.
