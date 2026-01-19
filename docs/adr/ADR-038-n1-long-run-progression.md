# ADR-038: N=1 Long Run Progression Algorithm

## Status
**Proposed**

## Date
2026-01-17

## Context

### The Bug

The current `WorkoutPrescriptionGenerator` produces dangerous long run progression:

| Week | Phase | Long Run | Jump |
|------|-------|----------|------|
| 1 | rebuild | 6.7 mi | - |
| 2 | rebuild | 8.4 mi | +1.7 |
| 3 | rebuild | 10.1 mi | +1.7 |
| **4** | **build** | **21.9 mi** | **+11.8 (117%)** |
| 5 | build | 21.9 mi | 0 |
| 6 | peak | 22.0 mi | +0.1 |

A 117% increase in one week violates basic training principles and is dangerous.

### Root Cause Analysis

The bug is in `workout_prescription.py`:

```python
# Line 278 - sets start to PEAK, not current
self.long_run_start = max(self.bank.peak_long_run_miles, 10)  # → 22 miles
```

**REBUILD phases** use volume-based calculation (lines 468-487):
```python
miles_per_run = target_miles / len(available_days)
assignments[long_day] = ("easy_long", miles_per_run * 1.4)  # → 7-10 miles
```

**BUILD phases** use `calculate_long_run_for_week` which starts from PEAK:
```python
target_this_week = self.long_run_start + (weeks_of_building * progression_rate)
# With long_run_start = 22: immediately jumps to 22+ miles
```

**Result**: No continuity between rebuild (~10mi) and build (22mi).

### The N=1 Violation

The athlete's data shows:
- **Recent long run**: 12 miles (Jan 13)
- **Average long run** (6 months): 14.6 miles
- **Peak long run**: 22 miles
- **19 weeks** with long runs >= 13 miles

But the algorithm ignores this data. It uses:
- Population formula for rebuild (`target_miles / days * 1.4`)
- Peak-based calculation for build (`long_run_start = peak`)

Neither approach queries the athlete's actual current or average long run.

### Reference: Better Implementation Exists

`model_driven_plan_generator.py` has a better approach in `_get_established_baseline()`:
- Calculates `long_run_miles` (typical) from history
- Calculates `peak_long_run_miles` from history  
- Uses progressive scaling: `build_pct = 0.75 + (0.20 * progress)`

The fix should bring this N=1 approach to `WorkoutPrescriptionGenerator`.

## Decision

### 1. Extend FitnessBank with Current Long Run Data

Add to `FitnessBank` dataclass:

```python
# In fitness_bank.py
@dataclass
class FitnessBank:
    # Existing fields...
    
    # NEW: Current long run capability (from recent data)
    current_long_run_miles: float      # Max long run in last 4 weeks
    average_long_run_miles: float      # Average of all long runs >= 10mi
```

Calculation in `FitnessBankCalculator._calculate_peak_capabilities()`:

```python
def _calculate_current_long_run(self, activities: List) -> Tuple[float, float]:
    """
    Calculate current and average long run from activity data.
    
    N=1: Uses athlete's actual data, not population formulas.
    """
    today = date.today()
    four_weeks_ago = today - timedelta(days=28)
    
    recent_long_runs = []
    all_long_runs = []
    
    for a in activities:
        miles = (a.distance_m or 0) / 1609.344
        
        # Long run threshold: 10+ miles OR 90+ minutes
        duration_min = (a.duration_s or 0) / 60
        if miles >= 10 or duration_min >= 90:
            all_long_runs.append(miles)
            
            if a.start_time.date() >= four_weeks_ago:
                recent_long_runs.append(miles)
    
    current = max(recent_long_runs) if recent_long_runs else 0.0
    average = sum(all_long_runs) / len(all_long_runs) if all_long_runs else 0.0
    
    return current, average
```

### 2. Rewrite Long Run Progression Algorithm

Replace the current broken logic with N=1 progression:

```python
# In workout_prescription.py

class WorkoutPrescriptionGenerator:
    def __init__(self, bank: FitnessBank, race_distance: str = "marathon"):
        # ...existing init...
        
        # N=1 Long Run Progression
        # Start from CURRENT capability (what they're actually doing)
        # Progress to PEAK capability (what they've proven they can do)
        self.long_run_current = max(
            bank.current_long_run_miles,
            bank.average_long_run_miles * 0.7,  # Floor: 70% of average
            8.0  # Absolute minimum for any distance
        )
        
        # Peak target based on race distance AND proven capability
        distance_peak = self.LONG_RUN_PEAK_TARGETS.get(race_distance, 18)
        proven_peak = bank.peak_long_run_miles
        
        # Use proven capability if they've shown they can do it
        if proven_peak >= distance_peak * 0.9:
            self.long_run_peak = proven_peak
        else:
            self.long_run_peak = min(distance_peak, proven_peak + 4)  # Allow 4mi stretch max
        
        logger.info(
            f"N=1 Long Run Progression: "
            f"current={self.long_run_current:.1f}mi → "
            f"peak={self.long_run_peak:.1f}mi | "
            f"proven_peak={proven_peak:.1f}mi | "
            f"distance={race_distance}"
        )
    
    def calculate_long_run_for_week(self, week_number: int, total_weeks: int, 
                                     theme: WeekTheme) -> float:
        """
        Calculate long run distance using N=1 progression.
        
        Algorithm:
        1. Start from current capability (not peak)
        2. Progress linearly to peak over build weeks
        3. Apply phase-specific adjustments
        4. Respect safety constraints (max weekly increase)
        """
        # Taper/race weeks: reduce from peak
        if theme in [WeekTheme.TAPER_1, WeekTheme.TAPER_2, WeekTheme.RACE]:
            taper_pct = {
                WeekTheme.TAPER_1: 0.70,
                WeekTheme.TAPER_2: 0.55,
                WeekTheme.RACE: 0.40,
            }
            return self.long_run_peak * taper_pct.get(theme, 0.60)
        
        # Recovery weeks: mid-point between current and peak
        if theme == WeekTheme.RECOVERY:
            return self.long_run_current + (self.long_run_peak - self.long_run_current) * 0.5
        
        # Calculate build progression
        # Reserve last 3 weeks for taper
        build_weeks = max(1, total_weeks - 3)
        
        # Progress factor: 0.0 at week 1, 1.0 at peak week
        progress = min(1.0, (week_number - 1) / build_weeks)
        
        # Linear progression from current to peak
        target = self.long_run_current + (self.long_run_peak - self.long_run_current) * progress
        
        # Safety: max 2 miles increase per week
        if week_number > 1:
            max_increase = 2.0  # miles
            prev_week_target = self.long_run_current + (self.long_run_peak - self.long_run_current) * ((week_number - 2) / build_weeks)
            target = min(target, prev_week_target + max_increase)
        
        # Apply time safety (3 hours max)
        long_pace = self.paces.get("long", 9.0)
        time_limit = 180 / long_pace  # 180 minutes
        target = min(target, time_limit)
        
        return target
```

### 3. Unify Rebuild and Build Logic

Remove the separate volume-based calculation for rebuild weeks. All phases use the same progression:

```python
def _assign_days_by_theme(self, theme: WeekTheme, target_miles: float,
                          week_number: int = 1, total_weeks: int = 12):
    """
    Assign workout types and miles to days based on theme.
    
    CHANGE: All phases now use progressive long run calculation.
    """
    # Progressive long run for ALL phases
    progressive_long = self.calculate_long_run_for_week(week_number, total_weeks, theme)
    
    # ... rest of assignment logic uses progressive_long
```

### 4. Audit Logging

Every long run prescription logs:

```python
logger.info(
    f"Long run prescribed: week={week_number}, theme={theme.value}, "
    f"target={target:.1f}mi | "
    f"current={self.long_run_current:.1f}, peak={self.long_run_peak:.1f}, "
    f"progress={progress:.2f}"
)
```

## Algorithm Behavior Examples

### Example 1: Elite Athlete Returning from Injury (Michael)
- Current long run: 12 miles
- Average long run: 14.6 miles
- Peak long run: 22 miles
- 9-week plan

