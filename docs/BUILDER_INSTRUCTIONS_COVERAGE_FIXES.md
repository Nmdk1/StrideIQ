# Builder Instructions: Shape Sentence Coverage Fixes

**Date:** March 8, 2026 (v2 — incorporates tech advisor code review)  
**Context:** Shape sentence coverage is ~60% recent, drops sharply on
historical data. Three failure modes from production analysis.  
**Read first:** `docs/specs/SHAPE_SENTENCE_SPEC.md`

---

## Pipeline Reminder

The extractor pipeline in `extract_shape()` is:

```
raw_blocks = _detect_zone_transitions(time, zone_per_point)
merged_blocks = _merge_micro_phases(raw_blocks, MIN_PHASE_DURATION_S)
merged_blocks = _consolidate_same_zone(merged_blocks)
merged_blocks = _merge_similar_pace_blocks(merged_blocks, phase_pace, ...)
merged_blocks = _consolidate_same_zone(merged_blocks)
                                                          ← FIX 1 GOES HERE
phases = _build_phases(merged_blocks, ...)                ← phases built from blocks
accelerations = _detect_accelerations(time, ..., phases)  ← accels built from phases
summary = _compute_summary(phases, accelerations, ...)
classification = _derive_classification(phases, accelerations, summary, ...)
```

Blocks are `(start_idx, end_idx, zone)` tuples. Phases and accelerations
do not exist until `_build_phases()` and `_detect_accelerations()` run.
Any merge logic that runs before those steps **cannot reference Phase or
Acceleration objects** — it must work from raw signals (pace_per_point,
cadence, grade arrays) and the block tuples.

---

## Success Gate

**Do not optimize for coverage alone.** The target is **higher coverage
without trust regressions**.

Before accepting any fix set, require all of the following:

1. The 14-activity verification table is re-run and does not regress on
   known-good recent activities
2. No new trust-breaking visible sentences are introduced on the three
   athlete validation set
3. Coverage increases for the diagnosed suppression buckets
   (`phase_count > 8`, `anomaly`, `cls=None`) without weakening
   suppression as a shortcut
4. The recent working corpus (Michael last ~10, Larry last ~10) stays
   working

**Coverage is a secondary metric. Trust is the primary metric.** If a
change raises coverage by surfacing more wrong sentences, it failed.

---

## Fix 1: Anti-Oscillation Merge (Highest ROI)

**Problem:** Larry's easy runs at 13:00-14:00/mi produce 10+ phases
because GPS noise dips his pace below the easy ceiling into gray zone
for brief periods, creating easy→gray→easy→gray oscillation.

**Where to insert:** After the final `_consolidate_same_zone()` and
BEFORE `_build_phases()`. This is a block-level operation.

```python
# In extract_shape(), after Step 3d:
merged_blocks = _consolidate_same_zone(merged_blocks)  # existing Step 3d

# Step 3e: Anti-oscillation merge — collapse easy↔gray GPS noise
merged_blocks = _merge_easy_gray_oscillation(
    merged_blocks, phase_pace, cadence, time, pace_profile,
)
merged_blocks = _consolidate_same_zone(merged_blocks)  # clean up after

# Step 4: Classify phase types (existing)
phases = _build_phases(...)
```

**New function signature:**

```python
def _merge_easy_gray_oscillation(
    blocks: List[Tuple[int, int, str]],
    pace_per_point: List[float],
    cadence: List,
    time: List,
    pace_profile: PaceProfile,
) -> List[Tuple[int, int, str]]:
```

**Merge rules — absorb the gray block into the preceding easy block
ONLY when ALL of the following are true:**

1. Pattern is exactly `easy → gray → easy` (three consecutive blocks)
2. Gray block duration < 90 seconds (compute from `time[end] - time[start]`)
3. Gray block average pace is within 25 sec/mi of **each** adjacent easy
   block's average pace independently (not their average — comparing to
   the average of two neighbors can swallow a genuine moderate insert
   when the neighbors are far apart)
4. Gray block average pace is near the **easy ceiling**, not the easy
   center — specifically, the gray pace should be no more than 30 sec/mi
   faster than `pace_profile._easy_ceiling()`. The bug is boundary
   oscillation around the fast edge of easy, not deep gray work.
5. If cadence data exists in the gray block: compute cadence CV in a
   short boundary window (last 15s of preceding easy + gray block +
   first 15s of following easy). If CV < 0.15, cadence is steady and
   the effort didn't change. This is the strongest signal for slow
   runners like Larry where GPS pace is noisy but cadence is stable.
6. No speed-work signature in the gray block: check that `min(pace)` in
   the gray block does NOT trigger
   `pace_profile.is_significant_acceleration()`, and no cadence spike
   > 15 spm above the boundary window average exists in the gray block.

**CRITICAL: Because accelerations don't exist yet at this pipeline stage,
the "don't erase real work" guard MUST use raw-signal proxies (rules 4
and 6 above), not Acceleration objects.**

**When the pattern matches, absorb:** Change the gray block's zone to
'easy', then the subsequent `_consolidate_same_zone()` will merge the
three blocks into one.

