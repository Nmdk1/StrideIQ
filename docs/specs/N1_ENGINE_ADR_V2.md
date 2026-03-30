# ADR: N=1 Plan Engine V2 — Rebuild

**Date:** 2026-03-28
**Status:** DRAFT — Founder approval required before any code
**Decision:** Rebuild the N=1 plan engine to pass 12 coaching-quality blocking criteria

---

## Context

The current `n1_engine.py` (690 lines) was built without adequate understanding
of the knowledge base. It produces plans that fail coaching review: monotonous
long runs, formulaic MP scheduling, no midweek quality variation, fixed T-block
ladder as the only threshold format, hard-coded "max 2 quality/week" cap, and
cutbacks by position math instead of coaching intent.

The founder's standard: a world-class coach would hand this plan to their athlete
with confidence. The current engine does not meet this standard.

**Precondition for the builder:** Before Phase 0 begins, the builder must have
read and be able to cite specific rules from `PLAN_GENERATION_FRAMEWORK.md`,
`TRAINING_PHILOSOPHY.md`, `TRAINING_METHODOLOGY.md`, `03_WORKOUT_TYPES.md`,
`04_RECOVERY.md`, and ALL pilot variant docs (`easy_pilot_v1.md`,
`threshold_pilot_v1.md`, `intervals_pilot_v1.md`, `repetitions_pilot_v1.md`,
`long_run_pilot_v1.md`). If the builder cannot explain why a workout appears
on a given day, they have not read the KB.

---

## Decision

Rebuild the engine to pass 12 blocking criteria agreed with the founder before
any code ships. The build is test-first: the evaluator that checks these criteria
is built BEFORE the engine changes, so every change is validated immediately.

---

## Athlete Inputs

The plan request accepts the following athlete-specified parameters. These are
respected absolutely — the engine never overrides them.

| Input | Source | Notes |
|-------|--------|-------|
| `race_date` | Request | Target race date |
| `race_distance` | Request | `5k`, `10k`, `half_marathon`, `marathon` |
| `days_per_week` | Request or intake questionnaire | 3-7 days. Respected absolutely. |
| `rest_days` | Request or fitness bank detection | List of day-of-week ints (0=Mon..6=Sun). Athlete selects which days are rest. |
| `long_run_day` | Request or fitness bank detection | Day-of-week int. Defaults to Sun (6) if not specified. |
| `target_peak_weekly_miles` | Request | Athlete's chosen peak mileage target |
| `goal_time_seconds` | Request (optional) | Goal finish time |
| `tune_up_races` | Request (optional) | List of tune-up races with dates |

The current API (`ConstraintAwarePlanRequest`) needs `days_per_week`, `rest_days`,
and `long_run_day` added as optional fields. If absent, inferred from fitness bank
(`typical_rest_days`, `typical_long_run_day`) or defaulted (rest=Mon, long=Sun).

**Variant selector:** Each plan day includes a `workout_stem` and `phase_context`
enabling the frontend to render a dropdown of valid workout variants from the
registry. Implementation of the frontend dropdown is a separate frontend rollout
phase (out of scope for this engine build) but the data shape is emitted from
day one so the contract is stable.

---

## 12 Blocking Criteria (Founder-Agreed)

Every generated plan must pass ALL automated criteria. If any fails for any
archetype in the core gate set, the build does not proceed.

**Gate categories:**
- **Automated gates (BC-1 through BC-7, BC-9 through BC-12):** Machine-checked
  by the evaluator. Hard fail = build blocked.
- **Founder review gate (BC-8):** Human judgment. Required sign-off on archetypes
  6, 7, 10, 12, and any archetype that changes substantially during iteration.

### BC-1: Weekly structure is athlete-appropriate

Quality density is N=1 — no universal caps. The evaluator checks against this
rule table:

| Distance | Experience | Days/wk | Quality sessions/week (range) |
|----------|------------|---------|-------------------------------|
| marathon | any | any | 1–2 (quality long counts as 1) |
| half_marathon | any | any | 1–2 |
| 10k | beginner | any | 0–1 |
| 10k | intermediate | any | 1–2 |
| 10k | experienced/elite | 5+ | 1–3 |
| 5k | beginner | any | 0–1 |
| 5k | intermediate | any | 1–2 |
| 5k | experienced/elite | 5+ | 1–3 |

**Exception:** Athletes with ≤3 days/week may have all days be quality if
experience is intermediate or above.

