# ADR-031: Constraint-Aware Planning Layer

**Status:** Accepted (Implemented)  
**Date:** 2026-01-15  
**Author:** Engineering Team  
**Depends On:** ADR-030 (Fitness Bank Framework)  
**Implementation:**  
- `apps/api/services/week_theme_generator.py`  
- `apps/api/services/workout_prescription.py`  
- `apps/api/services/constraint_aware_planner.py`

---

## Context

The Fitness Bank captures what an athlete CAN do. But athletes don't train in ideal conditions:
- Injuries require protected ramp-ups
- Work/life limits available days
- Multiple races need coordinated tapers
- Individual τ values mean different recovery needs

Generic plans ignore these constraints. A 70mpw athlete returning from injury shouldn't get a 70mpw week 1 plan — even though they've proven they can handle it.

---

## Decision

Build a **Constraint-Aware Planning Layer** that:

1. **Respects detected patterns** (Sunday long runs, Thursday quality, Monday rest)
2. **Protects constraints** (injury ramp, dual race coordination)
3. **Alternates themes** (T-emphasis → MP-emphasis → Recovery)
4. **Prescribes concretely** from personal VDOT/efficiency, not templates

### Architecture Choice: Rule-Based vs ML

| Approach | Pros | Cons |
|----------|------|------|
| **Rule-based** | Explainable, fast, auditable, works with N=1 | Less adaptive to novel patterns |
| **ML-based** | Can discover hidden patterns | Black box, needs large N, slow |

**Chosen: Rule-based** — because:
- Explainability is critical for athlete trust
- N=1 means no training data for ML
- Rules encode coaching wisdom directly
- Fast execution (milliseconds, not seconds)

---

## Components

### 1. WeekThemeGenerator

Generates week-by-week training emphasis based on Fitness Bank.

```python
class WeekTheme(Enum):
    REBUILD_EASY = "rebuild_easy"       # Injury return - easy only
    REBUILD_STRIDES = "rebuild_strides" # Add strides, still easy base
    BUILD_T_EMPHASIS = "build_t"        # Threshold focus
    BUILD_MP_EMPHASIS = "build_mp"      # Marathon pace focus
    BUILD_MIXED = "build_mixed"         # Both quality types
    RECOVERY = "recovery"               # 40% reduction
    PEAK = "peak"                       # Maximum quality
    SHARPEN = "sharpen"                 # Race-specific work
    TAPER_1 = "taper_1"                 # 30% reduction
    TAPER_2 = "taper_2"                 # 50% reduction
    TUNE_UP_RACE = "tune_up"            # Secondary race week
    RACE = "race"                       # Goal race week
```

**Rules:**
- Alternate: T → MP → T (never consecutive same-emphasis)
- Recovery every 3-4 weeks (3 for τ1 > 35, 4 for τ1 < 30)
- Injury constraint: first 2-3 weeks = REBUILD_*
- Dual races: protect second taper, tune-up as sharpening

### 2. WorkoutPrescriptionGenerator

Generates specific workout structures with paces from personal VDOT.

**Pace Zones (from VDOT):**
```
Easy:      VDOT - 30%
Marathon:  VDOT race pace for marathon
Threshold: VDOT - 12%
Interval:  VDOT + 3%
```

**Structure Templates by Experience:**
```python
THRESHOLD_STRUCTURES = {
    "elite": [
        "2x4mi @ T w/ 3min jog",
        "3x3mi @ T w/ 2min jog",
        "8mi @ T straight",
        "10mi @ T straight"
    ],
    "experienced": [
        "2x3mi @ T w/ 2min jog",
        "3x2mi @ T w/ 2min jog",
        "6mi @ T straight"
    ],
    "intermediate": [
        "2x15min @ T w/ 3min jog",
        "3x10min @ T w/ 2min jog",
        "20min @ T straight"
    ],
    "beginner": [
        "2x10min @ T w/ 3min jog",
        "3x8min @ T w/ 2min jog"
    ]
}

MP_LONG_RUN_TEMPLATES = {
    "build_early": "{total}mi easy, last {mp}mi @ MP",
    "build_mid": "{total}mi with middle {mp}mi @ MP",
    "peak": "{total}mi with {mp}mi @ MP (race simulation)",
    "with_threshold": "{total}mi: {easy}E + {mp}@MP + {t}@T + {easy}E"
}
```

### 3. ConstraintAwarePlanner (Orchestrator)

Coordinates all components:

