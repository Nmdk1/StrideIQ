# Cross-Training Session Detail Capture — Phase A Spec

**Date:** 2026-04-01
**Status:** APPROVED — Founder sign-off Apr 1, 2026. Build-safe for builder handoff.
**Depends on:** Cross-Training Activity Storage Workstream 1 (COMPLETE)

---

## 1. What This Is

A structured detail capture layer for cross-training activities that gives the
correlation engine queryable data beyond "athlete did strength for 47 minutes."

The platform already ingests cross-training activities (6 sports, sport-aware TSS,
76 downstream sport filters). What's missing is the *internal structure* of those
sessions — what exercises, what load, what intensity distribution — without which
the correlation engine has nothing to discover.

**Design principle:** Capture rich, let the engine discover. We do NOT hardcode
assumptions about which cross-training patterns help running. The research informs
what we *capture*; the N=1 engine discovers what *matters* per athlete.

**Scope boundary:** Phase A builds structured tables for **strength only**. Cycling,
walking, hiking, and flexibility do NOT get structured detail tables in this phase.
Their Activity-level fields (duration, HR, TSS, elevation) are sufficient for
current correlation engine needs.

---

## 2. Architecture Decision: Hybrid Storage

**Decision:** JSON capture layer + structured query tables.

| Layer | Purpose | Location |
|-------|---------|----------|
| **Capture** | Lossless raw data preservation | `Activity.session_detail` JSONB (already exists) |
| **Query** | Correlation-ready structured data | `StrengthExerciseSet` table (new) |
| **Classification** | Exercise → movement pattern mapping | Python dictionary in `services/strength_taxonomy.py` (no DB) |

**Why not pure JSON for queries:**
- "All sessions where deadlift sets >= 3 AND weight > bodyweight AND lag to next run <= 72h"
  is possible in PostgreSQL JSON but unmaintainable at scale
- JSON columns cannot be efficiently indexed for the patterns the engine needs
- Type safety and validation at write time prevents garbage data from reaching correlations

**Why not pure structured tables:**
- Exercise taxonomy evolves as the engine finds signals
- JSON preserves everything Garmin sends — if we discover a new field matters in 6 months,
  we re-process from JSON without re-collecting data

**What does NOT need a structured table (Phase A):**
- **Cycling:** Duration + HR + TSS (already captured) answers the engine's questions.
  Zone distribution (if Garmin sends it) stored as structured keys in `session_detail`.
- **Walking/hiking:** Duration + HR + elevation (already on Activity) is sufficient.
- **Flexibility:** Duration + frequency is enough. "Did regular yoga correlate with
  fewer missed training days?" is answerable from Activity-level data.

### 2.1 `session_detail` JSONB Key Convention

The `session_detail` JSONB column on Activity stores multiple payloads over the
activity's lifecycle. To prevent overwrites, all writes use namespaced top-level keys:

```python
SESSION_DETAIL_KEYS = {
    "detail_webhook_raw": "Raw Garmin activity detail webhook payload (set by detail guard)",
    "exercise_sets_raw": "Raw Garmin exerciseSets API response (set by exercise set fetch)",
}
```

Merge contract: all writes use `activity.session_detail = {**(activity.session_detail or {}), key: value}`.
Never overwrite the entire column.

### 2.2 Data Retention

`session_detail` payloads are typically 2-50 KB per activity. At 50 athletes ×
3 strength sessions/week × 50 KB = ~7.5 MB/week. Not a storage concern for years.
No retention policy needed in Phase A. Revisit if athlete count exceeds 500.

---

## 3. Research Foundation

These findings inform what we capture, not what we assume. The engine discovers
per-athlete relationships.

### 3.1 Strength → Running Performance (2024-2025 meta-analyses)

| Finding | Source | Capture Implication |
|---------|--------|---------------------|
| Heavy resistance (≥80% 1RM) improves running economy; submaximal does not | Sports Medicine 2024 | Must capture **weight relative to estimated 1RM**, not just absolute kg |
| Complex training (heavy + plyometric) outperforms either alone | Frontiers in Physiology 2025 | Must capture **movement pattern** to detect interaction effects between session types |
| 10-14 weeks of consistent heavy resistance > 6-8 weeks | Systematic review 2024 | Engine needs **frequency/consistency aggregates** from structured data |
| Hip extension strength correlates with running kinematics | BMC Sports Science 2024 | Must classify **muscle group / movement pattern** — not just exercise name |
| Running economy improvements greater at higher speeds and higher VO2max | Sports Medicine 2024 | Athlete fitness level moderates the effect — engine should discover this naturally |