**Phase modifiers:** Base phase has 0 quality (strides/hills only) unless
the athlete is experienced+ doing 5K/10K (intervals OK in base on fresh legs).
Cutback weeks: 0 quality. Taper weeks: 1 sharpening session per week
(aligned with BC-11 — taper is sharp, not just reduced).

**What counts as "quality":** Threshold, intervals, repetitions, MP long,
HMP long, race-pace work. Strides, hill sprints, and easy+strides do NOT
count as quality sessions.

### BC-2: Plan tells a progressive, purposeful story

Reading week 1 through race week, periodization is visible and logical.
A coach can see where this athlete will peak, how quality evolves, where
the race-specific work appears.

**Evaluator check:** Every week has a phase label. Phase sequence follows a
logical order (base→build→peak→taper, with distance-appropriate sub-phases).
No phase appears after a later phase (no "build" after "peak").

### BC-3: Long runs vary meaningfully

**Definition of "peak zone":** Weeks where long_run_miles ≥ (plan's max
long run distance − 2mi). Within this zone, no two consecutive long runs
differ by less than 2 miles. Type variation across the plan: easy longs,
MP longs, fast-finish longs, progressive longs, cutdown longs.

**Short-plan waiver:** For plans ≤8 weeks or where the peak zone contains
≤2 weeks, BC-3 is satisfied if long run TYPE varies (even if distance
cannot vary meaningfully). For abbreviated builds (≤5 weeks), BC-3 is
waived entirely.

### BC-4: Quality targets specific adaptations and progresses

Threshold work progresses — with variety (cruise intervals, continuous
progression 25→30→35→40min, alternating formats, broken threshold). Not a
single ladder repeated. MP work progresses inside long runs (N=1, not a
fixed fraction formula). Intervals match goal distance ceiling needs.
Repetitions (200/300m) present for 5K. Every quality session answers "what
adaptation does this produce?"

**Evaluator check:** No two threshold sessions in the plan have identical
format AND duration. MP mileage per long run increases across the build
(not necessarily every consecutive MP week, but trending). For 5K plans
with experienced+ athletes, at least 1 rep session exists.

### BC-5: Every workout has a "why"

No filler days. Even easy days serve recovery from yesterday or preparation
for tomorrow.

**Evaluator check:** This is partially human-judgment. The automated check
verifies that easy day mileage varies (post-quality easy is lighter than
standalone easy, pre-long-run easy is lighter). Not all easy days identical.

### BC-6: Recovery architecture is intelligent

Cutback weeks at phase transitions (not modulo math). Cutback volume
genuinely reduced (volume ≤ 75% of prior non-cutback week). Easy/recovery
around every quality session. Quality never adjacent to quality without
recovery between. Day before long run is easy or rest.

**Short-plan waiver:** Abbreviated builds (≤5 weeks) have no cutback weeks.
Plans ≤8 weeks may have 0-1 cutback weeks.

### BC-7: Plan is individualized to THIS athlete

A beginner gets fundamentally different workout selection, not just scaled
numbers. An advanced 3-day/week athlete gets all quality days. An athlete
with no race data gets effort descriptions, not paces. An athlete with a
5-week horizon gets a compressed plan. An athlete returning from injury
gets conservative progression and lower ceilings.

**Evaluator check:** Generate plans for archetypes that differ only in one
dimension (e.g., same distance, different experience). Verify the plans
are structurally different (different workout types, not just different
numbers).

### BC-8: World-class coach would hand this to their athlete (MANUAL GATE)

Full plan dump, every day, every week. Read it like a coach. Would you
hand this to an athlete and feel confident?

**This is a founder review gate.** It is not machine-checked. The builder
generates full plan dumps for archetypes 6, 7, 10, 12 and the founder
reviews them. Sign-off required before deploy.

### BC-9: Volume sawtooth pattern

Build-build-cutback-build higher. Visible in the mileage column. Not flat,
not monotonic, not erratic.

**Evaluator check:** For non-abbreviated plans with ≥10 weeks: identify
cutback weeks (volume ≤ 75% of prior). The week after a cutback must
exceed the week before the cutback (build higher). The overall volume
trend is upward toward peak.

**Short-plan waiver:** Abbreviated builds (≤5 weeks) are exempt — no
cutbacks, volume may be flat at peak.

### BC-10: Race-specific accumulation is sufficient

Backward-planned from race day.

