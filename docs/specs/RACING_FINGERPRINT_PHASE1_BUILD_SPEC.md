# Racing Fingerprint — Phase 1 Builder Spec

**Date:** March 4, 2026
**Status:** Ready to build
**Depends on:** `RACING_FINGERPRINT_AND_PROGRESS_STATE_MACHINE_SPEC.md`

---

## Before You Build

Read these three documents in order before writing any code:

1. **`docs/FOUNDER_OPERATING_CONTRACT.md`** — How you work with this
   founder. Non-negotiable.
2. **`docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md`** — How every screen
   should feel. What's been agreed. What's been rejected.
3. **`docs/specs/RACING_FINGERPRINT_AND_PROGRESS_STATE_MACHINE_SPEC.md`**
   — The product design. The WHAT. This document is the HOW.

---

## Document Structure

This is one document with three sections and hard gates between them.
You cannot begin a section until the previous section's gate passes.

```
Pre-Work (P1–P4)  ──[GATE A]──→  Phase 1A  ──[GATE B]──→  Phase 1B  ──[GATE C]──→  STOP
```

P1–P4 are independent of each other. Work them in any order or in
parallel. All four must pass before Gate A opens.

**After Gate C:** No more code is written. Phase 1B produces findings.
The founder reviews them. If the findings are true and non-trivial,
Phase 2 (surfaces, visuals, state machine rendering) begins under a
separate spec. If the findings are wrong or trivial, the data or the
analysis needs fixing — loop back within Phase 1.

---

## Pre-Work: Data Quality Prerequisites

These four tasks fix systemic data quality issues discovered during
production inspection of the founder's account (742 activities, 540
Strava + 202 Garmin). Every downstream computation depends on clean
data. Do not skip these.

---

### P1: Retroactive Duplicate Detection and Resolution

**Problem:** Cross-provider deduplication exists at ingestion time
(Strava sync skips if Garmin match exists within ±1h / 5% distance).
But existing duplicates in the database are not cleaned up. Downstream
computations (training load, weekly volume, block signatures) have no
dedup awareness and double-count volume.

**Existing code:**
- `services/activity_deduplication.py` — `match_activities()` uses
  TIME_WINDOW_S=3600, DISTANCE_TOLERANCE=0.05, HR_TOLERANCE_BPM=5
- `tasks/strava_tasks.py` — cross-provider dedup at Strava ingestion
  (search for "Cross-provider dedup" in file)
- `tasks/garmin_webhook_tasks.py` — Garmin webhook dedup via
  `match_activities()` (search for "Time-window dedup" in file)
- `routers/calendar.py` — display-only dedup
  (`_activities_are_probable_duplicates`)
- Activity model has no `is_duplicate` field

**What to build:**

1. **Add `is_duplicate` column to Activity model.**

   ```python
   # In models.py, Activity class
   is_duplicate = Column(Boolean, default=False, nullable=False,
                         server_default="false", index=True)
   duplicate_of_id = Column(UUID(as_uuid=True), ForeignKey("activity.id"),
                            nullable=True)
   ```

   Create Alembic migration in `apps/api/alembic/versions/`. Naming
   convention: `fingerprint_p1_add_duplicate_fields.py`.

2. **Build retroactive duplicate scanner.**

   New file: `services/duplicate_scanner.py`

   ```python
   def scan_and_mark_duplicates(athlete_id: UUID, db: Session) -> dict:
       """
       Scan all activities for an athlete. Identify cross-provider
       duplicates by time window (±1 hour) + distance match (±5%).

       TRIGGER: Admin endpoint (POST /admin/scan-duplicates/{athlete_id}).
       Run manually for the founder's account during pre-work. Future:
       run automatically after initial sync completes for new athletes.

       For each duplicate pair:
       - Keep the record with richer data (prefer Garmin HR when
         Strava HR is null; prefer Strava names when Garmin names
         are generic like "Running" or null)
       - Merge best fields into primary
       - Mark secondary as is_duplicate=True, duplicate_of_id=primary.id

       Returns: {"pairs_found": int, "marked_duplicate": int}
       """
   ```

   Use the existing `match_activities()` from
   `activity_deduplication.py` for matching logic. Add field-merge
   logic that doesn't exist yet.

   **Field merge rules:** For each nullable column on the primary
   record, fill from the secondary if the primary is null. If both
   are non-null, apply these precedence rules:
   - **Physiological data** (avg_hr, max_hr, avg_cadence, max_cadence,
     avg_stride_length_m, avg_ground_contact_ms, avg_vertical_oscillation_cm,
     avg_power_w, garmin_aerobic_te, garmin_perceived_effort): prefer
     Garmin (richer sensor data).
   - **Metadata** (name, is_race_candidate, workout_type): prefer
     Strava (athlete-curated names, race tags).
   - **GPS / distance / duration** (distance_m, duration_s,
     total_elevation_gain, start_lat, start_lng, moving_time_s):
     prefer the record with the longer `moving_time_s` (more complete
     GPS trace).
   - **Performance scores** (performance_percentage, race_confidence,
     intensity_score): prefer the record with the higher value (more
     signal).

3. **Add dedup filter to training load queries.**

   In `services/training_load.py`, every query that fetches activities
   must add `.filter(Activity.is_duplicate == False)`. Two locations:

   - `calculate_training_load()` — the activity query inside this method
   - `get_load_history()` — the activity query inside this method

4. **Add dedup filter to all downstream aggregate queries.**

   Search for `Activity.athlete_id ==` across services. Any query that
   aggregates (sum, count, average) must exclude duplicates. Key files:
   - `services/training_load.py`
   - `services/coach_context.py` (if it queries activities)
   - `services/home_signals.py` (if it queries activities)
   - `services/athlete_metrics.py`
   - Any weekly/monthly volume computation

**Tests to write:** `tests/test_duplicate_scanner.py`

```python
class TestDuplicateScanner:
    def test_identifies_cross_provider_duplicate(self, db_session, test_athlete):
        """Two activities from different providers, same time ±30min,
        same distance ±3% → marked as duplicates."""

    def test_keeps_richer_record_as_primary(self, db_session, test_athlete):
        """Garmin has HR, Strava has name → primary gets both."""

    def test_does_not_flag_different_activities(self, db_session, test_athlete):
        """Two activities 3 hours apart → not duplicates."""

    def test_does_not_flag_same_provider(self, db_session, test_athlete):
        """Two Strava activities (different external_activity_id) at
        similar times → not duplicates (handled by unique constraint)."""

    def test_training_load_excludes_duplicates(self, db_session, test_athlete):
        """Create duplicate pair, compute training load, verify TSS
        is counted once not twice."""
```

**P1 Verification (run in production after deploy):**

```sql
-- Count duplicate pairs found
SELECT COUNT(*) FROM activity WHERE is_duplicate = true;

-- Verify no orphaned duplicate_of references
SELECT COUNT(*) FROM activity a
WHERE a.is_duplicate = true
AND NOT EXISTS (
    SELECT 1 FROM activity b WHERE b.id = a.duplicate_of_id
);
-- Expected: 0

-- Verify training load difference for founder
-- (run before and after P1 deploy, compare CTL values)
```

