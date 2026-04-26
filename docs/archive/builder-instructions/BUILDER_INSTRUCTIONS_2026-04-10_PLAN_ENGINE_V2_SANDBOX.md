# StrideIQ Plan Engine V2 — Sandbox Builder Instructions

**Date:** April 10, 2026
**Status:** Ready to build
**Depends on:** `docs/specs/PLAN_GENERATOR_ALGORITHM_SPEC.md` (the algorithm)
**This document:** How to build and test it safely

---

## Philosophy: We Learn From Sources, We Don't Replicate Them

The `docs/references/` folder contains KB documents from multiple
coaching and physiological sources: John Davis, Jon Green, David and
Megan Roche, Peter Coe, and a broad exercise physiology synthesis.
These are INPUTS to StrideIQ's own system — not templates to copy.

- **Davis** gives us the theoretical framework: the four components of
  marathon fitness, the ladder of support, three-phase periodization,
  the principle that extension is the progression (not speed).
- **Green** gives us the adaptive coaching philosophy: plans written in
  pencil, the athlete decides, suppression over hallucination.
- **Roche** gives us concrete plan structures to learn from: distance
  ranges, effort-based prescription, workout variety, the hierarchy
  of interventions.
- **Coe** gives us multi-pace training principles and the value of
  short, intense stimuli for economy.
- **The founder** gives us the quality bar: a physicist with coaching
  credentials and decades of competitive experience who can produce
  a better plan on a napkin than most certified coaches.

StrideIQ's generator synthesizes ALL of these into its own system.
Workout types are named by what they DO (e.g., "sustained_threshold_long"
not "Power Hour"). The effort dictionary is StrideIQ's own, informed
by multiple sources. The periodization blends Davis's three-phase model
with Canova's specificity funnel and the founder's practical experience.

When a reference doc says "SWAP does X," read it as "here's a pattern
we can learn from." When the algorithm spec says "do X," that's what
we actually build.

---

## Prime Directive

V2 must not write to any athlete's active plan. It reads production
data. It writes only to preview/temp storage. No athlete sees V2
output until the cutover flag is flipped on their account.

The current engine (`services/plan_framework/`) stays completely
untouched. Not one line changes in V1 until V2 passes all quality
gates and the founder manually reviews output.

---

## Read Order (mandatory before writing code)

The full read order is defined in `docs/PLAN_ENGINE_V2_MASTER_PLAN.md`.
You should have already read documents 1-2 before arriving here.

1. `docs/PLAN_ENGINE_V2_MASTER_PLAN.md` — start here, the north star
2. `docs/wiki/index.md` → then `docs/wiki/plan-engine.md` — understand
   the full system and where V2 fits
3. **This document** — how to build safely
4. `docs/specs/PLAN_GENERATOR_ALGORITHM_SPEC.md` — the algorithm
   (single source of truth for all generation logic)

Then, before implementing specific modules:

5. `docs/references/ROCHE_SWAP_TRAINING_PHILOSOPHY_UNIFIED_2026-04-10.md`
   (why the algorithm is structured this way — hierarchy, bottleneck,
   speed theory, threshold theory, fatigue resistance)
6. `docs/references/ROCHE_SWAP_EFFORT_DICTIONARY_2026-04-10.md`
   (mandatory — every athlete-facing effort term)
7. `docs/references/ROCHE_SWAP_WORKOUT_EXECUTION_GUIDE_2026-04-10.md`
   (how every workout type is executed)

Do NOT start coding before reading documents 1-4. If you haven't
read them, you will build the wrong thing.

---

## Step 1 — Directory Structure

Create inside the existing repo. Do not create a new repo or branch.

