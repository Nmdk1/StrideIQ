# Campaign Detection & Data Integrity — Phase 1C Builder Spec

**Date:** March 4, 2026
**Status:** Ready to build
**Depends on:** Phase 1A + 1B complete (Gate C passed)

---

## Before You Build

Read these documents in order:

1. **`docs/FOUNDER_OPERATING_CONTRACT.md`** — Non-negotiable.
2. **`docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md`** — How every screen
   should feel.
3. **`docs/specs/RACING_FINGERPRINT_AND_PROGRESS_STATE_MACHINE_SPEC.md`**
   — The product design. The five states. The sentence is the product.
4. **`docs/specs/RACING_FINGERPRINT_PHASE1_BUILD_SPEC.md`** — What was
   built in Phase 1. Reference for existing code, models, and tests.

---

## Why This Spec Exists

You built Phase 1 exceptionally. The pipeline, the curation flow, the
pattern extraction, the quality gate — all well-engineered, all
working. Gate C passed. Three findings validated by the founder.

Then we looked deeper.

The founder's real training story is a 6-month campaign to rebuild
aerobic durability: 53 long runs from April to November 2025, including
15-mile weekday runs starting in September. That campaign produced a
7-minute half marathon PB (1:27:14, run 4 days after a femur fracture)
and a sub-40 10K (39:39, run limping, last run before forced shutdown).

The system's finding was: "your best races had 16-mile long runs vs
14-mile." The founder's response: "pretty fucking lame."

He's right. The finding is statistically true and completely misses the
story. Three specific architectural problems caused this:

**1. Fixed lookback windows can't see campaigns.** The block signature
uses 8-18 weeks depending on distance. The founder's marathon prep
started in April — 7 months before the target race. The 18-week window
captures the tail end, not the build itself.

**2. The system can't distinguish taper from injury.** A 5-week volume
decline before a race could be strategic rest or a broken femur. The
founder's "long taper" before weaker races was actually injury. The
finding "short taper works, long taper doesn't" is true but the
causal explanation is wrong.

**3. Data integrity problems corrupted the analysis.**
- 3 of the founder's most important races (Nov 29 half, Dec 13 10K,
  Sep 5K) were in the system but not confirmed — Tier 1 races stayed
  `user_confirmed = None` instead of auto-confirming
- 4 duplicate PerformanceEvents exist (same race, Garmin + Strava
  versions both confirmed separately)
- GPS times differ from chip times (1:27:40 GPS vs 1:27:14 chip) with
  no way to record the actual result

**The real story the system should tell:**

The founder PBs every race when healthy. After a deliberate decision
in May 2025 to build aerobic durability, they did long runs almost
every weekend and many 15-mile weekday runs for 6 months. The PB
progression accelerated: 5K from 20:42 to ~18:53, half marathon from
1:34:08 to 1:27:14, 10K from 41:12 to 39:39. The campaign was
interrupted by a femur fracture on November 25th, but the fitness
was so deep that the founder still PB'd the half 4 days later and
the 10K 2 weeks later while limping.

That's the finding worth saying. "16 vs 14 miles" is not.

This spec fixes the data, builds campaign detection, and re-runs
pattern extraction to produce findings that match reality.

---

## Ground Truth: The Founder's Verified Race History

This is the authoritative race list, verified by the founder during
this session. Build and validate against this. Chip times are the
actual result; GPS times are stored for reference.

| Date | Distance | GPS Time | Chip Time | Pace/mi | Context |
|------|----------|----------|-----------|---------|---------|
| 2024-09-02 | 5K | 20:42 | — | 6:37 | Comeback race |
| 2024-09-14 | 5K | 21:05 | — | 6:48 | |
| 2024-10-12 | 5K | 21:26 | — | 6:43 | |
| 2024-11-16 | 5K | 19:58 | — | 6:26 | **PB** — broke 20 min |
| 2024-11-30 | Half | 1:34:08 | — | 7:09 | Stennis, 1st Masters. **PB** |
| 2025-04-12 | 10K | 41:12 | — | 6:36 | Gulf Coast, 3rd overall. **PB** |
| 2025-04-18 | Mile | 5:44 | — | 5:34 | Threefoot, 1st place. **PB** |
| 2025-04-26 | 5K | 19:30 | — | 6:17 | **PB** |
| 2025-05-03 | 10K | 43:12 | 41:27 | ~6:41 | Chip time 41:27 |
| 2025-06-14 | 5K | 20:03 | — | 6:25 | Pascagoula, 1st Grandmaster |
| 2025-09-?? | 5K | 19:01* | ~18:53 | ~6:05 | **PB** — *GPS may be short |
| 2025-11-29 | Half | 1:27:40 | 1:27:14 | 6:39 | **PB** — 4 days post femur fracture. 7-min PB |
| 2025-12-13 | 10K | 39:39 | — | 6:18 | **PB** — sub-40. Limping. Last run before shutdown |

