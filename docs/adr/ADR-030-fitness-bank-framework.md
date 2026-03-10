# ADR-030: Fitness Bank Framework

**Status:** Accepted (Implemented)  
**Date:** 2026-01-15  
**Author:** Engineering Team  
**Stakeholders:** Athletes, Coaches, Product  
**Implementation:** `apps/api/services/fitness_bank.py`

---

## Context

Generic training plans fail for real athletes because they ignore:
1. **Banked fitness** - A 275 mi/month runner doesn't "start over" after injury
2. **Individual response rates** - τ1=25 days vs τ1=50 days requires different approaches  
3. **Proven race capabilities** - 6:18 10K while limping proves more than any formula
4. **Constraints vs fitness** - Mechanical injury ≠ aerobic deconditioning
5. **Week structure sophistication** - T-emphasis/MP-emphasis alternation

Current system generates plans based on recent volume, not peak capability. This produces conservative plans that underserve experienced athletes.

---

## Decision

Implement a **Fitness Bank Framework** that:

1. Tracks athlete's **peak proven capabilities** alongside current state
2. Uses **race performances as ground truth** for fitness calibration
3. Distinguishes between **constraint-limited** (injury) vs **fitness-limited** (detrained)
4. Generates **week themes** with specific workout structures
5. Prescribes **specific intervals** ("2x3mi @ T") not generic descriptions
6. Supports **multi-race planning** with priority levels

---

## Architecture

### 1. Fitness Bank Model

```python
@dataclass
class FitnessBank:
    """Athlete's proven fitness capabilities."""
    
    # Peak capabilities (from history)
    peak_weekly_miles: float          # Highest sustainable week
    peak_monthly_miles: float         # Highest month
    peak_long_run_miles: float        # Longest long run
    peak_mp_long_run_miles: float     # Longest MP portion
    peak_ctl: float                   # Highest chronic training load
    
    # Proven race performances
    race_performances: List[RacePerformance]
    best_rpi: float                  # From best race
    
    # Current state
    current_weekly_miles: float
    current_ctl: float
    current_atl: float
    
    # Individual response
    tau1: float                       # Fitness time constant
    tau2: float                       # Fatigue time constant
    recovery_rate: str                # "fast", "normal", "slow"
    
    # Constraints
    constraint_type: Optional[str]    # "injury", "time", "none"
    constraint_details: Optional[str] # "leg", "schedule", etc.
    weeks_since_peak: int
    
    # Projections
    weeks_to_race_ready: int          # Based on τ1 and gap
    projected_ctl_at_race: float
```

### 2. Race Performance Model

```python
@dataclass  
class RacePerformance:
    """A proven race result."""
    date: date
    distance: str                     # "5k", "10k", "half", "marathon"
    distance_m: float
    finish_time_seconds: int
    pace_per_mile: float
    rpi: float
    conditions: Optional[str]         # "limping", "hot", "hilly"
    confidence: float                 # How much to weight this
```

### 3. Week Theme Model

```python
class WeekTheme(Enum):
    BASE = "base"                     # Easy + strides, building volume
    THRESHOLD_EMPHASIS = "t_emphasis" # Threshold as key session
    MP_EMPHASIS = "mp_emphasis"       # Marathon pace as key session
    RECOVERY = "recovery"             # 40% reduction, all easy
    PEAK_MP = "peak_mp"               # Biggest MP long run
    TAPER_1 = "taper_1"               # 30% reduction, maintain intensity
    TAPER_2 = "taper_2"               # 50% reduction, sharpening only
    RACE_WEEK = "race_week"           # Race execution
```

### 4. Specific Workout Structures

```python
THRESHOLD_STRUCTURES = {
    "beginner": ["2x10min @ T", "3x8min @ T"],
    "intermediate": ["2x15min @ T", "3x10min @ T", "20min @ T"],
    "experienced": ["2x3mi @ T", "3x2mi @ T", "8mi @ T straight"],
    "elite": ["4x2mi @ T", "2x4mi @ T", "10mi @ T straight"]
}

MP_LONG_RUN_STRUCTURES = {
    "build_early": "{total}mi with last {mp}mi @ MP",
    "build_mid": "{total}mi with middle {mp}mi @ MP", 
    "build_late": "{total}mi with {mp}mi @ MP finish",
    "peak": "{total}mi with {mp}mi @ MP (race simulation)"
}
```

---

## Implementation Plan

### Phase 1: Fitness Bank Calculator

**File:** `apps/api/services/fitness_bank.py`

