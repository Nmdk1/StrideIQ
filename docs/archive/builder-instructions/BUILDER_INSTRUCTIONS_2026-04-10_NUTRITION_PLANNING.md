# Builder Instructions: Nutrition Planning Product

**Date:** April 10, 2026
**Status:** APPROVED — build when founder says GO
**Depends on:** Session 1 complete (reporting surface shipped)
**Estimated effort:** 1 session
**Priority:** Strategic — closes the loop between nutrition logging and actionable daily targets

---

## Read Order (mandatory)

1. `docs/FOUNDER_OPERATING_CONTRACT.md`
2. `docs/specs/NUTRITION_PHOTO_TRACKING_SPEC.md` (the full nutrition spec — context for what exists)
3. This file (build instructions)
4. `apps/api/models.py` — `Athlete` (line ~10), `BodyComposition` (line ~880), `NutritionEntry` (line ~906), `GarminDay` (line ~2758), `PlannedWorkout` (line ~1532)
5. `apps/api/routers/nutrition.py` — existing reporting + CRUD endpoints
6. `apps/web/app/nutrition/page.tsx` — current three-tab page (Log / History / Insights)
7. `apps/api/services/correlation_engine.py` — `aggregate_daily_inputs()` for wiring
8. `apps/api/services/coach_tools.py` — `build_athlete_brief()` nutrition snapshot section

---

## What This Is

A goal-based nutrition planning layer on top of the existing logging and
reporting surface. Athletes set calorie and macro targets. The system
calculates a load-adaptive daily target based on training scheduled for
that day. Targets are starting points that the athlete adjusts — the
correlation engine is the real authority over time.

This is NOT a diet app. No meal recommendations. No "eat this." No shame.
No population-based recommendations. No government guidelines. The system
shows the athlete neutral information about their intake vs their target
and lets them decide what to do with it.

**Both under-fueling AND over-eating are real problems.** The founder
explicitly stated they regained 30 pounds while training because they
couldn't see their caloric intake. The product must make overconsumption
visible with the same neutrality it uses for under-fueling. The progress
bar goes both ways — amber below 70% of target, also amber above 130%.
Not red, not shame, just signal.

---

## Philosophy: N=1

**Non-negotiable.** Every calculation in this feature is a starting point,
never a recommendation. The language everywhere is "your target" and "your
data shows" — never "experts recommend" or "guidelines suggest."

- Mifflin-St Jeor BMR is the *seed calculation* so the athlete doesn't
  start from zero. It is not presented as what they should eat.
- The 1.8 g/kg protein default is the starting slider position, not a
  prescription. The athlete moves it wherever they want.