```bash
# Run on production container after deploy
docker exec strideiq_api python -c "
from database import SessionLocal
from models import Activity, Athlete
db = SessionLocal()
athlete = db.query(Athlete).filter(Athlete.email=='mbshaf@gmail.com').first()
total = db.query(Activity).filter(Activity.athlete_id==athlete.id).count()
dupes = db.query(Activity).filter(Activity.athlete_id==athlete.id, Activity.is_duplicate==True).count()
print(f'Total: {total}, Duplicates marked: {dupes}, Clean: {total - dupes}')
db.close()
"
```

---

### P2: Classify Unclassified Activities

**Problem:** 48% of activities (357 of 742 for founder) have
`workout_type = None`. Block signatures require effort classification
for intensity distribution.

**Existing code:**
- `routers/compare.py` — `POST /classify-all` endpoint already exists.
  It queries unclassified activities (distance ≥ 1000m), runs
  `WorkoutClassifierService.classify_activity()` on each, and commits.
- `services/effort_classification.py` — `classify_effort_bulk()`
  exists, returns `Dict[UUID, str]` mapping activity IDs to effort
  labels (hard/moderate/easy).

**What to build:**

This is primarily operational. The `/classify-all` endpoint already
works. But it runs per-athlete (authenticated), not as an admin batch.

1. **Add admin batch classification endpoint.**

   In `routers/admin.py`:

   ```python
   @router.post("/admin/classify-all-athletes")
   async def admin_classify_all(
       current_user: Athlete = Depends(require_admin),
       db: Session = Depends(get_db),
   ):
       """Classify all unclassified activities across all athletes."""
   ```

   Or run the existing `/classify-all` endpoint for the founder's
   account. Either approach works. The admin endpoint is better for
   production use.

2. **Verify `classify_effort_bulk()` handles edge cases.**

   The `classify_effort_bulk()` function computes thresholds once
   and applies to all activities. Verify it handles:
   - Activities with no HR data and no pace data (should return a
     reasonable default or skip, not crash)
   - Activities with no TPP profile (should fall back to HR-based
     classification)

**Tests to write:** `tests/test_effort_classification_bulk.py`

```python
class TestClassifyEffortBulk:
    def test_classifies_activity_with_hr_only(self, db_session, test_athlete):
        """Activity with HR but no pace → classifies via HR tier."""

    def test_classifies_activity_with_no_data(self, db_session, test_athlete):
        """Activity with no HR and no pace → returns default or skips."""

    def test_bulk_matches_individual(self, db_session, test_athlete):
        """Bulk classification produces same result as individual."""
```

**P2 Verification (run in production after deploy):**

```bash
docker exec strideiq_api python -c "
from database import SessionLocal
from models import Activity, Athlete
db = SessionLocal()
athlete = db.query(Athlete).filter(Athlete.email=='mbshaf@gmail.com').first()
total = db.query(Activity).filter(Activity.athlete_id==athlete.id, Activity.is_duplicate==False).count()
classified = db.query(Activity).filter(Activity.athlete_id==athlete.id, Activity.is_duplicate==False, Activity.workout_type.isnot(None)).count()
print(f'Total (non-dup): {total}, Classified: {classified}, Pct: {classified/total*100:.1f}%')
db.close()
"
```

**Expected:** Classification percentage > 90%. Activities with
insufficient data for classification are acceptable gaps.

---

### P3: Fix Training Load Lookback

**Problem:** `calculate_training_load()` in `services/training_load.py`
has a hardcoded `lookback_days = 60`. CTL uses a 42-day EMA decay
constant. With only 60 days of history, the EMA starts from 0.0 and
never converges to the true value. Historical race dates months or
years in the past will produce wildly inaccurate CTL.

**Existing code:**
- `services/training_load.py` — `calculate_training_load()` method,
  hardcoded `lookback_days = 60`
- EMA constants: `ATL_DECAY_DAYS = 7`, `CTL_DECAY_DAYS = 42`
- EMA alpha: `atl_decay = 2 / (ATL_DECAY_DAYS + 1)`,
  `ctl_decay = 2 / (CTL_DECAY_DAYS + 1)`
- `calculate_workout_tss()` computes TSS per activity (hrTSS, rTSS,
  or estimated fallback)
- Redis cache key includes `target_date`

**What to build:**

Build a single-pass EMA function that walks from the athlete's first
activity to their last and returns CTL/ATL/TSB at any requested date.
This is more accurate than a windowed approach and more efficient when
computing training state for multiple race dates (which Phase 1A
requires).

1. **New function in `services/training_load.py`:**

   ```python
   def compute_training_state_history(
       self,
       athlete_id: UUID,
       target_dates: Optional[List[date]] = None,
   ) -> Dict[date, LoadSummary]:
       """
       Single-pass EMA from athlete's first activity to last.

       Walks all activities chronologically. Computes daily TSS.
       Applies ATL/CTL EMA on every day (including rest days).
       Returns LoadSummary at each requested target_date.

       If target_dates is None, returns values at every day
       (useful for charting full history).

       Excludes duplicate activities (is_duplicate == True).
       """
   ```

   Implementation:
   - Query ALL activities for athlete, ordered by start_time,
     filtered by `is_duplicate == False`
   - Find first and last activity dates
   - Build `daily_tss: Dict[date, float]` from activities
   - Walk day by day from first to last, applying EMA
   - Collect `LoadSummary` at each requested target_date
   - Cache the full history in Redis with athlete-scoped key
   - **Cache invalidation:** Invalidate the athlete's training state
     cache on any activity create, update, delete, or duplicate
     marking. Cache key pattern: `training_state_history:{athlete_id}`.
     Callers that modify activities must call
     `invalidate_training_state_cache(athlete_id)`.

2. **Update `calculate_training_load()` to use the new function.**

   For backward compatibility, keep the existing function but change
   it to call `compute_training_state_history()` with
   `target_dates=[target_date]` and return the single result. This
   automatically fixes the 60-day lookback problem for all callers.

3. **Update `get_load_history()` to use the new function.**

   Replace the internal loop with a call to
   `compute_training_state_history(target_dates=None)` filtered to
   the requested date range.

**Tests to write:** `tests/test_training_load_single_pass.py`

```python
class TestSinglePassEMA:
    def test_converges_with_full_history(self, db_session, test_athlete):
        """Create 180 days of activities. Compute CTL at day 180.
        Compare to 60-day window computation. Full history CTL
        should be higher (more accumulated fitness)."""

    def test_matches_manual_ema(self, db_session, test_athlete):
        """Create known TSS sequence. Compute CTL manually using
        the EMA formula. Verify single-pass function matches."""

    def test_returns_values_at_multiple_dates(self, db_session, test_athlete):
        """Request CTL/ATL/TSB at 5 different dates in one call.
        Verify all 5 are returned and internally consistent."""

    def test_excludes_duplicate_activities(self, db_session, test_athlete):
        """Create duplicate pair. Verify TSS is counted once."""

    def test_rest_days_decay_correctly(self, db_session, test_athlete):
        """Create activity, then 14 rest days, then activity.
        Verify CTL/ATL decay during rest period follows EMA formula."""

    def test_backward_compatible(self, db_session, test_athlete):
        """calculate_training_load() still works and returns
        LoadSummary with same interface."""
```

**P3 Verification (run in production after deploy):**