```python
class FitnessBankCalculator:
    """Calculate athlete's fitness bank from history."""
    
    def calculate(self, athlete_id: UUID) -> FitnessBank:
        """
        Analyze full training history to build fitness bank.
        
        Steps:
        1. Find peak weekly/monthly volumes
        2. Extract race performances with RPI
        3. Calculate current state (CTL/ATL)
        4. Determine τ values from response patterns
        5. Detect constraints (injury, time gap)
        6. Project recovery timeline
        """
        pass
    
    def _extract_race_performances(self, activities: List[Activity]) -> List[RacePerformance]:
        """Find and analyze all race performances."""
        pass
    
    def _calculate_best_rpi(self, races: List[RacePerformance]) -> float:
        """Find best RPI, weighted by recency and conditions."""
        pass
    
    def _detect_constraint(self, 
                          peak_volume: float, 
                          current_volume: float,
                          weeks_gap: int) -> Tuple[str, str]:
        """Determine if athlete is injury-limited vs detrained."""
        pass
    
    def _project_recovery(self,
                         current_ctl: float,
                         peak_ctl: float,
                         tau1: float) -> int:
        """Estimate weeks to race-ready based on τ1."""
        pass
```

### Phase 2: Week Theme Generator

**File:** `apps/api/services/week_theme_generator.py`

```python
class WeekThemeGenerator:
    """Generate week themes based on fitness bank and race goals."""
    
    THEME_PATTERNS = {
        "marathon_16_week": [
            "base", "base", "t_emphasis", "recovery",
            "mp_emphasis", "t_emphasis", "mp_emphasis", "recovery",
            "t_emphasis", "mp_emphasis", "t_emphasis", "peak_mp",
            "taper_1", "tune_up", "taper_2", "race_week"
        ],
        "marathon_12_week": [
            "base", "t_emphasis", "recovery",
            "mp_emphasis", "t_emphasis", "mp_emphasis", 
            "t_emphasis", "peak_mp", "recovery",
            "taper_1", "taper_2", "race_week"
        ],
        "marathon_8_week_experienced": [
            "t_emphasis", "mp_emphasis", "t_emphasis", "peak_mp",
            "recovery", "taper_1", "tune_up", "race_week"
        ]
    }
    
    def generate_themes(self, 
                       fitness_bank: FitnessBank,
                       race_date: date,
                       race_distance: str,
                       tune_up_races: List[Dict] = None) -> List[WeekTheme]:
        """Generate week themes based on athlete capability and timeline."""
        pass
```

### Phase 3: Specific Workout Generator

**File:** `apps/api/services/workout_prescription.py`

```python
class WorkoutPrescriptionGenerator:
    """Generate specific workout prescriptions based on experience level."""
    
    def generate_threshold_workout(self,
                                   experience: str,
                                   week_theme: WeekTheme,
                                   target_tss: float,
                                   paces: Dict[str, str]) -> DayPlan:
        """
        Generate specific threshold prescription.
        
        Example outputs:
        - Beginner: "3x8min @ 6:45 with 2min jog recovery"
        - Experienced: "2x3mi @ 6:20 with 3min jog recovery"
        - Elite: "8mi @ 6:15 straight (T-emphasis week)"
        """
        pass
    
    def generate_mp_long_run(self,
                            experience: str,
                            week_number: int,
                            total_weeks: int,
                            proven_mp_capability: float,
                            target_long: float,
                            paces: Dict[str, str]) -> DayPlan:
        """
        Generate MP long run scaled to proven capability.
        
        Example outputs:
        - Week 5 (early build): "20mi with last 8mi @ 6:50"
        - Week 8 (peak): "24mi with 18mi @ 6:48 (race simulation)"
        """
        pass
```

### Phase 4: Constraint-Aware Planner

**File:** `apps/api/services/constraint_aware_planner.py`

```python
class ConstraintAwarePlanner:
    """Generate plans that respect current constraints while targeting peak capability."""
    
    def generate_return_to_fitness_plan(self,
                                        fitness_bank: FitnessBank,
                                        race_date: date,
                                        constraint: str) -> ModelDrivenPlan:
        """
        Generate plan for athlete returning from constraint.
        
        Key principles:
        1. Target peak capability, not current volume
        2. Use τ1 to estimate ramp-up timeline
        3. Insert quality only when constraint allows
        4. Preserve race-specific work even in reduced plan
        """
        pass
    
    def generate_minimum_viable_plan(self,
                                    fitness_bank: FitnessBank,
                                    race_date: date,
                                    available_weeks: int) -> ModelDrivenPlan:
        """
        Generate minimum training needed to be race-ready.
        
        For experienced athlete with banked fitness:
        - Focus on maintaining, not building
        - Key sessions only: 1 threshold, 1 MP long run per week
        - Everything else is recovery
        """
        pass
```