### 3.2 Timing and Interference (2025 review, 42 studies)

| Finding | Capture Implication |
|---------|---------------------|
| 3+ hour gap between strength and endurance prevents molecular interference | Engine needs **time-gap-to-next-run** at multiple lag windows (24h, 48h, 72h) |
| Strength-first sequence optimizes neuromuscular adaptations | Engine needs **session ordering within day** — derivable from timestamps |
| ATR periodization on non-consecutive days prevents attenuation | Engine needs **strength frequency and spacing** — aggregatable from structured data |

### 3.3 Core Training (2025 systematic review)

| Finding | Capture Implication |
|---------|---------------------|
| Core training improves trunk endurance and sprint speed; evidence for RE is mixed | Let the engine decide per athlete — capture core work as a distinct movement pattern |
| Longer programs (16-24 weeks) with progressive loading more effective | Engine needs **temporal consistency** — how many weeks has this pattern persisted |

### 3.4 Flexibility/Yoga (2025)

| Finding | Capture Implication |
|---------|---------------------|
| Yoga improves neuromuscular control and muscle elasticity | Correlation question: "does yoga frequency correlate with fewer missed days?" |
| Direct running performance correlations weak in population studies | Perfect N=1 candidate — population says weak, individual may say strong |
| No internal session structure needed | Activity-level fields (sport, duration, frequency) are sufficient |

### 3.5 Real-World Calibration (Founder Data)

The bodyweight proxy for "heavy" is useless for trained strength athletes:

| Athlete | Weight | Light Day | Heavy Day | % Bodyweight |
|---------|--------|-----------|-----------|--------------|
| Founder (57y) | 150 lbs | 225×8 (est 1RM: 285) | 295×5 (est 1RM: 344) | 150-197% BW |
| Brian | 180 lbs | — | 405×5 (est 1RM: 486) | 225% BW |

At >80% bodyweight threshold, **every single set** classifies as heavy — zero
signal differentiation between light and heavy days. Estimated 1RM is mandatory
for meaningful intensity classification. See §4.3 for the 1RM tracking approach.

---

## 4. Data Model

### 4.1 `StrengthExerciseSet` Table (NEW)

```
Table: strength_exercise_set
├── id                  UUID PK (default uuid4)
├── activity_id         UUID FK → activity.id (NOT NULL, indexed)
├── athlete_id          UUID FK → athlete.id (NOT NULL, indexed)
├── set_order           Integer NOT NULL (1-indexed position within the session)
├── exercise_name_raw   Text NOT NULL (Garmin's original exercise name, e.g. "BARBELL_DEADLIFT")
├── exercise_category   Text NOT NULL (Garmin's category, e.g. "DEADLIFT")
├── movement_pattern    Text NOT NULL (our classification — see taxonomy below)
├── muscle_group        Text NULLABLE (primary muscle group — see taxonomy)
├── is_unilateral       Boolean DEFAULT false
├── set_type            Text NOT NULL DEFAULT 'active' ('active' or 'rest')
├── reps                Integer NULLABLE (NULL for timed sets like planks)
├── weight_kg           Float NULLABLE (NULL for bodyweight exercises)
├── duration_s          Float NULLABLE (for timed sets/holds, rest periods)
├── estimated_1rm_kg    Float NULLABLE (Epley formula when reps 1-10 and weight present)
├── created_at          DateTime(tz) DEFAULT now()
```

**Indexes:**
- `ix_strength_set_activity` on `(activity_id)`
- `ix_strength_set_athlete_pattern` on `(athlete_id, movement_pattern)`

**Constraints:**
- FK `activity_id` → `activity.id` ON DELETE CASCADE
- FK `athlete_id` → `athlete.id` ON DELETE CASCADE

**Idempotency contract:** For each `activity_id`, the parser write is idempotent.
Implementation: DELETE all `StrengthExerciseSet` rows for the `activity_id`, then
INSERT new rows, in a single transaction. Celery retries and webhook replays produce
identical final state.

### 4.2 Movement Pattern Taxonomy

Python dictionary in `services/strength_taxonomy.py` — not in the database.
Evolves without migrations.

