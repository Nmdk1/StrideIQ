# Racing Fingerprint & Progress Page State Machine

**Date:** March 4, 2026
**Status:** Founder-approved spec with Phase 1 build scope defined
**Origin:** Deep discussion between founder, outside advisor, and new advisor
**Replaces:** `PROGRESS_NARRATIVE_WIRING_SPEC.md` (deleted — that spec was wrong)

---

## Before You Build

Read these three documents in order before writing any code. The first
defines how you work with this founder. The second defines how every
screen should feel. The third — this spec — defines what to build.
A builder who skips the first two will produce technically correct work
that violates the product vision. That has already happened once. It
will not happen again.

1. **`docs/FOUNDER_OPERATING_CONTRACT.md`** — Non-negotiable operating
   rules. Read order, commit discipline, evidence over claims,
   suppression over hallucination. Every session, every feature.

2. **`docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md`** — What has been
   agreed, what has been rejected, how every screen should feel. Do not
   re-propose rejected decisions. Do not build surfaces that contradict
   the design philosophy.

3. **This spec.** The product design, the data foundation, the Phase 1
   scope, the validation gate.

---

## The Product Thesis

The sentence is the product. Everything else is infrastructure to produce
the sentence.

"Your current block most closely matches the 18 weeks before your best
race." That sentence is the product. The `PerformanceEvent` table, the
block signature extraction, the training state computation — those are
the machinery that makes the sentence accurate, personal, and fast.

Every architectural decision in this spec is governed by: does it make
the sentence more accurate, more personal, or faster to produce?

---

## The Design Principle

Visual First, Narrative Bridge, Earned Fluency — applied to the progress
page as a state machine.

The progress page is not a dashboard that needs to be interesting every
day. It is a destination the athlete visits at specific moments in their
training life:

- When they want to understand where they are in the block
- When they're anxious before a race
- When they're reflecting after one
- When they want to see what the data has proved about their body

Design it for those visits, not for daily engagement. Daily engagement
belongs to home.

The system knows when to speak and when to be silent. A coach who says
the right thing at the right moment and nothing otherwise is a
fundamentally different product from a dashboard that fills space.

---

## The Five States

The progress page is a state machine. The backend already knows which
state the athlete is in — race goal exists, days to race, whether a race
just happened, whether this is first connect, whether correlation
findings exist. The frontend reads that state and renders the right
version.

### State 1: First Connect

**Trigger:** Athlete has just connected Strava/Garmin. Historical data
has been synced. No race goal set yet.

**What the athlete sees:**

**The Race Curation Experience** (see Phase 1A for the full
specification). This is the onboarding moment. The system presents the
athlete's racing history for the first time through a discovery flow —
confirmed races, candidate races, and the ability to add any the system
missed. As the athlete curates, the Racing Life Strip builds in real
time: each confirmed race adds a pin, and the shape of their racing
history emerges as they go.

**Visual:** The Racing Life Strip — their entire running history as a
horizontal visual. Time flows left to right. Training volume is height.
Color encodes intensity (cool blues for easy weeks, warm amber for hard
weeks, deep reds for race weeks). Race days are marked as bright vertical
pins. Best performances glow. Worst are muted.

The athlete sees the rhythm of their training life for the first time —
loading phases, recovery dips, tapers, race peaks. Years of running in
one shape they've never seen before.

**Narrative:** Below the strip, the first fingerprint finding. Not all
findings — one. The most significant pattern the system found across
their race history.

Example: "I found 9 races in your history. Your 3 best performances
share a pattern — you peaked your hardest training 5 weeks out, not 3.
Your 2 worst races both had heavy training inside 3 weeks of race day."

**What's absent:** No block overlay (no active block). No readiness
gauge. No convergence warning. Just the history and the first sentence.

**Call to action:** Set a race goal to unlock the block comparison.

---

### State 2: In a Training Block (active race goal, > 2 weeks out)

**Trigger:** Athlete has a race goal set. Race is more than 14 days away.
The system has enough training data since the block began to compute a
meaningful signature.

**What the athlete sees:**

**Visual:** The Block Shape Overlay — two area shapes overlaid. The
current training block and the closest historical match. Volume is
height. Intensity is color. Time flows left to right toward race day.

Where the shapes align, the overlap is visible — the athlete sees "I'm
tracking my best block." Where they diverge, the gap is clear. The
overlap percentage is a visual signal. The overlay updates daily.

The athlete learns a visual language for reading training blocks. After
20 visits, they recognize build weeks, recovery weeks, and taper phases
by shape and color without reading a word.