- After 30 days of data, the setup calculation becomes irrelevant. The
  correlation engine findings ("your efficiency improves when pre-run
  carbs exceed 45g") are what matter — the athlete's own data, not a
  population table.

---

## Data Already Available

Before building anything, know what exists:

| Data | Source | Column/Field |
|------|--------|-------------|
| Weight | `BodyComposition.weight_kg` or `Activity.weight_kg` | Most recent date, either table |
| Height | `Athlete.height_cm` | Line 111 in models.py |
| Age | `Athlete.birthdate` | Compute from today |
| Sex | `Athlete.sex` | 'male' / 'female' |
| Active calories | `GarminDay.active_kcal` | Daily from Garmin |
| Today's workout | `PlannedWorkout` | `workout_type` for today's date |
| Completed activities | `Activity` | `workout_type`, `start_time` |
| Nutrition log | `NutritionEntry` | Today's logged entries |
| Correlation findings | `CorrelationFinding` | Nutrition-related confirmed findings |

**If `height_cm` is null:** The setup flow must collect it. Gate the BMR
calculation until height is provided. Show a single input field before the
goal selection step.

---

## Build Steps

### Step 1: `NutritionGoal` Model + Migration

```python
class NutritionGoal(Base):
    __tablename__ = "nutrition_goal"

    id = Column(UUID, primary_key=True, default=uuid4)
    athlete_id = Column(UUID, ForeignKey("athlete.id"), nullable=False, unique=True)
    goal_type = Column(Text, nullable=False)           # 'performance', 'maintain', 'recomp'
    calorie_target = Column(Integer, nullable=True)     # base daily target (rest day)
    protein_g_per_kg = Column(Float, nullable=False, default=1.8)
    carb_pct = Column(Float, nullable=True)             # % of non-protein calories to carbs
    fat_pct = Column(Float, nullable=True)              # % of non-protein calories to fat
    caffeine_target_mg = Column(Integer, nullable=True) # daily caffeine target
    load_adaptive = Column(Boolean, default=True)
    load_multipliers = Column(JSONB, nullable=True)     # {"rest": 1.0, "easy": 1.15, ...}
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
```

**One row per athlete.** Not a history table. If target history is needed
later, add a `NutritionGoalRevision` table.

**Default load_multipliers by goal type:**

Performance / Maintain:
```json
{"rest": 1.0, "easy": 1.15, "moderate": 1.3, "hard": 1.45, "long": 1.6}
```

Recomp:
```json
{"rest": 0.85, "easy": 1.0, "moderate": 1.3, "hard": 1.45, "long": 1.6}
```

**Recomp logic:** Same `base_calories` (BMR × 1.2), same protein target,
same training-day multipliers. The only difference is rest and easy days:
a 15% deficit on rest days and maintenance (1.0x) on easy days. The deficit
is small and restricted to low-load days — no under-fueling on training
days. This is the entire mechanical difference between recomp and
performance. No separate formula, no body fat calculations, no timeline.

These are starting points. The setup flow tells the athlete: "These are
starting points — adjust based on how you feel."

**Migration:** Chain `down_revision` to `interval_view_001` (current head).
Set `branch_labels = None`. Update EXPECTED_HEADS in
`.github/scripts/ci_alembic_heads_check.py` to match the new revision ID.
Do NOT use `down_revision = None`. After creating the migration, verify
with `python .github/scripts/ci_alembic_heads_check.py` — it must print
"OK" with 1 head.

### Step 2: BMR + Daily Target Calculation Service

Create `apps/api/services/nutrition_targets.py`.

**BMR calculation — Mifflin-St Jeor:**

```
Male:   BMR = (10 × weight_kg) + (6.25 × height_cm) - (5 × age_years) + 5
Female: BMR = (10 × weight_kg) + (6.25 × height_cm) - (5 × age_years) - 161
```

**CRITICAL — Base calorie calculation (prevents double-counting):**

```
base_calories = BMR × 1.2
```

The 1.2 factor is a fixed sedentary NEAT multiplier. It accounts for basic
daily living (walking around the house, standing, fidgeting). It does NOT
use Garmin's `active_kcal` or average rest-day calories. Those vary daily
based on whether the athlete hiked, walked 10K steps, etc. Using them as
the base would inflate the number that then gets multiplied by training
load — double-counting.

Training expenditure is handled entirely by the load multipliers:

```
daily_target = base_calories × load_multiplier_for_today
```

**Determining today's tier:**

1. Check `PlannedWorkout` for today. Map `workout_type` to tier:
   - `rest`, `recovery` → `rest`
   - `easy` → `easy`
   - `threshold`, `steady_state` → `moderate`
   - `intervals`, `threshold_intervals`, `race` → `hard`
   - `long` → `long`
2. If no planned workout, check completed `Activity` records for today and
   classify the same way.
3. **Cross-training rule:** If multiple activities exist on a day, use the
   **single highest-tier** multiplier. Do NOT sum multipliers. A strength
   session (moderate) + easy run (easy) = moderate, not moderate + easy.
   This prevents compounding and stays conservative until the correlation
   engine validates individual multipliers.
4. Fall back to `rest` if nothing found.

**Macro targets from the goal:**

```python
# Weight source: query BodyComposition and Activity, take the row with the
# most recent date regardless of source. One query with UNION ordered by
# date desc, limit 1. If neither has a value, gate the calculation.
weight_kg = get_latest_weight(db, athlete_id)
protein_g = goal.protein_g_per_kg * weight_kg
protein_cal = protein_g * 4
remaining_cal = daily_target - protein_cal
carbs_g = (remaining_cal * goal.carb_pct) / 4
fat_g = (remaining_cal * goal.fat_pct) / 9
```

Default split: `carb_pct=0.55`, `fat_pct=0.45` (of non-protein calories).
These percentages are athlete-adjustable.

**Validation: `carb_pct + fat_pct` must equal 1.0** (within tolerance of
0.01). `POST /v1/nutrition/goal` rejects with 400 if the sum is outside
`[0.99, 1.01]`. The frontend enforces this with a linked slider — moving
carbs up automatically moves fat down and vice versa. The backend
validation is the safety net.

**Return shape:**

```python
def compute_daily_targets(db, athlete_id, date=None) -> dict:
    return {
        "calorie_target": int,       # load-adjusted for today
        "protein_g": float,
        "carbs_g": float,
        "fat_g": float,
        "caffeine_mg": int | None,
        "day_tier": str,             # "rest" | "easy" | "moderate" | "hard" | "long"
        "base_calories": int,        # BMR × 1.2
        "multiplier": float,         # actual multiplier used
        "load_adaptive": bool,       # whether load adaptation is on
    }
```

### Step 3: API Endpoints

Add to `apps/api/routers/nutrition.py`:

```
GET  /v1/nutrition/goal          → current NutritionGoal for athlete
POST /v1/nutrition/goal          → create or update goal (upsert)
GET  /v1/nutrition/daily-target  → computed targets for today (or ?date=)
```

**`GET /v1/nutrition/daily-target`** is the key endpoint. It calls
`compute_daily_targets()` and merges with today's actual intake from
`NutritionEntry` to return both targets and actuals:

```json
{
  "targets": { "calories": 2760, "protein_g": 144, "carbs_g": 350, "fat_g": 80, "caffeine_mg": 300 },
  "actuals": { "calories": 1850, "protein_g": 95, "carbs_g": 210, "fat_g": 55, "caffeine_mg": 180 },
  "day_tier": "hard",
  "multiplier": 1.45,
  "pct_complete": 67,
  "time_pct": 58,
  "insights": []
}
```

`pct_complete` = actuals.calories / targets.calories × 100.
`time_pct` = athlete's **local** current hour / 24 × 100 (for pacing
comparison). Use `Athlete.timezone` to convert from UTC. If
`Athlete.timezone` is null, fall back to UTC. Do NOT use server time
directly — an athlete in CST at 2pm local would get 83% from UTC, making
the pacing comparison wrong.
`insights` = array of correlation findings relevant to today (see Step 6).