**Regression protection:**
- Michael's Feb 27 progression (9:20→8:00): gray phases are genuine
  effort changes with >25 sec/mi delta to neighbors → not absorbed
- A moderate long run at 7:30 between easy 8:20 phases: pace is 50+
  sec/mi faster than the easy ceiling → fails rule 4 → not absorbed
- Only oscillation patterns get merged, not isolated gray at start/end

**Expected impact:** Larry from 41% to ~75%. Michael's older long runs
(esp Feb 08 — 20 easy↔gray transitions) should resolve.

---

## Fix 2: Anomaly Recalibration (Hybrid Rule)

**File:** `apps/api/services/shape_extractor.py`, function `_check_anomaly`

**Current logic (line 1398-1416):**
```python
return gaps > 0 and (unrealistic_count > 0 or gaps >= 3)
```

Any run with 3+ GPS gaps >30s is anomaly regardless of run duration.

**Fix: Hybrid rule — proportion plus severity, not pure proportion.**

Do NOT replace with only `corruption_pct > 0.05`. That risks letting
repeated meaningful gaps through on shorter runs and ignores single
huge gaps. Use a hybrid:

```python
def _check_anomaly(
    velocity: List[float], time: List, phases: List[Phase],
) -> bool:
    total_duration = time[-1] - time[0] if len(time) >= 2 else 0
    if total_duration <= 0:
        return True

    n = len(time)
    total_gap_time = 0
    gap_count = 0
    max_single_gap = 0
    unrealistic_count = 0

    for i in range(1, n):
        dt = time[i] - time[i - 1]
        if dt > 30:
            gap_count += 1
            total_gap_time += dt
            max_single_gap = max(max_single_gap, dt)

    for v in velocity:
        if v is not None and v > MAX_VELOCITY_MPS:
            unrealistic_count += 1

    corruption_pct = total_gap_time / total_duration

    # Always anomaly: unrealistic velocity spikes
    if unrealistic_count > 0:
        return True

    # Always anomaly: single huge gap (> 5 minutes)
    if max_single_gap > 300:
        return True

    # Proportion-based: > 5% of run is gaps
    if corruption_pct > 0.05:
        return True

    # Severity on shorter runs: 3+ gaps on runs < 30 min
    if gap_count >= 3 and total_duration < 1800:
        return True

    return False
```

**Why hybrid:** A 20-mile run with three 30-second gaps is 1.3%
corruption (normal). A 15-minute run with three 30-second gaps is
10% corruption AND trips the short-run severity rule. A single
5-minute GPS blackout is always suspicious.

**Expected impact:** Michael's 15-20mi long runs stop being anomaly.
Genuinely corrupted data still gets caught.

---

## Fix 3: Classification Rule Fixes (Three Separate Issues)

### Fix 3A: Hill Repeats — Acceleration-Aware Detection

**Problem:** After zone model fix, BHL's hill repeat run collapsed from
23 phases to 1 phase. Hill efforts are now accelerations on top of a
single easy phase, but the classifier only checks for `hill_effort`
phases.

**Step 1: Add grade data to Acceleration and thread it through the
acceleration pipeline.**

Add `avg_grade` field to the `Acceleration` dataclass:

```python
@dataclass
class Acceleration:
    start_time_s: int
    end_time_s: int
    duration_s: int
    distance_m: float
    avg_pace_sec_per_mile: float
    avg_pace_heat_adjusted: Optional[float]
    pace_zone: str
    avg_hr: Optional[float]
    hr_delta: Optional[float]
    avg_cadence: Optional[float]
    cadence_delta: Optional[float]
    position_in_run: float
    recovery_after_s: Optional[int]
    hr_recovery_rate: Optional[float] = None
    avg_grade: Optional[float] = None        # NEW
    elevation_gain_m: Optional[float] = None  # NEW
```

This is not a local dataclass tweak. You must thread grade/elevation
through the full acceleration path:

- `extract_shape(...)` must pass `grade` and `altitude` into
  `_detect_accelerations(...)`
- `_detect_accelerations(...)` must pass them into both
  `_detect_velocity_accelerations(...)` and
  `_detect_cadence_accelerations(...)`
- both channel detectors must pass them into `_build_acceleration(...)`
- `_build_acceleration(...)` computes:
  - `avg_grade` from `grade_smooth[start_idx:end_idx+1]`
  - `elevation_gain_m` as summed positive altitude deltas inside the
    acceleration window, not just end-start net change

Do not partially wire this. If one channel lacks grade/elevation data,
merged acceleration behavior becomes inconsistent.

**Step 2: Update `_derive_classification()` hill_repeats check.**

Per `docs/specs/SHAPE_SENTENCE_SPEC.md`, hill repeats are defined by:
- base phases easy/gray
- 3+ accelerations
- meaningful uphill grade on those accelerations

Do NOT add extra repeat-structure gates (duration CV, periodic spacing,
recovery symmetry) unless the founder explicitly changes the spec. The
current problem is that the classifier cannot see hill work once it has
collapsed into accelerations instead of phases.