**Narrative:** The match sentence and what it means right now.

Example: "Your current block is tracking 87% of the pattern before your
personal best at Philadelphia. Volume peaked at the same point. Your
long runs are following the same progression. The one difference: your
quality sessions are slightly harder this time — your body has been
handling them well."

No acronyms. No CTL/ATL/TSB. A coach pointing at two shapes: "See how
similar these look? That's where you want to be."

**Supporting context (below the fold):**
- Racing history for this distance (previous results, visual comparison)
- What's working in this block vs historical patterns
- Operating manual entries relevant to this race distance
- Taper recommendation based on personal history (when applicable)

**What's absent:** Post-race analysis. First-connect novelty strip
(moved to racing profile). Findings unrelated to the current race.

---

### State 3: Pre-Race Window (active race goal, ≤ 14 days out)

**Trigger:** Race day is within 14 days.

**What the athlete sees:**

**Visual:** The Block Shape Overlay shifts emphasis. The final portion
of the shape — the taper — is expanded and highlighted. The athlete's
current taper is overlaid on their optimal personal taper pattern (from
their best historical races). The match/deviation in the taper zone is
the visual focus.

If the system detects convergence toward a bad historical pattern, the
Convergence Warning visual appears: the current trajectory line
approaching a historical bad-outcome trajectory. Lines converging = risk.
Color shifts from green to amber as proximity increases.

**Narrative:** The pre-race sentence. Confidence-building when the data
supports it. Honest when it doesn't. Never falsely reassuring.

Confidence example: "Your block matches your best marathon preparation.
Your taper is tracking the same 12-day pattern that preceded your 3:08.
Your body has been here before and raced well."

Caution example: "Your current block shares 3 of 4 signatures with the
block before your DNS at Houston. The one time this pattern appeared and
you still raced well, you backed off volume by 20% in the final 2 weeks.
You haven't done that yet."

Neutral example: "This is your first race at this distance with enough
training data to compare. No historical pattern to match — your body is
writing a new signature."

**What's absent:** Everything that doesn't serve pre-race decision-making.
The page is focused. One visual. One narrative. Supporting context only
if directly relevant to the next 14 days.

---

### State 4: Post-Race (race completed within the last 7 days)

**Trigger:** A race-flagged activity was recorded within the last 7 days
for the distance matching the race goal.

**What the athlete sees:**

**Visual:** The Race Report Card — the completed block's anatomy. A
visual comparison of this block against the athlete's average block and
their best block for this distance.

Structural differences are shown as visual comparisons (not tables):
long runs (length and intensity), quality sessions (frequency and
effort), volume trajectory (peak timing), taper execution (duration and
depth). The athlete sees at a glance what was unique about this block.

**Narrative:** What the block analysis revealed.

After a great race: "This was your strongest marathon by age-graded
performance. What set it apart: you ran your long runs 45 seconds per
mile easier than usual. You did fewer hard sessions but pushed each one
closer to race pace. And you started your taper 3 days earlier than
your average. Your body had more time to absorb the work."

After a disappointing race: "This block's signature is closest to your
race at [worst historical match]. The common pattern in your 2 weakest
performances: training stayed heavy inside 3 weeks of race day. Your
best races all had volume reduction by that point."

After a first race: "This is your first fingerprinted race at this
distance. The block signature has been saved. After your next race,
the system will start comparing blocks to find what works best for
your body."

**What's absent:** Block overlay (the race is over — the overlay
freezes as a historical snapshot). Convergence warning (no longer
relevant). Pre-race anxiety content.

**Call to action:** Reflect on the race (harder/as expected/easier).
Set next race goal. View updated operating manual.

---

### State 5: Between Cycles (no active race goal)

**Trigger:** No race goal is set. The athlete is in maintenance, base
building, or hasn't set a goal yet (but has history).

**What the athlete sees:**

**Visual:** The Personal Operating Manual — accumulated findings about
their body, each with a small, specific visual.

Each confirmed finding gets a mini-visual paired with its sentence:
- A threshold line for "Your sleep cliff: below 6.2 hours, performance
  drops" — data dots visible on either side of the break point
- A decay curve for "The benefit of threshold sessions lasts about 3
  days" — gentle downward slope showing effect fading
- Two overlapping taper shapes for "Your best taper: 12 days, 40%
  reduction" — actual vs ideal
- A scatter showing race vs training performance — "You race 3-4%
  faster than your training suggests"

The operating manual grows with each race, each confirmed correlation,
each pattern that clears the statistical gate.