```bash
docker exec strideiq_api python -c "
from database import SessionLocal
from models import Athlete
from services.training_load import TrainingLoadService
from datetime import date
db = SessionLocal()
athlete = db.query(Athlete).filter(Athlete.email=='mbshaf@gmail.com').first()
svc = TrainingLoadService(db)

# Compare old vs new for a date 6 months ago
from datetime import timedelta
old_date = date.today() - timedelta(days=180)
result = svc.compute_training_state_history(athlete.id, target_dates=[old_date, date.today()])
for d, load in sorted(result.items()):
    print(f'{d}: CTL={load.ctl:.1f}  ATL={load.atl:.1f}  TSB={load.tsb:.1f}')
db.close()
"
```

**Expected:** CTL 6 months ago should reflect actual accumulated
fitness, not near-zero from cold-start. Current-day CTL should be
similar to the old function (both have enough recent data).

---

### P4: Expand Race Detection to 8 Standard Distances

**Problem:** `detect_race_candidate()` in
`services/performance_engine.py` checks only 4 distances: 5K, 10K,
half marathon, marathon. It also has a hard HR gate — if HR data is
missing, it returns `(False, 0.0)` regardless of all other signals.
This caused the founder's account to detect 4 of 15+ actual races.

**Existing code:**
- `services/performance_engine.py` — `detect_race_candidate()`
  function with 4-distance dict and HR gate
- `services/personal_best.py` — `DISTANCE_CATEGORIES` dict with GPS
  tolerance ranges for 13 distances including all 8 we need:
  - mile: (1570, 1660)
  - 5k: (4957, 5311)
  - 10k: (9914, 10622)
  - 15k: (14850, 15150)
  - 25k: (24750, 25250)
  - half_marathon: (21000, 21300)
  - marathon: (42000, 42400)
  - 50k: (49500, 50500)

**What to build:**

1. **Expand the distance dict in `detect_race_candidate()`.**

   Replace the 4-distance dict with the 8 standard distances. Use the
   tolerance ranges from `DISTANCE_CATEGORIES` in `personal_best.py`
   instead of the current 3% tolerance:

   ```python
   RACE_DISTANCES = {
       'mile': (1570, 1660),
       '5k': (4957, 5311),
       '10k': (9914, 10622),
       '15k': (14850, 15150),
       '25k': (24750, 25250),
       'half_marathon': (21000, 21300),
       'marathon': (42000, 42400),
       '50k': (49500, 50500),
   }
   ```

2. **Remove the hard HR gate. Make HR a weighted signal.**

   Current code returns `(False, 0.0)` when HR is missing. Change to:
   - HR present → use it as 40% weight signal (existing logic)
   - HR absent → HR signal scores 0, but other signals can still push
     confidence above threshold. An activity at exactly 10K distance
     with a name containing "Race" and consistent splits should still
     be detectable.

   Adjust the threshold accordingly. Without HR, max possible
   confidence = 0.6 (distance 0.2 + pace 0.3 + effort 0.1). Set a
   separate no-HR threshold at 0.50 (requires distance match + good
   pace consistency to qualify as candidate without HR).

3. **Add name-based race detection as a new signal (15% weight).**

   New signal, carved from reduced weights on existing signals:

   ```python
   # Rebalanced weights (starting point — calibrate after P4
   # verification against the founder's known race list; adjust
   # if false positive rate exceeds 20%):
   # HR: 35% (was 40%)
   # Pace consistency: 25% (was 30%)
   # Distance match: 15% (was 20%)
   # Name signal: 15% (NEW)
   # Effort profile: 10% (unchanged)

   RACE_NAME_PATTERNS = [
       r'\brace\b', r'\bclassic\b', r'\bcharity\b',
       r'\bmarathon\b', r'\bhalf\b', r'\b5k\b', r'\b10k\b',
       r'\b\d+k\b', r'\bchip\s*time\b',
       r'\b(?:1st|2nd|3rd|\d+th)\b',
       r'\boverall\b', r'\bgrandmaster\b', r'\bags?\s*group\b',
       r'\bfinish(?:er)?\b', r'\bbib\b', r'\bcourse\b',
   ]

   def _name_race_score(activity_name: Optional[str]) -> float:
       if not activity_name:
           return 0.0
       name_lower = activity_name.lower()
       matches = sum(1 for p in RACE_NAME_PATTERNS
                     if re.search(p, name_lower))
       if matches >= 3:
           return 1.0
       elif matches >= 2:
           return 0.8
       elif matches >= 1:
           return 0.5
       return 0.0
   ```

4. **Accept `activity_name` as a new parameter.**

   Update the function signature:

   ```python
   def detect_race_candidate(
       activity_pace: Optional[float],
       max_hr: Optional[int],
       avg_hr: Optional[int],
       splits: List[dict],
       distance_meters: float,
       duration_seconds: Optional[int],
       activity_name: Optional[str] = None,  # NEW
   ) -> Tuple[bool, float]:
   ```

   Update all callers (primarily `tasks/strava_tasks.py`
   `_calculate_performance_metrics`) to pass `activity.name`.

5. **Preserve Strava race tag separately.**

   Add a new field to Activity:

   ```python
   strava_workout_type_raw = Column(Integer, nullable=True)
   ```

   In `tasks/strava_tasks.py`, when creating an activity from Strava,
   store the raw `workout_type` integer:

   ```python
   strava_workout_type_raw=a.get("workout_type"),
   ```

   This preserves the original signal even after the classifier
   overwrites `activity.workout_type`. Migration:
   `fingerprint_p4_add_strava_raw_workout_type.py`.

   Also backfill: for existing activities where
   `is_race_candidate == True` and `provider == 'strava'`, set
   `strava_workout_type_raw = 3` (we know these came from race-tagged
   Strava activities).

**Tests to write:** `tests/test_race_detection_expanded.py`

```python
class TestExpandedRaceDetection:
    def test_detects_mile_race(self):
        """Activity at 1609m with race-like HR → detected."""

    def test_detects_15k_race(self):
        """Activity at 15000m → detected."""

    def test_detects_25k_race(self):
        """Activity at 25100m → detected."""

    def test_detects_50k_race(self):
        """Activity at 50200m → detected."""

    def test_detects_race_without_hr(self):
        """Activity at 10K distance, name='Gulf Coast Classic',
        consistent splits, no HR → detected as candidate."""

    def test_name_boosts_confidence(self):
        """Activity with 'Charity 5K - 1st Overall' name →
        name signal = 1.0."""

    def test_name_alone_insufficient(self):
        """Activity named 'Race prep' at non-standard distance →
        not detected (no distance match)."""

    def test_backward_compatible_without_name(self):
        """Existing callers that don't pass activity_name still work."""

    def test_strava_race_tag_preserved(self):
        """Strava activity with workout_type=3 stores
        strava_workout_type_raw=3 on Activity."""
```

**P4 Verification (run in production after deploy):**