```
apps/api/services/plan_engine_v2/
├── __init__.py
├── engine.py                # orchestrator — the only public entry point
├── pace_ladder.py           # full percentage-based pace ladder from RPI
├── segments_builder.py      # unified segment schema population
├── effort_mapper.py         # internal % MP → athlete-facing effort text
├── progression.py           # extension-based + build-over-build + variety-based
├── periodization.py         # phase construction by mode and distance
├── workout_library.py       # workout builders for every type in the KB
├── fueling.py               # fueling targets for ≥90 min workouts
├── distance_ranges.py       # range computation by mode, training age, day role
├── long_run_rotation.py     # A/B/C long run type cycling
├── models.py                # V2-specific dataclasses (PaceLadder, PhaseStructure, etc.)
└── evaluation/
    ├── __init__.py
    ├── harness.py           # run V1 + V2 on same inputs, compare
    ├── quality_gate.py      # V2 validation criteria (all must pass)
    ├── synthetic_athletes.py # 15 fixed test profiles
    └── report.py            # side-by-side comparison output
```

---

## Step 2 — Shared Imports (Read-Only)

V2 imports the following from existing code. It does not copy, modify,
or redefine them.

```python
from models import TrainingPlan, PlannedWorkout, Athlete
from services.fitness_bank import get_athlete_fitness_profile
from services.workout_prescription import calculate_paces_from_rpi
```

`calculate_paces_from_rpi()` is sacred. Daniels zones do not change.
V2 uses these paces as its foundation and extends them with the
percentage-based ladder that fills the gaps BETWEEN named zones.

---

## Step 3 — Module Responsibilities

### `models.py` (V2 dataclasses)

```python
from dataclasses import dataclass

@dataclass
class PaceLadder:
    """Full percentage-based pace ladder for one athlete.

    Every value is seconds-per-km. Values derived from
    calculate_paces_from_rpi() as the anchor, then filled
    by interpolation for unnamed percentages.
    """
    paces: dict[int, int]
    # key = percentage of MP (70, 75, 80, 85, 88, 90, 92, 95,
    #        97, 100, 101, 103, 105, 108, 110, 115, 120)
    # value = pace in seconds per km

    easy_floor: int        # 70% MP — slowest prescribed pace
    easy_ceiling: int      # 80% MP
    marathon: int          # 100% MP — the anchor
    threshold: int         # 103-105% MP (from Daniels)
    vo2max: int            # 110-115% MP (from Daniels)
    repetition: int        # 120%+ MP (from Daniels)

    # Named zone values come from calculate_paces_from_rpi().
    # Intermediate percentages are interpolated linearly.


@dataclass
class WorkoutSegment:
    """Unified segment schema — matches PLAN_GENERATOR_ALGORITHM_SPEC §5."""
    type: str
    # One of: warmup, cooldown, work, float, jog_rest, easy,
    # threshold, interval, stride, steady, hike,
    # fatigue_resistance, uphill_tm

    pace_pct_mp: int              # internal only — NEVER shown to athlete
    pace_sec_per_km: int          # concrete number athlete sees
    distance_km: float | None     # one of distance or duration required
    duration_min: float | None
    reps: int | None              # for repeated intervals
    rest_min: float | None        # recovery between reps
    grade_pct: float | None       # for uphill_tm and hill segments
    fueling_target_g_per_hr: int | None  # for workouts ≥90 min
    description: str              # athlete-facing effort language


@dataclass
class PhaseStructure:
    phases: list  # ordered list of Phase objects
    total_weeks: int
    mode: str     # race, build_onramp, build_volume, build_intensity, maintain


@dataclass
class Phase:
    name: str          # general, supportive, specific, taper, build, onramp
    weeks: int
    focus: str         # human description of phase goal
    quality_density: int  # quality sessions per week (0-2)
    workout_pool: list[str]  # which workout types are available


@dataclass
class FuelingPlan:
    during_run_carbs_g_per_hr: int
    notes: str  # athlete-facing guidance in plain language


@dataclass
class WorkoutProgression:
    """Tracks extension state within a block for build-over-build."""
    workout_key: str
    current_duration_min: float
    current_distance_km: float
    current_reps: int
    pace_sec_per_km: int
    block_number: int
```

---

### `pace_ladder.py`

Exports `compute_pace_ladder(rpi: float) -> PaceLadder`.

