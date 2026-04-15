# Builder Instructions: Training Lifecycle Product

**Date:** April 10, 2026
**Status:** APPROVED — build when founder says GO
**Depends on:** Nothing (independent of Nutrition Planning and Coach Tier)
**Estimated effort:** 2 sessions (Phase 1+2 in session 1, Phase 3+4 in session 2)
**Priority:** Critical — this is the scale play. Fixes day-one retention and empty-calendar churn.

---

## Read Order (mandatory)

1. `docs/FOUNDER_OPERATING_CONTRACT.md`
2. `docs/TRAINING_PLAN_REBUILD_PLAN.md` (current plan architecture, phase status)
3. This file (build instructions)
4. `apps/api/models.py` — `TrainingPlan` (line ~1504), `PlannedWorkout` (line ~1553)
5. `apps/api/services/plan_framework/n1_engine.py` — the race plan generator (study `AthleteState`, `plan_weeks`, `assemble_plan`, `_make_day`, `_long_run_day`, `_easy_day`, `_rest_day`, variant dispatch)
6. `apps/api/services/fitness_bank.py` — `FitnessBank` and `FitnessBankCalculator` (this is your primary input for Build/Maintain modes)
7. `apps/api/services/constraint_aware_planner.py` — the race plan wrapper (DO NOT modify, study only)
8. `apps/api/routers/plan_generation.py` — existing endpoints
9. `apps/api/tasks/garmin_webhook_tasks.py` — first-session sweep trigger (line ~935)
10. `apps/web/app/home/page.tsx` — where the first-session card lives
11. `apps/web/app/plans/create/page.tsx` — existing plan creation UI (keep for power users)

---

## What This Is

The plan generator today only supports race plans. Every path requires a race date
and a race distance. This means:

- A new athlete who connects Garmin sees an empty calendar until they manually
  create a race plan.
- An athlete between races has no plan. Calendar goes empty. They drift.
- An athlete who does not race (maintenance runners, base builders, off-season
  athletes) cannot use the plan generator at all.

This feature adds three new plan modes (Build, Maintain, Custom), automates the
first-session flow from Garmin connect to populated calendar, eliminates empty
calendars through auto-renewal and post-race transitions, and replaces the
13-step plan creation wizard with a one-tap mode selection for first-time users.

**This is the single most important feature for scale.** Runna's most requested
feature is plan continuity. Their athletes hate starting from scratch every plan.
We solve this at the architecture level — the calendar never goes empty.

---

## Philosophy

1. **Free on day one.** Build and Maintain plans are free tier. An athlete who
   connects Garmin and taps "Getting Faster" gets a plan immediately. No paywall
   on the first plan. Custom week designer and auto-renewal are Pro features.

2. **Earned, not given.** The first-session flow drops the athlete into plan
   selection AFTER their first correlation findings appear. Sequencing:
   data arrives → insights surface → "Here's what your data shows. Here's a plan
   built around it." The plan feels earned because the athlete just saw what the
   platform learned about them.

3. **The athlete decides.** Build, Maintain, Custom, Race — the athlete picks
   their mode. The system never auto-generates a plan without the athlete choosing.
   The system DOES auto-renew plans the athlete opted into (Build/Maintain).

4. **N=1 from the start.** Every plan — including the free ones — uses the
   athlete's actual paces (RPI), actual volume (FitnessBank), actual days per
   week (from Garmin history), and actual recovery rate (fingerprint when available).
   No "beginner/intermediate/advanced" questionnaire. The data speaks.

5. **Extension is the progression, not speed.** Within a training block,
   workouts progress by increasing the duration of effort at the SAME pace,
   not by increasing the pace of the same duration. Example: 400s at 5:50 →
   800s at 5:50 → 1200s at 5:50 → miles at 5:50. Same pace, longer hold.
   Threshold: 6×5min → 3×9min → 2×14min at the same pace. This is the modern
   approach (Davis, Canova). It yields faster adaptation, lower biomechanical
   load, and directly measures the capability the marathon demands — sustaining
   a pace for longer. The plan generator MUST use extension-based progression
   within each workout category.

