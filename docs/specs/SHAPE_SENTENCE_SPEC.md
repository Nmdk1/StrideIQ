# Shape Sentence & Zone Model Spec

**Date:** March 6, 2026
**Status:** Draft — Founder review required
**Depends on:** `docs/specs/LIVING_FINGERPRINT_SPEC.md` (deployed)
**Origin:** Founder + advisor session. The shape extractor is deployed and
working. The zone model and sentence generation are the missing layers
that turn shape data into visible athlete value.

---

## Read Order

1. `docs/FOUNDER_OPERATING_CONTRACT.md`
2. `docs/PRODUCT_MANIFESTO.md`
3. `docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md`
4. `docs/RUN_SHAPE_VISION.md`
5. `docs/specs/LIVING_FINGERPRINT_SPEC.md` (what's built)
6. This spec (what to fix and add)

---

## The Problem

The Living Fingerprint pipeline extracts per-second stream data into
phases, accelerations, and classifications. The engineering works. But
the output is broken in production:

| Athlete | Run | Correct answer | System output |
|---------|-----|---------------|---------------|
| Michael | 7mi easy at 8:30 | "7 miles easy" | 64 phases, cls=None |
| Michael | 6mi progression 8:12→7:15 | "6 miles building from 8:12 to 7:15" | 48 phases, cls=None |
| Michael | 13mi long run at 7:30 | "13 mile long run at 7:30" | 113 phases, cls=long_run |
| Larry | 4mi easy at 14:45 | "4 miles easy" | 87 phases, cls=track_intervals |
| Larry | 2.5mi with 4 strides | "2.5 miles easy with 4 strides" | 54 phases, cls=track_intervals |
| BHL | 18mi long run at 8:50 | "18 mile long run at 8:50" | 63 phases, cls=fartlek |
| BHL | 5mi with 3mi at tempo | "5 miles with 3 at tempo" | 19 phases, cls=fartlek |
| BHL | 5mi with 6 hill repeats | "5 miles with 6 hill repeats" | 23 phases, cls=hill_repeats (correct) |

**Root cause:** The pace profile derivation fails to find the athlete's
actual training zones and falls through to `_derive_profile_from_stream`,
which uses the run's own velocity percentiles as "zones." For a steady
easy run at 8:30/mi, the GPS noise envelope (7:50-9:10) gets carved
into four fake zones. The extractor then classifies GPS noise as
training structure, producing 48-113 micro-phases for runs that should
have 1-3 phases.

**Consequence:** With garbage phases, no classification matches, the
system outputs `None`, and any sentence would be "6 miles (unclassified)"
— worse than Strava's "Morning Run."

This spec fixes the zone model, fixes the phase pipeline, and adds the
sentence generation layer that turns correct shapes into natural
language a runner would text their training partner.

---

## Part 1: The Zone Model

### Current design (broken)

```python
def classify_pace(self, pace_sec_per_mile):
    # Uses midpoints between zones as boundaries
    rep_int = (repetition + interval) / 2
    int_thr = (interval + threshold) / 2
    thr_mar = (threshold + marathon) / 2
    mar_easy = (marathon + easy) / 2
    # Every pace maps to exactly one zone — no gray area
```

The midpoint approach creates continuous coverage: every pace is
"something." This is wrong. When an athlete runs 7:30/mi and their
marathon pace is 6:50 and easy pace is 8:20, that 7:30 is NOT marathon.
It's NOT easy. It's between zones. A good coach would ask "what was
your intention?"

### New design: Discrete bands with gray area

Each training zone is a narrow band (±10 seconds per mile) centered on
the athlete's known pace for that zone. Anything between bands is **gray
area** — effort that doesn't match a declared training purpose.

```python
@dataclass
class ZoneBand:
    name: str           # 'easy', 'marathon', 'threshold', 'interval', 'repetition'
    center_sec: int     # athlete's pace for this zone in sec/mile
    half_width: int     # ±10 sec default

    @property
    def floor(self) -> int:
        return self.center_sec - self.half_width  # faster edge

    @property
    def ceiling(self) -> int:
        return self.center_sec + self.half_width  # slower edge

    def contains(self, pace_sec: float) -> bool:
        return self.floor <= pace_sec <= self.ceiling
```

**Special rule for easy:** Easy has a ceiling but NO floor. There is no
such thing as "too slow" on an easy day — only "too fast." Any pace
slower than the easy ceiling is easy. The band extends to infinity on
the slow side.

**Walking boundary:** Paces slower than 20:00/mi (1200 sec/mi, ~3.0 mph)
are classified as `walking`, not `easy`. This prevents walk breaks,
aid station stops, and warm-up walks from inflating the easy phase or
confusing the classification.

```python
WALKING_THRESHOLD_SEC = 1200  # 20:00/mi = 3.0 mph

def classify_pace(self, pace_sec_per_mile: float) -> str:
    if pace_sec_per_mile <= 0:
        return 'stopped'
    if pace_sec_per_mile >= WALKING_THRESHOLD_SEC:
        return 'walking'

    # Check named zones from fastest to slowest
    for zone in [repetition, interval, threshold, marathon]:
        if zone.contains(pace_sec_per_mile):
            return zone.name

    # Easy has no floor — anything above easy ceiling is easy
    if pace_sec_per_mile >= self.easy_band.floor:
        return 'easy'

    # Between zones = gray area
    return 'gray'
```

### Preventing band overlaps (no overlap resolution needed)

Bands are constructed so they **never overlap.** When two adjacent
zones would overlap (e.g., threshold ±10 and marathon ±10 are only
18 sec apart), the **slower zone's floor (faster edge) is shrunk**
to sit 1 second above the faster zone's ceiling (slower edge).

```python
def build_zone_bands(centers: Dict[str, int], half_width: int = 10) -> List[ZoneBand]:
    """Build non-overlapping zone bands.
    
    Ordered fastest to slowest: rep, interval, threshold, marathon, easy.
    If two bands would overlap, shrink the slower zone's floor
    to sit 1 second above the faster zone's ceiling.
    """
    ordered = ['repetition', 'interval', 'threshold', 'marathon']
    bands = []
    for name in ordered:
        band = ZoneBand(name=name, center_sec=centers[name], half_width=half_width)
        if bands:
            prev = bands[-1]
            if band.floor <= prev.ceiling:
                # Shrink this band's floor to avoid overlap
                band.floor_override = prev.ceiling + 1
        bands.append(band)
    # Easy band — no floor (extends to walking boundary)
    bands.append(ZoneBand(name='easy', center_sec=centers['easy'], half_width=half_width))
    return bands
```

This eliminates the directional context / overlap resolution logic
entirely — it was complexity that only existed because overlaps were
allowed. With guaranteed non-overlapping bands, every pace maps to
exactly one zone or gray area. No ambiguity, no runtime resolution.

### Gray area is a coaching signal

When a run or phase falls in the gray area, the system has three
responsibilities:

1. **Name the pace, not the zone.** The sentence says "at 7:30" instead
   of "at tempo" or "easy." The pace speaks for itself when it doesn't
   fit a named zone.

2. **Identify what it cost.** Compare the next quality session to the
   athlete's baseline for that session type. Was HR elevated? Was pace
   slower than recent sessions? Did the gray zone effort eat into the
   next workout? The system has every activity — it can measure this.

3. **Identify what it gained.** Was this race-specific work (proximity
   to a confirmed race, pace near race pace)? Was it a deliberate
   moderate long run? Or was it a run without clear purpose?

The gray area coaching signal lives in the **coach briefing** and the
**activity detail page**, not in the sentence on the activity list. The
list sentence is clean: "13 miles at 7:30". The detail page adds: "Gray
zone — between your easy (8:20+) and marathon (6:50). Your Thursday
tempo was 6:40 at 155 bpm vs 6:35 at 150 bpm last week."

The system informs. The athlete decides.

---

## Part 2: Phase Detection (Fixed)

### Problem

The current extractor produces 48-113 phases for steady runs because:

1. **Stream-relative fallback creates fake zones.** When the athlete's
   real pace profile isn't found, percentile-based zones from the run's
   own GPS noise distribution are used. Every steady run produces 4
   "zones" from noise.

2. **Micro-phase merging isn't aggressive enough.** Even with the
   MIN_PHASE_DURATION_S = 60 in code, phases as short as 19-20 seconds
   appear in production output. The pace-similarity merge (20 sec/mi
   threshold) re-fragments phases that were merged.

### Fix 1: Pace profile resolution must succeed

The shape extractor must resolve the athlete's real training paces.
The fallback chain:

```
1. AthleteTrainingPaceProfile.paces → pace_profile_from_training_paces()
2. Athlete RPI → pace_profile_from_rpi()
3. FAIL LOUDLY — do NOT fall back to stream-relative
```

**The stream-relative fallback must be removed for phase detection.**
It produces garbage for any steady-effort run. If neither the training
profile nor RPI exists, the shape extractor should:
- Still extract accelerations (velocity spikes are absolute, not zone-relative)
- Set all phases to a single "unzoned" phase with raw pace data
- Set classification to `null`
- Log an honest gap: "No pace profile available for zone classification"

This is suppression over hallucination. An unzoned shape with correct
accelerations is vastly better than 64 fake phases.

### Fix 2: Phase model matches the zone model

With the discrete band + gray area zone model, phase detection becomes:

```
Step 1: Smooth velocity (30s window, as today)
Step 2: Classify each point using discrete bands + gray area
Step 3: Detect transitions (zone changes)
Step 4: Merge — any phase shorter than 60s merges into its neighbor
Step 5: Consolidate — adjacent phases in the SAME zone merge regardless
        of pace difference (they're the same effort)
Step 6: Adjacent gray-area phases with similar pace (within 20 sec/mi)
        merge into one gray-area phase
```

The key change in Step 5: two adjacent "easy" phases should ALWAYS
merge, even if one is 8:20/mi and the other is 8:50/mi. They're both
easy. GPS noise between them doesn't constitute a zone transition.
This is what collapses the 64-phase easy run into 1-2 phases.

### Expected results with correct zones

| Run | Current phases | Expected phases |
|-----|---------------|-----------------|
| 7mi easy at 8:30 | 64 | 1 (easy) |
| 6mi progression 8:12→7:15 | 48 | 3-4 (warmup → easy → gray/marathon) |
| 13mi long run at 7:30 | 113 | 2-3 (warmup → gray → cooldown) |
| 2.5mi with strides | 54 | 1-2 (easy → easy) + 4 accelerations |
| 4mi easy at 14:45 | 87 | 1 (easy) |
| 18mi long run at 8:50 | 63 | 3-5 (warmup → easy/marathon → cooldown) |
| 5mi with 6 hill repeats | 23 | 3-5 (warmup → easy → easy → cooldown) + 6 hill accels |

---

## Part 3: Phase and Acceleration Independence

Phases and accelerations are **two independent layers**, not one
hierarchy.

**Phases** describe the sustained effort zones — the base layer of the
run. What zone was the athlete holding? For how long? Most runs are
1-3 phases:
- Easy run: one easy phase
- Tempo: easy → threshold → easy
- Progression: easy → gray → marathon (building)
- Intervals: alternating work/recovery phases

**Accelerations** are bursts within or on top of phases. They don't
change the phase classification. Strides during an easy run don't make
the run "not easy" — the run is still easy with strides on top.

```
Phase layer:     [────────── easy ──────────][── easy ──]
Accel layer:                                  ^ ^ ^ ^  (strides)
Classification:  "easy run with strides"
```

```
Phase layer:     [── easy ──][── threshold ──][── easy ──]
Accel layer:     (none)
Classification:  "tempo"
```

```
Phase layer:     [────────── easy ──────────]
Accel layer:      ^  ^  ^  ^  ^  ^  (scattered surges)
Classification:  "fartlek"
```

### Hill work is acceleration + elevation, not a phase change

On a hilly route at 14% grade, pace drops to 8:30/mi even though
effort is at threshold. Pace-based zone classification correctly calls
this "easy" by pace. The hill effort is captured as an **acceleration**
with elevation data, not as a phase change.

This matches how a runner describes it: "8 miles easy with 6 hill
repeats." The base effort is easy. The hills are the work, detected
by velocity spikes AND/OR cadence spikes with significant elevation
gain (avg_grade > 4%) during the acceleration.

**Hill work within hill work:** On a hilly course (e.g., Bonita Lakes,
14% grade sections), the athlete is already climbing at 8:30+. Within
that, 10-second bursts at 7:00-8:00 are hill sprints — accelerations
on top of already-hard terrain. The acceleration detector catches the
velocity spike relative to the surrounding phase pace, not relative to
flat-ground easy pace. This means the acceleration baseline should be
the **current phase's average pace**, not the run's overall easy pace.

**Future: Location-based hill recognition.** When the system has enough
history (30+ activities), it can identify recurring hill routes (same
GPS coordinates, same grade profile) and compare hill repeat quality
across sessions: same hill, same grade, different pace/HR over time.
Pure fitness signal. Not in this spec — route matching is a separate
capability.

---

## Part 4: Classification Rules (Updated)

Classification derives from phase + acceleration combination. The
phase count is now expected to be 1-8, not 48-113.

| Classification | Phase signature | Acceleration signature |
|---|---|---|
| `easy_run` | All phases easy (or walking), ≤3 phases | 0-1 accelerations |
| `strides` | Base phases easy or gray | 3-8 end-loaded accels (final 25%), interval/rep zone |
| `fartlek` | Base phases easy/gray | 3+ scattered accels, variable duration |
| `tempo` | Contains 1 threshold phase > 12 min | ≤2 accelerations |
| `threshold_intervals` | 2-5 threshold phases, recovery between | 0-2 accelerations |
| `track_intervals` | 4+ interval/rep phases, similar duration, recovery between | 0 accelerations |
| `progression` | 3+ phases, each ≥15 sec/mi faster than previous, any zones | any |
| `hill_repeats` | Base phases easy/gray | 3+ accels with avg_grade > 4% |
| `long_run` | Duration > 2× athlete's rolling median duration, any zone | any (sub-classify below) |
| `medium_long_run` | Duration > 1.65× athlete's rolling median duration (but < 2×), any zone | any |
| `long_run_with_strides` | long_run + end-loaded accels | — |
| `long_run_with_tempo` | long_run + embedded threshold phase > 10min | — |
| `gray_zone_run` | Primary phase is gray area, no structured work | 0-1 accels |
| `null` | Doesn't match any pattern | — |

**Key changes:**

- **`recovery_run` removed.** A slow easy run is still `easy_run`.
  Runners don't meaningfully distinguish "recovery" from "easy" in
  how they describe runs — "4 miles easy" covers both. The system
  doesn't need to guess intent from HR.

- **`progression` is structural, not zone-dependent.** A progression
  is defined by 3+ phases where each phase is ≥15 sec/mi faster than
  the previous. The final phase does NOT need to reach marathon pace
  or any specific zone. BHL's Feb 16 run (8:30→7:10, dropping through
  threshold) is a progression regardless of where those paces fall
  relative to his zones. This also correctly captures builds from easy
  into gray zone (Michael's 9:20→8:00) without requiring a zone
  boundary crossing.

- **Long run uses duration, not distance.** `Duration > 2× athlete's
  rolling 30-day median duration` identifies genuine long runs. A new
  `medium_long_run` classification at `1.65× median` captures the
  "not quite long but longer than usual" runs that are a distinct
  training stimulus.

- **`gray_zone_run`** explicitly identifies runs where the athlete held
  effort between named zones with no structured work. This triggers
  the coaching layer (Part 6).

**Long run is duration-based, not zone-based.** A 90-minute run is a
long run whether it's at easy pace, gray zone, or marathon pace. The
zone describes intensity; the classification describes the type.

---

## Part 5: Shape Sentences

### The quality bar

The sentence must read like something a runner would text their
training partner. Not like something a system would generate.

**"10 miles with a 20-min tempo at 6:03/mi"** — that's what a human
says. That sentence IS the product.

**"10.3 miles classified as long_run with 6 phases containing threshold
work"** — that's a database talking. Worse than "Morning Run."

### Suppression over hallucination

When the shape extractor classifies with high confidence, the sentence
is magic. When it's uncertain, ambiguous, or the structure is unclear,
**the original activity name is the right answer.** Silence beats a
wrong structural claim.

A wrong sentence destroys trust faster than no sentence builds it.
If the system says "tempo" and the athlete did intervals, trust is
gone instantly. That's worse than Strava showing "Morning Run," because
Strava never claimed to understand.

### Suppression rules

Output the original activity name (suppress the shape sentence) when:

1. **Classification is null** and no dominant phase is clear
2. **Pace profile was unavailable** (unzoned shape)
3. **Anomaly detected** (GPS gaps, unrealistic velocity)
4. **Run is very short** (< 1 mile, < 8 minutes) — not enough data
   for structural claims
5. **Phase count > 8** after all merging — the extractor couldn't
   resolve a clean structure (this is a safety valve)

When suppressing, still store the RunShape data for investigation use.
Only the sentence is suppressed, not the shape.

### Sentence patterns by classification

Each pattern has variables filled from the shape data. Formatting
rules: distances round to nearest 0.5 mi (or whole km), paces format
as M:SS/mi or M:SS/km per athlete preference. All patterns below use
miles; the system respects `athlete.preferred_units`.

---

**easy_run**
```
"{distance} easy"
"{distance} easy at {avg_pace}"
```
Use the shorter form when avg_pace is within the easy band. Add pace
only when it's notable (near the easy ceiling) or the athlete likes
seeing pace.

Examples:
- "5 miles easy"
- "7 miles easy at 8:34"

---

**strides**
```
"{distance} easy with {n} strides"
"{distance} easy with {n} strides (fastest {fastest_accel_pace})"
```
Include fastest pace when strides are at interval/rep zone. Omit if
all strides are at similar pace.

Examples:
- "4 miles easy with 5 strides (fastest 6:02)"
- "7 miles easy with 4 strides"

---

**fartlek**
```
"{distance} with {n} surges"
"{distance} with {n} surges through the middle"
"{distance} fartlek with surges at {avg_accel_pace}"
```
Use "through the middle" when accelerations are clustered in the
middle 50% of the run. Use "surges" not "accelerations."

Examples:
- "6 miles with 8 surges"
- "5 miles fartlek with surges at 7:05"

---

**tempo**
```
"{distance} with {tempo_duration}-min tempo at {tempo_pace}"
"{distance} with {tempo_distance} at tempo ({tempo_pace})"
```
Always include the tempo pace — it's the most important number. Use
duration when it's a time-based effort, distance when it's a
distance-based effort (heuristic: if tempo phase distance rounds to
a clean mile/km value, use distance).

Examples:
- "10 miles with a 20-min tempo at 6:03"
- "8 miles with 3 miles at tempo (6:28)"

---

**threshold_intervals**
```
"{distance} with {n}x{rep_duration} at threshold ({avg_work_pace})"
"{distance} with {n} threshold reps at {avg_work_pace}"
```
Examples:
- "9 miles with 4x8min at threshold (6:30)"
- "7 miles with 3 threshold reps at 6:35"

---

**track_intervals**
```
"{distance} with {n}x{rep_distance} at {avg_work_pace}"
```
Use distance for reps when they round to standard track distances
(200m, 400m, 600m, 800m, 1000m, 1200m, 1600m, mile). Use duration
otherwise.

Examples:
- "9 miles with 5x1000m at 5:48"
- "8 miles with 12x400m at 5:22"
- "7 miles with 6x3min at 6:15"

---

**progression**
```
"{distance} building from {start_pace} to {end_pace}"
```
Always include start and end pace — the progression IS the story.

Examples:
- "8 miles building from 8:12 to 7:15"
- "6 miles building from 9:00 to 7:30"

---

**hill_repeats**
```
"{distance} with {n} hill repeats"
"{distance} easy with {n} hill repeats"
```
Don't include pace for hill repeats — pace on hills is meaningless
without grade context. The effort is captured in HR, not pace.

Examples:
- "5 miles with 6 hill repeats"
- "8 miles easy with 4 hill repeats"

---

**long_run** (duration > 2× rolling median)
```
"{distance} long run"
"{distance} long run at {avg_pace}"
```
Include pace when it's in the gray zone or marathon zone — that's
meaningful information about the intensity of the long run. Omit
pace when it's solidly in easy zone (the athlete knows easy is easy).

Examples:
- "13 miles long run at 7:30"
- "16 mile long run"
- "18 miles at 8:50"

---

**medium_long_run** (duration > 1.65× rolling median, < 2×)
```
"{distance} medium-long"
"{distance} medium-long at {avg_pace}"
```
Examples:
- "10 miles medium-long"
- "11 miles medium-long at 8:15"

---

**long_run_with_strides**
```
"{distance} long run with {n} strides"
```
Examples:
- "14 miles with 6 strides at the end"

---

**long_run_with_tempo**
```
"{distance} long run with {tempo_duration} at tempo ({tempo_pace})"
```
Examples:
- "16 miles with 20 minutes at tempo (6:45)"
- "18 miles with 4 miles at marathon pace (6:50)"

---

**gray_zone_run**
```
"{distance} at {avg_pace}"
```
No zone label. The pace speaks for itself. The coaching layer handles
the "why" question on the detail page and in the briefing.

Examples:
- "6 miles at 7:45"
- "8 miles at 7:30"

---

### Multi-feature hierarchy

When a run has multiple interesting features (strides AND progression),
use this priority order for the sentence:

1. Structured work (tempo, intervals, threshold) — always leads
2. Progression — second priority
3. Accelerations (strides, surges) — third
4. Long run — fourth (modified by 1-3 above)
5. Easy/recovery — default

A long run with strides AND a tempo section → "16 miles with 20-min
tempo (6:45) and 4 strides at the end" — but only if both features are
clear. If ambiguous, use the primary feature only. Simpler is better
than comprehensive.

### The activity list is the product surface

The sentence appears in two places:

1. **Activity list** — replaces "Morning Run" / "Afternoon Run" as the
   activity title (or subtitle below the original name). This is the
   primary surface. The athlete scans their week and sees:

   ```
   Mon:  5 mi easy
   Tue:  8 mi with 4x1mi at 6:15
   Wed:  4 mi recovery
   Thu:  6 mi easy with strides
   Fri:  rest
   Sat:  5 mi with 20-min tempo at 6:45
   Sun:  14 mi long run at 7:30
   ```

   That's a training log that writes itself. The athlete never types
   anything. They look at their week and it's described the way they'd
   describe it to their coach.

   **No platform does this.** This is the screenshot that gets shared —
   not one run, but a whole week that the app understood without being
   told.

2. **Activity detail page** — appears as the structured description
   above the chart. Accompanied by the gray zone coaching context when
   applicable.

---

## Part 6: Gray Zone Intelligence

### When it triggers

Gray zone intelligence activates when:
- A run's primary phase is classified as `gray` (between named zones)
- The run is not a long run (long runs in gray zone get the long_run
  classification with pace shown, but still trigger the coaching layer
  on the detail page)

### What it shows (detail page / coach briefing)

**Format:**
```
Gray zone — {avg_pace}, between your {slower_zone} ({slower_zone_pace}+)
and {faster_zone} ({faster_zone_pace}).
{cost_sentence}
```

**Cost analysis logic:**
```
Look at the next quality session within 48 hours:
- Is there one? (scheduled workout, threshold/interval classification)
- Compare its HR and pace to the athlete's rolling 4-week average for
  that session type
- If HR > avg + 3 bpm at same pace → "Your {day} {session_type} showed
  elevated HR ({actual} vs {baseline} bpm at {pace})"
- If pace > avg + 5 sec/mi at same HR → "Your {day} {session_type}
  pace was {delta} slower than recent sessions"
- If no quality session within 48h → no cost statement
- If next session was normal → "No impact on your {day} {session_type}"
```

**Gain analysis logic:**
```
- Is there a confirmed race within 14 days?
  → "Race-specific: {pace} is {delta} from your {race_distance} goal pace"
- Is this a long run day (by distance)?
  → "Moderate long run — faster than easy, not quite marathon pace"
- Neither?
  → no gain statement (silence is acceptable)
```

### What it does NOT do

- Does NOT say "you ran too fast" or "this was junk miles"
- Does NOT prescribe what the athlete should have done
- Does NOT judge the athlete's choice
- Shows the receipt. The athlete connects the dots.

---

## Part 7: Wiring Into Coaching Surfaces

The shape data is currently extracted and stored on `Activity.run_shape`
but **nothing downstream reads it.** The morning briefing, yesterday's
insight, the coach, the activity list — all blind to shape. This is
the most important part of this spec: the shape sentence must flow into
every surface that talks about an activity.

### Surface 1: Yesterday's Insight (`generate_yesterday_insight`)

**Current state:** Returns "5.0 mi at 8:34." or "HR stayed low (132 avg)."
Zero shape awareness.

**After this spec:** When `shape_sentence` exists on the activity,
it replaces the default distance/pace line. The shape sentence IS the
insight for yesterday's run.

```python
def generate_yesterday_insight(activity: Activity) -> str:
    if activity.shape_sentence:
        # The shape sentence IS the insight
        result = activity.shape_sentence
        # Add HR context only when notable
        if activity.avg_hr and activity.avg_hr > 165:
            result += f" (HR ran high — {activity.avg_hr} avg)"
        return result
    # ... existing fallback for activities without shape data
```

### Surface 2: Home Briefing Context (`_build_rich_intelligence_context`)

**Current state:** Reads N=1 insights, daily intelligence, wellness
trends, PB patterns, block comparison, training story. No shape data
for recent activities.

**After this spec:** Add a new section — "Recent Activity Shapes" —
that gives the coach structural understanding of the last 3-5 activities.

```python
# 7. Recent activity shapes — what the athlete actually did this week
try:
    recent = db.query(Activity).filter(
        Activity.athlete_id == athlete_uuid,
        Activity.shape_sentence.isnot(None),
    ).order_by(Activity.start_time.desc()).limit(5).all()
    if recent:
        lines = []
        for a in recent:
            day = a.start_time.strftime("%a")
            lines.append(f"- {day}: {a.shape_sentence}")
        sections.append(
            "--- This Week's Training (auto-detected from stream data) ---\n"
            + "\n".join(lines)
        )
except Exception as e:
    logger.debug(f"Activity shapes failed for home briefing: {e}")
```

This gives the coach context like:
```
--- This Week's Training (auto-detected from stream data) ---
- Wed: 4 miles easy with 5 strides (fastest 6:02)
- Tue: 6 miles building from 8:12 to 7:15
- Mon: 7 miles easy
- Sun: 13 mile long run at 7:30
- Sat: 5 miles easy at 9:15
```

The coach can now reference the actual training week when speaking.
"Your progression run Tuesday built from 8:12 to 7:15 — the first
time you've touched 7:15 since your injury."

### Surface 3: Coach Briefing (pre-structured paragraph)

For the most recent activity specifically, the coach receives a
pre-structured paragraph, not the raw RunShape JSON. The LLM doesn't
need to know there were 6 phases. It needs to know the workout had a
tempo block and how it compares to history.

**Format for coach context:**
```
This was a {distance} {classification} — {sentence}.
{phase_summary}
{comparison_to_recent}
{gray_zone_note if applicable}
```

**Example:**
```
This was a 10-mile run with a 20-minute threshold block at 6:03/mi
(138 bpm avg). The easy bookends were 8:15-8:30 at 118-125 bpm.
4 months ago, 6:03/mi cost 128 bpm — today it cost 138 bpm
(post-injury rebuild).
```

The coach can then speak naturally about the workout without parsing
JSON or inventing structure. The pre-structured paragraph ensures the
coach's output is grounded in real shape data.

### Surface 4: Activity List API

The activity list endpoint must return `shape_sentence` for each
activity. The frontend renders it as the primary descriptor (or
subtitle below the athlete's original name).

```
GET /v1/activities → each activity includes:
{
    "name": "Lauderdale County Running",     // original
    "shape_sentence": "7 miles easy",         // new — null if suppressed
    "distance_m": 11265,
    "duration_s": 3420,
    ...
}
```

The frontend shows `shape_sentence` when present, falls back to `name`.

### Surface 5: Activity Detail Page

The activity detail page shows the shape sentence prominently above
the chart, replacing or supplementing the generic title. When gray
zone intelligence applies, the cost/gain analysis appears below the
sentence.

### What this means for post-sync timing

Shape extraction already runs in `post_sync_processing_task` (step 5).
The sentence generation runs immediately after shape extraction —
same task, same pipeline. The sentence is stored on the Activity
before the home briefing refresh is triggered (step 6 in the current
pipeline). So by the time the coach generates the briefing, the
shape sentence is available.

```
post_sync_processing_task:
  1. Derived signals
  2. Strava best efforts
  3. Generate insights
  4. Heat adjustment
  5. Shape extraction → sentence generation (NEW: generate sentence here)
  6. Finding persistence
  7. Home briefing refresh (reads shape_sentence)
```

---

## Part 8: Implementation Sequence

### Phase 1: Fix the zone model (MUST ship first)

1. **Replace `classify_pace` with discrete band model.** ±10 sec bands,
   easy no floor, gray area between zones, walking at 20:00+/mi.
2. **Build non-overlapping bands.** When bands would overlap, shrink the
   slower zone's floor to 1 sec above the faster zone's ceiling.
   No overlap resolution logic needed — it's prevented at construction.
3. **Remove stream-relative fallback for phase detection.** If no pace
   profile exists, produce a single unzoned phase. Log honest gap.
4. **Fix pace profile resolution.** Verify that
   `pace_profile_from_training_paces` and `pace_profile_from_rpi`
   actually resolve for Michael, Larry, and BHL. Debug why they fail.
5. **Same-zone consolidation.** Adjacent phases in the same zone ALWAYS
   merge, regardless of pace difference within the zone.
6. **Backfill all existing run_shape data** with corrected zone model.
7. **Verify:** Michael's 7mi easy → 1-2 phases. Larry's 4mi easy →
   1-2 phases. BHL's 18mi long run → 3-5 phases.

### Phase 2: Shape sentences

1. **Implement sentence generator.** Function that takes a RunShape +
   PaceProfile + athlete preferences and returns a string.
2. **Add suppression rules.** When classification is null/unzoned/
   anomaly/short/too-many-phases → return None (use original name).
3. **Store sentence on Activity.** New column `shape_sentence`
   (Text, nullable). Populated during shape extraction.
4. **Surface in API.** Activity list and detail endpoints include
   `shape_sentence` when present.
5. **Surface in frontend.** Activity list shows shape_sentence as
   subtitle or replacement for generic titles. Activity detail shows
   it as the structural description.

### Phase 3: Gray zone intelligence

1. **Implement cost analysis.** Compare next quality session to
   rolling baseline.
2. **Implement gain analysis.** Race proximity, long run context.
3. **Wire into coach briefing.** Pre-structured paragraph per activity.
4. **Wire into activity detail page.** Gray zone context section.

### Phase 4: Coach briefing integration

1. **Generate pre-structured paragraph per activity.**
2. **Pass to coach context instead of raw JSON.**
3. **Verify coach output quality** with real activities.

---

## Verification: The 14-Activity Test

After Phase 1 + 2, re-run shape extraction for these 14 activities
and verify the sentence output matches or closely approximates:

| Date | Athlete | Expected sentence |
|------|---------|-------------------|
| Mar 05 | Michael | "4 miles with 5 strides (fastest 6:02)" |
| Mar 04 | Michael | "6 miles building from 8:12 to 7:15" |
| Mar 03 | Michael | "7 miles easy" |
| Mar 01 | Michael | "5 miles easy at 9:15" |
| Feb 28 | Michael | "13 mile long run at 7:30" |
| Feb 27 | Michael | "6 miles building from 9:20 to 8:00" |
| Mar 05 | Larry | "1 mile easy" |
| Mar 03 | Larry | "2.5 miles easy with 4 strides" |
| Mar 01 | Larry | "4 miles easy" |
| Feb 28 | Larry | "2 miles easy" |
| Mar 05 | BHL | "5 miles with 3 at tempo (7:30-8:00)" |
| Feb 28 | BHL | "18 mile long run at 8:50" |
| Feb 18 | BHL | "5 miles with 6 hill repeats" |
| Feb 16 | BHL | "6 miles building from 8:30 to 7:10" |

If any sentence is wrong, the builder should suppress it (output the
original name) and log why. Wrong is always worse than generic.

---

## Appendix A: Zone Band Examples

### Michael (competitive masters, ~19:00 5K)
| Zone | Center | Band (non-overlapping) |
|------|--------|------|
| Easy | 8:30/mi (510s) | 8:20+ (no floor, walking at 20:00+) |
| Marathon | 6:50/mi (410s) | 6:43 - 7:00 |
| Threshold | 6:32/mi (392s) | 6:22 - 6:42 |
| Interval | 6:00/mi (360s) | 5:50 - 6:10 |
| Repetition | 5:30/mi (330s) | 5:20 - 5:40 |
| Gray areas | — | 7:00 - 8:20, 6:10 - 6:22, 5:40 - 5:50 |

Marathon floor shrunk from 6:40 to 6:43 to avoid overlap with
threshold ceiling (6:42). The big gray area (7:00 - 8:20) is where
long run pace lives. 7:30 for Michael is not easy and not marathon —
it's moderate effort the system names by pace, not by zone.

### Larry (79-year-old masters, ~12:00/mi easy)
| Zone | Center | Band (non-overlapping) |
|------|--------|------|
| Easy | 13:00/mi (780s) | 12:50+ (no floor, walking at 20:00+) |
| Marathon | 12:00/mi (720s) | 11:50 - 12:10 |
| Threshold | 11:00/mi (660s) | 10:50 - 11:10 |
| Interval | 10:00/mi (600s) | 9:50 - 10:10 |
| Repetition | 9:00/mi (540s) | 8:50 - 9:10 |

No overlaps — Larry's zones are 1+ minute apart. His strides at
9:14-10:30 are solidly in the interval/repetition zone.

### BHL (returning from injury, ~8:30 easy)
| Zone | Center | Band (non-overlapping) |
|------|--------|------|
| Easy | 9:00/mi (540s) | 8:50+ (no floor, walking at 20:00+) |
| Marathon | 8:00/mi (480s) | 7:50 - 8:10 |
| Threshold | 7:15/mi (435s) | 7:05 - 7:25 |
| Interval | 6:30/mi (390s) | 6:20 - 6:40 |
| Repetition | 5:50/mi (350s) | 5:40 - 6:00 |

No overlaps — BHL's zones are 25+ seconds apart.

---

## Appendix B: What This Replaces

This spec supersedes the following sections of
`docs/specs/LIVING_FINGERPRINT_SPEC.md`:

- **Phase Detection Algorithm** (Steps 1-7) — replaced by Part 2
- **Zone classification** — replaced by Part 1
- **Classification table** — replaced by Part 4
- **Overlap resolution logic** — eliminated entirely; bands are
  constructed non-overlapping (H1), so no runtime resolution needed

The acceleration detection (dual-channel velocity + cadence) is
**unchanged**. It works correctly in production. The phase layer is
what's broken; the acceleration layer is what's working.

The investigation registry, finding persistence, weather normalization,
and Celery integration from the Living Fingerprint spec are all
**unchanged** and remain deployed.

---

## Appendix C: Review Resolution Log

Items resolved during codex review, incorporated into spec:

| ID | Resolution | Spec section updated |
|----|-----------|---------------------|
| H1 | Prevent band overlaps by shrinking slower zone's floor | Part 1 (band construction), Appendix A |
| H2 | Progression is structural: 3+ phases, ≥15 sec/mi each step, no zone requirement | Part 4 (classification table) |
| H3 | BHL Feb 16 reclassified as progression (8:30→7:10) | Verification table |
| M2 | `recovery_run` removed — `easy_run` covers all easy/recovery runs | Part 4, Part 5 (sentence patterns) |
| M3 | Long run = 2× rolling median duration; medium-long = 1.65× | Part 4 (classification table) |
| M4 | Walking boundary at 20:00/mi (1200 sec/mi, 3.0 mph) | Part 1 (classify_pace) |
| L1 | Overlap resolution logic removed (dead code after H1) | Part 1, Appendix B |