1. Call `calculate_paces_from_rpi(rpi)` to get named Daniels zones
2. Set `marathon` (100% MP) as the anchor
3. Compute every percentage from 70% to 120% by interpolation:
   - Named zones (easy, threshold, vo2max, repetition) are pinned
     to their Daniels values
   - Intermediate percentages are linearly interpolated between
     the nearest named zones
4. Return the full `PaceLadder`

No hardcoded pace values anywhere in V2. Everything flows from RPI.

Ref: Algorithm Spec §3 ("The Pace Ladder").

---

### `effort_mapper.py`

Exports `map_effort(pct_mp: int) -> str`.

Maps internal percentage to athlete-facing effort text. StrideIQ's
effort vocabulary draws from established coaching terminology (Davis,
Daniels, Roche) but is our own system. The mapping table:

| Internal % MP | Athlete-facing term |
|--------------|---------------------|
| 70-80% | Easy / very easy |
| 80-88% | Easy/mod |
| 88-92% | Moderate / steady / 50K effort |
| 92-95% | Steady to moderate |
| 95-100% | Marathon effort |
| 101-103% | Half marathon effort |
| 103-105% | 1-hour effort / threshold |
| 105-110% | 10K effort |
| 110-115% | 5K effort |
| 115-120% | 3K effort |
| 120%+ | Mile effort / fast strides |

No athlete-facing text in V2 ever contains a percentage, "% MP",
or pace formula. Percentages exist only in `pace_pct_mp` fields
(internal metadata for weather adjustment and post-workout analysis).

Ref: `docs/references/ROCHE_SWAP_EFFORT_DICTIONARY_2026-04-10.md`
is one reference for effort terminology — read it for inspiration,
but the mapping above is StrideIQ's canonical version.

---

### `segments_builder.py`

Exports `build_segments(workout_type: str, ladder: PaceLadder,
params: dict) -> list[WorkoutSegment]`.

Every structured workout MUST have segments populated. Easy and rest
days may have null segments.

13 segment types: `warmup`, `cooldown`, `work`, `float`, `jog_rest`,
`easy`, `threshold`, `interval`, `stride`, `steady`, `hike`,
`fatigue_resistance`, `uphill_tm`.

Every segment includes BOTH `pace_pct_mp` (internal) AND
`pace_sec_per_km` (athlete-facing). The effort `description` is
generated by `effort_mapper.map_effort()`.

Ref: Algorithm Spec §5 ("Segments Schema").

---

### `workout_library.py`

Exports a registry of workout builder functions. Each takes
`(ladder: PaceLadder, params: dict)` and returns a fully-populated
workout with segments.

**Minimum required workout types:**

Workout types are named by what they DO, not by any coach's brand name.
The KB reference docs inform the execution details but the names and
structures belong to StrideIQ.

| Key | What it does | KB source for execution details |
|-----|-------------|-------------------------------|
| `easy` | Easy/mod run with distance range | Physiology synthesis: easy volume |
| `easy_strides_flat` | Easy + 4-8×20-30s flat strides at end | Multiple: economy stimulus |
| `easy_strides_hill` | Easy + 4-8×30-45s hill strides at end | Multiple: power + economy |
| `long_run_a` | Easy/mod progressive (natural, no structure) | Davis: general aerobic development |
| `long_run_b` | Threshold segments within long run | Davis: supportive phase work |
| `long_run_c` | Fatigue resistance (hard efforts at END when depleted) | Davis: resilience development |
| `threshold_uphill_tm` | Uphill treadmill threshold intervals | Multiple: controlled threshold training |
| `threshold_cruise` | Flat tempo/cruise intervals | Daniels: threshold development |
| `vo2max_track` | Track intervals (400-1000m) | Multiple: vVO2 stimulus |
| `vo2max_hills` | Hill intervals (2-4 min) at VO2 effort | Multiple: power + VO2 |
| `hills_short` | 8-12×30-45s short hills for power | Multiple: neuromuscular power |
| `hills_plus_steady` | Short hills + sustained moderate combo | Combo: power → lactate shuttling |
| `speed_plus_threshold` | Fast intervals + threshold combo | Combo: ceiling → sustain |
| `sustained_threshold_long` | 60-90 min sustained mod/hard effort | Race-specific: ultra simulation |
| `fatigue_resistance_finish` | Hard efforts at END of long run | Davis: resilience under depletion |
| `back_to_back_day2` | Moderate run day after long run | Ultra-specific: accumulated fatigue |
| `run_hike` | Alternating run/hike segments | Beginner ultra: manage biomechanical load |
| `z2_uphill_tm` | Continuous easy on treadmill at grade | Supplemental: climbing-specific Z2 |
| `steady_moderate` | Sustained moderate effort (not threshold) | General: lactate shuttling |
| `race_day` | Race with fueling protocol | — |
| `rest` | Complete rest day | — |
| `cross_train` | X-train (bike, swim, elliptical) | — |