6. **Build over build — the system remembers.** Each successive training block
   must progress from where the previous block ended. If Block 1 ends with the
   athlete doing 1200s at 5:50, Block 2 does NOT start back at 400s at 5:50.
   Block 2 starts at or near Block 1's midpoint (800s at 5:50) and peaks at a
   new level (miles at 5:45, or 2K reps at 5:50). The auto-renewal task MUST
   read the previous block's peak workout data (max extension achieved, pace
   held) and use it to seed the next block's starting point. This is the
   difference between a plan generator and a training system.

---

## Knowledge Base References (mandatory reading for builder)

The plan generator's workout structures, periodization, and progression logic
are grounded in a coherent coaching knowledge base. Read these before building:

1. `docs/references/DAVIS_MODERN_MARATHON_APPROACH_REFERENCE_NOTE_2026-04-10.md` — the full framework: percentage-based pacing, three-phase periodization, full-spectrum training, alternating-km workout structures, and the 13-week worked example
2. `docs/references/DAVIS_FIVE_PRINCIPLES_MARATHON_TRAINING_2026-04-10.md` — the four components of marathon fitness (VO2max, SSmax, Running Economy, Resilience) and the five principles that govern plan design
3. `docs/references/SSMAX_STEADY_STATE_MAX_REFERENCE_NOTE_2026-04-10.md` — the intensity boundary between sustainable and unsustainable work; defines which workouts are sub-SSmax vs supra-SSmax
4. `docs/references/COE_STYLE_TRAINING_REFERENCE_NOTE_2026-04-10.md` — multi-pace variety, Canova's "add not replace" principle, strength periodization
5. `docs/references/DAVIS_MARATHON_BUILD_SAMPLE_2026-04-10.md` — a 2-week sample schedule that serves as the quality bar for workout descriptions

**The generator's output should be indistinguishable in quality from these
reference plans.** If a generated workout description is vaguer, less specific,
or less structured than the Davis sample, it fails the quality bar.

---

## Phase 1: Model Changes + Build/Maintain Generators

### Migration

Chain to the latest Alembic head. One migration file.

**TrainingPlan changes:**

| Column | Change | Details |
|--------|--------|---------|
| `goal_race_date` | `nullable=False` → `nullable=True` | Build/Maintain/Custom have no race |
| `goal_race_distance_m` | `nullable=False` → `nullable=True` | Same |
| `auto_renew` | NEW `Boolean, default=False` | True for Build/Maintain/Custom |
| `block_length_weeks` | NEW `Integer, nullable=True` | Default 4. How many weeks per block |
| `block_number` | NEW `Integer, default=1` | Current block count for Build/Maintain (increments on renewal) |
| `peak_workout_state` | NEW `JSONB, nullable=True` | Stores peak extension + pace per workout category at block end (for build-over-build seeding) |
| `week_template` | NEW `JSONB, nullable=True` | For Custom mode only |

**plan_type accepted values (documentation, not enum constraint):**
Existing: `'5k'`, `'10k'`, `'half_marathon'`, `'marathon'`, `'base_build'`
New: `'build'`, `'maintain'`, `'custom'`

**generation_method values:**
Existing: `'ai'`, `'template'`, `'custom'`
No changes needed. Build/Maintain use `'ai'`. Custom uses `'custom'`.

### Build Mode Generator

**New file: `apps/api/services/plan_framework/general_plan_generator.py`**

DO NOT modify `n1_engine.py`. DO refactor shared primitives out of it if needed
(e.g., extract `_make_day`, `_long_run_day`, `_easy_day`, `_rest_day`, variant
dispatch into a shared module that both files import).

**Inputs** (all derived from `FitnessBank` — no athlete form input needed):

- `current_weekly_miles` — from FitnessBank
- `current_long_run_miles` — from FitnessBank
- `best_rpi` — from FitnessBank (for pace computation)
- `experience` — from FitnessBank
- `days_per_week` — from FitnessBank recent activity patterns
- `fingerprint` — from FitnessBank (cutback frequency, quality spacing)