```bash
docker exec strideiq_api python -c "
from database import SessionLocal
from models import Activity, Athlete
from services.performance_engine import detect_race_candidate
db = SessionLocal()
athlete = db.query(Athlete).filter(Athlete.email=='mbshaf@gmail.com').first()

RACE_DISTANCES = {
    'mile': (1570, 1660), '5k': (4957, 5311), '10k': (9914, 10622),
    '15k': (14850, 15150), '25k': (24750, 25250),
    'half_marathon': (21000, 21300), 'marathon': (42000, 42400),
    '50k': (49500, 50500),
}

for name, (lo, hi) in sorted(RACE_DISTANCES.items(), key=lambda x: x[1][0]):
    activities = db.query(Activity).filter(
        Activity.athlete_id == athlete.id,
        Activity.distance_m >= lo,
        Activity.distance_m <= hi,
        Activity.is_duplicate == False,
    ).all()
    for a in activities:
        is_race, conf = detect_race_candidate(
            activity_pace=None,
            max_hr=a.max_hr,
            avg_hr=a.avg_hr,
            splits=[],
            distance_meters=float(a.distance_m) if a.distance_m else 0,
            duration_seconds=a.duration_s,
            activity_name=a.name,
        )
        if is_race or conf > 0.3:
            pace = ''
            if a.distance_m and a.duration_s and a.distance_m > 0:
                ps = a.duration_s / (a.distance_m / 1000)
                pace = f'{int(ps//60)}:{int(ps%60):02d}/km'
            print(f'{name:15s} {a.start_time.strftime(\"%Y-%m-%d\")} {a.name or \"(no name)\":40s} conf={conf:.2f} race={is_race} {pace}')
db.close()
"
```

**Expected:** Significantly more races detected than the original 4.
Cross-reference against the founder's known race list (see product
spec, Data Quality Investigation section).

---

### ═══════════════════════════════════════════════════════
### GATE A: Pre-Work Complete
### ═══════════════════════════════════════════════════════

**All four conditions must be true before ANY Phase 1A work begins.**

**A1.** P1 verification passes — duplicates marked, training load
excludes them, zero orphaned `duplicate_of` references.

**A2.** P2 verification passes — > 90% of non-duplicate activities
have `workout_type` assigned.

**A3.** P3 tests pass — `compute_training_state_history()` returns
accurate CTL for dates 6+ months in the past. Manual EMA verification
test passes.

**A4.** P4 verification passes — expanded race detection finds
significantly more candidate races in founder's data than the
original 4.

**Evidence required:** Paste the output of each verification command
and the test suite results. Do not proceed on assertion alone.

---

## Phase 1A: PerformanceEvent Table + Race Curation Experience

---

### 1A.1: PerformanceEvent Model and Migration

**New file:** Add to `models.py`

```python
class PerformanceEvent(Base):
    __tablename__ = "performance_event"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"),
                        nullable=False, index=True)
    activity_id = Column(UUID(as_uuid=True), ForeignKey("activity.id"),
                         nullable=False, index=True)

    distance_category = Column(Text, nullable=False)
    event_date = Column(Date, nullable=False, index=True)
    event_type = Column(Text, nullable=False)
    # event_type values: 'race', 'race_pb', 'training_pb'

    # Performance
    time_seconds = Column(Integer, nullable=False)
    pace_per_mile = Column(Float, nullable=True)
    rpi_at_event = Column(Float, nullable=True)
    performance_percentage = Column(Float, nullable=True)
    is_personal_best = Column(Boolean, default=False)

    # Training state at event
    ctl_at_event = Column(Float, nullable=True)
    atl_at_event = Column(Float, nullable=True)
    tsb_at_event = Column(Float, nullable=True)
    fitness_relative_performance = Column(Float, nullable=True)

    # Block signature (the fingerprint)
    block_signature = Column(JSONB, nullable=True)

    # Wellness state
    pre_event_wellness = Column(JSONB, nullable=True)

    # Classification
    race_role = Column(Text, nullable=True)
    # race_role values: 'a_race', 'tune_up', 'training_race', 'unknown'
    user_classified_role = Column(Text, nullable=True)
    cycle_id = Column(UUID(as_uuid=True), nullable=True)

    # Source / verification
    detection_source = Column(Text, nullable=False, default='algorithm')
    # detection_source values: 'algorithm', 'strava_tag', 'user_verified',
    #                          'user_added'
    detection_confidence = Column(Float, nullable=True)
    user_confirmed = Column(Boolean, nullable=True)
    # True = confirmed race, False = rejected, None = not yet reviewed

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(),
                        onupdate=func.now())
    computation_version = Column(Integer, nullable=False, default=1)

    __table_args__ = (
        UniqueConstraint('athlete_id', 'activity_id',
                         name='uq_performance_event_athlete_activity'),
        Index('ix_performance_event_athlete_date',
              'athlete_id', 'event_date'),
    )
```

**Migration:** `fingerprint_1a_create_performance_event.py`

---

### 1A.2: Algorithmic Population Pipeline

**New file:** `services/performance_event_pipeline.py`

```python
def populate_performance_events(
    athlete_id: UUID,
    db: Session,
) -> dict:
    """
    Scan all non-duplicate activities at standard distances.
    Apply expanded race detection. Create PerformanceEvents for:

    TRIGGER: This function runs in three contexts:
    1. Admin endpoint (POST /admin/populate-performance-events/{athlete_id})
       — manual trigger for initial backfill and testing.
    2. Post-sync task — after Strava/Garmin sync completes for an
       athlete, queue as a Celery task to detect new races in the
       synced batch. Only scans newly synced activities, not the
       full history.
    3. On-demand via race curation API — when the athlete opens the
       discovery experience and no PerformanceEvents exist yet.

    For the founder's initial build, trigger via admin endpoint.
    Post-sync automation is a follow-up after 1A is validated.

    1. Activities where user_verified_race == True
    2. Activities where strava_workout_type_raw == 3
    3. Activities where detect_race_candidate() returns
       is_race=True or confidence >= 0.5
    4. PersonalBest records at standard distances linked to
       race-flagged activities

    For each PerformanceEvent created, compute:
    - Training state (via compute_training_state_history)
    - Block signature (via compute_block_signature)
    - RPI (via calculate_rpi_from_race_time)
    - Performance percentage (via calculate_age_graded_performance)
    - Fitness-relative performance (RPI vs predicted from CTL)

    Returns: {"events_created": int, "events_updated": int}
    """


def compute_block_signature(
    activity_id: UUID,
    event_date: date,
    distance_category: str,
    athlete_id: UUID,
    db: Session,
) -> dict:
    """
    Compute the block signature for a PerformanceEvent.

    Lookback window scales with distance:
    - mile, 5k: 8 weeks
    - 10k, 15k: 12 weeks
    - half_marathon: 14 weeks
    - marathon: 18 weeks
    - 50k: 20 weeks

    For each week in the lookback window:
    1. Group non-duplicate activities by week (relative to event)
    2. Compute: total volume, intensity distribution
       (easy/moderate/hard from classify_effort_bulk),
       long run distance, number of quality sessions
    3. Build volume_trajectory (weekly volumes)
    4. Detect taper (where volume starts declining)
    5. Find peak volume week and peak intensity week

    Returns JSONB-ready dict.
    """


LOOKBACK_WEEKS = {
    'mile': 8, '5k': 8,
    '10k': 12, '15k': 12,
    'half_marathon': 14,
    'marathon': 18,
    '50k': 20,
}


def classify_race_role(
    event: "PerformanceEvent",
    all_events: List["PerformanceEvent"],
) -> str:
    """
    Infer race_role from proximity and distance hierarchy.

    - Two races within 8 weeks, second is equal/longer distance →
      first is 'tune_up'
    - Only race in its distance category within 12 weeks →
      'a_race'
    - Default: 'unknown'
    """
```

---