```python
MOVEMENT_PATTERN_MAP = {
    # --- Hip-dominant compound (posterior chain) ---
    "DEADLIFT": ("hip_hinge", "posterior_chain"),
    "BARBELL_DEADLIFT": ("hip_hinge", "posterior_chain"),
    "DUMBBELL_DEADLIFT": ("hip_hinge", "posterior_chain"),
    "TRAP_BAR_DEADLIFT": ("hip_hinge", "posterior_chain"),
    "ROMANIAN_DEADLIFT": ("hip_hinge", "posterior_chain"),
    "SUMO_DEADLIFT": ("hip_hinge", "posterior_chain"),
    "STIFF_LEG_DEADLIFT": ("hip_hinge", "posterior_chain"),
    "SINGLE_LEG_DEADLIFT": ("hip_hinge", "posterior_chain"),  # is_unilateral = True
    "HIP_THRUST": ("hip_hinge", "glutes"),
    "GLUTE_BRIDGE": ("hip_hinge", "glutes"),
    "KETTLEBELL_SWING": ("hip_hinge", "posterior_chain"),
    "GOOD_MORNING": ("hip_hinge", "posterior_chain"),

    # --- Squat pattern (quad-dominant compound) ---
    "SQUAT": ("squat", "quadriceps"),
    "BARBELL_SQUAT": ("squat", "quadriceps"),
    "BACK_SQUAT": ("squat", "quadriceps"),
    "FRONT_SQUAT": ("squat", "quadriceps"),
    "GOBLET_SQUAT": ("squat", "quadriceps"),
    "OVERHEAD_SQUAT": ("squat", "quadriceps"),
    "SPLIT_SQUAT": ("squat", "quadriceps"),       # is_unilateral = True
    "BULGARIAN_SPLIT_SQUAT": ("squat", "quadriceps"), # is_unilateral = True

    # --- Lunge pattern (unilateral lower body) ---
    "LUNGE": ("lunge", "quadriceps"),              # is_unilateral = True
    "WALKING_LUNGE": ("lunge", "quadriceps"),
    "REVERSE_LUNGE": ("lunge", "quadriceps"),
    "LATERAL_LUNGE": ("lunge", "hip_abductors"),
    "STEP_UP": ("lunge", "quadriceps"),

    # --- Push (upper body) ---
    "BENCH_PRESS": ("push", "chest"),
    "INCLINE_BENCH_PRESS": ("push", "chest"),
    "PUSH_UP": ("push", "chest"),
    "OVERHEAD_PRESS": ("push", "shoulders"),
    "MILITARY_PRESS": ("push", "shoulders"),
    "DUMBBELL_PRESS": ("push", "chest"),
    "DIPS": ("push", "triceps"),

    # --- Pull (upper body) ---
    "PULL_UP": ("pull", "lats"),
    "CHIN_UP": ("pull", "biceps"),
    "LAT_PULLDOWN": ("pull", "lats"),
    "BARBELL_ROW": ("pull", "upper_back"),
    "DUMBBELL_ROW": ("pull", "upper_back"),
    "SEATED_ROW": ("pull", "upper_back"),
    "FACE_PULL": ("pull", "rear_delts"),

    # --- Core ---
    "PLANK": ("core", "core_anterior"),
    "SIDE_PLANK": ("core", "core_lateral"),
    "CRUNCH": ("core", "core_anterior"),
    "SIT_UP": ("core", "core_anterior"),
    "RUSSIAN_TWIST": ("core", "core_rotational"),
    "DEAD_BUG": ("core", "core_anterior"),
    "BIRD_DOG": ("core", "core_posterior"),
    "PALLOF_PRESS": ("core", "core_rotational"),
    "AB_WHEEL": ("core", "core_anterior"),
    "HANGING_LEG_RAISE": ("core", "core_anterior"),

    # --- Plyometric (explosive / reactive) ---
    "BOX_JUMP": ("plyometric", "lower_body_explosive"),
    "JUMP_SQUAT": ("plyometric", "lower_body_explosive"),
    "DEPTH_JUMP": ("plyometric", "lower_body_explosive"),
    "BOUNDING": ("plyometric", "lower_body_explosive"),
    "SINGLE_LEG_HOP": ("plyometric", "lower_body_explosive"),

    # --- Carry (loaded locomotion) ---
    "FARMERS_WALK": ("carry", "full_body"),
    "SUITCASE_CARRY": ("carry", "core_lateral"),
    "OVERHEAD_CARRY": ("carry", "shoulders"),

    # --- Calf / lower leg ---
    "CALF_RAISE": ("calf", "calves"),
    "SEATED_CALF_RAISE": ("calf", "calves"),

    # --- Isolation (machine / single-joint) ---
    "LEG_PRESS": ("isolation", "quadriceps"),
    "LEG_EXTENSION": ("isolation", "quadriceps"),
    "LEG_CURL": ("isolation", "hamstrings"),
    "BICEP_CURL": ("isolation", "biceps"),
    "TRICEP_EXTENSION": ("isolation", "triceps"),
    "LATERAL_RAISE": ("isolation", "shoulders"),
}

UNILATERAL_EXERCISES = {
    "SPLIT_SQUAT", "BULGARIAN_SPLIT_SQUAT",
    "LUNGE", "WALKING_LUNGE", "REVERSE_LUNGE", "LATERAL_LUNGE",
    "STEP_UP", "SINGLE_LEG_HOP",
    "SUITCASE_CARRY",
    "DUMBBELL_ROW",
    "SINGLE_LEG_DEADLIFT",
}

DEFAULT_MOVEMENT_PATTERN = ("compound_other", None)
```