This is the minimum set. Additional variants may be needed for specific
plan modes. The KB reference documents describe HOW each concept works
(physiological rationale, execution cues, progression rules) — read
them to understand the principles, then implement StrideIQ's version.

---

### `long_run_rotation.py`

Exports `next_long_run_type(previous: str) -> str`.

Three types rotate: A → B → C → A → B → C.

- **Type A (Easy Progressive):** Start easy, let the run come to you.
  Natural progression in the final third if the body says yes. No
  structured segments. No prescribed fast finish.
- **Type B (Threshold Segments):** 15-20 min easy warm-up, 1-3
  structured intervals at threshold or marathon effort (e.g., 3×1mi
  at 1hr effort, 20min at HM effort), 10 min cool-down.
- **Type C (Fatigue Resistance):** Easy/mod for most of the run.
  Final 2-3 miles: 4-8×30-45s hills at 3K-5K effort, or 4×2min at
  10K effort. The fatigue from the long run IS the setup — these are
  not standalone hill intervals.

No athlete gets the same long run type two weeks in a row.

This rotation is a StrideIQ design decision informed by multiple
coaching traditions (Davis's specificity progression, Daniels's phase
emphasis, and observed plan structures across the KB). The three types
map to the three physiological targets: aerobic development (A),
sustained speed (B), and resilience under fatigue (C).

---

### `distance_ranges.py`

Exports `compute_range(day_role: str, mode: str, training_age_years: int,
peak_weekly_km: float) -> tuple[float, float]`.

Returns `(min_km, max_km)`. SWAP plans use wide, human-scale ranges
that vary by plan mode and day role:

| Day role | Typical range |
|----------|--------------|
| Easy (low-volume athlete) | 5-8 km |
| Easy (mid-volume) | 8-13 km |
| Easy (high-volume) | 10-16 km |
| Long run (HM plan) | 16-26 km |
| Long run (Marathon plan) | 16-32 km |
| Long run (Ultra plan) | 16-40 km |
| Long run (Onramp) | 6-10 km |

These are NOT computed as ±15% of a target. They are human-scale
ranges derived from successful coaching practice (Green, Roche, and
others all use wide ranges), scaled to the athlete's current weekly
volume. The athlete chooses where in the range based on feel. This
embodies Green's "plans written in pencil" philosophy.

Ref: Algorithm Spec §9 ("Distance Ranges").

---

### `progression.py`

Exports:
- `apply_extension(workout, week_in_block, block_position) -> workout`
- `seed_from_previous_block(current_block, previous_peak_state) -> None`

**Three progression types** (determined by plan mode and distance):

1. **Extension-based (Marathon, HM, Ultra, Build-Volume):**
   Pace stays CONSTANT within a block. Segment duration/distance
   grows week over week.
   - Threshold: 5min → 7min → 9min → 10min at same effort
   - Speed: 400m → 800m → 1200m → mile at same pace
   - Long run: grows 1-2 mi/week with down week every 4th (-20%)
   - Recovery between intervals may shrink (2min → 90s → 1min)