**Narrative:** Summary of what the data has proved, without repeating
stale findings. New entries since last visit are highlighted. The page
is quiet — it has nothing urgent to say. The athlete visits when they
want to reflect, plan, or remember what their body has taught them.

**What's absent:** Block overlay (no active block). Pre-race content.
Post-race analysis (older than 7 days, moved to race history).
Convergence warning. The page is intentionally quiet.

**Call to action:** Set a race goal to activate the block overlay and
fingerprint comparison.

---

## State Transitions

```
First Connect ──[set race goal]──→ In Training Block
                                        │
                                   [≤ 14 days]
                                        ↓
                                   Pre-Race Window
                                        │
                                   [race completed]
                                        ↓
                                    Post-Race
                                        │
                              [7 days elapsed OR
                               new goal set]
                                        ↓
                         Between Cycles ←──── or ──→ In Training Block
```

Edge cases:
- Athlete sets a race goal but has no training history → State 2 with
  a note: "Start training and the block comparison will appear after
  your first 2 weeks of data."
- Athlete has no races in history → State 5 with operating manual
  entries only from correlation findings (no race fingerprint content).
- Athlete has a race goal AND a race just completed → State 4 takes
  priority for 7 days, then transitions to State 2 for the next race.
- Multiple race goals → The nearest race governs the state. After it
  completes, the next race takes over.
- **Athlete has extensive training history but no detected races** →
  This is common: trail runners at non-standard distances, athletes who
  don't use Strava's race flag, manual loggers without workout_type
  metadata. The system should detect this state (high activity count,
  zero PerformanceEvents) and show State 5 with a prompt: "I found
  [N] activities but no identified races. Have you raced? Mark past
  races to unlock your racing fingerprint." Link to an interface where
  the athlete can browse their history and flag races. This is the
  acquisition moment for athletes whose data doesn't self-identify —
  the system needs their help, and the payoff (fingerprint analysis)
  motivates them to provide it.

---

## Data Foundation: The PerformanceEvent Table

One row per identified race or race-day PB. This is the single source
of truth for "this was a performance event, here's the full context."

### What qualifies as a PerformanceEvent

An activity that meets ANY of:
- `user_verified_race == True`
- `is_race_candidate == True` AND `race_confidence >= 0.7`
- Strava `workout_type == 3` (race) — preserved separately from
  classifier override
- A personal best at a standard distance achieved on an activity that
  meets one of the above criteria (race PB)

### Standard distances (8)

Mile, 5K, 10K, 15K, 25K, Half Marathon, Marathon, 50K

GPS tolerance ranges already defined in `personal_best.py` for all 8.
Race detection currently covers only 4 (5K, 10K, half, marathon) — must
be expanded to all 8.

### Fields

**Identity:**
- `id` (UUID, primary key)
- `athlete_id` (FK → Athlete)
- `activity_id` (FK → Activity)
- `distance_category` (enum: the 8 standard distances)
- `event_date` (date)
- `event_type` (enum: `race`, `race_pb`, `training_pb`)

**Performance:**
- `time_seconds` (integer)
- `pace_per_mile` (float)
- `rpi_at_event` (float — derived from race time via RPI calculator)
- `performance_percentage` (float — age-graded, from WMA)
- `is_personal_best` (boolean — was this a PB at the time?)

**Training State at Event (computed, not backfilled from activities):**
- `ctl_at_event` (float — chronic training load on event date)
- `atl_at_event` (float — acute training load on event date)
- `tsb_at_event` (float — training stress balance on event date)
- `fitness_relative_performance` (float — actual RPI vs predicted from
  CTL, measures outperformance/underperformance of fitness)

**Block Signature (JSONB — the fingerprint):**
- `block_signature` containing:
  - `volume_trajectory` — weekly volume for N weeks before event
  - `intensity_distribution` — proportion of easy/moderate/hard per week
  - `long_run_pattern` — long run distances and effort levels
  - `quality_session_pattern` — frequency and intensity of hard sessions
  - `taper_signature` — volume reduction curve in final weeks
  - `peak_volume_week_offset` — which week (relative to race) had peak
    volume
  - `peak_intensity_week_offset` — which week had hardest training

**Wellness State (when data exists):**
- `pre_event_wellness` (JSONB) containing:
  - `avg_sleep_hours_7d` — average sleep in 7 days before
  - `avg_hrv_7d` — average HRV in 7 days before (if available)
  - `hrv_trend_14d` — HRV trajectory direction
  - `avg_stress_7d` — average stress in 7 days before
  - `readiness_at_event` — readiness score on event day (if available)