### 1A.3: Race Curation API

**New file:** `routers/fingerprint.py`

Router prefix: `/v1/fingerprint`, tags: `["Fingerprint"]`

Register in `main.py` with other routers.

**Endpoints:**

```python
@router.get("/race-candidates")
async def get_race_candidates(
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RaceCandidateResponse:
    """
    Returns three tiers for the discovery experience:

    Tier 1 - "Races we found": PerformanceEvents where
      user_confirmed is True OR detection_confidence >= 0.7
      OR detection_source in ('strava_tag', 'user_verified').

    Tier 2 - "Were these races?": PerformanceEvents where
      user_confirmed is None AND detection_confidence between
      0.3 and 0.7.

    Tier 3 - "Browse history": Activities at standard distances
      that don't have a PerformanceEvent yet (for adding missed
      races). Return as cards with: name, date, distance, pace,
      duration, day of week, start_lat/start_lng (for location).
      Paginated: limit (default 50) and offset (default 0) query
      params. Filterable by date range and distance category.
      Athletes can have hundreds of activities at standard
      distances — don't return them all.

    **Critical: many activities have no name.** The founder's
    entire 2024 history (first year back running) has name=NULL
    on every Strava activity. The Nov 30, 2024 Stennis Space
    Center Half Marathon (1st Masters, 4:26/km, HR=156) is a
    nameless 21184m activity — indistinguishable from a training
    long run without the athlete's help. For nameless activities,
    the card must show enough context to trigger recognition
    without a name: pace (a 4:26/km half is obviously a race
    effort vs a 5:34/km training long run), day of week (Saturday
    morning = more likely a race), HR intensity, and date. Sort
    browse results by pace (fastest first within each distance)
    to surface race efforts at the top.

    Each item includes enough context for the athlete to
    recognize the day: name (if available), date, time of day,
    day of week, pace, distance, HR if available, location if
    available.
    """


@router.post("/confirm-race/{event_id}")
async def confirm_race(
    event_id: UUID,
    confirmed: bool,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Athlete confirms (True) or rejects (False) a candidate race.

    On confirm:
    - Set user_confirmed = True
    - Set detection_source = 'user_verified'
    - If training state / block signature not yet computed,
      compute them now
    - Return updated Racing Life Strip data

    On reject:
    - Set user_confirmed = False
    - Remove from strip data
    """


@router.post("/add-race/{activity_id}")
async def add_race(
    activity_id: UUID,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Athlete identifies an activity as a race the system missed.

    - Create PerformanceEvent from the activity
    - Set detection_source = 'user_added'
    - Set user_confirmed = True
    - Compute training state and block signature
    - Return updated Racing Life Strip data
    """


@router.get("/strip")
async def get_racing_life_strip(
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RacingLifeStripResponse:
    """
    Returns data for the Racing Life Strip visual:

    - Weekly training volume (all non-duplicate activities,
      grouped by week, from first activity to last)
    - Weekly intensity (proportion of easy/moderate/hard per week)
    - Confirmed PerformanceEvents as pins (date, distance_category,
      time_seconds, is_personal_best, performance_percentage)

    The frontend renders this as the horizontal visual described
    in the product spec.
    """


@router.get("/findings")
async def get_fingerprint_findings(
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FingerprintFindingsResponse:
    """
    Returns pattern extraction findings for the athlete.
    Only returns findings that pass the automated quality gate
    (see Phase 1B).

    Initially empty until Phase 1B populates findings.
    """
```

**Response models (Pydantic):**

Define in a new file `schemas/fingerprint.py`:

```python
class RaceCard(BaseModel):
    """One race candidate, presented as a card the athlete recognizes."""
    event_id: Optional[UUID] = None
    activity_id: UUID
    name: Optional[str]
    date: date
    time_of_day: Optional[str]  # e.g., "8:30 AM"
    distance_category: str
    distance_meters: int
    pace_display: str  # e.g., "4:32/km"
    duration_display: str  # e.g., "21:45"
    location: Optional[str]  # from start_lat/start_lng reverse geocode, or None
    detection_confidence: Optional[float]
    detection_source: Optional[str]
    user_confirmed: Optional[bool]
    is_personal_best: bool = False

    model_config = ConfigDict(from_attributes=True)


class RaceCandidateResponse(BaseModel):
    confirmed: List[RaceCard]    # Tier 1
    candidates: List[RaceCard]   # Tier 2
    browse_count: int            # How many browseable activities exist
    strip_data: RacingLifeStripData  # Current strip state


class RacingLifeStripData(BaseModel):
    weeks: List[WeekData]  # Weekly volume + intensity
    pins: List[RacePin]    # Confirmed events as pins


class WeekData(BaseModel):
    week_start: date
    total_volume_km: float
    intensity: str  # 'easy', 'moderate', 'hard' (dominant)
    activity_count: int


class RacePin(BaseModel):
    event_id: UUID
    date: date
    distance_category: str
    time_seconds: int
    is_personal_best: bool
    performance_percentage: Optional[float]
```

---

### 1A.4: Race Curation Frontend (Discovery Experience)

**Read the product spec section "The Race Curation Experience" before
building this.** It is prescriptive. The spec says what the moment is.
Don't deviate.

Key requirements from the product spec:

- **Cards, not tables.** Each race candidate is a card with enough
  context to trigger recognition. Not a row. Not a checkbox list.
- **Three tiers:** "Races we found" → "Were these races?" → "Any
  races we missed?"
- **Real-time strip building.** As the athlete confirms races, the
  Racing Life Strip updates. Each confirmed race adds a pin. The
  shape of their racing history emerges as they curate.
- **Fingerprint payoff during curation.** The strip builds visually
  as they go. When curation is complete, the first finding appears.
- **This is onboarding into the fingerprint feature.** Not a setup
  screen. Not a form. A discovery experience.

**Files to create/modify:**
- New page: `apps/web/app/fingerprint/page.tsx` (Next.js App Router —
  follows existing pattern like `apps/web/app/progress/page.tsx`,
  `apps/web/app/discovery/page.tsx`)
- Uses the `/v1/fingerprint/race-candidates` and
  `/v1/fingerprint/strip` endpoints
- Calls `/v1/fingerprint/confirm-race` and `/v1/fingerprint/add-race`
  on user interaction

**Frontend implementation details are determined by the existing
frontend framework and patterns.** Match the existing component
structure, state management, and styling approach. Do not introduce
new frameworks or patterns.

---

### 1A.5–1A.7: Training State, Block Signatures, Fitness-Relative Performance

These are computed inside `populate_performance_events()` (1A.2) and
when individual races are confirmed/added via the curation API (1A.3).
They are not separate build steps — they are functions called by the
pipeline.

**Training state:** Call `compute_training_state_history()` from P3
with all race dates as `target_dates`. Store CTL/ATL/TSB on each
PerformanceEvent.

**Block signature:** Call `compute_block_signature()` from 1A.2.
Store as JSONB on PerformanceEvent.

**Fitness-relative performance:** This column is `None` until the
athlete has 8+ confirmed races with both `rpi_at_event` and
`ctl_at_event`. At that point, fit a simple linear regression
(CTL → predicted RPI) from the athlete's own data:
- `predicted_rpi` = linear model output for `ctl_at_event`
- `fitness_relative_performance` = `rpi_at_event / predicted_rpi`
  (values > 1.0 = outperformance)
