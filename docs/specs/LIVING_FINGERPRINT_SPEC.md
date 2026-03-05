# Living Fingerprint — Activity Intelligence Pipeline

**Date:** March 5, 2026
**Status:** Reviewed by Codex + Opus. Ready for build.
**Origin:** Founder + builder deep discussion (8 rounds)
**Reviews:** Codex conditional GO (4 HIGHs resolved below). Opus BUILD.

---

## Read Order (Non-Negotiable)

1. `docs/FOUNDER_OPERATING_CONTRACT.md` — How you work with this founder
2. `docs/PRODUCT_MANIFESTO.md` — The soul of the product
3. `docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md` — How every screen should feel
4. `docs/RUN_SHAPE_VISION.md` — Vision for run data visualization
5. `docs/PRODUCT_STRATEGY_2026-03-03.md` — The compounding intelligence moat
6. `docs/specs/CORRELATION_ENGINE_ROADMAP.md` — The 12-layer engine roadmap
7. This spec — your primary working document

---

## The Problem

The system has per-second stream data for every activity. It has weather
data. It has training pace profiles with zone boundaries. It has an
investigation engine that mines findings. It has a training story engine
that synthesizes them. And yet:

1. **The system can't see the shape of a run.** It operates on per-mile
   splits. Strides, fartleks, cruise intervals, progressive builds —
   invisible. The founder's father ran strides and the coach only noticed
   the overall mile pace.

2. **Weather comparisons use raw temperature.** The heat adjustment
   formula exists in the frontend tool (`HeatAdjustedPace.tsx`) but isn't
   used in any backend analysis. Every pace comparison across seasons is
   confounded.

3. **Investigations recompute from scratch on every request.** No
   persistence. No incremental updates. No signal declarations.

4. **Findings describe what happened, not what it means.** The training
   story produces observations, not insights.

The Living Fingerprint solves all four by establishing a persistent,
incrementally-updated intelligence layer that operates on activity shapes
and weather-normalized paces.

---

## Architecture Decision: Option A (View Layer on Existing Postgres)

The fingerprint is NOT a new data store. Postgres is already the signal
store. The existing models ARE the signal types:

| Signal Type | Existing Model | Status |
|---|---|---|
| `activity_summary` | `Activity` | Complete |
| `activity_stream` | `ActivityStream` | Complete |
| `activity_splits` | `ActivitySplit` | Complete |
| `daily_health` | `DailyCheckin` | Partial (HRV, sleep, resting HR) |
| `environment` | `Activity.temperature_f`, `.humidity_pct` | Complete |
| `race_result` | `PerformanceEvent` | Complete |
| `subjective` | `DailyCheckin.rpe` | Partial |
| `nutrition` | — | Future |
| `body_composition` | — | Future |
| `biomarker` | — | Future |

The adapter layer translates external data into model writes — which is
what `strava_tasks.py` and `garmin_webhook_tasks.py` already do.
Formalizing that with an interface is useful. Replacing the storage is
risk with no payoff.

---

## What Gets Built (Three Capabilities + Integration)

### Capability 1: Weather Normalization

#### Problem
The heat-adjusted pace formula (Temp °F + Dew Point °F combined value)
exists in `apps/web/app/components/tools/HeatAdjustedPace.tsx` lines
44-82. It's research-validated against Berlin Marathon (668K runners),
Six Major Marathons Study, McMillan Calculator, and Training Pace App.

The backend doesn't use it. Every investigation that compares paces
across seasons is confounded.

#### What Exists
- `Activity.temperature_f` — stored for most outdoor activities
- `Activity.humidity_pct` — stored for most outdoor activities
- `weather_backfill.py` fetches `dew_point_2m` from Open-Meteo but
  stores it only in the backfill return, NOT on the Activity model
- The dew point Magnus formula is implemented in TypeScript

#### Build

**New file:** `apps/api/services/heat_adjustment.py`

```python
def calculate_dew_point_f(temp_f: float, humidity_pct: float) -> float:
    """Magnus formula. Identical to HeatAdjustedPace.tsx calculateDewPoint."""

def calculate_heat_adjustment_pct(temp_f: float, dew_point_f: float) -> float:
    """Combined value model. Identical to HeatAdjustedPace.tsx calculateHeatAdjustment.
    Returns the percentage slowdown (0.0 to ~0.12)."""

def heat_adjusted_pace(pace_sec_per_mile: float, temp_f: float,
                       humidity_pct: float) -> float:
    """Returns what this pace would be in ideal conditions (combined < 120).
    adjusted = raw_pace / (1 + adjustment_pct)"""
```

**Schema change:** Add to `Activity` model:
- `dew_point_f` (Float, nullable) — stored at ingestion or backfill
- `heat_adjustment_pct` (Float, nullable) — computed from temp + dew point

**Backfill:** One-time migration script computes `dew_point_f` from
`temperature_f` + `humidity_pct` (Magnus formula) and
`heat_adjustment_pct` for all existing activities with weather data.