**Marathon MP accumulation floor:**

| Experience | Horizon ≥16w | Horizon 12-15w | Horizon <12w |
|------------|-------------|----------------|-------------|
| Experienced/Elite | ≥40mi | ≥30mi | ≥20mi |
| Intermediate | ≥30mi | ≥20mi | ≥15mi |
| Beginner | N/A (readiness gate refuses) | N/A | N/A |

MP miles are counted as the portion of the long run at marathon pace,
not the entire long run distance.

**10K:** At least 4 threshold sessions and at least 2 VO2/interval sessions
before taper.

**5K:** At least 3 interval sessions and at least 1 rep session (for
experienced+) before taper.

### BC-11: Taper is sharp, not just reduced

Volume drops 30-50% in first taper week, further to 50-65% off peak by
race week. Intensity maintained: at least 1 sharpening session per taper
week (short threshold touch, strides, brief intervals). The athlete arrives
fresh AND sharp.

**Evaluator check:** Taper week volume < 75% of peak volume. At least
one workout in each taper week has intensity != "easy" and != "rest"
(strides count).

### BC-12: Paces from data, effort descriptions without it

When `best_rpi` exists: specific paces from Training Pace Calculator appear
in workout descriptions (e.g., "7:15/mi").

When `best_rpi` is absent: NO numeric pace strings appear anywhere in the
plan. Only effort descriptors ("comfortably hard", "conversational",
"5K race effort", etc.).

**Evaluator check:** Regex scan of all workout descriptions. If the
archetype has `rpi: None`, any match of `\d{1,2}:\d{2}\s*/mi` is a
hard fail.

---

## What's Wrong With the Current Engine (mapped to criteria)

| Criterion | Current Engine Violation |
|-----------|------------------------|
| BC-1 | Hard cap `wq[:2]` — max 2 quality sessions regardless of athlete/distance |
| BC-2 | Formulaic phase allocation by proportions — no coaching intent in transitions |
| BC-3 | Long runs increase monotonically to ceiling, then repeat at ceiling. No variation in type or distance at peak |
| BC-4 | `T_BLOCK_STANDARD` is the only threshold format. No variation. MP uses fixed fraction formula (`0.25 + idx * 0.08`) |
| BC-5 | Easy days are uniform fill. No structural purpose differentiation |
| BC-6 | Cutbacks by `is_last and count >= 3` — position math, not phase-boundary coaching |
| BC-7 | Same algorithm for all athletes, scaled by constants only. Rest days hardcoded to Monday, long run to Sunday |
| BC-9 | Volume curve is smooth ramp with uniform cutbacks — no sawtooth coaching shape |
| BC-10 | MP accumulation logged but not architecturally planned backward from race day |
| BC-11 | Taper has NO quality — `quality_map[wt.week_number] = []` for all taper weeks |

---

## Build Sequence

### Phase 0: Build the Plan Quality Evaluator (BLOCKER — before any engine work)

**Depends on:** Nothing. First thing built.

Build `scripts/eval_plan_quality.py` that:

1. Generates plans for the 14-archetype core gate set (see table below).

2. For each generated plan, dumps EVERY day of EVERY week in human-readable
   format: week number, phase, day-of-week, workout type, name, miles,
   description.

3. Checks each automated BC (1-7, 9-12) programmatically per the evaluator
   rules defined above.

4. For BC-8 (manual gate): outputs the full plan dump to stdout/file for
   founder review.

5. Reports PASS/FAIL per criterion per archetype. Summary at end.

**This evaluator runs against the CURRENT engine first** to establish the
baseline of failures, then validates every subsequent engine change.

### Phase 1: Fix Long Run Curve + Volume Sawtooth (BC-3, BC-9)

**Depends on:** Phase 0 (evaluator exists to validate changes).

The long run column must tell a story:

- Post-cutback long runs return to near previous peak (not gradual rebuild)
- Peak long runs alternate distances (20→22→20 or 21→22→18mp — not 22→22→22)
- Long run TYPE varies: some weeks easy, some MP, some fast-finish, some progressive
- Volume sawtooth: build-build-cutback-build higher — shaped at phase boundaries

### Phase 2: Fix Quality Session Scheduling (BC-1, BC-4, BC-10, BC-11)

**Depends on:** Phase 1 (long run curve must exist before quality schedules around it).