2. **Variety-based (5K, 10K):**
   Speed sessions rotate structures weekly — NOT pure extension.
   Week 1: 400s. Week 2: 600s. Week 3: pyramid. Week 4: off-track
   threshold. Each week targets VO2max/economy with novel stimulus.

3. **Hybrid alternating (Champion Ultra 100K-100mi):**
   Speed weeks and threshold weeks alternate, then converge in the
   final phase. Speed → Threshold → Speed → Threshold → Convergence.

**Build-over-build seeding:**
`TrainingPlan.peak_workout_state` stores the peak workout parameters
from the final week of each block. The next block's opening week
starts at or above the previous block's week 1 values (never below
the previous peak's starting point).

Ref: Algorithm Spec §6 ("Extension-Based Progression"),
Algorithm Spec §7 ("Build-Over-Build Progression").

---

### `periodization.py`

Exports `build_phases(mode, distance, weeks_available, training_age)
-> PhaseStructure`.

Phase structures vary by mode AND distance:

**Race mode — Marathon/HM:**

| Weeks available | General | Supportive | Specific | Taper |
|----------------|---------|------------|----------|-------|
| 16-20 | 4-6 | 4-6 | 4-6 | 2 |
| 12-15 | 2-4 | 4 | 4-5 | 1-2 |
| 8-11 | 0-2 | 3-4 | 3-4 | 1 |

**Race mode — 5K/10K:**

| Phase | Weeks | Focus |
|-------|-------|-------|
| Economy + Aerobic | 4-6 | Strides, hills, easy volume |
| Race-specific | 4-6 | Variety-based speed, race-effort long runs |
| Taper | 1 | Reduced volume, sharp stimuli |

**Race mode — Ultra (50K-50mi Intermediate/Advanced):**

| Phase | Weeks | Focus |
|-------|-------|-------|
| Speed + Power | 3-4 | Hill intervals, VO2, strides |
| Threshold Bridge | 3-4 | Uphill TM threshold, steady runs |
| Race-specific | 3-4 | Back-to-backs, Power Hour, altitude sim |
| Taper | 1-2 | Within final phase |

**Race mode — Ultra (100K-100mi Champion):**

| Phase | Weeks | Focus |
|-------|-------|-------|
| Hybrid alternating | 8-10 | Speed↔Threshold weeks alternate |
| Convergence | 2-3 | Both combined |
| Embedded race (optional) | 1 | Mid-cycle marathon/50K |
| Recovery | 1 | Post-embedded-race |
| Re-ignition + taper | 2-3 | Final peak + taper |

**Build-Onramp:** 8 weeks, single phase. 4 runs/week. No threshold.
Hill strides + easy volume + distance-effort alternation weeks.

**Build-Volume:** 6 weeks repeatable. General phase only. 1 quality
day (alternating speed/threshold by week). BONUS WEEK every 7th cycle.

**Build-Intensity:** 4 weeks. Supportive phase. 2 quality days.
Athletes must graduate from Build-Volume first.

**Maintain:** 4 weeks repeatable. 1 quality day. Effort diversity.
Hold current fitness without progressive overload.

Ref: Algorithm Spec §4 ("Periodization"). Phase structures synthesize
Davis's three-phase model (general → supportive → specific), Canova's
specificity funnel, and practical patterns observed across multiple
coaching traditions in the KB reference documents.

---

### `fueling.py`

Exports `compute_fueling(workout, training_age_years) -> FuelingPlan | None`.

Returns `None` for workouts under 90 minutes total duration.

For ≥90 minutes:

| Training age | Carbs g/hr | Notes text |
|-------------|-----------|------------|
| 0-2 years | 60 | "Practice fueling: aim for 60 g/hr carbs. Start at minute 30. Building gut tolerance is training." |
| 2-5 years | 75 | "Practice race fueling: target 75 g/hr carbs starting at minute 30." |
| 5+ years | 75-90 | "Fuel at your practiced rate (75-90 g/hr). Start early, don't wait until you're hungry." |
| Race day | athlete's practiced rate | "Execute your fueling plan: [rate] g/hr carbs, [fluid] ml/hr. You've practiced this." |