**Ingestion hook:** `weather_backfill.py` already fetches dew point. Store
it on the Activity. Compute `heat_adjustment_pct` at the same time.

**Investigation engine update:** All investigations that compare paces
(`investigate_pace_at_hr_adaptation`, `investigate_stride_economy`,
`investigate_workout_progression`) switch from raw pace to
heat-adjusted pace.

**`investigate_heat_tax` refactored (H3 resolution):** Once all pace
comparisons use heat-adjusted pace, the original heat_tax investigation
("hot races are slower") becomes redundant — that's now accounted for
by normalization. Refactor it to answer a genuinely N=1 question:
**does this athlete's actual heat response match, exceed, or fall
short of the generic formula?** Compare their observed slowdown at
high combined values against the formula's predicted slowdown. If they
handle heat better than average, that's actionable ("your heat
tolerance is above average — you lose less than most runners in hot
conditions"). If worse, equally useful. This replaces the generic
"heat makes you slower" finding with a personal heat resilience score.

**Existing weather controls (M3 resolution):** The weather confound
flags in investigations (e.g., `weather_confound` in
`investigate_training_recipe`, temperature band filtering in
`investigate_pace_at_hr_adaptation`) become redundant once paces are
pre-normalized. Remove the confound flag logic from investigations
that now use heat-adjusted pace. The normalization replaces the
confound detection — simpler code, better results.

#### Test Gate
- `heat_adjustment.py` unit tests: known combined values produce correct
  adjustment percentages (cross-validate against TypeScript implementation)
- Backfill script processes all existing activities without error
- Investigation output changes are reviewed — findings that were
  flagged "suggestive" due to weather confound should now have higher
  confidence

---

### Capability 2: Activity Shape Extraction

#### Problem
The system has per-second velocity, HR, cadence, elevation, and distance
in `ActivityStream.stream_data`. The existing `run_stream_analysis.py`
detects segments (warmup/work/recovery/cooldown/steady) and moments
(pace surges, cardiac drift, cadence changes). But it stops too early.

It finds "pace surge at minute 47" but doesn't characterize: how long,
how fast relative to the athlete's zones, HR response, was there recovery
after, were there similar ones, where in the run did they cluster.

The coach, the investigation engine, and the training story are all blind
to what the athlete actually did within each run.

#### What Exists
- `ActivityStream` with per-second data: `time`, `velocity_smooth`,
  `heartrate`, `cadence`, `altitude`, `grade_smooth`, `distance`, `latlng`
- `run_stream_analysis.py` (~1800 lines): `analyze_stream()` produces
  `StreamAnalysisResult` with `segments`, `drift`, `moments`
- `Segment` dataclass: type, start/end index, duration, avg_pace, avg_hr,
  avg_cadence, avg_grade
- `Moment` dataclass: type, index, time_s, value
- `AthleteContext` with threshold_hr, max_hr, resting_hr for tiered
  classification
- `AthleteTrainingPaceProfile` with `paces` JSONB containing zone
  boundaries (easy, marathon, threshold, interval, repetition)
- `WorkoutClassifierService` for activity-level classification
- `stream_analysis_cache.py` for caching analysis results

#### Build

**Extend `StreamAnalysisResult`** with a new `RunShape` dataclass:

```python
@dataclass
class Acceleration:
    start_time_s: int
    end_time_s: int
    duration_s: int
    distance_m: float
    avg_pace_sec_per_mile: float
    avg_pace_heat_adjusted: Optional[float]  # if weather data exists
    pace_zone: str        # 'easy', 'marathon', 'threshold', 'interval', 'repetition'
    avg_hr: Optional[float]
    hr_delta: Optional[float]   # change from pre-acceleration baseline
    avg_cadence: Optional[float]
    cadence_delta: Optional[float]
    position_in_run: float   # 0.0 = start, 1.0 = end
    recovery_after_s: Optional[int]  # seconds until pace returns to baseline

@dataclass
class Phase:
    """A sustained segment with consistent effort character."""
    start_time_s: int
    end_time_s: int
    duration_s: int
    distance_m: float
    avg_pace_sec_per_mile: float
    avg_pace_heat_adjusted: Optional[float]
    pace_zone: str
    avg_hr: Optional[float]
    avg_cadence: Optional[float]
    elevation_delta_m: float
    avg_grade: Optional[float]
    pace_cv: float          # coefficient of variation — was pace steady or variable?
    phase_type: str         # 'warmup', 'easy', 'steady', 'tempo', 'threshold',
                            # 'interval_work', 'interval_recovery', 'cooldown',
                            # 'acceleration', 'hill_effort', 'recovery_jog'

@dataclass
class ShapeSummary:
    """Computed properties of the overall shape. Queryable by investigations."""
    total_phases: int
    acceleration_count: int
    acceleration_avg_duration_s: Optional[float]
    acceleration_avg_pace_zone: Optional[str]
    acceleration_clustering: str  # 'end_loaded', 'scattered', 'periodic', 'none'
    has_warmup: bool
    has_cooldown: bool
    pace_progression: str  # 'building', 'fading', 'steady', 'variable', 'even_split'
    pace_range_sec_per_mile: float  # fastest phase - slowest phase
    longest_sustained_effort_s: int
    longest_sustained_zone: str
    elevation_profile: str  # 'flat', 'hilly', 'net_uphill', 'net_downhill', 'out_and_back'
    workout_classification: Optional[str]  # derived label, nullable if shape is novel

@dataclass
class RunShape:
    phases: List[Phase]
    accelerations: List[Acceleration]
    summary: ShapeSummary
```