### Step 4: Guided Setup Flow (Frontend)

**Where it appears:** Non-intrusive banner at the top of the nutrition page
when the athlete has no `NutritionGoal`. Text: "Set daily targets based on
your training." One tap opens the setup flow.

**The flow is a bottom sheet, not a new page.** Three steps:

**Step A — Prerequisites (only if needed)**
If `height_cm` is null: single input "Height" with cm/ft-in toggle.
If latest `weight_kg` is null: single input "Current weight."
Skip this step entirely if both exist.

**Step B — Goal Selection**
Three cards, single tap to select:
- **Performance** — "Fuel your training. Targets adjust with your schedule."
- **Maintain** — "Stable intake. Consistent energy."
- **Recomp** — "Small deficit on rest days, maintenance on training days."

No weight goal input. No timeline. No "lose X by Y."

**Step C — Review Targets**
Show computed values with editable fields:
- Daily base: [calculated] cal (editable number input)
- Protein: [calculated] g/day ([X] g/kg) (adjustable via slider or input)
- Carbs: [X]% of remaining (adjustable)
- Fat: [X]% of remaining (adjustable)
- Caffeine: [optional] mg/day (input field, can leave blank)

Below: "These are calculated starting points. Adjust to match your
experience — the system learns what actually works for you."

One button: "Set Targets" → POST /v1/nutrition/goal → close sheet.