**Key dates:**
- Bone stress fracture: November 25, 2025
- Long run campaign start: April 2025
- Weekday 15-miler escalation: September 2025
- Return to pain-free running: late February 2026

**PB progression pattern:** When healthy and training consistently,
the founder PBs every race. Improvement rate accelerated after the
November 2024 sub-20 5K. The 6-month campaign (Apr-Nov 2025)
produced the steepest gains.

**Starting data state (as of this spec):**
- 60 total PerformanceEvents in the database
- 14 with `user_confirmed = True` (includes 4 duplicate pairs from
  Garmin+Strava — so only ~10 distinct races confirmed)
- 3 with `user_confirmed = None` (including the Nov 29 half and
  Dec 13 10K — Strava-tagged but never explicitly confirmed)
- 43 with `user_confirmed = False` (rejected by founder during
  curation)
- The 1B extraction ran when only 1 event was confirmed (the
  Threefoot Mile). The founder then confirmed more races through
  the curation flow. Re-extraction with ~17 confirmed events
  produced the 3 findings that passed Gate C2.

After DI-1 and DI-2, the expected state is ~13 distinct confirmed
races (no duplicates, Strava-tagged races auto-confirmed).

---

## Document Structure

```
Data Integrity (DI-1 to DI-3)  ──[GATE E]──→  Campaign Detection (CD-1 to CD-3)  ──[GATE F]──→  Revised Extraction  ──[GATE G]──→  STOP
```

---

## Data Integrity Fixes

**DI-1 must run before DI-2.** Auto-confirming Tier 1 events first
will surface duplicate pairs that the dedup pass then resolves.

### DI-1: Auto-confirm Tier 1 races

**Problem:** PerformanceEvents detected via `strava_tag` or with
`detection_confidence >= 0.7` show in Tier 1 ("Races we found") but
have `user_confirmed = None`. The strip pin fix (commit `45b8a8c`)
changed the filter to `user_confirmed == True`, making these races
invisible to analysis despite being presented to the athlete as
confirmed.

**Fix:** In `populate_performance_events()`, set `user_confirmed = True`
for Strava-tagged races and high-confidence detections. These are
pre-confirmed — the athlete can reject them, but they shouldn't have
to explicitly confirm what the system already presented as found.

Update the pipeline code at the detection source assignment:
- `strava_tag` (workout_type == 3): `user_confirmed = True`
- Algorithm confidence >= 0.7: `user_confirmed = True`
- Algorithm confidence 0.3-0.7: `user_confirmed = None` (candidate)

**Retroactive fix:** Update existing PerformanceEvents:
```sql
UPDATE performance_event
SET user_confirmed = true
WHERE detection_source = 'strava_tag'
  AND user_confirmed IS NULL;

UPDATE performance_event
SET user_confirmed = true
WHERE detection_confidence >= 0.7
  AND detection_source = 'algorithm'
  AND user_confirmed IS NULL;
```

Run this AFTER confirming it doesn't auto-confirm events the founder
already rejected (`user_confirmed = False`).

**Verification:**
```bash
# Count should increase from 14 to ~17+ for the founder
docker exec strideiq_api python -c "
from core.database import SessionLocal
from models import Athlete, PerformanceEvent
db = SessionLocal()
a = db.query(Athlete).filter(Athlete.email=='mbshaf@gmail.com').first()
confirmed = db.query(PerformanceEvent).filter(
    PerformanceEvent.athlete_id == a.id,
    PerformanceEvent.user_confirmed == True,
).count()
print(f'Confirmed PerformanceEvents: {confirmed}')
db.close()
"
```

---

### DI-2: Deduplicate PerformanceEvents