- Remove universal 2-quality cap. Quality density per the BC-1 rule table.
- Threshold variety: cruise intervals, continuous progression, alternating formats.
  The rule is progression, not one fixed ladder.
- MP scheduling is N=1: backward-planned from total MP accumulation target.
  MP touches in medium-long runs on select weeks. MP in long runs spaced
  2-4 weeks apart, never consecutive.
- Intervals when ceiling-raising is needed (not base-only restriction).
- Taper keeps quality: strides, short threshold, brief sharpening.
- Repetitions (200/300m at 1500m pace) for 5K experienced+.
- Athlete rest days + long run day respected in assembly.

### Phase 3: Fix Day-by-Day Assembly (BC-5, BC-6, BC-7)

**Depends on:** Phase 2 (quality sessions must be scheduled before assembly places them).

- Easy days have purpose: post-quality is lighter, pre-long is lighter.
- Strides placed intelligently based on weekly stimulus already covered.
- Medium-long never day-after-long or day-before-quality.
- Structure A/B alternation for marathon/half produces visible weekly rhythm.
- Athlete-specified rest days and long run day respected (not hardcoded Mon/Sun).
- Weekend quality for shorter distances where appropriate.

### Phase 4: Validate and Iterate

**Depends on:** Phases 1-3.

- Run evaluator against rebuilt engine for all 14 archetypes
- Generate full plan dumps for archetypes 6, 7, 10, 12, 14
- Fix any automated BC failures (builder fixes and re-runs autonomously)
- Present dumps to founder for BC-8 sign-off
- Iterate until all BCs pass

**Iteration protocol:** For BC-1 through BC-7 and BC-9 through BC-12, the
builder fixes failures and re-runs the evaluator without founder involvement.
BC-8 requires founder review on each pass. This prevents fix-one-break-another
cycles from burning budget while ensuring the coaching judgment gate is real.

### Phase 5: Validate Wiring + Deploy

**Depends on:** Phase 4 (all BCs pass).

The orchestrator (`constraint_aware_planner.py`) and API endpoint already wire
to the engine. This phase validates the existing wiring works with the rebuilt
engine, adds the new athlete input fields, and deploys.

- Add `days_per_week`, `rest_days`, `long_run_day` to `ConstraintAwarePlanRequest`
- Lift the `max(3, min(6, ...))` clamp in `constraint_aware_planner.py` to
  permit 7-day plans end-to-end (archetype 14 requires this). The request
  schema already allows 3-7; the planner normalization must match.
- Verify orchestrator passes new fields through to engine
- CI green
- Deploy to production
- Smoke test against founder's account (`dry_run=true`)

---

## Core Gate Set: 14 Archetypes

| # | Name | mpw | Days | LR | Exp | Distance | Weeks | RPI | Notes |
|---|------|-----|------|----|-----|----------|-------|-----|-------|
| 1 | Day-one beginner | 0 | 6 | 0 | BEG | 10k | 12 | no | Couch-to-10K path (see BC waivers below) |
| 2 | Casual 5K | 15 | 4 | 5 | BEG | 5k | 8 | no | Conservative, effort-based paces |
| 3 | Building half | 25 | 5 | 8 | INT | half_marathon | 16 | yes | Needs volume ramp |
| 4 | Competitive 10K | 40 | 6 | 12 | EXP | 10k | 12 | yes | 2-3 quality/week |
| 5 | Marathon first-timer | 35 | 5 | 12 | INT | marathon | 18 | yes | Full build, conservative |
| 6 | Advanced marathoner | 55 | 6 | 18 | EXP | marathon | 18 | yes | MP in long + MLR, T-block variety |
| 7 | Elite 5K | 50 | 6 | 14 | ELI | 5k | 12 | yes | 3 quality/week, reps + intervals + threshold |
| 8 | 3-day athlete | 20 | 3 | 8 | INT | half_marathon | 12 | yes | All quality days |
| 9 | Abbreviated 10K | 45 | 6 | 14 | EXP | 10k | 5 | yes | No periodization, compressed |
| 10 | High-mileage marathon | 70 | 6 | 20 | ELI | marathon | 16 | yes | MP long + threshold same week OK |
| 11 | Slow marathoner | 30 | 5 | 10 | INT | marathon | 18 | no | 20mi LR cap, effort descriptions |
| 12 | Founder profile | 55 | 6 | 15 | EXP | 10k | 10 | yes | Intervals + threshold + hard long |
| 13 | Injury comeback | 20 | 4 | 6 | EXP | half_marathon | 14 | yes | Was 45mpw, `injury: achilles_tendinopathy`, conservative rebuild |
| 14 | Tune-up marathoner | 60 | 7 | 18 | EXP | marathon | 16 | yes | Has tune-up 5K at week 12, tests pre-race/post-race scheduling |