```python
if n_accels >= 3:
    # Existing phase-based check
    hill_efforts_from_phases = [p for p in effort_phases if p.phase_type == 'hill_effort']
    if len(hill_efforts_from_phases) >= 3:
        return 'hill_repeats'

    # Acceleration-based check (after zone consolidation)
    if summary.elevation_profile not in ('flat',):
        hill_accels = [a for a in accelerations
                       if a.avg_grade is not None and a.avg_grade > 4.0
                       and a.elevation_gain_m is not None and a.elevation_gain_m > 0]
        if len(hill_accels) >= 3:
            return 'hill_repeats'
```

The goal is to honor the spec: if an easy/gray run contains 3+ uphill
accelerations, classify it as `hill_repeats` rather than leaving it as
`cls=None` or misclassifying it as `fartlek`.

### Fix 3B: Progression — Debug Before Relaxing

**DO NOT start by relaxing the ≥15 sec/mi rule.**

The code already has TWO progression paths:
1. Strict: every consecutive step ≥15 sec/mi (line 1280-1288)
2. Fallback: `summary.pace_progression == 'building'` AND total
   drop > 30 sec/mi (line 1308-1316)

BHL's Feb 16 4-phase run fails BOTH paths. The strict rule failing
on a 10 sec/mi final step is only half the story. The fallback also
failed, which means one of:
- `effort_phases` shrank after warmup/cooldown exclusion
- `summary.pace_progression` came out `variable`, not `building`
- acceleration/hilly structure disqualified it

**Required debug output for BHL Feb 16 before writing any fix:**
```
effort_phases count after warmup/cooldown exclusion
summary.pace_progression value
exact phase paces being fed into the strict rule
n_accels and acceleration_clustering
has_stride_pattern value
elevation_profile
```

**Only after identifying which branch actually fails and why, write
the targeted fix for that branch.**

### Fix 3C: "1-phase cls=None" — Probably Not an easy_run Bug

**The code already catches quiet 1-phase runs:**
```python
# Line 1380: primary easy_run check
if all_easy_or_gray and n_accels <= 1 and len(effort_phases) <= 3:
    return 'easy_run'

# Line 1391: fallback for any quiet short shape
if n_accels <= 1 and len(effort_phases) <= 3:
    return 'easy_run'
```

A 1-phase run reaching `cls=None` almost certainly has `n_accels > 1`.
This is likely a **hilly single-phase with multiple accelerations**
problem — same bucket as the hill-repeat issue.

**Required debug output for BHL Feb 26 before writing any fix:**
```
n_accels
summary.acceleration_clustering
summary.elevation_profile
all_easy_or_gray
effort_phases count and zones
```

If `n_accels > 1`, this belongs in the hilly-acceleration bucket
(Fix 3A), not a separate easy_run rule bug.

---

## Required Tests Before Merging

Add these to `test_shape_extractor.py`:

1. **Oscillation collapse:** Larry-style easy→gray→easy→gray→easy
   oscillation (gray phases < 90s, pace near easy ceiling, steady
   cadence) → collapses to one easy phase
2. **Genuine gray preserved:** Short gray insert between easy phases
   with pace > 25 sec/mi faster than neighbors → does NOT get absorbed
3. **Long run GPS tolerance:** 20-mile run with 3× 30-second gaps →
   NOT anomaly
4. **Corrupted run still caught:** 15-minute run with 3× 30-second
   gaps → IS anomaly
5. **Single huge gap:** Run with one 6-minute gap → IS anomaly
6. **Hill repeats from accelerations:** Single-phase hilly run with
   3+ graded accelerations on an easy/gray base → `hill_repeats`
7. **Hilly run ≠ hill repeats:** Single-phase hilly run with 3+
   accelerations that do NOT meet uphill grade requirement → NOT
   `hill_repeats`
8. **Progression regression:** Whatever fix lands for 3B, include
   the actual BHL data as a regression test
9. **14-activity verification gate:** Re-run the validation set and
   assert no regressions on known-good recent activities
10. **Trust gate:** A deliberately ambiguous/honest-gap case stays
    suppressed rather than being forced into a wrong sentence

---

## Build Sequence

1. Fix 1 (anti-oscillation merge) → backfill → measure coverage
2. Fix 2 (anomaly hybrid) → backfill → measure
3. Fix 3A (hill repeats + Acceleration.avg_grade) → verify BHL
4. Fix 3B (progression — debug first, then fix) → verify BHL Feb 16
5. Fix 3C (1-phase debug — likely resolved by 3A)
6. Full backfill after all fixes
7. Coverage recheck — aim for materially higher coverage across all
   three athletes while preserving trust and the 14-activity table

## Do NOT Touch

- Acceleration detection (dual-channel velocity + cadence) — works
- Sentence generator patterns — correct
- `title_authorship` detection — premature until coverage ≥ 80%
- Suppression rules (phase_count > 8, cls=null) — safety valves;
  fix the upstream problems that trigger them

---

## Deploy

```bash
cd /opt/strideiq/repo && git pull origin main && docker compose -f docker-compose.prod.yml up -d --build
```