**4-week block structure:**

| Week | Volume | Quality Sessions | Long Run |
|------|--------|-----------------|----------|
| W1 | current | 1 (threshold type) | current LR |
| W2 | +5-7% | 1-2 (add speed if experienced) | +1 mi |
| W3 | +10-12% (block peak) | 2 | +1 mi (block LR peak) |
| W4 | -15% cutback | 1 easy quality OR strides only | -2 mi cutback |

Adaptation needs for workout type selection:
- Always: `AEROBIC_BASE`, `THRESHOLD`
- Intermediate+: add `CEILING`
- Experienced+: add `NEUROMUSCULAR`
- No `RACE_SPECIFIC` (no race to be specific about)

Quality type rotation across blocks:
- Block 1: threshold focus (cruise intervals, tempo)
- Block 2: speed focus (track intervals, fartlek)
- Block 3: mixed (threshold + speed)
- Block 4+: repeat cycle

### Extension-Based Workout Progression (within each block)

Each workout category progresses by increasing EXTENSION (segment duration)
at a STABLE PACE across the 4-week block. The pace is set from RPI at the
start of the block and does NOT increase week-over-week.

**Speed/interval category example:**
- W1: 6×400m at RPI-derived 5K pace (e.g. 5:50/mi) — 2min jog
- W2: 5×800m at same pace — 2min jog
- W3: 4×1200m at same pace — 2min jog
- W4: cutback — 4×400m at same pace OR strides only

**Threshold category example:**
- W1: 6×5min at RPI-derived threshold pace — 1min jog
- W2: 4×7min at same pace — 1min jog
- W3: 3×10min at same pace — 1min jog
- W4: cutback — 3×5min at same pace OR easy tempo

**Long run category:**
- W1: current long run distance, easy effort
- W2: +1mi, last 2mi at moderate effort (90% MP)
- W3: +1mi (block peak), last 3mi at moderate effort
- W4: cutback, all easy

The progression levers in priority order:
1. **Extension** — longer segments at the same pace (primary)
2. **Recovery pace** — faster float/jog between segments (secondary)
3. **Volume** — more total work at the target pace (tertiary)
4. **Speed** — faster target pace (LAST resort, only across blocks, not within)

### Build-Over-Build Seeding (across blocks)

When a block completes, the generator records `peak_workout_state` on the
`TrainingPlan`:

```json
{
  "speed": {"segment_distance_m": 1200, "pace_per_km": 228, "reps": 4},
  "threshold": {"segment_duration_min": 10, "pace_per_km": 252, "reps": 3},
  "long_run": {"distance_km": 20.1, "peak_effort_pct_mp": 90}
}
```

When the auto-renewal task generates the NEXT block, it reads
`peak_workout_state` from the completed block and seeds the new block:

- **Speed:** New block W1 starts at previous block's ~W2 extension level.
  If Block 1 peaked at 4×1200m at 5:50, Block 2 starts at 4×800m at 5:45
  (slightly faster pace, back off extension, then progress again).
- **Threshold:** Same pattern. If Block 1 peaked at 3×10min, Block 2 starts
  at 4×7min at a slightly faster pace (RPI may have updated from new data).
- **Long run:** New block starts at previous block's W1 distance, peaks
  1-2mi higher than previous block's peak.

The key constraint: **Block N+1's starting workout should feel achievable
based on Block N's peak workout.** Not identical, not trivial — the athlete
should recognize it as familiar but notice it's a step forward.

If RPI has improved between blocks (from the training adaptation), the pace
updates automatically. If RPI is flat, the progression is pure extension.
If RPI has declined (injury, illness, life), the generator backs off both
pace and extension.

Phase label on `PlannedWorkout.phase`: `"build"` (not `"base"` / `"peak"` / `"taper"`)
Week number: sequential across blocks (W1-W4, W5-W8, W9-W12...)