**How `workout_classification` is derived (from shape, not hardcoded):**

The classification is an optional label derived from the shape's
structural properties. The shape is the truth; the label is convenience.
New workout types that don't exist in this list are still fully
described by their phases and accelerations.

| Classification | Shape Signature |
|---|---|
| `easy_run` | All phases in easy zone, acceleration_count < 2, low pace_cv |
| `recovery_run` | All phases in recovery/easy zone, shorter than typical, low HR |
| `strides` | 3-8 accelerations of 10-30s, clustered in final 15% (end_loaded), at interval/rep zone |
| `fartlek` | 3+ accelerations of 15-90s, scattered distribution, variable duration |
| `tempo` | One phase > 12 min at threshold zone, with warmup/cooldown |
| `threshold_intervals` | 2-5 phases at threshold zone, 4-15 min each, recovery between |
| `track_intervals` | 4+ phases at interval/rep zone, similar duration, recovery between |
| `progression` | Each successive phase faster, final phase at marathon pace or faster |
| `over_under` | Alternating phases above/below marathon pace, ~10-15 sec/mi spread |
| `hill_repeats` | Repeated efforts with significant elevation gain, recovery jogs down |
| `long_run` | Distance > athlete's 30-day avg × 1.5, primarily easy/steady zone |
| `long_run_with_strides` | long_run + end_loaded accelerations |
| `long_run_with_tempo` | long_run + embedded threshold phase > 10 min |
| `anomaly` | GPS gaps > 30s AND (unrealistic velocity > 25 mph OR 3+ separate gaps); single tunnel/pause is not anomaly |
| `null` | Shape doesn't match known patterns — phases/accelerations still fully described |

**Note (H2 resolution):** `race` is intentionally excluded from shape
classification. Race identification is handled by the separate
PerformanceEvent pipeline and may not exist at shape extraction time
(athlete confirms races later). A race effort will be classified by
its shape structure — typically `tempo` or `progression` or `null` —
and separately tagged as a race by the event pipeline. The shape
describes the effort; the event pipeline identifies the context.

**Phase vs Segment relationship (H4 resolution):** Phases are computed
from the same raw stream data as existing Segments, NOT derived from
Segments. Both use `velocity_smooth`, `heartrate`, `cadence`,
`grade_smooth`. The existing Segment output (5 types: warmup, work,
recovery, cooldown, steady) stays for backward compatibility — it's
consumed by the coach tool and the existing activity view. Phases (11
types) are the new, richer representation that uses training pace
profiles for zone classification. Both live in `StreamAnalysisResult`
but serve different consumers.

**Where this runs:** Inside `analyze_stream()` as the final
computation step, after segments and moments. Phases are a parallel
output, not a replacement. Requires `AthleteContext` for zone
classification (uses training pace profile when available, falls back
to stream-relative percentiles).

#### Phase Detection Algorithm

The hardest engineering in this spec. This pseudocode defines how
per-second stream data becomes structured phases.

**Step 1: Smooth and compute per-point metrics**
```
velocity_smooth = rolling_mean(velocity, window=15s)
pace_per_point = 26.8224 / velocity_smooth  (sec/mi, skip if v < 0.5 m/s)
zone_per_point = classify_pace(pace, athlete_pace_profile)
                 # returns: 'recovery', 'easy', 'marathon', 'threshold',
                 #          'interval', 'repetition', 'stopped'
                 # Falls back to stream-relative percentiles if no profile
```

**Step 2: Detect zone transitions (changepoint detection)**
```
For each point i:
  if zone_per_point[i] != zone_per_point[i-1]:
    mark as candidate transition at time[i]

Merge transitions closer than MIN_PHASE_DURATION (20s):
  keep the later zone if the earlier segment is too short

Result: ordered list of (start_time, end_time, dominant_zone) blocks
```

**Step 3: Merge micro-phases**
```
For each block:
  if duration < MIN_PHASE_DURATION (20s):
    merge into adjacent block with the same zone
    if both neighbors differ, merge into the longer neighbor
  
Result: stable phases with minimum duration guarantee
```