- If < 8 confirmed races: leave `None`. Do not use a population
  default — different athletes at different fitness levels make
  a population model meaningless.
- The pipeline should check this threshold on every race
  confirmation and backfill the column when it becomes available.

**Why 8:** You need enough variance in both CTL and RPI to fit
a non-degenerate line. With 3-5 points clustered at similar
fitness, the model produces nonsense slopes. 8 is conservative
but safe.

---

### Tests for Phase 1A

**File:** `tests/test_performance_event_pipeline.py`

```python
class TestPerformanceEventPopulation:
    def test_creates_event_from_user_verified_race(self):
        """Activity with user_verified_race=True → PerformanceEvent created."""

    def test_creates_event_from_strava_race_tag(self):
        """Activity with strava_workout_type_raw=3 → PerformanceEvent created."""

    def test_creates_event_from_high_confidence_detection(self):
        """detect_race_candidate confidence >= 0.7 → PerformanceEvent created."""

    def test_creates_candidate_from_medium_confidence(self):
        """detect_race_candidate confidence 0.3-0.7 → PerformanceEvent
        created with user_confirmed=None."""

    def test_ignores_low_confidence(self):
        """detect_race_candidate confidence < 0.3 → no PerformanceEvent."""

    def test_skips_duplicate_activities(self):
        """Activity with is_duplicate=True → skipped."""

    def test_computes_training_state(self):
        """PerformanceEvent has non-null CTL/ATL/TSB."""

    def test_computes_block_signature(self):
        """PerformanceEvent has non-null block_signature JSONB with
        expected keys."""

    def test_computes_rpi(self):
        """PerformanceEvent has non-null rpi_at_event."""

    def test_unique_constraint_prevents_duplicate_events(self):
        """Running pipeline twice doesn't create duplicate events."""


class TestBlockSignature:
    def test_lookback_scales_with_distance(self):
        """5K uses 8 weeks, marathon uses 18 weeks."""

    def test_volume_trajectory_correct(self):
        """Known activity set → expected weekly volumes."""

    def test_intensity_distribution_correct(self):
        """Known classified activities → expected easy/moderate/hard
        proportions."""

    def test_taper_detection(self):
        """Volume declines for 2 weeks before event → taper detected."""

    def test_no_crash_on_sparse_data(self):
        """Only 3 activities in lookback window → signature still
        computed (sparse but valid)."""


class TestRaceRoleClassification:
    def test_tune_up_before_longer_race(self):
        """5K 4 weeks before marathon → tune_up."""

    def test_a_race_when_alone(self):
        """Only race in 12-week window → a_race."""

    def test_user_override(self):
        """User sets role → user_classified_role takes precedence."""
```

**File:** `tests/test_fingerprint_api.py`

```python
class TestRaceCandidatesEndpoint:
    def test_returns_three_tiers(self):
        """Response has confirmed, candidates, and browse_count."""

    def test_requires_auth(self):
        """401 without token."""

    def test_confirmed_tier_includes_high_confidence(self):
        """Events with confidence >= 0.7 appear in confirmed tier."""

    def test_candidate_tier_includes_medium_confidence(self):
        """Events with confidence 0.3-0.7 appear in candidates tier."""

    def test_card_has_recognition_context(self):
        """Each card has name, date, pace_display, distance_category."""


class TestConfirmRaceEndpoint:
    def test_confirm_sets_user_confirmed_true(self):
    def test_reject_sets_user_confirmed_false(self):
    def test_confirm_triggers_computation(self):
        """Confirming a race computes training state and block sig."""
    def test_returns_updated_strip_data(self):

class TestAddRaceEndpoint:
    def test_creates_performance_event(self):
    def test_sets_detection_source_user_added(self):
    def test_returns_updated_strip_data(self):

class TestStripEndpoint:
    def test_returns_weekly_data(self):
    def test_returns_race_pins(self):
    def test_pins_match_confirmed_events(self):
```

---

### ═══════════════════════════════════════════════════════
### GATE B: Phase 1A Complete
### ═══════════════════════════════════════════════════════

**All conditions must be true before ANY Phase 1B work begins.**

**B1.** All Phase 1A tests pass: `pytest tests/test_performance_event_pipeline.py tests/test_fingerprint_api.py -v`

**B2.** Founder's account verification:

```bash
docker exec strideiq_api python -c "
from database import SessionLocal
from models import Athlete, PerformanceEvent
db = SessionLocal()
athlete = db.query(Athlete).filter(Athlete.email=='mbshaf@gmail.com').first()
events = db.query(PerformanceEvent).filter(
    PerformanceEvent.athlete_id == athlete.id
).order_by(PerformanceEvent.event_date).all()
print(f'Total PerformanceEvents: {len(events)}')
for e in events:
    sig = 'YES' if e.block_signature else 'NO'
    ctl = f'{e.ctl_at_event:.1f}' if e.ctl_at_event else 'N/A'
    print(f'  {e.event_date} | {e.distance_category:15s} | {e.time_seconds:5d}s | CTL={ctl} | sig={sig} | source={e.detection_source} | confirmed={e.user_confirmed}')
db.close()
"
```

**Expected:**
- PerformanceEvents exist for all of the founder's known races
  (including the ones previously missed: 25K trail races, 16K
  Bellhaven Hills, November half marathons, early 5Ks)
- Each confirmed event has non-null CTL, block_signature, and
  rpi_at_event
- CTL values are plausible (not near-zero from cold-start)

**B3.** Race curation flow works end-to-end:
- `/v1/fingerprint/race-candidates` returns the three tiers
- Confirming a race updates the strip data
- Adding a missed race creates a PerformanceEvent with computed fields
- The Racing Life Strip data reflects all confirmed events

**B4.** The discovery experience renders in the frontend:
- Cards are cards (not table rows)
- The strip builds as races are confirmed
- The flow matches what the product spec describes

**Evidence required:** Paste API responses, test output, and a
screenshot of the discovery experience.

---

## Phase 1B: Pattern Extraction + Validation

---

### 1B.1: Pattern Extraction Service

**New file:** `services/fingerprint_analysis.py`