**Problem:** The founder has 4 duplicate PerformanceEvent pairs — same
race on the same date, both the Garmin and Strava activity versions
confirmed separately. Sep 2 5K, Sep 14 5K, Apr 12 10K, Jun 14 5K all
have two confirmed events each. This doubles their weight in pattern
extraction.

**Root cause:** The `add-race` endpoint creates a PerformanceEvent
without checking if one already exists for the same athlete + date +
distance category. The pipeline's `populate_performance_events()`
checks `existing_event_activity_ids` but that's per-activity, not
per-race. Two different activities (Garmin + Strava) for the same
race produce two events.

**Fix:**
1. Add a uniqueness check to `add-race` and `confirm-race`: before
   creating or confirming, check if a confirmed PerformanceEvent
   already exists for this athlete within ±2 hours and ±10% distance.
   If so, keep the one with richer data (prefer named activity over
   unnamed, prefer the one with HR data).

2. Add a dedup pass to `populate_performance_events()`: after creating
   all events, scan for duplicate pairs (same athlete, same date,
   same distance category) and mark the secondary as
   `user_confirmed = False` with a note in detection_source.

3. Retroactive cleanup for the founder's account:
   For each duplicate pair, keep the PerformanceEvent linked to the
   activity with the richer data (name, HR). Delete or reject the
   duplicate.

**Verification:**
```bash
# No duplicate pairs should exist
docker exec strideiq_api python -c "
from core.database import SessionLocal
from models import Athlete, PerformanceEvent
from collections import Counter
db = SessionLocal()
a = db.query(Athlete).filter(Athlete.email=='mbshaf@gmail.com').first()
events = db.query(PerformanceEvent).filter(
    PerformanceEvent.athlete_id == a.id,
    PerformanceEvent.user_confirmed == True,
).all()
date_dist = Counter((e.event_date, e.distance_category) for e in events)
dupes = {k: v for k, v in date_dist.items() if v > 1}
print(f'Confirmed events: {len(events)}')
print(f'Duplicate pairs: {len(dupes)}')
for k, v in dupes.items():
    print(f'  {k[0]} {k[1]}: {v} events')
db.close()
"
```

**Expected:** 0 duplicate pairs.

---

### DI-3: Chip time support

**Problem:** GPS-recorded time and official chip time differ. The
founder's half marathon GPS says 1:27:40, chip says 1:27:14. A 5K
shows 19:01 because the watch was stopped late, chip was ~18:53.
The system uses GPS time for RPI, PB tracking, and analysis. This
produces slightly wrong performance numbers and misses the actual
achievement.

**Fix:** Add `chip_time_seconds` (nullable Integer) to the
`PerformanceEvent` model. When present, use it instead of
`time_seconds` for:
- RPI calculation
- PB determination
- Pace display
- Pattern extraction comparisons

Add to the race curation API:
- `POST /v1/fingerprint/confirm-race/{event_id}` accepts optional
  `chip_time_seconds` in the body
- `POST /v1/fingerprint/add-race/{activity_id}` accepts optional
  `chip_time_seconds` in the body

Frontend: when confirming a race, show an optional "Chip time" input
field. Format: HH:MM:SS or MM:SS. The athlete can skip it (GPS time
is used) or enter the official result.

**Migration:** `phase1c_di3_add_chip_time.py` — add nullable
`chip_time_seconds` column to `performance_event`.

**Helper property on PerformanceEvent:**
```python
@property
def effective_time_seconds(self) -> int:
    """Chip time if available, otherwise GPS time."""
    return self.chip_time_seconds or self.time_seconds
```

Use `effective_time_seconds` everywhere the old `time_seconds` was
used for analysis. `time_seconds` (GPS) is always stored for reference.

---

### ═══════════════════════════════════════════════════════
### GATE E: Data Integrity Complete
### ═══════════════════════════════════════════════════════

**All conditions must be true:**

**E1.** Founder's confirmed PerformanceEvents include:
- Nov 29 2025 half marathon (1:27:40 GPS / 1:27:14 chip)
- Dec 13 2025 10K (39:39)
- All previously confirmed races
- No duplicate pairs