```python
class ConstraintAwarePlanner:
    def generate_plan(self, 
                     athlete_id: UUID,
                     race_date: date,
                     race_distance: str,
                     tune_up_races: List[Dict] = None) -> Plan:
        
        # 1. Get Fitness Bank
        bank = get_fitness_bank(athlete_id, db)
        
        # 2. Apply constraint overrides
        constraints = self._analyze_constraints(bank, race_date, tune_up_races)
        
        # 3. Generate week themes
        themes = self.theme_generator.generate(bank, race_date, constraints)
        
        # 4. Fill workouts per theme
        weeks = []
        for week_num, theme in enumerate(themes):
            week = self.workout_generator.generate_week(
                theme=theme,
                week_num=week_num,
                bank=bank,
                constraints=constraints
            )
            weeks.append(week)
        
        # 5. Calculate TSS trajectory and validate
        plan = self._apply_tss_constraints(weeks, bank)
        
        # 6. Generate counter-conventional notes
        notes = self._generate_insights(bank, constraints, themes)
        
        return Plan(weeks=weeks, notes=notes, fitness_bank=bank.to_dict())
```

---

## Constraint Types

### Injury Return
```python
if bank.constraint_type == "injury":
    # First 2 weeks: REBUILD_EASY
    # Week 3: REBUILD_STRIDES  
    # Week 4+: Normal but 80% target volume
    # Add note: "Ramping carefully from injury"
```

### Dual Races
```python
if tune_up_races:
    # Find tune-up dates
    # Insert TUNE_UP_RACE theme
    # Protect recovery after tune-up
    # Note: "Using {tune_up} as final sharpening for {goal}"
```

### Fast Adapter (τ1 < 30)
```python
if bank.tau1 < 30:
    # Recovery weeks every 4 weeks instead of 3
    # Can handle steeper volume ramp
    # Shorter taper (10 days vs 14)
    # Note: "Your τ1={tau1}d = faster adaptation than typical"
```

### Slow Adapter (τ1 > 45)
```python
if bank.tau1 > 45:
    # Recovery weeks every 3 weeks
    # Gentler volume ramp
    # Longer taper (21 days)
    # Note: "Your τ1={tau1}d = patience builds fitness"
```

---

## Day Pattern Preservation

```python
def _assign_workout_to_day(self, workout_type: str, bank: FitnessBank) -> int:
    """Respect detected patterns."""
    
    if workout_type == "long_run":
        return bank.typical_long_run_day or 6  # Sunday default
    
    if workout_type in ("threshold", "intervals"):
        return bank.typical_quality_day or 3  # Thursday default
    
    if workout_type == "rest":
        return bank.typical_rest_days[0] if bank.typical_rest_days else 0
```

---

## Example Output

For athlete with:
- Peak: 71mpw, 22mi long, 18@MP
- Current: 16mpw (injury return)
- τ1: 25 days
- Experience: Elite
- Pattern: Sun long, Thu quality, Mon rest
- Races: 10-mile March 7, Marathon March 15

**Week Themes Generated:**
```
Week 1: REBUILD_EASY       (30 miles)
Week 2: REBUILD_STRIDES    (40 miles)
Week 3: BUILD_T_EMPHASIS   (55 miles)
Week 4: RECOVERY           (35 miles)
Week 5: BUILD_MP_EMPHASIS  (65 miles)
Week 6: BUILD_T_EMPHASIS   (70 miles)
Week 7: PEAK               (72 miles)
Week 8: TUNE_UP_RACE       (32 miles) ← 10-mile race
Week 9: RACE               (44 miles) ← Marathon
```

**Sample Week 5 (BUILD_MP_EMPHASIS):**
```
Mon: REST
Tue: 10mi with 6mi @ MP (6:50/mi)
Wed: 8mi easy (8:00/mi)
Thu: 12mi: 3E + 2x3mi @ T (6:20/mi) w/ 2min + 3E
Fri: 6mi easy + 6x100m strides
Sat: 5mi easy
Sun: 20mi with last 12mi @ MP (6:50/mi)

Total: 65 miles, 2 quality sessions, specific prescriptions
```

---

## Tone Guidelines

**Do:**
- "2x3mi @ 6:20 w/ 2min jog"
- "Your τ1=25d means sharper taper works"
- "18@MP in 24 — you've done this before"

**Don't:**
- "Great job on your training!"
- "You can do it!"
- "Threshold work for 30 minutes"

---

## Testing Requirements

### Unit Tests
- `test_theme_alternation`: T → MP → T pattern
- `test_injury_protection`: First weeks are REBUILD
- `test_recovery_insertion`: Every 3-4 weeks
- `test_dual_race_coordination`: Tune-up + goal race
- `test_respects_patterns`: Sunday long, Thursday quality

### Integration Tests
- `test_full_plan_michael`: Generate for real data
- `test_workout_paces_from_vdot`: Paces match personal VDOT
- `test_volume_ramp_injury`: 16mpw → 70mpw in 7 weeks

---

## Success Metrics

1. **Pattern Respect**: 100% of long runs on preferred day
2. **Theme Alternation**: 0 consecutive same-emphasis weeks
3. **Specific Prescriptions**: 100% workouts have structure + paces
4. **Constraint Protection**: Injury returns never exceed 20% weekly increase
5. **Athlete Validation**: Plans match self-coached quality

---

*Plans built from your data, respecting your constraints, targeting your proven peak.*