**Step 4: Classify phase type**
```
For each phase:
  Compute: avg_pace, avg_hr, avg_cadence, elevation_delta, pace_cv, distance

  phase_type = dominant_zone  (default)

  # Position-based overrides:
  if phase is first AND zone in ('easy', 'recovery') AND duration < 15% of total:
    phase_type = 'warmup'
  if phase is last AND zone in ('easy', 'recovery') AND duration < 15% of total:
    phase_type = 'cooldown'

  # Effort-based refinements:
  if zone == 'threshold' AND duration > 240s (4 min):
    phase_type = 'threshold'
  if zone in ('interval', 'repetition') AND duration > 10s:
    phase_type = 'interval_work'
  if zone in ('easy', 'recovery') AND preceded_by('interval_work', 'threshold'):
    phase_type = 'interval_recovery' OR 'recovery_jog'

  # Elevation-based:
  if avg_grade > 4% AND duration > 30s:
    phase_type = 'hill_effort'
```

**Step 5: Detect accelerations**
```
Baseline velocity = median velocity of all 'easy'/'steady' phases
                    (or median of full run if no easy phases)

For each point in non-warmup, non-cooldown phases:
  if velocity > baseline * 1.15 AND zone >= 'marathon':  # Opus point: minimum zone threshold
    start tracking acceleration

  Acceleration ends when velocity drops below baseline * 1.10
  for > 5 consecutive seconds

  if acceleration duration >= 10s:
    Record: start_time, end_time, duration, avg_pace, zone, HR delta,
            cadence delta, position_in_run, recovery_after

CRITICAL: Accelerations must reach at least marathon pace zone to
count. This prevents hill crests, GPS noise, and pace variation on
easy runs from producing false accelerations.
```

**Step 6: Compute shape summary**
```
acceleration_clustering:
  end_loaded:  >60% of accelerations in final 25% of run (by distance)
  periodic:    acceleration intervals have CV < 0.3 (evenly spaced)
  scattered:   >2 accelerations, not end_loaded, not periodic
  none:        0-1 accelerations

pace_progression (renamed from overall_trajectory per L1):
  building:    weighted linear regression of phase avg_pace has negative slope
               (getting faster) with R² > 0.6
  fading:      positive slope with R² > 0.6
  steady:      |slope| < 5 sec/mi across phases, R² < 0.3
  even_split:  first half avg within 10 sec/mi of second half avg
  variable:    none of the above

elevation_profile:
  flat:           total elevation gain < 50m
  hilly:          gain per mile > 30m
  net_uphill:     net elevation > +30m
  net_downhill:   net elevation < -30m
  out_and_back:   net elevation within ±10m AND gain > 50m
```

**Step 7: Derive classification (optional label)**
```
Apply classification table (see above) to shape summary.
If no rule matches → classification = null.
Shape data (phases, accelerations, summary) is always complete
regardless of whether classification succeeds.
```

**Handling messy data:**
- GPS dropout (velocity = 0 for > 5s): mark as 'stopped', exclude
  from phase metrics, do not count as acceleration
- Unrealistic velocity (> 11 m/s / 25 mph): clamp to previous valid
  value, flag in shape metadata
- Watch pause/resume (time gap > 30s with no distance): split into
  separate phase, mark gap
- Traffic stop (velocity near 0, HR stays elevated): classify as
  'stopped', not 'recovery'

**Storage:** Add `run_shape` (JSONB, nullable) column to `Activity`.
Stores `RunShape.to_dict()`. Populated when stream analysis runs.
The existing `stream_analysis_cache.py` continues to cache the full
`StreamAnalysisResult`; the shape is an additional persistent field
on Activity for fast querying by the investigation engine.

**Zone classification requires training pace profile:** The shape
extractor classifies each phase's pace zone using the athlete's
`AthleteTrainingPaceProfile.paces` when available. Without it, falls
back to stream-relative bands (same tiered approach as existing
segment detection). The zone classification is what makes the shape
meaningful — a 6:30/mi phase is "threshold" for one athlete and "easy"
for another.

**Backfill:** Run shape extraction for all activities with existing
`ActivityStream` data. Since shape extraction extends `analyze_stream()`
and most activities have cached `StreamAnalysisResult`, the per-activity
cost is ~0.5-1 second for the additional phase/acceleration computation.
Activities without cache require full analysis (~2-5 seconds). Estimated
total for ~700 activities: 15-30 minutes. Run as background Celery task.

#### Test Gate
- Shape extraction produces correct output for known activities:
  - Founder's March 4 progressive run (8:12 → 7:15, should classify
    as `progression`)
  - Father's run with strides (should detect accelerations at end)
  - BHL's structured workout (should detect threshold intervals)
- Classification matches human judgment for 10+ hand-verified activities
- Null classification for novel shapes preserves full phase/acceleration
  data
- Anomaly detection catches GPS gaps and unrealistic velocities
- Activities without stream data produce null shape (no crash)

---

### Capability 3: Investigation Registry