**E2.** PB progression is correct. Run this and verify the chain
matches reality:
```bash
docker exec strideiq_api python -c "
from core.database import SessionLocal
from models import Athlete, PerformanceEvent
db = SessionLocal()
a = db.query(Athlete).filter(Athlete.email=='mbshaf@gmail.com').first()
events = db.query(PerformanceEvent).filter(
    PerformanceEvent.athlete_id == a.id,
    PerformanceEvent.user_confirmed == True,
).order_by(PerformanceEvent.event_date).all()
pbs = {}
for ev in events:
    t = ev.chip_time_seconds or ev.time_seconds
    cat = ev.distance_category
    is_pb = cat not in pbs or t < pbs[cat]
    if is_pb:
        pbs[cat] = t
    m, s = divmod(t, 60)
    h, m = divmod(m, 60)
    ts = f'{h}:{m:02d}:{s:02d}' if h else f'{m}:{s:02d}'
    pb = ' ** PB **' if is_pb else ''
    print(f'{ev.event_date} | {ev.distance_category:15s} | {ts:>9s} | {ev.detection_source:14s}{pb}')
db.close()
"
```

**E3.** No confirmed PerformanceEvents linked to duplicate activities
(`is_duplicate = True`).

**E4.** All DI tests pass.

---

## Campaign Detection

### CD-1: Inflection Point Detection

**New file:** `services/campaign_detection.py`

The core capability: given an athlete's full activity history, find
the dates where sustained training volume shifted to a new level.

```python
@dataclass
class InflectionPoint:
    date: date
    type: str  # 'step_up', 'step_down', 'disruption'
    before_avg_weekly_km: float
    after_avg_weekly_km: float
    change_pct: float
    sustained_weeks: int  # how many weeks the new level held


def detect_inflection_points(
    athlete_id: UUID,
    db: Session,
    min_change_pct: float = 20.0,
    min_sustained_weeks: int = 4,
) -> List[InflectionPoint]:
    """
    Find dates where weekly volume shifted significantly and held.

    Algorithm:
    1. Compute weekly total volume (km) for every week in the
       athlete's history. Exclude duplicate activities.
    2. Compute a rolling 4-week average.
    3. Find dates where the 4-week average increased or decreased
       by >= min_change_pct compared to the previous 4-week average,
       AND the new level held for >= min_sustained_weeks.
    4. Classify each inflection:
       - step_up: volume increased and held (new training phase)
       - step_down: volume decreased gradually (planned reduction)
       - disruption: volume dropped to near-zero (< 25% of prior
         average) within 1 week (injury/illness signal)

    The founder's data should show:
    - step_up in April 2025 (long run campaign begins)
    - step_up in September 2025 (weekday 15-milers added)
    - disruption in late November 2025 (femur fracture)
    """
```

**Key design decisions:**
- Use 4-week rolling average, not raw weekly volume. Single recovery
  weeks shouldn't trigger false inflection points.
- `min_change_pct = 20.0` is a starting threshold. Tune after
  validating against the founder's data. If it misses the September
  escalation (weekday 15-milers), lower the threshold or add a
  secondary signal based on training frequency, not just volume.
- Disruption detection is separate from step_down. A disruption is
  sudden (volume cliff in 1 week). A step_down is gradual (planned
  taper or deload). The system must distinguish these.

---

### CD-2: Campaign Construction