**Movement pattern categories** (what the correlation engine groups by):

| Pattern | What It Represents | Running Relevance Hypothesis |
|---------|-------------------|------------------------------|
| `hip_hinge` | Posterior chain compound (deadlifts, hip thrusts) | Strongest theoretical transfer — hip extensors drive running |
| `squat` | Quad-dominant compound | Leg strength, uphill power |
| `lunge` | Unilateral lower body | Running-specific single-leg stability |
| `push` | Upper body pressing | Low direct transfer, but overall robustness |
| `pull` | Upper body pulling | Postural support for long runs |
| `core` | Anterior/lateral/rotational stabilization | Mixed evidence — let engine decide |
| `plyometric` | Explosive/reactive movements | Complex training benefit (combined with heavy) |
| `carry` | Loaded locomotion | Core + grip + postural endurance |
| `calf` | Lower leg isolation | Direct ground contact mechanics |
| `isolation` | Single-joint machine work | Lowest expected transfer, but engine decides |
| `compound_other` | Unmapped exercise (logged for taxonomy expansion) | Fallback — no assumptions |

### 4.3 Estimated 1RM Tracking

Computed at write time on each `StrengthExerciseSet` row using the Epley formula:

```python
def estimate_1rm(weight_kg: float, reps: int) -> Optional[float]:
    """Epley formula — reasonable for 1-10 rep range."""
    if weight_kg is None or weight_kg <= 0:
        return None
    if reps is None or reps < 1:
        return None
    if reps == 1:
        return weight_kg
    if reps > 10:
        return None  # Epley unreliable above 10 reps
    return round(weight_kg * (1 + reps / 30), 1)
```

The aggregation function derives per-exercise **peak estimated 1RM** from the
maximum `estimated_1rm_kg` observed for each `(athlete_id, exercise_category)`
across all historical sets. This enables `ct_heavy_sets` to be computed as
sets at ≥85% of estimated 1RM rather than a bodyweight proxy.

**Fallback when no 1RM history exists:** `ct_heavy_sets` = NULL (not guessed).
The signal becomes available after the athlete has logged enough sessions for
the engine to have a baseline. This is correct behavior — no fake assumptions.

**Fallback when bodyweight is unknown:** `ct_heavy_sets` uses 1RM-relative
threshold only. The bodyweight proxy is not used (see §3.5 for why).

### 4.4 Session Intensity Classification

After parsing all sets for a strength activity, classify the session and store
on the Activity as a derived field (`strength_session_type`):

```python
STRENGTH_SESSION_TYPES = {
    "maximal":            "avg_reps <= 5 AND avg_weight_pct_1rm >= 0.85",
    "strength_endurance": "avg_reps 6-10 AND avg_weight_pct_1rm >= 0.75",
    "hypertrophy":        "avg_reps 6-12 AND avg_weight_pct_1rm < 0.75",
    "endurance":          "avg_reps >= 13",
    "power":              "plyometric_sets > 0 AND (heavy_sets > 0 OR maximal)",
    "mixed":              "none of the above",
}
```

- **`maximal`**: Low reps, high relative intensity. Classic strength.
- **`strength_endurance`**: 6-10 reps at ≥75% 1RM. High load, moderate reps.
  The founder's "light day" (225×8 at 79% 1RM) falls here. Sits at the
  intersection of strength and endurance adaptations — potentially the most
  interesting session type for the correlation engine.
- **`hypertrophy`**: 6-12 reps at <75% 1RM. Muscle building, less neural demand.
- **`endurance`**: High-rep, low-weight. Muscular endurance.
- **`power`**: Complex training — plyometric + heavy in the same session.
  The combination the research predicts outperforms either alone.
- **`mixed`**: Does not fit cleanly into any category.

When no 1RM history exists, classification falls back to rep-count only
(maximal = ≤5 reps, endurance = ≥13, otherwise mixed). The rep-count
classification is still directionally useful.

---