#### Problem
The investigation engine is a flat list of functions
(`ALL_INVESTIGATIONS`) that all query the database directly. There's
no declaration of what signals each investigation needs. There's no
way to know which investigations would activate when a new data source
(WHOOP, nutrition) connects. Honest gaps are manually maintained.

`mine_race_inputs()` recomputes everything from scratch on every request.

#### What Exists
- `ALL_INVESTIGATIONS: List[Callable]` — 10 investigation functions
- Each function signature: `(athlete_id, db, zones, events) -> Finding(s)`
- `mine_race_inputs()` iterates all investigations, collects findings
- `RaceInputFinding` dataclass with `layer`, `finding_type`, `sentence`,
  `receipts`, `confidence`
- `training_story_engine.py` synthesizes findings into `TrainingStory`

#### Build

**Investigation registry with signal declarations:**

```python
from dataclasses import dataclass
from typing import List, Optional, Callable

@dataclass
class InvestigationSpec:
    name: str
    fn: Callable
    requires: List[str]        # signal types needed
    min_activities: int = 0    # minimum outdoor activities
    min_races: int = 0         # minimum PerformanceEvents
    min_data_weeks: int = 0    # minimum weeks of data
    description: str = ""      # human-readable what this investigates

INVESTIGATION_REGISTRY: List[InvestigationSpec] = []

def investigation(requires: List[str], min_activities: int = 0,
                  min_races: int = 0, min_data_weeks: int = 0,
                  description: str = ""):
    """Decorator that registers an investigation with its signal requirements."""
    def decorator(fn):
        INVESTIGATION_REGISTRY.append(InvestigationSpec(
            name=fn.__name__,
            fn=fn,
            requires=requires,
            min_activities=min_activities,
            min_races=min_races,
            min_data_weeks=min_data_weeks,
            description=description,
        ))
        return fn
    return decorator
```

**Apply to existing investigations:**

```python
@investigation(
    requires=['activity_summary', 'activity_splits'],
    min_activities=20,
    description="Cardiovascular durability from back-to-back quality + long run days"
)
def investigate_back_to_back_durability(athlete_id, db, zones, events):
    ...

@investigation(
    requires=['activity_summary', 'activity_splits', 'environment'],
    min_activities=30,
    description="Personal heat impact on pace at equivalent HR"
)
def investigate_heat_tax(athlete_id, db, zones, events):
    ...

@investigation(
    requires=['activity_stream', 'run_shape'],  # NEW — needs shapes
    min_activities=10,
    description="Stride frequency, quality, and progression over time"
)
def investigate_stride_progression(athlete_id, db, zones, events):
    ...
```

**Runner function checks signal availability:**

```python
def get_athlete_signal_coverage(athlete_id: UUID, db: Session) -> Dict[str, bool]:
    """Check which signal types have sufficient data for this athlete."""
    # activity_summary: Activity count
    # activity_splits: ActivitySplit count
    # activity_stream: ActivityStream count
    # run_shape: Activity count where run_shape IS NOT NULL
    # daily_health: DailyCheckin count where hrv IS NOT NULL
    # environment: Activity count where temperature_f IS NOT NULL
    # race_result: PerformanceEvent count
    # subjective: DailyCheckin count where rpe IS NOT NULL

def mine_race_inputs(athlete_id, db) -> Tuple[List[RaceInputFinding], List[str]]:
    """Run investigations that have sufficient signals.
    Returns (findings, honest_gaps).
    honest_gaps = investigations that were skipped and why."""
    coverage = get_athlete_signal_coverage(athlete_id, db)
    zones = load_training_zones(athlete_id, db)
    events = load_events(athlete_id, db)

    findings = []
    honest_gaps = []

    for spec in INVESTIGATION_REGISTRY:
        # Check signal requirements
        missing = [s for s in spec.requires if not coverage.get(s)]
        if missing:
            honest_gaps.append(f"{spec.description}: needs {', '.join(missing)}")
            continue
        # Check minimum data
        if not meets_minimums(spec, athlete_id, db):
            honest_gaps.append(f"{spec.description}: not enough data yet")
            continue
        # Run investigation
        try:
            result = spec.fn(athlete_id, db, zones, events)
            if result:
                findings.extend(result if isinstance(result, list) else [result])
        except Exception as e:
            logger.error("Investigation %s failed: %s", spec.name, e)

    return findings, honest_gaps
```

**Honest gaps become automatic.** When WHOOP connects and `daily_health`
signals arrive with HRV data, `investigate_hrv_race_correlation` (which
requires `['daily_health', 'race_result']`) auto-enables. No code
change — the adapter writes `DailyCheckin` records with HRV populated.

#### Test Gate
- All 10 existing investigations produce identical output with the
  decorator applied (no behavioral change)
- An investigation requiring `['daily_health']` is correctly skipped
  for athletes without HRV data and appears in honest gaps
- `mine_race_inputs()` returns both findings and honest_gaps

---