`TrainingPlan` row:
- `plan_type = 'build'`
- `goal_race_date = NULL`
- `goal_race_distance_m = NULL`
- `auto_renew = True`
- `block_length_weeks = 4`
- `plan_start_date = next Monday`
- `plan_end_date = plan_start + 4 weeks` (extends on renewal)
- `total_weeks = 4` (increments on renewal)
- `name = "Build — Block 1"` (increments on renewal)
- `status = 'active'`

### Maintain Mode Generator

Same file, same inputs, different prescription.

**4-week block structure:**

| Week | Volume | Quality Sessions | Long Run |
|------|--------|-----------------|----------|
| W1 | current | 1 (type A — tempo) | current LR |
| W2 | current | 1 (type B — intervals) | current LR |
| W3 | current | 1 (type C — fartlek) | current LR |
| W4 | -10-15% cutback | 0-1 easy quality / strides | -2 mi |

No volume progression. Flat. Recovery week every 4th week. Quality sessions
rotate type each week to maintain all energy systems without overloading any.

Phase label: `"maintain"`
Plan name: `"Maintain — Block 1"`

Everything else identical to Build mode structurally.

### API Endpoint

**`POST /v2/plans/general`**

```python
class GeneralPlanRequest(BaseModel):
    plan_mode: Literal["build", "maintain"]
    # No race_date, no distance — everything auto-detected from data
```

Access control: authenticated, no Pro gate (free tier).

Logic:
1. Call `get_fitness_bank(athlete.id, db)` to get all inputs
2. Call `generate_build_plan(bank)` or `generate_maintain_plan(bank)`
3. Deactivate any existing active plan (same as constraint-aware does)
4. Save `TrainingPlan` + `PlannedWorkout` rows
5. Invalidate briefing cache
6. Return plan summary

Guard: if FitnessBank has zero running activities, return 422 with
`"Connect Garmin and complete at least 5 runs before generating a plan."`

### Auto-Renewal Task

**New Celery beat task** in `apps/api/tasks/plan_renewal_tasks.py`:

Schedule: runs daily at 03:00 UTC (before briefing pipeline at 04:00).

Logic:
1. Query `TrainingPlan` where `auto_renew = True` AND `status = 'active'`
2. For each: find MAX `scheduled_date` from `PlannedWorkout`
3. If max date <= `today + 7 days`:
   a. Refresh `FitnessBank` for the athlete
   b. Compute `peak_workout_state` from the current block's W3 (peak week)
      workouts by reading their `segments` JSONB — extract max segment
      distance, pace, and rep count per workout category
   c. Store `peak_workout_state` on the `TrainingPlan` row
   d. Generate next 4-week block using the same mode, passing
      `peak_workout_state` as the seed for starting extension levels
   e. Append new `PlannedWorkout` rows (week numbers continue from last)
   f. Update `plan_end_date`, `total_weeks`, `block_number` on the plan
   g. Update plan name: `"Build — Block {block_number}"`
   h. Log: `"Auto-renewed plan %s for athlete %s — block %d (seeded from peak: speed=%dm, threshold=%dmin)"`
4. Guard: skip if athlete created a DIFFERENT plan manually (a newer
   `TrainingPlan` with different ID exists and is active)
5. Guard: if `peak_workout_state` shows regression from the previous
   block's seed (e.g., athlete skipped most quality sessions), log a
   warning and generate a conservative block that repeats the previous
   block's starting level instead of progressing

Register in Celery beat schedule alongside existing tasks.

---

## Phase 2: First-Session Flow

### Readiness Endpoint

**`GET /v1/plans/readiness`**

Returns:
```json
{
  "ready": true,
  "running_activity_count": 23,
  "has_active_plan": false,
  "garmin_connected": true,
  "estimated_rpi": 48.2,
  "current_weekly_miles": 35.0,
  "days_per_week": 5,
  "backfill_in_progress": false
}
```

`ready = True` when:
- `running_activity_count >= 5` (enough for reliable RPI)
- `garmin_connected = True`
- `has_active_plan = False`

This endpoint is cheap — FitnessBank computation is already cached / fast.
The frontend polls this every 10 seconds during the first session only (while
backfill is in progress), then stops.

### Home Page First-Session Card