**Key:** BEG=Beginner, INT=Intermediate, EXP=Experienced, ELI=Elite

**Note on archetype 11:** The slow marathoner at 30mpw with a 20mi LR cap will
accumulate fewer MP miles than a high-volume athlete. BC-10 uses the tier-scaled
threshold (30mi for intermediate) rather than the universal 40mi floor.

**Note on archetype 1 (Couch-to-10K BC waivers):** Archetype 1 follows the
Couch-to-10K code path, which produces walk/run progressions — not periodized
training plans. The following automated BCs are **waived** for this archetype
because their failures are correct behavior, not bugs:
- BC-3 (long run variation — walk/run has no coaching-sense "long runs")
- BC-4 (quality progression — no quality sessions in walk/run)
- BC-9 (volume sawtooth — progressive ramp, no cutbacks)
- BC-10 (race-specific accumulation — not applicable to walk/run)
- BC-11 (taper sharpening — taper is just easy + race day)

BCs that still apply: BC-1, BC-2, BC-5, BC-6, BC-7, BC-12.

**Note on archetype 13:** Injury comeback athletes are `EXPERIENCED` by history
but constrained by current state. The engine input includes
`injury_constraints: ["achilles_tendinopathy"]` so the engine applies lower
ceilings and conservative progression distinct from a healthy rebuilder at the
same volume. Without the injury constraint in the input, the engine would treat
this as a normal rebuilding athlete — which is wrong.

This is the **core gate set** — the canonical 14 archetypes that define pass/fail.
Additional exploratory archetypes may be added for edge-case testing but are not
gating.

---

## What We're NOT Changing

- Orchestrator (`constraint_aware_planner.py`) — keeps its wiring role
- Fitness bank, pace engine, load context — data sources stay
- API endpoint structure, DB models — infrastructure stays
- Quality gate (`plan_quality_gate.py`) — stays but rules may be updated
  to align with the 12 BCs
- Couch-to-10K path — stays (founder-specified, implemented in current
  `n1_engine.py` lines 955-1014, verified functional)

**New API fields added in Phase 5:** `days_per_week`, `rest_days`, `long_run_day`
on `ConstraintAwarePlanRequest`. These are additive (optional with defaults),
not breaking changes.

---

## Variant Selector Contract

Each plan day emits:

```
{
  "workout_stem": "threshold",         # e.g., threshold, intervals, long_mp, easy
  "phase_context": "build_1",          # current phase
  "week_in_phase": 2,                  # position within phase
  "experience": "experienced",         # athlete's level
  "stimulus_already_covered": ["vo2"]  # what this week already touches
}
```

This enables the frontend (separate frontend rollout phase, out of scope for
this engine build) to render a dropdown of valid variants filtered by
`build_context_tags`, `when_to_avoid`, `pairs_poorly_with`, and
`sme_status == "approved"` from the workout registry. The athlete picks;
the system serves only valid options.

The data shape is emitted from day one of the rebuild so the contract is stable
when the frontend is built.

---

## Success Criteria

The engine ships when:

1. All automated BCs (1-7, 9-12) pass for all 14 core archetypes
2. BC-8: Founder reviews full plan dumps for archetypes 6, 7, 10, 12, 14
   and signs off
3. CI green
4. Production deployment successful
5. Founder generates a plan on their own account and confirms quality

---

## Risk

The primary risk is the same one that caused the first failure: building
code without understanding the coaching. The mitigations:

1. **KB reading precondition** — builder must demonstrate understanding
   before Phase 0 begins
2. **Phase 0 evaluator** — establishes the failure baseline and validates
   every subsequent change
3. **14 diverse archetypes** — catch archetype-specific failures
4. **Tiered gate structure** — automated checks prevent regression; human
   review catches what automation cannot
5. **Iteration protocol** — builder iterates autonomously on automated BCs,
   only blocks on BC-8 for founder review

---

*This ADR replaces the previous scope. `N1_PLAN_ENGINE_SPEC.md` remains
as reference for architectural decisions; this ADR governs what gets built
and in what order.*