**Classification:**
- `race_role` (enum: `a_race`, `tune_up`, `training_race`, `unknown`)
- `cycle_id` (nullable UUID — groups races in the same training cycle)

**Metadata:**
- `created_at`, `updated_at`
- `computation_version` (integer — allows recomputation when algorithm
  improves)

### Population strategy

1. **On race identification:** When an activity is flagged as a race
   (Strava sync, athlete verification, or algorithmic detection), create
   or update the PerformanceEvent. Compute training state and block
   signature at that time.

2. **Historical backfill:** On first connect, after activity sync
   completes, scan for all race-flagged activities at standard distances.
   Create PerformanceEvents for each. Compute training state by walking
   backward through the activity log.

3. **Recomputation:** When the computation algorithm changes (version
   bump), recompute affected PerformanceEvents. Targeted, not global.

### Tune-up vs A-race classification

Inferred from race proximity, distance hierarchy, and effort context
within a cycle:

- If two races are within 8 weeks and the second is equal or longer
  distance → the first is a `tune_up`
- If a race is the only race in its distance category within 12 weeks
  → `a_race` (default assumption)
- Athlete can override via the reflection flow → stored as
  `user_classified_role`
- `training_race` — athlete explicitly marks a race-effort workout as
  not a goal race

**Effort-relative context matters for tune-up risk assessment:** A 5K
all-out 2 weeks before a marathon is physiologically different from a
conservative half marathon 6 weeks out. The classification should
capture not just the role (tune-up vs A-race) but the effort relative
to the A-race distance. A tune-up at a much shorter distance with
maximum effort close to the A-race carries different risk than a
tune-up at a similar distance with conservative pacing further out.
The pattern analysis (Layer 3) must account for this when evaluating
the tune-up-to-A-race relationship — not just "did you race before
your A-race" but "how hard did you race and how close to race day."

### Block signature computation

For each PerformanceEvent, compute the block signature by looking at
all activities in the N weeks before the event:

1. Group activities by week (relative to race day)
2. Per week: total volume, intensity distribution (easy/moderate/hard
   from `classify_effort()`), long run distance, number of quality
   sessions
3. Volume trajectory: the sequence of weekly volumes
4. Taper detection: identify where volume starts declining consistently
5. Peak timing: which week had maximum volume and maximum intensity

The lookback window scales with distance:
- Mile/5K: 8 weeks
- 10K/15K: 12 weeks
- Half marathon: 14 weeks
- Marathon: 18 weeks
- 50K: 20 weeks

Training state (CTL/ATL/TSB) is computed for race day only — not stored
on every activity. Walk backward through the activity log, apply the
EMA decay functions, compute the value at the event date.

---

## Pattern Extraction: The Four Layers

These analyses run across all PerformanceEvents for an athlete. Outputs
are sentences stored as findings. Minimum 3 PerformanceEvents at any
distance before pattern extraction runs. Minimum 5 for high-confidence
findings.

### Layer 1: Where Do Your PBs Live?

Distribution of personal bests across race day vs training. How much
faster does the athlete perform on race day vs their training ceiling?

**Finding examples:**
- "You race 4% faster than your best training efforts. You peak for
  competition."
- "Your training PBs and race PBs are within 1%. You train close to
  your ceiling."

### Layer 2: Block Signature Comparison

What structural patterns differentiate best races from worst races?
Compare block signatures across performance quartiles.

**Finding examples:**
- "Your best races followed blocks where volume peaked 5 weeks out.
  Your worst races had volume peaks inside 3 weeks."
- "Your best marathons had longer but slower long runs. Your worst had
  shorter but faster long runs."
- "Your best performances had a 12-day taper with 40% volume reduction.
  Your worst had shorter tapers with less reduction."

### Layer 3: Tune-up to A-Race Relationship

When you PB a tune-up race within 6 weeks of an A-race, what happens
at the A-race? Fitness-relative (Layer 4), not raw time.

**Finding examples:**
- "You've PB'd tune-ups before 3 A-races. Twice, the A-race
  underperformed your fitness. The common factor: volume stayed high for
  2 weeks after the tune-up PB."
- "Your tune-up performances don't predict your A-race outcomes. Your
  A-race performance correlates more strongly with taper execution than
  tune-up result."

### Layer 4: Fitness-Relative Performance

Normalize every race result against fitness at the time. Did the athlete
outperform or underperform their training state?

Uses `fitness_relative_performance` on the PerformanceEvent:
`actual_rpi / predicted_rpi_from_ctl` — values > 1.0 = outperformance.

