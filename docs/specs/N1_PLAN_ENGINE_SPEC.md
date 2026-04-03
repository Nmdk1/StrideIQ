# N=1 Plan Engine — Scope

**Date:** 2026-03-28 (updated 2026-04-01: goal-time derivation, volume regression fix)
**Status:** DRAFT — Founder review required before build
**Replaces:** All existing plan generators (archetype, semi-custom, constraint-aware, principle, starter)

---

## 1. What This Is

A single plan generation engine that produces individualized training plans for
athletes from beginner through elite, for 5K through marathon (later: 50K, 50mi,
100mi, 100K). The engine starts from the athlete's actual state — their data,
their history, their races — and uses the knowledge base as a framework of rules
and guardrails. Population constants exist only for cold-start athletes who have
no data.

**One engine. All distances. All levels. N=1.**

---

## 2. What We're Replacing

| Path | File | Status |
|------|------|--------|
| Archetype generator | `services/plan_generator.py` + `plans/*.json` | DELETE — only marathon archetype exists |
| Semi-custom generator | `services/plan_framework/generator.py` | DELETE — NameError crash, framework violations |
| KB-driven generator | `services/plan_framework/kb_driven_generator.py` | DELETE — invented rules, vol_cap = 0.30 |
| Principle generator | `services/principle_plan_generator.py` | DELETE — diverges from framework entirely |
| Starter plan | `services/starter_plan.py` | DELETE — 8-week default with no logic |

**What survives (refactored):**

| Component | File | Role |
|-----------|------|------|
| Orchestrator | `services/constraint_aware_planner.py` | Refactored to call new engine |
| L30 baselines | `services/plan_framework/load_context.py` | Provides athlete history inputs |
| Fitness bank | `services/fitness_bank.py` | N=1 data source |
| Pace engine | `services/plan_framework/pace_engine.py` | RPI → training paces |
| Quality gate | `services/plan_quality_gate.py` | Structural + coaching validation |
| Router | `routers/plan_generation.py` | API endpoint, save function |
| Models | `models.py` (TrainingPlan, PlannedWorkout) | DB schema |

---

## 3. Architecture: Five Steps

### Step 1 — Athlete State Resolution

Resolve the athlete's current state into a standardized input, regardless of
data source (fitness bank, questionnaire, or hybrid).

**Output shape:**

```
current_weekly_miles: float      # trailing 4-week avg (bank) or stated
current_long_run_miles: float    # L30 non-race max (bank) or stated
peak_weekly_miles: float         # historical peak (bank) or stated target
best_rpi: Optional[float]       # from race history or 0.0 (never fabricated)
goal_time_seconds: Optional[int] # athlete-specified target race time
experience_level: enum           # BEGINNER / RECREATIONAL / INTERMEDIATE / ADVANCED / ELITE
days_per_week: int               # athlete-specified, respected absolutely
injury_constraints: list         # from athlete facts
training_recency: enum           # BUILDING / MAINTAINING / REBUILDING / NEW
easy_pace_per_mile: float        # from RPI or stated (for time-based floors)
```

**RPI resolution order (no fabrication):**
1. Race history → `_find_best_race` returns actual RPI (>0)
2. Athlete goal time → `calculate_rpi_from_race_time(distance_m, goal_time_seconds)`
3. No data → `best_rpi = 0.0`, paces omitted (athlete runs by feel)

No default RPI is ever fabricated. The old 45.0 default has been removed.
`_estimate_rpi_from_training` has been deleted — training data cannot reliably
estimate race fitness.

Data-rich athletes: fitness bank → load context → correlation findings.
Cold-start athletes: questionnaire → stated values → conservative defaults.
The engine doesn't care which path produced the input.

### Step 2 — Phase Schedule

Work backward from race day. Allocate phases based on weeks available
and distance. Cutbacks land at phase boundaries.

**Phase allocation rules (compressed for short plans):**