| Week | Theme | Long Run | Progression |
|------|-------|----------|-------------|
| 1 | rebuild | 12.0 mi | current |
| 2 | rebuild | 13.7 mi | +1.7 |
| 3 | rebuild | 15.3 mi | +1.6 |
| 4 | build | 17.0 mi | +1.7 |
| 5 | build | 18.7 mi | +1.7 |
| 6 | peak | 20.3 mi | +1.6 |
| 7 | taper | 15.4 mi | (70% of peak) |
| 8 | race | 8.9 mi | (tune-up week) |
| 9 | race | 26.2 mi | marathon |

### Example 2: Intermediate Athlete (No Injury)
- Current long run: 10 miles
- Average long run: 10 miles
- Peak long run: 14 miles
- 12-week plan

| Week | Theme | Long Run |
|------|-------|----------|
| 1 | base | 10.0 mi |
| 4 | build | 11.3 mi |
| 7 | build | 12.7 mi |
| 9 | peak | 14.0 mi |
| 11 | taper | 9.8 mi |
| 12 | race | 13.1 mi |

### Example 3: Beginner (5K Plan)
- Current long run: 4 miles
- Peak target: 8 miles (5K appropriate)
- 8-week plan

| Week | Theme | Long Run |
|------|-------|----------|
| 1 | base | 4.0 mi |
| 4 | build | 6.0 mi |
| 6 | peak | 8.0 mi |
| 8 | race | 3.1 mi |

Same algorithm, different outputs based on each athlete's N=1 data.

## Considered Alternatives

### Option A: Just adjust the cap values
**Rejected**: Still population-based thinking. Doesn't use athlete's actual data.

### Option B: Different formulas for different experience levels
**Rejected**: Creates complexity and edge cases. N=1 should handle all levels with one algorithm.

### Option C: Use model_driven_plan_generator for all plans
**Rejected**: Would require significant refactoring. Better to fix the specific bug in WorkoutPrescriptionGenerator.

## Implementation Plan

### Files Modified

1. `apps/api/services/fitness_bank.py`
   - Add `current_long_run_miles` and `average_long_run_miles` to FitnessBank
   - Add calculation method in FitnessBankCalculator

2. `apps/api/services/workout_prescription.py`
   - Replace `long_run_start` with `long_run_current` and `long_run_peak`
   - Rewrite `calculate_long_run_for_week` to use N=1 progression
   - Update `_assign_days_by_theme` to use progressive_long for all phases
   - Add audit logging

3. `apps/api/tests/test_fitness_bank_framework.py`
   - Add tests for current/average long run calculation
   - Add tests for progression across all experience levels

4. `apps/api/tests/test_long_run_progression.py` (NEW)
   - Comprehensive tests for the new algorithm
   - Edge cases: injury return, no history, all distances

### Tests Required

1. **Unit tests**:
   - `test_current_long_run_calculation`: Verifies correct extraction from recent data
   - `test_progression_injury_return`: 12 → 22 over 6 weeks, max 2mi/week increase
   - `test_progression_healthy_athlete`: Smooth progression without jumps
   - `test_progression_beginner`: Appropriate scaling for low-volume athletes
   - `test_all_distances`: 5k, 10k, 10mi, half, marathon produce appropriate peaks

2. **Integration tests**:
   - `test_full_plan_no_jumps`: No week-to-week increase > 3 miles
   - `test_full_plan_uses_athlete_data`: Long runs reflect athlete's history

### Feature Flag

**Flag**: `plan.n1_long_run_progression`

| State | Behavior |
|-------|----------|
| `off` | Current (broken) behavior |
| `shadow` | Run both, log comparison, serve current |
| `on` | Serve new N=1 progression |

### Rollout Criteria

1. Shadow mode 3 days, zero errors
2. Long runs for returning athletes start from current capability
3. No week-to-week jump > 3 miles in any generated plan
4. Manual review of Michael's plan approved

## Consequences

### Positive
- Long runs progress smoothly from current → peak
- No dangerous 100%+ weekly jumps
- Uses athlete's actual data (N=1)
- Same algorithm works for all experience levels
- Audit logging enables debugging

### Negative
- Slightly more complex than current (broken) logic
- Requires FitnessBank schema change
- Existing tests may need updates

### Mitigations
- Feature flag enables safe rollout
- Comprehensive test coverage
- Audit logging for debugging

## Related ADRs

- ADR-030: Fitness Bank Framework
- ADR-031: Constraint-Aware Planning
- ADR-037: N=1 Phase 2 Training Plan Improvements