This is the denominator that prevents false findings. A tune-up PB when
CTL is 52 is a different event than a tune-up PB when CTL is 35.

**Finding examples:**
- "Your best races outperformed your fitness by 3-5%. Your worst races
  underperformed by 2-4%. The difference isn't fitness level — it's
  what you did in the final 3 weeks."
- "Your race-day outperformance correlates with taper length. Longer
  tapers produce bigger outperformance for your body."

---

## The Five Surfaces

Each surface is a different way of presenting fingerprint findings to
the athlete at the right moment. One infrastructure, five moments, one
sentence each.

### Surface 1: First Connect Hook

**Where:** Progress page, State 1
**When:** Immediately after initial data sync completes
**What:** Racing life strip + the single most significant finding
**Goal:** Acquisition — "I've never seen anything like this"

### Surface 2: Block Comparison (Daily During Race Prep)

**Where:** Progress page, States 2 and 3
**When:** Active race goal, within training window
**What:** Block shape overlay + match narrative
**Goal:** Daily engagement during race prep — "Am I on track?"

### Surface 3: Pre-Race Confidence/Warning

**Where:** Progress page, State 3 (and optionally home page as a signal)
**When:** ≤ 14 days from race
**What:** Taper comparison + historical match sentence.
Convergence warning if trajectory matches a bad historical outcome.
**Goal:** The sentence at mile 18 — confidence or honest caution

### Surface 4: Post-Race Analysis

**Where:** Progress page, State 4
**When:** Within 7 days of a completed race
**What:** Race report card — what was unique about this block
**Goal:** Understanding — "What went right / what went wrong"

### Surface 5: Personal Operating Manual

**Where:** Progress page, State 5 (and as individual entries on relevant
surfaces when contextually appropriate)
**When:** Between cycles, or as supplementary content during cycles
**What:** Accumulated findings, each with a specific mini-visual
**Goal:** The document that makes leaving impossible — "My body's
playbook"

---

## Integration with Existing Systems

### Correlation Engine (Layers 1-4)

The correlation engine's confirmed findings enrich the operating manual
and the pre-race analysis. Threshold detection tells the athlete their
sleep cliff. Asymmetric response tells them protecting sleep matters
more than optimizing it. Decay curves tell them how many days before a
race to protect their sleep. These are operating manual entries.

The fingerprint's block signature analysis is a separate but
complementary system. The correlation engine finds "sleep affects your
performance." The fingerprint finds "your best races had 7.2 hours
average in the final 10 days." Both are surfaced in the operating
manual. Both inform the pre-race analysis.

### Existing Pre-Race Fingerprinting Service

`pre_race_fingerprinting.py` currently analyzes the 24-72 hour wellness
window before races. This is a subset of what the new system does. The
existing service's statistical comparison (Mann-Whitney, Cohen's d) and
pattern detection (conventional vs inverted) remain valid for the
wellness component. The new system wraps it — the block signature is the
broader context, the wellness window is one component within it.

The broken home page signal (`get_fingerprint_signal()` with attribute
mismatches) should be fixed as a standalone task.

### Effort Classification / TPP

Block signature intensity distribution uses `classify_effort()` to
categorize activities within each week as easy/moderate/hard. The effort
classification spec (Tier 0: TPP) is a dependency for accurate intensity
distribution — pace-based effort classification produces cleaner labels
than HR-based, especially for historical activities with varying
environmental conditions.

Fitness-relative performance (Layer 4) uses RPI at event time and CTL
at event time. RPI is derived from the race result itself via
`calculate_rpi_from_race_time()`. CTL is computed from training history.
The ratio gives outperformance/underperformance.

### Race Detection Expansion

Current race detection covers 4 distances (5K, 10K, half, marathon).
Must expand to all 8 standard distances (add mile, 15K, 25K, 50K).
GPS tolerance ranges already exist in `personal_best.py` for all 8.
Additionally, preserve Strava's original race tag (`workout_type == 3`)
separately from the classifier's `workout_type` string — the current
flow overwrites the Strava tag.

---

## Narrative Principles (Non-Negotiable)

1. **No acronyms.** Never CTL, ATL, TSB, RPI, TPP, PMC, EMA, GAP in
   athlete-facing text. A coach says "your fitness" not "your CTL."
   A coach says "you were fresh and recovered" not "your TSB was +8."

2. **No false precision.** "Your current block is tracking well" not
   "your block similarity score is 87.3%." The percentage can exist in
   the visual (as overlap proportion). The narrative speaks in human
   terms.