```python
@dataclass
class FingerprintFindingResult:
    """One finding from the pattern analysis.

    Named FingerprintFindingResult (not FingerprintFinding) to avoid
    collision with the SQLAlchemy model StoredFingerprintFinding in
    models.py.
    """
    layer: int  # 1-4
    finding_type: str  # e.g., 'pb_distribution', 'block_comparison',
                       #       'tuneup_pattern', 'fitness_relative'
    sentence: str  # The athlete-facing finding
    evidence: dict  # Supporting data (explorable)
    statistical_confidence: float  # 0-1
    effect_size: float  # Cohen's d or equivalent
    sample_size: int  # Number of events in analysis
    confidence_tier: str  # 'high', 'exploratory', 'descriptive', 'suppressed'
    is_significant: bool  # Passes automated quality gate


def extract_fingerprint_findings(
    athlete_id: UUID,
    db: Session,
) -> List[FingerprintFindingResult]:
    """
    Run all four layers of pattern extraction across the athlete's
    confirmed PerformanceEvents.

    Returns findings sorted by significance.
    Only returns findings that pass the automated quality gate.
    """


def _layer1_pb_distribution(
    events: List[PerformanceEvent],
    activities: List[Activity],
    db: Session,
) -> List[FingerprintFindingResult]:
    """
    Layer 1: Where Do PBs Live?

    Compare race-day performance vs best training performance at
    each distance. Compute the race-day uplift percentage.

    Minimum: 3 PerformanceEvents.

    Finding: "You race X% faster than your best training efforts"
    or "Your training and race performances are within X%."
    """


def _layer2_block_comparison(
    events: List[PerformanceEvent],
) -> List[FingerprintFindingResult]:
    """
    Layer 2: Block Signature Comparison.

    Sort events by performance (fitness-relative, not raw time).
    Split into top half vs bottom half (not quartiles — quartiles
    require 12+ events to get 3 per group).

    For each dimension of the block signature, compute:
    - Mean and std for top group
    - Mean and std for bottom group
    - Effect size (Cohen's d from pooled SD)

    If both groups have >= 3 events: add Mann-Whitney U p-value.
    If either group has < 3: report descriptive stats only, no
    p-value, mark finding as 'descriptive' tier.

    Minimum: 6 PerformanceEvents (3 per group) for statistical
    comparison. 4-5 events: descriptive only. < 4: skip layer.

    Findings: differences in volume peak timing, taper duration,
    long run patterns, intensity distribution, quality session
    frequency.
    """


def _layer3_tuneup_pattern(
    events: List[PerformanceEvent],
) -> List[FingerprintFindingResult]:
    """
    Layer 3: Tune-up to A-Race Relationship.

    Find pairs where a tune_up precedes an a_race within 8 weeks.
    Compare A-race fitness-relative performance when:
    - Tune-up was a PB vs not
    - Volume stayed high after tune-up vs reduced
    - Time gap between tune-up and A-race

    Minimum: 2 tune-up → A-race pairs.

    Findings about the relationship between tune-up performance
    and A-race outcome.
    """


def _layer4_fitness_relative(
    events: List[PerformanceEvent],
) -> List[FingerprintFindingResult]:
    """
    Layer 4: Fitness-Relative Performance.

    Analyze outperformance/underperformance across all events.
    Split into outperformers (fitness_relative_performance > 1.0)
    vs underperformers (< 1.0). Correlate with block signature
    dimensions to find what predicts outperformance.

    **Activation gate:** This layer requires `fitness_relative_performance`
    to be non-null, which requires 8+ confirmed races with CTL and RPI.
    If the column is null on all events, skip this layer entirely and
    return an empty list. Do not attempt to compute fitness-relative
    values inline — they come from the pipeline's linear model.

    When active:
    Minimum: 6 PerformanceEvents with valid fitness_relative_performance
    (3 per group) for statistical comparison. 4-5: descriptive only.
    < 4: skip.

    Findings: what training patterns produce outperformance.
    """
```

---

### 1B.2: Automated Quality Gate

Every finding must pass these thresholds before it reaches the
founder for review. These are not advisory — they are hard stops.

```python
QUALITY_THRESHOLDS = {
    # --- Per-analysis minimums (total events entering the layer) ---
    'min_sample_size': 3,          # Minimum events for any analysis
    'min_effect_size': 0.3,        # Cohen's d >= 0.3 (small-medium)
    'max_p_value': 0.10,           # p < 0.10 (relaxed for small N)

    # --- Comparison layer minimums (Layers 2 and 4) ---
    # These layers split events into groups (top vs bottom).
    # You cannot run a statistical test on N=1 per group.
    'min_comparison_total': 6,     # Minimum events for group comparison
    'min_per_group': 3,            # Minimum events in each group

    # --- High-confidence tier ---
    'high_confidence_sample': 8,   # Events needed for high-confidence
    'high_confidence_per_group': 4,# Per-group for high-confidence
    'high_confidence_effect': 0.5, # Cohen's d for high-confidence
    'high_confidence_p': 0.05,     # p-value for high-confidence
}


def passes_quality_gate(finding: FingerprintFindingResult) -> bool:
    """
    Returns True if the finding clears the automated quality gate.

    Layer 1 (PB distribution) and Layer 3 (tune-up pattern) are
    descriptive analyses — they report observed patterns. Quality
    gate: sample >= 3, |d| >= 0.3.

    Layers 2 and 4 are comparison analyses — they split events into
    groups and test for differences. Quality gate: total >= 6,
    per-group >= 3, |d| >= 0.3, p < 0.10.

    When a comparison layer has sufficient total events but < 3
    per group (e.g., 5 events split 4/1), fall back to descriptive
    statistics: report mean ± SD per group, effect size from pooled
    SD, but DO NOT produce a p-value. Mark as 'descriptive' tier
    instead of 'exploratory' or 'high'.

    Findings that don't clear the gate are suppressed entirely.
    """
```

---

### 1B.3: Finding Storage

Store findings on the athlete for retrieval by the `/v1/fingerprint/findings`
endpoint.

Option A: Add a `StoredFingerprintFinding` model (new table).
Option B: Store as JSONB on the Athlete model.

Recommendation: **New table.** Findings have metadata (layer, type,
confidence, effect size, creation date, computation version) that
benefits from queryability.

```python
class StoredFingerprintFinding(Base):
    __tablename__ = "fingerprint_finding"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"),
                        nullable=False, index=True)
    layer = Column(Integer, nullable=False)
    finding_type = Column(Text, nullable=False)
    sentence = Column(Text, nullable=False)
    evidence = Column(JSONB, nullable=False)
    statistical_confidence = Column(Float, nullable=False)
    effect_size = Column(Float, nullable=False)
    sample_size = Column(Integer, nullable=False)
    confidence_tier = Column(Text, nullable=False)
    # confidence_tier: 'high', 'exploratory', 'descriptive', 'suppressed'
    computation_version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

Migration: `fingerprint_1b_create_findings_table.py`

---

### Tests for Phase 1B

**File:** `tests/test_fingerprint_analysis.py`

```python
class TestLayer1PBDistribution:
    def test_identifies_race_day_uplift(self):
        """Athlete races 4% faster than training → finding produced."""

    def test_identifies_training_ceiling(self):
        """Athlete trains within 1% of race → finding produced."""

    def test_suppresses_with_insufficient_data(self):
        """Only 2 events → no finding (below min_sample_size)."""


class TestLayer2BlockComparison:
    def test_identifies_volume_peak_difference(self):
        """Best races peak 5 weeks out, worst peak 2 weeks out →
        finding with effect size > 0.3."""

    def test_identifies_taper_difference(self):
        """Best races have longer tapers → finding produced."""

    def test_suppresses_trivial_difference(self):
        """Difference exists but Cohen's d < 0.3 → suppressed."""

    def test_descriptive_fallback_with_5_events(self):
        """5 events → top half (3) vs bottom half (2). Reports mean ± SD
        and effect size but no p-value. Tier = 'descriptive'."""

    def test_skips_with_fewer_than_4_events(self):
        """3 events → skip layer entirely (can't form meaningful groups)."""


class TestLayer3TuneupPattern:
    def test_identifies_tuneup_pb_risk(self):
        """Tune-up PBs followed by A-race underperformance →
        finding produced."""

    def test_handles_no_tuneup_pairs(self):
        """No tune-up → A-race pairs → no finding (not an error)."""