## 5. Ingest Pipeline

### 5.0 Pre-Build Gate: Endpoint Access Verification

**HARD GATE — must pass before Commit 2 starts.**

Before building the exercise set fetch task, verify that the Garmin
`exerciseSets` endpoint is accessible with production credentials:

1. SSH into production server
2. Use Brian's Garmin OAuth token to probe one known strength activity:
   `GET {garmin_base}/activity-service/activity/{activityId}/exerciseSets`
3. If 200 with exercise data → proceed with Commit 2 as specced
4. If 403/404/not available → switch to FIT file download path (fallback)

This gate does NOT block Commit 1. The data model and taxonomy are
endpoint-agnostic.

**Fallback path (if exerciseSets unavailable):**
Download the `.FIT` file via the Activity API, parse using the FIT SDK's
`SetMesg` message type. More complex but proven — same data, different source.

### 5.1 Current State (Already Built)

```
Garmin webhook → adapt_activity_summary() → Activity row (sport="strength")
Garmin detail webhook → session_detail["detail_webhook_raw"] = raw_item (JSONB capture)
```

### 5.2 New: Exercise Set Fetch

When a strength activity is created (in `_ingest_activity_summary_item`), after
the Activity row is committed:

```
Activity created (sport="strength")
    ↓
Enqueue exercise set fetch task (new Celery task)
    ↓
GET {garmin_activity_url}/{garmin_activity_id}/exerciseSets
    ↓
Parse exerciseSets response
    ↓
Idempotent write (DELETE existing + INSERT in one transaction):
    For each exercise set:
    ├── Look up (exercise_category, exercise_name) in MOVEMENT_PATTERN_MAP
    ├── Classify movement_pattern, muscle_group, is_unilateral
    ├── Compute estimated_1rm_kg via Epley formula
    ├── If unknown exercise: log via structured logger, use DEFAULT_MOVEMENT_PATTERN
    └── Write StrengthExerciseSet row
    ↓
Classify session intensity type → Activity.strength_session_type
    ↓
Store raw exerciseSets response in Activity.session_detail["exercise_sets_raw"]
```

### 5.3 Garmin API Call

```python
def fetch_garmin_exercise_sets(garmin_activity_id: int, athlete_id: str) -> Optional[dict]:
    """
    Fetch exercise sets from Garmin Activity API.

    Endpoint: GET /activity-service/activity/{activityId}/exerciseSets
    Auth: OAuth token from athlete's Garmin connection.

    Returns raw JSON response or None on failure.
    """
```

**Error handling:**
- 404 (no exercise data available): log, mark as `exercise_sets_unavailable`, do not retry
- 401 (token expired): refresh token, retry once
- 429 (rate limit): defer with exponential backoff
- 500 (Garmin server error): retry up to 3 times with backoff

### 5.4 Parser

Parser lives in `services/strength_parser.py` (new file, separate from
`garmin_adapter.py` — the adapter translates Garmin field names; the parser
extracts structured exercise data and applies the taxonomy).

```python
def parse_exercise_sets(raw_response: dict, activity_id: str, athlete_id: str) -> List[dict]:
    """
    Parse Garmin exerciseSets response into StrengthExerciseSet-ready dicts.

    Expected Garmin fields (from FIT SDK / community research):
    - exerciseCategory: str (e.g., "DEADLIFT")
    - exerciseName: str (e.g., "BARBELL_DEADLIFT")
    - sets: list of {
        setType: "ACTIVE" | "REST",
        repetitionCount: int,
        weight: float (kg),
        duration: float (seconds),
      }

    NOTE: Exact field names will be validated against Brian's first real
    webhook. If field names differ, update this parser — the
    session_detail JSONB preserves the original payload for re-processing.
    """
```

### 5.5 Unknown Exercise Handling

When a Garmin exercise name is not in `MOVEMENT_PATTERN_MAP`:

1. Classify as `("compound_other", None)`
2. Log at WARNING via structured app logger:
   `"Unknown Garmin exercise: {name} (category: {category}) — classified as compound_other"`
   Fields: `exercise_name`, `exercise_category`, `athlete_id`, `activity_id`
3. Searchable via standard log infrastructure (`docker logs strideiq_api | grep "Unknown Garmin exercise"`)
4. Founder/admin can review unknowns and expand the taxonomy without a migration

### 5.6 Idempotency Contract

For each `activity_id`, the parser write is **idempotent**:

```python
def write_exercise_sets(db, activity_id: str, parsed_sets: List[dict]):
    """
    Idempotent write: delete all existing rows for this activity,
    then insert new rows, in a single transaction.
    """
    db.query(StrengthExerciseSet).filter(
        StrengthExerciseSet.activity_id == activity_id
    ).delete()
    db.add_all([StrengthExerciseSet(**s) for s in parsed_sets])
    db.flush()
```

Celery retries, webhook replays, and backfill re-runs all produce identical
final state. No duplicate rows. No corrupted aggregates.

---

## 6. Correlation Engine Integration

### 6.1 New Aggregate Function

```python
def aggregate_cross_training_inputs(
    athlete_id: str,
    start_date: datetime,
    end_date: datetime,
    db: Session
) -> Dict[str, List[Tuple[date, float]]]:
    """
    Compute cross-training signals for the correlation engine.

    Signals (per day, aligned to correlation engine's date-keyed format):

    Strength signals (from StrengthExerciseSet):
    - ct_strength_sessions: count of strength activities
    - ct_strength_duration_min: total strength duration
    - ct_lower_body_sets: total sets of hip_hinge + squat + lunge + calf
    - ct_upper_body_sets: total sets of push + pull
    - ct_core_sets: total sets of core pattern
    - ct_plyometric_sets: total sets of plyometric pattern
    - ct_heavy_sets: sets at ≥85% estimated 1RM for that exercise
      (NULL when no 1RM history exists — not guessed)
    - ct_total_volume_kg: sum(weight_kg * reps) across all sets
    - ct_unilateral_sets: total sets where is_unilateral = True
    - ct_session_type: categorical — maximal/strength_endurance/hypertrophy/
      endurance/power/mixed (from Activity.strength_session_type)

    Timing signals (from Activity timestamps — multiple lag windows):
    - ct_strength_lag_24h: bool — strength in prior 24 hours
    - ct_strength_lag_48h: bool — strength in prior 48 hours
    - ct_strength_lag_72h: bool — strength in prior 72 hours
    - ct_hours_since_strength: float — continuous lag variable
    - ct_strength_frequency_7d: count of strength sessions in trailing 7 days

    Cycling signals (from Activity where sport='cycling'):
    - ct_cycling_duration_min: total cycling duration
    - ct_cycling_tss: cycling TSS (already computed by TrainingLoadCalculator)

    Flexibility signals (from Activity where sport='flexibility'):
    - ct_flexibility_sessions_7d: flexibility sessions in trailing 7 days
    """
```

### 6.2 `ct_heavy_sets` Computation

```python
def compute_heavy_sets(
    sets: List[StrengthExerciseSet],
    athlete_id: str,
    db: Session
) -> Optional[int]:
    """
    Count sets at ≥85% of estimated 1RM for their exercise.

    1. Query max(estimated_1rm_kg) per exercise_category for this athlete
       from all historical StrengthExerciseSet rows.
    2. For each set in the current session:
       - If exercise has a known 1RM AND set has weight: heavy if weight >= 0.85 * 1RM
       - If no 1RM history for this exercise: skip (not counted as heavy or light)
    3. Return count, or None if no sets had 1RM context.
    """
```

Units: weight_kg throughout. Garmin sends weight in kg natively.
If athlete profile weight is in lbs, convert at read time (÷ 2.20462).

### 6.3 Interaction Effect Discovery

The correlation engine already supports combination correlations
(`discover_combination_correlations()`). Cross-training signals feed
into this existing mechanism. The engine can discover patterns like:

- `ct_lower_body_sets` × `ct_hours_since_strength` → `pace_threshold`
  (heavy lower body work PLUS adequate recovery gap → threshold improvement)
- `ct_core_sets` × `weekly_volume` → `efficiency`
  (core work at higher volumes → efficiency gain — or loss)
- `ct_plyometric_sets` × `ct_heavy_sets` → `pace_threshold`
  (the complex training interaction effect the research predicts)
- `ct_session_type` == "strength_endurance" → `efficiency`
  (the 6-10 rep, ≥75% 1RM zone — most theoretically interesting for runners)
- `ct_strength_lag_48h` → `pace_threshold`
  (does 48h recovery between strength and quality running produce better outcomes?)

These are hypotheses. The engine tests them. We do not pre-bake them.

### 6.4 FRIENDLY_NAMES and DIRECTION_EXPECTATIONS