**Total time:** Under 60 seconds for an athlete with height and weight
already recorded.

### Step 5: Daily Target Display (Frontend)

Integrate into the existing nutrition page. The Log tab and History tab
both show target progress when a `NutritionGoal` exists.

**Log tab (top card replacement):**
Replace the current "Today's Nutrition" summary with a target-aware card:

```
Today: Hard Day — Threshold Intervals           ← from PlannedWorkout
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 67%               ← progress bar
1,850 / 2,760 cal

P: 95 / 144g    C: 210 / 350g    F: 55 / 80g
Caffeine: 180 / 300mg
```

**Progress bar colors:**
- Green fill: 70–110% of target (on track)
- Amber fill: <70% (under-fueled) or >130% (overconsumption visible)
- The bar fills beyond 100% if intake exceeds target (extends past the
  right edge). No cap at 100%.

**Time-of-day pacing (V1 — simple):**
If `pct_complete < time_pct - 15`: show subtle text "Behind pace"
If `pct_complete > time_pct + 30`: show subtle text "Ahead of pace"
Otherwise: show nothing (on track).

No meal-count modeling in V1. Just time-of-day percentage.

**History tab:**
Each day in the 7-day summary gets a target overlay:
- The calorie bar shows actual vs target as a dual-bar or filled proportion.
- Days over 130% or under 70% get an amber dot indicator.

### Step 6: Correlation Finding Hooks

Read-only integration. No new engine work.

Query `CorrelationFinding` for this athlete where:
- `input_metric` is in the explicit nutrition whitelist:
  `daily_calories`, `daily_protein_g`, `daily_carbs_g`, `daily_fat_g`,
  `daily_caffeine_mg`, `pre_run_carbs_g`, `pre_run_caffeine_mg`,
  `pre_run_meal_gap_minutes`, `during_run_carbs_g_per_hour`
  (Do NOT use `LIKE 'daily_%'` — that would match non-nutrition signals
  like `daily_step_count` and `daily_active_time`.)
- `is_active = True`
- `times_confirmed >= 3`

Format as contextual nudges on the daily target card. Examples:
- "Your data: efficiency improves when pre-run carbs > 45g. Today's
  threshold — aim for 45–60g carbs 2–3h before."
- "Your data: sleep quality correlates with daily caffeine below 350mg."

Show a maximum of 1 insight per day. Pick the most relevant based on
today's planned workout type. If no nutrition findings exist yet, show
nothing — the section appears only when there's something to show.

### Step 7: Coach Awareness

Update `build_athlete_brief()` in `coach_tools.py`:

The existing "Nutrition Snapshot" section already shows intake. Add one
line when a `NutritionGoal` exists:

```
Targets: 2,760 cal (Hard day, 1.45x) | 144g P | 350g C | 80g F
Current: 1,850 cal (67%) — behind pace at 2pm
Goal: performance
```

Include the day tier label in plain language ("Hard day"), not just the
multiplier number. The coach reads this quickly between athletes — "Hard
day (1.45x)" is immediately meaningful, "1.45x" alone is not. Also
include the goal type so the coach knows the athlete's intent.

The coach can then reference targets vs actuals when the athlete asks
about nutrition, without needing to call a tool.

---

## What V1 Does NOT Build

- No meal recommendations or food suggestions
- No meal timing prescriptions beyond pre-run patterns
- No micro-nutrient tracking (vitamins, minerals, sodium)
- No integration with external nutrition apps
- No AI-generated meal plans
- No social/comparison features
- No food restriction or allergy management
- No penalty UX — no streaks, no shame, no "you broke your streak"
- No weight goal timelines
- No body fat percentage targets