| Distance | Full Plan (16-18w) | Medium (10-12w) | Short (5-8w) |
|----------|-------------------|-----------------|--------------|
| 5K | Base 3 → Cut → Build (T+I) 4 → Cut → Peak 3 → Taper 1 → Race | Base 2 → Build 4 → Cut → Peak 2 → Taper 1 → Race | Build 3 → Cut → Peak 2 → Taper → Race |
| 10K | Base 3 → Cut → Threshold 3 → Cut → Race-spec 3 → Taper 2 → Race | Base 2 → Threshold 3 → Cut → Race-spec 2 → Taper → Race | Threshold 2 → Cut → Peak 2 → Taper → Race |
| Half | Base 3 → Cut → Build 1 (T) 3 → Cut → Build 2 (HMP) 3 → Cut → Peak 2 → Taper 2 → Race | Base 2 → Build 4 → Cut → Peak 2 → Taper → Race | Build 3 → Cut → Peak → Taper → Race |
| Marathon | Base 3 → Cut → Build 1 (T) 3 → Cut → Build 2 (MP) 3 → Cut → Peak 3 → Taper 3 | Base 2 → Build 1 3 → Cut → Build 2 3 → Cut → Taper 2 → Race | REFUSE if < 12 weeks for beginners |

**Abbreviated builds (≤ 5 weeks to race, athlete already fit):**
No periodization phases. No cutbacks. The structure is:
quick ramp (if needed) → peak weeks → taper-race (→ taper-race if tune-up).
All training systems needed for the distance are touched simultaneously
with progressive overload week over week within the allotted peak mileage.
Phase boundaries do not exist — the engine orchestrates threshold, VO2,
race-specific, and neuromuscular work across the peak weeks based on
what the distance demands and what the athlete needs. This is an edge
case that requires the engine to think like a coach compressing a full
build into 3 training weeks, not like a phase allocator.

Athletes already at peak fitness (no ramp needed): skip or shorten base.
Tune-up races: inserted as fixed points; taper wraps around them.

**Readiness gate:** If the athlete cannot support the distance, refuse:
- Marathon: athlete must be able to do a 12mi run BEFORE starting the program.
  If not, they need base building first — offer a base-building plan instead.
  Long runs in a marathon program do not begin below 14mi. Below 14mi is
  just a regular run for someone doing marathon volume.
- Half: must be able to reach 12mi long run within available weeks or refuse.
- For beginners: "You need more base building first. Here's a base-building
  plan instead."

### Step 3 — Volume and Long Run Curves

Two separate curves computed from athlete state.

**Volume curve:**
- Start: `max(current_weekly_miles, recent_8w_median, last_complete_week_miles)` — always meets the athlete where they are
- Peak: athlete-specified or `starting_vol + days_per_week` for abbreviated plans (1 mi per running session build room)
- Abbreviated plan peak is capped at historical `peak_weekly_miles` — never exceeds proven capability. If returning to established peaks, no cap applies.
- Ramp: linear steps, tier-based ceiling (6-8 mi/week for HIGH/ELITE)
- If athlete is already at peak: hold, don't force a ramp
- Cutback: -25%
- Taper: -30% first week, -50% second, race week minimal
- No percentage-based weekly caps. The 10% rule is rejected.
- No distance-specific volume caps. No distance should override an athlete's proven mileage.
- Undershoot handler: when assembled days fall below target weekly volume, shortfall is distributed to easy runs (capped per run at `min(14mi, target_vol/days * 1.6)`).
- **Future (N=1 recovery ceiling):** Use athlete's actual tau1/tau2/HRV signature to set how aggressively they can absorb volume increases. The 1mi/session is a floor; the ceiling should be individualized.

**Long run curve:**
- Start: L30_non_race_max + 1 mile
- Build: +2 mi/week (non-cutback). +3 for experienced with strong history.
- Cutback: 60-70% of prior peak long
- Ceiling by distance:
  - Marathon: 22mi (HIGH/ELITE). For runners targeting slower than 3:45,
    cap at 20mi (a 10:00/mi runner doing 22mi is running 3:40 — the training
    benefit beyond 20mi is outweighed by injury risk and recovery cost).
  - Half: 16-18mi
  - 10K: 18mi
  - 5K: 15mi
- If athlete is already at or above distance-appropriate long run: maintain
- Volume supports long run. Volume is NEVER a cap on long run.
- No time ceiling for athletes who can handle it. The 20mi cap for sub-3:45
  marathoners IS the time-practical ceiling for that population.
- **Long run must be meaningfully above the athlete's daily average.**
  At 55mpw over 6 days, daily avg is ~9mi. A 10mi "long run" is not a
  long run — it's a Tuesday. The long run must actually function as the
  peak aerobic load for the week.