In `apps/web/app/home/page.tsx`, detect the state:
`no active plan + Garmin connected`.

Three card states:

**State 1: Backfill in progress, not ready**
```
┌──────────────────────────────────────┐
│  Analyzing your training history...  │
│  [████████░░░░] 12 runs imported     │
│  We need a few more to build your    │
│  personalized plan.                  │
└──────────────────────────────────────┘
```
Uses existing `backfill_progress` Redis data + readiness endpoint.

**State 2: Ready — mode selection**
```
┌──────────────────────────────────────┐
│  We've analyzed 23 runs.             │
│  Your current pace: 8:05/mi easy     │
│  Your weekly volume: ~35 miles       │
│                                      │
│  What are you training for?          │
│                                      │
│  ┌────────────┐  ┌────────────┐      │
│  │ 🏁 I have  │  │ 📈 Getting │      │
│  │  a race    │  │   faster   │      │
│  └────────────┘  └────────────┘      │
│  ┌────────────┐  ┌────────────┐      │
│  │ 🔄 Stay    │  │ 🎯 My own  │      │
│  │ consistent │  │   plan     │      │
│  └────────────┘  └────────────┘      │
└──────────────────────────────────────┘
```

Card behaviors:
- **"I have a race"** → opens a MINIMAL race form: distance picker + date picker
  + optional goal time. That's it. Three fields. Then generates constraint-aware
  plan. This is NOT the 13-step wizard — everything else is auto-detected.
  Pro access required for this path.
- **"Getting faster"** → one tap. Calls `POST /v2/plans/general {mode: "build"}`.
  Plan generates. Card transitions to State 3. Free tier.
- **"Stay consistent"** → one tap. Calls `POST /v2/plans/general {mode: "maintain"}`.
  Free tier.
- **"My own plan"** → navigates to Custom week designer (Phase 4). Pro required.
  Until Phase 4 is built, this button should show a "Coming soon" tooltip or
  navigate to the existing `/plans/create` page.

**State 3: Plan created**
```
┌──────────────────────────────────────┐
│  Your plan is ready.                 │
│  Build — Block 1: 4 weeks           │
│  Starting Monday, March 30          │
│                                      │
│  [View Calendar →]                   │
└──────────────────────────────────────┘
```

Disappears after first calendar visit.

### Design requirements

The mode selection cards must be visually compelling. Large, clean, with subtle
iconography. Not form inputs. Not radio buttons. Not a dropdown. Four distinct
tappable cards with clear visual hierarchy. Mobile-first — these will be tapped
on phones during onboarding.

Use the existing design language from the home page (dark theme, accent colors,
card-based layout). The cards should feel like choosing a path, not filling out
a form.

### Weather-Adjusted Pace Targets

The infrastructure exists: weather API fetches conditions, `heat_adjustment_pct`
is computed, activities are stamped with dew point and temperature. But all of
this is **retrospective** — it stamps activities after the run. The planned
workout paces are static, set at generation time.

An athlete looking at today's workout sees "Easy Run at 8:05/mi" when it is
85°F with 78% dew point. That pace is wrong for those conditions. They either
run too hard chasing the number, or ignore the plan and lose trust.

**The fix: weather-adjusted paces at read time.**

When the calendar or home page requests today's planned workout, the API:

1. Fetch today's weather forecast for the athlete's location (from
   `Athlete.timezone` → coordinates, or last activity GPS)
2. Compute `heat_adjustment_pct` using the existing formula in
   `apps/api/services/weather_service.py`
3. Apply the adjustment to all pace targets on the `PlannedWorkout`
4. Return both original and adjusted paces in the response

The `PlannedWorkout` row does NOT change. The adjustment is applied at read
time based on current conditions. The response includes:

```json
{
  "target_pace_per_km": 301,
  "adjusted_pace_per_km": 316,
  "adjustment_reason": "82°F, 71% humidity — paces adjusted +5%",
  "heat_adjustment_pct": 5.0
}
```

The frontend displays:

```
Easy Run — 8:25/mi
(adjusted from 8:05 for 82°F, 71% humidity)
```