The fueling plan is attached to the workout AND mentioned in the
workout description. "This is training your gut as much as your legs."

Ref: Algorithm Spec §10 ("Workout Description Quality Bar"). Fueling
science drawn from multiple sources (the fueling reference doc
synthesizes current sports nutrition research, not a single coach's
protocol).

---

### `engine.py`

The orchestrator. Single public entry point:

```python
def generate_plan_v2(
    athlete_id: uuid.UUID,
    mode: str,
    # "race" | "build_onramp" | "build_volume" | "build_intensity" | "maintain"
    goal_event: str | None = None,
    # "5K" | "10K" | "half_marathon" | "marathon" | "50K" | "50_mile"
    # | "100K" | "100_mile" | None (for Build/Maintain)
    target_date: date | None = None,
    previous_peak_state: dict | None = None,
    preview_only: bool = True,
) -> dict:
    """Returns serialized plan + quality gate result."""
```

`preview_only=True` is the default. MUST remain True until cutover.

**Execution order:**

1. Load athlete profile from `get_athlete_fitness_profile()`
2. Compute pace ladder from RPI via `calculate_paces_from_rpi()`
3. Determine training age from athlete profile
4. Build phase structure from mode + distance + weeks
5. For each phase and week:
   a. Select workout types from the phase's workout pool
   b. Build workouts using `workout_library` builders
   c. Apply distance ranges to easy/long runs
   d. Rotate long run types (A/B/C)
   e. Populate segments on all structured workouts
   f. Map effort language on all segments and descriptions
   g. Attach fueling plans to qualifying workouts
6. Apply extension progression within each phase
7. If `previous_peak_state` provided, apply build-over-build seeding
8. Run quality gate — if ANY check fails, raise
   `PlanEngineV2ValidationError` with failing checks. Do NOT return
   a partial plan.
9. Serialize and save to `plan_preview` table
10. Return serialized plan + gate result

---

## Step 4 — Database

One new table only:

```sql
CREATE TABLE plan_preview (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    athlete_id UUID REFERENCES athlete(id),
    engine_version VARCHAR(10) DEFAULT 'v2',
    mode VARCHAR(30),
    goal_event VARCHAR(30),
    generated_at TIMESTAMPTZ DEFAULT NOW(),
    plan_json JSONB,
    quality_gate_passed BOOLEAN,
    quality_gate_details JSONB,
    notes TEXT
);
```

V2 NEVER writes to `training_plan` or `planned_workout`. Only to
`plan_preview`. Preview records are not shown to athletes. They are
safe to delete.

---

## Step 5 — Evaluation Harness

### `synthetic_athletes.py`

15 fixed profiles. Version-controlled. Do not change between runs.