- Marathon long runs do not begin below 14mi. Below that is just a run.

### Step 4 — Quality Session Scheduling

Distance-specific quality work. This is where coaching lives.

**5K — Ceiling race (VO2max is the limiter):**
- Base: strides + hills. Intervals OK on fresh legs.
- Build: VO2 intervals primary (400m → 800m → 1000m progression).
  Threshold secondary (T-block for sustained-hard foundation).
  For advanced runners: 200m and 300m REPS at 1500m pace during build.
  This is neuromuscular ceiling work (rep-pace speed) that makes 5K pace
  feel slow by comparison. Uses `repetitions` stem from registry.
- Peak: 5K-pace specific work. Short, sharp race-rhythm sessions.
- Quality focus: raise the ceiling so 5K pace sits comfortably under it.
  Ceiling = both VO2 (intervals) AND mechanical speed (reps at 1500m pace).

**10K — Threshold race (sustained hard, VO2 ceiling above):**
- Base: strides + hills. Intervals OK on fresh legs.
- Build: Threshold primary (T-block 6-step progression).
  VO2 secondary (ceiling raiser — 800m-1000m at interval pace).
- Peak: 10K rhythm work (1200m at 10K pace, sparse).
  Threshold maintenance. Short sharp VO2 touches.
- Quality focus: T-work IS the 10K. VO2 raises ceiling above it.
- The 5K tune-up (if scheduled) IS the peak VO2 stimulus.

**Half marathon — Sustained hard + race-pace endurance:**
- Base: strides + hills.
- Build 1: T-block (6-step progression).
- Build 2: HMP in long runs (progressive → HMP finish).
  Structure A/B alternation begins.
- Peak: HMP finish long runs (dress rehearsal). T maintenance.
- Quality focus: threshold base → HMP specificity → race simulation.

**Marathon — Endurance + race-pace accumulation:**
- Base: strides + hills. No quality. Volume building.
- Build 1: T-block (6-step progression).
- Build 2: MP integration. Structure A/B alternation.
  MP in long runs — progression is N=1 based on athlete's marathon
  experience, current long run capacity, and tolerance. No fixed ladder.
  Start conservatively, build gradually. The engine computes the right
  MP volume per long run for each athlete, not a population sequence.
  MP in medium-long on select weeks.
- Peak: dress rehearsal. T maintenance.
- Total cumulative MP before taper: 40-50+ miles minimum.
- Quality focus: T-base → MP accumulation → race simulation.
- Long runs in marathon programs do not begin below 14mi.

**Phase rules (all distances):**
- Base: NO quality sessions. Strides and hills only.
  Exception: intervals can live here for short-distance athletes (KB-documented).
- Never ramp volume AND quality simultaneously.
- Max 2 quality sessions per week. Never 3.
- Quality day → easy/recovery day before next quality.
- Saturday before Sunday long = always easy.
- Weekly stimulus ledger determines stride gear on easy days.

**T-block progression (all distances where threshold applies):**

| Step | Session | Scale by tier |
|------|---------|---------------|
| 1 | 6 x 5min @ T, 2min jog | Low: 4x4min, Mid: 5x5min |
| 2 | 5 x 6min @ T, 2min jog | |
| 3 | 4 x 8min @ T, 2min jog | |
| 4 | 3 x 10min @ T, 3min jog | |
| 5 | 2 x 15min @ T, 3min jog | |
| 6 | 30-40min continuous @ T | Low: 20min, High: 40min |

### Step 5 — Day-by-Day Assembly

Given weekly targets + quality prescription + days_per_week:

1. Place long run (Sunday)
2. Place rest (Monday — or athlete-specified rest day)
3. Place quality sessions with spacing rules
4. Saturday before Sunday long = always easy
5. Fill remaining slots with easy / medium-long / recovery
6. Medium-long (typically Tuesday) only for 40+ mpw athletes; 15mi hard cap
7. Apply Structure A/B for marathon/half in build/peak
8. Weekly stimulus ledger → stride gear for easy days
9. Medium-long = 75% of that week's long run distance, capped at 15mi.
   Long = 20mi → MLR = 15mi. Long = 16mi → MLR = 12mi.