```python
@dataclass
class TrainingCampaign:
    athlete_id: UUID
    start_date: date  # inflection point (step_up) that began it
    end_date: date  # race day, disruption, or next campaign start
    end_reason: str  # 'race', 'disruption', 'new_campaign', 'ongoing'
    phases: List[CampaignPhase]
    linked_races: List[UUID]  # PerformanceEvent IDs within this campaign
    total_weeks: int
    peak_weekly_volume_km: float
    avg_weekly_volume_km: float


@dataclass
class CampaignPhase:
    name: str  # 'base_building', 'escalation', 'race_specific',
               # 'taper', 'disrupted'
    start_date: date
    end_date: date
    weeks: int
    avg_volume_km: float
    intensity_distribution: dict  # easy/moderate/hard proportions


def build_campaigns(
    athlete_id: UUID,
    inflection_points: List[InflectionPoint],
    events: List[PerformanceEvent],
    db: Session,
) -> List[TrainingCampaign]:
    """
    Construct training campaigns from inflection points and races.

    A campaign starts at a step_up inflection point and ends at:
    - A disruption (injury)
    - A race (the campaign produced a race)
    - The next step_up (new campaign began)
    - Today (ongoing campaign)

    Multiple races can exist within one campaign (e.g., tune-up
    races before an A race). All are linked to the campaign.

    Phase detection within a campaign:
    - base_building: volume increasing, intensity mostly easy
    - escalation: volume stable or increasing, intensity shifting
      toward moderate/hard, or training frequency increasing
    - race_specific: volume near peak, quality sessions increase
    - taper: volume decreasing (planned — gradual, not a cliff)
    - disrupted: volume cliff (injury/illness)

    The founder's 2025 data should produce one campaign:
    - Start: April 2025 (step_up)
    - Phases: base_building (Apr-Aug), escalation (Sep-Oct),
      race_specific (Oct-Nov)
    - End: November 25 (disruption — femur fracture)
    - Linked races: Sep 5K, Nov 29 half, Dec 13 10K
    - The Nov 29 half and Dec 13 10K are AFTER the disruption —
      they were raced on residual fitness. The campaign ended
      but the fitness lingered.
    """
```

**Races after disruption:** Some races happen after a campaign ends
because the athlete still has fitness. The Nov 29 half (4 days post-
fracture) and Dec 13 10K (limping) are examples. These races should
be linked to the campaign that produced the fitness, not treated as
a separate block. Tag them as `raced_on_residual_fitness = True`.

**Cutoff: 4 weeks.** Only link races within 4 weeks of the disruption
date to the preceding campaign. Beyond 4 weeks, residual fitness has
decayed enough that the link is misleading. Races beyond the cutoff
are unlinked (no campaign) unless a new campaign has started.

**Storage:** Add `campaign_data` (JSONB, nullable) to the
`PerformanceEvent` model. Contains the campaign summary for this
race — start date, total weeks, phases, peak volume. This replaces
the fixed-window `block_signature` as the primary analysis input.
Keep `block_signature` for backward compatibility.

**Migration:** `phase1c_cd2_add_campaign_data.py`

---

### CD-3: Disruption Classification

```python
def classify_disruption(
    athlete_id: UUID,
    disruption_date: date,
    db: Session,
) -> dict:
    """
    When a disruption is detected, determine what happened.

    Signals:
    - Volume before vs after (how severe was the drop?)
    - Duration of zero/near-zero volume (how long was the break?)
    - Return pattern (gradual rebuild vs sudden return)
    - Cross-reference with injury_history on Athlete model if available

    Returns:
    {
        'type': 'injury' | 'illness' | 'life_event' | 'unknown',
        'severity': 'complete_stop' | 'major_reduction' | 'moderate_reduction',
        'duration_weeks': int,
        'volume_before_km': float,
        'volume_during_km': float,
        'volume_after_km': float,
        'recovery_pattern': 'gradual' | 'sudden' | 'not_yet_recovered',
    }

    For the founder's November 2025 disruption:
    - type: injury (complete stop)
    - severity: complete_stop
    - duration_weeks: ~12+ (still recovering as of March 2026)
    - volume_before: ~70 km/week
    - volume_during: ~0
    - recovery_pattern: not_yet_recovered (or gradual if recent
      return shows in data)
    """
```

---

### ═══════════════════════════════════════════════════════
### GATE F: Campaign Detection Complete
### ═══════════════════════════════════════════════════════

**F1.** All campaign detection tests pass.

**F2.** Founder's campaign detection produces correct results:
```bash
docker exec strideiq_api python -c "
from core.database import SessionLocal
from models import Athlete
from services.campaign_detection import detect_inflection_points, build_campaigns
from models import PerformanceEvent
db = SessionLocal()
a = db.query(Athlete).filter(Athlete.email=='mbshaf@gmail.com').first()
ips = detect_inflection_points(a.id, db)
print('Inflection points:')
for ip in ips:
    print(f'  {ip.date} | {ip.type:12s} | {ip.before_avg_weekly_km:.0f} -> {ip.after_avg_weekly_km:.0f} km/wk ({ip.change_pct:+.0f}%) | held {ip.sustained_weeks}w')
events = db.query(PerformanceEvent).filter(
    PerformanceEvent.athlete_id == a.id,
    PerformanceEvent.user_confirmed == True,
).all()
campaigns = build_campaigns(a.id, ips, events, db)
print(f'\nCampaigns: {len(campaigns)}')
for c in campaigns:
    print(f'  {c.start_date} to {c.end_date} ({c.total_weeks}w) — ended: {c.end_reason}')
    print(f'    Peak vol: {c.peak_weekly_volume_km:.0f} km/wk | Avg: {c.avg_weekly_volume_km:.0f} km/wk')
    print(f'    Phases: {", ".join(p.name for p in c.phases)}')
    print(f'    Linked races: {len(c.linked_races)}')
db.close()
"
```