```python
PROFILES = [
    # Training age = years of consistent running
    {
        "id": "beginner_5k",
        "rpi": 35, "days_per_week": 3, "weekly_miles": 12,
        "training_age": 0.5, "goal_event": "5K",
        "weeks_to_race": 10, "mode": "race",
    },
    {
        "id": "developing_10k",
        "rpi": 42, "days_per_week": 4, "weekly_miles": 22,
        "training_age": 2, "goal_event": "10K",
        "weeks_to_race": 10, "mode": "race",
    },
    {
        "id": "developing_hm",
        "rpi": 45, "days_per_week": 4, "weekly_miles": 28,
        "training_age": 3, "goal_event": "half_marathon",
        "weeks_to_race": 12, "mode": "race",
    },
    {
        "id": "established_marathon",
        "rpi": 55, "days_per_week": 5, "weekly_miles": 45,
        "training_age": 8, "goal_event": "marathon",
        "weeks_to_race": 16, "mode": "race",
        "notes": "Founder profile — review this one manually",
    },
    {
        "id": "masters_marathon",
        "rpi": 50, "days_per_week": 5, "weekly_miles": 38,
        "training_age": 20, "goal_event": "marathon",
        "weeks_to_race": 18, "mode": "race",
    },
    {
        "id": "advanced_50k",
        "rpi": 58, "days_per_week": 6, "weekly_miles": 55,
        "training_age": 6, "goal_event": "50K",
        "weeks_to_race": 12, "mode": "race",
    },
    {
        "id": "champion_100mi",
        "rpi": 65, "days_per_week": 6, "weekly_miles": 75,
        "training_age": 10, "goal_event": "100_mile",
        "weeks_to_race": 16, "mode": "race",
    },
    {
        "id": "onramp_brand_new",
        "rpi": None, "days_per_week": 3, "weekly_miles": 0,
        "training_age": 0, "goal_event": None,
        "weeks_to_race": None, "mode": "build_onramp",
        "notes": "No RPI — brand new runner. Paces from defaults.",
    },
    {
        "id": "build_volume_low",
        "rpi": 40, "days_per_week": 4, "weekly_miles": 20,
        "training_age": 1, "goal_event": None,
        "weeks_to_race": None, "mode": "build_volume",
    },
    {
        "id": "build_volume_high",
        "rpi": 56, "days_per_week": 5, "weekly_miles": 50,
        "training_age": 5, "goal_event": None,
        "weeks_to_race": None, "mode": "build_volume",
    },
    {
        "id": "build_intensity",
        "rpi": 52, "days_per_week": 5, "weekly_miles": 40,
        "training_age": 4, "goal_event": None,
        "weeks_to_race": None, "mode": "build_intensity",
    },
    {
        "id": "maintain_casual",
        "rpi": 42, "days_per_week": 3, "weekly_miles": 18,
        "training_age": 3, "goal_event": None,
        "weeks_to_race": None, "mode": "maintain",
    },
    {
        "id": "short_build_hm",
        "rpi": 48, "days_per_week": 4, "weekly_miles": 30,
        "training_age": 3, "goal_event": "half_marathon",
        "weeks_to_race": 8, "mode": "race",
        "notes": "Compressed timeline — tests phase allocation",
    },
    {
        "id": "first_marathon",
        "rpi": 44, "days_per_week": 4, "weekly_miles": 25,
        "training_age": 2, "goal_event": "marathon",
        "weeks_to_race": 20, "mode": "race",
        "notes": "First-time marathoner — fueling targets critical",
    },
    {
        "id": "return_from_injury",
        "rpi": 48, "days_per_week": 3, "weekly_miles": 10,
        "training_age": 5, "goal_event": None,
        "weeks_to_race": None, "mode": "build_onramp",
        "notes": "Experienced runner rebuilding — tests onramp for non-beginners",
    },
]
```

### `quality_gate.py`

Every check must pass. A single failure returns `passed=False`.

```python
GATE_CHECKS = [
    # Segments
    "all_structured_workouts_have_segments",
    "all_segments_have_pace_pct_mp_and_pace_sec_per_km",
    "all_segment_types_are_valid",          # from the 13-type enum
    "hill_and_tm_segments_have_grade_pct",

    # Effort language
    "no_percentage_in_athlete_descriptions", # no "105% MP", "90% MP"
    "no_rpi_in_athlete_descriptions",
    "all_descriptions_use_effort_dictionary_terms",

    # Fueling
    "all_workouts_gte_90min_have_fueling_target",
    "fueling_scales_with_training_age",
    "race_day_has_full_fueling_protocol",

    # Distance ranges
    "all_easy_runs_have_distance_range",     # min != max
    "all_long_runs_have_distance_range",

    # Long run rotation
    "no_consecutive_same_long_run_type",     # A/B/C rotation

    # Progression
    "extension_pace_constant_within_block",  # pace doesn't increase
    "extension_duration_grows_within_block",  # duration/distance grows
    "build_over_build_seeds_correctly",       # block N+1 >= block N week 1

    # Periodization
    "race_mode_has_correct_phases",           # general+supportive+specific+taper
    "build_onramp_has_no_threshold",          # first 8 weeks no threshold
    "build_volume_has_no_taper",
    "5k_10k_uses_variety_progression",        # not extension
    "ultra_champion_uses_hybrid_alternating",

    # Paces
    "all_paces_within_valid_range",          # easy floor to rep ceiling
    "named_daniels_zones_match_rpi",         # threshold = calculate_paces value

    # Structure
    "general_phase_no_race_specific_language",
    "taper_volume_25_to_35_pct_below_peak",
    "strides_have_3_week_onramp_for_new",    # training_age < 1
    "no_null_rpi_athlete_gets_pace_predictions",
]
```