```python
# Added to n1_insight_generator.py FRIENDLY_NAMES
"ct_strength_sessions": "strength training sessions",
"ct_strength_duration_min": "strength training duration",
"ct_lower_body_sets": "lower body strength sets",
"ct_upper_body_sets": "upper body strength sets",
"ct_core_sets": "core training sets",
"ct_plyometric_sets": "explosive/plyometric sets",
"ct_heavy_sets": "heavy resistance sets",
"ct_total_volume_kg": "total strength volume",
"ct_unilateral_sets": "single-leg exercise sets",
"ct_session_type": "strength session type",
"ct_strength_lag_24h": "strength within 24 hours before run",
"ct_strength_lag_48h": "strength within 48 hours before run",
"ct_strength_lag_72h": "strength within 72 hours before run",
"ct_hours_since_strength": "hours between strength and running",
"ct_strength_frequency_7d": "strength sessions per week",
"ct_cycling_duration_min": "cycling duration",
"ct_cycling_tss": "cycling training stress",
"ct_flexibility_sessions_7d": "flexibility sessions per week",

# DIRECTION_EXPECTATIONS: deliberately EMPTY for cross-training signals.
# We do not assume directionality. The engine discovers.
```

---

## 7. Coach Prompt Extension

When an athlete has cross-training data, extend the coach context:

```python
def _build_cross_training_context(athlete_id: str, db) -> Optional[str]:
    """
    Build cross-training context for coach prompt.

    Example output:
    "## Cross-Training Context (Last 7 Days)
     Strength: 3 sessions (Mon, Wed, Fri)
       - Lower body emphasis (Mon: deadlift 5x5, squat 3x8; Wed: lunges, step-ups)
       - Core: planks, dead bugs (every session)
       - Total volume: 4,250 kg
       - Last strength session: Monday (42 hours ago)
     Cycling: 1 session (Sat) — 45 min, TSS 38
     Yoga: 2 sessions (Tue, Thu) — 30 min each

     ## Relevant Timing
     Next planned quality run: Thursday tempo
     Hours since last lower-body strength: 42
     Your data shows threshold sessions are better with 48+ hours after heavy legs."
    """
```

The coach should be able to answer questions like:
- "Should I do legs today or will it hurt my Thursday tempo run?"
- "Is my strength training helping my running?"
- "How much rest do I need between deadlifts and intervals?"

The coach does NOT prescribe strength programming. It observes what the athlete
does, surfaces what the data shows, and answers questions in context.