The original pace is visible but secondary. The adjusted pace is the hero
number. This applies to ALL workout types — easy, long, threshold, intervals.
Threshold and interval paces adjust by the same percentage.

**Briefing integration:** The morning briefing already generates daily. When
weather data is available and today has a planned workout, the briefing should
mention the adjustment: "Your threshold session today targets 6:45/mi — adjusted
from 6:30 for the heat. Dew point is 72°F. Stay on effort, not pace."

**What already exists (read, do not rebuild):**
- `apps/api/services/weather_service.py` — `fetch_weather_for_date()`, `enrich_activity_weather()`
- `heat_adjustment_pct` computation from dew point
- Weather data on all 605+ activities

**What to build:**
- A `get_adjusted_paces(workout, athlete, db)` helper that fetches today's
  forecast and returns adjusted pace targets
- Wire it into the calendar/home workout detail API responses
- Add adjustment context to the briefing prompt

This is the feature Runna's community is begging for ("ahead of summer in the
northern hemisphere"). We have every piece of the pipeline. This closes the
last connection.

---

## Phase 3: Post-Race Transition + Plan Continuity

### Post-Race Detection

**Celery beat task** (can be in same file as auto-renewal):

Schedule: runs daily at 03:00 UTC.

Logic:
1. Query `TrainingPlan` where `status = 'active'` AND `goal_race_date IS NOT NULL`
   AND `goal_race_date < today`
2. For each:
   a. Set `status = 'completed'`
   b. Generate a recovery block (see below)
   c. Log: `"Marked plan %s as completed — race date %s passed"`

### Recovery Block

Auto-generated when a race plan completes. This is a short `TrainingPlan` with
`plan_type = 'recovery'`, `auto_renew = False`.

Duration scales with race distance:

| Distance | Recovery days | Structure |
|----------|--------------|-----------|
| 5K | 4 days | 2 days complete rest, 2 days easy 20-30min |
| 10K | 6 days | 2 days rest, 4 days easy 30-40min |
| Half marathon | 8 days | 3 days rest, 5 days easy 30-45min |
| Marathon | 10 days | 4 days rest, 6 days easy 30-45min |
| 50K ultra | 14 days | 5 days rest, 9 days easy 20-40min progressive |

These are shorter than population recommendations because the athlete profile
is serious, Garmin-connected, and paying attention to recovery metrics. The
athlete can shorten or extend manually (edit the plan dates or delete workouts).

Recovery block is generated with `generation_method = 'ai'` and uses RPI easy
pace for the easy run days.

### Transition Prompt

On the home page, when a recovery block exists and its end date is within
3 days, show a transition card:

```
┌──────────────────────────────────────┐
│  Your [Race Name] recovery is        │
│  wrapping up. What's next?           │
│                                      │
│  [Same four mode selection cards]    │
└──────────────────────────────────────┘
```

Same UI as the first-session mode selection. Same endpoints. The athlete
picks their next mode and a new plan generates immediately.

### The Rule

After this feature ships, an athlete with Garmin connected will ALWAYS have
workouts on their calendar unless they explicitly delete their plan:

- Race plan ends → recovery block auto-generates → transition prompt → next plan
- Build/Maintain block nearing end → auto-renew generates next block
- Custom plan template → repeats indefinitely

The calendar never goes empty.

---

## Phase 4: Custom Week Designer (Session 2)

### Overview

A visual weekly grid where the athlete designs their training week. The system
fills in distances, paces, and workout details based on their data.

### Data Model

`TrainingPlan.week_template` JSONB:
```json
{
  "cycle_weeks": 1,
  "weeks": [{
    "days": [
      {"day": 0, "type": "easy"},
      {"day": 1, "type": "intervals"},
      {"day": 2, "type": "rest"},
      {"day": 3, "type": "threshold"},
      {"day": 4, "type": "easy"},
      {"day": 5, "type": "rest"},
      {"day": 6, "type": "long"}
    ]
  }]
}
```

`cycle_weeks: 2` enables alternating weeks (e.g., threshold week / speed week).