### `harness.py`

```python
def run_evaluation():
    results = []
    for profile in PROFILES:
        v2_plan = generate_plan_v2(
            athlete_id=profile["id"],
            mode=profile["mode"],
            goal_event=profile.get("goal_event"),
            # ... other params
            preview_only=True,
        )
        gate = run_quality_gate(v2_plan)
        results.append({
            "profile": profile,
            "plan_summary": summarize_plan(v2_plan),
            "gate_passed": gate.passed,
            "gate_failures": gate.failing_checks,
            "gate_warnings": gate.warnings,
        })

    # Optionally run V1 on comparable profiles for side-by-side
    # (V1 only supports race mode, so Build/Maintain profiles skip V1)

    return generate_report(results)
```

### `report.py`

For each profile:
1. Plan summary (phases, weeks, key sessions per week)
2. Sample workout descriptions (1 easy, 1 quality, 1 long run)
3. Quality gate result (pass/fail, failing checks)
4. Progression verification (show pace constancy + duration growth)
5. Fueling coverage (how many workouts have targets)
6. Distance range coverage (how many runs have ranges)
7. Flag for founder review if gate passed

Report written to `apps/api/services/plan_engine_v2/evaluation/
reports/YYYYMMDD_HHMMSS.json` and printed as readable text.

---

## Step 6 — Cutover Path

Do NOT implement until:
- [ ] All 15 profiles generate without errors
- [ ] Quality gate passes on all 15
- [ ] Report generated and reviewed
- [ ] Founder manually reviews their own profile (established_marathon)
  and at least first_marathon, onramp_brand_new, advanced_50k
- [ ] V1 test suite still passes (confirm V1 untouched)

**When ready:**

1. Add `POST /v2/plans/generate` endpoint in a new router file
   (`routers/plan_generation_v2.py`). Do not modify the existing
   `routers/plan_generation.py`.
2. Add `plan_engine_version: str = "v1"` field to `Athlete` model
   (default "v1").
3. Flip to "v2" for founder account first. Run for 7 days.
4. Extend to opted-in beta athletes. Run for 7 more days.
5. After 2 weeks stable: flip global default to "v2".
6. V1 stays in place (unreachable from production but not deleted)
   for 4+ more weeks.
7. Archive V1 after 4 weeks stable V2 production.

---

## What Builder Does NOT Do

- Does not modify `services/plan_framework/` in any way
- Does not modify any existing router or endpoint
- Does not write to `training_plan`, `planned_workout`, or any table
  an athlete's UI reads from
- Does not change `calculate_paces_from_rpi()` or `models.py`
- Does not create a new repo, branch, or deployment target
- Does not expose any V2 endpoint without explicit founder instruction
- Does not import from V1 beyond the three shared imports listed above

---

## Definition of Done (Before Any Cutover Discussion)

- [ ] All 15 synthetic profiles generate complete plans without errors
- [ ] Quality gate passes on all 15
- [ ] Side-by-side report generated
- [ ] Founder manually reviews established_marathon output and approves
- [ ] Founder reviews first_marathon, onramp_brand_new, advanced_50k
- [ ] V1 test suite passes (existing `pytest` green, no changes to V1)
- [ ] No imports from V1 beyond the three shared imports
- [ ] Code passes linting and type checks
- [ ] `plan_preview` migration chains correctly