10. For fewer days/week: trim easy days first, then medium-long;
    preserve long + quality + rest

**Race/tune-up scheduling:**
- Race day = race workout
- Day before race = pre_race (easy 4-6mi + strides)
- Day after race = rest
- Day after tune-up = easy recovery

---

## 4. Adaptive Re-Plan

When athlete state changes mid-plan (missed week, illness, injury, life event,
or simply feeling stronger than expected):

"Coach noticed you've run 20 miles this week instead of 55 — looks like a
disrupted week. Here's what should change for the remaining weeks and why:
[restructured plan]. Your peak week moved from week 4 to week 5. Your threshold
session intensity stays the same but the cutback shifts."

Athlete: Approve / Modify / Dismiss.

**Implementation:** The engine is stateless — it takes an athlete state and
race goal and produces a plan. Re-planning is calling the engine with updated
inputs (current state mid-plan) for remaining weeks. The system diffs old plan
vs new and presents changes with coaching rationale.

**Never auto-applied.** The athlete decides. The system informs.

---

## 5. Workout Variant Dropdown (Phase 2 — after engine is working)

Each plan day specifies a workout stem and constraints:
`{ stem: "threshold", phase: "build_1", week_in_phase: 2, experience: "advanced" }`

The frontend renders a dropdown of valid variants from the workout registry,
filtered by:
- `build_context_tags` matching current phase
- `when_to_avoid` excluding contraindicated variants
- `pairs_poorly_with` excluding weekly conflicts
- `sme_status == "approved"` only
- Weekly stimulus ledger (no redundant system touches)

The athlete picks what appeals to them today. This keeps them mentally fresh
and gives them agency within coaching constraints. Only valid options are
served — bad choices are not possible.

The 36 approved variants across 4 pilots were built for exactly this purpose.

---

## 6. Acceptance Criteria

A plan is correct when a knowledgeable coach reviews it and says "yes, this
trains the right systems for this race, for THIS athlete."

### Structural (automated)

1. `workout_count_per_week == days_per_week` (±1 race week)
2. `medium_long_miles < long_run_miles` every week
3. No negative mileage
4. No quality sessions in base phase (strides/hills only)
5. Hard day never followed by hard day without easy between
6. Saturday before Sunday long = easy
7. Race day correctly placed; day after race = rest
8. Threshold ≤ 10% of weekly volume per session
9. Intervals ≤ 8% of weekly volume
10. Easy/recovery volume ≥ 70% of weekly total

### Coaching Quality (parametric matrix — the real test)

**For every (distance × experience × weeks_to_race) combination:**

| Check | Rule |
|-------|------|
| Long run floor | Week 1 long ≥ L30_max + 1 for data-rich athletes |
| Long run build | Non-cutback weeks: long_n ≥ long_(n-1) + 1 (up to ceiling) |
| Long run ceiling | Respects distance caps; N=1 override when history exceeds |
| Long run minimum for marathon | Never below 14mi; below that is not a long run |
| Long run vs daily avg | Long run must be meaningfully above daily average (no 10mi "long" at 55mpw) |
| Marathon long cap (sub-3:45) | 20mi max for runners targeting slower than 3:45 marathon |
| Medium-long sizing | 75% of long run distance, hard cap 15mi |
| Volume curve | Increases toward stated peak; no ramp if already there |
| Quality timing | No quality while volume is ramping (first N weeks) — except abbreviated builds |
| T-block progression | Threshold sessions show progression across weeks |
| Distance-appropriate quality | 5K has intervals + reps (200/300 at 1500 pace for advanced); 10K has threshold + VO2; marathon has MP accumulation |
| MP progression | N=1, not a fixed ladder; no population-default step sequence |
| MP accumulation (marathon) | Cumulative MP ≥ 40mi before taper |
| Cutbacks at boundaries | Not `week % N == 0`; at phase transitions. No cutbacks in abbreviated builds. |
| Phase names | Every week has a labeled phase (or "peak" for abbreviated builds) |
| Readiness gate | Marathon refuses if athlete can't do 12mi before starting the program |
| Cold-start safety | Beginner plans are conservative; no aggressive workouts early |
| Day-one athletes | Never-ran athletes get walk/run progression, not a race plan |

### Qualitative (founder review)