3. **Suppression over hallucination.** If the system doesn't have
   enough data or the finding doesn't clear the statistical gate, say
   nothing. "This is your first race at this distance — your body is
   writing a new signature" is better than a fabricated comparison.

4. **The system informs and points, the athlete decides.** "Your
   current block resembles the one before your best race" is
   information. "The last time this happened and you still raced well,
   you backed off by 20%" is pointing. "You should taper now" is a
   decision. The system provides information and points toward what
   worked before. The athlete makes the call. A coach who only provides
   information without ever pointing toward a decision isn't serving
   the athlete.

5. **No templates.** If the system can't say something genuinely
   contextual — specific numbers, specific races, specific patterns from
   this athlete's data — it says nothing. Silence over slop.

6. **Evidence is explorable.** Every sentence should be backed by data
   the athlete can tap into. "Your best races had volume peaks 5 weeks
   out" — tap to see the 3 races, the peak weeks, the data.

---

## Phase 1 Build Scope

### Data Quality Investigation (March 4, 2026)

Production data inspection of the founder's account (742 activities,
540 Strava + 202 Garmin) revealed three systemic issues that must be
resolved before the fingerprint can produce accurate results:

**1. Race detection catches ~25% of actual races.**

The founder has 15+ races across 2 years. The system detected 4. Root
causes:
- Race detection only checks 4 distances (5K, 10K, half, marathon) —
  misses mile, 15K, 25K, 50K entirely
- Detection requires HR data as a hard gate — activities without HR
  (common in early sync periods and some Garmin imports) are silently
  skipped, even when the activity name says "Gulf Coast Classic - 3rd
  overall"
- Confidence threshold (0.70-0.85) filters out real races with
  lower-confidence detection scores
