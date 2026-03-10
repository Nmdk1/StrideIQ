# Session Handoff — March 3, 2026: Investigation Engine

**Read order:**
1. `docs/FOUNDER_OPERATING_CONTRACT.md`
2. `docs/PRODUCT_MANIFESTO.md`
3. `docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md`
4. This document

---

## What Happened

Built and validated a question-based investigation engine for mining
training data. Ran 4 deep-mine passes against the founder's data to
discover what the system can and cannot find.

### The Big Insight

The founder rejected the dimension-scanning approach. Out of 6 manually
surfaced findings, only 1 was genuinely new to him. The winning finding
was a **multi-activity cross-reference** (pairing Saturday VO2 sessions
with Sunday long runs, computing cardiac drift, tracking the trend). The
other 5 were single-variable observations the founder already tracked.

**The founder's directive:** The system should ask questions, not scan
dimensions. Cross-referenced findings that connect multiple activities
are the only ones worth presenting. Single-variable findings (HR trends,
cadence changes, volume patterns) are things attentive athletes already
watch.

### What Was Built

`apps/api/services/race_input_analysis.py` was restructured around:

1. **Environmental context layer** — `ActivityContext` dataclass with
   indoor/outdoor detection (elevation < 20m = treadmill), temperature,
   humidity fields, and `get_gap_adjusted_pace()` for grade-adjusted
   split analysis.

2. **Four investigation functions**, each self-contained:
   - `investigate_back_to_back_durability` — pairs consecutive-day
     quality + long run sessions, computes cardiac drift trend,
     compares with/without prior quality work. **This is the one that
     produced a genuine finding.**
   - `investigate_race_execution` — analyzes race-day splits using
     GAP-adjusted pace (falls back to raw with disclosure if no GAP).
   - `investigate_recovery_cost` — compares next-day easy run metrics
     after different quality session types vs baseline.
   - `investigate_training_recipe` — within-distance training profile
     comparison with recency confound detection.

3. **`mine_race_inputs()`** runs all investigations and legacy analysis.

### Validation Results (9 findings produced)

| # | Type | Verdict | Why |
|---|------|---------|-----|
| 1 | Back-to-back durability | **GENUINE** | Founder didn't know the drift numbers |
| 2-4 | Race execution | WRONG | No GAP data → split ratios reflect course elevation, not pacing |
| 5 | Recovery cost | PROBABLY KNOWN | Founder deliberately runs easy after hard days |
| 6 | 5K training recipe | CONFOUNDED | "Higher indoor %" = heat avoidance, not treadmill benefit |
| 7 | 10K training recipe | FLAGGED | System correctly detected recency confound |
| 8 | Threshold adaptation | KNOWN | Founder planned the shift deliberately |
| 9 | Weekly pattern | TABLE STAKES | Founder knew the Saturday/Sunday routine |

**Hit rate: 1 genuine out of 9. The system is honest (it flags
confounds) but doesn't suppress enough obvious/confounded findings.**

### Founder Corrections (Critical Context)

1. **July cardiac drift was HEAT, not fitness.** 90-110°F, extreme
   humidity. Low-drift July/August runs were on treadmill. Humidity
   didn't break until October.

2. **Cadence increase was humidity breaking**, not unconscious
   adaptation. Founder tracks cadence closely.

3. **Training mix "flush and rebuild" was deliberate** — heat drove
   founder indoors, then started the structured plan late September.

4. **Easy-pace HR** is a sanity check, not a metric. Too many confounds
   (elevation, temp, humidity).

5. **Finding 6 (negative splits) was FACTUALLY WRONG.** Founder did not
   negative split the 5K. The 10K course was uphill out, downhill back.
   System must use GAP, not raw pace, for split analysis.

6. **Founder ran real doubles in 2024** (84-mile peak week). Those
   aren't Garmin/Strava duplicates.

### The Automation Question

Founder asked: "How is the algorithm going to replace what you just did?
You had to go through findings multiple times and mine again based on
what you found."

Answer agreed on: **Question-based investigations with confound
registries.** Each investigation:
1. Queries specific data it needs
2. Cross-references multiple activities (single-variable suppressed)
3. Checks its own confounds
4. Returns a finding only if it survives

The iterative refinement (mine → find → re-mine) is partially
automatable through the confound registry. What can't be automated is
domain knowledge about what's interesting — but that's encoded in the
investigation library, which grows over time.

---

## What Needs to Happen Next

### Immediate (blocks finding quality)

1. **Weather data backfill** — We have `start_lat`, `start_lng`, and
   `start_time` on every activity. Temperature and humidity exist as
   columns but are only populated for 21/743 activities (all from
   Jan-Feb 2026). A historical weather API call for each activity would
   fill the gap. Without this, the system cannot distinguish fitness
   adaptation from weather changes. This is the single biggest confound.

2. **GAP-adjusted race execution** — `gap_seconds_per_mile` exists on
   splits but appears to be unpopulated for race activities. Need to
   check coverage and ensure it's populated during sync. Without GAP,
   split ratio analysis on hilly courses produces wrong findings.

3. **Suppress single-variable findings** — The engine should not present
   findings that don't cross-reference multiple activities. "Your HR
   dropped" is something the athlete watches. "Your cardiac drift after
   interval + long run pairs decreased over 8 weeks" requires the
   system to compute.

### Architectural (improves hit rate)

4. **Confound registry** — Formalize the mapping:
   ```
   cardiac_drift → [temperature, humidity, indoor/outdoor, elevation]
   split_ratio → [elevation_profile (use GAP)]
   easy_hr → [temperature, humidity, altitude]
   cadence → [terrain, temperature, indoor/outdoor]
   training_recipe → [recency, environment/season]
   ```

5. **More investigation types** — The library should grow:
   - "What's the ROI of your long run progression?" (20km → 35km, did
     it produce measurably better race outcomes?)
   - "Does your interval pace improve over a training block?"
     (controlled for indoor/outdoor and temperature)
   - "What's your optimal rest-day-before-race pattern?"
   - "Do back-to-back quality days help or hurt your next quality
     session?"

### Product Integration

6. These findings need a home in the product. The manifesto says:
   "Visual catches the eye → narrative answers." The findings are the
   narrative. They need visuals (drift trend chart, paired session
   timeline, race execution chart with GAP overlay).

---

## Files Changed This Session

- `apps/api/services/race_input_analysis.py` — Major restructure:
  added environmental context layer, 4 investigation functions,
  restructured `mine_race_inputs()` to run investigations.
  **Not committed yet.** Needs tests before commit.

- `scripts/deep_mine.py` — Temporary analysis script (v1)
- `scripts/deep_mine_v2.py` — Temporary analysis script (v2)
- `scripts/deep_mine_v3.py` — Temporary analysis script (v3)
- `scripts/deep_mine_v4.py` — Temporary analysis script (v4)
- `scripts/check_confounds.py` — Confound data inventory
- `scripts/run_investigations.py` — Investigation runner
  All temporary — can be deleted after findings are validated.

## Production State

Production is healthy. No deploy this session — code changes are local
only. Tree is not clean (uncommitted changes to `race_input_analysis.py`
and temporary scripts).

## Tests

No tests written yet for the new investigations. Existing tests for
the legacy analysis functions should still pass. Test design needed
before commit.