---

## Validation Rules

### Rule 1: Peak Volume Usage
For experienced athletes (peak_weekly_miles > 60):
- Plan target should be 85-100% of peak, not 75% of P90
- Recovery weeks should be 40% reduction, not 25%

### Rule 2: Race Performance Priority
- RPI from races trumps calculated RPI from training
- Recent race at suboptimal conditions (limping) still counts
- Weight races by: recency × distance_relevance × conditions

### Rule 3: Constraint Recognition
- If current_volume < 50% of peak AND gap < 8 weeks: likely injury
- If current_volume < 50% of peak AND gap > 12 weeks: likely detrained
- Injury returns use τ1 for recovery projection
- Detrained requires conservative rebuild

### Rule 4: Week Theme Alternation
For marathon plans > 10 weeks:
- Never two consecutive hard-theme weeks
- Recovery week every 3-4 weeks
- T-emphasis and MP-emphasis should alternate

### Rule 5: Specific Prescriptions
- All threshold work must specify structure: "2x3mi" not "threshold"
- All MP long runs must specify MP portion: "20mi with 8 @ MP"
- Strides must be added to appropriate easy days

---

## Testing Requirements

### Unit Tests
- `test_fitness_bank_calculation`
- `test_race_performance_extraction`
- `test_rpi_calculation_with_conditions`
- `test_constraint_detection`
- `test_recovery_projection`
- `test_week_theme_generation`
- `test_workout_prescription_by_experience`

### Integration Tests
- `test_full_plan_for_experienced_athlete`
- `test_injury_return_plan`
- `test_tune_up_race_integration`
- `test_minimum_viable_plan`

### Validation Tests (Real Data)
- `test_michaels_plan_matches_self_coached`
- `test_volume_scaling_for_70mpw_runner`
- `test_mp_long_run_progression`

---

## Success Metrics

1. **Volume Accuracy**: Generated peak week within 10% of athlete's historical peak
2. **MP Prescription**: Peak MP long run matches athlete's proven capability
3. **Workout Specificity**: 100% of workouts have specific prescriptions
4. **Theme Alternation**: No violations of consecutive hard weeks
5. **Recovery Weeks**: Proper 40% reduction every 3-4 weeks

---

## Migration Path

1. Create `FitnessBank` model and calculator
2. Update `ModelDrivenPlanGenerator` to use fitness bank
3. Add week theme generation
4. Add specific workout prescriptions
5. Add constraint-aware planning
6. Validate against real athlete data
7. Deploy behind feature flag

---

## Appendix: Example Output

For Michael (mbshaf) with:
- Peak: 71 mpw, 275 mi/month, 22mi long, 18@MP
- Current: ~45 mpw (injury recovery)
- Proven: 6:18 10K (RPI 54-55), 1:27:40 half
- τ1: 25 days
- Constraint: Leg injury

Generated plan should show:
```
Week 1 (t_emphasis): 55 miles
  Thu: 10mi with 2x2mi @ 6:20 (T) + strides
  Sun: 16mi easy

Week 2 (mp_emphasis): 60 miles
  Tue: 12mi with 6mi @ 6:48 (MP)
  Thu: 10mi with 3x1mi @ 6:20 (T)
  Sun: 18mi with 8mi @ 6:48 (MP finish)

Week 3 (recovery): 42 miles
  All easy + strides

Week 4 (t_emphasis): 65 miles
  Thu: 12mi with 2x3mi @ 6:20 (T) + strides
  Sun: 20mi easy

Week 5 (mp_emphasis): 70 miles
  Tue: 14mi with 8mi @ 6:48 (MP)
  Thu: 12mi with 8mi @ 6:20 (T straight)
  Sun: 20mi with 14mi @ 6:48 (MP)

Week 6 (peak_mp): 72 miles
  Tue: 12mi with 6mi @ 6:48 (MP)
  Thu: 10mi + 8x100m strides
  Sun: 24mi with 18mi @ 6:48 (RACE SIMULATION)

Week 7 (taper_1): 50 miles
  Thu: 10mi with 4mi @ 6:20 (T)
  Sun: 14mi easy (fast finish)

Week 8 (tune_up): 32 miles
  Tue: 8mi + strides
  Sat: 10-MILE RACE (6:20 pace)
  Sun: 4mi recovery

Week 9 (race_week): 44 miles
  Wed: 5mi + strides
  Sat: 3mi shakeout
  Sun: MARATHON (target 7:00-7:15)
```

---

*This ADR establishes the framework for truly personalized training that uses the athlete as the blueprint, not generic templates.*