- Activity names — the most reliable race signal ("Pascagoula Charity
  5k - 1st Grandmaster") — are not used by the detection algorithm
- Strava race tags applied after initial sync don't flow back to
  StrideIQ
- All 2024 Strava activities have `name = NULL` — an entire year of
  racing history invisible to name-based detection. The Nov 30, 2024
  Stennis Space Center Half Marathon (1st Masters) is a nameless
  21184m activity with HR=156, missed by all heuristics.

**2. Activity duplication from Strava + Garmin.**

Both sources are ingested. Cross-provider deduplication exists at
ingestion time (fixed Feb 23 after a SEV-1 — 40% mileage inflation).
But existing duplicates in the database are not cleaned up, and
downstream computations (training load, weekly volume, coach context)
have no dedup awareness. Double-counted volume will corrupt every
block signature.

**3. 48% of activities have no effort classification.**

357 of 742 activities have `workout_type = None`. Block signatures
require effort classification (easy/moderate/hard) for intensity
distribution. The `classify-all` endpoint exists but hasn't been run
on the full history.

---

### Pre-Work (data quality prerequisites)

These must complete before the PerformanceEvent backfill runs.

**P1. Retroactive duplicate detection and resolution.**

Scan existing activities. Identify cross-provider duplicates by time
window (±1 hour) + distance match (±5%). For each duplicate pair,
keep the record with richer data (prefer Garmin HR when Strava HR is
null; prefer Strava names when Garmin names are generic). Mark the
secondary record as `is_duplicate = True` or merge fields into the
primary. All downstream computations must exclude duplicates.

**P2. Classify unclassified activities.**

Run `classify_effort_bulk()` across all activities with null
`workout_type`. The endpoint exists. This is an operational task, not
a code change.

**P3. Fix training load lookback.**

The hardcoded 60-day lookback in `calculate_training_load()` produces
inaccurate CTL for historical race dates (EMA starts from 0.0 with
insufficient convergence time). Two options:
- Make `lookback_days` a parameter and pass 180+ for race context
- Build a single-pass EMA function that walks from the athlete's first
  activity to their last and extracts CTL/ATL/TSB at any requested date

The single-pass approach is more accurate and more efficient when
computing training state for multiple races.

**P4. Expand race detection to 8 standard distances.**

Add mile, 15K, 25K, 50K to `detect_race_candidate()`. GPS tolerance
ranges already defined in `personal_best.py`. Also add name-based
detection as a supplementary signal: activity names containing "race",
"classic", "charity", "marathon", "5k", "10k", "half", ordinal
placements ("1st", "2nd", "3rd"), and "chip time" should boost race
confidence even when HR is missing.

---

### Phase 1A: PerformanceEvent Table + Race Curation Experience

#### The Race Curation Experience

**This is not a workaround for bad detection. This is a product
feature.** Every athlete who connects will have races the algorithm
missed. Trail ultras at non-standard distances, local road races with
unusual courses, manually logged runs without metadata — algorithmic
detection will never catch all of them reliably. The manual flow is
the primary path for the athlete's verified race history. Algorithmic
detection is the convenience layer that pre-populates it.

**The experience: the athlete's racing life, presented for the first
time.**

The flow is NOT "here are activities that might be races, confirm or
deny." It IS "here is your running history — here are the
performances we identified, here are the ones we're not sure about,
here are the ones we might have missed. Help us get this right and
we'll show you something you've never seen about your own racing."

**Each candidate race is a card the athlete recognizes, not a row in
a table.** Distance, date, day of week, time of day, location if
available, pace, HR if available, name if it exists. Enough context
that the athlete remembers the day. The confirmation is a moment of
reconnecting with a race they ran, not a data entry task.

**Many activities have no name.** Production data shows the founder's
entire 2024 history has `name = NULL` on every Strava activity. The
Nov 30, 2024 Stennis Space Center Half Marathon (1st Masters, 4:26/km,
HR=156) sits in the database as a nameless 21184m activity —
indistinguishable from a training long run without the athlete's help.
For nameless activities, the card must make pace, day of week, and HR
the primary recognition triggers. A 4:26/km half on a Saturday
morning is obviously a race; a 5:34/km half on a Tuesday is not.
Sort Tier 3 browse by pace (fastest first within each distance) to
surface race efforts at the top.

The system presents three tiers:

1. **"Races we found"** — high-confidence detections (Strava race tag,
   user-verified, confidence ≥ 0.7). Pre-confirmed. The athlete sees
   each one and can correct any that are wrong.

2. **"Were these races?"** — medium-confidence candidates. Activities
   at standard distances with race-like characteristics but below the
   confidence threshold. The athlete taps yes or no. Each one is
   presented as a card with enough context to trigger recognition.

3. **"Any races we missed?"** — the athlete can browse their activity
   history (filtered by date range or distance) and flag additional
   races the system couldn't detect. This catches the Bellhaven Hills
   16K, the trail races, the untagged events.

**The fingerprint payoff is visible during curation, not promised
afterward.** As the athlete confirms races, the Racing Life Strip
builds in real time. Each confirmed race adds a pin to the strip.
The shape of their racing history emerges as they curate it. By the
time they're done confirming, they've already seen the first version
of the visual they built together with the system.

The moment ends when the strip is populated and the system says:
"I found [N] races across [M] years. Let me analyze what your best
performances had in common." The first fingerprint finding appears.
The product has delivered value before the athlete has set a single
race goal.

**This is the onboarding into the fingerprint feature.** Not a setup
screen. Not a form. A discovery experience — like unwrapping presents.
Each race the system found is a small revelation. Each one the athlete
adds enriches the picture. The payoff builds visually as they go.

#### Technical scope for Phase 1A

1. **Create `PerformanceEvent` model and migration.** Schema as defined
   in the Data Foundation section above.

2. **Build the algorithmic population pipeline.** On first connect or
   on demand: scan activities at standard distances, apply expanded
   race detection (P4), create PerformanceEvents for high-confidence
   matches. Compute training state and block signature for each.

3. **Build the race curation API.** Endpoints for:
   - `GET /v1/fingerprint/race-candidates` — returns the three tiers
     (confirmed, candidates, browse history)
   - `POST /v1/fingerprint/confirm-race` — athlete confirms or rejects
     a candidate
   - `POST /v1/fingerprint/add-race` — athlete identifies a race from
     their activity history
   - `GET /v1/fingerprint/strip` — returns the data for the Racing
     Life Strip (populated events + training volume timeline)

4. **Build the race curation frontend.** The discovery experience
   described above. Cards, not tables. Real-time strip building.
   Fingerprint payoff at the end.

5. **Compute training state for each confirmed race.** Single-pass EMA
   from first activity to last. Extract CTL/ATL/TSB at each race date.
   Store on PerformanceEvent.

6. **Compute block signature for each confirmed race.** Weekly volume,
   intensity distribution, long run pattern, quality sessions, taper
   signature, peak timing. JSONB on PerformanceEvent.

7. **Compute fitness-relative performance.** RPI from race result via
   `calculate_rpi_from_race_time()`. Compare to predicted performance
   from CTL. Store outperformance/underperformance ratio.

---

### Phase 1B: Pattern Extraction + Validation

Run the four-layer analysis across the founder's PerformanceEvents.
Validate findings against reality before building any surface.

1. **Layer 1:** Where do PBs live — race day vs training?
2. **Layer 2:** Block signature comparison — what differentiates best
   from worst?
3. **Layer 3:** Tune-up to A-race relationship — does the founder's
   tune-up PB pattern predict A-race outcomes?
4. **Layer 4:** Fitness-relative performance — normalize everything
   against CTL at race time.

**Validation gate:** The founder reviews the findings. Do they match
what they know about their own racing patterns? If the findings are
wrong or trivial, the data or the analysis needs fixing before any
surface is built. If the findings are genuine — if the system
discovers something true about the athlete's body that they suspected
but couldn't confirm — Phase 1 is complete and the surfaces are worth
building.

**No surface is built until the findings are validated against
reality.** Don't design visuals for findings that haven't been
confirmed to be true and meaningful.

#### Validation Result (March 4, 2026)

**PASSED.** 17 confirmed races. Three findings produced and validated:

1. **Long run correlation:** Best races preceded by 16 mi long runs vs
   14 mi before weaker races. True — founder's peak blocks reach
   18-22 mi long runs.

2. **Race-day uplift:** Races meaningfully outperform training. True —
   founder races deep into pain, producing uplift training alone
   wouldn't predict.

3. **Taper pattern:** Short taper (2 weeks) correlates with best races.
   What looks like a 5-week taper before weaker races is actually
   injury-forced rest, not intentional taper. **This finding is the
   canonical example of the product's core loop:** the system surfaces
   a true pattern from data; the athlete provides context the data
   cannot see; the sentence improves. Future work: distinguish
   intentional taper from unplanned volume loss (injury detection
   from training load discontinuities).

---

## What This Spec Does NOT Cover

- **Specific visual implementation.** The visual concepts (racing life
  strip, block shape overlay, convergence lines, report card, operating
  manual mini-visuals) are described at the concept level. Visual design
  and interaction design require a separate pass — likely with mockups,
  not prose. The visuals must be modern, high-impact, and take advantage
  of current web capabilities. They are not standard chart library
  output.

- **Specific API endpoint design.** The backend needs to serve state
  information and fingerprint data to the frontend. Endpoint design
  follows from the data model, not from this spec.

- **Builder implementation instructions.** This spec defines WHAT the
  athlete experiences. A builder spec (written after this is approved)
  will define HOW to build it — specific files, functions, components,
  test plans.

- **Timeline or phasing beyond Phase 1.** Phase 1 scope (pre-work,
  1A, 1B) is defined above. Subsequent phases (surface buildout,
  progress page state machine rendering, proactive coach integration)
  are sequenced after Phase 1B validation passes.

---

## Competitive Differentiation

No running platform offers historical block fingerprinting, block-to-
block matching, tune-up-to-A-race pattern analysis, or pre-race warnings
grounded in personal history. Strava predicts race times from ML
comparison to other athletes. Garmin uses VO2max lookup tables. Training
Peaks has the PMC for load management. Runalyze has deep analytics but
no pattern intelligence.

Nobody answers "what produced your best races" or "which historical
block does your current training resemble." The Racing Fingerprint is
the first feature in recreational running that uses an athlete's
complete race history to produce specific, personal, data-backed
statements about their body that change how they train.

The viral unit is the sentence, not the chart. "It told me something
about my own body that I didn't know, and it was true." That gets said
to other runners with genuine emotion.

---

## Scientific Grounding

- Training load alone explains ~26.5% of race performance variance.
  The shape of the fitness curve matters more than the absolute level.
- The 7-3 week pre-race window has the greatest positive effect on
  performance. Training in the 0-14 day window has a negative effect.
- Optimal taper: ~2 weeks, 41-60% volume reduction, intensity
  maintained. Individual variation is enormous — 3 of 11 Olympic gold
  medalists didn't take a rest day in the final 5 days.
- Subjective measures outperform objective measures for detecting
  training state changes.
- The Banister impulse-response model is conceptually useful but
  statistically unreliable as a race time predictor. Don't fake
  precision the science doesn't support.
- The race-to-race pattern literature is thin — this is a genuine N=1
  discovery opportunity.
- **Population findings establish the prior. The athlete's own history
  overrides it.** The taper research says 41-60% volume reduction over
  2 weeks. That's the starting assumption for an athlete with no race
  history. But when an athlete's own data shows their best races
  followed a 35% reduction over 10 days, their data wins. Every
  population statistic cited in this spec is a cold-start heuristic,
  not a rule.

---

*This spec represents the shared vision established during a deep
discussion session. The sentence is the product. The visual catches the
eye. The narrative builds understanding. Together they build fluency
that becomes the moat.*