### Capability 4: New Shape-Aware Investigations

These investigations are impossible without activity shapes. They
operate on `Activity.run_shape` (JSONB) populated by Capability 2.

#### `investigate_stride_progression`
**Question:** How did stride frequency and quality change over the
training block?

**Method:** Query activities where
`run_shape.summary.acceleration_clustering == 'end_loaded'` and
acceleration pace zone is interval or repetition. Track:
- Count per run over time
- Average acceleration pace over time
- Average duration over time
- Ratio of stride pace to easy pace (speed range)

**Finding:** "You added end-of-run strides starting in August,
averaging 4 per run. Your stride pace dropped from 6:50 to 6:20 over
12 weeks while your easy pace held steady — your speed range widened
22% without compromising aerobic development."

#### `investigate_cruise_interval_quality`
**Question:** Did threshold interval duration or pace improve over
successive sessions?

**Method:** Query activities where shape contains 2+ phases at
threshold zone lasting 4+ minutes each. Track across sessions:
- Sustained threshold duration (sum of threshold phases)
- Threshold pace (heat-adjusted)
- HR at threshold pace
- Recovery between threshold phases (duration and HR recovery)

**Finding:** "Over 8 threshold sessions from September to November,
your sustained threshold distance grew from 2.6km to 8.0km. Your
threshold HR dropped from 159 to 156 over the same period."

#### `investigate_interval_recovery_trend`
**Question:** Does recovery between interval reps improve over
successive sessions?

**Method:** Query activities with 4+ work phases at interval/rep zone.
For each session, measure the recovery phases between work phases:
- Recovery duration
- HR at end of recovery (before next rep)
- HR drop rate (bpm per second of recovery)

Track these across sessions of similar structure.

**Finding:** "Across your track sessions from July to October, your
inter-rep HR recovery improved — HR dropped to 140 within 60 seconds
by October vs 75 seconds in July. Your body is clearing fatigue
faster between efforts."

#### `investigate_workout_variety_effect`
**Question:** How does the distribution of workout types change
leading into best vs worst races?

**Method:** For each race, compute the shape classification distribution
in the 6 weeks prior. Compare distributions between top and bottom
race performances.

**Finding:** "Before your best races, you averaged 2 fartleks per
week and ran strides after 70% of easy runs. Before your weakest
race, you had zero fartleks and no strides in 4 weeks."

#### `investigate_progressive_run_execution`
**Question:** How consistent is the athlete's progressive run
execution, and does it predict race pacing quality?

**Method:** Query activities classified as `progression`. Measure:
- How evenly the pace drops across phases
- Whether final phase reaches marathon pace or faster
- HR response to the build

Correlate with race execution quality (even splits, fade, etc.)

**Finding:** "You executed 6 progressive runs from September to
November. Your final-phase pace averaged 6:55/mi at 152 bpm. Your
half marathon was paced at 6:42/mi — the progressive runs built
the gear you raced in."

---

### Integration: The Incremental Update Pipeline

#### Problem
Currently `mine_race_inputs()` recomputes all investigations on every
API request. Findings aren't stored. Shape extraction doesn't run
after ingestion.

#### Build

**Step 1: Shape extraction in the ingestion pipeline**

When a new activity syncs and its stream is fetched:
- `post_sync_processing_task` already runs after Strava sync
- Add a step: if `ActivityStream` exists, run shape extraction,
  store `run_shape` on Activity
- For Garmin: `process_garmin_activity_detail_task` stores streams,
  add shape extraction after stream storage

**Step 2: Weather normalization at ingestion**

When weather data is backfilled or arrives with the activity:
- Compute `dew_point_f` and `heat_adjustment_pct`
- Store on Activity
- If shape already exists and has phases, update heat-adjusted paces
  in the shape

**Step 3: Periodic fingerprint refresh**

A Celery beat task (daily or after sync) runs the investigation
registry for athletes with new data. Findings are stored in an
evolved version of the existing `fingerprint_finding` table.

**Migration path (H1 resolution):** The existing
`StoredFingerprintFinding` model (`fingerprint_finding` table, defined
at `models.py:610`, migration
`alembic/versions/fingerprint_1b_create_findings_table.py`) has 6
rows of Phase 1B findings. **Migrate** the existing table:

- Rename model from `StoredFingerprintFinding` to `AthleteFinding`
  (keep tablename `fingerprint_finding` to avoid data loss)
- Add columns: `investigation_name` (Text), `first_detected_at`
  (DateTime), `last_confirmed_at` (DateTime), `superseded_at`
  (DateTime, nullable), `is_active` (Boolean, default True)
- Rename `evidence` → `receipts` (JSONB)
- Rename `confidence_tier` → `confidence` (Text)
- Drop columns no longer needed: `statistical_confidence` (Float),
  `effect_size` (Float), `sample_size` (Integer)