The 12 synthetic athletes in `eval_realistic_athletes.py` serve as the
qualitative test. For each:
- Does the plan make sense for who they are?
- Would a real coach prescribe this?
- Are the workout types appropriate for the distance and the athlete's level?

**The gold standard:** If a plan gives an experienced runner a long run under
14mi, it is wrong. If a 3-day/20mpw beginner gets a marathon plan, it is wrong.
If a 10K plan has no intervals or VO2 work, it is wrong.

---

## 7. Cold-Start Path

**Athlete on day 1, no sync, no data:**

Ask: Current weekly miles, longest recent run, days per week, race goal,
race date, how long they've been running.

Use stated values. Apply conservative defaults:
- Experience = BEGINNER if < 2 years
- Long run floor = stated longest run (no L30 computation)
- Volume = stated weekly miles
- Paces = effort descriptions only (no RPI)
- Progression = conservative (smaller steps, more cutbacks)

Flag every assumption. As data comes in (first synced week, first race),
recalibrate and offer a re-plan.

**For true beginners (never ran before):**

If they want a marathon and can't do 12mi before starting, they need base
building first. If they've never run at all, they need a walk/run progression
before ANY race plan.

**Couch to 10K — Beginner with No Injury (founder-specified):**

This is the standard plan for an athlete who has never run before.
Founder's exact words:

> "Get them to walk 1 mile, run 1 mile, walk 1 mile for the first
> 6 days and on day seven run 3 miles - repeat for week 2. Week three
> walk 1 mile run 2 miles per day for 6 days, then 4 on day 7. Do that
> for three weeks then increase to 3 miles per day with 6 mile long run -
> three weeks. Then 4 miles per day with 8 mile long run. 3 weeks - this
> is 9 weeks - taper and do the 5k. This is the couch to 10k."

| Weeks | Daily (6 days) | Day 7 (Long Run) | Weekly Volume |
|-------|---------------|-------------------|---------------|
| 1-2 | Walk 1mi, Run 1mi, Walk 1mi | Run 3mi | ~21mi |
| 3 | Walk 1mi, Run 2mi | Run 4mi | ~22mi |
| 4-6 | Run 3mi | Run 6mi | ~24mi |
| 7-9 | Run 4mi | Run 8mi | ~32mi |
| 10+ | Taper → Race 5K/10K | | |

This is one archetype within a generator that serves the full spectrum
from couch to elite. The engine detects when a day-one athlete needs
this path and serves it. It must handle edge cases and different
distances — not every beginner wants a 10K. But this progression is
the standard foundation.

The beginner plan is NOT tuned to any one athlete — it is the
population-safe starting point for someone with zero running history.

---

## 8. Migration Plan

### Phase 0: Cleanup (before building anything)
- One commit removes all old generators + their tests
- Surviving infrastructure keeps its tests
- CI drops from ~12 min to ~6-8 min
- Codebase is clean for the build

### Phase 1: Build Engine (5K through marathon)
- New module: `services/plan_framework/n1_engine.py` (or similar)
- New test suite: coaching quality matrix tests
- Build iteratively: volume curve → long run curve → phase schedule →
  quality scheduling → day assembly
- Qualitative eval after each step
- Founder review before deployment

### Phase 2: Deploy + Validate
- Wire to existing API endpoint
- Generate plans for real athletes (founder first)
- Verify against fitness bank data
- Deploy to production

### Phase 3: Variant Dropdown
- Wire workout registry to plan output
- Build frontend dropdown
- Filter by build_context_tags, weekly ledger, contraindications
- Athlete selects variant, system serves execution guidance

### Phase 4: Adaptive Re-Plan
- "Coach noticed..." trigger system
- Diff engine (old plan vs new)
- Athlete approval flow (approve / modify / dismiss)

---

## 9. What This Does NOT Cover (Explicitly Out of Scope for V1)

- Distances beyond marathon (50K, 50mi, 100K, 100mi) — later phase
- Cross-training integration
- Strength/mobility programming
- Dynamic mid-week adjustments (daily readiness → auto-swap)
- Multi-race season planning
- Workout variant dispatch to frontend (Phase 2-3)

---

*This scope defines what we build and how we know it works. Implementation
details (class structure, function signatures, module organization) are
engineering decisions made during the build.*