class TestLayer4FitnessRelative:
    def test_identifies_outperformance_pattern(self):
        """Outperformance correlates with taper length → finding."""

    def test_normalizes_for_fitness_level(self):
        """Same raw time at different CTL → different
        fitness_relative_performance values."""


class TestQualityGate:
    def test_passes_significant_finding(self):
        """Large effect, low p, sufficient N → 'high' tier."""

    def test_suppresses_noisy_finding(self):
        """Small effect, high p → 'suppressed'."""

    def test_exploratory_middle_ground(self):
        """Moderate effect, borderline p → 'exploratory' tier."""

    def test_descriptive_when_small_groups(self):
        """Comparison layer with 5 events (3/2 split) → 'descriptive'
        tier with mean ± SD but no p-value."""

    def test_no_p_value_on_n1_group(self):
        """Comparison layer with 4 events (3/1 split) → no p-value
        produced. Effect size from pooled SD only."""

    def test_sample_size_gate(self):
        """Only 2 events → suppressed regardless of effect size."""

    def test_comparison_layer_requires_6_for_statistical(self):
        """Layer 2 with exactly 6 events (3/3 split) → statistical
        test runs and produces p-value."""
```

---

### ═══════════════════════════════════════════════════════
### GATE C: Phase 1B Complete
### ═══════════════════════════════════════════════════════

**Two sub-gates. Both must pass.**

#### Gate C1: Automated Quality Gate

```bash
# All Phase 1B tests pass
pytest tests/test_fingerprint_analysis.py -v

# Findings exist and pass quality thresholds
docker exec strideiq_api python -c "
from database import SessionLocal
from models import Athlete
from services.fingerprint_analysis import extract_fingerprint_findings
db = SessionLocal()
athlete = db.query(Athlete).filter(Athlete.email=='mbshaf@gmail.com').first()
findings = extract_fingerprint_findings(athlete.id, db)
for f in findings:
    print(f'[{f.confidence_tier:12s}] L{f.layer} | {f.finding_type:25s} | d={f.effect_size:.2f} | n={f.sample_size} | {f.sentence[:80]}')
print(f'\nTotal findings: {len(findings)}')
print(f'Passing quality gate: {sum(1 for f in findings if f.confidence_tier in ("high", "exploratory", "descriptive"))}')
print(f'Suppressed: {sum(1 for f in findings if f.confidence_tier == "suppressed")}')
db.close()
"
```

**Expected:** At least 1 finding passes the quality gate. Suppressed
findings demonstrate the gate is working (not everything passes).

#### Gate C2: Founder Validation (Human Gate)

**This gate has no automated test.** The founder reads the findings
and answers one question: **Are these true?**

The builder presents findings to the founder with supporting evidence.
The founder compares against their own knowledge of their racing
history.

**If yes:** Phase 1 is complete. The system discovered something true
about the athlete's body that they suspected but couldn't confirm.
The findings are worth building surfaces for. Proceed to Phase 2
under a separate spec.

**If no:** Identify why. Options:
- Data is wrong (loop back to pre-work)
- Analysis is wrong (fix the algorithm, re-run 1B)
- Findings are true but trivial (raise quality thresholds, look for
  deeper patterns)
- Insufficient race history (wait for more data, or expand what
  qualifies as a PerformanceEvent)

**Do not proceed to Phase 2 if the findings are wrong or trivial.**

---

### Gate C2 Result (March 4, 2026)

**PASSED.** Three findings validated by the founder (17 confirmed races):

1. **Long run correlation (TRUE):** Best races preceded by longer long
   runs (16 vs 14 mi). Founder context: peak training blocks reach
   18-22 mi long runs at ~70 mi/week.

2. **Race-day uplift (TRUE):** Races outperform training by a
   meaningful margin. Founder context: "I race hard — willing to hurt
   bad and deep into race." The mile was an outlier (one-off effort).

3. **Taper length (TRUE WITH CONTEXT):** System detected short taper
   (2 weeks) correlates with better races, long taper (5 weeks) with
   weaker races. Founder context: "I never taper 5 weeks — that's
   injury, not strategy. I only do short tapers." The system correctly
   detected the pattern but the causal interpretation needs nuance:
   what looks like a long taper is actually forced rest from injury.

   **This is the canonical example of why the athlete provides context
   the data cannot.** The system should eventually distinguish between
   intentional taper and unplanned volume loss. Until then, the
   sentence should describe the pattern without asserting causation:
   "Your best races follow short, sharp tapers. When volume drops
   earlier, those races don't go as well."

---

## What Is NOT Built in Phase 1

These items do not begin until Gate C passes. They will be scoped in a
separate spec.

- Progress page state machine rendering (the five states)
- Block Shape Overlay visual
- Convergence Warning visual
- Race Report Card visual
- Personal Operating Manual visual
- Racing Life Strip as a persistent progress page component (the strip
  in Phase 1 exists only in the curation flow)
- Pre-race confidence/warning sentences on the progress page
- Post-race analysis sentences on the progress page
- Morning briefing integration
- Proactive coach integration
- Home page fingerprint signal

---

## File Index

New files created in Phase 1:

| File | Phase | Purpose |
|------|-------|---------|
| `services/duplicate_scanner.py` | P1 | Retroactive duplicate detection |
| `services/performance_event_pipeline.py` | 1A | Event population + block sigs |
| `services/fingerprint_analysis.py` | 1B | Four-layer pattern extraction |
| `routers/fingerprint.py` | 1A | Race curation API |
| `schemas/fingerprint.py` | 1A | Pydantic response models |
| `tests/test_duplicate_scanner.py` | P1 | Dedup tests |
| `tests/test_training_load_single_pass.py` | P3 | EMA accuracy tests |
| `tests/test_race_detection_expanded.py` | P4 | Expanded detection tests |
| `tests/test_effort_classification_bulk.py` | P2 | Bulk classification tests |
| `tests/test_performance_event_pipeline.py` | 1A | Pipeline tests |
| `tests/test_fingerprint_api.py` | 1A | API endpoint tests |
| `tests/test_fingerprint_analysis.py` | 1B | Pattern extraction tests |

Files modified in Phase 1:

| File | Phase | Change |
|------|-------|--------|
| `models.py` | P1, 1A, 1B | Add is_duplicate, PerformanceEvent, StoredFingerprintFinding |
| `services/training_load.py` | P1, P3 | Dedup filter, single-pass EMA |
| `services/performance_engine.py` | P4 | 8 distances, no HR gate, name signal |
| `tasks/strava_tasks.py` | P4 | Store strava_workout_type_raw, pass name |
| `routers/admin.py` | P2 | Admin batch classify endpoint |
| `main.py` | 1A | Register fingerprint router |

Migrations:

| Migration | Phase |
|-----------|-------|
| `fingerprint_p1_add_duplicate_fields.py` | P1 |
| `fingerprint_p4_add_strava_raw_workout_type.py` | P4 |
| `fingerprint_1a_create_performance_event.py` | 1A |
| `fingerprint_1b_create_findings_table.py` | 1B |

---

*This spec is a builder document. It defines HOW to build Phase 1 of
the Racing Fingerprint. For WHAT the athlete experiences and WHY, read
`RACING_FINGERPRINT_AND_PROGRESS_STATE_MACHINE_SPEC.md`. For how you
work with this founder, read `FOUNDER_OPERATING_CONTRACT.md`. For how
every screen should feel, read `DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md`.*