- Backfill existing 6 rows: set `investigation_name` from
  `finding_type`, `first_detected_at` = `created_at`,
  `last_confirmed_at` = `created_at`, `is_active` = True
- Update `fingerprint_analysis.py` and `routers/fingerprint.py` to
  use the new model name and columns

Final schema:
```python
class AthleteFinding(Base):
    __tablename__ = "fingerprint_finding"
    id = Column(UUID, primary_key=True, default=uuid4)
    athlete_id = Column(UUID, ForeignKey("athlete.id"), nullable=False, index=True)
    finding_type = Column(Text, nullable=False, index=True)
    layer = Column(Text, nullable=False)
    sentence = Column(Text, nullable=False)
    receipts = Column(JSONB, nullable=False)
    confidence = Column(Text, nullable=False)
    investigation_name = Column(Text, nullable=False)
    first_detected_at = Column(DateTime(timezone=True), server_default=func.now())
    last_confirmed_at = Column(DateTime(timezone=True), server_default=func.now())
    superseded_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    computation_version = Column(Integer, nullable=False, default=1)
```

**Supersession logic (Opus point 3):** Match on
`investigation_name + finding_type`. One active finding per
investigation per finding_type per athlete. When the investigation
runs again, it replaces the previous finding for that
(investigation_name, finding_type) pair. Simple, deterministic,
no ambiguity.

When investigations rerun after new data:
- New findings that don't match an existing
  `(investigation_name, finding_type)` → insert
- Findings that match → update `last_confirmed_at`, `receipts`,
  `sentence`
- Findings that previously existed but the investigation no longer
  produces → set `superseded_at = now()`, `is_active = False`

**Step 4: Training story reads from stored findings**

`synthesize_training_story()` reads from `AthleteFinding` (active
only) instead of recomputing. The training story is itself cached
and invalidated when findings change.

**Step 5: Coach reads from fingerprint**

`_build_rich_intelligence_context()` in `home.py` reads from stored
findings and cached training story. No recomputation on the API
request path.

#### What NOT to build

- **Full dependency graph for selective invalidation.** Run all
  eligible investigations after sync. It's 10-15 functions. Total
  compute time is seconds. Selective invalidation is overengineering.
- **Separate signal store / append-only timeline.** Postgres is the
  signal store. The models are the signal types.
- **data_coverage metadata table.** Query the models directly.
  `SELECT COUNT(*) FROM daily_checkin WHERE hrv IS NOT NULL` tells
  you HRV coverage.

---

## Narrative Constraints

These apply to every finding, every training story, every coach
output that references fingerprint data.

1. **Never say "because."** The system has correlation, timing, and
   co-occurrence. It presents evidence. The athlete draws conclusions.
   "Your HRV improvement coincided with the period when easy volume
   exceeded 50 miles per week" — not "because of."

2. **Never hardcode paces, distances, or assumptions.** Use the
   athlete's training pace profile for zone classification. Use
   stream-relative percentiles as fallback. A 6:30/mi acceleration
   is "threshold" for one athlete and "easy" for another.

3. **Connections are emergent, not predefined.** The investigation
   engine finds what's actually in the data. Connections between
   findings emerge from temporal overlap and co-occurrence, not from
   a predefined list of relationships. The existing Training Story
   Engine uses connection type categories (input_to_adaptation,
   adaptation_to_outcome, compounding) as a *lens* for viewing
   connections — the taxonomy is how connections are displayed, not
   a constraint on what connections can exist. Which findings connect
   to which is discovered from the data. The categories just describe
   the nature of each discovered connection.

4. **Suppression over hallucination.** If a finding doesn't clear
   the statistical gate, it doesn't surface. Silence is better than
   a confident wrong answer.

5. **No template narratives.** If the system can't say something
   genuinely specific to this athlete's data, it says nothing.

---

## Build Sequence

| Phase | Days | What | Depends On |
|---|---|---|---|
| 1 | 1-2 | Weather normalization service + backfill | Nothing |
| 2 | 1 | Investigation registry decorator + honest gaps | Nothing |
| 3 | 3-5 | Activity shape extractor + backfill | Nothing (M1: heat-adjusted paces in phases are Optional — filled in by a final pass after Phase 1 completes) |
| 4 | 2-3 | Shape-aware investigations | Phase 2 + Phase 3 |
| 5 | 1-2 | AthleteFinding migration + stored findings + incremental worker | Phase 2 |
| 6 | 1 | Training story + coach reads from stored findings | Phase 5 |

**Phases 1, 2, and 3 are independent and can be built in parallel**
(M1 resolution). Phase 1 writes `dew_point_f` and
`heat_adjustment_pct` to Activity. Phase 3 writes `run_shape` to
Activity with `avg_pace_heat_adjusted = null`. A final pass after
both complete fills in heat-adjusted paces on existing shapes.
Phase 3 is the largest and hardest engineering.
Phase 4 is where the product value emerges.
Phases 5 and 6 are plumbing that makes everything production-quality.