**Expected for the founder:**
- Inflection points include: step_up ~April 2025, step_up ~September
  2025 (weekday long runs), disruption ~November 25 2025
- At least one campaign spanning April-November 2025
- Campaign links to the Sep 5K, Nov 29 half, Dec 13 10K
- Disruption classified as injury/complete_stop

**F3.** Campaign data stored on PerformanceEvents for all confirmed
races.

---

## Revised Pattern Extraction

### RE-1: Campaign-Level Findings

**Modify:** `services/fingerprint_analysis.py`

Replace the fixed-window block signature analysis with campaign-level
analysis. The existing four layers remain but operate on campaigns
instead of windows:

**Layer 1 (PB Distribution):** Unchanged — this compares race-day
performance to training. Not dependent on block windows.

**Layer 2 (Campaign Comparison):** Instead of comparing 8-week block
signatures, compare full campaigns. Sort races by performance. Split
into top half vs bottom half. For each campaign dimension (total weeks,
peak volume, phase structure, escalation presence), compute effect size.

The finding should capture what's different about the FULL preparation,
not just the final weeks. For the founder: the best races came from
campaigns with 20+ weeks of sustained long run volume, including
weekday long runs in the later phases. The weakest races came from
short campaigns or campaigns interrupted early.

**Layer 3 (Tune-up Pattern):** Unchanged — tune-up to A-race
relationship is not dependent on block windows.

**Layer 4 (Fitness-Relative):** Still gated on 8+ confirmed races
with the CTL→RPI model. When active, operates on campaign-level data.

**New Layer 5: Trajectory Analysis.**

```python
def _layer5_trajectory(
    events: List[PerformanceEvent],
) -> List[FingerprintFindingResult]:
    """
    Layer 5: Performance Trajectory.

    Analyze the athlete's performance trajectory across all races
    at each distance. Detect:
    - Continuous improvement (PB every race when healthy)
    - Improvement rate (how fast are they getting faster?)
    - Acceleration points (when did improvement rate increase?)
    - Disruption impact (how much did injuries set them back?)

    For the founder: "When healthy, you PB every race. Your
    improvement rate accelerated after November 2024. The 6-month
    long run campaign from April-November 2025 produced your
    steepest gains — 7 minutes off your half marathon, sub-40 10K."

    Minimum: 4 races at the same distance, or 6 races total across
    distances with RPI normalization.
    """
```

### RE-2: Narrative Quality

Every finding sentence must pass this test: would the founder say
"that's lame" or "that's true"?

Guidelines:
- Capture the SCOPE of what happened, not just the statistical
  difference. "6 months of sustained long run volume" not "16 vs
  14 mile long runs."
- Name the phases when they exist: "base building," "escalation,"
  "race-specific." These are terms the athlete recognizes.
- Acknowledge disruptions explicitly. "Your campaign was interrupted
  by injury" not "your taper was 5 weeks."
- Trajectory findings should convey momentum: "every race faster
  than the last" not "average improvement of 2.3%."
- Reference specific races when the sample is small enough that
  each one matters.

---

### ═══════════════════════════════════════════════════════
### GATE G: Revised Extraction Complete
### ═══════════════════════════════════════════════════════

**G1.** All revised extraction tests pass.

**G2.** Run extraction on founder's account. Paste full output.
Findings must reference campaigns, not fixed windows. At least one
finding must capture the 6-month long run campaign arc.

**G3. Founder validation (human gate).** Present findings to the
founder. The bar is higher than Gate C2. The founder already rejected
"16 vs 14 miles" as lame. The new findings must make the founder say
"yes, that's what actually happened."

