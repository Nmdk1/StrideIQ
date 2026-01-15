# Fitness Bank Framework

**Status:** Production Ready  
**Date:** 2026-01-15  
**ADRs:** 030, 031, 032

---

## Overview

The Fitness Bank Framework is StrideIQ's core plan generation system for subscriber custom plans. It replaces generic template-based planning with true N=1 personalization based on the athlete's complete training history.

**Key Principle:** The athlete's history IS the data. Generic plans fail because they ignore what the athlete has already proven they can do.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     API: /v2/plans/constraint-aware             │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                  ConstraintAwarePlanner                          │
│    Orchestrates all components, generates complete plan          │
└───────────────────────────────┬─────────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
        ▼                       ▼                       ▼
┌───────────────┐     ┌────────────────┐     ┌────────────────────┐
│ FitnessBank   │     │ WeekTheme      │     │ Workout            │
│ Calculator    │     │ Generator      │     │ Prescription       │
│               │     │                │     │ Generator          │
│ Analyzes full │     │ T → MP → T     │     │ "2x3mi @ 6:25"     │
│ training      │     │ alternation    │     │ specific paces     │
│ history       │     │                │     │                    │
└───────────────┘     └────────────────┘     └────────────────────┘
```

---

## Components

### 1. FitnessBank (`services/fitness_bank.py`)

Calculates the athlete's **proven capabilities**:

| Field | Description |
|-------|-------------|
| `peak_weekly_miles` | Highest sustainable weekly volume |
| `peak_long_run_miles` | Longest long run completed |
| `peak_mp_long_run_miles` | Longest MP portion in a long run |
| `best_vdot` | Best race performance (VDOT) |
| `tau1` / `tau2` | Individual response time constants |
| `experience_level` | Beginner / Intermediate / Experienced / Elite |
| `constraint_type` | None / Injury / Time / Detrained |

**Usage:**
```python
from services.fitness_bank import get_fitness_bank