**Backfill ordering (L3 resolution):** Phases 1 and 3 backfills can
run in parallel. After both complete, a final pass updates
`avg_pace_heat_adjusted` on shapes using the weather data. This
ordering is enforced in the backfill orchestration script.

---

## Validation Gate (Human Gate — Founder Review)

**Gate L is a human gate.** The builder presents:

1. Shape extraction output for 10+ activities (including founder's
   runs, father's runs, BHL's runs). The founder verifies the shapes
   match what actually happened.

2. Weather-normalized investigation findings vs raw findings. The
   founder evaluates whether normalization improved accuracy.

3. New shape-aware findings (stride progression, cruise interval
   quality, interval recovery trends). The founder evaluates: "does
   this tell me something I didn't know?"

4. The updated training story with shape-aware findings integrated.

The bar: the founder's father runs strides and the system notices.
The founder runs a progressive run and the system describes the
build. BHL's structured workout is correctly decomposed into warmup,
threshold intervals, and cooldown without BHL typing it in the
activity name.

If the system can describe the shape of a run accurately, classify
it when a known pattern matches, and mine genuine insights from
shapes across hundreds of activities — Gate L passes.

If it produces another statistical observation about average long
run distance — Gate L fails and the shape extractor goes deeper.

---

## Ground Truth for Shape Verification

Activity UUIDs for querying (M4 resolution):

**1. Founder's March 4 progressive run**
- UUID: `65543f5b-8ae7-455e-9b8f-26891a8a1203`
- Athlete: `4368ec7f-c30d-45ff-a6ee-58db7716be24` (mbshaf@gmail.com)
- 9,667m, 6 miles, 2,942 stream points
- Splits: 8:12 → 7:49 → 7:41 → 7:46 → 7:39 → 7:15
- Expected classification: `progression`
- Expected summary: pace_progression = `building`, 6 phases,
  final phase approaching marathon pace

**2. Father Larry's run with strides**
- UUID: `04ed985d-7f1c-4243-aea2-988ce5453f2d`
- Athlete: `d0065617-41c3-47fb-8257-64abfd561a31` (wlsrangertug@gmail.com)
- 1,769m, ~1.1 miles, 842 stream points
- Split: 1 mile at ~12:00
- Expected: strides detected if they happened — accelerations in
  final portion at zone >= marathon (relative to Larry's zones).
  Classified as `strides` or `easy_run` based on what stream shows.
- **Acid test:** if the shape extractor can't see Larry's strides,
  it's not ready

**3. BHL's structured threshold workout**
- UUID: `51c8cdb6-5f37-46ab-b0ae-b87dec3d0910`
- Athlete: `703b9728-3d97-4295-89a7-320acac74416` (bhlevesque@gmail.com)
- 8,466m, ~5.25 miles, 691 stream points
- Name: "1 mile warmup, 2@8:00, 1@7:30, 1 mile cool down"
- Splits: 8:47 → 7:46 → 7:41 → 7:30 → 8:27 → 8:01
- Expected classification: `threshold_intervals`
- Expected phases: warmup (easy zone), 3 work phases (threshold
  zone), cooldown (easy zone)

**4. Plain easy run (Opus addition: over-detection test)**
- Find a founder easy run with no structure (no strides, no tempo,
  no intervals). Query: `Activity` with `workout_type = 'easy_run'`,
  has `ActivityStream`, distance 4-8 miles.
- Expected classification: `easy_run`
- Expected: 1 phase (possibly with warmup/cooldown), 0
  accelerations. The shape extractor must NOT find structure that
  isn't there. Over-detection is as bad as under-detection.

**Backfill time (M5 correction):** Shape extraction extends
`analyze_stream()`. For activities with cached `StreamAnalysisResult`,
the additional phase/acceleration computation is ~0.5-1 second, not
5-10 seconds. For activities without cache, the full stream analysis
runs (~2-5 seconds). Backfill of ~700 activities should complete in
15-30 minutes, not 1-2 hours.

---

## Future Extensibility

When a new data source connects (WHOOP, nutrition, CGM):

1. Write an adapter that transforms raw data into existing model
   writes (e.g., WHOOP → `DailyCheckin` with HRV, sleep, recovery)
2. Write new investigations decorated with
   `@investigation(requires=['daily_health'])` or whatever signals
   the new source provides
3. The registry auto-enables them when the data exists

No architecture changes. No schema migrations for the fingerprint.
The investigation registry is the extension point.

---

## Rules

- Scoped commits only. Never `git add -A`.
- Show evidence, not claims. Paste test output.
- Suppression over hallucination.
- No acronyms in athlete-facing text.
- Tree clean, tests green, production healthy at end of session.
- The athlete decides, the system informs.

---

## Deploy Process

```bash
ssh root@187.124.67.153
cd /opt/strideiq/repo && git pull origin main && docker compose -f docker-compose.prod.yml up -d --build
docker logs strideiq_api --tail=50
```