Workout types available in the designer:
`rest`, `easy`, `long`, `threshold`, `intervals`, `tempo`, `fartlek`,
`strides`, `progression`, `race_pace`, `cross_training`

### Template → PlannedWorkout Conversion

When the athlete saves a template:
1. Read `FitnessBank` for paces, volume, experience
2. Distribute total weekly volume across running days proportionally
   (long run gets 25-30% of volume, other days split the remainder)
3. For each day type, generate a concrete `PlannedWorkout` with:
   - Distance from volume distribution
   - Paces from RPI
   - Segments for structured workouts (intervals, tempo, etc.)
   - Title and description
4. Generate `block_length_weeks` weeks of concrete workouts
5. Set `auto_renew = True`

### The UI

**New component: `apps/web/components/plans/WeekDesigner.tsx`**

A 7-column grid (Mon-Sun). Each cell is a droppable slot. Below the grid,
a row of draggable workout type pills:

```
┌─────┬─────┬─────┬─────┬─────┬─────┬─────┐
│ Mon │ Tue │ Wed │ Thu │ Fri │ Sat │ Sun │
│     │     │     │     │     │     │     │
│Easy │Intv │Rest │Thrs │Easy │Rest │Long │
│     │     │     │     │     │     │     │
└─────┴─────┴─────┴─────┴─────┴─────┴─────┘

[Rest] [Easy] [Long] [Threshold] [Intervals]
[Tempo] [Fartlek] [Strides] [Progression]
```

Interactions:
- Tap a cell → opens a picker with workout types
- Tap an assigned cell → opens options (change type, clear)
- Volume summary updates live: "Week total: ~38 miles"
- Days per week auto-calculated from non-rest slots
- Save → generates plan → navigates to calendar

Access control: Pro tier only. The button on the mode selection card shows
lock icon for free users with "Upgrade to Pro" CTA.

Mobile-first: the grid stacks vertically on small screens, each day as a
full-width row with the workout type as a selectable chip.

### Coach Integration Note

The Custom week designer is the same UI coaches will use in the Coach Tier
to assign training to their athletes. When building this component, ensure
it accepts an `athleteId` prop so a coach can design a week for someone
other than themselves. The template is stored against the athlete's
`TrainingPlan` with `generation_method = 'coach'`.

---

## Validation Criteria

### Phase 1

- [ ] `TrainingPlan` with `goal_race_date = NULL` can be created and saved
- [ ] Build plan generates 4 weeks with progressive volume (W3 > W2 > W1, W4 cutback)
- [ ] Maintain plan generates 4 weeks with flat volume (W1 = W2 = W3, W4 cutback)
- [ ] Both modes use RPI-derived paces (not hardcoded, not population)
- [ ] Quality sessions appear on appropriate days with correct spacing
- [ ] **Extension-based progression:** Speed workouts increase segment distance week-over-week at the SAME pace (e.g. 400m → 800m → 1200m → cutback, all at 5K pace from RPI)
- [ ] **Extension-based progression:** Threshold workouts increase segment duration week-over-week at the SAME pace (e.g. 5min → 7min → 10min → cutback)
- [ ] **Extension-based progression:** Pace does NOT increase within a block. Pace is set at block start from RPI and held constant.
- [ ] Auto-renewal task generates next block when last workout is within 7 days
- [ ] Auto-renewal computes and stores `peak_workout_state` from the completing block
- [ ] Auto-renewal seeds next block's starting extension from previous block's peak
- [ ] **Build-over-build:** Block 2's W1 speed workout starts at Block 1's ~W2 extension level (not back to W1)
- [ ] **Build-over-build:** If RPI improved between blocks, paces update; if flat, extension is the only progression lever
- [ ] **Build-over-build:** If athlete skipped most quality sessions, next block repeats previous starting level (no phantom progression)
- [ ] Existing race plan generation is completely unaffected

### Phase 2