**Timing context is critical.** The coach must have enough cross-training timing
data to reason about optimal spacing. When the correlation engine has discovered
a timing pattern (e.g., "your threshold pace is 3% better with ≥48h between
heavy leg work and the session"), that finding flows into the coach context via
the existing fingerprint prompt section. The cross-training context provides
the *current state* ("last heavy leg session was 36 hours ago"); the fingerprint
provides the *discovered pattern* ("48h is your optimal gap"). Together they
enable the coach to say: "Your data shows your threshold sessions are better
with at least 48 hours between heavy leg work and the session. Your last
deadlift session was 36 hours ago — you might want to wait until tomorrow."

That is not prescription. That is the N=1 engine speaking through the coach.

---

## 8. Build Sequence

### Pre-Gate: Endpoint Access Verification (Day 0)

Run a token-authenticated probe against one known Brian strength activity
via the Garmin `exerciseSets` endpoint. Result determines Commit 2 architecture.
Does NOT block Commit 1.

### Commit 1: Data Model + Migration + Taxonomy

- `StrengthExerciseSet` model in `models.py`
- `strength_session_type` column on Activity (nullable Text)
- Alembic migration `cross_training_003`
- Movement pattern taxonomy in `services/strength_taxonomy.py` (new file)
- Epley formula `estimate_1rm()` in `services/strength_taxonomy.py`
- Session intensity classifier in `services/strength_taxonomy.py`
- Unit tests for taxonomy: all known exercises map correctly, unknown falls back
- Unit tests for Epley: boundary cases (1 rep, 10 reps, 0 weight, None)
- Unit tests for session classifier: each type, edge cases, missing 1RM fallback

### Commit 2: Exercise Set Fetch + Parser (gated on endpoint verification)

- New Celery task: `fetch_garmin_exercise_sets_task` in `tasks/garmin_webhook_tasks.py`
- Parser: `parse_exercise_sets()` in `services/strength_parser.py` (new file)
- Idempotent write: `write_exercise_sets()` with DELETE + INSERT
- Wire into strength activity creation in `garmin_webhook_tasks.py`
- Store raw response in `session_detail["exercise_sets_raw"]` (namespaced merge)
- Classify session intensity → `Activity.strength_session_type`
- Tests: parser handles expected fields, handles missing fields gracefully,
  handles empty response, unknown exercises logged, idempotent re-parse

### Commit 3: Correlation Engine Signals

- `aggregate_cross_training_inputs()` in `correlation_engine.py`
- `compute_heavy_sets()` with 1RM-relative threshold
- Wire into `analyze_correlations()` call chain
- FRIENDLY_NAMES for all new signals
- Lag window signals (24h, 48h, 72h boolean + continuous)
- Tests: aggregation produces correct values from fixture data,
  zero cross-training produces empty inputs (no noise),
  1RM-relative heavy sets computed correctly,
  lag windows computed correctly

### Commit 4: Coach Context Extension

- `_build_cross_training_context()` in `ai_coach.py`
- Extend `build_context()` to include cross-training when data exists
- Include timing context (hours since last strength, next planned quality)
- Tests: context is absent when no cross-training data, present when it exists

### Post-Build: Backfill (Admin Task)

- One-time admin script to backfill historical strength sessions from Garmin
- Rate-limited: max 10 activities per minute per athlete
- Resumable with checkpoint (last processed activity timestamp)
- Uses same `fetch_garmin_exercise_sets_task` pipeline
- Order: Brian first, Larry second, founder third
- Scope: last 180 days only
- Triggered manually per athlete

---

## 9. Validation Strategy

### 9.1 Before Brian's First Session

- Taxonomy coverage: all Garmin exercise categories we know about are mapped
- Parser handles graceful degradation: missing reps → null, missing weight → null
- Aggregation functions produce correct output from fixture data
- Idempotent write produces identical state on retry

### 9.2 After Brian's First Session

- Inspect `session_detail` JSONB for the raw webhook payload
- Inspect `exerciseSets` response — validate field names against spec
- If field names differ: update parser, re-process from `session_detail`
- Verify `StrengthExerciseSet` rows were created correctly
- Verify movement patterns classified correctly
- Verify estimated 1RM computed correctly for his deadlift numbers
- Verify session intensity classification

### 9.3 After 4 Weeks of Data (or immediately after backfill)

- Run correlation engine for Brian — do any cross-training signals show up?
- Check FRIENDLY_NAMES render correctly in coach prompt
- Verify lag window signals produce different values at 24h/48h/72h
- First opportunity for the engine to discover real patterns

### 9.4 N=1 Research Opportunity

The founder (57y, 150 lbs, deadlift 1RM ~344 lbs) and Brian (180 lbs,
deadlift 1RM ~486 lbs) are both consistently above the 80% 1RM threshold
the 2024 meta-analysis identifies as the inflection point for running economy
improvement. The correlation engine will tell each athlete whether their strength
sessions are showing up in threshold pace, running economy, injury pattern,
or recovery quality — and whether the volume, peak intensity, or session type
is the more predictive variable.

---

## 10. Resolved Questions (Founder Decisions)

1. **Garmin exerciseSets endpoint access:**
   Day-0 pre-build gate. Verify before Commit 2. If inaccessible, switch to
   FIT file download path. Does not block Commit 1.

2. **Athlete bodyweight for relative intensity:**
   Add bodyweight to onboarding (not optional — numeric input "What's your
   approximate weight?"). Use `BodyComposition` when available, onboarding input
   as fallback. However, `ct_heavy_sets` uses estimated 1RM threshold (≥85% 1RM)
   as primary — the bodyweight proxy is not used because it provides zero signal
   differentiation for trained athletes (see §3.5). When no 1RM history exists,
   `ct_heavy_sets` = NULL (not guessed).

3. **Backfill Brian's historical strength:**
   Yes. Last 180 days. Rate-limited (10/min/athlete). Resumable checkpoints.
   Brian first, Larry second, founder third. Same pipeline as live ingest.
   One-time admin task, not recurring.

---

## Appendix: Research References

1. Sports Medicine (2024): "The Effect of Strength Training Methods on Middle-Distance and Long-Distance Runners' Athletic Performance: A Systematic Review with Meta-analysis"
2. Sports Medicine (2024): "Effect of Strength Training Programs in Middle- and Long-Distance Runners' Economy at Different Running Speeds"
3. Frontiers in Sports and Active Living (2025): "The effects, mechanisms, and influencing factors of concurrent strength and endurance training with different sequences"
4. Frontiers in Physiology (2025): "Effect of complex training on lower limb strength and running economy in adolescent distance runners"
5. BMC Sports Science (2024): "Unveiling the influence of hip isokinetic strength on lower extremity running kinematics"
6. Frontiers in Sports and Active Living (2025): "Exploring the role of the core in sports performance"
7. International Journal of Yoga (2025): "Biomechanical Assessment of Yoga-Based Warm-Up Routines in Reducing Injury Risk among Runners"