---

## Testable Success Criteria

1. **Setup flow completes in <60 seconds** for an athlete with existing
   height and weight. Time it.
2. **BMR calculation matches Mifflin-St Jeor within 1 calorie** — write a
   unit test with known inputs (male, 80kg, 175cm, 45yo → BMR = 1,648).
   Also test the full `compute_daily_targets()` output for a known athlete
   profile (BMR + base + multiplier + macros) — not just the BMR in
   isolation.
3. **Load tier correctly resolves** for: rest day, single easy run, single
   threshold workout, long run, and multi-activity day (strength + easy →
   highest tier). Write tests for each case.
4. **Progress bar renders at 0%, 50%, 100%, and 150%** — no visual
   breakage at extremes.
5. **daily-target endpoint returns in <100ms** — it queries 3-4 tables,
   should be fast.
6. **Coach brief includes target line** when goal exists, omits it when
   no goal is set. Verify with the existing `_verify_coach.py` pattern.
7. **Migration chains correctly** — `ci_alembic_heads_check.py` passes.
8. **Frontend build green** — `npx tsc --noEmit` and `npx next build`.
9. **No population language anywhere in the UI.** Grep the frontend for
   "recommend", "guideline", "suggest", "should eat", "expert". Zero hits
   in the nutrition page.

---

## Integration Points — Nutrition as a First-Class Metric

Nutrition is not a sidecar feature. When the input pipeline above is
built and data starts flowing, nutrition becomes a core input metric
at the same level as training load, sleep, and HRV. The integrations
below should be built as data becomes available.

### Correlation Engine

Nutrition data enters the correlation engine as a dimension alongside
existing metrics. Target findings:
- "When you consumed 80+ g/hr carbs on long runs, your cardiac drift
  was 22% lower" (population-validated pattern)
- "Your protein intake in the 2 hours after threshold sessions
  correlates with faster recovery on the following day"
- "On days when you logged <1500 kcal, your next-day easy pace was
  15 sec/mi slower"

Nutrition correlations use the same statistical rigor as all other
findings. No spurious claims. Suppress over hallucinate.

### Daily Briefing

When tomorrow's workout is ≥90 min or a race simulation:
- "You have a 16-mile long run tomorrow. Your fueling on your last
  two long runs averaged 45 g/hr — below the 75 g/hr floor. Consider
  preparing gels tonight."

When fueling data shows a pattern:
- "Your last 3 long runs with 75+ g/hr carbs all had negative splits.
  Keep doing what you're doing."

When no nutrition data exists: say nothing. Don't remind athletes
to log food — that's penalty UX.

### Coach Model

The coach should be fueling-aware when reviewing workout outcomes:
- After a bonked long run: ask about fueling before suggesting
  fitness issues
- After a great race: acknowledge fueling if data shows they hit
  their target
- In pre-race conversations: reference their practiced fueling rate
  from training logs

The coach never prescribes specific diets or calorie targets. It
references the athlete's own data and patterns.

### Plan Generator (Workout Descriptions)

Already specified in the Algorithm Spec (section 10, Workout
Description Quality Bar): all workouts ≥90 min include
`fueling_target_g_per_hr` in the segments schema and a fueling
reminder in the description text. The fueling target scales with
training age:
- Early development: 60 g/hr
- Developing: 75 g/hr
- Established: 75-90 g/hr
- Race day: athlete's practiced rate

### Fueling Product Library (Future)

When the product library is built (gels, drinks, chews), the system
can compute whether an athlete's planned products hit their g/hr
target: "Your 2 gels + 1 bottle of Tailwind = ~65 g/hr. You need
one more gel per hour to hit your 90 g/hr target."

This is the future state — not a blocker for the current build.