- [ ] Readiness endpoint returns `ready: true` when >= 5 running activities exist
- [ ] Home page shows backfill progress card when Garmin connected + no plan + backfill in progress
- [ ] Home page shows mode selection cards when ready + no plan
- [ ] "Getting faster" one-tap generates a Build plan and shows confirmation
- [ ] "Stay consistent" one-tap generates a Maintain plan
- [ ] "I have a race" opens minimal race form (3 fields only)
- [ ] Mode selection cards render well on mobile (375px width)
- [ ] Today's planned workout paces adjust for current weather conditions at read time
- [ ] Adjusted pace shown as hero number with original pace and reason visible
- [ ] Briefing mentions weather-adjusted paces when today has a planned workout

### Phase 3

- [ ] Completed race plan auto-generates recovery block scaled to distance
- [ ] Recovery block has correct rest days and easy run days per distance table
- [ ] Transition prompt appears on home page when recovery is ending
- [ ] Athlete can pick next mode from transition prompt
- [ ] Calendar is never empty for a Garmin-connected athlete with any plan mode

### Phase 4

- [ ] Week designer renders 7-day grid with tappable cells
- [ ] Workout type assignment updates volume summary live
- [ ] Template saves to `week_template` JSONB
- [ ] Template generates concrete `PlannedWorkout` rows with real paces and distances
- [ ] Pro gate enforced — free users see upgrade CTA
- [ ] Mobile layout works (vertical stack)

---

## Files That Change

| File | Change |
|------|--------|
| `apps/api/models.py` | TrainingPlan: nullable race fields, new columns (auto_renew, block_length_weeks, block_number, peak_workout_state, week_template) |
| `apps/api/alembic/versions/training_lifecycle_001.py` | NEW — migration |
| `apps/api/services/plan_framework/general_plan_generator.py` | NEW — Build + Maintain generators |
| `apps/api/services/plan_framework/n1_engine.py` | Refactor: extract shared primitives to importable functions (no logic changes) |
| `apps/api/routers/plan_generation.py` | New endpoint: POST /v2/plans/general |
| `apps/api/tasks/plan_renewal_tasks.py` | NEW — auto-renewal + post-race detection |
| `apps/api/tasks/celery_config.py` (or beat schedule) | Register new daily task |
| `apps/web/app/home/page.tsx` | First-session card + mode selection |
| `apps/web/components/plans/ModeSelector.tsx` | NEW — mode selection cards component |
| `apps/web/components/plans/WeekDesigner.tsx` | NEW — Phase 4 custom week grid |
| `apps/web/lib/api/services/plans.ts` | New API client methods |
| `apps/api/services/weather_service.py` | Read existing + add `get_adjusted_paces()` helper |
| `apps/api/routers/v1.py` or calendar endpoint | Return adjusted paces on today's workout |
| `apps/api/services/home.py` | Briefing prompt: mention weather-adjusted paces |

## What Does NOT Change

- `constraint_aware_planner.py` — race plans are untouched
- `n1_engine.py` logic — only extracting shared helpers, no behavioral changes
- `fitness_bank.py` — read-only input, no modifications
- Existing `PlannedWorkout` rows in production — new columns are nullable
- Correlation engine — reads `PlannedWorkout` rows regardless of plan mode
- Briefing — reads `PlannedWorkout` rows regardless of plan mode
- Calendar UI — renders `PlannedWorkout` rows regardless of plan mode

---

## Competitive Context

Runna's most requested feature is plan continuity — athletes hate starting from
scratch. Their second is real-time adaptability around missed workouts and
added runs. Their third is weather-adjusted pacing.

We already have weather data infrastructure (shipped) but paces don't adjust
proactively — this feature closes that loop. We already have cross-training
integration across six sports (shipped). We already have grade-adjusted effort
on maps (shipped). What we do NOT have is plan continuity, non-race training
modes, and proactive weather-adjusted pace targets. This feature closes all
three gaps and puts us ahead of every competitor on the training lifecycle.

The ultra community on Runna is actively looking for alternatives after Runna
paused their ultra plan rebuild. Our Phase 4 (50K Ultra) has 37 xfail contract
tests ready. That is a separate opportunity but worth noting as future context.