bank = get_fitness_bank(athlete_id, db)
print(f"Peak: {bank.peak_weekly_miles}mpw")
print(f"Best VDOT: {bank.best_vdot}")
print(f"τ1: {bank.tau1}d")
```

### 2. WeekThemeGenerator (`services/week_theme_generator.py`)

Generates week-by-week training emphasis:

| Theme | Volume | Description |
|-------|--------|-------------|
| `REBUILD_EASY` | 40% | Injury return, easy only |
| `REBUILD_STRIDES` | 55% | Add strides, easy base |
| `BUILD_T_EMPHASIS` | 80% | Threshold focus |
| `BUILD_MP_EMPHASIS` | 85% | Marathon pace focus |
| `RECOVERY` | 55% | Volume reduction |
| `PEAK` | 100% | Maximum quality |
| `TAPER_1` | 65% | Maintain intensity |
| `TAPER_2` | 45% | Final sharpening |
| `TUNE_UP_RACE` | 45% | Secondary race |
| `RACE` | 60% | Goal race |

**Rules:**
- Alternate T → MP → T (never consecutive same-emphasis)
- Recovery every 3-4 weeks based on τ1
- Injury: first 2-3 weeks = REBUILD_*
- Dual races: tune-up + goal race coordination

### 3. WorkoutPrescriptionGenerator (`services/workout_prescription.py`)

Generates specific workout structures with personal paces:

**Threshold Structures by Experience:**
```
Elite:        "2x4mi @ T", "3x3mi @ T", "8mi @ T straight"
Experienced:  "2x3mi @ T", "3x2mi @ T", "6mi @ T straight"
Intermediate: "2x15min @ T", "3x10min @ T"
Beginner:     "2x10min @ T", "3x8min @ T"
```

**MP Long Run Progression:**
```
Early build:  "20mi with last 8mi @ MP"
Mid build:    "22mi: 8E + 14mi @ MP"
Peak:         "24mi with 18mi @ MP (race simulation)"
```

### 4. ConstraintAwarePlanner (`services/constraint_aware_planner.py`)

Orchestrates the full plan generation:

1. Get Fitness Bank
2. Generate week themes
3. Apply constraint overrides (injury ramp, dual races)
4. Fill workouts with specific prescriptions
5. Inject counter-conventional notes
6. Calculate race predictions

---

## API Endpoints

### POST `/v2/plans/constraint-aware`

**Request:**
```json
{
  "race_date": "2026-03-15",
  "race_distance": "marathon",
  "race_name": "Boston Marathon",
  "tune_up_races": [
    {
      "date": "2026-03-07",
      "distance": "10_mile",
      "name": "10 Mile Record Attempt",
      "purpose": "threshold"
    }
  ]
}
```

**Response:**
```json
{
  "success": true,
  "plan_id": "uuid",
  "fitness_bank": {
    "peak": { "weekly_miles": 71, "long_run": 22, "mp_long_run": 18 },
    "best_vdot": 53.2,
    "tau1": 25,
    "tau2": 18,
    "experience": "elite",
    "constraint": { "type": "injury", "returning": true }
  },
  "prediction": {
    "time": "3:01:09",
    "confidence_interval": "±5-8 min"
  },
  "weeks": [...]
}
```

### GET `/v2/plans/constraint-aware/preview`

Preview Fitness Bank without generating full plan.

---

## Database Schema

### TrainingPlan

| Column | Type | Description |
|--------|------|-------------|
| `generation_method` | Text | "constraint_aware" |
| `baseline_vdot` | Float | Best VDOT at plan creation |
| `baseline_weekly_volume_km` | Float | Peak weekly volume |

### PlannedWorkout

| Column | Type | Description |
|--------|------|-------------|
| `title` | Text | "2x4mi @ T" |
| `description` | Text | Full with paces |
| `coach_notes` | Text | Personal paces + insights |
| `phase` | Text | build / peak / taper / race |

---

## Testing

### Unit Tests

```bash
docker-compose exec api pytest tests/test_fitness_bank_framework.py -v
```

17 tests covering:
- VDOT calculation
- Pace zone calculation
- Theme alternation
- Injury protection
- Tune-up race insertion
- Workout prescription

### Integration Test

```bash
docker-compose exec api python scripts/test_full_integration.py
```

9 checks:
- Weeks generated
- 7 days per week
- Theme alternation
- Race week at end
- Tune-up race week
- Workouts have descriptions
- Workouts have paces
- Personalized insights
- Fitness bank populated

---

## Example Output

For an athlete with:
- Peak: 71mpw, 22mi long, 18@MP
- Current: 16mpw (injury return)
- τ1: 25 days, τ2: 18 days
- Best race: 39:10 10K (VDOT 53)
- Goal: Marathon March 15, 10-mile tune-up March 7

**Generated Plan:**
```
Week  1: rebuild_easy            28mi
Week  2: rebuild_strides         36mi
Week  3: rebuild_strides         39mi
Week  4: build_t                 58mi  (2x4mi @ 6:25)
Week  5: build_mp                69mi  (18mi w/ 10@MP)
Week  6: peak                    73mi  (23mi w/ 14@MP)
Week  7: taper_1                 55mi
Week  8: tune_up                 32mi  (10-MILE RACE)
Week  9: race                    43mi  (MARATHON)

Prediction: 3:01:09 (±5-8 min injury uncertainty)
```

**Personalized Insights:**
- "Your τ1=25d means faster adaptation than typical runners"
- "Peak capability: 71mpw, 22mi long, 18@MP. This plan targets that level."
- "10 Mile Record Attempt: Race this HARD. It's your final threshold effort."

---

## Security

- Elite tier enforcement
- Rate limiting (5 plans/day)
- JWT authentication required
- Feature flag: `plan.model_driven_generation`

---

## Files

| File | Purpose |
|------|---------|
| `services/fitness_bank.py` | FitnessBank model + calculator |
| `services/week_theme_generator.py` | Theme generation |
| `services/workout_prescription.py` | Specific prescriptions |
| `services/constraint_aware_planner.py` | Orchestrator |
| `routers/plan_generation.py` | API endpoints |
| `tests/test_fitness_bank_framework.py` | Unit tests |
| `scripts/test_full_integration.py` | Integration test |
| `docs/adr/ADR-030-fitness-bank-framework.md` | Architecture |
| `docs/adr/ADR-031-constraint-aware-planning.md` | Planning layer |
| `docs/adr/ADR-032-constraint-aware-api-integration.md` | API contract |

---

*Built from YOUR data. Respecting YOUR constraints. Targeting YOUR proven peak.*