**If the founder says the findings are still lame:** Go deeper. Look
at the data again. The trajectory is in there — 53 long runs, PBs
on consecutive races, a campaign cut short by injury. If the system
can't articulate that, the analysis is still too shallow.

**Gate G requires founder review.** Builder presents findings and
waits for the founder's explicit approval before proceeding to
Phase 2. Do not self-evaluate. Do not infer adequacy from test
results. Stop, surface the findings to the founder, and wait.
The founder is the only person who can evaluate whether the system
found the real story.

**After Gate G passes: STOP.** Phase 2 surfaces begin under a
separate spec, with findings worth displaying.

---

## Tests

**File:** `tests/test_campaign_detection.py`

```python
class TestInflectionPointDetection:
    def test_finds_volume_step_up(self):
        """20%+ sustained volume increase → step_up inflection."""

    def test_finds_disruption(self):
        """Volume cliff to near-zero in 1 week → disruption."""

    def test_distinguishes_taper_from_disruption(self):
        """Gradual 3-week decline → step_down, not disruption."""

    def test_ignores_single_week_spike(self):
        """One high-volume week followed by return to baseline →
        not an inflection point."""

    def test_minimum_sustained_weeks(self):
        """Volume increase that reverts after 2 weeks → not detected
        with min_sustained_weeks=4."""

    def test_finds_multiple_inflections(self):
        """Base building step_up + later escalation step_up +
        disruption → 3 inflection points."""


class TestCampaignConstruction:
    def test_campaign_spans_step_up_to_race(self):
        """Step_up inflection → race 20 weeks later → one campaign."""

    def test_campaign_ends_at_disruption(self):
        """Step_up → disruption before race → campaign ended by
        disruption, not race."""

    def test_races_after_disruption_linked(self):
        """Race 4 days after disruption → linked to campaign,
        tagged as residual fitness."""

    def test_multiple_races_in_campaign(self):
        """Tune-up + A-race in same campaign → both linked."""

    def test_phase_detection(self):
        """Campaign with increasing volume then stable then decreasing
        → base_building, race_specific, taper phases detected."""


class TestDisruptionClassification:
    def test_complete_stop_is_injury(self):
        """Volume drops to 0 for 4+ weeks → complete_stop."""

    def test_gradual_reduction_is_not_disruption(self):
        """Volume decreases 30% over 3 weeks → not a disruption."""


class TestRevisedExtraction:
    def test_layer2_uses_campaigns(self):
        """Layer 2 compares campaign dimensions, not fixed windows."""

    def test_layer5_detects_pb_chain(self):
        """Sequential PBs across races → trajectory finding."""

    def test_layer5_detects_acceleration(self):
        """Improvement rate increases at a point → acceleration
        finding referencing the training change that caused it."""

    def test_narrative_references_campaign_scope(self):
        """Finding sentence mentions months/weeks of preparation,
        not just peak long run distance."""

    def test_disruption_acknowledged_in_finding(self):
        """Race after disruption → finding mentions injury context,
        not 'long taper'."""
```

---

## File Index

New files:

| File | Section | Purpose |
|------|---------|---------|
| `services/campaign_detection.py` | CD | Inflection points, campaigns, disruptions |
| `tests/test_campaign_detection.py` | CD | Campaign detection tests |

Modified files:

| File | Section | Change |
|------|---------|--------|
| `models.py` | DI-3, CD-2 | Add `chip_time_seconds`, `campaign_data` to PerformanceEvent |
| `services/performance_event_pipeline.py` | DI-1, DI-2 | Auto-confirm Tier 1, dedup PerformanceEvents |
| `services/fingerprint_analysis.py` | RE-1 | Campaign-level analysis, Layer 5 trajectory |
| `routers/fingerprint.py` | DI-2, DI-3 | Dedup check on add/confirm, chip time support |
| `schemas_fingerprint.py` | DI-3 | Add chip_time fields to confirm/add endpoints |

Migrations:

| Migration | Section |
|-----------|---------|
| `phase1c_di3_add_chip_time.py` | DI-3 |
| `phase1c_cd2_add_campaign_data.py` | CD-2 |

---

*This spec exists because the first findings were statistically true
and completely missed the story. The system told a physicist who spent
6 months rebuilding his aerobic engine that his long runs were 2 miles
longer. That's not insight. That's trivia. Build something better.*
